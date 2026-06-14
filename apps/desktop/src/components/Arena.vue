<script setup lang="ts">
// A/B 擂台：擂主守擂法。当前擂主 vs 下一张挑战者，用户选谁更好；
// N 张照片经 N-1 轮选出 1 张本组最佳。机器不替用户淘汰——留谁、是否整组舍弃都由用户定。
import { computed, onMounted, onUnmounted, ref } from "vue";
import { thumbnailUrl } from "../api";

const props = defineProps<{ candidates: string[] }>();
const emit = defineEmits<{ finish: [winner: string | null, losers: string[]]; close: [] }>();

const champion = ref<string | null>(props.candidates[0] ?? null);
const idx = ref(1); // 下一个挑战者下标
const losers = ref<string[]>([]);
const history = ref<{ champion: string; idx: number }[]>([]);

const challenger = computed(() => (idx.value < props.candidates.length ? props.candidates[idx.value] : null));
const done = computed(() => challenger.value === null);
const totalRounds = computed(() => Math.max(0, props.candidates.length - 1));
const basename = (p: string) => p.split(/[\\/]/).pop() ?? p;

function pick(championWins: boolean) {
  if (champion.value === null || challenger.value === null) return;
  history.value.push({ champion: champion.value, idx: idx.value });
  losers.value.push(championWins ? challenger.value : champion.value);
  if (!championWins) champion.value = challenger.value;
  idx.value += 1;
}
function undo() {
  const last = history.value.pop();
  if (!last) return;
  champion.value = last.champion;
  idx.value = last.idx;
  losers.value.pop();
}
function keepWinner() {
  emit("finish", champion.value, [...losers.value]);
}
function discardGroup() {
  emit("finish", null, [...props.candidates]);
}

function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") return emit("close");
  if (done.value) {
    if (e.key === "Enter") keepWinner();
    return;
  }
  if (e.key === "ArrowLeft") pick(true);
  else if (e.key === "ArrowRight") pick(false);
  else if (e.key === "u" || e.key === "U") undo();
}
onMounted(() => window.addEventListener("keydown", onKey));
onUnmounted(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <div class="arena">
    <!-- 对决中 -->
    <template v-if="!done && champion && challenger">
      <div class="duel">
        <figure class="side" @click="pick(true)">
          <img :src="thumbnailUrl(champion, 1024)" alt="" />
          <figcaption>擂主 · 留左 ←</figcaption>
        </figure>
        <div class="vs">VS</div>
        <figure class="side" @click="pick(false)">
          <img :src="thumbnailUrl(challenger, 1024)" alt="" />
          <figcaption>挑战者 · 留右 →</figcaption>
        </figure>
      </div>
      <footer>
        <span class="progress">第 {{ history.length + 1 }} / {{ totalRounds }} 轮</span>
        <span class="grow" />
        <button class="btn" :disabled="!history.length" @click="undo">撤销 (U)</button>
        <button class="btn danger" @click="discardGroup">整组舍弃</button>
        <button class="btn" @click="emit('close')">退出 (Esc)</button>
      </footer>
    </template>

    <!-- 选出胜者 -->
    <template v-else-if="done && champion">
      <div class="result">
        <img :src="thumbnailUrl(champion, 1024)" alt="" />
        <p class="cap">本组胜出 · {{ basename(champion) }}</p>
      </div>
      <footer>
        <span class="progress">淘汰 {{ losers.length }} 张</span>
        <span class="grow" />
        <button class="btn" :disabled="!history.length" @click="undo">撤销 (U)</button>
        <button class="btn danger" @click="discardGroup">整组舍弃</button>
        <button class="btn primary" @click="keepWinner">留下这张 (Enter)</button>
      </footer>
    </template>
  </div>
</template>

<style scoped>
.arena {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(8, 9, 12, 0.96);
  display: flex;
  flex-direction: column;
  padding: 24px;
  gap: 16px;
}
.duel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  min-height: 0;
}
.side {
  margin: 0;
  flex: 1;
  max-width: 46%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  border-radius: 12px;
  border: 2px solid transparent;
  transition: border-color 0.15s, transform 0.1s;
}
.side:hover { border-color: #6366f1; }
.side:active { transform: scale(0.99); }
.side img {
  max-width: 100%;
  max-height: calc(100% - 32px);
  object-fit: contain;
  border-radius: 8px;
}
.side figcaption { color: var(--muted); font-size: 14px; }
.vs { color: var(--muted); font-weight: 700; letter-spacing: 1px; }

.result {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 0;
}
.result img { max-width: 70%; max-height: calc(100% - 40px); object-fit: contain; border-radius: 10px; border: 2px solid #34d399; }
.result .cap { color: #34d399; font-weight: 600; }

footer { display: flex; align-items: center; gap: 10px; }
footer .grow { flex: 1; }
footer .progress { color: var(--muted); font-size: 14px; }
.btn {
  border: 1px solid var(--border);
  background: transparent;
  color: #eef0f5;
  border-radius: 8px;
  padding: 9px 16px;
  cursor: pointer;
  font: inherit;
  transition: border-color 0.2s, background 0.2s, opacity 0.2s;
}
.btn:hover:not(:disabled) { border-color: #6366f1; background: rgba(99, 102, 241, 0.12); }
.btn:disabled { opacity: 0.45; cursor: default; }
.btn.primary { background: #34d399; border-color: #34d399; color: #0b1f17; font-weight: 600; }
.btn.primary:hover { background: #2bbd86; }
.btn.danger:hover:not(:disabled) { border-color: #f87171; background: rgba(248, 113, 113, 0.12); }
</style>
