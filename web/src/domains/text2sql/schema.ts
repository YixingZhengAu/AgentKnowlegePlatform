/** 本域用到的生成类型别名 + 一些纯展示工具。
 *
 * 类型全部来自 `api/types.gen.ts`(`make types` 生成),**本文件不许手写 API 类型** ——
 * 这里只是把深路径起个短名字,后端改字段名时下游照样编译报错。
 */

import type { components } from '@/api/types.gen'

type S = components['schemas']

export type Datasource = S['DatasourceOut']
export type DatasourceList = S['ListResponse_DatasourceOut_']
export type DatasourceCreate = S['DatasourceCreate']
export type DatasourceUpdate = S['DatasourceUpdate']
export type ConnIn = S['DatasourceConnIn']
export type TestConnectionResult = S['TestConnectionResult']
export type JobStarted = S['JobStarted']

export type SchemaSnapshot = S['SchemaOut']
export type TableDetail = S['TableDetailOut']
export type ColumnMeta = S['ColumnMetaOut']
export type Relation = S['RelationOut']
export type EnumValue = S['EnumValueOut']
export type TableSave = S['TableSave']
export type ColumnPatch = S['ColumnPatch']
export type DescribeRequest = S['DescribeRequest']
export type DescribeSuggestion = S['DescribeSuggestion']
export type IndexStats = S['IndexStats']

/** 连接目标的可读形态 —— 与后端 `TestConnectionResult.target` 同一个写法(不含口令)。 */
export function connTarget(ds: Pick<Datasource, 'user' | 'host' | 'port' | 'database'>): string {
  return `${ds.user}@${ds.host}:${ds.port}/${ds.database}`
}

/** 一张表"治理到什么程度":列描述写满了才算完。列表页的进度点靠它。 */
export function tableDescribed(
  t: Pick<TableDetail, 'description' | 'column_count' | 'described_columns'>,
): boolean {
  return Boolean(t.description) && t.column_count > 0 && t.described_columns >= t.column_count
}

// ---------------------------------------------------------------- 意图与模板(D3/D4)

export type SqlIntent = S['SqlIntentOut']
export type SqlIntentList = S['ListResponse_SqlIntentOut_']
export type SqlIntentDetail = S['SqlIntentDetail']
export type IntentCreate = S['IntentCreate']
export type IntentUpdate = S['IntentUpdate']
export type IntentParams = S['IntentParams']
export type ParamFilter = S['ParamFilter']
export type ParamOutput = S['ParamOutput']
export type ParamGroupBy = S['ParamGroupBy']
export type IntentQuestion = S['IntentQuestionOut']
export type QuestionsGenerated = S['QuestionsGenerated']
export type QuestionsSaveResult = S['QuestionsSaveResult']
export type TemplateResult = S['TemplateResult']
export type TemplateDesign = S['TemplateDesign']
export type RunResult = S['RunResult']
export type ParseParamsResult = S['ParseParamsResult']
export type IntentPublishResult = S['IntentPublishResult']
export type GenerateIntentsRequest = S['GenerateIntentsRequest']
export type NonDataFace = S['NonDataFaceOut']
export type NonDataFaceList = S['ListResponse_NonDataFaceOut_']
export type NonDataFacesSaveResult = S['NonDataFacesSaveResult']

/** 两种意图的前缀标签 —— 与生成期 prompt 里的 `Query:` / `Stats:` 逐字一致
 *  (出处 `services/text2sql/intents.py`)。分型错了 SQL 模板一定生成不对,所以它要显眼。 */
export function intentTypeLabel(t: string): string {
  return t === 'stats' ? 'Stats' : 'Query'
}

/** 三区参数一共几个 —— "运行时能动的东西"的总量,列表页与详情页都摆这个数。 */
export function paramCount(p?: IntentParams | null): number {
  if (!p) return 0
  return p.filters.length + p.outputs.length + p.groupbys.length
}

/** 意图能不能发布,以及不能的原因 —— 原因由后端给(`publisher.publish_blockers`),
 *  前端一个字不自己编:那套校验只有一处出处。 */
export function publishable(it: Pick<SqlIntentDetail, 'publish_blockers'>): boolean {
  return it.publish_blockers.length === 0
}
