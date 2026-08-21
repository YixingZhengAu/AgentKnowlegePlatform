# web/src/domains/exact-qa/ · architect

当前只有空白壳:`IngestPage.tsx` 是识别色 + EmptyState,无任何表单逻辑。

未来本域代码全部落在本文件夹(组件、hooks、审核渲染器);对外只通过 `module.ts`
描述符暴露,注册进 `../index.ts` 的 DOMAINS。禁止 import 兄弟域(document/text2sql)。

`qa_pair` 审核渲染器:尚未注册,审核台走 JSON 兜底;由本域在本文件夹实现后
在 `module.ts` 的 `renderers` 登记(契约见 `components/staging/types.ts`)。
