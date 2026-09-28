#!/bin/bash
# manual-qa 一键部署脚本 v2（Ubuntu / 腾讯云轻量）
# 修正: Docker 走腾讯云镜像源（官方源在服务器侧被墙）

set -e

SERVER_IP=${1:?用法: bash deploy.sh <服务器IP>}
APP_DIR=/opt/manual-qa

echo "=== [1/5] 基础环境 ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg ufw fail2ban git > /dev/null

# Docker: 腾讯云镜像
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.cloud.tencent.com/docker-ce/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null
systemctl enable --now docker
# Docker Hub 拉取走腾讯镜像加速
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{"registry-mirrors": ["https://mirror.ccs.tencentyun.com"]}
EOF
systemctl restart docker
docker pull hello-world > /dev/null 2>&1 && echo "docker pull 测试: OK" || echo "警告: 镜像拉取失败(稍后排查)"

echo "=== [2/5] 防火墙与安全 ==="
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw --force enable
systemctl enable --now fail2ban

echo "=== [3/5] 拉取项目 ==="
mkdir -p $APP_DIR && cd $APP_DIR
if [ ! -d .git ]; then
  git clone https://ghproxy.net/https://github.com/www312/manual-qa.git . || \
  git clone https://github.com/www312/manual-qa.git .
fi

echo "=== [4/5] 交换分区 ==="
if ! swapon --show | grep -q swap; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=20 > /dev/null
  echo 'vm.swappiness=20' >> /etc/sysctl.conf
fi

echo "=== [5/5] 完成 ==="
echo "环境: $(uname -r) | RAM $(free -h | awk '/Mem/{print $2}') | Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"
echo "git repo: $(cd $APP_DIR && git log --oneline | head -1)"
echo "下一步: scp 数据 + docker compose up"
