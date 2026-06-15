<script setup lang="ts">
// 完成页：展示输出目录与留存数量，可打开输出目录。
import { invoke } from "@tauri-apps/api/core";
import { computed, onMounted } from "vue";
import { useProjectsStore } from "../stores/projects";

const props = defineProps<{ id: string }>();
const store = useProjectsStore();
const pid = computed(() => Number(props.id));

onMounted(() => store.loadProject(pid.value));

const project = computed(() => store.detail?.project);
const keptCount = computed(
  () => store.detail?.groups.reduce((sum, g) => sum + g.kept_count, 0) ?? 0,
);

function openFolder() {
  if (project.value) invoke("open_path", { path: project.value.target_dir });
}
</script>

<template>
  <section v-if="project" class="done">
    <div class="seal">✓</div>
    <h1>{{ project.name }} · 已完成</h1>
    <p class="lede">
      已把 <b>{{ keptCount }}</b> 张通过的照片复制到输出目录，workspace 副本已清理。
    </p>
    <code class="path">{{ project.target_dir }}</code>
    <div class="ops">
      <button class="btn btn--primary" @click="openFolder">打开输出目录</button>
      <RouterLink to="/" class="btn">返回项目列表</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.done { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 8vh 0; text-align: center; }
.seal {
  width: 64px; height: 64px; border-radius: 50%;
  display: grid; place-items: center;
  font-size: 30px; color: #08251a;
  background: linear-gradient(180deg, #8ad6ad, var(--green));
  box-shadow: 0 0 0 6px var(--green-soft);
}
h1 { margin: 0; font-family: var(--font-display); font-weight: 400; font-size: 28px; }
.lede { margin: 0; color: var(--ink-dim); font-size: 14px; }
.lede b { color: var(--amber-bright); }
.path {
  font-family: var(--font-mono); font-size: 12.5px; color: var(--ink-dim);
  background: var(--surface); padding: 8px 14px; border-radius: 8px; word-break: break-all; max-width: 600px;
}
.ops { display: flex; gap: 12px; margin-top: 8px; }
.ops .btn { text-decoration: none; }
</style>
