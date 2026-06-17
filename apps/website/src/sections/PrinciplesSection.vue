<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../i18n";
const { t } = useI18n();
const c = computed(() => t.value.principles);
</script>

<template>
  <section class="section">
    <div class="container">
      <p class="section-kicker">{{ c.kicker }}</p>
      <h2 class="section-title">{{ c.title }}</h2>
      <div class="grid">
        <div v-for="(it, i) in c.items" :key="i" class="card" :class="it.tone">
          <span class="dot" />
          <h3>{{ it.title }}</h3>
          <p>{{ it.body }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 28px; }
.card h3 { font-family: var(--font-display); font-weight: 400; font-size: 22px; margin: 14px 0 10px; }
.card p { color: var(--ink-dim); margin: 0; line-height: 1.7; }
.dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; }
.card.green .dot { background: var(--green); box-shadow: 0 0 0 5px var(--green-soft); }
.card.red .dot { background: var(--red); box-shadow: 0 0 0 5px var(--red-soft); }
.card.green:hover { border-color: var(--green); }
.card.red:hover { border-color: var(--red); }
@media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
</style>
