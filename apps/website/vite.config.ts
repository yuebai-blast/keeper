// 从 vitest/config 导入 defineConfig：它在 vite 配置类型上扩展了 test 字段（vite 自带的不认识 test）。
// 前提是 vitest 与项目 vite 同主版本（均 vite6）——故 vitest 锁 ^4，避免旧版自带 vite5 类型与 vue() 插件打架。
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";

// 官网为纯静态站；vitest 用 node 环境跑纯逻辑测试（无需 DOM，不依赖 jsdom）
export default defineConfig({
    plugins: [vue()],
    // dev 下把同源端点 /api/gh/releases 转发到 GitHub releases 列表，
    // 与 prod 的 nginx 反代对齐（前端代码统一打这一个同源端点）。本地直连、不带缓存，限流无所谓。
    server: {
        proxy: {
            "/api/gh/releases": {
                target: "https://api.github.com",
                changeOrigin: true,
                headers: {
                    // GitHub API 强制要求 UA，缺了会 403
                    "User-Agent": "keeper-website",
                    Accept: "application/vnd.github+json",
                },
                // per_page=10 与 prod nginx 对齐：收窄响应体，且留足窗口避免最新 desktop-v* 被 website 版挤出
                rewrite: () => "/repos/yuebai-blast/keeper/releases?per_page=10",
            },
        },
    },
    test: {
        environment: "node",
        include: ["src/**/*.test.ts"],
    },
});
