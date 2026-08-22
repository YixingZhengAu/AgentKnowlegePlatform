"""索引面的建立与重建 —— `exact_qa_vectors` 一问一行。

★ **索引面 = 标准问 + 每条相似问,各自一行向量**(与 DB-DESIGN 的一问一行对齐)。
答案本身不进索引:用户问的是问题,拿答案去匹配问题会把"答案里恰好出现的词"当成召回信号。
一条 item 的得分 = 它所有问题面得分的最大值(命中哪一句问法都算命中这条知识)。

★ **维护规则:item 的问题集合一变就全删重建该 item 的向量行**(不做增量 diff)。
理由:一条 QA 的问题面只有 4–6 句,重建的成本是一次 embedding 调用;
而增量维护要处理"改了标准问、删了一条相似问、又加回来"的组合,是纯粹的自找麻烦。

沙箱阶段这层是 numpy 内存矩阵(见 documents/S1-PLAN.md §5 M4),换成 pgvector 时
**唯一真正会出错的地方是距离算子与归一化** —— 选错了分数会静默偏移,阈值全部作废。
所以 `scripts/smoke_exact_qa_store.py` 强制对数:同一 query 的 pgvector 分数与
本地余弦手算值必须差 < 1e-3。
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import ExactQaItem, ExactQaVector
from app.providers import get_embedder

log = get_logger(__name__)


def index_faces(item: ExactQaItem) -> list[str]:
    """一条 QA 的全部问题面(标准问在前),去重且保持顺序。

    去重是必须的:`exact_qa_vectors` 上有 (item_id, question_text) 唯一约束,
    而人在审核台上完全可能把某条相似问改成与标准问一样。
    """
    faces: dict[str, None] = {}
    for q in [item.standard_question, *(item.similar_questions or [])]:
        q = (q or "").strip()
        if q:
            faces.setdefault(q, None)
    return list(faces)


async def rebuild_item_vectors(session: AsyncSession, item: ExactQaItem) -> int:
    """全删重建一条 item 的向量行。返回写入的行数(= 索引面数)。

    **不 commit**:采纳是一个事务(写正式表 + 建索引),提交由调用方统一做 ——
    向量写失败时那条 QA 不该已经出现在正式表里。
    """
    faces = index_faces(item)
    await session.execute(delete(ExactQaVector).where(ExactQaVector.item_id == item.id))
    if not faces:
        return 0
    vectors = await get_embedder().embed(faces)
    session.add_all(
        [
            ExactQaVector(item_id=item.id, question_text=face, embedding=vec)
            for face, vec in zip(faces, vectors, strict=True)
        ]
    )
    log.info("exact_qa_vectors_rebuilt", item_id=str(item.id), faces=len(faces))
    return len(faces)


async def drop_item_vectors(session: AsyncSession, item_id: uuid.UUID) -> None:
    """下线一条 QA:删掉它的索引面,它立刻不再参与检索(正式行留着可追溯)。"""
    await session.execute(delete(ExactQaVector).where(ExactQaVector.item_id == item_id))


async def index_size(session: AsyncSession, kb_id: uuid.UUID | None = None) -> tuple[int, int]:
    """(已启用的 QA 条数, 索引面行数)—— 给冒烟脚本和文档列表的漏斗计数用。"""
    item_stmt = select(ExactQaItem.id).where(ExactQaItem.status == "enabled")
    if kb_id is not None:
        item_stmt = item_stmt.where(ExactQaItem.kb_id == kb_id)
    item_ids = [r[0] for r in (await session.execute(item_stmt)).all()]
    if not item_ids:
        return 0, 0
    faces = (
        await session.execute(
            select(ExactQaVector.id).where(ExactQaVector.item_id.in_(item_ids))
        )
    ).all()
    return len(item_ids), len(faces)
