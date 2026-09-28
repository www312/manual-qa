#!/bin/bash
# manual-qa 一键部署脚本（Ubuntu 24.04 / 腾讯云轻量 2核4G）
# 用法: bash deploy.sh 43.142.30.173
# 前提: SSH 可达 + root 密码；脚本在服务器上执行

set -e

SERVER_IP=${1:?用法: bash deploy.sh <服务器IP>}
APP_DIR=/opt/manual-qa

echo "=== [1/5] 服务器基础环境 ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg ufw fail2ban > /dev/null

# Docker 官方源安装
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null
systemctl enable --now docker
echo "docker: $(docker --version)"

echo "=== [2/5] 防火墙与安全 ==="
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw --force enable
# fail2ban 防 SSH 爆破（默认 sshd jail）
systemctl enable --now fail2ban

echo "=== [3/5] 拉取项目 ==="
mkdir -p $APP_DIR && cd $APP_DIR
if [ ! -d .git ]; then
  # GitHub 直连不稳时走 ghproxy
  git clone https://github.com/www312/manual-qa.git . 2>/dev/null || \
  git clone https://ghproxy.net/https://github.com/www312/manual-qa.git .
fi

echo "=== [4/5] 交换分区（4G 内存兜底）==="
if ! swapon --show | grep -q swap; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo 'vm.swappiness=20' >> /etc/sysctl.conf && sysctl -p > /dev/null
fi

echo "=== [5/5] 数据传输提示 ==="
echo "代码就绪。下一步（由部署端执行）:"
echo "  1. scp 上传 data/chunks_selected.jsonl + data/qdrant/ (约2G) + .env"
echo "  2. cd $APP_DIR && docker compose up -d --build"
echo "  3. 首次入库: QDRANT_URL=http://localhost:6333 uv run python -m manual_qa.index"
echo ""
echo "基础环境完成: $(uname -r) | RAM: $(free -h | awk '/Mem/{print $2}') | Docker OK"
