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

// 指标图例：含义 + 取值范围 + 高低意义。单个「?」hover 即见，讲清所有本地指标。
const LEGEND: { name: string; range: string; meaning: string }[] = [
  { name: "终分", range: "0–100", meaning: "本地综合分 = 基础分 − 扣分项；漏斗据此筛选" },
  { name: "基础分", range: "0–100", meaning: "扣分前 = 技术质量×0.45 + 美学×0.20 + 锐度×0.35" },
  { name: "技术质量", range: "0–100", meaning: "TOPIQ 无参考画质；越高越清晰干净。face=按主脸裁剪评，nr=按整图评" },
  { name: "美学", range: "0–100", meaning: "CLIP-IQA+ 观感分；越高观感越好" },
  { name: "锐度", range: "0–100", meaning: "主体（优先主脸）锐度归一；越高越锐利，脱焦/糊则低" },
  { name: "熵", range: "0–8", meaning: "灰度信息熵；越低画面越单调（如大片纯色），越高细节越丰富" },
  { name: "亮度", range: "0–255", meaning: "平均亮度；过低偏欠曝、过高偏过曝" },
  { name: "对比", range: "0–~128", meaning: "亮度标准差；越大明暗反差越强" },
  { name: "欠曝", range: "0–100%", meaning: "死黑像素占比；越高欠曝越严重" },
  { name: "过曝", range: "0–100%", meaning: "死白像素占比；越高过曝越严重" },
  { name: "人脸数", range: "≥0", meaning: "高置信人脸数（去掉背景误检）" },
  { name: "主脸面积", range: "0–100%", meaning: "最大人脸占整图比例" },
  { name: "检测置信度", range: "0–1", meaning: "主脸检测可信度；越高越确定是人脸" },
  { name: "主脸锐度", range: "拉普拉斯方差", meaning: "主脸区清晰度原始值；越大越锐，偏小则人脸糊/脱焦" },
  { name: "睁眼度", range: "EAR≈0–0.4", meaning: "眼睛纵横比；越大睁得越开，低于 0.18 判为闭眼" },
];

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
        <span class="help" tabindex="0" aria-label="指标说明">?
          <div class="tip" role="tooltip">
            <div class="tip-title">本地评测指标说明</div>
            <div v-for="item in LEGEND" :key="item.name" class="tip-row">
              <b>{{ item.name }}</b>
              <span class="tip-range">{{ item.range }}</span>
              <span class="tip-meaning">{{ item.meaning }}</span>
            </div>
          </div>
        </span>
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

/* 指标说明：单个「?」，hover/focus 弹出图例 */
.help {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  margin-left: auto;
  border-radius: 50%;
  border: 1px solid var(--line-strong);
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: 10px;
  cursor: help;
  user-select: none;
}
.help:hover, .help:focus-visible { color: var(--amber-bright); border-color: var(--amber); outline: none; }
.tip {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 20;
  width: 290px;
  max-height: 320px;
  overflow-y: auto;
  padding: 8px 10px;
  display: none;
  flex-direction: column;
  gap: 4px;
  background: var(--surface-2);
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
  text-align: left;
  cursor: default;
}
.help:hover .tip, .help:focus-within .tip { display: flex; }
.tip-title {
  font-size: 11px;
  color: var(--amber-bright);
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--line);
}
.tip-row {
  display: grid;
  grid-template-columns: 56px auto;
  gap: 0 8px;
  font-size: 11px;
  line-height: 1.4;
}
.tip-row b { color: var(--ink-dim); font-weight: 600; font-family: var(--font-mono); }
.tip-range {
  grid-column: 2;
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: 10px;
}
.tip-meaning { grid-column: 2; color: var(--ink-dim); }
</style>
