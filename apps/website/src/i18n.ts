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

export function useI18n() {
  const t = computed<Copy>(() => COPY[locale.value]);
  function setLocale(next: Locale) {
    locale.value = next;
    localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = next === "zh" ? "zh-CN" : "en";
  }
  function toggle() {
    setLocale(locale.value === "zh" ? "en" : "zh");
  }
  return { locale, t, setLocale, toggle };
}
