"""解析产物的落盘位置(本域唯一的路径出处)+ 图片 URL 改写 + 清盘。

目录形态(**与 S1 逐字相同,是有意的**):

    sources/{source_id}.pdf              上传的原件
    parses/{document_id}/
        parsed.json                      块序列 + 丢弃统计
        chunks.json                      切片(含描述),审核台改动后回写
        images/*.jpg                     MinerU 切出的图表截图

🩸 为什么抄 S1 的目录:`app/api/files.py` 的图片出口是**按 document_id 寻址、
不分域**的。沿用同一套目录,S2 的图片白拿那个接口;换个目录就得再开一个共享接口。
"""

import base64
import json
import re
import shutil
from pathlib import Path

from app.config import settings
from app.core.logging import get_logger
from app.schemas.document import (
    CHUNKS_NAME,
    IMAGES_SUBDIR,
    PARSE_SUBDIR,
    PARSED_NAME,
    SOURCES_SUBDIR,
    Chunk,
    image_url,
)

log = get_logger(__name__)

#: markdown 里的图片引用 —— 库里存相对路径,只在接口出口改写成 URL
_MD_IMAGE_RE = re.compile(r"(!\[[^\]]*\]\()" + IMAGES_SUBDIR + r"/([^)\s]+)(\))")


# ─── 路径 ─────────────────────────────────────────────────────────────────────

def source_pdf_rel(source_id: str) -> str:
    """原件的相对路径(存进 `ingest_sources.uri` / `documents.raw_uri`)。"""
    return f"{SOURCES_SUBDIR}/{source_id}.pdf"


def source_pdf_path(source_id: str) -> Path:
    """原件的绝对路径。"""
    return settings.storage_path / source_pdf_rel(source_id)


def save_source_pdf(source_id: str, data: bytes) -> str:
    """把上传的字节落盘,返回相对路径。"""
    path = source_pdf_path(source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return source_pdf_rel(source_id)


def parse_dir(document_id: str) -> Path:
    """某文档的解析产物目录。"""
    return settings.storage_path / PARSE_SUBDIR / document_id


def images_dir(document_id: str) -> Path:
    """某文档的切图目录。"""
    return parse_dir(document_id) / IMAGES_SUBDIR


def parsed_path(document_id: str) -> Path:
    """`parsed.json` 的绝对路径。"""
    return parse_dir(document_id) / PARSED_NAME


def chunks_path(document_id: str) -> Path:
    """`chunks.json` 的绝对路径。"""
    return parse_dir(document_id) / CHUNKS_NAME


# ─── 读写 ─────────────────────────────────────────────────────────────────────

def save_images(images: dict[str, str], document_id: str) -> list[str]:
    """把 base64 data URI 落盘为 `images/<name>`,返回文件名列表。

    MinerU 走 HTTP 时图片是 data URI —— 所以 server 与 MinerU 容器**无需共享文件卷**。
    """
    target = images_dir(document_id)
    target.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for name, data_uri in sorted(images.items()):
        payload = data_uri.split(",", 1)[1] if "," in data_uri else data_uri
        (target / name).write_bytes(base64.b64decode(payload))
        saved.append(name)
    return saved


def read_image(document_id: str, rel_img: str) -> bytes:
    """读一张切图的字节(describe 要把它喂给模型)。

    Args:
        document_id: 文档 id。
        rel_img: `Figure.img`,形如 `images/<sha256>.jpg`。

    Returns:
        图片字节。

    Raises:
        FileNotFoundError: 文件不在磁盘上。
    """
    return (parse_dir(document_id) / rel_img).read_bytes()


def save_chunks(document_id: str, chunks: list[Chunk]) -> None:
    """把切片写进 `chunks.json`(审核台改动后也回写这里)。"""
    path = chunks_path(document_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "[\n" + ",\n".join(c.model_dump_json(indent=2) for c in chunks) + "\n]"
    path.write_text(payload, encoding="utf-8")


def load_chunks(document_id: str) -> list[Chunk]:
    """读回 `chunks.json`。

    Raises:
        FileNotFoundError: 还没跑过切分。
    """
    raw = json.loads(chunks_path(document_id).read_text(encoding="utf-8"))
    return [Chunk.model_validate(item) for item in raw]


# ─── 出口改写与清盘 ───────────────────────────────────────────────────────────

def rewrite_image_urls(md: str, document_id: str) -> str:
    """把正文里的 `images/x.jpg` 换成可访问的 URL。

    纪律:**库里只存相对路径**,URL 只在接口出口拼 —— 换域名/换网关不用改数据。
    """
    return _MD_IMAGE_RE.sub(
        lambda m: m.group(1) + image_url(document_id, m.group(2)) + m.group(3), md
    )


def remove_document_files(document_id: str, raw_uri: str | None) -> None:
    """删文档时清盘。**永不抛异常** —— 库里的行这时已经没了,磁盘残留只值一条 warning。"""
    target = parse_dir(document_id)
    try:
        if target.is_dir():
            shutil.rmtree(target)
    except OSError as exc:
        log.warning("document_parse_dir_remove_failed", document_id=document_id, error=str(exc))
    if raw_uri:
        try:
            (settings.storage_path / raw_uri).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("document_source_remove_failed", raw_uri=raw_uri, error=str(exc))
