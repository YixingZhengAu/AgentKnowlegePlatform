"""M1 文档解析:PDF → 带页标记的 markdown + 图片 + parse_result.json。

**MinerU 的 HTTP 客户端已上提到 `app/providers/mineru.py`**(契约变更 C3,S2 引入)——
S1 与 S2 都要解析 PDF,而域与域之间不许互相 import,所以解析入口归供应商层。
本文件只剩 S1 自己的产物加工:拼 `paged.md`、页尺寸、落图、统计。
"""

import base64
from collections import Counter
from pathlib import Path

from app.core.logging import get_logger
from app.schemas.exact_qa import (
    PAGE_MARKER_FMT,
    ContentBlock,
    PageInfo,
    ParseStats,
)

log = get_logger(__name__)


# ---------------------------------------------------------------- 产物加工(纯函数)


def extract_pages(middle_json: dict) -> list[PageInfo]:
    """从 middle.json 取每页物理尺寸(前端把归一化 bbox 换算回 point 时要用)。"""
    return [
        PageInfo(page_idx=i, width_pt=p["page_size"][0], height_pt=p["page_size"][1])
        for i, p in enumerate(middle_json.get("pdf_info", []))
    ]


def save_images(images: dict[str, str], images_dir: Path) -> list[str]:
    """把 base64 data URI 落盘为 images/<sha256>.jpg,返回文件名列表。

    MinerU 走 HTTP 时图片是 data URI —— 所以 server 与 MinerU 容器**无需共享文件卷**。
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for name, data_uri in sorted(images.items()):
        payload = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
        (images_dir / name).write_bytes(base64.b64decode(payload))
        saved.append(name)
    return saved


def _caption(block: ContentBlock) -> list[str]:
    return block.image_caption or block.chart_caption or block.table_caption or []


def build_paged_md(blocks: list[ContentBlock]) -> str:
    """把已过滤噪声的块序列拼成带页标记的 markdown。

    这是校对与抽取的**统一文本载体**:MinerU 自己的 md 没有任何页边界信息,
    而 origin_ref 需要 page_idx,所以自己拼一份(契约见 S1-plan §8.3b)。
    """
    lines: list[str] = []
    cur_page = -1
    for b in blocks:
        if b.page_idx != cur_page:
            cur_page = b.page_idx
            if lines:
                lines.append("")
            lines.append(PAGE_MARKER_FMT.format(page_idx=cur_page))
            lines.append("")

        if b.type == "text":
            text = (b.text or "").strip()
            if not text:
                continue
            lines.append(f"{'#' * min(b.text_level, 6)} {text}" if b.text_level else text)
            lines.append("")
        elif b.type == "equation":
            lines.append((b.text or "").strip())
            lines.append("")
        elif b.type in ("image", "chart"):
            if b.img_path:
                lines.append(f"![]({b.img_path})")
                lines.append("")
            for cap in _caption(b):
                lines.append(cap.strip())
                lines.append("")
        elif b.type == "table":
            for cap in b.table_caption:
                lines.append(cap.strip())
                lines.append("")
            if b.table_body:
                lines.append(b.table_body.strip())
                lines.append("")
            for note in b.table_footnote:
                lines.append(note.strip())
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def dropped_by_type(raw: list[ContentBlock], kept: list[ContentBlock]) -> dict[str, int]:
    """被丢掉的块按类型计数(页眉页脚页码,以及 MinerU 新冒出来的陌生类型)。

    只有总数的话,"这篇少了 23 块"没法判断是正常页边噪声还是我们漏认了新类型。
    """
    kept_ids = {id(b) for b in kept}
    counter = Counter(b.type for b in raw if id(b) not in kept_ids)
    return dict(sorted(counter.items()))


def make_stats(
    raw: list[ContentBlock], kept: list[ContentBlock], pages: int, elapsed_ms: int
) -> ParseStats:
    return ParseStats(
        page_count=pages,
        block_count=len(kept),
        noise_dropped=len(raw) - len(kept),
        dropped_by_type=dropped_by_type(raw, kept),
        table_count=sum(1 for b in kept if b.type == "table"),
        image_count=sum(1 for b in kept if b.type in ("image", "chart")),
        equation_count=sum(1 for b in kept if b.type == "equation"),
        elapsed_ms=elapsed_ms,
    )
