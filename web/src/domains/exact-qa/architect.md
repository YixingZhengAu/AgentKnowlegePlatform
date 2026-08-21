# web/src/domains/exact-qa/ · architect

当前只有空白壳:`IngestPage.tsx` 是识别色 + EmptyState,无任何表单逻辑。

未来本域代码全部落在本文件夹(组件、hooks、审核渲染器);对外只通过 `module.ts`
描述符暴露,注册进 `../index.ts` 的 DOMAINS。禁止 import 兄弟域(document/text2sql)。

`qa_pair` 审核渲染器:Stage 1 过渡期由 shared 层 `components/staging/QaRenderers.tsx`
提供并在 `module.ts` 注册;Stage 2 删除后 qa_pair 走 JSON 兜底,真实渲染器由本域重写。
