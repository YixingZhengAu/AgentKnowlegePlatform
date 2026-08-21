# server/app/services/architect.md

## 分域约定

每个知识域一个子包,内部固定三块职责,便于三个模块横向对照(面试可讲的对称性):

```
<domain>/
  ingest.py     Job 子类:steps 声明 + 每步实现(产出 staging_items)
  publisher.py  审核通过后写正式表 + 建索引
  retrieve.py   run_chat() 里的检索 stage
```

- Job 框架、staging 审核、发布骨架都在 `app/core`,这里只填各域差异
- 检索 stage 统一返回结构(证据列表 + 引用),由 `core/chat.py` 汇总成 citations
