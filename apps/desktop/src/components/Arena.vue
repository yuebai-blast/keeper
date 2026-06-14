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
    <div class="bar">
      <span class="title">A/B 擂台</span>
      <span class="sep" />
      <span v-if="!done" class="round">第 {{ history.length + 1 }} / {{ totalRounds }} 轮</span>
      <span v-else class="round done">本组终选</span>
      <span class="grow" />
      <button class="btn btn--ghost" @click="emit('close')">退出 <kbd>Esc</kbd></button>
    </div>

    <!-- 对决中 -->
    <template v-if="!done && champion && challenger">
      <div class="duel">
        <figure class="card" @click="pick(true)">
          <span class="badge">擂主</span>
          <img :src="thumbnailUrl(champion, 1024)" alt="" />
          <figcaption>留左 <kbd>←</kbd></figcaption>
        </figure>
        <div class="vs"><span>VS</span></div>
        <figure class="card" @click="pick(false)">
          <span class="badge">挑战者</span>
          <img :src="thumbnailUrl(challenger, 1024)" alt="" />
          <figcaption>留右 <kbd>→</kbd></figcaption>
        </figure>
      </div>
      <footer>
        <button class="btn" :disabled="!history.length" @click="undo">撤销 <kbd>U</kbd></button>
        <span class="grow" />
        <button class="btn btn--danger" @click="discardGroup">整组舍弃</button>
      </footer>
    </template>

    <!-- 选出胜者 -->
    <template v-else-if="done && champion">
      <div class="result">
        <figure>
          <img :src="thumbnailUrl(champion, 1024)" alt="" />
          <figcaption>本组胜出 · {{ basename(champion) }}</figcaption>
        </figure>
      </div>
      <footer>
        <button class="btn" :disabled="!history.length" @click="undo">撤销 <kbd>U</kbd></button>
        <span class="tally">已淘汰 {{ losers.length }} 张</span>
        <span class="grow" />
        <button class="btn btn--danger" @click="discardGroup">整组舍弃</button>
        <button class="btn btn--keep" @click="keepWinner">留下这张 <kbd>↵</kbd></button>
      </footer>
    </template>
  </div>
</template>

<style scoped>
.arena {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: radial-gradient(120% 90% at 50% 0%, rgba(28, 21, 12, 0.98), rgba(8, 6, 4, 0.99));
  display: flex;
  flex-direction: column;
  padding: 20px 24px 24px;
  gap: 18px;
}

.bar { display: flex; align-items: center; gap: 12px; }
.bar .title {
  font-family: var(--font-display);
  font-size: 16px;
  letter-spacing: 0.02em;
}
.bar .sep { width: 1px; height: 16px; background: var(--line-strong); }
.round { font-family: var(--font-mono); font-size: 12.5px; color: var(--amber); letter-spacing: 0.05em; }
.round.done { color: var(--green); }
.grow { flex: 1; }

.duel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
  min-height: 0;
}
.card {
  margin: 0;
  position: relative;
  flex: 1;
  max-width: 46%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 12px;
  border: 2px solid var(--line);
  background: rgba(0, 0, 0, 0.25);
  transition: border-color 0.16s, transform 0.1s, box-shadow 0.2s;
  overflow: hidden;
}
.card:hover { border-color: var(--amber); box-shadow: 0 0 0 4px var(--amber-soft), var(--shadow); }
.card:active { transform: scale(0.992); }
.card img { max-width: 100%; max-height: 100%; object-fit: contain; display: block; }
.badge {
  position: absolute;
  top: 12px;
  left: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--amber-bright);
  background: rgba(0, 0, 0, 0.55);
  padding: 4px 10px;
  border-radius: 6px;
  backdrop-filter: blur(3px);
}
.card figcaption {
  position: absolute;
  bottom: 12px;
  font-size: 13px;
  color: var(--ink-dim);
  background: rgba(0, 0, 0, 0.5);
  padding: 5px 12px;
  border-radius: 7px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  backdrop-filter: blur(3px);
}

.vs {
  flex: none;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: 1px solid var(--line-strong);
  display: grid;
  place-items: center;
}
.vs span {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 17px;
  color: var(--amber);
}

.result {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
}
.result figure {
  margin: 0;
  position: relative;
  max-width: 72%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.result img {
  max-width: 100%;
  max-height: calc(100% - 36px);
  object-fit: contain;
  border-radius: 12px;
  border: 2px solid var(--green);
  box-shadow: 0 0 0 5px var(--green-soft), var(--shadow);
}
.result figcaption { margin-top: 14px; color: var(--green); font-weight: 500; font-size: 14px; }

footer { display: flex; align-items: center; gap: 12px; }
.tally { font-family: var(--font-mono); font-size: 12.5px; color: var(--ink-faint); }

kbd {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink);
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid var(--line-strong);
  border-radius: 5px;
  padding: 1px 6px;
  min-width: 18px;
  text-align: center;
}
.btn--keep kbd,
.btn--danger kbd { color: inherit; border-color: currentColor; opacity: 0.7; }
</style>
