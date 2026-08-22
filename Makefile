# Clenergy 企业知识 Agent 系统 —— 开发命令入口
# 详细说明见 README.md

.PHONY: help db db-stop db-wait migrate seed db-reset mineru mineru-stop api web dev types install psql smoke smoke-s1 smoke-sse test lint demo

SHELL := /bin/bash
COMPOSE := docker compose
PG_CONTAINER := agent_system_pg
MINERU_CONTAINER := agent_system_mineru

help:  ## 列出所有命令
	grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ===== 数据库 =====

db:  ## 起 Postgres(pgvector),等到健康为止
	$(COMPOSE) up -d postgres
	@$(MAKE) --no-print-directory db-wait

db-stop:  ## 停 Postgres(保留数据)
	$(COMPOSE) stop postgres

db-wait:
	@echo "等待 Postgres 就绪..."
	@for i in $$(seq 1 40); do \
		if docker exec $(PG_CONTAINER) pg_isready -U postgres -d agent_system >/dev/null 2>&1; then \
			echo "Postgres 就绪"; exit 0; \
		fi; sleep 1; \
	done; echo "Postgres 启动超时"; exit 1

psql:  ## 进系统库 psql
	docker exec -it $(PG_CONTAINER) psql -U postgres -d agent_system

migrate:  ## 跑 Alembic 迁移到最新
	cd server && uv run alembic upgrade head

seed:  ## 灌最小演示数据(1 用户 / 1 agent / 3 个空 KB)
	cd server && uv run python -m scripts.seed_minimal

db-reset:  ## 删库重建 + 迁移 + seed(改表零成本的底气,会丢数据)
	$(COMPOSE) down -v
	@$(MAKE) --no-print-directory db
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed

# ===== PDF 解析服务(S1)=====

mineru:  ## 起 MinerU 解析容器(18001;首次会 build 镜像 + 下 1GB 权重)
	$(COMPOSE) up -d mineru-api
	@echo "等待 MinerU 就绪..."
	@for i in $$(seq 1 60); do \
		if [ "$$(docker inspect $(MINERU_CONTAINER) --format '{{.State.Health.Status}}' 2>/dev/null)" = healthy ]; then \
			echo "MinerU 就绪(http://127.0.0.1:18001)"; exit 0; \
		fi; sleep 3; \
	done; echo "MinerU 启动超时"; exit 1

mineru-stop:  ## 停 MinerU 解析容器(保留模型权重卷)
	$(COMPOSE) stop mineru-api

# ===== 开发服务 =====

api:  ## 只起后端(8000)
	cd server && uv run uvicorn app.main:app --reload --port 8000

web:  ## 只起前端(5173)
	cd web && npm run dev

dev:  ## 前后端一起起(Ctrl-C 一起停)
	@trap 'kill 0' EXIT INT TERM; \
	( cd server && uv run uvicorn app.main:app --reload --port 8000 ) & \
	( cd web && npm run dev ) & \
	wait

# ===== 契约与依赖 =====

smoke:  ## 冒烟:真实调 LLM 与 Embedding(会花一点钱,验证 key/网络)
	cd server && uv run python -m scripts.smoke_llm
	cd server && uv run python -m scripts.smoke_embedding

smoke-s1:  ## 冒烟:S1 精准问答全链路(LLM 三点 + 存储/pgvector 对数 + HTTP 13 步 + chat 三问)
	cd server && uv run python -m scripts.smoke_exact_qa
	cd server && uv run python -m scripts.smoke_exact_qa_store
	cd server && ./scripts/smoke_s1_api.sh
	cd server && uv run python -m scripts.smoke_s1_chat

smoke-sse:  ## 冒烟:前端 SSE 客户端打真后端(需先 make api / make dev)
	cd web && npm run smoke:sse

test:  ## 跑离线测试(不联网、不连 DB)
	cd server && uv run pytest -q

lint:  ## 后端 ruff + 前端 eslint + TS 编译(契约链路的守门人)
	cd server && uv run ruff check app scripts tests
	cd web && npm run lint && npx tsc -b


demo:  ## 打一份静态预览(fixture 数据、零后端、零外部请求)-> web/dist-demo/preview.html
	cd web && npx vite build --config vite.config.demo.ts
	cd web && node demo/inline.mjs

types:  ## openapi.json -> web/src/api/types.gen.ts(前端禁止手写 API 类型)
	cd server && uv run python -m scripts.dump_openapi ../web/openapi.json
	cd web && npx --yes openapi-typescript openapi.json -o src/api/types.gen.ts

install:  ## 安装前后端依赖
	cd server && uv sync
	cd web && npm install
