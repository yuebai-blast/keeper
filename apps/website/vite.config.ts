import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 官网为纯静态站；vitest 用 jsdom 环境跑组合式函数纯逻辑测试
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
