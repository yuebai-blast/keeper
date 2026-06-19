// 评测进度的展示文案：阶段中文名 + 照片级「阶段 X / N」，GroupDetail 与 GroupList 复用。
import { AssessPhase, type AssessProgress } from "../api";

const PHASE_LABEL: Record<string, string> = {
  [AssessPhase.LAYER1]: "本地评分",
  [AssessPhase.LAYER2]: "大模型打分",
};

/** 阶段中文名（IDLE/DONE 无文案）。 */
export function phaseLabel(phase: string): string {
  return PHASE_LABEL[phase] ?? "";
}

/** 照片级进度文本，如「本地评分 12 / 30」；非评分阶段返回准备中文案。 */
export function photoProgressText(p: AssessProgress): string {
  const label = phaseLabel(p.phase);
  if (!label) return "准备中…";
  return `${label} ${p.done} / ${p.total}`;
}
