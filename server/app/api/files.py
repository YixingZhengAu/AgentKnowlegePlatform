"""文件服务:解析产物的图片出口(M1.5 的最后一环)+ 上传原件的 PDF 出口。

MinerU 把图/表/公式切成独立的 jpg,markdown 里是 `images/<sha256>.jpg` 相对路径 ——
**没有这个端点,校对页和答案里的图片就是一堆 404 占位框**。

PDF 出口是给校对页做原文对照用的:左边浏览器原生 PDF 阅读器(`#page=N` 可直接跳页),
右边编辑解析出来的 markdown —— 校对的意思就是"对着原件看解析对不对",少了原件就没得对。

只读、只服务 FILE_STORAGE_DIR 之内的路径、图片只允许单层文件名(见 `_safe_name`):
路径穿越(`..%2f`)在这类"按名字取文件"的端点上是最常见的洞。
"""

import re
import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import SessionDep
from app.config import settings
from app.core.errors import NotFoundError
from app.models import Document
from app.services.exact_qa import storage

router = APIRouter(prefix="/api/files", tags=["files"])

#: MinerU 的图片名是 sha256 + 扩展名;放宽一点允许连字符/下划线,但**不允许任何分隔符**
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _safe_name(name: str) -> str:
    if not _SAFE_NAME.match(name) or name.startswith("."):
        raise NotFoundError("Image not found", code="image_not_found")
    return name


@router.get("/parses/{document_id}/images/{name}")
async def get_parse_image(document_id: uuid.UUID, name: str) -> FileResponse:
    """`GET /api/files/parses/{document_id}/images/{name}` —— 契约见 schemas/exact_qa.py。"""
    path = storage.images_dir(str(document_id)) / _safe_name(name)
    if not path.is_file():
        raise NotFoundError("Image not found", code="image_not_found")
    media = _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
    # 内容按 sha256 命名 = 内容寻址,可以放心长缓存
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/documents/{document_id}/pdf")
async def get_source_pdf(document_id: uuid.UUID, session: SessionDep) -> FileResponse:
    """上传原件(校对页左侧的 PDF 预览)。

    路径不从 URL 拼,而是从 `documents.raw_uri` 取(入库时由 storage 层写的相对路径),
    再断言它落在 FILE_STORAGE_DIR 之内 —— 库里的值也不当可信输入。
    """
    doc = await session.get(Document, document_id)
    if doc is None or not doc.raw_uri:
        raise NotFoundError("Source file not found", code="source_not_found")
    root = settings.storage_path.resolve()
    path = (root / doc.raw_uri).resolve()
    if not path.is_file() or root not in path.parents:
        raise NotFoundError("Source file not found", code="source_not_found")
    # inline 而不是 attachment:要在 iframe 里显示,不是让人下载。
    # 刻意不回传文件名 —— 原名是用户上传的字符串,拼进响应头是没必要的风险
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline", "Cache-Control": "private, max-age=3600"},
    )
