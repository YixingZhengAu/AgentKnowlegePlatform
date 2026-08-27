# workflow 域 · 结构说明

## 这个域为什么存在

第四种知识:**编排**。前三种各自回答一个问题,编排把它们按业务签过字的顺序连起来把一件事做完,
外加代码节点(阈值 / 分支)与动作节点(写库 / 外发)。层级上它与精准问答、智能问数**同级**
(都注册意图、命中即执行),文档 RAG 才是兜底 —— 这套口径的唯一出处是
`src/pages/how-it-works/`(那里的 `ROUTING` 与 `WORKFLOW`,页面是 `/how-it-works/workflow`)。

**当前范围**:导航里有位置 + 一页静态预览,**没有后端、没有表、没有 Job、没有审核台**。
所以这个域没有 `schema.ts`(不碰生成类型)、没有 `actions.ts`、没有 `renderers.tsx`。

## 页面结构(`CanvasPage.tsx`)

| 区                | 放什么                                                                 |
| ----------------- | ---------------------------------------------------------------------- |
| 顶部横幅          | 「Design preview — nothing here is wired up」+ 一句为什么 + 去说明页的按钮 |
| 画布工具条        | 编排名 + `draft` 徽标 + 节点/层/闸门计数 + **禁用的** Test run / Publish |
| 左:节点面板       | 五种可拖的节点(Trigger / Knowledge / LLM / Code / Action),色点区分     |
| 中:画布           | 八个节点竖排 + 箭头收口;点阵底纹用 `radial-gradient(var(--border-strong)…)` 画,**不引新 hex** |
| 右:节点检查器      | 选中那个知识节点:类型 / 知识来源 / 输入(标出「自动绑定自第 02 步」)/ 输出 / 只读约束 |

三份常量都在文件顶部:`PALETTE`(面板)、`NODES`(画布)、`INSPECTOR`(检查器)。
节点顺序刻意与说明页 `WORKFLOW_EXAMPLE.steps` 一致 —— 两边讲的必须是同一条编排。

**不 import 说明页的数据**:那是 `pages/`,域只允许向上依赖 shared 层(`src/{api,components,layouts,lib}`)。
所以这里是一份**刻意的手抄**,改一边就要改另一边(见本域 claude.md 的纪律)。

## 真开发的时候往哪长

| 要做的事           | 落点                                                                  |
| ------------------ | --------------------------------------------------------------------- |
| 画布编辑 / 版本 / 运行记录 | 本域新页面 + `IngestPage.tsx` 里加一条 `<Route>`(不碰共享路由表)   |
| 后端                | `server/app/services/workflow/` + `services/__init__.py` 加一行注册    |
| 知识类型            | 要进 `knowledge_bases.type` 就得先改 `documents/DB-DESIGN.md`,再改 `web/src/api/schema.ts` 的 `KB_TYPES`,并把 `domains/types.ts` 里那条「没有后端类型」的注释删掉 |
