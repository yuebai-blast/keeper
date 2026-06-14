<script setup lang="ts">
import { computed, onMounted, onUnmounted } from "vue";
import { useEngineStore } from "./stores/engine";

const engine = useEngineStore();
let timer: number | undefined;

// 终态：就绪或加载失败后不再轮询；其余（连不上/加载中）持续重试
const settled = computed(
  () => engine.phase === "online" && (engine.health?.status === "ready" || engine.health?.status === "error"),
);

function stopPoll() {
  if (timer) window.clearInterval(timer);
  timer = undefined;
}
function startPoll() {
  stopPoll();
  timer = window.setInterval(async () => {
    if (settled.value) return stopPoll();
    await engine.refresh();
  }, 1800);
}
async function reconnect() {
  await engine.refresh();
  if (!settled.value) startPoll();
}

const dot = computed(() => {
  if (engine.phase === "offline") return "offline";
  if (engine.health?.status === "ready") return "ready";
  if (engine.health?.status === "error") return "error";
  return "loading";
});
const label = computed(() => {
  if (engine.phase === "connecting") return "正在连接推理服务…";
  if (engine.phase === "offline") return "连不上推理服务";
  if (engine.health?.status === "ready") return "推理服务就绪";
  if (engine.health?.status === "error") return "模型加载失败";
  return "模型加载中…";
});

onMounted(async () => {
  await engine.refresh();
  startPoll();
});
onUnmounted(stopPoll);
</script>

<template>
  <main class="app">
    <header class="brand">
      <h1>Keeper <span>· 留影</span></h1>
      <p class="tagline">把最好的留下，留在你自己的电脑里</p>
    </header>

    <section class="card">
      <div class="status">
        <span class="indicator" :class="dot" />
        <div class="status-text">
          <strong>{{ label }}</strong>
          <small v-if="engine.health">引擎 v{{ engine.health.version }}</small>
        </div>
        <button class="btn" :disabled="engine.phase === 'connecting'" @click="reconnect">重连</button>
      </div>

      <p v-if="engine.phase === 'offline'" class="hint">
        请先在另一个终端启动推理服务：<code>mise run sidecar</code>
      </p>
      <p v-else-if="engine.health?.status === 'loading'" class="hint">
        首次启动正在下载/载入本地模型，稍候片刻…
      </p>
      <p v-else-if="engine.health?.status === 'error'" class="hint err">
        {{ engine.health.detail }}
      </p>
      <p v-else-if="engine.ready" class="hint ok">
        分组 / 本地评分 / 大模型打分 已就绪。
      </p>
    </section>

    <footer class="next">
      下一步：导入照片目录 → 分组 → 评分 → A/B 擂台终选（开发中）
    </footer>
  </main>
</template>

<style scoped>
.app {
  max-width: 640px;
  margin: 0 auto;
  padding: 14vh 24px 0;
  display: flex;
  flex-direction: column;
  gap: 28px;
}
.brand h1 {
  margin: 0;
  font-size: 34px;
  letter-spacing: 0.5px;
}
.brand h1 span {
  color: var(--muted);
  font-weight: 400;
}
.tagline {
  margin: 8px 0 0;
  color: var(--muted);
}
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px;
}
.status {
  display: flex;
  align-items: center;
  gap: 14px;
}
.indicator {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  flex: none;
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.04);
}
.indicator.ready { background: #34d399; }
.indicator.loading { background: #fbbf24; animation: pulse 1.2s infinite; }
.indicator.error { background: #f87171; }
.indicator.offline { background: #6b7280; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
.status-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.status-text small { color: var(--muted); }
.btn {
  border: 1px solid var(--border);
  background: transparent;
  color: inherit;
  border-radius: 8px;
  padding: 7px 14px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.btn:hover:not(:disabled) { border-color: #6366f1; background: rgba(99, 102, 241, 0.1); }
.btn:disabled { opacity: 0.5; cursor: default; }
.hint {
  margin: 16px 0 0;
  color: var(--muted);
  font-size: 14px;
}
.hint.ok { color: #34d399; }
.hint.err { color: #f87171; }
.hint code {
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 7px;
  border-radius: 5px;
}
.next {
  color: var(--muted);
  font-size: 13px;
}
</style>

<style>
:root {
  --bg: #14151a;
  --card: #1c1e26;
  --border: #2a2d38;
  --muted: #8b90a0;
  font-family: Inter, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #eef0f5;
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; }
code { font-family: "SFMono-Regular", Menlo, monospace; }
</style>
