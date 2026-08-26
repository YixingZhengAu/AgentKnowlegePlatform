# 企业知识 Agent 系统 —— 开发命令入口
# 详细说明见 README.md

.PHONY: help bootstrap db db-stop db-wait migrate seed db-reset bizdb bizdb-wait bizdb-verify bizdb-reset bizdb-seed-gen seed-s3 mysql mineru mineru-stop rerank-model api web dev types install psql smoke smoke-s1 smoke-s2 smoke-s2-rerun smoke-s3 smoke-s3-api smoke-s3-chat smoke-sse test lint demo

SHELL := /bin/bash
COMPOSE := docker compose
PG_CONTAINER := agent_system_pg
BIZ_CONTAINER := agent_system_bizdb
MINERU_CONTAINER := agent_system_mineru

help:  ## 列出所有命令
	grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ===== 一键装环境 =====

bootstrap:  ## 新机器从零装:工具链检查 + .env + 依赖 + 库 + 迁移 + seed + 自检(细节见 bootstrap.sh --help)
	./bootstrap.sh

# ===== 数据库 =====

db:  ## 起系统库 Postgres(pgvector)+ 演示业务库 MySQL,等到都健康为止
	$(COMPOSE) up -d postgres biz-mysql
	@$(MAKE) --no-print-directory db-wait
	@$(MAKE) --no-print-directory bizdb-wait

db-stop:  ## 停两个数据库(保留数据)
	$(COMPOSE) stop postgres biz-mysql

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
	@# 只删 pg 的数据卷:compose down -v 会把 MinerU 那 1GB 权重卷也删掉,重下很贵
	@vol=$$(docker inspect $(PG_CONTAINER) --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' 2>/dev/null); \
		$(COMPOSE) rm -sf postgres >/dev/null 2>&1 || true; \
		if [ -n "$$vol" ]; then docker volume rm -f "$$vol" >/dev/null; echo "已删数据卷 $$vol"; fi
	@$(MAKE) --no-print-directory db
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed

# ===== 演示业务库(S3 问数的查询目标,独立 MySQL 8.4 / 3307)=====

bizdb:  ## 只起演示业务库 MySQL,等到健康为止
	$(COMPOSE) up -d biz-mysql
	@$(MAKE) --no-print-directory bizdb-wait

bizdb-wait:
	@echo "等待业务库 MySQL 就绪..."
	@for i in $$(seq 1 60); do \
		if [ "$$(docker inspect $(BIZ_CONTAINER) --format '{{.State.Health.Status}}' 2>/dev/null)" = healthy ]; then \
			echo "业务库就绪(127.0.0.1:3307,只读账号 biz_reader)"; exit 0; \
		fi; sleep 1; \
	done; echo "业务库启动超时(看 docker compose logs biz-mysql)"; exit 1

bizdb-verify:  ## 业务库自检:27 项断言(行数/对账/日期覆盖/库存流水/只读账号)
	cd server && uv run python -m scripts.verify_bizdb

mysql:  ## 进业务库 mysql(只读账号)
	docker exec -it $(BIZ_CONTAINER) mysql -ubiz_reader -pbiz_reader demo_biz

bizdb-reset:  ## 删业务库数据卷重建(init 脚本只在首次创建时执行,改了 SQL 必须走这条)
	@vol=$$(docker inspect $(BIZ_CONTAINER) --format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}' 2>/dev/null); \
		$(COMPOSE) rm -sf biz-mysql >/dev/null 2>&1 || true; \
		if [ -n "$$vol" ]; then docker volume rm -f "$$vol" >/dev/null; echo "已删业务库数据卷 $$vol"; fi
	@$(MAKE) --no-print-directory bizdb
	@$(MAKE) --no-print-directory bizdb-verify

bizdb-seed-gen:  ## 重新生成 03-seed.sql(改了生成器才用;之后必须 make bizdb-reset)
	cd docker/mysql && python3 gen_seed.py

# ===== 重排模型(S2 文档 RAG)=====

rerank-model:  ## 预下载重排模型权重(~90MB;运行时走离线缓存,省掉每次 8.6s 的版本核对)
	cd server && uv run python -m scripts.fetch_rerank_model

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

smoke-s2:  ## 冒烟:S2 文档 RAG 运营层(禁用/启用 · 引用回显 · 检索调试台;不留痕。需先 make api)
	cd server && ./scripts/smoke_s2_api.sh

smoke-s2-rerun:  ## 冒烟:S2 单文档重跑(分册 4 §6 第四条)。⚠ 会改演示数据、花钱,演示前不要跑
	cd server && ./scripts/smoke_s2_api.sh --with-rerun

seed-s3:  ## 灌 S3 演示知识(数据源 + 语义层 + 7 个已验证意图 + 索引面;幂等)
	cd server && uv run python -m scripts.seed_s3_demo

smoke-s3:  ## 冒烟:S3 智能问数(业务库 27 项 + 索引对数 + 评测集在正式代码路径下重跑,零 LLM)
	cd server && uv run python -m scripts.verify_bizdb
	cd server && uv run python -m scripts.smoke_s3_index
	cd server && uv run python -m scripts.smoke_s3_e2e --check

smoke-s3-api:  ## 冒烟:S3 HTTP 层 27 步(含错误路径;不留痕、零 LLM。需先 make api)
	cd server && ./scripts/smoke_s3_api.sh

smoke-s3-chat:  ## 冒烟:S3 问数接进 chat 的三问(命中/模板外/非问数 + SSE 协议,真调 LLM)
	cd server && uv run python -m scripts.smoke_s3_chat

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
