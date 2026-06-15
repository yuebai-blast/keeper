<script setup lang="ts">
// 项目主页：列出全部项目（可恢复），入口新建项目。
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useProjectsStore } from "../stores/projects";
import { fmtTimeRange } from "../util/format";

const store = useProjectsStore();
const router = useRouter();

onMounted(() => store.loadProjects());

const STATUS_LABEL: Record<string, string> = {
  grouping: "分组中",
  selecting: "选片中",
  completed: "已完成",
};

function open(id: number, status: string) {
  router.push(status === "completed" ? `/projects/${id}/complete` : `/projects/${id}`);
}
</script>

<template>
  <section class="home">
    <div class="head">
      <div>
        <h1>选片项目</h1>
        <p class="lede">每次选片是一个项目，进度随时保存——可随时退出、稍后继续。</p>
      </div>
      <RouterLink to="/new" class="btn btn--primary lg">新建项目</RouterLink>
    </div>

    <p v-if="store.error" class="err">{{ store.error }}</p>

    <p v-if="!store.busy && store.list.length === 0" class="empty">
      还没有项目。点「新建项目」选择一个照片文件夹开始。
    </p>

    <ul class="list">
      <li v-for="p in store.list" :key="p.id" class="card" @click="open(p.id, p.status)">
        <div class="title">
          <span class="name">{{ p.name }}</span>
          <span class="status" :class="`s-${p.status}`">{{ STATUS_LABEL[p.status] ?? p.status }}</span>
        </div>
        <div class="meta">
          <span>{{ p.photo_count }} 张</span>
          <span v-if="p.location">· {{ p.location }}</span>
          <span v-if="fmtTimeRange(p.time_start, p.time_end)">· {{ fmtTimeRange(p.time_start, p.time_end) }}</span>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.home { display: flex; flex-direction: column; gap: 22px; }
.head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }
h1 { margin: 0 0 6px; font-family: var(--font-display); font-weight: 400; font-size: 30px; }
.lede { margin: 0; color: var(--ink-dim); font-size: 13.5px; }
.btn.lg { padding: 11px 22px; font-size: 14px; text-decoration: none; }
.empty { color: var(--ink-faint); font-size: 14px; padding: 30px 0; }
.err { color: var(--red); font-family: var(--font-mono); font-size: 13px; }

.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 18px;
  cursor: pointer;
  transition: border-color 0.18s, transform 0.1s;
}
.card:hover { border-color: var(--amber); transform: translateY(-1px); }
.title { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.name { font-family: var(--font-display); font-size: 19px; }
.status {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  padding: 2px 9px;
  border-radius: 20px;
  border: 1px solid var(--line-strong);
  color: var(--ink-dim);
}
.status.s-completed { color: var(--green); border-color: var(--green); }
.status.s-selecting { color: var(--amber-bright); border-color: var(--amber); }
.meta { display: flex; gap: 8px; flex-wrap: wrap; color: var(--ink-faint); font-size: 12.5px; font-family: var(--font-mono); }
</style>
