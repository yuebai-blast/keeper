<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../i18n";
import { useRelease } from "../composables/useRelease";

const { t } = useI18n();
const { version, urlFor, primaryKey, releasesLatest } = useRelease();

// 系统识别同步完成（navigator.userAgent），首屏即可定按钮文案与链接，无加载态闪烁。
// 链接：识别到 mac/windows 就指向对应平台直链（urlFor 在版本号未到位时自带 Releases 页兜底）；
//       其它系统（Linux 等）无对应产物，直接引导到 Releases 页。
const primaryHref = computed(() => (primaryKey ? urlFor(primaryKey) : releasesLatest));
const primaryLabel = computed(() => {
  if (!primaryKey) return t.value.hero.fallbackPrimary;
  const osName = primaryKey === "windows" ? "Windows" : "macOS";
  return t.value.hero.primaryPrefix + osName;
});

const wall = Array.from({ length: 9 }, (_, i) => i + 1);
const keepIdx = [2, 6];
const cutIdx = [1, 5, 9];
const c = computed(() => t.value.hero);
</script>

<template>
  <section id="top" class="hero">
    <div class="container grid">
      <div class="copy">
        <p class="kicker">{{ c.kicker }}</p>
        <h1>{{ c.titleA }}<br /><em>{{ c.titleB }}</em></h1>
        <p class="lede">{{ c.lede }}</p>
        <div class="cta">
          <a class="btn btn--primary big" :href="primaryHref" target="_blank" rel="noopener">↓ {{ primaryLabel }}</a>
          <a class="btn" href="#download">{{ c.otherPlatforms }}</a>
        </div>
        <p class="meta">
          <span v-if="version">v{{ version }} · </span>{{ c.meta }}
        </p>
      </div>

      <div class="stage" aria-hidden="true">
        <div class="wall">
          <div
            v-for="n in wall"
            :key="n"
            class="t"
            :class="{ keep: keepIdx.includes(n), cut: cutIdx.includes(n) }"
            :data-tag="keepIdx.includes(n) ? c.keep : cutIdx.includes(n) ? c.cut : ''"
          >
            <img :src="`https://picsum.photos/seed/kw${n}/160/200`" alt="" loading="lazy" />
          </div>
        </div>
        <div class="badge">{{ c.wallBadge }}</div>
        <figure class="polaroid">
          <img src="https://picsum.photos/seed/kpola/300/300" alt="" loading="lazy" />
          <figcaption>{{ c.polaroidCap }}</figcaption>
        </figure>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero { padding: 72px 0 80px; }
.grid { display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 32px; align-items: center; }
.kicker { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; text-transform: uppercase; color: var(--amber); margin: 0 0 20px; }
h1 { font-family: var(--font-display); font-weight: 400; font-size: 48px; line-height: 1.14; margin: 0 0 20px; letter-spacing: -0.01em; }
h1 em { font-style: italic; color: var(--amber-bright); }
.lede { font-size: 16px; line-height: 1.75; color: var(--ink-dim); max-width: 440px; margin: 0 0 30px; }
.cta { display: flex; gap: 13px; margin-bottom: 16px; flex-wrap: wrap; }
.big { padding: 14px 26px; font-size: 15px; }
.meta { font-family: var(--font-mono); font-size: 12px; color: var(--ink-faint); margin: 0; }

.stage { position: relative; height: 360px; display: flex; align-items: center; justify-content: center; }
.wall { display: grid; grid-template-columns: repeat(3, 84px); grid-auto-rows: 104px; gap: 6px; transform: rotate(-3deg); }
.t { border-radius: 5px; overflow: hidden; position: relative; border: 1px solid var(--line); }
.t img { width: 100%; height: 100%; object-fit: cover; filter: sepia(0.12) brightness(0.85); }
.t.cut { opacity: 0.4; }
.t.keep::after, .t.cut::after { content: attr(data-tag); font-family: var(--font-display); position: absolute; top: 4px; left: 5px; font-size: 11px; border-radius: 4px; padding: 0 6px; line-height: 18px; }
.t.keep::after { color: #08251a; background: var(--green); }
.t.cut::after { color: #2a0f08; background: var(--red); }
.badge { position: absolute; left: -6px; top: 10px; font-family: var(--font-mono); font-size: 10.5px; color: var(--amber-bright); background: rgba(20, 16, 10, 0.9); border: 1px solid var(--amber); border-radius: 20px; padding: 5px 12px; backdrop-filter: blur(4px); }
.polaroid { position: absolute; right: 0; bottom: 0; width: 150px; margin: 0; background: #f3ecdd; padding: 9px 9px 30px; border-radius: 3px; transform: rotate(6deg); box-shadow: 0 20px 44px -16px rgba(0, 0, 0, 0.85); }
.polaroid img { width: 100%; height: 148px; object-fit: cover; filter: sepia(0.2) contrast(1.04); }
.polaroid figcaption { font-family: var(--font-display); font-style: italic; font-size: 12px; color: #5a4326; text-align: center; margin-top: 7px; }
@media (max-width: 860px) { .grid { grid-template-columns: 1fr; } .stage { display: none; } h1 { font-size: 38px; } }
</style>
