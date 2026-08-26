"""S2 引用的编号对齐与入选规则(分册 3 §5-3 / §3b)。

为什么这一层必须有单测:两种错法都**不报错**,只是安静地把引用面板做错 ——
① 编号错位:答案里的 `[3]` 指向面板第 2 条,点回原文点到别的切片;
② 入选错:把检索的 Top-5 无条件全挂,一个只用了 1 片的答案显示 5 个出处。
②曾经真的上线过(2026-08-25 实测发现),所以这里逐条钉住。
"""

import uuid

import pytest

from app.core.chat import (
    DOC_RAG_NO_EVIDENCE,
    _doc_rag_citations,
    _doc_rag_context,
    _doc_rag_used,
)
from app.services.document.retriever import DocRagHit


def _hit(seq: int) -> DocRagHit:
    return DocRagHit(
        chunk_id=uuid.uuid4(),
        doc_id=uuid.uuid4(),
        doc_name="handbook.pdf",
        seq=seq,
        page_idx=seq,
        heading_path=f"Handbook > Section {seq}",
        content=f"Body of chunk {seq}.",
        figures=[],
        score=1.0 - seq / 10,
    )


@pytest.fixture
def hits() -> list[DocRagHit]:
    return [_hit(i) for i in range(5)]


# ─── 编号对齐 ─────────────────────────────────────────────────────────────────

def test_prompt_numbering_matches_citation_seq(hits):
    """🩸 RAG 最经典的错位点:prompt 里的 `[n]` 必须 ≡ `message_citations.seq`。"""
    context = _doc_rag_context(hits)["content"]
    citations = _doc_rag_citations(hits)
    assert [c["seq"] for c in citations] == [1, 2, 3, 4, 5]
    for citation, hit in zip(citations, hits, strict=True):
        # 第 n 块的正文,必须紧跟在 prompt 里的 `[n]` 之后
        marker = f"[{citation['seq']}] "
        block = context.split(marker, 1)[1]
        assert hit.content in block.split("\n[", 1)[0]
        assert citation["ref_id"] == str(hit.chunk_id)


def test_context_carries_locating_metadata(hits):
    """证据块要带文档名/标题/页码 —— 模型据此说"手册第 3 页写着…"。"""
    context = _doc_rag_context(hits)["content"]
    assert "handbook.pdf" in context
    assert "Handbook > Section 2" in context
    assert "(page 3)" in context  # page_idx=2 → 人看的第 3 页
    assert DOC_RAG_NO_EVIDENCE in context  # 哨兵句必须在指令里,否则模型无从遵守


# ─── 入选规则(区分派)─────────────────────────────────────────────────────────

def test_only_cited_chunks_survive(hits):
    """答案引了哪几条就留哪几条 —— 不是把候选全挂上。"""
    citations = _doc_rag_citations(hits)
    used = _doc_rag_used("Top-1 is 77.2% [1], measured on a Titan X [4].", citations)
    assert [c["seq"] for c in used] == [1, 4]


def test_numbering_is_not_recompacted(hits):
    """🩸 只引了 [1] 和 [3] 时,面板就是 [1] [3],**中间留空号**。

    把 [3] 重编成 [2],正文里的 [3] 就指向面板第 2 条 —— 又回到错位。
    """
    used = _doc_rag_used("A [1] then C [3].", _doc_rag_citations(hits))
    assert [c["seq"] for c in used] == [1, 3]


def test_sentinel_answer_gets_no_citations(hits):
    """模型明说没找到依据 → 零引用。挂任何出处都是假的。"""
    assert _doc_rag_used(DOC_RAG_NO_EVIDENCE, _doc_rag_citations(hits)) == []


def test_substantive_answer_without_marks_keeps_top1(hits):
    """有实质内容却忘标编号 → 保底留 Top-1。

    显示成"无出处"比多显示一条最相关的材料更糟:那会让有据的答案看着像幻觉。
    """
    used = _doc_rag_used("The warranty runs for ten years.", _doc_rag_citations(hits))
    assert [c["seq"] for c in used] == [1]


def test_out_of_range_marks_are_dropped(hits):
    """模型引了不存在的编号(或照抄了原文自带的文献号)→ 丢掉,保留有效的。"""
    used = _doc_rag_used("See [7] and [2].", _doc_rag_citations(hits))
    assert [c["seq"] for c in used] == [2]


def test_out_of_range_only_falls_back_to_top1(hits):
    """全是越界编号 = 等于没引 —— 走"忘标编号"那一支,而不是挂一条越界的。"""
    used = _doc_rag_used("As reported in [14].", _doc_rag_citations(hits))
    assert [c["seq"] for c in used] == [1]


def test_no_candidates_means_no_citations():
    """没召回就没引用 —— 引用只能来自检索到的证据,生成的内容不许编引用。"""
    assert _doc_rag_used("Anything at all [1].", []) == []
