"""S2 的摄取 Job:`doc_ingest` —— 一个 Job 五步跑完,末端停在人工审核。

```
上传 PDF ──▶ doc_ingest ──▶ 待审核 ──(审核台:编辑 / 不采纳 / 合并相邻)──▶ Publish
             parse/clean/chunk/describe/stage                          chunks + 向量
```

★ **为什么是一个 Job 而不是像 S1 那样两个**:S1 中间夹着"人工校对解析文本"那道关,
S2 没有 —— 切分与描述都不需要人先看一眼原文,人工关只有末端那一道(审核切片)。
所以五步连跑,`terminal_status` 用默认的 `review`。

文档级只管解析态(`documents.parse_status` 的 4 态),"审核中/已发布"由关联 Job
的状态推导 —— 不扩 CHECK 枚举,少一处会不同步的状态(与 S1 同一条纪律)。
"""

import uuid

from sqlalchemy import select

from app.config import settings
from app.core.jobs import JobRunContext, JobRunner, JobStepDef, register_job
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models import Document, StagingItem
from app.providers import mineru
from app.schemas.document import ITEM_TYPE, Chunk, ParseOutput
from app.services.document import chunker, cleaner, describer, parser, storage

log = get_logger(__name__)

JOB_TYPE = "doc_ingest"


async def _document(document_id: uuid.UUID) -> Document:
    """取文档行。

    Raises:
        RuntimeError: 文档不存在(上传与建 Job 之间被删了)。
    """
    async with SessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            raise RuntimeError(f"Document {document_id} not found")
        return doc


async def _patch_document(document_id: uuid.UUID, **fields) -> None:
    """Job 是长任务,每次写库自己开短 session(与 core/jobs.py 同一条纪律)。"""
    async with SessionLocal() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            return
        for k, v in fields.items():
            setattr(doc, k, v)
        await session.commit()


@register_job
class DocIngestJob(JobRunner):
    """PDF → 切片候选。五步全自动,末端停在审核台。"""

    job_type = JOB_TYPE
    steps = [
        JobStepDef("parse", "Parse with MinerU"),
        JobStepDef("clean", "Clean residual noise"),
        JobStepDef("chunk", "Split into chunks"),
        JobStepDef("describe", "Describe figures and tables"),
        JobStepDef("stage", "Stage chunks for review"),
    ]

    async def prepare(self, ctx: JobRunContext) -> None:
        """取出 document_id 并核对原件在磁盘上(重跑也会执行,必须幂等)。

        Raises:
            RuntimeError: 参数缺 document_id,或原件不在磁盘上。
        """
        raw = ctx.params.get("document_id")
        if not raw:
            raise RuntimeError("params 缺 document_id")
        document_id = uuid.UUID(str(raw))
        ctx.scratch["document_id"] = document_id

        doc = await _document(document_id)
        if not doc.raw_uri:
            raise RuntimeError("文档没有原件路径(raw_uri 为空)")
        pdf = settings.storage_path / doc.raw_uri
        if not pdf.exists():
            raise RuntimeError(f"原件不在磁盘上:{doc.raw_uri}")
        ctx.scratch["pdf"] = pdf
        ctx.scratch["doc_name"] = doc.name

    async def run_step(self, step: JobStepDef, ctx: JobRunContext) -> str | None:
        """失败时把文档也标成 failed。

        界面上的文档列表是用户唯一的入口,只在 job 里写 error 的话,
        列表上那一行看着还是"处理中",永远转圈。
        """
        try:
            return await super().run_step(step, ctx)
        except Exception as exc:
            document_id = ctx.scratch.get("document_id")
            if document_id is not None:
                await _patch_document(
                    document_id,
                    parse_status="failed",
                    parse_error=f"{step.name}: {type(exc).__name__}: {exc}"[:2000],
                )
            raise

    # ─── 五步 ────────────────────────────────────────────────────────────────

    async def step_parse(self, ctx: JobRunContext) -> str:
        """调 MinerU,落图,得到结构化块序列。"""
        document_id: uuid.UUID = ctx.scratch["document_id"]
        await _patch_document(document_id, parse_status="parsing", parse_error=None)

        raw = await mineru.call_mineru(ctx.scratch["pdf"])
        content_list = mineru.as_json(raw.get("content_list")) or []
        images = storage.save_images(raw.get("images") or {}, str(document_id))

        parsed = parser.parse_blocks(list(content_list), ctx.scratch["doc_name"])
        ctx.scratch["parsed"] = parsed
        target = storage.parsed_path(str(document_id))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(parsed.model_dump_json(indent=2), encoding="utf-8")

        unknown = sorted(parsed.stats.unknown_types)
        suffix = f" ({len(unknown)} unknown types: {', '.join(unknown)})" if unknown else ""
        return (
            f"{len(parsed.blocks)} blocks over {parsed.page_count} pages, "
            f"{len(images)} images{suffix}"
        )

    async def step_clean(self, ctx: JobRunContext) -> str:
        """去掉 MinerU 漏标的页眉页脚与行内 LaTeX。"""
        parsed: ParseOutput = ctx.scratch["parsed"]
        cleaned = cleaner.clean(parsed)
        ctx.scratch["cleaned"] = cleaned
        removed = len(parsed.blocks) - len(cleaned.blocks)
        return f"{len(parsed.blocks)} → {len(cleaned.blocks)} blocks ({removed} dropped)"

    async def step_chunk(self, ctx: JobRunContext) -> str:
        """按标题分节 + token 二次切,图表整块不切。"""
        cleaned: ParseOutput = ctx.scratch["cleaned"]
        chunks = chunker.build_chunks(cleaned)
        if not chunks:
            raise RuntimeError("切分结果为空:这份 PDF 没有可用正文")
        ctx.scratch["chunks"] = chunks
        with_figure = sum(1 for c in chunks if c.has_figure)
        tokens = sorted(c.token_count for c in chunks)
        return (
            f"{len(chunks)} chunks ({with_figure} with figures), "
            f"tokens min {tokens[0]} / median {tokens[len(tokens) // 2]} / max {tokens[-1]}"
        )

    async def step_describe(self, ctx: JobRunContext) -> str:
        """整条链唯一调 LLM 的一步:给图表写可检索的描述。"""
        document_id: uuid.UUID = ctx.scratch["document_id"]
        chunks: list[Chunk] = ctx.scratch["chunks"]
        described, tokens = await describer.describe(chunks, str(document_id))
        storage.save_chunks(str(document_id), chunks)
        if not described:
            return "No figures needed describing"
        return f"{described} figures described ({tokens:,} tokens)"

    async def step_stage(self, ctx: JobRunContext) -> str:
        """把切片写成待审候选。**幂等**:已经写过就不再写第二遍。"""
        document_id: uuid.UUID = ctx.scratch["document_id"]
        chunks: list[Chunk] = ctx.scratch["chunks"]

        async with SessionLocal() as session:
            existing = (
                await session.execute(
                    select(StagingItem.id).where(StagingItem.job_id == ctx.job_id).limit(1)
                )
            ).first()
            if existing is None:
                session.add_all(
                    [
                        StagingItem(
                            job_id=ctx.job_id,
                            kb_id=ctx.kb_id,
                            item_type=ITEM_TYPE,
                            payload=c.as_payload(),
                            origin_ref={
                                "document_id": str(document_id),
                                "page": c.page_idx,
                                "bbox": c.bbox,
                            },
                        )
                        for c in chunks
                    ]
                )
                await session.commit()

        cleaned: ParseOutput = ctx.scratch["cleaned"]
        doc = await _document(document_id)
        await _patch_document(
            document_id,
            parse_status="parsed",
            parse_error=None,
            # jsonb 必须整体赋新值,原地改字典 SQLAlchemy 看不见
            meta={
                **(doc.meta or {}),
                "page_count": cleaned.page_count,
                "chunk_count": len(chunks),
                "dropped": cleaned.stats.dropped_by_type,
            },
        )
        # stats 只有这一条通道能进 ingest_jobs.stats,前端的"Review items"按钮看它
        ctx.scratch["stats"] = {"staged": len(chunks)}
        return f"{len(chunks)} chunks staged for review"
