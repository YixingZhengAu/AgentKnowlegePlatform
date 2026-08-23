"""S3 索引层冒烟:pgvector 的余弦 vs 本地手算余弦 **必须对得上**,以及索引自洽性审计。

用法:`uv run python -m scripts.smoke_s3_index`(会调一次 embedding,几分钱)

★ **为什么专门为这件事写一个脚本**(S1 M4 留下的教训,原文照抄一遍):
  向量层迁移时唯一真正会静默出错的地方是**距离算子与归一化**。选错了不会报错,
  只会让分数整体偏移几个百分点 —— 而检索的两道门槛(0.45 / 0.03)是在实测分布上标定的,
  分数一偏,阈值全部作废,症状是"AI 偶尔答错",查起来极贵。
  所以这里强制对数:同一个问题,pgvector 算的 `1 - cosine_distance` 与 Python 手算的
  点积必须差 < 1e-6(向量入库前已 L2 归一化,两者在数学上就该相等)。

★ 第二项是**留一法自洽性审计**:每条索引面把自己排除后再检索,必须检回自己所属的意图。
  检回别的意图的面 = 会把用户主动拉去错的模板,是索引里最有害的一类数据。
  空路由的负例面不作为审计主体(它们本来就该互相像),但**留在索引里当竞争者** ——
  某条相似问法要是更像一句非问数问题,那是真冲突,必须被报出来。
"""

import asyncio
import math
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import IntentVector, KnowledgeBase
from app.services.text2sql import indexer
from app.services.text2sql import retrieve as rt

#: pgvector 与手算的允许差(理论上应为 0,留一点浮点余量)
TOLERANCE = 1e-6

PROBES = [
    "Monthly outbound units for Melbourne and Brisbane over the last year",
    "Who were our biggest customers by revenue in the past 6 months?",
    "What's the warranty period on the HC-300 battery cabinet?",
]

FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILED.append(name)


async def main() -> int:
    async with SessionLocal() as session:
        kb = (await session.scalars(
            select(KnowledgeBase).where(KnowledgeBase.type == "text2sql")
            .order_by(KnowledgeBase.created_at))).first()
        if kb is None:
            raise SystemExit("没有 text2sql 知识库。先跑 seed_minimal + seed_s3_demo")

        size = await indexer.index_size(session, kb.id)
        print(f"索引:{size['intents']} 个已发布意图 / {size['faces']} 条面 "
              f"(摘要 {size['summary']} + 问法 {size['question']} + 空路由 {size['non_data']})\n")
        check("索引面非空", size["faces"] > 0, str(size["faces"]))
        check("空路由面在位(少了它非问数问题会撞进最近的模板)",
              size["non_data"] > 0, str(size["non_data"]))

        # ---- 1. 向量都归一化了吗(手算余弦 == 点积 的前提)
        # 模长在 Python 里算:读回来的就是库里存的那份值,而 PG 侧的 l2_norm() 在
        # vector/halfvec/sparsevec 上都有重载,不加显式类型转换时选不出唯一候选
        # (实测报 AmbiguousFunctionError)—— 为一个断言去拼类型转换不值当
        index = await rt.load_index(session, kb.id)
        norms = [math.sqrt(sum(x * x for x in f["vec"])) for f in index]
        check("入库向量已 L2 归一化", all(abs(n - 1.0) < 1e-5 for n in norms),
              f"模长 {min(norms):.6f}..{max(norms):.6f}")

        # ---- 2. pgvector 的余弦 vs 本地手算
        worst = 0.0
        for probe in PROBES:
            qvec = await rt.embed_query(probe)
            rows = (await session.execute(
                select(IntentVector.face_text,
                       (1 - IntentVector.embedding.cosine_distance(qvec)).label("score"))
                .where(IntentVector.kb_id == kb.id)
                .order_by(IntentVector.embedding.cosine_distance(qvec))
                .limit(5))).all()
            by_text = {f["text"]: f["vec"] for f in index}
            for text, pg_score in rows:
                local = rt.cosine(qvec, by_text[text])
                worst = max(worst, abs(float(pg_score) - local))
        check(f"pgvector 余弦与手算点积一致(差 < {TOLERANCE})", worst < TOLERANCE,
              f"最大偏差 {worst:.3e}")

        # ---- 3. 三个探针的判定结论(顺手把空路由那条最重要的用例钉住)
        print()
        for probe in PROBES:
            r = await rt.retrieve(probe, index)
            top = r["candidates"][0]
            print(f"  {probe[:58]:<58} → {top['intent_id']:<14} "
                  f"{r['top1_score']:.4f} margin={r['margin']:.4f} reason={r['reason']}")
        warranty = await rt.retrieve(PROBES[-1], index)
        check("质保题被空路由拦下(B8 抓到的那个缺陷不许回归)",
              not warranty["is_data_question"] and warranty["reason"] == "null_route",
              f"is_data={warranty['is_data_question']} reason={warranty['reason']}")

        # ---- 4. 留一法自洽性审计
        #
        # 断言只压在**问法面**上,这是刻意的(与 B7 的结论一致):
        #   * 问法面是我们自己生成、自己可改的资产,撞车了就该改 → 硬断言 0 条;
        #   * 摘要面(意图 one-liner)是上游已发布的意图文案,i01↔i02、i15↔i16 两对天生咬得近。
        #     它们不动,而且这两条冲突恰恰是"只索引意图描述会出事"的实证 ——
        #     索引里真正把用户领到对模板的,是问法面,不是那句摘要。
        # 所以摘要面冲突只打印、不判失败;新增的摘要冲突会在这里被看见。
        print()
        findings = rt.audit_index(index)
        q_conflicts = [f for f in findings
                       if not f["ok"] and f["kind"] == rt.FACE_QUESTION]
        s_conflicts = [f for f in findings
                       if not f["ok"] and f["kind"] == rt.FACE_SUMMARY]
        check("问法面留一法审计无冲突(会把用户领到错模板的那一类)",
              not q_conflicts, f"{len(findings)} 条面受审")
        for f in q_conflicts:
            print(f"        ✗ {f['intent_id']} 的问法面检回了 {f['top1_intent']}"
                  f"({f['top1_score']} > 自身 {f['own_score']}):{f['text'][:70]}")
        print(f"  [INFO] 摘要面冲突 {len(s_conflicts)} 条(已知且不修,理由见上方注释)")
        for f in s_conflicts:
            print(f"         · {f['intent_id']} 的摘要检回 {f['top1_intent']}"
                  f"({f['top1_score']} > {f['own_score']}):{f['text'][:60]}")

    print(f"\nS3 INDEX SMOKE: {'ALL PASS' if not FAILED else f'{len(FAILED)} FAILED -> {FAILED}'}")
    return 0 if not FAILED else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
