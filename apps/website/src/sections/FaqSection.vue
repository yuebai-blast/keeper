<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../i18n";
const { t } = useI18n();
const c = computed(() => t.value.faq);
</script>

<template>
  <section id="faq" class="section">
    <div class="container">
      <p class="section-kicker">{{ c.kicker }}</p>
      <h2 class="section-title">{{ c.title }}</h2>
      <div class="list">
        <details v-for="(it, i) in c.items" :key="i" class="card">
          <summary>{{ it.q }}</summary>
          <p>{{ it.a }}</p>
        </details>
      </div>
    </div>
  </section>
</template>

<style scoped>
.list { display: flex; flex-direction: column; gap: 12px; margin-top: 28px; }
summary { font-family: var(--font-display); font-size: 18px; cursor: pointer; list-style: none; display: flex; justify-content: space-between; }
summary::after { content: "+"; color: var(--amber); font-family: var(--font-mono); }
details[open] summary::after { content: "−"; }
details p { color: var(--ink-dim); margin: 14px 0 0; line-height: 1.7; }
</style>
