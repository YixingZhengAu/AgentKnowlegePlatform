#!/usr/bin/env bash
# 服务器一次性装机(Ubuntu 24.04,arm64 或 amd64 都行)。
# 只装系统级依赖:Docker + compose、Node 22、uv、Caddy。装完再跑 bootstrap.sh 与 release.sh。
# 幂等:重复跑安全。
#
# 用法(在服务器上):cd <仓库>/deploy && ./provision.sh
set -euo pipefail

say() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }

[[ "$(id -u)" -eq 0 ]] && { echo "别用 root 跑,用普通用户(脚本内部自己 sudo)"; exit 1; }
command -v apt-get >/dev/null || { echo "这个脚本只针对 Debian/Ubuntu"; exit 1; }

say "更新 apt 索引"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg rsync git make openssl debian-keyring debian-archive-keyring apt-transport-https

if ! command -v docker >/dev/null; then
	say "装 Docker Engine + compose 插件(官方仓库)"
	sudo install -m 0755 -d /etc/apt/keyrings
	curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
	sudo chmod a+r /etc/apt/keyrings/docker.gpg
	echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
		| sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
	sudo apt-get update -y
	sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
	sudo usermod -aG docker "$USER"
	echo "已把 $USER 加进 docker 组 —— 本次会话还没生效,装机结束后重新登录一次(exit 再 ssh)"
else
	say "Docker 已在:$(docker --version)"
fi

if ! command -v node >/dev/null || [[ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)" -lt 22 ]]; then
	say "装 Node 22(NodeSource)"
	curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
	sudo apt-get install -y nodejs
else
	say "Node 已在:$(node -v)"
fi

if ! command -v uv >/dev/null && [[ ! -x "$HOME/.local/bin/uv" ]]; then
	say "装 uv(Python 依赖只用它;Python 3.13 由它自动拉)"
	curl -LsSf https://astral.sh/uv/install.sh | sh
else
	say "uv 已在"
fi

if ! command -v caddy >/dev/null; then
	say "装 Caddy(官方仓库;自动 HTTPS 靠它)"
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
	sudo apt-get update -y
	sudo apt-get install -y caddy
else
	say "Caddy 已在:$(caddy version)"
fi

# 2 vCPU / 8GB 的机器上 MinerU 解析会吃内存,加一块 swap 兜底(有就跳过)
if ! sudo swapon --show | grep -q /swapfile; then
	say "建 2G swap(MinerU 解析的内存尖峰兜底)"
	sudo fallocate -l 2G /swapfile
	sudo chmod 600 /swapfile
	sudo mkswap /swapfile >/dev/null
	sudo swapon /swapfile
	echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

say "装机完成"
cat <<'EOT'
下一步:
  1) 如果刚才把用户加进了 docker 组 —— 先 exit 重新 ssh 一次
  2) cd <仓库> && ./bootstrap.sh --with-mineru     # .env、依赖、两个库、迁移、seed、冒烟
  3) cd deploy && cp deploy.env.example deploy.env && vi deploy.env
  4) ./release.sh                                  # 构建前端 + 装 systemd + 配 Caddy + 起服务
EOT
