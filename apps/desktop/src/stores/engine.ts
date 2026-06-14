// 引擎（sidecar）连接状态的 Pinia store。
import { defineStore } from "pinia";
import { getHealth, retryWarmup, type Health } from "../api";

interface EngineState {
  health: Health | null;
  // connecting: 正在连/重试；offline: 连不上（服务没起）
  phase: "connecting" | "online" | "offline";
  error: string;
}

export const useEngineStore = defineStore("engine", {
  state: (): EngineState => ({
    health: null,
    phase: "connecting",
    error: "",
  }),
  getters: {
    // 模型是否就绪可服务
    ready: (s): boolean => s.phase === "online" && s.health?.status === "ready",
    // 是否首次下载模型（首次需联网，就绪后由用户点按钮进入；非首次自动进入）
    firstRun: (s): boolean => s.health?.first_run === true,
    // 加载失败且可重试（下载失败等）；依赖缺失不可重试
    canRetry: (s): boolean => s.health?.status === "error" && s.health?.retryable === true,
  },
  actions: {
    async refresh() {
      try {
        this.health = await getHealth();
        this.phase = "online";
        this.error = "";
      } catch (e) {
        this.phase = "offline";
        this.health = null;
        this.error = e instanceof Error ? e.message : String(e);
      }
    },
    // 重新预热模型（下载失败重试）。立刻把本地状态切回 loading，再拉最新就绪态。
    async retry() {
      try {
        this.health = await retryWarmup();
        this.phase = "online";
        this.error = "";
      } catch (e) {
        this.phase = "offline";
        this.error = e instanceof Error ? e.message : String(e);
      }
    },
  },
});
