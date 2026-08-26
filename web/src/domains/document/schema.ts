/** 本域用到的生成类型别名 + jsonb 读取工具 + stage 文案/色。
 *
 * 类型全部来自 `api/types.gen.ts`(`make types` 生成),**本文件不许手写 API 类型** ——
 * 这里只是把深路径起个短名字,后端改字段名时下游照样编译报错。
 *
 * 🩸 本域的 schema 类名**刻意不叫** `DocumentOut` / `UploadResult`:那两个名字 S1 先占了,
 * 撞名会让 openapi 退化成全限定名(`app__schemas__exact_qa__UploadResult`),
 * 把**别人的**前端打断。后端那边有同样一段注释(`server/app/schemas/document.py`)。
 *
 * payload / origin_ref 是 jsonb,openapi 里只有 `dict`,所以这两个形状只能写在前端:
 * 出处是 `server/app/schemas/document.py` 的 `Chunk.as_payload()` 与
 * `services/document/ingest.py` 里塞 `origin_ref` 的那几行,它们变了这里要跟着变。
 */

import type { components } from '@/api/types.gen'

type S = components['schemas']

export type DocumentOut = S['DocumentSummary']
export type DocumentList = S['ListResponse_DocumentSummary_']
export type UploadResult = S['IngestSubmitted']
export type MergeResult = S['ChunkMergeResult']
/** 点开引用 `[n]` 时实时读回来的切片全文 + 元数据。 */
export type ChunkDetail = S['ChunkDetail']

// ── 运营(S2-4)────────────────────────────────────────────────────────────
/** 切片管理页的一行:已发布的**正式行**,不是待审候选。 */
export type PublishedChunk = S['PublishedChunk']
export type PublishedChunkList = S['ListResponse_PublishedChunk_']
/** 启用/禁用的回执。启用要重算 embedding,所以按钮必须有 loading 态。 */
export type ChunkStatusResult = S['ChunkStatusResult']
/** 单文档重跑的回执。 */
export type ReingestResult = S['ReingestSubmitted']

// ── 检索调试台 ─────────────────────────────────────────────────────────────
export type SearchResult = S['SearchResult']
export type SearchHit = S['SearchHit']

/** 文档的推导态(出处 `server/app/api/document.py` 的 stage 推导);
 *  取值集合由 `DocumentOut['stage']` 钉住,后端加一态这里会漏但不会错配。 */
export type DocumentStage = DocumentOut['stage']

export const STAGE_LABEL: Record<string, string> = {
  pending: 'Queued',
  ingesting: 'Ingesting',
  review: 'Chunks to review',
  published: 'Published',
  failed: 'Failed',
}

/** 还在跑的阶段:列表要不要继续轮询,只看这一个判断。 */
export const STAGE_ACTIVE = ['pending', 'ingesting']

export function isStageActive(stage?: string | null): boolean {
  return stage != null && STAGE_ACTIVE.includes(stage)
}

export function stageTone(stage: string): 'success' | 'danger' | 'info' | 'accent' | 'neutral' {
  if (stage === 'published') return 'success'
  if (stage === 'failed') return 'danger'
  if (isStageActive(stage)) return 'info'
  // 待人工处理的那一态用强调色:意思就是"该点这里了"(UI-STYLE §1)
  if (stage === 'review') return 'accent'
  return 'neutral'
}

/** 切片里的一张图/表,对应 payload 的 `figures[]` 一项。 */
export type Figure = {
  kind: 'image' | 'chart' | 'table'
  /** 相对路径 `images/<sha256>.jpg`,拼成 URL 见 `files.ts` */
  img: string
  description: string | null
  /** 描述被模型截断过 —— 审核时要看得见 */
  truncated: boolean
  source_caption: string[]
  source_footnote: string[]
  page_idx: number
  bbox: number[] | null
}

export type ChunkPayload = {
  seq: number
  content: string
  heading_path: string[]
  token_count: number
  page_idx: number
  bbox: number[] | null
  figures: Figure[]
}

const FIGURE_KINDS = ['image', 'chart', 'table']

/** 读一条图表:openapi 生成的 `Figure` 字段带默认值(TS 里是可选),
 *  jsonb 来的更是什么都可能缺 —— 两个来源都过这里补齐。 */
export function readFigure(value: unknown): Figure | null {
  if (!value || typeof value !== 'object') return null
  const o = value as Record<string, unknown>
  if (typeof o.img !== 'string') return null
  const kind = typeof o.kind === 'string' && FIGURE_KINDS.includes(o.kind) ? o.kind : 'image'
  return {
    kind: kind as Figure['kind'],
    img: o.img,
    description: typeof o.description === 'string' ? o.description : null,
    truncated: o.truncated === true,
    source_caption: readStrList(o.source_caption),
    source_footnote: readStrList(o.source_footnote),
    page_idx: typeof o.page_idx === 'number' ? o.page_idx : 0,
    bbox: Array.isArray(o.bbox) ? (o.bbox as number[]) : null,
  }
}

function readStrList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((x): x is string => typeof x === 'string') : []
}

/** 读切片 payload:jsonb 来的东西不能假设类型,缺什么给什么兜底。 */
export function readChunkPayload(payload: Record<string, unknown>): ChunkPayload {
  return {
    seq: typeof payload.seq === 'number' ? payload.seq : 0,
    content: typeof payload.content === 'string' ? payload.content : '',
    heading_path: readStrList(payload.heading_path),
    token_count: typeof payload.token_count === 'number' ? payload.token_count : 0,
    page_idx: typeof payload.page_idx === 'number' ? payload.page_idx : 0,
    bbox: Array.isArray(payload.bbox) ? (payload.bbox as number[]) : null,
    figures: Array.isArray(payload.figures)
      ? payload.figures.map(readFigure).filter((f): f is Figure => f !== null)
      : [],
  }
}

/** 本域的 origin_ref 形状 —— **不是** `components['schemas']['OriginRef']`:
 *  那个是 S1 精准 QA 的(quote + page_idx),本域塞的是 `{document_id, page, bbox}`。 */
export type ChunkOrigin = {
  document_id: string
  page: number
  bbox: number[] | null
}

export function readOriginRef(value: unknown): ChunkOrigin | null {
  if (!value || typeof value !== 'object') return null
  const o = value as Record<string, unknown>
  if (typeof o.document_id !== 'string') return null
  return {
    document_id: o.document_id,
    page: typeof o.page === 'number' ? o.page : 0,
    bbox: Array.isArray(o.bbox) ? (o.bbox as number[]) : null,
  }
}

/** 标题路径的短展示形态:**按层级砍,不按字符砍**。
 *
 * 与后端 `schemas/document.py::short_heading` 同一条规则:按字符截会从单词中间切开
 * (`Battery Storage` → `ery Storage`),看着像解析坏了。最有信息量的是末几级。
 *
 * @param path 标题路径,由外到内。
 * @param keep 保留末几级,默认 2。
 * @returns 形如 `… > Sizing > Battery`;路径为空时返回空串。
 */
export function shortHeadingPath(path: string[], keep = 2): string {
  if (path.length <= keep) return path.join(' > ')
  return `… > ${path.slice(-keep).join(' > ')}`
}
