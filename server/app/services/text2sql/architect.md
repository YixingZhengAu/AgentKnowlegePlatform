# server/app/services/text2sql/architect.md

## 定位

智能问数(Text-to-SQL) 域(S3)的落点文件夹。本域的 Job 子类、publisher、检索 stage、prompt
**都写在这里**,不散落到 core 或其他目录。

## 计划内的文件形态(与 services/architect.md 的对称约定一致)

```
text2sql/
  ingest.py     Job 子类:steps 声明 + 每步实现(产出 staging_items,item_type=table_meta/metric/term)
  publisher.py  审核通过后写正式表 + 建索引
  retrieve.py   run_chat() 里的检索 stage
```

## 红线

- **不 import 兄弟域**(exact_qa / document / text2sql 互相隔离),只向上依赖
  `app/core`、`app/models`、`app/schemas`
- Job 子类写好后,注册行加在 `app/services/__init__.py`(全局唯一注册点),
  不要在 api 层或其他地方 import
- 共享表(`ingest_jobs`/`staging_items`/`publish_records`/`knowledge_bases`)
  不得加"只有本域需要"的列 —— 差异进 payload jsonb 或本域自己的表
- 具体流程**待需求方确认写入 PRD 后再动工**,此前不加接口、不写逻辑
