#!/usr/bin/env bash
# 把官网构建产物同步到服务器。凭据/目标走环境变量，绝不入库。
# 用法：export KEEPER_SITE_HOST=user@host KEEPER_SITE_PATH=/var/www/keeper-site
#       mise run site-deploy
set -euo pipefail

: "${KEEPER_SITE_HOST:?需要设置 KEEPER_SITE_HOST（如 user@host）}"
: "${KEEPER_SITE_PATH:?需要设置 KEEPER_SITE_PATH（如 /var/www/keeper-site）}"

DIST="apps/website/dist/"
[ -d "$DIST" ] || { echo "未找到 $DIST，请先 mise run site-build"; exit 1; }

echo "→ rsync $DIST → $KEEPER_SITE_HOST:$KEEPER_SITE_PATH"
rsync -avz --delete "$DIST" "$KEEPER_SITE_HOST:$KEEPER_SITE_PATH/"
echo "✓ 部署完成"
