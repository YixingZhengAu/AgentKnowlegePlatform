# Clenergy 企业知识 Agent 系统 —— 开发命令入口
# 详细说明见 README.md

.PHONY: help db db-stop db-wait migrate seed db-reset api web dev types install psql smoke test

SHELL := /bin/bash
COMPOSE := docker compose
PG_CONTAINER := agent_system_pg

help:  ## 列出所有命令
	grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

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

test:  ## 跑离线测试(不联网、不连 DB)
	cd server && uv run pytest -q


types:  ## openapi.json -> web/src/api/types.gen.ts(前端禁止手写 API 类型)
	cd server && uv run python -m scripts.dump_openapi ../web/openapi.json
	cd web && npx --yes openapi-typescript openapi.json -o src/api/types.gen.ts

install:  ## 安装前后端依赖
	cd server && uv sync
	cd web && npm install
