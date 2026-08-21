# server/scripts/architect.md

## 运行方式

一律 `cd server && uv run python -m scripts.<name>`(模块方式,才能 import app)。
常用的已包进 Makefile:`make seed` / `make types`。

## seed_minimal.py

- 幂等:按唯一键先查再插,`make db-reset` 会调用它
- 内容全英文(D5:平台面向澳洲用户),知识库 description 会喂给 S4 路由 LLM
- KB 绑定的 priority:精准 QA=10 / 文档=20 / 问数=30,体现"分层治理"的默认优先序

## 待加(后续 Step)

- Step 4:`smoke_llm.py`(补全 + 流式 + JSON 模式)、`smoke_embedding.py`(维度 + 余弦相似度)
- Step 8:`seed_fake_staging.py`(灌 20 条假 QA payload 验证审核台)
