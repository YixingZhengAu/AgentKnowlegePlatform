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

## 注册机制(结构调整 Stage 3 落地)

Job 子类靠 import 副作用写入 `core/jobs.py` 的注册表,注册链是:

```
api/jobs.py ──import──▶ app.services(__init__.py)──import──▶ core.jobs_demo(现)
                                                  └─import──▶ services.<域>.ingest(S1–S3 各加一行)
```

- `services/__init__.py` 是**唯一注册点**:api 层不认识任何具体域,加/删一个域的任务
  只改这一个文件的一行 —— 三个开发者并行时,这是后端唯一的共享落笔点(相邻行,git 可自动合并)
- 各域内部文件随便加,不需要动共享文件;router 等真需要时作为公共契约变更单独提

## 并行开发红线

- **不 import 兄弟域**;只向上依赖 core/models/schemas
- 共享表(`ingest_jobs`/`staging_items`/`publish_records`/`knowledge_bases`)不加域私有列,
  差异进 payload jsonb 或本域自己的表
- migration 串行生成:域开发者只改 models 里自己域的文件,不自己 `alembic revision`
  (集成者统一生成,避免 multiple heads,详见 `server/claude.md`)
