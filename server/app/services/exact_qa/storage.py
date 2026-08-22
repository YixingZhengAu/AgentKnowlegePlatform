"""解析产物的落盘位置与图片 URL 改写(M1.5 的两件事)。

**唯一的路径出处**:除本文件外,任何地方不许自己拼 `parses/{id}/...`。
文件名常量在 S1 沙箱阶段定型,集成后留在
`app/schemas/exact_qa.py`(是契约),落盘位置留在这里(是实现)。

目录形态(FILE_STORAGE_DIR 下):

    parses/{document_id}/
      paged.md           带页标记的解析文本 —— 校对页展示/编辑的对象、M2 的输入
      reviewed.md        校对后的文本(存在则 M2 用它;原始 paged.md 永远保留可对比)
      parse_result.json  页尺寸 + 块序列 + 统计
      images/*.jpg       MinerU 切出来的图/表/公式

**入库一律存相对路径**(`images/xxx.jpg`),URL 只在出口临时拼 ——
存储目录搬迁或域名变化都不影响历史数据(见 S1-plan §5 M1.5)。
"""

import re
import shutil
from pathlib import Path

from app.config import settings
from app.core.logging import get_logger
from app.schemas.exact_qa import (
    IMAGES_SUBDIR,
    PAGED_MD_NAME,
    PARSE_RESULT_NAME,
    PARSE_SUBDIR,
    REVIEWED_MD_NAME,
    ParseResult,
    image_url,
)

log = get_logger(__name__)

#: 上传原件在 FILE_STORAGE_DIR 下的子目录
SOURCES_SUBDIR = "sources"

#: markdown 里的图片引用:![alt](images/<name>) —— 只改写指向本文档 images/ 的相对路径
_MD_IMAGE_RE = re.compile(r"(!\[[^\]]*\]\()" + IMAGES_SUBDIR + r"/([^)\s]+)(\))")


# ---------------------------------------------------------------- 路径


def source_pdf_rel(source_id: str) -> str:
    """上传原件的相对路径(落 `ingest_sources.uri` / `documents.raw_uri`)。

    用 source_id 而不是原文件名:原文件名可能重名、带空格、带中文,
    而且会被拼进 URL —— 用 id 就没有这一堆边界情况(原名存在 original_name 列里)。
    """
    return f"{SOURCES_SUBDIR}/{source_id}.pdf"


def source_pdf_path(source_id: str) -> Path:
    return settings.storage_path / source_pdf_rel(source_id)


def save_source_pdf(source_id: str, data: bytes) -> str:
    """落盘上传的 PDF,返回相对路径。"""
    path = source_pdf_path(source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return source_pdf_rel(source_id)


def parse_dir(document_id: str) -> Path:
    """某文档的解析产物目录(绝对路径)。"""
    return settings.storage_path / PARSE_SUBDIR / str(document_id)


def parse_dir_rel(document_id: str) -> str:
    """落 `documents.meta.parse_dir` 的相对路径(不含 FILE_STORAGE_DIR 前缀)。"""
    return f"{PARSE_SUBDIR}/{document_id}"


def images_dir(document_id: str) -> Path:
    return parse_dir(document_id) / IMAGES_SUBDIR


def paged_md_path(document_id: str) -> Path:
    return parse_dir(document_id) / PAGED_MD_NAME


def reviewed_md_path(document_id: str) -> Path:
    return parse_dir(document_id) / REVIEWED_MD_NAME


def parse_result_path(document_id: str) -> Path:
    return parse_dir(document_id) / PARSE_RESULT_NAME


# ---------------------------------------------------------------- 读写


def load_parse_result(document_id: str) -> ParseResult:
    return ParseResult.model_validate_json(parse_result_path(document_id).read_text())


def source_md(document_id: str) -> tuple[str, str]:
    """抽取用的文本:优先 reviewed.md(人工校对产物),没有则退回 paged.md。

    返回 (文件名, 内容)。这条契约在沙箱阶段就定了(S1-plan §8.3b),
    集成后一字不改 —— 校对页保存写的就是 reviewed.md。
    """
    reviewed = reviewed_md_path(document_id)
    if reviewed.exists():
        return REVIEWED_MD_NAME, reviewed.read_text()
    return PAGED_MD_NAME, paged_md_path(document_id).read_text()


def save_reviewed_md(document_id: str, text: str) -> None:
    """校对页保存。**永不覆盖 paged.md**:原始解析件要留着做对比。"""
    reviewed_md_path(document_id).write_text(text, encoding="utf-8")


def remove_document_files(document_id: str, raw_uri: str | None) -> None:
    """删文档时清磁盘:解析产物整目录 + 上传原件。

    **删不掉不抛异常**:库里的行已经删了,这里再炸就变成"接口报错但数据已经没了";
    残留文件顶多占点空间,记一条 warning 比让调用方看到 500 有用。
    """
    target = parse_dir(document_id)
    try:
        if target.is_dir():
            shutil.rmtree(target)
    except OSError as exc:
        log.warning("exact_qa_parse_dir_remove_failed", document_id=document_id, error=str(exc))
    if raw_uri:
        try:
            (settings.storage_path / raw_uri).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("exact_qa_source_remove_failed", raw_uri=raw_uri, error=str(exc))


# ---------------------------------------------------------------- 图片 URL 改写


def rewrite_image_urls(md: str, document_id: str) -> str:
    """把 md 里的 `images/<name>` 改写成文件服务 URL。

    **为什么在后端改写而不是前端配 baseURL**:同一段文本会被校对页、审核台、对话消息、
    未来的导出多处消费,改写集中在一处才不会漏(S1-plan §5 M1.5 的定稿理由)。
    """
    return _MD_IMAGE_RE.sub(
        lambda m: m.group(1) + image_url(str(document_id), m.group(2)) + m.group(3), md
    )
