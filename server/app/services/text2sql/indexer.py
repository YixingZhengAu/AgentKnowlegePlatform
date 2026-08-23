"""索引面的建立与重建 —— `intent_vectors` 一面一行。

★ **索引面 = 意图摘要 + 每条相似问法,各自一行**;意图的 `brief` 不入索引
(B7 消融实测:加不加它,命中、均分、均边距全不变,却制造 3 条意图间自洽性冲突)。
一个意图的得分 = 它所有面得分的最大值(命中哪一句问法都算命中这个意图)。

★ **空路由负例面也住这张表**,`intent_id IS NULL`。它必须和真意图在同一次比较里竞争,
才可能"比所有真意图都更像" —— 换成单独一张表、单独比一次,就退化成又一个阈值。

★ **维护规则:一变就全删重建**(不做增量 diff),与 S1 的 `exact_qa_vectors` 同一条纪律:
  * 意图发布 / 相似问法保存 → 重建该 intent 的全部面;
  * 负例面保存 → 重建该 kb 下的全部负例面;
  * 意图下线 → 删它的面(正式行留着可追溯)。
一个意图的面只有 8–9 条,重建的成本是一次 embedding 调用;而增量维护要处理
"改了摘要、删了一条问法、又加回来"的组合,是纯粹的自找麻烦。

★ 写入前 L2 归一化(见 `retrieve.py` 顶部关于归一化的那段):让本地点积等于
pgvector 的余弦,好让冒烟脚本能把两条算路对上号。
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import IntentQuestion, IntentVector, SqlIntent
from app.providers import get_embedder
from app.services.text2sql import retrieve as rt
from app.services.text2sql.questions import _strip_prefix

log = get_logger(__name__)


async def _embed_normalized(texts: list[str]) -> list[list[float]]:
    return [rt.normalize(v) for v in await get_embedder().embed(texts)]


def intent_faces(intent: SqlIntent, questions: list[str]) -> list[tuple[str, str]]:
    """一个意图的全部索引面 [(face_kind, text)],摘要在前,去重且保持顺序。

    去重是必须的:`intent_vectors` 没有唯一约束,但同一句话嵌两遍纯属浪费,
    而且会让"哪一类面在干活"的统计失真 —— 人在界面上完全可能把某条相似问法
    改成与摘要一模一样。
    """
    seen: dict[str, str] = {}
    summary = _strip_prefix(intent.one_liner)
    if summary.strip():
        seen[summary] = rt.FACE_SUMMARY
    for q in questions:
        q = (q or "").strip()
        if q and q not in seen:
            seen[q] = rt.FACE_QUESTION
    return [(kind, text) for text, kind in seen.items()]


async def rebuild_intent_faces(session: AsyncSession, intent: SqlIntent) -> int:
    """全删重建一个意图的索引面。返回写入的面数。

    **不 commit**:发布是一个事务(写正式表 + 建索引),提交由调用方统一做 ——
    向量写失败时那个意图不该已经是 published 状态。
    """
    await session.execute(delete(IntentVector).where(IntentVector.intent_id == intent.id))
    if intent.status != "published":
        # 下线/草稿的意图不参与检索:面删掉就行,不用重建
        return 0
    questions = list((await session.scalars(
        select(IntentQuestion.question_text)
        .where(IntentQuestion.intent_id == intent.id)
        .order_by(IntentQuestion.created_at, IntentQuestion.question_text)
    )).all())
    faces = intent_faces(intent, questions)
    if not faces:
        return 0
    vectors = await _embed_normalized([text for _, text in faces])
    session.add_all([
        IntentVector(kb_id=intent.kb_id, intent_id=intent.id, face_kind=kind,
                     face_text=text, embedding=vec)
        for (kind, text), vec in zip(faces, vectors, strict=True)
    ])
    log.info("intent_faces_rebuilt", intent=intent.code, faces=len(faces))
    return len(faces)


async def drop_intent_faces(session: AsyncSession, intent_id: uuid.UUID) -> None:
    """意图下线:删它的面,它立刻不再参与检索(正式行留着可追溯)。"""
    await session.execute(delete(IntentVector).where(IntentVector.intent_id == intent_id))


async def rebuild_non_data_faces(session: AsyncSession, kb_id: uuid.UUID) -> int:
    """全删重建一个 kb 的空路由负例面。返回写入的面数。"""
    await session.execute(
        delete(IntentVector).where(
            IntentVector.kb_id == kb_id, IntentVector.intent_id.is_(None)))
    texts = await rt.load_non_data_faces(session, kb_id)
    if not texts:
        # 允许为空,但这等于关掉空路由 —— 记一条日志,别让它静默发生
        log.warning("non_data_faces_empty", kb_id=str(kb_id))
        return 0
    vectors = await _embed_normalized(texts)
    session.add_all([
        IntentVector(kb_id=kb_id, intent_id=None, face_kind=rt.FACE_NON_DATA,
                     face_text=text, embedding=vec)
        for text, vec in zip(texts, vectors, strict=True)
    ])
    log.info("non_data_faces_rebuilt", kb_id=str(kb_id), faces=len(texts))
    return len(texts)


async def index_size(session: AsyncSession, kb_id: uuid.UUID) -> dict[str, int]:
    """(已发布意图数, 各类面的行数)—— 给冒烟脚本与前端的漏斗计数用。"""
    intents = len((await session.scalars(
        select(SqlIntent.id).where(SqlIntent.kb_id == kb_id,
                                   SqlIntent.status == "published"))).all())
    kinds = (await session.execute(
        select(IntentVector.face_kind, IntentVector.id).where(IntentVector.kb_id == kb_id)
    )).all()
    out = {"intents": intents, "faces": len(kinds)}
    for kind in (rt.FACE_SUMMARY, rt.FACE_QUESTION, rt.FACE_NON_DATA):
        out[kind] = sum(1 for k, _ in kinds if k == kind)
    return out
