#!/usr/bin/env bash
# 把代码送上那台机器并跑完全流程(本地跑,读 deploy.env + stack.env)。
# 分阶段,可单独重跑:
#   ./remote_deploy.sh code       git HEAD 打包上传 + .env + deploy.env
#   ./remote_deploy.sh provision  服务器装机(Docker / Node / uv / Caddy / swap)
#   ./remote_deploy.sh bootstrap  ./bootstrap.sh -y --with-mineru(慢,MinerU 要 build + 下 1GB 权重)
#   ./remote_deploy.sh seed       make seed-s3(问数的演示知识与向量)
#   ./remote_deploy.sh migrate    make migrate(只跑 Alembic 迁移)
#   ./remote_deploy.sh release    迁移 + 构建前端 + systemd + Caddy + 自检
#   ./remote_deploy.sh all        以上全部,按顺序
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
REPO_LOCAL="$(cd .. && pwd)"

say() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
inf() { printf '  · %s\n' "$1"; }
die() { printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

[[ -f deploy.env ]] || die "缺 deploy.env"
[[ -f stack.env  ]] || die "缺 stack.env —— 先跑 ./aws_up.sh"
# shellcheck disable=SC1091
set -a; source ./deploy.env; source ./stack.env; set +a

REPO_ROOT="${REPO_ROOT:-/home/ubuntu/agent-system}"
KNOWN_HOSTS="$HERE/known_hosts"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$KNOWN_HOSTS" -o LogLevel=ERROR)
# 非交互 ssh 不读 ~/.bashrc(Ubuntu 的 .bashrc 对非交互 shell 直接 return),而 uv 装在
# ~/.local/bin —— 不显式补 PATH 的话服务器上 make 会报 "uv: command not found"。
rsh() { ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "export PATH=\$HOME/.local/bin:\$PATH; $*"; }

stage_code() {
	say "打包 git HEAD 并上传($(git -C "$REPO_LOCAL" rev-parse --short HEAD))"
	local tar=/tmp/knowledge-agent-src.tar.gz
	git -C "$REPO_LOCAL" archive --format=tar.gz -o "$tar" HEAD
	inf "$(du -h "$tar" | cut -f1)"
	rsh "mkdir -p $REPO_ROOT"
	scp "${SSH_OPTS[@]}" -q "$tar" "$SSH_TARGET:/tmp/src.tar.gz"
	rsh "tar -xzf /tmp/src.tar.gz -C $REPO_ROOT && rm /tmp/src.tar.gz && chmod +x $REPO_ROOT/bootstrap.sh"
	inf "解到 $REPO_ROOT"
	# deploy/ 已在 git 里,上面那包就带了它;这里再单独送一次是为了能**不提交也发布**
	# ——改部署脚本时改完就能试。排除本地 *.env 与 known_hosts:密码与 IP 不随包走。
	# 用 tar over ssh 而不是 rsync -e:仓库路径里有空格,拼 -e 字符串会被拆词。
	tar czf - --exclude '*.env' --exclude known_hosts -C "$HERE" . \
		| rsh "mkdir -p $REPO_ROOT/deploy && tar xzf - -C $REPO_ROOT/deploy"
	rsh "chmod +x $REPO_ROOT/deploy/*.sh"
	inf "deploy/ 已同步"
	# 少数文件可以用工作树版覆盖 HEAD 版:装机路径上的紧急修复不必等提交。
	# **显式清单,不是"所有改动过的文件"** —— 后者会把别人未完成的功能一起带上线。
	# 空清单 = 纯 git HEAD 部署,这是常态(那两个装机修复已经提交,不再需要覆盖)。
	WORKTREE_OVERRIDES=()   # 例:(bootstrap.sh docker/mineru/Dockerfile)
	for f in ${WORKTREE_OVERRIDES[@]+"${WORKTREE_OVERRIDES[@]}"}; do
		rsh "mkdir -p $REPO_ROOT/$(dirname "$f")"
		scp "${SSH_OPTS[@]}" -q "$REPO_LOCAL/$f" "$SSH_TARGET:$REPO_ROOT/$f"
		inf "覆盖 $f(工作树版)"
	done
	rsh "chmod +x $REPO_ROOT/bootstrap.sh"

	say "送应用配置 .env"
	# SECRET_KEY 必须跨重发**稳定**:datasources.dsn_enc 是用它加密的,换了 key 就解不开
	# 连接串,问数直接报 datasource_dsn_undecryptable(实测踩过)。所以服务器上已有的那把留着,
	# 只有第一次(服务器还没有 .env)才生成。
	EXISTING_SECRET="$(rsh "grep -h '^SECRET_KEY=' $REPO_ROOT/.env 2>/dev/null | cut -d= -f2-" || true)"
	if [[ -n "$EXISTING_SECRET" ]]; then
		inf "沿用服务器上已有的 SECRET_KEY(不动它,否则已加密的数据源连接串会失效)"
	fi

	# 从本地 .env 出发(key 与阈值都已调好),只换掉线上不同的几项
	EXISTING_SECRET="$EXISTING_SECRET" python3 - "$REPO_LOCAL/.env" "${OPENAI_API_KEY:-}" > /tmp/server.env <<'PY'
import os, sys, secrets, base64
src, key_override = sys.argv[1], sys.argv[2]
existing = os.environ.get("EXISTING_SECRET", "").strip()
lines = open(src).read().splitlines()
out = []
for ln in lines:
    if ln.startswith("APP_ENV="):
        ln = "APP_ENV=prod"
    elif key_override and ln.startswith("OPENAI_API_KEY="):
        ln = f"OPENAI_API_KEY={key_override}"
    elif ln.startswith("SECRET_KEY="):
        # 服务器自己的 Fernet key(本地那把不必外传;线上是全新 seed,不需要解本地密文)。
        # 已经有一把就沿用 —— 换 key = 线上所有 dsn_enc 报废。
        ln = "SECRET_KEY=" + (existing or base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    out.append(ln)
print("\n".join(out))
PY
	scp "${SSH_OPTS[@]}" -q /tmp/server.env "$SSH_TARGET:$REPO_ROOT/.env"
	rm -f /tmp/server.env
	inf "已写 $REPO_ROOT/.env(APP_ENV=prod,SECRET_KEY 服务器独立生成)"

	say "送部署配置 deploy/deploy.env"
	python3 - > /tmp/remote-deploy.env <<PY
print("""# remote_deploy.sh 生成,服务器侧 release.sh 读它
SITE_ADDRESS=$SITE_ADDRESS
BASIC_AUTH_USER=${BASIC_AUTH_USER:-interviewer}
BASIC_AUTH_PASSWORD=${BASIC_AUTH_PASSWORD:-}
REPO_ROOT=$REPO_ROOT
RUN_USER=${RUN_USER:-ubuntu}
API_PORT=${API_PORT:-8000}""")
PY
	scp "${SSH_OPTS[@]}" -q /tmp/remote-deploy.env "$SSH_TARGET:$REPO_ROOT/deploy/deploy.env"
	rm -f /tmp/remote-deploy.env
	inf "SITE_ADDRESS=$SITE_ADDRESS,密码门:$([[ -n "${BASIC_AUTH_PASSWORD:-}" ]] && echo 开 || echo 关)"
}

stage_provision() { say "服务器装机";  rsh "cd $REPO_ROOT/deploy && ./provision.sh"; }
stage_bootstrap() {
	say "bootstrap(依赖 / 两个库 / 迁移 / seed / 冒烟$([[ "${WITH_MINERU:-true}" == "true" ]] && echo " / MinerU"))"
	local flags="-y"
	[[ "${WITH_MINERU:-true}" == "true" ]] && flags="$flags --with-mineru"
	rsh "cd $REPO_ROOT && ./bootstrap.sh $flags"
}
stage_seed()     { say "灌问数演示知识(make seed-s3)"; rsh "cd $REPO_ROOT && make seed-s3"; }
stage_migrate()  { say "跑迁移(make migrate)"; rsh "cd $REPO_ROOT && make migrate"; }
# 迁移必须在 release 之前:release.sh 会重启后端,新代码起来时 schema 得已经是新的。
# (踩过:只跑 code+release 发了 S2 的代码,库还停在 S3 版本,列表接口 503 column chunks.status does not exist)
stage_release()  { stage_migrate; say "发布"; rsh "cd $REPO_ROOT/deploy && ./release.sh"; }

case "${1:-all}" in
	code)      stage_code ;;
	provision) stage_provision ;;
	bootstrap) stage_bootstrap ;;
	seed)      stage_seed ;;
	migrate)   stage_migrate ;;
	release)   stage_release ;;
	all)       stage_code; stage_provision; stage_bootstrap; stage_seed; stage_release ;;
	*)         die "不认识的阶段:$1(code|provision|bootstrap|seed|migrate|release|all)" ;;
esac

say "完成"
echo "站点:https://$SITE_ADDRESS"
