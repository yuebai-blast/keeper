// 照片库 / 分组状态的 Pinia store。
import { invoke } from "@tauri-apps/api/core";
import { defineStore } from "pinia";
import { groupPhotos, type Group, type PhotoError } from "../api";

interface LibraryState {
  imported: boolean; // 是否已导入并分组
  total: number; // 导入的照片数
  groups: Group[];
  errors: PhotoError[];
  busy: boolean; // 导入/分组进行中
  error: string; // 流程级错误（取消不算）
}

export const useLibraryStore = defineStore("library", {
  state: (): LibraryState => ({
    imported: false,
    total: 0,
    groups: [],
    errors: [],
    busy: false,
    error: "",
  }),
  actions: {
    /** 弹目录选择器（Rust 壳扫图）→ 调 sidecar 分组。用户取消则什么都不做。 */
    async importAndGroup() {
      this.busy = true;
      this.error = "";
      try {
        const paths = await invoke<string[]>("import_photos");
        if (paths.length === 0) return; // 取消或空目录
        this.total = paths.length;
        const res = await groupPhotos(paths);
        this.groups = res.groups;
        this.errors = res.errors;
        this.imported = true;
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e);
      } finally {
        this.busy = false;
      }
    },
    reset() {
      this.imported = false;
      this.total = 0;
      this.groups = [];
      this.errors = [];
      this.error = "";
    },
  },
});
