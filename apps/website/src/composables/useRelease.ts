import { computed, onMounted, ref } from "vue";
import {
  detectOS,
  pickDesktopRelease,
  primaryMatchKey,
  RELEASES_API,
  RELEASES_LATEST,
  type DesktopRelease,
  type MatchKey,
} from "./release";

// 给页头「GitHub」链接等复用（指向 Releases 页）
export { RELEASES_LATEST } from "./release";

// 全站共享一次拉取结果（首屏与下载区复用，避免重复请求）
const release = ref<DesktopRelease | null>(null);
let started = false;

async function load() {
  if (started) return;
  started = true;
  try {
    // 同源反代（prod nginx / dev vite proxy）→ GitHub releases 列表，从中挑最新桌面正式版
    const res = await fetch(RELEASES_API, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    release.value = pickDesktopRelease(Array.isArray(data) ? data : []);
  } catch {
    release.value = null; // 失败：不显示版本号 + 下载兜底到 Releases 页，不影响可用性
  }
}

export function useRelease() {
  onMounted(load);
  const os = detectOS(navigator.userAgent);
  const version = computed(() => release.value?.version ?? null);

  // 拿到桌面版则给真实资产直链；否则（加载中 / 失败 / 该平台无产物）回退 Releases 页
  function urlFor(key: MatchKey): string {
    return release.value?.urls[key] ?? RELEASES_LATEST;
  }
  const primaryKey = primaryMatchKey(os);

  return { os, version, urlFor, primaryKey, releasesLatest: RELEASES_LATEST };
}
