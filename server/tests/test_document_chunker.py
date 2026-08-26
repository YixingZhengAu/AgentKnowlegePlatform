"""S2 切分层的离线单测 —— ★ 整个 S2 的质量地基。

为什么这一层必须有单测:切分错了**不报错**,只是悄悄给出更差的答案 ——
半句话的切片、被拼没了换行的 JSON、搜不到任何东西的纯标题片。
这些都只能靠断言抓,人眼扫 dump 抓不全。

下面每一条断言背后都有一次真实的返工(注释里的 🩸)。
"""

import pytest

from app.schemas.document import Block, Chunk, ParseOutput
from app.services.document.chunker import (
    FIGURE_PLACEHOLDER,
    build_chunks,
    count_tokens,
    pack_units,
    split_units,
)


def _blocks(*blocks: Block) -> ParseOutput:
    return ParseOutput(doc_name="t", blocks=list(blocks))


def _h(text: str, level: int = 1, path: list[str] | None = None) -> Block:
    return Block(type="text", page_idx=0, text=text, text_level=level, heading_path=path or [])


def _p(text: str, page: int = 0, path: list[str] | None = None) -> Block:
    return Block(type="text", page_idx=page, text=text, heading_path=path or [])


def _fig(img: str = "images/a.jpg", page: int = 0) -> Block:
    return Block(type="table", page_idx=page, img_path=img, table_body="<table></table>")


# ─── 装片:句子边界 ───────────────────────────────────────────────────────────

def test_pack_never_cuts_mid_sentence():
    """二次切只在句子边界下刀 —— 半句话的切片是最难查的质量问题。"""
    sentences = [f"Sentence number {i} is here." for i in range(40)]
    parts = pack_units([(s, False) for s in sentences], max_tokens=40, overlap_tokens=0)
    assert len(parts) > 1
    for part in parts:
        assert part.rstrip().endswith(".")


def test_pack_respects_max_tokens():
    """除非单句本身就超上限,否则每片都在预算内。"""
    units = [(f"Line {i} of the manual.", False) for i in range(60)]
    for part in pack_units(units, max_tokens=50, overlap_tokens=10):
        assert count_tokens(part) <= 50 + 12  # 允许最后一句刚好压线


def test_pack_overlap_is_whole_sentences():
    """重叠回退整句,不按 token 硬切(硬切出来的重叠是半句)。"""
    units = [(f"S{i} text here.", False) for i in range(30)]
    parts = pack_units(units, max_tokens=30, overlap_tokens=12)
    assert len(parts) > 1
    tail = parts[0].split(" ")[-3:]
    assert " ".join(tail) in parts[1]


def test_quote_ending_is_a_sentence_boundary():
    """🩸 `… 2020.”` 这种收尾曾匹配不上,两段被粘成"一句"。"""
    units = split_units('It complies with AS/NZS 4777.2:2020.” The next clause starts here.')
    assert len(units) == 2


def test_url_is_not_shattered_by_ascii_colon():
    """🩸 全角分支曾误写成 ASCII 且零宽,任何冒号后都下刀 —— URL 被切三段。"""
    url = "See http://127.0.0.1:8766/report.html for details."
    assert split_units(url) == [(url, True)]


def test_cjk_join_does_not_insert_spaces():
    """🩸 一律用空格拼会往中文句子里插空格,文本就和原文对不上了。"""
    packed = pack_units(split_units("接口编排执行失败:重试三次仍未成功。"), 512, 0)[0]
    assert " " not in packed


# ─── 切片结构 ─────────────────────────────────────────────────────────────────

def test_seq_is_contiguous():
    """seq 从 0 连续 —— 上下文扩展(取前后片)靠它。"""
    chunks = build_chunks(_blocks(_h("H"), _p("Body one."), _p("Body two.")))
    assert [c.seq for c in chunks] == list(range(len(chunks)))


def test_heading_text_goes_into_content():
    """🩸 `tsv` 只索引 `content`:标题不进正文,标题里的词就永远搜不到。"""
    chunks = build_chunks(_blocks(_h("5. Channel Commercial Policy"), _p("Body.")))
    assert any("Channel Commercial Policy" in c.content for c in chunks)


def test_no_headline_only_chunks():
    """🩸 纯标题片搜不到东西,还在向量空间里挤成一团 —— 不出片,但文本要顺延。"""
    chunks = build_chunks(
        _blocks(_h("Part A", 1), _h("A.1", 2), _p("Only body in the document."))
    )
    assert all(c.token_count > 10 for c in chunks)
    joined = "\n".join(c.content for c in chunks)
    assert "Part A" in joined and "A.1" in joined  # 文本一个字都不能丢


def test_figure_lands_in_exactly_one_chunk():
    """一张图只属于一片:重复了会在召回里占两个名额。"""
    chunks = build_chunks(_blocks(_h("H"), _p("Before."), _fig(), _p("After.")))
    imgs = [f.img for c in chunks for f in c.figures]
    assert imgs == ["images/a.jpg"]


def test_figure_chunk_carries_neighbouring_text():
    """图表整块不切,并与前后各一段正文合成一片(孤立的描述语义太薄)。"""
    chunks = build_chunks(_blocks(_h("H"), _p("Before."), _fig(), _p("After.")))
    fig_chunk = next(c for c in chunks if c.figures)
    assert "Before." in fig_chunk.content and "After." in fig_chunk.content
    assert FIGURE_PLACEHOLDER % "images/a.jpg" in fig_chunk.content


def test_neighbouring_text_is_not_emitted_twice():
    """被图借走的那段正文不再单独出片,否则同一句话会出现在两片里。"""
    chunks = build_chunks(_blocks(_h("H"), _p("Unique sentence here."), _fig()))
    assert sum(c.content.count("Unique sentence here.") for c in chunks) == 1


def test_code_block_keeps_its_newlines():
    """🩸 JSON 报文靠换行才读得懂,走句子切分会把换行拼成空格。"""
    code = '{\n  "order_no": "QY-2026-001",\n  "status": "shipped"\n}'
    chunks = build_chunks(
        _blocks(_h("API"), Block(type="code", page_idx=0, text=code))
    )
    assert any(code in c.content for c in chunks)


def test_idempotent():
    """同一份输入跑两次逐字一致 —— 否则 golden 快照和重跑都失去意义。"""
    parsed = _blocks(_h("H"), _p("One. Two. Three."), _fig(), _p("Tail."))
    assert [c.model_dump() for c in build_chunks(parsed)] == [
        c.model_dump() for c in build_chunks(parsed)
    ]


def test_heading_path_is_carried():
    """每片都带 heading_path —— embedding 输入的前缀靠它。"""
    chunks = build_chunks(_blocks(_h("Manual", 1), _h("3. Wiring", 2, ["Manual"]), _p("x.")))
    assert chunks[-1].heading_path == ["Manual", "3. Wiring"]


# ─── payload 往返 ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("page_idx", [0, 7])
def test_payload_round_trips(page_idx: int):
    """🩸 发布与"合并相邻"都是拿 payload 反过来 `Chunk.model_validate()` 的:
    少一个必填字段(实测漏过 `page_idx`)当场 500。"""
    chunk = Chunk(seq=3, content="x", page_idx=page_idx, token_count=1, bbox=[1, 2, 3, 4])
    assert Chunk.model_validate(chunk.as_payload()) == chunk
