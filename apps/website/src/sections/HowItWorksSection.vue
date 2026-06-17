<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../i18n";
const { t } = useI18n();
const c = computed(() => t.value.how);
</script>

<template>
  <section id="how" class="section">
    <div class="container">
      <p class="section-kicker">{{ c.kicker }}</p>
      <h2 class="section-title">{{ c.title }}</h2>
      <p class="section-lede">{{ c.lede }}</p>
      <ol class="steps">
        <li v-for="s in c.steps" :key="s.n" class="card step">
          <span class="n">{{ s.n }}</span>
          <h3>{{ s.title }}</h3>
          <p>{{ s.body }}</p>
        </li>
      </ol>
    </div>
  </section>
</template>

<style scoped>
.steps { list-style: none; padding: 0; margin: 32px 0 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.step .n { font-family: var(--font-mono); font-size: 13px; color: var(--amber); }
.step h3 { font-family: var(--font-display); font-weight: 400; font-size: 19px; margin: 10px 0 8px; }
.step p { color: var(--ink-dim); font-size: 13.5px; margin: 0; line-height: 1.65; }
@media (max-width: 860px) { .steps { grid-template-columns: 1fr 1fr; } }
@media (max-width: 480px) { .steps { grid-template-columns: 1fr; } }
</style>
