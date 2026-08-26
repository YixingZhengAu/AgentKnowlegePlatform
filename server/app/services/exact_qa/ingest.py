"""S1 的两个摄取 Job:`qa_parse`(解析)与 `qa_extract`(抽取)。

★ **为什么是两个 Job 而不是一个**:中间夹着一道人工关。
上传后自动解析 → 停下来等人校对解析文本 →(人点「确认,开始抽取」)→ 才抽 QA。
一个 Job 做不到"中间停下来等人",而且解析失败与抽取失败要能各自重跑
(解析要重跑 MinerU,抽取要重花 LLM 的钱,混在一起重跑就是浪费)。

```
上传 PDF ──▶ qa_parse ──▶ 待校对 ──(人工校对 + 确认)──▶ qa_extract ──▶ 候选 QA 待采纳
             fetch/parse/store                          extract/similar/stage
             terminal=published(不产待审)                terminal=review(等人采纳)
```

文档级只管解析态(`documents.parse_status` 的 4 态),"待校对/抽取中/待采纳"由关联 Job
的状态推导(S1-plan §8.4 的方案 A)—— 不扩 CHECK 枚举,少一处会不同步的状态。
"""

import uuid

from sqlalchemy import select

from app.config import settings
from app.core.jobs import JobRunContext, JobRunner, JobStepDef, register_job
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models import Document, StagingItem
from app.providers import mineru
from app.schemas.exact_qa import (
    PAGED_MD_NAME,
    ContentBlock,
    ParseResult,
    QaCandidateSet,
)
from app.services.exact_qa import parser, storage
from app.services.exact_qa.extractor import extract
from app.services.exact_qa.similar_gen import fill_similar

log = get_logger(__name__)


async def _document(document_id: uuid.UUID) -> Document:
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


class _DocumentJob(JobRunner):
    """两个 Job 共用的一点东西:从 params 取 document_id、失败时把文档标成 failed。

    失败落到文档上很重要:界面上的文档列表是用户唯一的入口,
    只在 job 里写 error 的话列表上那一行看着还是"解析中",永远转圈。
    """

    async def prepare(self, ctx: JobRunContext) -> None:
        raw = ctx.params.get("document_id")
        if not raw:
            raise RuntimeError("params 缺 document_id")
        ctx.scratch["document_id"] = uuid.UUID(str(raw))

    async def run_step(self, step: JobStepDef, ctx: JobRunContext) -> str | None:
        try:
            return await super().run_step(step, ctx)
        except Exception as exc:
            document_id = ctx.scratch.get("document_id")
            if document_id is not None:
                await self._on_failure(document_id, f"{step.name}: {type(exc).__name__}: {exc}")
            raise

    async def _on_failure(self, document_id: uuid.UUID, message: str) -> None:
        await _patch_document(document_id, parse_status="failed", parse_error=message[:2000])


# ==========================================================================
# qa_parse:PDF → paged.md + images + parse_result.json
# ==========================================================================


@register_job
class QaParseJob(_DocumentJob):
    job_type = "qa_parse"
    steps = [
        JobStepDef("fetch", "Load uploaded PDF"),
        JobStepDef("parse", "Parse with MinerU"),
        JobStepDef("store", "Store parsed artefacts"),
    ]
    # 解析不产出待审内容,跑完就是终态;等人校对这件事由文档状态表达,不占用 job 状态
    terminal_status = "published"

    async def step_fetch(self, ctx: JobRunContext) -> str:
        doc = await _document(ctx.scratch["document_id"])
        if not doc.raw_uri:
            raise RuntimeError("文档没有原件路径(raw_uri 为空)")
        pdf = settings.storage_path / doc.raw_uri
        if not pdf.exists():
            raise RuntimeError(f"原件不在磁盘上:{doc.raw_uri}")
        ctx.scratch["pdf"] = pdf
        await _patch_document(doc.id, parse_status="parsing", parse_error=None)
        return f"Loaded {doc.name} ({pdf.stat().st_size / 1024:.0f} KB)"

    async def step_parse(self, ctx: JobRunContext) -> str:
        raw = await mineru.call_mineru(ctx.scratch["pdf"])
        ctx.scratch["raw"] = raw
        content_list = mineru.as_json(raw.get("content_list")) or []
        blocks = [ContentBlock.model_validate(b) for b in content_list]
        ctx.scratch["blocks_raw"] = blocks

        # 陌生类型不报错(会被当噪声丢掉),但必须留痕:否则内容悄悄少了没人知道
        unknown = sorted({b.type for b in blocks if b.is_unknown_type})
        if unknown:
            log.warning(
                "mineru_unknown_block_types",
                document_id=str(ctx.scratch["document_id"]),
                types=unknown,
            )
        suffix = f" ({len(unknown)} unknown types: {', '.join(unknown)})" if unknown else ""
        return f"MinerU returned {len(blocks)} blocks{suffix}"

    async def step_store(self, ctx: JobRunContext) -> str:
        document_id = ctx.scratch["document_id"]
        raw = ctx.scratch["raw"]
        raw_blocks: list[ContentBlock] = ctx.scratch["blocks_raw"]
        kept = [b for b in raw_blocks if not b.is_noise]
        pages = parser.extract_pages(mineru.as_json(raw.get("middle_json")) or {})

        out_dir = storage.parse_dir(str(document_id))
        out_dir.mkdir(parents=True, exist_ok=True)
        images = parser.save_images(raw.get("images") or {}, storage.images_dir(str(document_id)))
        storage.paged_md_path(str(document_id)).write_text(
            parser.build_paged_md(kept), encoding="utf-8"
        )

        doc = await _document(document_id)
        result = ParseResult(
            document_id=str(document_id),
            source_pdf=doc.raw_uri or "",
            parse_dir=storage.parse_dir_rel(str(document_id)),
            pages=pages,
            blocks=kept,
            images=images,
            # 解析耗时由 Job 的 step 日志记(框架已有),这里不重复计时
            stats=parser.make_stats(raw_blocks, kept, len(pages), 0),
        )
        storage.parse_result_path(str(document_id)).write_text(
            result.model_dump_json(indent=2, exclude_none=True), encoding="utf-8"
        )

        stats = result.stats.model_dump()
        await _patch_document(
            document_id,
            parse_status="parsed",
            parse_error=None,
            meta={
                **(doc.meta or {}),
                "parse_dir": result.parse_dir,
                "parse_stats": stats,
                "review_source": PAGED_MD_NAME,
            },
        )
        ctx.scratch["stats"] = stats
        by_type = ", ".join(f"{t}x{n}" for t, n in (stats.get("dropped_by_type") or {}).items())
        dropped = f"dropped {stats['noise_dropped']} noise" + (f": {by_type}" if by_type else "")
        return (
            f"{stats['page_count']} pages / {stats['block_count']} blocks "
            f"({dropped}), {len(images)} images"
        )


# ==========================================================================
# qa_extract:校对后的文本 → 候选 QA(带相似问)
# ==========================================================================


@register_job
class QaExtractJob(_DocumentJob):
    job_type = "qa_extract"
    steps = [
        JobStepDef("extract", "Extract QA candidates"),
        JobStepDef("similar", "Generate similar questions"),
        JobStepDef("stage", "Write candidates for review"),
    ]
    # 摄取类任务跑完停在 review 等人采纳(采纳即发布,见 publisher.py)
    terminal_status = "review"

    async def _on_failure(self, document_id: uuid.UUID, message: str) -> None:
        """抽取失败不该把文档的**解析**状态改成 failed —— 解析是好的,重跑抽取即可。"""
        async with SessionLocal() as session:
            doc = await session.get(Document, document_id)
            if doc is None:
                return
            doc.meta = {**(doc.meta or {}), "extract_error": message[:2000]}
            await session.commit()

    async def step_extract(self, ctx: JobRunContext) -> str:
        document_id = str(ctx.scratch["document_id"])
        source_name, md = storage.source_md(document_id)
        blocks = storage.load_parse_result(document_id).blocks
        cs, _ = await extract(
            document_id=document_id, source_md_name=source_name, md=md, blocks=blocks
        )
        ctx.scratch["cs"] = cs
        st = cs.stats
        dropped = ", ".join(f"{k}={v}" for k, v in st.dropped.items()) or "none"
        return (
            f"{source_name}: {len(md)} chars / {st.chunk_count} chunks → "
            f"{st.raw_count} raw → {st.kept_count} kept (dropped {dropped})"
        )

    async def step_similar(self, ctx: JobRunContext) -> str:
        cs: QaCandidateSet = ctx.scratch["cs"]
        stats, _ = await fill_similar(cs)
        return (
            f"{stats['raw']} rephrasings → {stats['kept']} kept "
            f"(same as standard {stats['drop_same_as_standard']}, "
            f"cross-item conflicts {stats['drop_conflict']}, failed {stats['failed']})"
        )

    async def step_stage(self, ctx: JobRunContext) -> str:
        cs: QaCandidateSet = ctx.scratch["cs"]
        async with SessionLocal() as session:
            # 幂等:重跑这一步不该把候选写两遍
            existing = (
                await session.execute(
                    select(StagingItem.id).where(StagingItem.job_id == ctx.job_id)
                )
            ).all()
            if existing:
                return f"{len(existing)} candidates already staged, nothing to do"
            session.add_all(
                [
                    StagingItem(
                        job_id=ctx.job_id,
                        kb_id=ctx.kb_id,
                        item_type="qa_pair",
                        payload=c.as_payload(),
                        origin_ref=c.origin_ref.model_dump(exclude_none=True),
                        confidence=c.confidence,
                    )
                    for c in cs.candidates
                ]
            )
            await session.commit()

        faces = sum(len({c.standard_question, *c.similar_questions}) for c in cs.candidates)
        ctx.scratch["stats"] = {
            "candidates": len(cs.candidates),
            "index_faces_if_all_accepted": faces,
            **cs.stats.model_dump(exclude={"dropped"}),
            "dropped": cs.stats.dropped,
        }
        return f"Wrote {len(cs.candidates)} candidates, waiting for review"
