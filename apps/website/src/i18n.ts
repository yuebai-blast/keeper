import { computed, ref } from "vue";
import { COPY, type Copy } from "./content/copy";

export type Locale = "zh" | "en";

const STORAGE_KEY = "keeper-locale";

function initialLocale(): Locale {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "zh" || saved === "en") return saved;
  return "zh"; // 默认中文
}

const locale = ref<Locale>(initialLocale());

// 把 <html lang> 同步到当前 locale（zh→zh-CN，en→en）。
// 模块加载时立即执行一次：修正 index.html 写死 zh-CN 与 localStorage 已存 en 不一致的首屏问题；
// setLocale 切换时也会再次调用，保持两处单一来源。
function syncDocumentLang(value: Locale) {
  document.documentElement.lang = value === "zh" ? "zh-CN" : "en";
}
syncDocumentLang(locale.value);

export function useI18n() {
  const t = computed<Copy>(() => COPY[locale.value]);
  function setLocale(next: Locale) {
    locale.value = next;
    localStorage.setItem(STORAGE_KEY, next);
    syncDocumentLang(next);
  }
  function toggle() {
    setLocale(locale.value === "zh" ? "en" : "zh");
  }
  return { locale, t, setLocale, toggle };
}
