"""S2 解析层的离线单测:块类型的宽容度 + 标题路径推导。

两处最容易静默出错、且错了不报错的地方:
① **陌生块类型**:content_list 是 MinerU 的输出而非我们的入参,收窄成 Literal
   只有风险没有收益 —— 一个陌生块不许把整篇文档打成 failed(S1 的血泪,S2 继承);
② **标题路径**:错了不会抛异常,只会让每一片切片挂在错误的章节下,
   检索时看不出来,人工审核也很难一眼发现。
"""

from app.schemas.document import (
    CONTENT_BLOCK_TYPES,
    NOISE_BLOCK_TYPES,
    MineruBlock,
    declared_field_names,
)
from app.services.document.parser import parse_blocks


def _text(text: str, page: int = 0, level: int | None = None) -> dict:
    block: dict = {"type": "text", "page_idx": page, "text": text}
    if level is not None:
        block["text_level"] = level
    return block


# ─── 宽容度 ───────────────────────────────────────────────────────────────────

def test_unknown_type_is_dropped_not_raised():
    """MinerU 冒出的新类型:按噪声丢、计进 unknown_types,**不抛异常**。"""
    out = parse_blocks(
        [_text("body"), {"type": "molecule_diagram", "page_idx": 0, "text": "?"}], "d"
    )
    assert len(out.blocks) == 1
    assert out.stats.unknown_types == {"molecule_diagram": 1}


def test_malformed_block_is_counted_not_raised():
    """字段坏掉的块只记一笔就跳过 —— 一个坏块不许打死整篇。"""
    out = parse_blocks([{"type": "text", "page_idx": "not-an-int"}, _text("ok")], "d")
    assert [b.text for b in out.blocks] == ["ok"]
    assert out.stats.total == 1


def test_noise_blocks_are_dropped_with_trace():
    """页眉页脚页码丢弃,但每一类都要留下计数。"""
    noise = [{"type": t, "page_idx": 0, "text": t} for t in sorted(NOISE_BLOCK_TYPES)]
    out = parse_blocks([*noise, _text("body")], "d")
    assert len(out.blocks) == 1
    assert set(out.stats.dropped_by_type) == NOISE_BLOCK_TYPES
    assert not out.stats.unknown_types  # 已知噪声不算"未知类型"


def test_empty_figure_is_dropped():
    """退化图表块(无图无 HTML)什么都描述不出来,留着只会在正文里剩个死占位符。"""
    out = parse_blocks(
        [{"type": "table", "page_idx": 0, "img_path": ""}, _text("body")], "d"
    )
    assert len(out.blocks) == 1
    assert out.stats.dropped_by_type == {"table(empty)": 1}


def test_code_block_is_content_not_noise():
    """🩸 code 块要进正文:JSON 报文、API 响应正是用户会拿去搜的字符串。"""
    assert "code" in CONTENT_BLOCK_TYPES
    out = parse_blocks(
        [{"type": "code", "page_idx": 0, "code_body": '{"order": "QY-2026-001"}'}], "d"
    )
    assert out.blocks[0].text == '{"order": "QY-2026-001"}'


# ─── 标题路径 ─────────────────────────────────────────────────────────────────

def test_heading_path_excludes_self():
    """标题块自己的路径不含自己,否则每一层都会重复一次。"""
    out = parse_blocks([_text("Handbook", level=1)], "d")
    assert out.blocks[0].heading_path == []


def test_body_inherits_the_heading_above_it():
    """正文块挂在它上面那个标题下。"""
    out = parse_blocks([_text("Handbook", level=1), _text("body")], "d")
    assert out.blocks[1].heading_path == ["Handbook"]


def test_sibling_headings_are_not_nested():
    """🩸 兄弟标题不许变成父子。

    入栈必须**先于**取路径:顺序反了,同级的第二个标题会把第一个当成父级
    (实测 `1. Document Control > 2. Scope`,而这两个都是 h2)。
    """
    out = parse_blocks(
        [
            _text("Handbook", level=1),
            _text("1. Document Control", level=2),
            _text("a"),
            _text("2. Scope", level=2),
            _text("b"),
        ],
        "d",
    )
    assert out.blocks[-1].heading_path == ["Handbook", "2. Scope"]


def test_heading_stack_pops_deeper_levels():
    """从 h3 回到 h2 时,h3 必须被弹出去。"""
    out = parse_blocks(
        [
            _text("H1", level=1),
            _text("H2a", level=2),
            _text("H3", level=3),
            _text("H2b", level=2),
            _text("tail"),
        ],
        "d",
    )
    assert out.blocks[-1].heading_path == ["H1", "H2b"]


def test_level_can_skip_without_misaligning():
    """标题层级会跳级(只有 h1 和 h3),路径不能因此错位。"""
    out = parse_blocks([_text("H1", level=1), _text("H3", level=3), _text("t")], "d")
    assert out.blocks[-1].heading_path == ["H1", "H3"]


# ─── 图表线索 ─────────────────────────────────────────────────────────────────

def test_figure_keeps_all_source_hints():
    """图表块的 caption / footnote / table_body 一个都不能丢 —— describe 全要喂给模型。"""
    out = parse_blocks(
        [
            {
                "type": "table",
                "page_idx": 2,
                "img_path": "images/x.jpg",
                "table_caption": ["Table 1. Backbones"],
                "table_footnote": ["Measured on a Titan X."],
                "table_body": "<table><tr><td>1</td></tr></table>",
                "bbox": [1, 2, 3, 4],
            }
        ],
        "d",
    )
    block = out.blocks[0]
    assert block.captions == ["Table 1. Backbones"]
    assert block.footnotes == ["Measured on a Titan X."]
    assert block.table_body and block.bbox == [1, 2, 3, 4]


def test_image_footnote_is_declared():
    """🩸 S1 的契约漏了 image/chart 的 footnote(静默丢掉),S2 必须收齐。"""
    declared = declared_field_names()
    for field in ("image_footnote", "chart_footnote", "table_footnote", "code_footnote"):
        assert field in declared


def test_extra_fields_are_reported_not_swallowed():
    """MinerU 新加的字段要能被看见,否则"新字段静默消失"只能靠肉眼发现。"""
    out = parse_blocks([{**_text("t"), "brand_new_field": 1}], "d")
    assert out.extra_fields_seen == {"brand_new_field": 1}
    assert MineruBlock.model_validate({**_text("t"), "brand_new_field": 1}).type == "text"
