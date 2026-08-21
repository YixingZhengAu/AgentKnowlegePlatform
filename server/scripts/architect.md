# server/scripts/architect.md

## 运行方式

一律 `cd server && uv run python -m scripts.<name>`(模块方式,才能 import app)。
常用的已包进 Makefile:`make seed` / `make types`。

## seed_minimal.py

- 幂等:按唯一键先查再插,`make db-reset` 会调用它
- 内容全英文(D5:平台面向澳洲用户),知识库 description 会喂给 S4 路由 LLM
- KB 绑定的 priority:精准 QA=10 / 文档=20 / 问数=30,体现"分层治理"的默认优先序

## 冒烟脚本(smoke_llm / smoke_embedding)

`make smoke` 一次跑两个。都用 **light tier**(便宜)且带断言,失败非零退出:

- `smoke_llm`:① 补全(断言非空)② 流式(打印 **first_token 延迟** —— 决定对话页体感)
  ③ JSON 模式(用的就是 S4 路由决策的 schema 形状,断言 `targets` 有值)
- `smoke_embedding`:断言每条向量维度 == `EMBEDDING_DIM`,且**同义句相似度 > 无关句**
  (只验"跑通"不够,要验向量真的有语义)

错误处理:捕获 `AppError` 只打一行 `code + message`,不刷栈 ——
冒烟脚本是给人看结论的。key 完全没配时由 `config.py` 在 import 期报 `MissingConfigError`。

## 待加(后续 Step)

- Step 8:`seed_fake_staging.py`(灌 20 条假 QA payload 验证审核台)
