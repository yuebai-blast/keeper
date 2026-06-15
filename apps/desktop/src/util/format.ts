// 展示用的小工具：文件名、时间、分数取舍。
import type { PhotoView } from "../api";

export const basename = (p: string): string => p.split(/[\\/]/).pop() ?? p;

/** 把 ISO 时间格式化为「YYYY-MM-DD HH:mm」；空值返回空串。 */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 拍摄时间范围：同段折叠，仅一端则显示一端，都空返回空串。 */
export function fmtTimeRange(start: string | null, end: string | null): string {
  const a = fmtDateTime(start);
  const b = fmtDateTime(end);
  if (a && b) return a === b ? a : `${a} — ${b}`;
  return a || b;
}

/** 展示分：优先层②大模型分，没有则层①本地分；都无返回 null。 */
export function displayScore(p: PhotoView): number | null {
  if (p.llm_score != null) return p.llm_score;
  if (p.local_score != null) return p.local_score;
  return null;
}

/** 按展示分降序（无分排最后）。 */
export function byScoreDesc(a: PhotoView, b: PhotoView): number {
  return (displayScore(b) ?? -1) - (displayScore(a) ?? -1);
}
