"""M6 混合检索 —— S2 在问答链路里的那一环(串行兜底的最后一棒)。

```
query → ①双路各 Top-30 → ②RRF(k=60) → ③cross-encoder 重排 Top-5
      → ④按 seq 扩上下文 → 交给 generate
```

🩸 **输出契约**(分册 2 §6.0):每条命中必须随身带
`chunk_id / doc_id / 文档名 / page_idx / heading_path / seq / 分数 / figures`。
这些字段在检索这一环丢了后面补不回来 —— 引用落库发生在 generate,不会回头查检索现场。

🩸 **本期不设分数阈值**(`DOC_RAG_MIN_SCORE` 暂缓,分册 2 §8:正负两堆分数重叠)。
"无召回"只指**双路一条都没有**,那时才走兜底话术。

重排的策略(纯 rerank / guard 安全网)与阈值都在 Provider 层
(`app/providers/cross_encoder_rerank.py`),这里只负责按召回名次把候选交给它。
"""

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models import AgentKbBinding, Document, KnowledgeBase
from app.models import Chunk as ChunkRow
from app.providers import get_embedder, get_reranker

log = get_logger(__name__)

#: 英文停用词 —— **必须我们自己去**,理由见 `keyword_terms()`
STOPWORDS = frozenset("""
a an and are as at be been being by for from had has have how i in into is it its
of on or that the this these those to was were what when where which who whom why
with do does did much many can could should would will shall may might must
you your they them their we us our he she his her if then than there here about
""".split())

_TERM_RE = re.compile(r"[a-z0-9][a-z0-9\-.]*")


@dataclass(slots=True)
class DocRagHit:
    """一条最终命中 —— 字段就是要交给 generate 的全部内容。"""

    chunk_id: uuid.UUID
    doc_id: uuid.UUID
    doc_name: str
    seq: int
    page_idx: int
    heading_path: str
    content: str
    figures: list[dict]
    score: float
    rank_vector: int | None = None
    rank_fts: int | None = None
    rrf_score: float = 0.0
    rerank_score: float | None = None
    context_seqs: list[int] = field(default_factory=list)


@dataclass(slots=True)
class DocRagTrace:
    """检索轨迹 —— 演示台要如实显示真实发生的事。"""

    query: str
    vector_hits: int = 0
    fts_hits: int = 0
    fused: int = 0
    reranked: bool = False


# ─── 关键词腿 ─────────────────────────────────────────────────────────────────

def keyword_terms(query: str) -> list[str]:
    """把自然语言问题变成关键词腿真正该用的词。

    🩸 **两个坑必须同时躲开**(沙箱 Step 5 实测):
    ① `plainto_tsquery` 是 **AND 语义**,而 `simple` 分词器**不去停用词** ——
       "how much does it cost to extend the warranty on an HC-430" 会变成
       `how & much & does & it & … & warranty`,**命中 0 条**;
    ② 改成 OR 又会命中几乎全库,而 `ts_rank` **没有 IDF**,
       `the` 与 `warranty` 对分数的贡献一样大,排序就废了。
    解法:**自己去停用词再 OR**。实测命中收敛到十余条,且正确切片排第一。

    Args:
        query: 用户问题原文。

    Returns:
        去掉停用词后的小写词列表;全是停用词时为空(调用方据此跳过这条腿)。
    """
    return [t for t in _TERM_RE.findall(query.lower()) if t not in STOPWORDS]


async def _search_fts(
    session: AsyncSession, query: str, kb_ids: list[uuid.UUID] | None, top_k: int
) -> list[tuple[uuid.UUID, float]]:
    """去停用词 → 逐词 `plainto_tsquery` 用 `||` 并起来 → `ts_rank` 排序。

    逐词交给 `plainto_tsquery` 而不是自己拼 `to_tsquery` 字符串:
    词里带 `:`、`&`、`!` 时手拼会让解析器报错,交给它则一律安全。

    🩸 `status = 'active'`:**这条过滤在两条腿上各有一份**,改了这里就得改
    `_search_vector`,漏一条就是"下线了还能被搜到"(DB-DESIGN §3)。
    """
    terms = keyword_terms(query)
    if not terms:
        return []

    params: dict[str, object] = {f"t{i}": t for i, t in enumerate(terms)}
    params["top_k"] = top_k
    ors = " || ".join(f"plainto_tsquery('simple', :t{i})" for i in range(len(terms)))
    kb_filter = ""
    if kb_ids is not None:
        params["kb_ids"] = list(kb_ids)
        kb_filter = "AND d.kb_id IN :kb_ids"

    sql = text(
        f"""
        WITH q AS (SELECT ({ors}) AS tq)
        SELECT c.id, ts_rank(c.tsv, q.tq) AS score
        FROM chunks c JOIN documents d ON d.id = c.doc_id, q
        WHERE c.tsv @@ q.tq AND c.status = 'active' {kb_filter}
        ORDER BY score DESC
        LIMIT :top_k
        """
    )
    if kb_ids is not None:
        # IN :param 要显式声明成可展开的,否则 SQLAlchemy 把列表当单个值绑进去
        sql = sql.bindparams(bindparam("kb_ids", expanding=True))
    rows = (await session.execute(sql, params)).all()
    return [(row[0], float(row[1])) for row in rows]


async def _search_vector(
    session: AsyncSession, query: str, kb_ids: list[uuid.UUID] | None, top_k: int
) -> list[tuple[uuid.UUID, float]]:
    """pgvector 余弦 Top-K。

    余弦相似度 = `1 - cosine_distance`。**距离算子必须是 cosine**
    (HNSW 索引建在 `vector_cosine_ops` 上):换成 L2 分数会静默偏移。

    🩸 `status == "active"`:另一份在 `_search_fts`,见那边的说明。
    禁用时 embedding 已被清空,`is_not(None)` 其实也挡得住 —— 但**不能只靠它**:
    那是"顺便挡住了",不是"写明了要挡"。
    """
    qvec = (await get_embedder().embed([query]))[0]
    distance = ChunkRow.embedding.cosine_distance(qvec)
    stmt = (
        select(ChunkRow.id, distance.label("distance"))
        .join(Document, Document.id == ChunkRow.doc_id)
        .where(ChunkRow.embedding.is_not(None), ChunkRow.status == "active")
        .order_by(distance)
        .limit(top_k)
    )
    if kb_ids is not None:
        stmt = stmt.where(Document.kb_id.in_(kb_ids))
    rows = (await session.execute(stmt)).all()
    return [(cid, 1.0 - float(dist)) for cid, dist in rows]


# ─── 融合 ─────────────────────────────────────────────────────────────────────

def rrf(runs: list[list[uuid.UUID]], k: int) -> list[tuple[uuid.UUID, float]]:
    """Reciprocal Rank Fusion:`Σ 1/(k + 名次)`,只吃名次不吃分数。

    两条腿的分数量纲根本不同(余弦 0–1 vs `ts_rank` 0.0x),**不能直接相加** ——
    这正是 RRF 存在的理由。

    Args:
        runs: 每条腿的命中 id 列表,已按各自分数降序。
        k: 平滑常数,越大越拉平名次差异。

    Returns:
        `[(chunk_id, 融合分), ...]`,按融合分降序。
    """
    scores: dict[uuid.UUID, float] = {}
    for run in runs:
        for rank, cid in enumerate(run, 1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])


async def _load_chunks(
    session: AsyncSession, chunk_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[ChunkRow, str]]:
    """按 id 取回切片行与它所属的文档名。"""
    if not chunk_ids:
        return {}
    stmt = (
        select(ChunkRow, Document.name)
        .join(Document, Document.id == ChunkRow.doc_id)
        .where(ChunkRow.id.in_(chunk_ids))
    )
    return {row.id: (row, name) for row, name in (await session.execute(stmt)).all()}


async def _context_seqs(
    session: AsyncSession, doc_id: uuid.UUID, seq: int, span: int
) -> list[int]:
    """命中片前后各 `span` 片里**真实存在**的 seq(合并过会留空洞)。

    只记 seq 不拼正文:拼不拼、拼多少由生成阶段决定,检索这一环别替它做主。
    """
    if span <= 0:
        return []
    stmt = select(ChunkRow.seq).where(
        ChunkRow.doc_id == doc_id,
        ChunkRow.seq.between(seq - span, seq + span),
        ChunkRow.seq != seq,
    )
    return sorted(int(s) for s in (await session.execute(stmt)).scalars().all())


# ─── 公共入口 ─────────────────────────────────────────────────────────────────

async def agent_document_kb_ids(session: AsyncSession, agent_id: uuid.UUID) -> list[uuid.UUID]:
    """这个 Agent 绑了哪些文档 RAG 库(没绑就返回空,调用方据此整条跳过)。"""
    stmt = (
        select(AgentKbBinding.kb_id)
        .join(KnowledgeBase, KnowledgeBase.id == AgentKbBinding.kb_id)
        .where(AgentKbBinding.agent_id == agent_id, KnowledgeBase.type == "document")
    )
    return list((await session.execute(stmt)).scalars().all())


async def retrieve(
    session: AsyncSession,
    query: str,
    *,
    kb_ids: list[uuid.UUID] | None = None,
    top_n: int | None = None,
) -> tuple[list[DocRagHit], DocRagTrace]:
    """跑完整条检索链,返回命中与轨迹。

    Args:
        session: 数据库会话。
        query: 用户问题。
        kb_ids: 限定知识库;`None` 表示不限,空列表表示"不该命中任何东西"。
        top_n: 返回条数,默认 `DOC_RAG_RERANK_TOPN`。

    Returns:
        `(命中列表, 轨迹)`;双路都没召回时命中为空,由上层走兜底话术。
    """
    trace = DocRagTrace(query=query)
    if kb_ids is not None and not kb_ids:
        return [], trace

    limit = top_n if top_n is not None else settings.doc_rag_rerank_topn
    vector = await _search_vector(session, query, kb_ids, settings.doc_rag_vector_topk)
    fts = await _search_fts(session, query, kb_ids, settings.doc_rag_fts_topk)
    trace.vector_hits, trace.fts_hits = len(vector), len(fts)

    fused = rrf([[c for c, _ in vector], [c for c, _ in fts]], settings.doc_rag_rrf_k)
    trace.fused = len(fused)
    if not fused:
        log.info("doc_rag_no_recall", query=query[:120])
        return [], trace

    rows = await _load_chunks(session, [c for c, _ in fused])
    ordered = [(cid, s) for cid, s in fused if cid in rows]
    rrf_of = dict(ordered)
    vector_rank = {cid: i for i, (cid, _) in enumerate(vector, 1)}
    fts_rank = {cid: i for i, (cid, _) in enumerate(fts, 1)}

    # 🩸 **必须按 RRF 名次传给重排**:guard 触发时 Provider 原序返回,靠的就是这个顺序
    candidates = [cid for cid, _ in ordered]
    hits = await get_reranker().rerank(query, [rows[cid][0].content for cid in candidates], limit)
    trace.reranked = True

    results: list[DocRagHit] = []
    for hit in hits:
        cid = candidates[hit.index]
        row, doc_name = rows[cid]
        meta = row.meta or {}
        results.append(
            DocRagHit(
                chunk_id=row.id,
                doc_id=row.doc_id,
                doc_name=doc_name,
                seq=row.seq,
                page_idx=int(meta.get("page_idx", 0)),
                heading_path=row.heading_path or "",
                content=row.content,
                figures=list(meta.get("figures") or []),
                score=hit.score,
                rank_vector=vector_rank.get(cid),
                rank_fts=fts_rank.get(cid),
                rrf_score=rrf_of[cid],
                rerank_score=hit.score,
                context_seqs=await _context_seqs(
                    session, row.doc_id, row.seq, settings.doc_rag_context_expand
                ),
            )
        )

    log.info(
        "doc_rag_retrieved",
        query=query[:120],
        vector=trace.vector_hits,
        fts=trace.fts_hits,
        fused=trace.fused,
        returned=len(results),
        top_score=round(results[0].score, 3) if results else None,
    )
    return results, trace


async def index_stats(session: AsyncSession) -> dict:
    """索引概况(冒烟脚本与运维面板用)。"""
    total = int((await session.execute(select(func.count(ChunkRow.id)))).scalar_one())
    vectored = int((await session.execute(select(func.count(ChunkRow.embedding)))).scalar_one())
    return {"chunks": total, "with_embedding": vectored}
