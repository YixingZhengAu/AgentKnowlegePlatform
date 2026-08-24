#!/usr/bin/env bash
# 企业知识 Agent 系统 —— 一键装环境
#
# 干什么:把「新克隆的仓库」变成「能跑起来的系统」——检查工具链、生成 .env、装前后端依赖、
#        起 Postgres(pgvector)与演示业务库 MySQL、建表、灌演示数据,最后自检一遍并打印下一步。
# 幂等:重复跑安全(依赖是 sync、迁移到 head、seed 是 upsert;已存在的 .env 不会被覆盖)。
#
# 用法:./bootstrap.sh [选项]
#   --with-mineru   连 PDF 解析容器一起装(build 镜像 + 下 1GB 权重,约 10 分钟;S1 上传解析要用)
#   --reset         先删库重建(会丢现有演示数据;两个数据库的卷都删)
#   --skip-smoke    跳过真实调 LLM/Embedding 的冒烟(省钱,但也就不验 key 是否可用)
#   -y, --yes       非交互:缺 uv 直接装,不再问任何确认(CI / 无人值守用)
#   -h, --help      看这段说明
#
# 不管什么:公网部署(HTTPS / 反代 / 常驻 / 密码门)—— 那是 deploy/ 的事,见 documents/DEPLOY.md。
#          本脚本只负责把机器变成"能跑",线上线下走同一条路径。
#
# 装不了的东西(需要系统级安装,脚本只检查并给出装法):Docker、Node 22+。
# uv 缺失时可以由脚本装(官方 installer)。Python 3.13 不用手动装,uv sync 会自己拉。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# ===== 输出与状态 =====

if [[ -t 1 ]]; then
	C_RESET=$'\033[0m'; C_STEP=$'\033[36m'; C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_DIM=$'\033[2m'
else
	C_RESET=''; C_STEP=''; C_OK=''; C_WARN=''; C_ERR=''; C_DIM=''
fi

STEP_NO=0
TOTAL_STEPS=8
WARN_COUNT=0
# 模板必须带 XXXXXX:GNU mktemp 的 -t 不接受纯前缀(BSD 接受),写死前缀会让这个脚本只能在 macOS 上跑
WARN_LOG="$(mktemp -t bootstrap-warn.XXXXXX)"

step()  { STEP_NO=$((STEP_NO + 1)); printf '\n%s[%d/%d] %s%s\n' "$C_STEP" "$STEP_NO" "$TOTAL_STEPS" "$1" "$C_RESET"; }
ok()    { printf '  %s✅%s %s\n' "$C_OK" "$C_RESET" "$1"; }
info()  { printf '  %s·%s  %s\n' "$C_DIM" "$C_RESET" "$1"; }
warn()  { printf '  %s⚠%s  %s\n' "$C_WARN" "$C_RESET" "$1"; WARN_COUNT=$((WARN_COUNT + 1)); printf '%s\n' "$1" >> "$WARN_LOG"; }
die()   { printf '\n  %s✗%s %s\n\n' "$C_ERR" "$C_RESET" "$1" >&2; exit 1; }

# 出错时告诉用户失败在哪一步,而不是只留一行 shell 报错
on_exit() {
	local code=$?
	rm -f "$WARN_LOG"
	if [[ $code -ne 0 ]]; then
		local where="第 ${STEP_NO}/${TOTAL_STEPS} 步"
		[[ $STEP_NO -eq 0 ]] && where="参数解析阶段"
		printf '\n%s✗ bootstrap 在%s失败(exit=%d)。修掉上面的报错后重跑本脚本即可(幂等)。%s\n\n' \
			"$C_ERR" "$where" "$code" "$C_RESET" >&2
	fi
	exit $code
}
trap on_exit EXIT

# ===== 参数 =====

WITH_MINERU=0
DO_RESET=0
SKIP_SMOKE=0
ASSUME_YES=0

while [[ $# -gt 0 ]]; do
	case "$1" in
		--with-mineru) WITH_MINERU=1 ;;
		--reset)       DO_RESET=1 ;;
		--skip-smoke)  SKIP_SMOKE=1 ;;
		-y|--yes)      ASSUME_YES=1 ;;
		# 说明就是文件头那段注释,只此一份,不会和代码走散
		-h|--help)     awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "${BASH_SOURCE[0]}"; exit 0 ;;
		*)             die "未知参数 $1(看 ./bootstrap.sh --help)" ;;
	esac
	shift
done
[[ $WITH_MINERU -eq 1 ]] && TOTAL_STEPS=9

confirm() {  # confirm "问题" -> 0=yes;-y 时一律 yes;非交互终端一律 no
	[[ $ASSUME_YES -eq 1 ]] && return 0
	[[ -t 0 ]] || return 1
	local reply
	read -r -p "  ? $1 [y/N] " reply
	[[ "$reply" =~ ^[Yy]$ ]]
}

printf '%s=== 企业知识 Agent 系统 · 一键装环境 ===%s\n' "$C_STEP" "$C_RESET"
info "仓库:$REPO_ROOT"

# ===== 1. 工具链 =====

step "检查工具链"

command -v docker >/dev/null 2>&1 || die "缺 Docker。装法:https://docs.docker.com/desktop/ (macOS 也可 brew install --cask docker),装完启动 Docker Desktop 再重跑。"
docker info >/dev/null 2>&1 || die "Docker 装了但守护进程没起。启动 Docker Desktop(或 systemctl start docker)后重跑。"
docker compose version >/dev/null 2>&1 || die "缺 docker compose v2(本项目用 'docker compose' 而非老的 'docker-compose')。升级 Docker 到 28+。"
ok "docker $(docker version --format '{{.Server.Version}}') + compose v2,守护进程在跑"

if ! command -v node >/dev/null 2>&1; then
	die "缺 Node。装法:brew install node@22 或 https://nodejs.org/(需要 22+)。"
fi
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [[ "$NODE_MAJOR" -lt 22 ]]; then
	die "Node 版本太低($(node -v)),需要 22+。装法:brew install node@22 或用 nvm install 22。"
fi
command -v npm >/dev/null 2>&1 || die "有 node 没 npm,检查 Node 安装是否完整。"
ok "node $(node -v) / npm $(npm -v)"

if ! command -v uv >/dev/null 2>&1; then
	warn "缺 uv(本项目 Python 依赖只用 uv,禁止 pip install)"
	if confirm "现在用官方 installer 装 uv?"; then
		curl -LsSf https://astral.sh/uv/install.sh | sh
		# installer 装到 ~/.local/bin,当前 shell 还没有它
		export PATH="$HOME/.local/bin:$PATH"
		command -v uv >/dev/null 2>&1 || die "uv 装完仍不在 PATH。把 \$HOME/.local/bin 加进 PATH 后重跑。"
		warn "uv 装在 \$HOME/.local/bin —— 记得把它加进你 shell 配置的 PATH,否则新终端里 make 命令会找不到 uv"
	else
		die "没有 uv 装不下去。装法:curl -LsSf https://astral.sh/uv/install.sh | sh 或 brew install uv"
	fi
fi
ok "uv $(uv --version | awk '{print $2}')(Python 3.13 由它自动拉,不用手装)"

command -v openssl >/dev/null 2>&1 || warn "缺 openssl,生成不了 SECRET_KEY(见下一步提示)"

# ===== 2. .env =====

step "准备 .env(密钥只留本地,永不入库)"

if [[ -f .env ]]; then
	ok ".env 已存在,不动它(要重来就先手动删掉)"
else
	cp .env.example .env
	ok "从 .env.example 生成 .env"
	if command -v openssl >/dev/null 2>&1; then
		# Fernet key = urlsafe base64 的 32 字节
		FERNET="$(openssl rand -base64 32 | tr '+/' '-_')"
		# BSD sed 与 GNU sed 的 -i 语义不同,统一用临时文件
		sed "s|^SECRET_KEY=.*|SECRET_KEY=${FERNET}|" .env > .env.tmp && mv .env.tmp .env
		ok "SECRET_KEY 已自动生成(Fernet,44 字符)"
	else
		warn "SECRET_KEY 仍是占位符,手动生成:openssl rand -base64 32 | tr '+/' '-_'"
	fi
fi

if grep -q '^OPENAI_API_KEY=sk-你的key' .env; then
	if [[ $ASSUME_YES -eq 0 && -t 0 ]]; then
		printf '  ? 粘贴 OPENAI_API_KEY(直接回车跳过,之后手填):'
		read -r OPENAI_KEY
		if [[ -n "$OPENAI_KEY" ]]; then
			sed "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${OPENAI_KEY}|" .env > .env.tmp && mv .env.tmp .env
			ok "OPENAI_API_KEY 已写入 .env"
		else
			warn "OPENAI_API_KEY 还是占位符 —— 问答与抽取都会失败,记得填 .env"
		fi
	else
		warn "OPENAI_API_KEY 还是占位符 —— 问答与抽取都会失败,记得填 .env"
	fi
else
	ok "OPENAI_API_KEY 已配置"
fi

# ===== 3. 依赖 =====

step "装依赖(后端 uv sync + 前端 npm)"

(cd server && uv sync)
ok "后端依赖就绪(server/.venv)"

if [[ -f web/package-lock.json ]]; then
	npm --prefix web ci
else
	npm --prefix web install
fi
ok "前端依赖就绪(web/node_modules)"

# ===== 4. 数据库容器 =====

step "起 Postgres 16 + pgvector"

if [[ $DO_RESET -eq 1 ]]; then
	if confirm "--reset 会删掉两个数据库的卷(现有演示数据全丢),继续?"; then
		# 只删 pg 的卷:compose down -v 会连 MinerU 那 1GB 权重卷一起删掉,重下很贵
		PGVOL="$(docker inspect agent_system_pg \
			--format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' 2>/dev/null || true)"
		docker compose rm -sf postgres >/dev/null 2>&1 || true
		if [[ -n "$PGVOL" ]]; then
			docker volume rm -f "$PGVOL" >/dev/null
			ok "旧数据卷已删($PGVOL);MinerU 权重卷未受影响"
		else
			warn "没找到已有的 pg 数据卷(容器可能从没起过),当作全新安装继续"
		fi
		BIZVOL="$(docker inspect agent_system_bizdb \
			--format '{{range .Mounts}}{{if eq .Destination "/var/lib/mysql"}}{{.Name}}{{end}}{{end}}' 2>/dev/null || true)"
		docker compose rm -sf biz-mysql >/dev/null 2>&1 || true
		if [[ -n "$BIZVOL" ]]; then
			docker volume rm -f "$BIZVOL" >/dev/null
			ok "旧业务库数据卷已删($BIZVOL)"
		fi
	else
		die "已取消(去掉 --reset 再跑)"
	fi
fi

docker compose up -d postgres
info "等 Postgres 就绪..."
for _ in $(seq 1 60); do
	if docker exec agent_system_pg pg_isready -U postgres -d agent_system >/dev/null 2>&1; then
		READY=1; break
	fi
	sleep 1
done
[[ "${READY:-0}" -eq 1 ]] || die "Postgres 60s 内没就绪。看日志:docker compose logs postgres"
ok "Postgres 就绪(localhost:5432);扩展 vector / pgcrypto 已装"

# ===== 5. 演示业务库(S3 问数的查询目标)=====

step "起演示业务库 MySQL 8.4(demo_biz,只读账号 biz_reader)"

docker compose up -d biz-mysql
info "等业务库就绪(首次启动要建表 + 灌 24 个月的演示数据)..."
for _ in $(seq 1 120); do
	if [[ "$(docker inspect agent_system_bizdb --format '{{.State.Health.Status}}' 2>/dev/null)" == healthy ]]; then
		BIZ_READY=1; break
	fi
	sleep 2
done
if [[ "${BIZ_READY:-0}" -eq 1 ]]; then
	ok "业务库就绪(127.0.0.1:3307);init 脚本已建七表并灌数"
else
	die "业务库 4 分钟内没就绪。看日志:docker compose logs biz-mysql"
fi

# ===== 6. 建表 + 演示数据 =====

step "建表(Alembic)+ 灌最小演示数据"

(cd server && uv run alembic upgrade head)
ok "迁移到 head"
(cd server && uv run python -m scripts.seed_minimal)
ok "演示数据就绪(1 用户 / 1 agent / 3 个空知识库;seed 幂等)"

# S3 的演示知识(语义层 + 7 个已验证意图 + 索引面)。要现算 embedding,所以要 key;
# 没 key 时跳过而不是失败 —— 其余功能不依赖它
if grep -q '^OPENAI_API_KEY=sk-你的key' .env; then
	warn "OPENAI_API_KEY 没填,跳过 S3 演示知识(问数会没有可命中的意图)。填好后跑:make seed-s3"
else
	(cd server && uv run python -m scripts.seed_s3_demo >/dev/null)
	ok "S3 演示知识就绪(7 个已验证意图 + 75 条索引面;含空路由负例面)"
fi

# ===== 7. MinerU(可选)=====

if [[ $WITH_MINERU -eq 1 ]]; then
	step "起 MinerU PDF 解析容器(首次要 build 镜像 + 下 1GB 权重,慢)"
	docker compose up -d mineru-api
	info "等 MinerU 就绪(首次含模型下载,最多等 15 分钟)..."
	for _ in $(seq 1 300); do
		if [[ "$(docker inspect agent_system_mineru --format '{{.State.Health.Status}}' 2>/dev/null)" == healthy ]]; then
			MINERU_READY=1; break
		fi
		sleep 3
	done
	if [[ "${MINERU_READY:-0}" -eq 1 ]]; then
		ok "MinerU 就绪(http://127.0.0.1:18001),PDF 上传解析可用"
	else
		warn "MinerU 没在时限内就绪。看日志:docker compose logs -f mineru-api;之后可单独 make mineru"
	fi
else
	info "跳过 MinerU(S1 上传 PDF 才需要)。要装:./bootstrap.sh --with-mineru 或 make mineru"
fi

# ===== 8. 自检 =====

step "自检:离线测试 + lint + 业务库数据断言"

(cd server && uv run pytest -q)
ok "后端离线测试通过(不联网、不连库)"
(cd server && uv run ruff check app scripts tests)
(cd web && npm run lint --silent && npx tsc -b)
ok "lint + TS 编译通过(契约链路的守门人)"
# 演示数据是生成的,形状不对时症状会伪装成"AI 算错了" —— 所以装机就断言一遍
(cd server && uv run python -m scripts.verify_bizdb >/dev/null)
ok "业务库 27 项数据断言全过(含只读账号写入被拒)"

# ===== 9. 冒烟(真花钱)=====

step "冒烟:真实调 LLM 与 Embedding(验证 key / 网络 / 代理)"

if [[ $SKIP_SMOKE -eq 1 ]]; then
	info "--skip-smoke:跳过。之后想验 key:make smoke"
elif grep -q '^OPENAI_API_KEY=sk-你的key' .env; then
	warn "OPENAI_API_KEY 没填,跳过冒烟。填好后跑:make smoke"
else
	(cd server && uv run python -m scripts.smoke_llm)
	(cd server && uv run python -m scripts.smoke_embedding)
	ok "LLM 与 Embedding 都通"
fi

# ===== 收尾 =====

printf '\n%s=== 装完了 ===%s\n' "$C_OK" "$C_RESET"
if [[ $WARN_COUNT -gt 0 ]]; then
	printf '\n%s需要你手动收尾的 %d 处:%s\n' "$C_WARN" "$WARN_COUNT" "$C_RESET"
	while IFS= read -r w; do printf '  %s⚠%s  %s\n' "$C_WARN" "$C_RESET" "$w"; done < "$WARN_LOG"
fi
cat <<'EOF'

下一步:
  make dev        起前后端 -> 前端 http://localhost:5173  后端 http://localhost:8000/docs
  make help       看全部命令
  make mineru     起 PDF 解析容器(上传 PDF 走 S1 抽取流水线要它)
  make mysql      进演示业务库看数据(问数演示的那七张表)

读什么:
  README.md                       环境要求 / 命令表 / 界面能点什么
  documents/PRD.md                需求与架构
  documents/DOMAIN-DEV-GUIDE.md   动手写代码前必读:落点与并行开发纪律
  architect.md                    "我要改 X 该去哪个目录"
EOF
printf '\n'

exit 0
