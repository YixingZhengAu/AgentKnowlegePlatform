# web/architect.md

## 契约链路(Step 6 建立)

```
后端改 schema -> make types -> web/openapi.json -> src/api/types.gen.ts -> 前端编译报错
```

`make types` = `scripts.dump_openapi` 导出 + `openapi-typescript` 生成。
**前端不允许手写 API 类型**,改后端字段名必须让前端编译失败(这是验收项)。

## 计划结构(Step 6/7/8)

- `src/api/client.ts`:fetch 封装,统一解析后端错误体 `{"error":{code,message,detail}}` 并 toast
- `src/api/sse.ts`:封装 Step 5 的 SSE 协议,暴露 `onToken / onStageStart / onStageEnd / onDone`
- `src/layouts/AppLayout.tsx`:navy 侧栏(220px)+ 56px 白顶栏 + 内容区 + 360px 可折叠 trace 面板
- `src/components/StagingReview/`:泛型审核台(itemRenderer / editorRenderer / originPanel 三个插槽)
- `src/pages/styleguide`:隐藏路由,平铺全部 token 与组件态,作为 UI 验收对照

## 样式纪律

token 写在 `src/index.css` + Tailwind `theme.extend`;**hex 只允许出现在 token 定义处**,
组件里禁裸色值。三类知识识别色全站一致:精准QA=黄 / 文档RAG=蓝 / 问数=紫。
