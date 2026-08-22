"""精准问答冒烟(联网):三个 LLM 调用点各真调一次,验通路。

照 `smoke_llm.py` 的套路。**为什么必须有这一条**:沙箱里三处结构化输出用的是
openai SDK 的 `responses.parse(text_format=Model)`,集成后换成 Provider 层的
`complete(json_schema=...)` —— 请求形状换了,离线单测碰不到这一段。

跑法:cd server && uv run python -m scripts.smoke_exact_qa
"""

import asyncio
import sys
import time

from app.config import settings
from app.core.errors import AppError
from app.schemas.exact_qa import ContentBlock
from app.services.exact_qa.extractor import extract
from app.services.exact_qa.retriever import gate_hit
from app.services.exact_qa.similar_gen import fill_similar

# 一小段真实解析产物的形态(带页标记),够抽出两三条候选,不必付整篇的钱
EXCERPT = """<!-- page: 0 -->

# Darknet-53

We use a new network for performing feature extraction. Our new network is a hybrid approach
between the network used in YOLOv2, Darknet-19, and that newfangled residual network stuff.
Our network uses successive 3x3 and 1x1 convolutional layers but now has some shortcut
connections as well and is significantly larger. It has 53 convolutional layers so we call
it Darknet-53.

Each network is trained with identical settings and tested at 256 x 256, single crop accuracy.
Darknet-53 achieves 77.2 top-1 accuracy on ImageNet and processes 78 frames per second.
"""

BLOCKS = [
    ContentBlock(
        type="text",
        page_idx=0,
        bbox=[100, 200, 900, 400],
        text=EXCERPT.split("-->", 1)[1].strip(),
    )
]


def _cost(results) -> str:
    total = sum((r.cost_usd for r in results), start=type(results[0].cost_usd)(0))
    tokens = sum(r.usage.total_tokens for r in results)
    return f"{tokens} tokens / ${total}"


async def main() -> int:
    print(
        f"[smoke_exact_qa] main={settings.llm_model_main} light={settings.llm_model_light} "
        f"hit={settings.exact_qa_hit_threshold} gate={settings.exact_qa_hit_gate}"
    )

    # ① M2 抽取(main tier,结构化输出 + quote 逐字校验 + bbox 回填)
    print("① extract(main tier)")
    t0 = time.perf_counter()
    cs, results = await extract(
        document_id="smoke",
        source_md_name="paged.md",
        md=EXCERPT,
        blocks=BLOCKS,
    )
    print(f"  {int((time.perf_counter() - t0) * 1000)}ms  {_cost(results)}")
    st = cs.stats
    print(f"  原始 {st.raw_count} → 保留 {st.kept_count},丢弃 {st.dropped or '无'}")
    for c in cs.candidates[:3]:
        print(f"    [{c.confidence:.2f}] p{c.origin_ref.page_idx} {c.standard_question}")
        print(f"        quote: {c.origin_ref.quote[:70]}… bbox={c.origin_ref.bbox}")
    assert cs.candidates, "抽取没有产出任何候选"
    assert all(c.origin_ref.quote for c in cs.candidates), "有候选没带原文引用"

    # ② M3 相似问(light tier,并发 + 两道过滤)
    print("② similar questions(light tier)")
    t0 = time.perf_counter()
    stats, results = await fill_similar(cs, n=4)
    print(f"  {int((time.perf_counter() - t0) * 1000)}ms  {_cost(results)}")
    print(
        f"  原始 {stats['raw']} → 保留 {stats['kept']}(与标准问相同 "
        f"{stats['drop_same_as_standard']} / 跨条冲突 {stats['drop_conflict']} / "
        f"调用失败 {stats['failed']})"
    )
    for q in cs.candidates[0].similar_questions:
        print(f"    · {q}")
    assert stats["kept"] > 0, "一条改写都没留下"

    # ③ M4 命中复核(light tier):正例应放行,困难负例应否决
    print("③ hit gate(light tier)")
    target = next(
        (c for c in cs.candidates if "53" in c.answer or "layer" in c.answer.lower()),
        cs.candidates[0],
    )
    t0 = time.perf_counter()
    ok, _ = await gate_hit(
        "how many conv layers are in darknet-53", target.standard_question, target.answer
    )
    bad, _ = await gate_hit(
        "How many convolutional layers does Darknet-19 have?",
        target.standard_question,
        target.answer,
    )
    print(f"  {int((time.perf_counter() - t0) * 1000)}ms(两次)")
    print(f"  正例  → {ok.answers_the_question}  ({ok.reason})")
    print(f"  负例  → {bad.answers_the_question}  ({bad.reason})")
    assert ok.answers_the_question, "复核把正例否决了(阈值/prompt 有问题)"
    if bad.answers_the_question:
        # 不 assert:单次 LLM 判断有抖动,但它放行了就值得看一眼
        print("  ⚠ 复核放行了 Darknet-19 那条困难负例 —— 护栏(区分性 token)是它的兜底")

    # ④ 复核关的取向:**它只判"答的是不是这个问题",不给答案质量打分**
    #    前两条是 Step 7/8 实际被误否决过的真实案例(答案对、人已采纳,却因为"含糊"
    #    或"太简略"被挡下),固化在这里,以后再动 GATE_PROMPT 就能立刻量出来。
    print("④ hit gate 的取向(简略/含糊的正确答案必须放行,答错对象必须否决)")
    gate_cases = [
        # (应放行?, 用户问法, 库里标准问, 库里答案, 这条测什么)
        (
            True,
            "which gpus provided the runtimes in the yolov3 speed-accuracy plot",
            "What GPUs were used for reporting the runtimes in the YOLOv3 speed–accuracy figure?",
            "The runtimes were from either an NVIDIA M40 or a Titan X GPU, which are described "
            "as basically the same GPU.",
            "含糊(原文自己就不确定)",
        ),
        (
            True,
            "how does yolov3 predict box coordinates",
            "How does YOLOv3 predict bounding box coordinates?",
            "YOLOv3 predicts four coordinates for each bounding box: tx, ty, tw and th.",
            "简略(没展开损失函数与参数化)",
        ),
        (
            False,
            "How many convolutional layers does Darknet-19 have?",
            "How many convolutional layers does Darknet-53 have?",
            "Darknet-53 has 53 convolutional layers.",
            "邻近实体(19 vs 53)",
        ),
        (
            False,
            "What is the mAP of YOLOv3 at 608x608?",
            "What is the mAP of YOLOv3-320 on COCO?",
            "YOLOv3-320 reaches 28.2 mAP on COCO.",
            "不同分辨率(320 vs 608)",
        ),
    ]
    t0 = time.perf_counter()
    verdicts = await asyncio.gather(*[gate_hit(q, sq, a) for _, q, sq, a, _ in gate_cases])
    print(f"  {int((time.perf_counter() - t0) * 1000)}ms({len(gate_cases)} 次,并发)")
    wrong = []
    for (want, _q, _sq, _a, why), (v, _r) in zip(gate_cases, verdicts, strict=True):
        mark = "✅" if v.answers_the_question is want else "❌"
        print(f"  {mark} 期望{'放行' if want else '否决'} 实得{v.answers_the_question} "
              f"[{why}] {v.reason}")
        if v.answers_the_question is not want:
            wrong.append(why)
    assert not wrong, f"复核关取向不对:{wrong} —— gate 只判是否答了这个问题,不给质量打分"

    print("[smoke_exact_qa] 全部通过 ✅")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except AppError as exc:
        print(f"[smoke_exact_qa] 失败({exc.code}): {exc.message}")
        if exc.detail:
            print(f"  detail={exc.detail}")
        sys.exit(1)
