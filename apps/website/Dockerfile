# Keeper 官网镜像：多阶段构建。
#   stage build  —— 用钉死版本的 node + pnpm 把官网编译成静态产物（dist）
#   stage runtime —— 用 nginx 托管静态产物，容器内只听 80（明文 HTTP）
# TLS 由你服务器上的反向代理 / Cloudflare 终止，容器本身不处理证书。

# ---- 构建阶段 ----
FROM node:24.16.0-alpine AS build
WORKDIR /app

# pnpm 版本与 mise.toml 的 [tools] 保持一致，保证与本地/CI 构建可复现
RUN corepack enable && corepack prepare pnpm@10.11.0 --activate

# 先单独拷依赖清单，利用 Docker 层缓存：源码改动不重装依赖
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# ---- 运行阶段 ----
FROM nginx:1.27-alpine AS runtime

# 站点配置：gzip + 静态资源长缓存 + index.html 不缓存 + 单页回退
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
