#!/usr/bin/env bash
# 发布一次(在服务器上跑):构建前端 → 落静态目录 → 渲染并装 systemd 单元与 Caddy 配置
# → 起/重启后端与 Caddy → 健康自检。改完代码重传后再跑一次即可。幂等。
#
# 前置:./provision.sh 跑过、仓库根 ./bootstrap.sh 跑过(.env 与两个库就绪)、deploy.env 填好。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

say()  { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
die()  { printf '\n\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

[[ -f deploy.env ]] || die "缺 deploy.env。先 cp deploy.env.example deploy.env 并填好。"
# shellcheck disable=SC1091
set -a; source ./deploy.env; set +a

: "${SITE_ADDRESS:?deploy.env 缺 SITE_ADDRESS}"
: "${REPO_ROOT:?deploy.env 缺 REPO_ROOT}"
: "${RUN_USER:?deploy.env 缺 RUN_USER}"
API_PORT="${API_PORT:-8000}"
BASIC_AUTH_USER="${BASIC_AUTH_USER:-interviewer}"
BASIC_AUTH_PASSWORD="${BASIC_AUTH_PASSWORD:-}"
WEB_ROOT=/srv/knowledge-agent/web

[[ -f "$REPO_ROOT/.env" ]] || die "$REPO_ROOT/.env 不存在 —— 先在仓库根跑 ./bootstrap.sh"

# ===== 1. 应用配置的线上取向 =====
say "校对仓库根 .env 的线上取向"
ensure_env() {  # ensure_env KEY VALUE —— 有则改,无则加
	local key="$1" val="$2" f="$REPO_ROOT/.env"
	if grep -q "^${key}=" "$f"; then
		sed "s|^${key}=.*|${key}=${val}|" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
	else
		printf '%s=%s\n' "$key" "$val" >> "$f"
	fi
	echo "  · ${key}=${val}"
}
ensure_env APP_ENV prod
# 同源部署,CORS 白名单其实用不上;仍写成站点地址,免得日后有人从别处调它
case "$SITE_ADDRESS" in
	:*) ensure_env CORS_ORIGINS "http://${SITE_ADDRESS#:}" ;;
	*)  ensure_env CORS_ORIGINS "https://${SITE_ADDRESS}" ;;
esac

# ===== 2. 前端构建 =====
say "构建前端(tsc + vite build)"
(cd "$REPO_ROOT/web" && npm ci --no-audit --fund=false && npm run build)
[[ -f "$REPO_ROOT/web/dist/index.html" ]] || die "构建产物里没有 index.html"

say "同步静态产物到 $WEB_ROOT"
sudo mkdir -p "$WEB_ROOT"
sudo rsync -a --delete "$REPO_ROOT/web/dist/" "$WEB_ROOT/"
sudo chown -R caddy:caddy /srv/knowledge-agent
sudo chmod -R a+rX /srv/knowledge-agent

# ===== 3. 渲染模板 =====
# 用 python 而不是 sed 做替换:bcrypt hash 里有 $ / . 等元字符,字面替换更省心
AUTH_BLOCK=""
if [[ -n "$BASIC_AUTH_PASSWORD" ]]; then
	say "生成 Basic Auth hash(密码门开)"
	HASH="$(caddy hash-password --plaintext "$BASIC_AUTH_PASSWORD")"
	AUTH_BLOCK="$(python3 - "$HASH" <<'PY'
import sys
snippet = open('Caddyfile.auth.snippet').read().rstrip('\n')
print(snippet.replace('__BASIC_AUTH_HASH__', sys.argv[1]))
PY
)"
	AUTH_BLOCK="${AUTH_BLOCK//__BASIC_AUTH_USER__/$BASIC_AUTH_USER}"
else
	say "不开密码门(deploy.env 的 BASIC_AUTH_PASSWORD 为空)"
	echo "  · 站点按主机名匹配:直接扫公网 IP 的请求拿不到页面。主机名不可猜是这一层的全部依仗。"
fi

render() {  # render <模板文件>
	AUTH_BLOCK="$AUTH_BLOCK" SITE_ADDRESS="$SITE_ADDRESS" API_PORT="$API_PORT" \
	WEB_ROOT="$WEB_ROOT" REPO_ROOT="$REPO_ROOT" RUN_USER="$RUN_USER" \
	python3 -c '
import os, sys
text = open(sys.argv[1]).read()
for key in ("AUTH_BLOCK", "SITE_ADDRESS", "API_PORT", "WEB_ROOT", "REPO_ROOT", "RUN_USER"):
    text = text.replace(f"__{key}__", os.environ.get(key, ""))
sys.stdout.write(text)
' "$1"
}

say "装 systemd 单元 knowledge-agent-api"
render knowledge-agent-api.service.tmpl | sudo tee /etc/systemd/system/knowledge-agent-api.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable knowledge-agent-api >/dev/null
sudo systemctl restart knowledge-agent-api

say "装 Caddy 配置"
render Caddyfile.tmpl | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo caddy validate --config /etc/caddy/Caddyfile >/dev/null || die "Caddyfile 校验不过,看上面的报错"
sudo systemctl enable caddy >/dev/null
sudo systemctl reload caddy 2>/dev/null || sudo systemctl restart caddy

# ===== 4. 自检 =====
say "自检"
for i in $(seq 1 30); do
	curl -fsS "http://127.0.0.1:${API_PORT}/healthz" >/dev/null 2>&1 && break
	[[ $i -eq 30 ]] && die "后端 30s 内没起来:journalctl -u knowledge-agent-api -n 50"
	sleep 1
done
echo "  · 后端 /healthz: $(curl -fsS "http://127.0.0.1:${API_PORT}/healthz")"

SCHEME=https; HOST="$SITE_ADDRESS"
case "$SITE_ADDRESS" in :*) SCHEME=http; HOST="127.0.0.1${SITE_ADDRESS}" ;; esac
CODE="$(curl -s -o /dev/null -w '%{http_code}' "${SCHEME}://${HOST}/" || true)"
if [[ -n "$BASIC_AUTH_PASSWORD" ]]; then
	[[ "$CODE" == "401" ]] && echo "  · 无凭据访问返回 401(密码门生效)" \
		|| echo "  ⚠ 无凭据访问返回 $CODE(期望 401;证书刚签时可能是别的码,过一分钟再看)"
	CODE_AUTH="$(curl -s -o /dev/null -w '%{http_code}' -u "${BASIC_AUTH_USER}:${BASIC_AUTH_PASSWORD}" "${SCHEME}://${HOST}/" || true)"
	echo "  · 带凭据访问首页返回 $CODE_AUTH(期望 200)"
else
	[[ "$CODE" == "200" ]] && echo "  · 首页返回 200" \
		|| echo "  ⚠ 首页返回 $CODE(证书刚签时可能要等一分钟)"
fi

# 演示业务库是问数的查询目标,它没起来问数就全废
docker ps --format '{{.Names}}' | grep -q agent_system_pg     && echo "  · 系统库容器在跑"     || echo "  ⚠ agent_system_pg 没在跑:make db"
docker ps --format '{{.Names}}' | grep -q agent_system_bizdb  && echo "  · 演示业务库容器在跑" || echo "  ⚠ agent_system_bizdb 没在跑:make bizdb"
docker ps --format '{{.Names}}' | grep -q agent_system_mineru && echo "  · MinerU 解析容器在跑" || echo "  ⚠ MinerU 没在跑(不影响问答,只影响上传新 PDF):make mineru"

say "发布完成"
case "$SITE_ADDRESS" in
	:*) echo "打开 http://<公网IP>${SITE_ADDRESS}" ;;
	*)  echo "打开 https://${SITE_ADDRESS}" ;;
esac
[[ -n "$BASIC_AUTH_PASSWORD" ]] && echo "用户名 ${BASIC_AUTH_USER},密码见 deploy.env"
