// 引擎（sidecar）连接状态的 Pinia store。
import { defineStore } from "pinia";
import { getHealth, type Health } from "../api";

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
  },
});
