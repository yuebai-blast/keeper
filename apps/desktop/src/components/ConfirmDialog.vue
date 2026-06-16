<script setup lang="ts">
// 通用确认模态框：遮罩 + 居中卡片，标题/正文(slot)/确认取消。受 v-model:open 控制。
// 支持 Esc 与点遮罩取消。视觉沿用产品 CSS 变量。
import { watch } from "vue";

const props = defineProps<{
  open: boolean;
  title: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}>();
const emit = defineEmits<{
  "update:open": [boolean];
  confirm: [];
  cancel: [];
}>();

function close() {
  emit("update:open", false);
  emit("cancel");
}
function onConfirm() {
  emit("update:open", false);
  emit("confirm");
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") close();
}
watch(
  () => props.open,
  (v) => {
    if (v) window.addEventListener("keydown", onKey);
    else window.removeEventListener("keydown", onKey);
  },
);
</script>

<template>
  <Transition name="dlg">
    <div v-if="open" class="mask" @click.self="close">
      <div class="dialog" role="dialog" aria-modal="true">
        <h3 class="dtitle">{{ title }}</h3>
        <div class="dbody"><slot /></div>
        <div class="dactions">
          <button class="btn" @click="close">{{ cancelText ?? "取消" }}</button>
          <button class="btn" :class="danger ? 'btn--danger' : 'btn--primary'" @click="onConfirm">
            {{ confirmText ?? "确认" }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 24px;
}
.dialog {
  width: min(440px, 92vw);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 22px 24px 20px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
}
.dtitle {
  margin: 0 0 12px;
  font-family: var(--font-display);
  font-weight: 400;
  font-size: 20px;
  color: var(--ink);
}
.dbody { color: var(--ink-dim); font-size: 13.5px; line-height: 1.7; }
.dbody :deep(strong) { color: var(--amber-bright); font-weight: 600; }
.dbody :deep(p) { margin: 0 0 8px; }
.dbody :deep(ul) { margin: 0 0 8px; padding-left: 18px; }
.dbody :deep(li) { margin: 2px 0; }
.dactions { margin-top: 20px; display: flex; justify-content: flex-end; gap: 10px; }
.btn--danger { color: var(--red); border-color: var(--red); }

.dlg-enter-active,
.dlg-leave-active { transition: opacity 0.2s ease; }
.dlg-enter-from,
.dlg-leave-to { opacity: 0; }
.dlg-enter-active .dialog,
.dlg-leave-active .dialog { transition: transform 0.2s ease; }
.dlg-enter-from .dialog,
.dlg-leave-to .dialog { transform: translateY(10px) scale(0.98); }
</style>
