"""M1 解析:MinerU 原始产物 → 结构化块序列。

做四件事:
    1. 逐块校验(契约见 `app/schemas/document.py`),**未知类型按噪声丢弃、不抛异常**
    2. 丢掉噪声块(页眉页脚页码等),**按类型计数留痕**
    3. 用一个栈从 `text_level` 推导 `heading_path`(MinerU 不给这个字段)
    4. 图表块把切图路径 / caption / footnote / table_body 收齐,供 describe 用

MinerU 的 HTTP 客户端在 `app/providers/mineru.py`(契约变更 C3);本文件只做加工,不联网。
"""

from app.core.logging import get_logger
from app.schemas.document import (
    Block,
    DropStats,
    MineruBlock,
    ParseOutput,
    unknown_extra_fields,
)

log = get_logger(__name__)


# ─── 私有助手 ─────────────────────────────────────────────────────────────────

def _push_heading(stack: list[tuple[int, str]], level: int, title: str) -> None:
    """把标题压进栈,先弹出所有同级或更深的层。

    栈里存 `(level, title)` 而不是纯字符串:PDF 里的标题层级会跳级
    (只有 h1 和 h3、没有 h2),用列表下标当层级会错位。
    """
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))


def _to_block(src: MineruBlock, heading_path: list[str]) -> Block:
    """把校验过的原始块转成加工后的块。"""
    if src.type == "code":
        text = (src.code_body or "").strip()
    elif src.type in ("text", "equation"):
        text = (src.text or "").strip()
    else:
        # 图表块的正文留空:describe 步骤才会往里写 [image description] 那一段
        text = ""
    return Block(
        type=src.type,
        page_idx=src.page_idx,
        bbox=src.bbox,
        heading_path=heading_path,
        text_level=src.text_level,
        text=text,
        img_path=src.img_path,
        captions=src.captions,
        footnotes=src.footnotes,
        table_body=src.table_body,
    )


# ─── 公共函数 ─────────────────────────────────────────────────────────────────

def parse_blocks(raw_blocks: list[dict], doc_name: str) -> ParseOutput:
    """把 content_list 转成结构化块序列。

    Args:
        raw_blocks: MinerU content_list 的原始 dict 列表。
        doc_name: 文档展示名,进产物元信息。

    Returns:
        `ParseOutput`,含块序列、丢弃统计、未声明字段统计。
    """
    stats = DropStats()
    blocks: list[Block] = []
    heading_stack: list[tuple[int, str]] = []

    for raw in raw_blocks:
        try:
            src = MineruBlock.model_validate(raw)
        except Exception:  # noqa: BLE001 契约破了也不能打死整篇,记一笔继续
            stats.drop(str(raw.get("type", "<unparseable>")), unknown=True)
            continue

        if not src.is_content:
            stats.drop(src.type, unknown=src.is_unknown_type)
            continue

        # 退化图表块(无图无 HTML)什么都描述不出来,当噪声丢并留痕
        if src.is_empty_figure:
            stats.drop(f"{src.type}(empty)")
            continue

        text = (src.text or src.code_body or "").strip()
        if src.type in ("text", "code") and not text:
            stats.empty_text_blocks += 1
            continue

        # 🩸 标题块必须**先入栈再取路径**:入栈会弹掉同级与更深的层,
        # 顺序反了会把兄弟标题当成父级(实测:"1. Document Control > 2. Scope",
        # 而这两个都是 h2)。取 stack[:-1] 是因为自己的路径不含自己。
        if src.is_heading and src.text_level is not None:
            _push_heading(heading_stack, src.text_level, text)
            path = [title for _, title in heading_stack[:-1]]
        else:
            path = [title for _, title in heading_stack]
        blocks.append(_to_block(src, path))

    if stats.unknown_types:
        # 内容悄悄少了没人知道 —— 这条日志是唯一的报警
        log.warning("document_unknown_block_types", doc=doc_name, types=stats.unknown_types)

    return ParseOutput(
        doc_name=doc_name,
        blocks=blocks,
        stats=stats,
        extra_fields_seen=unknown_extra_fields(raw_blocks),
    )
