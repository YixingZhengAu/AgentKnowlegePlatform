"""M1 文档解析:PDF → 带页标记的 markdown + 图片 + parse_result.json。

形态:**HTTP 调常驻 mineru-api 容器**(Step 0 实测结论)。
为什么不用 CLI:3.4.5 的 CLI 内部本就是起一个临时 mineru-api 再打自己,
每次调用白付 ~13s 模型加载(实测 CLI 热跑 32s vs 常驻服务 17.7s)。
好处还有一个:MinerU 那 4.9GB 依赖树永远不进 server 的镜像。

S1 沙箱阶段(已删除)验证过的形态;集成只换了两处:
httpx 同步 → 异步(Job 跑在事件循环里)、落盘目录 → FILE_STORAGE_DIR。
拼 md 与统计的纯函数原样搬过来,连注释一起。
"""

import base64
import json
from collections import Counter
from pathlib import Path

import httpx

from app.config import settings
from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.schemas.exact_qa import (
    PAGE_MARKER_FMT,
    ContentBlock,
    PageInfo,
    ParseStats,
)

log = get_logger(__name__)


# ---------------------------------------------------------------- MinerU 调用


async def call_mineru(pdf: Path) -> dict:
    """POST /file_parse,一次拿回 md / content_list / middle_json / images。

    只开我们需要的四个开关:model_output 与 original_file 体积大且没用。
    """
    url = f"{settings.mineru_api_url.rstrip('/')}/file_parse"
    data = {
        "backend": "pipeline",         # 3.4.5 默认已是 hybrid-engine,必须显式指定
        "parse_method": "auto",
        "formula_enable": "true",
        "table_enable": "true",
        "return_md": "true",
        "return_content_list": "true",
        "return_middle_json": "true",  # 只为拿每页 page_size(PDF point)
        "return_images": "true",
        "return_model_output": "false",
        "return_original_file": "false",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.mineru_timeout_sec) as client:
            with pdf.open("rb") as fh:
                resp = await client.post(
                    url, data=data, files={"files": (pdf.name, fh, "application/pdf")}
                )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        # 报错要能直接指向"容器没起来",否则一眼看不出是服务问题还是文档问题
        raise ProviderError(
            f"MinerU 解析服务不可用({url}):{type(exc).__name__}: {exc}。"
            "起法:make mineru(定义在 docker/mineru + 根 docker-compose.yml)。",
            code="mineru_unavailable",
        ) from exc

    body = resp.json()
    if body.get("error"):
        raise ProviderError(f"MinerU 解析失败:{body['error']}", code="mineru_failed")
    results = body.get("results") or {}
    if not results:
        raise ProviderError(
            f"MinerU 返回空 results:{json.dumps(body)[:300]}", code="mineru_empty"
        )
    # 单文件上传,取第一个(key 是去掉扩展名的文件名)
    return next(iter(results.values()))


def as_json(value: object) -> object:
    """`/file_parse` 把 content_list / middle_json 以 **JSON 字符串** 回传(实测),
    CLI 落盘的是对象 —— 这里统一成对象,免得下游两套写法。"""
    return json.loads(value) if isinstance(value, str) else value


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
