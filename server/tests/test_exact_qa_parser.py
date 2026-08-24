"""S1 解析层的离线单测:块类型的宽容度 + 拼 md 与统计。

回归的起因(2026-08-23,手动测 data/company-it-policy.pdf):`ContentBlock.type`
写成 Literal 枚举,MinerU 实测吐出 `header` / `footer`(页眉页脚)不在枚举里,
pydantic 直接 ValidationError —— **一个陌生块把整篇文档打成 parse failed**。
content_list 是 MinerU 的输出而非我们的入参,收窄枚举没有收益,只有风险。
"""

from app.schemas.exact_qa import CONTENT_BLOCK_TYPES, NOISE_BLOCK_TYPES, ContentBlock
from app.services.exact_qa.parser import build_paged_md, dropped_by_type, make_stats

#: 实测形态:公司名页眉、"CLE-IT-POL-011 | Internal use only" 页脚、"Page 1 of 5" 页码
MARGIN_BLOCKS = [
    ContentBlock(
        type="header", page_idx=0, bbox=[82, 23, 297, 39], text="Example Australia Pty Ltd"
    ),
    ContentBlock(
        type="footer",
        page_idx=0,
        bbox=[80, 953, 297, 966],
        text="CLE-IT-POL-011 | Internal use only",
    ),
    ContentBlock(
        type="page_number", page_idx=0, bbox=[842, 953, 915, 966], text="Page 1 of 5"
    ),
]


def test_margin_types_parse_and_are_noise():
    """页眉页脚页码:能过校验(不再 ValidationError),且一律算噪声。"""
    for block in MARGIN_BLOCKS:
        assert block.type in NOISE_BLOCK_TYPES
        assert block.is_noise
        assert not block.is_unknown_type


def test_unknown_type_is_tolerated_but_flagged():
    """MinerU 升级冒出的新类型:不报错、按噪声丢掉、但要能被认出来是陌生的。"""
    block = ContentBlock.model_validate(
        {"type": "algorithm", "page_idx": 2, "text": "for i in range(n): ..."}
    )
    assert block.type == "algorithm"
    assert block.is_noise
    assert block.is_unknown_type


def test_content_types_are_kept():
    for type_ in sorted(CONTENT_BLOCK_TYPES):
        assert not ContentBlock(type=type_, page_idx=0).is_noise


def test_build_paged_md_only_renders_content():
    """噪声块不进 md;页标记按 page_idx 切,标题按 text_level 变 #。"""
    blocks = [
        ContentBlock(type="text", page_idx=0, text="Acceptable Use", text_level=1),
        ContentBlock(
            type="text", page_idx=0, text="Company laptops must use full-disk encryption."
        ),
        ContentBlock(
            type="table",
            page_idx=1,
            table_caption=["Table 1. Device classes."],
            table_body="<table><tr><td>Laptop</td></tr></table>",
        ),
    ]
    md = build_paged_md(blocks)
    assert "<!-- page: 0 -->" in md and "<!-- page: 1 -->" in md
    assert "# Acceptable Use" in md
    assert "full-disk encryption" in md
    assert "Table 1. Device classes." in md
    # 噪声块即便混进来也不该出现在正文里(拼 md 只认内容类型)
    assert "Internal use only" not in build_paged_md(blocks + MARGIN_BLOCKS)


def test_stats_break_down_dropped_blocks():
    """只有总数看不出"少的是页眉还是漏认的新类型",所以按类型计数。"""
    text = ContentBlock(type="text", page_idx=0, text="Reimbursement within 30 days.")
    raw = [text, *MARGIN_BLOCKS, ContentBlock(type="algorithm", page_idx=0, text="x")]
    kept = [b for b in raw if not b.is_noise]

    assert dropped_by_type(raw, kept) == {
        "algorithm": 1,
        "footer": 1,
        "header": 1,
        "page_number": 1,
    }
    stats = make_stats(raw, kept, pages=1, elapsed_ms=10)
    assert stats.block_count == 1
    assert stats.noise_dropped == 4
    assert stats.dropped_by_type["header"] == 1
