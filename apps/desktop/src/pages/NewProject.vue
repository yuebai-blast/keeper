<script setup lang="ts">
// 页面一：填项目名 + 选源文件夹 → 预览数量/时间/拍摄地 → 确认创建（复制副本）→ 分组 → 进列表。
import { invoke } from "@tauri-apps/api/core";
import { ref } from "vue";
import { useRouter } from "vue-router";
import type { ProjectPreview } from "../api";
import { useProjectsStore } from "../stores/projects";
import { fmtTimeRange } from "../util/format";

const store = useProjectsStore();
const router = useRouter();

const name = ref("");
const folder = ref("");
const preview = ref<ProjectPreview | null>(null);
const scanning = ref(false);
const creating = ref(false);
const localError = ref("");

async function chooseFolder() {
  localError.value = "";
  const picked = await invoke<string | null>("pick_folder");
  if (!picked) return; // 取消
  folder.value = picked;
  preview.value = null;
  scanning.value = true;
  try {
    preview.value = await store.preview(picked);
  } catch (e) {
    localError.value = e instanceof Error ? e.message : String(e);
  } finally {
    scanning.value = false;
  }
}

const canCreate = () =>
  !!name.value.trim() && !!folder.value && !!preview.value && preview.value.count > 0 && !creating.value;

async function create() {
  if (!canCreate()) return;
  creating.value = true;
  localError.value = "";
  try {
    const project = await store.create(name.value.trim(), folder.value);
    await store.runGroup(project.id); // 复制完成后立即分组
    router.push(`/projects/${project.id}`);
  } catch (e) {
    localError.value = e instanceof Error ? e.message : String(e);
  } finally {
    creating.value = false;
  }
}
</script>

<template>
  <section class="new">
    <RouterLink to="/" class="back">← 返回</RouterLink>
    <h1>新建项目</h1>

    <label class="field">
      <span>项目名称</span>
      <input v-model="name" type="text" placeholder="例如：林岚婚礼-上午" :disabled="creating" />
      <small>名称需唯一，将作为输出文件夹名（输出到 ~/Pictures/Keeper/{名称}）。</small>
    </label>

    <div class="field">
      <span>源文件夹</span>
      <div class="folder">
        <button class="btn" :disabled="creating" @click="chooseFolder">选择文件夹</button>
        <code v-if="folder" class="path">{{ folder }}</code>
        <span v-else class="muted">尚未选择</span>
      </div>
      <small>导入时会复制一份副本到 workspace，绝不改动你的原文件。</small>
    </div>

    <div v-if="scanning" class="preview muted">正在扫描…</div>
    <div v-else-if="preview" class="preview">
      <div class="stat"><b>{{ preview.count }}</b><span>张照片</span></div>
      <div v-if="fmtTimeRange(preview.time_start, preview.time_end)" class="stat">
        <b>{{ fmtTimeRange(preview.time_start, preview.time_end) }}</b><span>拍摄时间</span>
      </div>
      <div v-if="preview.location" class="stat"><b>{{ preview.location }}</b><span>拍摄地</span></div>
      <p v-if="preview.errors.length" class="warn">{{ preview.errors.length }} 张读取元数据失败（仍会导入）</p>
    </div>

    <p v-if="localError" class="err">{{ localError }}</p>

    <button class="btn btn--primary lg" :disabled="!canCreate()" @click="create">
      {{ creating ? "正在创建并分组…" : "确认创建" }}
    </button>
  </section>
</template>

<style scoped>
.new { display: flex; flex-direction: column; gap: 20px; max-width: 620px; }
.back { color: var(--ink-dim); text-decoration: none; font-size: 13px; width: fit-content; }
.back:hover { color: var(--amber-bright); }
h1 { margin: 0; font-family: var(--font-display); font-weight: 400; font-size: 28px; }
.field { display: flex; flex-direction: column; gap: 8px; }
.field > span { font-size: 13px; color: var(--ink-dim); }
.field small { color: var(--ink-faint); font-size: 12px; }
input {
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-sm);
  padding: 11px 14px;
}
input:focus { outline: none; border-color: var(--amber); }
.folder { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.path {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-dim);
  background: var(--surface);
  padding: 6px 10px;
  border-radius: 6px;
  word-break: break-all;
}
.muted { color: var(--ink-faint); font-size: 13px; }
.preview {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 18px 22px;
}
.stat { display: flex; flex-direction: column; gap: 3px; }
.stat b { font-family: var(--font-display); font-size: 22px; color: var(--amber-bright); font-weight: 400; }
.stat span { font-size: 12px; color: var(--ink-faint); }
.warn { flex-basis: 100%; margin: 0; color: var(--ink-faint); font-size: 12px; }
.err { color: var(--red); font-family: var(--font-mono); font-size: 13px; }
.btn.lg { padding: 12px 24px; font-size: 14.5px; width: fit-content; }
</style>
