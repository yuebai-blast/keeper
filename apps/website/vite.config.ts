import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 官网为纯静态站；vitest 用 node 环境跑纯逻辑测试（无需 DOM，不依赖 jsdom）
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
