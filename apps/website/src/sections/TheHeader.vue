<script setup lang="ts">
import { useI18n } from "../i18n";
import { RELEASES_LATEST } from "../composables/useRelease";

const { t, locale, toggle } = useI18n();
</script>

<template>
  <header class="hd">
    <div class="container row">
      <a href="#top" class="brand">
        <span class="logo">留影 Keeper</span>
        <span class="en">Local-first AI Culling</span>
      </a>
      <nav class="nav">
        <a href="#how">{{ t.nav.how }}</a>
        <a href="#features">{{ t.nav.features }}</a>
        <a href="#faq">{{ t.nav.faq }}</a>
        <button class="lang" @click="toggle">{{ locale === "zh" ? "中 / EN" : "EN / 中" }}</button>
        <a class="gh" :href="RELEASES_LATEST" target="_blank" rel="noopener">★ {{ t.nav.github }}</a>
        <a class="btn btn--primary dl" href="#download">{{ t.nav.download }}</a>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.hd { position: sticky; top: 0; z-index: 50; background: rgba(20, 16, 10, 0.78); backdrop-filter: blur(10px); border-bottom: 1px solid var(--line); }
.row { display: flex; align-items: center; justify-content: space-between; height: 64px; }
.brand { display: flex; align-items: baseline; gap: 9px; }
.logo { font-family: var(--font-display); font-size: 20px; font-weight: 500; }
.en { font-family: var(--font-mono); font-size: 11px; color: var(--ink-faint); letter-spacing: 0.12em; text-transform: uppercase; }
.nav { display: flex; align-items: center; gap: 18px; }
.nav a:not(.btn):not(.gh) { color: var(--ink-dim); font-size: 14px; }
.nav a:hover { color: var(--amber-bright); }
.lang { font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-dim); border: 1px solid var(--line-strong); border-radius: 20px; padding: 4px 11px; background: transparent; cursor: pointer; }
.lang:hover { color: var(--amber-bright); border-color: var(--amber); }
.gh { font-size: 13px; color: var(--ink-dim); border: 1px solid var(--line-strong); border-radius: 9px; padding: 6px 13px; }
.dl { padding: 8px 16px; }
@media (max-width: 760px) { .en, .nav a:not(.btn):not(.gh), .gh { display: none; } }
</style>
