<script setup lang="ts">
// 透明展示一张照片的全部评测数据：层①本地明细（必有）+ 层②大模型结果（有则优先）。
import { computed } from "vue";
import type { PhotoView } from "../api";

const props = defineProps<{ photo: PhotoView }>();

const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${Math.round(v * 100)}`;
const num = (v: number | null | undefined, d = 0) =>
  v == null ? "—" : v.toFixed(d);

const hasLlm = computed(() => props.photo.llm_score != null);
const detail = computed(() => props.photo.local_detail);
const face = computed(() => props.photo.local_detail?.face ?? null);
// 指标含义图例已抽到页面级的 MetricLegend 组件，这里只展示数值。

const VERDICT_LABEL: Record<string, string> = {
  ready: "开图即用",
  worth_editing: "值得修",
  not_worth: "不划算",
  unfixable: "修不了",
};
const VERDICT_CLASS: Record<string, string> = {
  ready: "v-ready",
  worth_editing: "v-worth",
  not_worth: "v-notworth",
  unfixable: "v-unfixable",
};
const verdictLabel = computed(() => VERDICT_LABEL[props.photo.llm_editable] ?? "");
const verdictClass = computed(() => VERDICT_CLASS[props.photo.llm_editable] ?? "");
</script>

<template>
  <div class="stats">
    <!-- 层②大模型（优先展示） -->
    <div v-if="hasLlm" class="block llm">
      <div class="row head">
        <span class="tag tag--llm">大模型</span>
        <span class="big">{{ Math.round(photo.llm_score!) }}</span>
        <span v-if="photo.origin" class="tag" :class="photo.origin === 'PASSED' ? 'tag--pass' : 'tag--quota'">
          {{ photo.origin === "PASSED" ? "达标通过" : "兜底补入" }}
        </span>
      </div>
      <p v-if="photo.llm_reason" class="reason">{{ photo.llm_reason }}</p>
      <p v-if="photo.llm_flaws" class="flaws">瑕疵：{{ photo.llm_flaws }}</p>
      <p v-if="photo.llm_editable" class="advice">
        <span class="tag" :class="verdictClass">{{ verdictLabel }}</span>
        <span v-if="photo.llm_edit_advice" class="advice-text">{{ photo.llm_edit_advice }}</span>
      </p>
    </div>

    <!-- 层①本地明细（始终有） -->
    <div class="block">
      <div class="row head">
        <span class="tag">本地</span>
        <span class="big" :class="{ small: hasLlm }">{{ photo.local_score == null ? "—" : Math.round(photo.local_score) }}</span>
        <span v-if="detail" class="muted">基础 {{ Math.round(detail.base) }}</span>
        <span v-if="photo.local_detail?.tech_source" class="muted">{{ photo.local_detail.tech_source }}</span>
      </div>
      <div v-if="detail" class="grid">
        <span>技术质量 <b>{{ pct(detail.tech_quality) }}</b></span>
        <span>美学 <b>{{ pct(detail.clipiqa) }}</b></span>
        <span>锐度 <b>{{ pct(detail.sharpness_norm) }}</b></span>
        <span>熵 <b>{{ num(detail.entropy, 1) }}</b></span>
        <span>亮度 <b>{{ num(detail.brightness_mean) }}</b></span>
        <span>对比 <b>{{ num(detail.contrast) }}</b></span>
        <span>欠曝 <b>{{ pct(detail.underexposed_ratio) }}%</b></span>
        <span>过曝 <b>{{ pct(detail.overexposed_ratio) }}%</b></span>
      </div>

      <!-- 人脸明细：选片以人像为主，睁眼/脸清晰度最关键 -->
      <div v-if="face" class="faces">
        <template v-if="face.count > 0">
          <span class="ftag">人脸 {{ face.count }}</span>
          <span v-if="face.main_eye_ear != null">睁眼 <b>{{ num(face.main_eye_ear, 2) }}</b></span>
          <span v-if="face.main_area_ratio != null">主脸面积 <b>{{ pct(face.main_area_ratio) }}%</b></span>
          <span v-if="face.main_det_score != null">置信 <b>{{ num(face.main_det_score, 2) }}</b></span>
          <span v-if="face.main_sharpness != null">主脸锐度 <b>{{ num(face.main_sharpness) }}</b></span>
        </template>
        <span v-else class="ftag muted-tag">未检测到人脸</span>
      </div>

      <ul v-if="detail?.penalties?.length" class="penalties">
        <li v-for="(pen, i) in detail.penalties" :key="i">{{ pen.reason }} −{{ Math.round(pen.points) }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.stats { display: flex; flex-direction: column; gap: 10px; font-size: 12.5px; }
.block { display: flex; flex-direction: column; gap: 6px; }
.block.llm { border-bottom: 1px solid var(--line); padding-bottom: 10px; }
.row.head { display: flex; align-items: baseline; gap: 8px; }
.big { font-family: var(--font-mono); font-size: 22px; color: var(--amber-bright); }
.big.small { font-size: 17px; color: var(--ink-dim); }
.muted { color: var(--ink-faint); font-family: var(--font-mono); font-size: 11px; }
.reason { margin: 0; color: var(--ink-dim); line-height: 1.5; }
.flaws { margin: 0; color: var(--red); font-size: 12px; }
.advice { margin: 0; display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
.advice-text { color: var(--ink-dim); font-size: 12px; line-height: 1.5; }
.tag.v-ready { color: var(--green); border-color: var(--green); }
.tag.v-worth { color: var(--amber-bright); border-color: var(--amber); }
.tag.v-notworth { color: var(--ink-faint); }
.tag.v-unfixable { color: var(--red); border-color: var(--red); }
.tag {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.06em;
  padding: 1px 7px;
  border-radius: 5px;
  border: 1px solid var(--line-strong);
  color: var(--ink-dim);
}
.tag--llm { color: var(--amber-bright); border-color: var(--amber); }
.tag--pass { color: var(--green); border-color: var(--green); }
.tag--quota { color: var(--ink-faint); }
.grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 3px 14px;
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: 11.5px;
}
.grid b { color: var(--ink-dim); font-weight: 500; }
.faces {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 12px;
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: 11.5px;
}
.faces b { color: var(--ink-dim); font-weight: 500; }
.ftag {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.04em;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid var(--line-strong);
  color: var(--ink-dim);
}
.ftag.muted-tag { color: var(--ink-faint); border-color: var(--line); }
.penalties { margin: 2px 0 0; padding-left: 16px; color: var(--red); font-size: 11.5px; }
.penalties li { line-height: 1.5; }
</style>
