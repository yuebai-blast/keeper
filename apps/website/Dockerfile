# Keeper 官网镜像：多阶段构建，版本统一由 mise 管。
#   stage build  —— 装 mise，按仓库根 mise.toml 的 [tools] 装钉死的 node/pnpm，编译出 dist
#   stage runtime —— 用 nginx 托管静态产物，容器内只听 80（明文 HTTP）
# TLS 由你服务器上的反向代理 / Cloudflare 终止，容器本身不处理证书。
#
# 构建上下文必须是仓库根（让 mise.toml 进上下文，镜像构建自包含、无需外部传版本号）：
#   docker build -f apps/website/Dockerfile .   ← 见 `mise run site-image` 与 CI
# 故下面所有 COPY 路径都是根相对（apps/website/...）。

# ---- 构建阶段：用 mise 按 mise.toml [tools] 装钉死的 node/pnpm ----
FROM debian:13-slim AS build

# mise 自身版本在此钉死（自举工具无法由 mise.toml 管，这是唯一的例外）
ENV MISE_VERSION=v2026.6.0
ENV MISE_DATA_DIR=/mise \
    MISE_CONFIG_DIR=/mise \
    MISE_CACHE_DIR=/mise/cache \
    MISE_INSTALL_PATH=/usr/local/bin/mise \
    PATH=/mise/shims:$PATH
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl https://mise.run | sh

WORKDIR /app

# 先拷版本锁，只装 node/pnpm（不碰 rust/uv/python），吃 Docker 层缓存：
# mise.toml 不变就不重装运行时
COPY mise.toml ./
RUN mise trust && mise install node pnpm

# 再单独拷依赖清单装依赖：源码改动不重装 node_modules
COPY apps/website/package.json apps/website/pnpm-lock.yaml ./apps/website/
WORKDIR /app/apps/website
RUN pnpm install --frozen-lockfile

# 最后拷源码并构建
COPY apps/website/ ./
RUN pnpm build

# ---- 运行阶段 ----
# 多阶段隔离：build 阶段的 debian + mise + node 都不进最终镜像，
# 最终镜像只是 nginx + 静态产物
FROM nginx:1.27-alpine AS runtime

# 站点配置：gzip + 静态资源长缓存 + index.html 不缓存 + 单页回退
COPY apps/website/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/website/dist /usr/share/nginx/html

EXPOSE 80
