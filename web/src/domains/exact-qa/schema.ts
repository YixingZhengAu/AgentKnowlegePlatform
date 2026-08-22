/** 本域用到的生成类型别名 + payload 读取工具。
 *
 * 类型全部来自 `api/types.gen.ts`(`make types` 生成),**本文件不许手写 API 类型** ——
 * 这里只是把深路径起个短名字,后端改字段名时下游照样编译报错。
 */

import type { components } from '@/api/types.gen'

type S = components['schemas']

export type ExactQaDocument = S['DocumentOut']
export type DocumentList = S['ListResponse_DocumentOut_']
export type DocumentFunnel = S['DocumentFunnel']
export type UploadResult = S['UploadResult']
export type ReviewText = S['ReviewTextOut']
export type ConfirmExtractResult = S['ConfirmExtractResult']
export type QaItem = S['ExactQaItemOut']
export type QaItemDetail = S['ExactQaItemDetail']
export type QaItemList = S['ListResponse_ExactQaItemOut_']
export type OriginRef = S['OriginRef']
export type PageInfo = S['PageInfo']

/** 文档的推导态(出处 `server/app/api/exact_qa.py::_stage`)—— 这不是 API 字段名,
 *  是那个函数的取值集合,所以允许写在前端;它一变,这张表就得跟着变。 */
export const STAGE_LABEL: Record<string, string> = {
  pending: 'Queued',
  parsing: 'Parsing',
  review_text: 'Ready to proofread',
  extracting: 'Extracting Q&A',
  extract_failed: 'Extraction failed',
  review_qa: 'Candidates to review',
  done: 'Done',
  failed: 'Parse failed',
}

/** 还在跑的阶段:列表要不要继续轮询,只看这一个判断。 */
export const STAGE_ACTIVE = ['pending', 'parsing', 'extracting']

export function isStageActive(stage?: string | null): boolean {
  return stage != null && STAGE_ACTIVE.includes(stage)
}

export function stageTone(stage: string): 'success' | 'danger' | 'info' | 'accent' | 'neutral' {
  if (stage === 'done') return 'success'
  if (stage === 'failed' || stage === 'extract_failed') return 'danger'
  if (isStageActive(stage)) return 'info'
  // 待人工处理的两个阶段用强调色:黄色的意思就是"该点这里了"(UI-STYLE §1)
  if (stage === 'review_text' || stage === 'review_qa') return 'accent'
  return 'neutral'
}

/** 候选 payload 的形状(出处 DB-DESIGN §8 的 qa_pair payload / `QaCandidate.as_payload()`)。
 *  jsonb 在 openapi 里只有 `dict`,所以取字段一律经过这里,不假设类型。 */
export type QaPayload = {
  standard_question: string
  answer: string
  keywords: string[]
  similar_questions: string[]
}

export function readQaPayload(payload: Record<string, unknown>): QaPayload {
  const list = (key: string): string[] => {
    const v = payload[key]
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
  }
  const text = (key: string): string => {
    const v = payload[key]
    return typeof v === 'string' ? v : ''
  }
  return {
    standard_question: text('standard_question'),
    answer: text('answer'),
    keywords: list('keywords'),
    similar_questions: list('similar_questions'),
  }
}

/** `staging_items.origin_ref` 也是 jsonb —— 同理,读它要挡一层。 */
export function readOriginRef(value: unknown): OriginRef | null {
  if (!value || typeof value !== 'object') return null
  const o = value as Record<string, unknown>
  if (typeof o.document_id !== 'string' || typeof o.quote !== 'string') return null
  return {
    document_id: o.document_id,
    quote: o.quote,
    page_idx: typeof o.page_idx === 'number' ? o.page_idx : 0,
    bbox: Array.isArray(o.bbox) ? (o.bbox as number[]) : null,
  }
}
