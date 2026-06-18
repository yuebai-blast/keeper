<script setup lang="ts">
// 本地评测指标图例：页面级的一个「指标说明」按钮，点一下展开面板，再点（或点空白处）收起。
// 不绑定到单张照片，整页固定一处即可。
import { ref } from "vue";

const open = ref(false);

// 含义 + 取值范围 + 高低意义，覆盖卡片上展示的全部本地指标。
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
</script>

<template>
  <div class="legend">
    <button class="btn btn--ghost" :class="{ active: open }" @click="open = !open">指标说明</button>

    <!-- 点空白处关闭 -->
    <div v-if="open" class="backdrop" @click="open = false" />

    <div v-if="open" class="panel" role="dialog" aria-label="本地评测指标说明">
      <div class="phead">
        <span>本地评测指标说明</span>
        <button class="x" aria-label="关闭" @click="open = false">×</button>
      </div>
      <div v-for="item in LEGEND" :key="item.name" class="row">
        <b>{{ item.name }}</b>
        <span class="range">{{ item.range }}</span>
        <span class="meaning">{{ item.meaning }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.legend { position: relative; }
.btn.active { color: var(--amber-bright); border-color: var(--amber); }
.backdrop { position: fixed; inset: 0; z-index: 90; }
.panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 100;
  width: 340px;
  max-height: 60vh;
  overflow-y: auto;
  padding: 10px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--surface-2);
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  text-align: left;
}
.phead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--amber-bright);
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--line);
}
.x {
  background: none;
  border: none;
  color: var(--ink-faint);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
}
.x:hover { color: var(--ink); }
.row {
  display: grid;
  grid-template-columns: 64px auto;
  gap: 0 8px;
  font-size: 11.5px;
  line-height: 1.45;
}
.row b { color: var(--ink-dim); font-weight: 600; font-family: var(--font-mono); }
.range {
  grid-column: 2;
  color: var(--ink-faint);
  font-family: var(--font-mono);
  font-size: 10px;
}
.meaning { grid-column: 2; color: var(--ink-dim); }
</style>
