/** 生成类型的可读别名 —— 页面只 import 这里,不直接碰 types.gen.ts 的深路径。
 *
 * 契约纪律:这些类型全部来自 openapi(`make types` 生成),
 * **禁止在前端手写任何 API 类型**。后端改字段名 -> 重跑 make types -> 这里下游编译报错。
 */

import type { components } from './types.gen'

type S = components['schemas']

export type KnowledgeBase = S['KnowledgeBaseOut']
export type Agent = S['AgentOut']
export type AgentDetail = S['AgentDetailOut']
export type AgentKbBinding = S['AgentKbBindingOut']
export type Conversation = S['ConversationOut']
export type Message = S['MessageOut']
export type ChatRequest = S['ChatRequest']
export type ChatResponse = S['ChatResponse']
export type TraceSpan = S['TraceSpanOut']
export type Trace = S['TraceOut']
export type Health = S['HealthResponse']

export type KbList = S['ListResponse_KnowledgeBaseOut_']
export type AgentList = S['ListResponse_AgentOut_']
export type ConversationList = S['ListResponse_ConversationOut_']
export type MessageList = S['ListResponse_MessageOut_']
export type TraceList = S['ListResponse_TraceOut_']

/** 三类知识的固定识别色(色值在 index.css,这里只做 type -> token 的映射)。 */
// 取值与 server/app/models/knowledge.py 的 KB_TYPES 一致(exact_qa / document / text2sql)
export const KB_TYPES = ['exact_qa', 'document', 'text2sql'] as const
export type KbType = (typeof KB_TYPES)[number]

export const KB_TYPE_LABEL: Record<string, string> = {
  exact_qa: 'Exact QA',
  document: 'Document RAG',
  text2sql: 'Text-to-SQL',
}

/** 识别色用固定映射而不是拼接 class 名 —— Tailwind 扫源码,拼出来的类名不会被生成。 */
export const KB_TYPE_DOT: Record<string, string> = {
  exact_qa: 'bg-kb-exact-qa',
  document: 'bg-kb-document',
  text2sql: 'bg-kb-text2sql',
}
