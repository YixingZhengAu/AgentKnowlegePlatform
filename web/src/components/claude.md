# web/src/components/

**职责**:跨页面复用的组件。**组件里禁止裸色值**,一律用 `index.css` 暴露的 token 类。

| 文件 | 说明 |
| --- | --- |
| `ui/` | shadcn 风格原子件(button/card/badge/table/input/textarea/kbd/segmented/skeleton),见 `ui/claude.md` |
| `DataState.tsx` | 列表页三态外壳:loading 骨架 / 错误+Retry / 空状态 |
| `EmptyState.tsx` | 空状态:线性图标 + 一句话 + 最多一个动作,不放插画 |
| `KbTypeTag.tsx` | 三类知识识别标(色点 + 英文标签),全站统一 |
| `StatusBadge.tsx` | 状态字符串 → 语义色徽标的**唯一映射**(ok/approved/failed…) |
| `ChatMessages.tsx` | 消息流与气泡(用户 navy 右对齐 / 助手浅填充块左对齐 + 计量) |
| `Composer.tsx` | 输入框:Enter 发送、Shift+Enter 换行、流式期间变 Stop(真 abort) |
| `TracePanel.tsx` | 执行轨迹面板:竖线时间轴,流式 span 或 `GET /api/traces/{id}`(可展开 input/output) |
| `JobProgress.tsx` | 通用任务进度条:轮询 + 声明式步骤 + 分步日志 + 从失败步骤重跑;**审核入口只在真有条目时才画**(`stats.staged`/`published` > 0) |
| `Toaster.tsx` | 订阅 `lib/toast` store 渲染 toast,固定右下角 |
| `StagingReview.tsx` | **泛型审核台**:筛选/排序/单条/批量/键盘流/发布;**动作层可由各域替换**(S1 的采纳即发布)。★ 保存不是裁决 —— 存过未裁决的那一条被钉在列表里,否则右侧详情会静默换人 |
| `Citations.tsx` | 答案下面的引用条(命中面 + 相似度 + 页码,可展开看原文摘录);**citation_type 可由各域在 `module.ts` 的 `citations` 里换成自己的渲染器**(S3 问数要画结果表格 + 最终 SQL) |
| `staging/` | 各类知识的渲染器(item_type → 卡片 + 编辑器),见 `staging/claude.md` |

详见 `architect.md`。
