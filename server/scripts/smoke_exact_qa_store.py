"""存储层冒烟(连库 + 联网):灌 fixture 候选 → 逐条采纳 → pgvector 查回 → **与手算余弦对数**。

★ 这个脚本存在的唯一理由是那个 1e-3 断言:
"内存 numpy 索引换 pgvector"是纯机械劳动,但**唯一真会出错的地方就是距离算子与归一化**
(选成 L2、或者忘了 pgvector 的 cosine_distance 已经内建归一化)。
选错了不会报错,只会让分数静默偏移几个百分点 —— 而 Step 5 花了一整轮调出来的
hit=0.55 / borderline=0.40 全部作废,表现出来就是"演示时该命中的不命中"。
所以这里拿**同一份向量**在 Python 里手算一遍余弦,和库里返回的分数比。

⚠ 实测踩到的坑(第一版写错了):不能"再调一次 embedding 然后跟库里的分数比" ——
**OpenAI 的 embedding 跨批次不确定**:同一句话单独一批与和别人拼一批,
两个向量的余弦是 0.99942(逐维最大差 3e-3),传到分数上就是 ~2e-3 的偏差。
第一版按 1e-3 断言必然红,但那红的不是算子而是"两个不同的向量"。
所以对数必须**读回库里存的那一份向量**,两边用同一个 query 向量 —— 这才只剩算子与精度。
副产品结论:**阈值只在 ±0.005 的尺度上有意义,不要调到小数点后三位**。

前置:`make db-reset`(或 make db + migrate + seed)、`.env` 里的 OPENAI_API_KEY。
跑法:cd server && uv run python -m scripts.smoke_exact_qa_store
"""

import asyncio
import json
import math
import pathlib
import sys
import uuid

from sqlalchemy import delete, func, select

from app.core.errors import AppError
from app.db import SessionLocal
from app.models import (
    ExactQaItem,
    ExactQaVector,
    IngestJob,
    KnowledgeBase,
    PublishRecord,
    StagingItem,
    User,
)
from app.models.user import DEFAULT_USERNAME
from app.providers import get_embedder
from app.schemas.exact_qa import QaCandidateSet
from app.services.exact_qa.indexer import index_size
from app.services.exact_qa.publisher import accept_candidate, disable_item, reject_candidate
from app.services.exact_qa.retriever import retrieve

#: 抽取+相似问的定型产物(36 条候选 / 180 个索引面),S1 Step 4 实测产出的那一份。
#: 存成 fixture 是为了让存储层的对数不用每次先花钱跑一遍抽取。
FIXTURE_QA = pathlib.Path(__file__).resolve().parent / "fixtures" / "qa_with_similar.json"

#: 采纳几条就够验通路(每条要付一次 embedding 的钱)。
#: 必须点名把"层数"那条挑进来 —— 否则正例探针在库里没有对应知识,分档验的就不是分档了。
ACCEPT_N = 8
MUST_INCLUDE = "convolutional layers"

#: 对数用的查询:正例 / 越界 / 困难负例各一条(取自 S1 Step 5 的人写评测集)
PROBES = [
    ("正例    ", "how many conv layers are in the yolov3 backbone"),
    ("越界负例", "How do I reset my password for the portal?"),
    ("困难负例", "How many convolutional layers does Darknet-19 have?"),
]

TOLERANCE = 1e-3


def cosine(a: list[float], b: list[float]) -> float:
    """手算余弦(不依赖 numpy):分数的第二个来源,用来给库里的分数对数。"""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


async def _reset(session) -> tuple[uuid.UUID, uuid.UUID]:
    """清掉上一次冒烟的痕迹,建一个 kb=exact_qa 的假 qa_extract job。"""
    kb = (
        await session.execute(
            select(KnowledgeBase).where(KnowledgeBase.type == "exact_qa").limit(1)
        )
    ).scalar_one_or_none()
    if kb is None:
        raise SystemExit("没有 exact_qa 类型的知识库,请先 make seed")
    user = (
        await session.execute(select(User).where(User.username == DEFAULT_USERNAME))
    ).scalar_one_or_none()
    if user is None:
        raise SystemExit(f"没有默认用户 {DEFAULT_USERNAME},请先 make seed")

    old = (
        (
            await session.execute(
                select(IngestJob.id).where(
                    IngestJob.job_type == "qa_extract",
                    IngestJob.params["smoke"].as_boolean().is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for job_id in old:
        # 正式表不挂在 job 上,得先按 source_staging_id 找回来删(否则每次冒烟越积越多)
        staging_ids = (
            (await session.execute(select(StagingItem.id).where(StagingItem.job_id == job_id)))
            .scalars()
            .all()
        )
        if staging_ids:
            await session.execute(
                delete(ExactQaItem).where(ExactQaItem.source_staging_id.in_(staging_ids))
            )
        await session.execute(delete(PublishRecord).where(PublishRecord.job_id == job_id))
        await session.execute(delete(IngestJob).where(IngestJob.id == job_id))  # staging 级联删
    await session.commit()

    job = IngestJob(
        kb_id=kb.id,
        job_type="qa_extract",
        status="review",  # 逐条采纳只在 review 态受理(assert_reviewable)
        steps=[{"name": "extract", "title": "Extract QA pairs"}],
        params={"smoke": True},
        progress=100,
        created_by=user.id,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job.id, user.id


async def main() -> int:
    if not FIXTURE_QA.exists():
        raise SystemExit(f"缺 fixture {FIXTURE_QA}")
    cs = QaCandidateSet.model_validate_json(FIXTURE_QA.read_text())
    picked = [c for c in cs.candidates if MUST_INCLUDE in c.standard_question.lower()]
    picked += [c for c in cs.candidates if c not in picked][: max(ACCEPT_N - len(picked), 0)]
    rejected = next(c for c in cs.candidates if c not in picked)
    print(f"[store] fixture {len(cs.candidates)} 条候选 → 取 {len(picked)} 条 | {FIXTURE_QA.name}")

    async with SessionLocal() as session:
        job_id, user_id = await _reset(session)

        # ① 灌候选(= qa_extract Job 的 stage 步骤会做的事)
        rows = [
            StagingItem(
                job_id=job_id,
                kb_id=(await session.get(IngestJob, job_id)).kb_id,
                item_type="qa_pair",
                payload=c.as_payload(),
                origin_ref=c.origin_ref.model_dump(exclude_none=True),
                confidence=c.confidence,
            )
            for c in [*picked, rejected]
        ]
        session.add_all(rows)
        await session.commit()
        print(f"① 写入 {len(rows)} 条 staging_items(job={job_id})")

        # ② 逐条采纳(采纳即发布:写正式表 + 建向量索引,一个事务)
        for staging in rows[:-1]:
            await accept_candidate(session, staging, user_id=user_id)
        await reject_candidate(
            session, rows[-1], note="smoke: not a useful QA", user_id=user_id
        )
        items, faces = await index_size(session)
        print(f"② 采纳 {len(picked)} 条 + 不采纳 1 条 → 正式 QA {items} 条 / 索引面 {faces} 行")
        assert items >= len(picked), "正式表条数不对"
        expected_faces = sum(len({c.standard_question, *c.similar_questions}) for c in picked)
        assert faces >= expected_faces, f"索引面应有 {expected_faces} 行,实得 {faces}"

        job = await session.get(IngestJob, job_id)
        assert job.status == "published", f"全部裁决完 job 该置 published,实为 {job.status}"
        print(f"   job 状态 → {job.status}(全部候选裁决完毕,逐条采纳语义的终态)")

        # ③ ★ 对数:pgvector 的分数 vs 手算余弦(**同一份向量**,只考算子与精度)
        print(f"③ pgvector 分数与手算余弦对数(容差 {TOLERANCE})")
        embedder = get_embedder()
        worst = 0.0
        for label, q in PROBES:
            qv = (await embedder.embed([q]))[0]
            # 用同一个 qv 让库算一次:这正是 retriever.retrieve() 里那条语句
            distance = ExactQaVector.embedding.cosine_distance(qv)
            row = (
                await session.execute(
                    select(ExactQaVector.question_text, ExactQaVector.embedding, distance)
                    .join(ExactQaItem, ExactQaItem.id == ExactQaVector.item_id)
                    .where(ExactQaItem.status == "enabled")
                    .order_by(distance)
                    .limit(1)
                )
            ).one()
            face, stored_vec, dist = row
            pg_score = 1.0 - float(dist)
            manual = cosine(qv, list(stored_vec))  # 读回库里存的那一份,不重新 embed
            diff = abs(manual - pg_score)
            worst = max(worst, diff)
            flag = "✅" if diff < TOLERANCE else "❌"
            print(f"   {flag} {label} pg={pg_score:.6f} 手算={manual:.6f} 差={diff:.2e}")
            print(f"        命中面:{face[:70]}")
            assert diff < TOLERANCE, (
                f"分数不对数(差 {diff:.2e})—— 距离算子或归一化选错了,"
                "Step 5 调出来的阈值会全部作废"
            )
        print(f"   最大偏差 {worst:.2e} < {TOLERANCE} ✅ 算子=cosine,Step 5 的阈值可原样沿用")

        # ④ 分档:走真正的 retrieve()(纯阈值 + 护栏,不开 light 复核)
        print("④ 分档:retrieve() 实跑(不开 light 模型复核,只看阈值 + 区分性 token 护栏)")
        tiers = {}
        for label, q in PROBES:
            result, _ = await retrieve(session, q, use_gate=False)
            best = result.top[0]
            tiers[label] = result
            print(
                f"   {label} [{best.score:.3f}] {result.tier.value}"
                + (f"  护栏缺 {result.guard_missing}" if result.guard_missing else "")
            )
            print(f"        命中面:{best.question_text[:70]}")
        assert tiers["正例    "].tier.value == "hit", "正例应该命中(库里有那条知识)"
        assert tiers["正例    "].answer, "命中必须带上原样返回的答案"
        assert tiers["越界负例"].tier.value == "miss", "越界问题应该 MISS"
        assert tiers["困难负例"].tier.value != "hit", "困难负例不许命中(护栏该拦下 Darknet-19)"
        assert tiers["困难负例"].guard_missing == ["19"], "护栏该报出缺的那个数字"
        ref = tiers["正例    "].origin_ref
        assert ref is not None, "命中要能带出 origin_ref(引用跳原文靠它)"
        print(f"   命中的出处:p{ref.page_idx} bbox={ref.bbox} 「{ref.quote[:50]}…」")

        # ⑤ 下线:删向量行,立刻不再被检索到(正式行保留,历史引用不悬空)
        # **只挑 enabled 的**:库里可能已经有下线过的条目(界面上点过下线),
        # 拿到那种条目就会看到"向量行 0 → 0"而误判成 bug(Step 8 回归时真踩到)
        item_id = (
            await session.execute(
                select(ExactQaItem.id)
                .where(ExactQaItem.status == "enabled")
                .order_by(ExactQaItem.created_at)
                .limit(1)
            )
        ).scalar_one()
        item = await session.get(ExactQaItem, item_id)

        async def face_rows() -> int:
            return (
                await session.execute(
                    select(func.count())
                    .select_from(ExactQaVector)
                    .where(ExactQaVector.item_id == item_id)
                )
            ).scalar_one()

        before = await face_rows()
        await disable_item(session, item)
        after = await face_rows()
        print(f"⑤ 下线一条:向量行 {before} → {after},正式行保留(status={item.status})")
        assert before > 0 and after == 0, "下线必须把向量行删干净,否则它还会被命中"

    print("[store] 全部通过 ✅")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except AppError as exc:
        print(f"[store] 失败({exc.code}): {exc.message}")
        if exc.detail:
            print(f"  detail={json.dumps(exc.detail, ensure_ascii=False)[:400]}")
        sys.exit(1)
