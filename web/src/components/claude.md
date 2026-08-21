# web/src/components/

**职责**:跨页面复用的组件。**组件里禁止裸色值**,一律用 `index.css` 暴露的 token 类。

| 文件 | 说明 |
| --- | --- |
| `ui/` | shadcn 风格原子件(button/card/badge/table/input/skeleton),见 `ui/claude.md` |
| `DataState.tsx` | 列表页三态外壳:loading 骨架 / 错误+Retry / 空状态 |
| `EmptyState.tsx` | 空状态:线性图标 + 一句话 + 最多一个动作,不放插画 |
| `KbTypeTag.tsx` | 三类知识识别标(色点 + 英文标签),全站统一 |
| `StatusBadge.tsx` | 状态字符串 → 语义色徽标的**唯一映射**(ok/approved/failed…) |
| `ChatMessages.tsx` | 消息流与气泡(用户 navy 右对齐 / 助手白卡片左对齐 + 计量) |
| `Composer.tsx` | 输入框:Enter 发送、Shift+Enter 换行、流式期间变 Stop(真 abort) |
| `TracePanel.tsx` | 执行轨迹面板:流式 span 或 `GET /api/traces/{id}`(可展开 input/output) |
| `JobProgress.tsx` | 通用任务进度条:轮询 + 声明式步骤 + 分步日志 + 从失败步骤重跑 |
| `Toaster.tsx` | 订阅 `lib/toast` store 渲染 toast,固定右下角 |

Step 8 的泛型审核台 `StagingReview/` 也放这里。详见 `architect.md`。
