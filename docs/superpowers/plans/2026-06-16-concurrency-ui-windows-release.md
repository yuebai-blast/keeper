# 并发补全 / 分组分区 / 一键通过模态框 / Windows 兼容 / 打包发布 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全本地评分并发；分组列表分「未处理/已处理」两区；一键通过改样式化模态框；让 sidecar 在 Windows 跑通；用 PyInstaller 打包 sidecar、Tauri 自动拉起、GitHub Actions 三平台 tag 发布 + 安装文档。

**Architecture:** sidecar（Python/FastAPI，分层 + DI）+ desktop（Tauri 2 + Vue3）。并发用 `ThreadPoolExecutor`；前端改 Vue 组件；打包用 PyInstaller 冻结 sidecar 成 Tauri sidecar 可执行，Rust 壳经 `tauri-plugin-shell` 启动它；CI 用 GitHub Actions matrix。

**Tech Stack:** Python 3.11 / uv / FastAPI / pytest；Vue3 + TS + Vite + Pinia；Tauri 2 / Rust；PyInstaller；GitHub Actions。

**约定：每个任务（Task）完成 → 跑该任务验证 → 通过后单独 `git commit`（中文信息，不 push）→ 进入下一任务。** 提交信息结尾加：
```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

---

## Task 1: 层① 本地评分并发

**Files:**
- Modify: `sidecar/keeper_engine/config/settings.py`（加 `local_concurrency` 配置）
- Modify: `sidecar/keeper_engine/service/assess_service.py`（并发 + 注入 settings）
- Modify: `sidecar/keeper_engine/container.py`（给 `assess_service` 注入 `settings`）
- Modify: `sidecar/keeper_engine/service/project_service.py`（`confirm_all` 注释说明不跨组并行）
- Test: `sidecar/tests/test_assess_service.py`（新建）

- [ ] **Step 1: 加配置项 `local_concurrency`**

在 `sidecar/keeper_engine/config/settings.py` 的「可配置项」区，`ark_concurrency` 之后附近加：

```python
    # 层① 本地评分组内并发度（逐张并行；torch/onnxruntime 推理释放 GIL，可获真实收益）。
    # 默认保守为 2，可经 KEEPER_LOCAL_CONCURRENCY 在真实机器上标定。
    local_concurrency: int = 2
```

- [ ] **Step 2: 写失败测试（并发编排：保序 + 容错）**

新建 `sidecar/tests/test_assess_service.py`：

```python
"""层① 并发编排测试——用桩 Prescreen/Readiness 验证并发下的保序与容错，不加载真实模型。"""

import threading
import time

import pytest

from keeper_engine.enumeration.biz_code import BizCode
from keeper_engine.exception.errors import BizException, VisionUnavailable
from keeper_engine.request.assess_request import AssessRequest, PhotoRef
from keeper_engine.service.assess_service import AssessService
from keeper_engine.service.funnel_service import FunnelService
from keeper_engine.service.params_service import ParamsService
from keeper_engine.vo.local_score import LocalScore


class FakeReadiness:
    def __init__(self, status="ready", detail=""):
        self.status = status
        self.detail = detail


class FakePrescreen:
    """按路径名末位数字给分；可注入 sleep 强制线程交错，记录最大并发数。"""

    def __init__(self, sleep=0.0, fail_paths=(), unavailable_paths=()):
        self._sleep = sleep
        self._fail = set(fail_paths)
        self._unavailable = set(unavailable_paths)
        self._active = 0
        self._max_active = 0
        self._lock = threading.Lock()

    def assess_photo(self, path, companions=()):
        with self._lock:
            self._active += 1
            self._max_active = max(self._max_active, self._active)
        try:
            if self._sleep:
                time.sleep(self._sleep)
            if path in self._unavailable:
                raise VisionUnavailable("model gone")
            if path in self._fail:
                raise ValueError("broken file")
            score = float(int(path[-1]) * 10)  # img0→0 … img9→90
            return LocalScore(path=path, score=score, detail=None)
        finally:
            with self._lock:
                self._active -= 1


def _svc(prescreen, readiness=None, concurrency=4):
    return AssessService(
        prescreen=prescreen,
        readiness=readiness or FakeReadiness(),
        funnel=FunnelService(),
        params=ParamsService(),
        concurrency=concurrency,
    )


def _req(n):
    return AssessRequest(group_id="g", photos=[PhotoRef(path=f"img{i}") for i in range(n)])


def test_results_keep_input_order_under_concurrency():
    pre = FakePrescreen(sleep=0.02)
    resp = _svc(pre, concurrency=4).assess(_req(6))
    assert [s.path for s in resp.scores] == [f"img{i}" for i in range(6)]
    assert pre._max_active > 1  # 确实并发了


def test_single_bad_photo_recorded_in_errors_not_fatal():
    resp = _svc(FakePrescreen(fail_paths={"img2"})).assess(_req(4))
    assert {e.path for e in resp.errors} == {"img2"}
    assert {s.path for s in resp.scores} == {"img0", "img1", "img3"}


def test_vision_unavailable_raises_model_not_ready():
    with pytest.raises(BizException) as ei:
        _svc(FakePrescreen(unavailable_paths={"img1"})).assess(_req(3))
    assert ei.value.code == BizCode.MODEL_NOT_READY


def test_not_ready_blocks():
    with pytest.raises(BizException) as ei:
        _svc(FakePrescreen(), readiness=FakeReadiness(status="loading")).assess(_req(2))
    assert ei.value.code == BizCode.MODEL_NOT_READY
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `mise run test -- tests/test_assess_service.py -v`
Expected: FAIL（`AssessService.__init__` 还没有 `concurrency` 参数 → TypeError）

- [ ] **Step 4: 改 `AssessService` 为并发**

把 `sidecar/keeper_engine/service/assess_service.py` 整体替换为：

```python
"""层① 本地评分端点编排：组内逐张「并发」打分 → 漏斗（保底数 M）收口出 survivors。

模型未就绪（预热中/失败）直接抛 MODEL_NOT_READY，不傻等也不假装健康；
单张数据错误（文件损坏等）记入 errors、不中断；任一张 VisionUnavailable → 整体 MODEL_NOT_READY。

并发：逐张评分用 ThreadPoolExecutor 并行（默认 local_concurrency=2）。torch / onnxruntime 的
推理在 C++ 段释放 GIL，多线程能拿到真实收益。onnxruntime InferenceSession.run 与 torch 的
no-grad 前向均为只读推理、可并发调用，故不在 VisionClient 内加锁（如未来换用非线程安全后端，
再就该次推理加最小锁）。结果按输入下标回填，保证与输入同序（survivors/排序不依赖完成顺序）。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..converter import score_converter
from ..enumeration.biz_code import BizCode
from ..exception.errors import BizException, VisionUnavailable
from ..request.assess_request import AssessRequest
from ..response.assess_response import AssessResponse
from ..response.common import PhotoError
from ..vo.local_score import LocalScore
from .funnel_service import FunnelService
from .params_service import ParamsService
from .prescreen_service import PrescreenService
from .readiness_service import ReadinessService


class AssessService:
    """/assess 编排：就绪门禁 + 逐张并发评分容错 + 漏斗收口（M）+ 组装响应。"""

    def __init__(
        self,
        prescreen: PrescreenService,
        readiness: ReadinessService,
        funnel: FunnelService,
        params: ParamsService,
        concurrency: int = 2,
    ) -> None:
        self._prescreen = prescreen
        self._readiness = readiness
        self._funnel = funnel
        self._params = params
        self._concurrency = max(1, concurrency)

    def assess(self, req: AssessRequest) -> AssessResponse:
        if self._readiness.status != "ready":
            raise BizException(
                BizCode.MODEL_NOT_READY,
                f"模型未就绪（{self._readiness.status}）：{self._readiness.detail or '预热中，请稍后重试'}",
            )

        photos = req.photos
        results: list[LocalScore | None] = [None] * len(photos)
        errors: list[PhotoError] = []
        unavailable: VisionUnavailable | None = None

        def work(idx: int) -> None:
            nonlocal unavailable
            photo = photos[idx]
            try:
                results[idx] = self._prescreen.assess_photo(photo.path, photo.companions)
            except VisionUnavailable as e:
                unavailable = e  # 本地模型整体不可用，循环外统一抛
            except Exception as e:  # noqa: BLE001 —— 单张数据错误上报而非静默跳过
                errors.append(PhotoError(path=photo.path, error=f"{type(e).__name__}: {e}"))

        workers = max(1, min(self._concurrency, len(photos))) if photos else 1
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, range(len(photos))))

        if unavailable is not None:
            raise BizException(BizCode.MODEL_NOT_READY, f"本地模型不可用：{unavailable}") from unavailable

        scores: list[LocalScore] = [s for s in results if s is not None]  # 保持输入顺序
        n = self._params.compute_n(len(photos))
        m = self._params.compute_m(n)
        survivors = score_converter.to_survivors(self._funnel.apply_funnel(scores, m))
        return AssessResponse(
            group_id=req.group_id, scores=scores, survivors=survivors, n=n, m=m, errors=errors
        )
```

- [ ] **Step 5: 容器注入 `concurrency`**

`sidecar/keeper_engine/container.py` 把 `assess_service` 改为：

```python
    assess_service = providers.Factory(
        AssessService,
        prescreen=prescreen_service,
        readiness=readiness_service,
        funnel=funnel_service,
        params=params_service,
        concurrency=settings.provided.local_concurrency,
    )
```

- [ ] **Step 6: `confirm_all` 注释说明不跨组并行**

`sidecar/keeper_engine/service/project_service.py` 的 `confirm_all` docstring 改为：

```python
        """一键通过：未评测的组先评测（默认信任大模型），再把所有组置为已确认。

        跨组「不」并行：组内层①已逐张并发、层②已按 ark_concurrency 并发；若再跨组并行，
        会叠加放大本地模型与显存/CPU 占用，风险（OOM/抖动）大于收益，故此处逐组串行。
        """
```

- [ ] **Step 7: 跑测试 + lint，确认通过**

Run: `mise run test -- tests/test_assess_service.py -v && mise run lint`
Expected: 4 passed；lint 无报错。

- [ ] **Step 8: 全量回归（确保没破坏既有）**

Run: `mise run test`
Expected: 全绿。

- [ ] **Step 9: 提交**

```bash
git add sidecar/keeper_engine/config/settings.py sidecar/keeper_engine/service/assess_service.py sidecar/keeper_engine/container.py sidecar/keeper_engine/service/project_service.py sidecar/tests/test_assess_service.py
git commit -m "feat(sidecar): 层①本地评分组内并发（保序+容错）+ 不跨组并行说明

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 分组列表分「未处理/已处理」两区

**Files:**
- Modify: `apps/desktop/src/pages/GroupList.vue`

- [ ] **Step 1: 拆分组 computed + 两区模板**

把 `GroupList.vue` 的 `<script setup>` 内 `confirmedCount` 之后加两个 computed：

```ts
const pendingGroups = computed(() =>
  (store.detail?.groups ?? []).filter((g) => g.status !== "confirmed"),
);
const confirmedGroups = computed(() =>
  (store.detail?.groups ?? []).filter((g) => g.status === "confirmed"),
);
// 组序号沿用「在全部分组中的原始次序」，避免两区各自从 1 起造成同号歧义
const indexOf = (gk: string) =>
  (store.detail?.groups ?? []).findIndex((g) => g.group_key === gk);
```

- [ ] **Step 2: 用两区替换原单一 `<ul class="list">`**

把模板里原来的 `<ul class="list"> … </ul>` 整块替换为一个可复用的内联结构（两区各渲染一次）。新模板片段：

```html
    <section v-if="pendingGroups.length" class="zone">
      <h2 class="zone-title">待处理 · {{ pendingGroups.length }}</h2>
      <ul class="list">
        <li
          v-for="g in pendingGroups"
          :key="g.group_key"
          class="card"
          @click="router.push(`/projects/${pid}/groups/${g.group_key}`)"
        >
          <div class="title">
            <span class="gname">组 {{ indexOf(g.group_key) + 1 }}</span>
            <span class="count">{{ g.photo_count }} 张</span>
            <span class="status" :class="`s-${g.status}`">{{ STATUS[g.status] ?? g.status }}</span>
            <span v-if="g.status !== 'pending'" class="kept">通过 {{ g.kept_count }}</span>
          </div>
          <div class="sub">
            <span v-if="g.location">{{ g.location }}</span>
            <span v-if="fmtTimeRange(g.time_start, g.time_end)">· {{ fmtTimeRange(g.time_start, g.time_end) }}</span>
          </div>
          <GroupThumbs :paths="g.photo_paths" :labels="g.photo_names" />
        </li>
      </ul>
    </section>

    <section v-if="confirmedGroups.length" class="zone zone--done">
      <h2 class="zone-title">已处理 · {{ confirmedGroups.length }}</h2>
      <ul class="list">
        <li
          v-for="g in confirmedGroups"
          :key="g.group_key"
          class="card"
          @click="router.push(`/projects/${pid}/groups/${g.group_key}`)"
        >
          <div class="title">
            <span class="gname">组 {{ indexOf(g.group_key) + 1 }}</span>
            <span class="count">{{ g.photo_count }} 张</span>
            <span class="status" :class="`s-${g.status}`">{{ STATUS[g.status] ?? g.status }}</span>
            <span class="kept">通过 {{ g.kept_count }}</span>
          </div>
          <div class="sub">
            <span v-if="g.location">{{ g.location }}</span>
            <span v-if="fmtTimeRange(g.time_start, g.time_end)">· {{ fmtTimeRange(g.time_start, g.time_end) }}</span>
          </div>
          <GroupThumbs :paths="g.photo_paths" :labels="g.photo_names" />
        </li>
      </ul>
    </section>
```

- [ ] **Step 3: 加分区样式**

在 `GroupList.vue` `<style scoped>` 末尾追加：

```css
.zone { display: flex; flex-direction: column; gap: 10px; }
.zone-title {
  margin: 6px 0 0;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-faint);
}
.zone--done { margin-top: 6px; padding-top: 14px; border-top: 1px solid var(--line); }
.zone--done .card { opacity: 0.62; }
.zone--done .card:hover { opacity: 1; }
```

- [ ] **Step 4: 前端类型检查通过**

Run: `cd apps/desktop && pnpm build`
Expected: `vue-tsc --noEmit` + vite build 成功，无类型错误。

- [ ] **Step 5: 手动验证**

Run: `mise run sidecar`（一个终端）+ `mise run app`（另一个终端）
确认：进入一个含已确认与未确认分组的项目 → 待处理区在上、已处理区在下方且视觉弱化；两区卡片都能点进组详情；任一区为空时该区标题不显示。

- [ ] **Step 6: 提交**

```bash
git add apps/desktop/src/pages/GroupList.vue
git commit -m "feat(desktop): 分组列表分「待处理/已处理」两区，已处理置于下方并弱化

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 一键通过样式化模态框

**Files:**
- Create: `apps/desktop/src/components/ConfirmDialog.vue`
- Modify: `apps/desktop/src/pages/GroupList.vue`

- [ ] **Step 1: 新建可复用 `ConfirmDialog.vue`**

`apps/desktop/src/components/ConfirmDialog.vue`：

```vue
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
```

> 说明：`btn` / `btn--primary` 是 `styles.css` 的全局按钮类（与 `GroupList.vue`、`SplashView.vue` 一致）；`btn--danger` 在本组件内补充定义。`--surface`/`--line-strong`/`--radius`/`--amber-bright`/`--red` 均为既有 CSS 变量。

- [ ] **Step 2: `GroupList.vue` 接入模态框，替换两处 `window.confirm`**

在 `<script setup>`：导入组件并加两个开关 ref，改写 `confirmAll`/`submit`。

导入与状态（加在 `import GroupThumbs` 后、`confirmedCount` 附近）：

```ts
import { ref } from "vue";
import ConfirmDialog from "../components/ConfirmDialog.vue";

const showConfirmAll = ref(false);
const showSubmit = ref(false);
```

把原 `confirmAll`/`submit` 改为：

```ts
async function doConfirmAll() {
  await store.confirmAll(pid.value);
}

async function doSubmit() {
  if (!store.allConfirmed) return;
  await store.complete(pid.value);
  router.push(`/projects/${pid.value}/complete`);
}
```

> 注意：`import { computed, onMounted } from "vue";` 这一行需补 `ref`，或单独 `import { ref } from "vue"`（上面已单独导入，避免改动原行）。

- [ ] **Step 3: 模板里按钮改为开弹框 + 挂两个对话框**

把 footer 两个按钮的 `@click` 改为开开关：

```html
      <button class="btn" :disabled="store.busy" @click="showConfirmAll = true">一键通过所有分组</button>
```
```html
      <button class="btn btn--keep" :disabled="!store.allConfirmed || store.busy" @click="showSubmit = true">
        提交并完成
      </button>
```

在 `</section>` 之前（仍在根 `section v-if="store.detail"` 内）加两个对话框：

```html
    <ConfirmDialog
      v-model:open="showConfirmAll"
      title="一键通过所有分组？"
      confirm-text="继续并开始评分"
      danger
      @confirm="doConfirmAll"
    >
      <p>此操作会：</p>
      <ul>
        <li>对<strong>尚未评测</strong>的分组自动运行本地评分（层①）与<strong>在线大模型评分</strong>（层②）；</li>
        <li>按大模型的选择把<strong>所有分组</strong>标记为「已确认」。</li>
      </ul>
      <p>其中在线大模型评分会调用外部服务，<strong>可能产生费用</strong>。标记后仍可逐组改回，但需重新逐组检查。</p>
    </ConfirmDialog>

    <ConfirmDialog
      v-model:open="showSubmit"
      title="提交并完成？"
      confirm-text="确认完成"
      @confirm="doSubmit"
    >
      <p>提交后会把所有「通过」的照片复制到输出目录，并删除 workspace 副本释放空间。</p>
    </ConfirmDialog>
```

- [ ] **Step 4: 给对话框列表加点排版（可选样式）**

`ConfirmDialog.vue` 的 `<style scoped>` 里 `.dbody` 后加：

```css
.dbody :deep(p) { margin: 0 0 8px; }
.dbody :deep(ul) { margin: 0 0 8px; padding-left: 18px; }
.dbody :deep(li) { margin: 2px 0; }
```

- [ ] **Step 5: 类型检查**

Run: `cd apps/desktop && pnpm build`
Expected: 成功，无类型错误。

- [ ] **Step 6: 手动验证**

Run: `mise run sidecar` + `mise run app`
确认：点「一键通过所有分组」弹出样式化模态框，含含义 + 费用提示；点「继续」执行、点「取消」/Esc/点遮罩关闭不执行；「提交并完成」同样弹新框且仅 `allConfirmed` 时按钮可点。

- [ ] **Step 7: 提交**

```bash
git add apps/desktop/src/components/ConfirmDialog.vue apps/desktop/src/pages/GroupList.vue
git commit -m "feat(desktop): 一键通过/提交完成改用应用内模态框，讲清含义与大模型费用

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Windows 兼容

**Files:**
- Modify: `sidecar/pyproject.toml`（onnxruntime 依赖去 CUDA 绑死）
- Modify: `sidecar/keeper_engine/service/settings_service.py`（chmod 跨平台）
- Test: `sidecar/tests/test_settings_service.py`（已有，追加用例）

- [ ] **Step 1: 修依赖 —— Windows 不再强制 onnxruntime-gpu**

`sidecar/pyproject.toml` 把这两行：

```toml
    "onnxruntime>=1.16 ; sys_platform != 'win32'",
    "onnxruntime-gpu[cuda,cudnn]>=1.16 ; sys_platform == 'win32'",
```

替换为（全平台 CPU 版，CUDA 由用户按需自备，避免无 N 卡 Windows 装不上）：

```toml
    # onnxruntime：全平台默认 CPU 版（与 KEEPER_DEVICE 默认 CPU 一致）。
    # 需要 GPU 的用户自行安装 onnxruntime-gpu 并设 KEEPER_DEVICE=cuda；不在依赖里绑死 CUDA，
    # 否则无 NVIDIA 卡的 Windows 机器会装不上/跑不起。
    "onnxruntime>=1.16",
```

- [ ] **Step 2: 重解析锁文件**

Run: `mise run install`
Expected: `uv sync` 成功，`sidecar/uv.lock` 更新（移除 onnxruntime-gpu）。

- [ ] **Step 3: 看 settings_service 现有 chmod 位置**

Run: `sed -n '125,175p' sidecar/keeper_engine/service/settings_service.py`
确认两处 `os.chmod(f, 0o600)` 的上下文（写密钥文件函数）。

- [ ] **Step 4: 写失败测试（Windows 上不调用 chmod）**

`sidecar/tests/test_settings_service.py` 末尾追加（保持文件既有 import 风格；若需要在文件顶部补 `import sys` / `from unittest.mock import patch`）：

```python
def test_secret_write_skips_chmod_on_windows(tmp_path, monkeypatch):
    """Windows 上 POSIX 0600 无意义：不应调用 os.chmod（避免无效/异常），仍正常写文件。"""
    import sys
    from unittest.mock import patch

    from keeper_engine.config.settings import Settings
    from keeper_engine.service.settings_service import SettingsService

    settings = Settings(home=tmp_path)
    svc = SettingsService(settings=settings, foundation_models=None)

    with patch.object(sys, "platform", "win32"), patch("os.chmod") as chmod:
        svc.save_ark_key("sk-test-123")  # 若方法名不同，改为实际写密钥的方法
        chmod.assert_not_called()

    assert settings.ark_key_file.read_text(encoding="utf-8").strip() == "sk-test-123"
```

> 执行者注意：把 `save_ark_key` 换成 settings_service 中真实写 ark key 的方法名（Step 3 已确认）；若写入是私有辅助函数，则测试调用对外公共方法。

- [ ] **Step 5: 运行测试，确认失败**

Run: `mise run test -- tests/test_settings_service.py -v`
Expected: FAIL（当前无条件调用 `os.chmod` → `chmod.assert_not_called()` 失败）

- [ ] **Step 6: 实现跨平台 chmod 守卫**

在 `settings_service.py` 顶部确保 `import os` 与 `import sys` 存在。把每处：

```python
        os.chmod(f, 0o600)
```

替换为：

```python
        # POSIX 限定权限；Windows 无等价 0600 语义（机密保护依赖用户目录 ACL），跳过避免无效调用。
        if sys.platform != "win32":
            os.chmod(f, 0o600)
```

- [ ] **Step 7: 跑测试 + lint**

Run: `mise run test -- tests/test_settings_service.py -v && mise run lint`
Expected: PASS；lint 无报错。

- [ ] **Step 8: 全量回归**

Run: `mise run test`
Expected: 全绿。

- [ ] **Step 9: 提交**

```bash
git add sidecar/pyproject.toml sidecar/uv.lock sidecar/keeper_engine/service/settings_service.py sidecar/tests/test_settings_service.py
git commit -m "fix(sidecar): Windows 兼容——onnxruntime 去 CUDA 绑死 + 机密文件 chmod 跳过 Windows

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: 打包 + CI/CD + 安装文档

> 本任务无法用单元测试驱动；以「命令成功 + 产物存在 + CI 全绿」为验证。分多个小步、每步可验证。**本轮不做代码签名/公证**。

**Files:**
- Create: `sidecar/keeper-sidecar.spec`（PyInstaller 配置）
- Modify: `sidecar/pyproject.toml`（dev 组加 pyinstaller）
- Modify: `mise.toml`（加 `bundle-sidecar` task）
- Modify: `apps/desktop/src-tauri/Cargo.toml`（加 `tauri-plugin-shell`）
- Modify: `apps/desktop/src-tauri/src/lib.rs`（启动时 spawn sidecar）
- Create: `apps/desktop/src-tauri/capabilities/default.json` 或修改既有 capabilities（放行 shell sidecar）
- Modify: `apps/desktop/src-tauri/tauri.conf.json`（externalBin）
- Modify: `apps/desktop/src/components/SplashView.vue`（offline 文案）
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`
- Modify: `README.md`（下载与安装）

### 5A — PyInstaller 打包 sidecar

- [ ] **Step 1: dev 依赖加 PyInstaller**

`sidecar/pyproject.toml` 的 `[dependency-groups]` dev 改为：

```toml
dev = ["pytest>=8", "ruff>=0.4", "pyinstaller>=6.6"]
```

Run: `mise run install`
Expected: 成功，pyinstaller 进 dev 依赖。

- [ ] **Step 2: 写 PyInstaller spec**

新建 `sidecar/keeper-sidecar.spec`：

```python
# PyInstaller 配置：把 Keeper sidecar 冻结成单目录可执行（onedir，启动更快、体积可控）。
# torch / onnxruntime / pyiqa / insightface / rawpy / opencv 需 collect 全部子模块与数据文件。
# 模型权重不打包，运行时下载到 ~/.keeper/models。
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []
for pkg in ("torch", "torchvision", "onnxruntime", "insightface", "pyiqa",
            "timm", "cv2", "rawpy", "pillow_heif", "transformers"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("uvicorn")

a = Analysis(
    ["entry.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="keeper-sidecar",
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="keeper-sidecar")
```

- [ ] **Step 3: PyInstaller 入口脚本**

新建 `sidecar/entry.py`（PyInstaller 入口，等价于 `python -m keeper_engine.main`）：

```python
"""PyInstaller 冻结入口：直接调用 sidecar 的 main()。

冻结后没有 `-m` 概念，故用显式入口。命令行参数（--host/--port）仍透传。
"""
from keeper_engine.main import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: mise task 打包**

`mise.toml` 末尾加：

```toml
[tasks.bundle-sidecar]
description = "用 PyInstaller 把 sidecar 冻结成可执行（产物在 sidecar/dist/keeper-sidecar/）"
dir = "sidecar"
run = "uv run pyinstaller keeper-sidecar.spec --noconfirm --clean"
```

- [ ] **Step 5: 本机打包验证**

Run: `mise run bundle-sidecar`
Expected: `sidecar/dist/keeper-sidecar/keeper-sidecar`（Windows 为 `keeper-sidecar.exe`）存在。

Run: `./sidecar/dist/keeper-sidecar/keeper-sidecar --port 8761 &` 然后 `curl -s http://127.0.0.1:8761/health`，确认返回 ApiResponse JSON（`code` 字段存在）。验证后 `kill %1`。

> 若缺 hidden import 报 `ModuleNotFoundError`，把缺失模块名加入 spec 的 `hiddenimports`，重跑 Step 5。

- [ ] **Step 6: 提交（打包脚手架）**

```bash
git add sidecar/keeper-sidecar.spec sidecar/entry.py sidecar/pyproject.toml sidecar/uv.lock mise.toml
git commit -m "build(sidecar): PyInstaller 冻结 sidecar 为可执行 + bundle-sidecar task

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### 5B — Tauri 自动拉起 sidecar

- [ ] **Step 7: Rust 加 shell 插件依赖**

`apps/desktop/src-tauri/Cargo.toml` `[dependencies]` 加：

```toml
tauri-plugin-shell = "2"
```

- [ ] **Step 8: 准备 sidecar 二进制目录约定**

约定把打包产物（onedir）整体作为资源随包分发，并提供一个带 target-triple 后缀的启动器二进制给 Tauri sidecar 机制。最简稳妥做法：用 `externalBin` 指向**单文件启动器**，由它再定位 onedir。为降低复杂度，本计划采用 **onefile 兜底**：在 Step 2 的 spec 末尾改用单文件（去掉 COLLECT、EXE 不 `exclude_binaries`）。

将 `keeper-sidecar.spec` 的 `exe`/`coll` 段替换为单文件：

```python
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="keeper-sidecar",
    console=True,
    onefile=True,
)
```

> 单文件启动稍慢（首次自解压），但避免 onedir 随 Tauri 分发的路径处理复杂度，先求可用。

- [ ] **Step 9: 加 mise task 把产物放到 Tauri 期望位置**

Tauri sidecar 要求二进制名带 target triple 后缀，放在 `src-tauri/binaries/`。`mise.toml` 加：

```toml
[tasks.stage-sidecar]
description = "把 PyInstaller 单文件产物按 target triple 命名放到 Tauri binaries/ 目录"
dir = "."
run = """
rustc -vV | sed -n 's/host: //p' | tr -d '\\n' > /tmp/triple.txt
TRIPLE=$(cat /tmp/triple.txt)
mkdir -p apps/desktop/src-tauri/binaries
EXT=""
if [ "$OS" = "Windows_NT" ]; then EXT=".exe"; fi
cp "sidecar/dist/keeper-sidecar$EXT" "apps/desktop/src-tauri/binaries/keeper-sidecar-$TRIPLE$EXT"
"""
```

> Windows runner 上 `mise` 跑 bash 步骤由 GitHub Actions 的 `shell: bash` 保证（见 release.yml）；本地 Windows 开发者可手动复制。

- [ ] **Step 10: tauri.conf.json 声明 externalBin**

`apps/desktop/src-tauri/tauri.conf.json` 的 `bundle` 段加 `externalBin`：

```json
  "bundle": {
    "active": true,
    "targets": "all",
    "externalBin": ["binaries/keeper-sidecar"],
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  }
```

- [ ] **Step 11: capabilities 放行 shell sidecar**

查看 `apps/desktop/src-tauri/capabilities/`（Run: `ls apps/desktop/src-tauri/capabilities/ && cat apps/desktop/src-tauri/capabilities/*.json`）。在默认 capability 的 `permissions` 数组加：

```json
"shell:allow-execute",
"shell:allow-spawn",
{
  "identifier": "shell:allow-spawn",
  "allow": [{ "name": "binaries/keeper-sidecar", "sidecar": true, "args": ["--port", "8761"] }]
}
```

> 若无 capabilities 目录或结构不同，按 Tauri 2 文档创建 `capabilities/default.json`，`windows: ["main"]`，含上面 shell 权限。

- [ ] **Step 12: Rust 壳启动时 spawn sidecar**

`apps/desktop/src-tauri/src/lib.rs` 改为在 `setup` 里 spawn sidecar（dev 模式不 spawn，沿用 `mise run sidecar`）：

```rust
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

// ……（pick_folder / open_path / exit_app 三个命令保持不变）……

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // 仅打包运行时自动拉起内置 sidecar；dev 下用 `mise run sidecar`，不重复起。
            if !cfg!(debug_assertions) {
                let sidecar = app
                    .shell()
                    .sidecar("keeper-sidecar")
                    .expect("缺少 keeper-sidecar 可执行")
                    .args(["--port", "8761"]);
                let (mut rx, _child) = sidecar.spawn().expect("无法启动 keeper-sidecar");
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = rx.recv().await {
                        if let CommandEvent::Stderr(line) | CommandEvent::Stdout(line) = event {
                            eprintln!("[sidecar] {}", String::from_utf8_lossy(&line));
                        }
                    }
                });
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![pick_folder, open_path, exit_app])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

> sidecar 子进程随 app 退出由 Tauri shell 插件管理（应用结束时清理子进程）。

- [ ] **Step 13: SplashView offline 文案改为打包视角**

`apps/desktop/src/components/SplashView.vue` 的 offline 分支：

```html
        <!-- 服务未启动 -->
        <div v-else-if="view === 'offline'" key="offline" class="stage">
          <p class="line warn">本地推理服务尚未就绪</p>
          <p class="hint">正在启动内置推理服务，请稍候；若长时间无响应，请重启应用。<br />（开发模式下请在终端运行 <code>mise run sidecar</code>）</p>
          <button class="btn" @click="engine.refresh()">重新连接</button>
        </div>
```

- [ ] **Step 14: 本机端到端验证（打包运行自动拉起）**

Run: `mise run bundle-sidecar && mise run stage-sidecar && cd apps/desktop && pnpm tauri build`
Expected: 出 `.app`/`.dmg`（macOS）。打开安装的 app，**不**手动起 sidecar，确认 Splash 能连上、模型就绪、可进入选片流程。

- [ ] **Step 15: 提交（自动拉起）**

```bash
git add apps/desktop/src-tauri/Cargo.toml apps/desktop/src-tauri/Cargo.lock apps/desktop/src-tauri/src/lib.rs apps/desktop/src-tauri/tauri.conf.json apps/desktop/src-tauri/capabilities sidecar/keeper-sidecar.spec mise.toml apps/desktop/src/components/SplashView.vue
git commit -m "feat(desktop): 打包态由 Tauri 壳自动拉起内置 sidecar（externalBin + shell 插件）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### 5C — GitHub Actions

- [ ] **Step 16: CI 工作流（lint + test）**

新建 `.github/workflows/ci.yml`：

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  sidecar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: jdx/mise-action@v2
      - run: mise install
      - run: uv sync --directory sidecar
      - run: mise run lint
      - run: mise run test
```

- [ ] **Step 17: Release 工作流（tag 三平台产物）**

新建 `.github/workflows/release.yml`：

```yaml
name: Release
on:
  push:
    tags: ["v*"]

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: macos-14      # Apple 芯片 (arm64)
            target: aarch64-apple-darwin
          - os: macos-13      # Intel (x86_64)
            target: x86_64-apple-darwin
          - os: windows-latest
            target: x86_64-pc-windows-msvc
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash
    steps:
      - uses: actions/checkout@v4
      - uses: jdx/mise-action@v2
      - run: mise install
      - run: mise run install
      - run: mise run bundle-sidecar
      - run: mise run stage-sidecar
      - name: Build Tauri app
        working-directory: apps/desktop
        run: pnpm tauri build
      - name: Upload to release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            apps/desktop/src-tauri/target/release/bundle/dmg/*.dmg
            apps/desktop/src-tauri/target/release/bundle/nsis/*.exe
            apps/desktop/src-tauri/target/release/bundle/msi/*.msi
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

> 注：`pnpm` 由 mise 提供（`mise install` 后在 PATH）。若 `pnpm tauri` 找不到，改用 `mise exec -- pnpm tauri build`。Windows 上 PyInstaller/torch 下载较慢，job 超时可在 `release.yml` 加 `timeout-minutes: 90`。

- [ ] **Step 18: 提交 CI**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml
git commit -m "ci: GitHub Actions——主分支 lint/test + tag 推送三平台编译产物发布

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### 5D — 安装文档

- [ ] **Step 19: README 增「下载与安装」**

在 `README.md` 选合适位置插入：

```markdown
## 下载与安装

到 [Releases](https://github.com/yuebai-blast/keeper/releases) 下载对应平台产物：

| 平台 | 产物 | 说明 |
| :-- | :-- | :-- |
| macOS · Apple 芯片（M 系列） | `Keeper_*_aarch64.dmg` | 打开 dmg 拖入「应用程序」 |
| macOS · Intel 芯片 | `Keeper_*_x64.dmg` | 同上 |
| Windows x64 | `Keeper_*_x64-setup.exe`（或 `.msi`） | 双击安装 |

**首次启动需联网**：应用会一次性下载约 1.6 GB 本地 AI 模型到 `~/.keeper/models`，之后完全离线运行，照片不出本地。

### 未签名产物的放行（本项目当前不做代码签名）

- **macOS**：首次打开若提示「已损坏 / 无法验证开发者」，在「系统设置 → 隐私与安全性」点「仍要打开」，或终端执行：
  `xattr -dr com.apple.quarantine /Applications/Keeper.app`
- **Windows**：SmartScreen 提示时点「更多信息 → 仍要运行」。

### 配置大模型

选片的层②评分需要火山方舟（Ark）API key，在应用「设置」页录入，或写入 `~/.keeper/ark_key`（权限 0600）。
```

> 执行者注意：表格里 dmg/exe 的确切文件名以 Tauri 实际产物名为准，首个 Release 出来后回填校正。

- [ ] **Step 20: 提交文档**

```bash
git add README.md
git commit -m "docs: README 增三平台下载与安装、未签名产物放行、大模型配置说明

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 21: 端到端发布验证（打 tag）**

```bash
git tag v0.1.0-rc.1
git push origin v0.1.0-rc.1   # 仅此步需 push 以触发 release，事先与用户确认
```
Expected: GitHub Actions `Release` 三 job 全绿，对应 Release 出现 macOS arm64/x64 dmg 与 Windows 安装包。

> 本步涉及 push 与外发产物，**执行前须经用户确认**（与其余任务「只 commit 不 push」约定不同）。

---

## 自检对照（Self-Review）

- **spec 覆盖**：任务1并发→Task1；任务2分区→Task2；任务3模态框→Task3；任务4 Windows（onnxruntime+chmod）→Task4；任务5（PyInstaller/externalBin 自动拉起/三平台 CI/安装文档/不签名）→Task5（5A–5D）。✅
- **不做项**：跨组并行（Task1 Step6 注释说明不做）、签名/公证（Task5 标注不做）。✅
- **类型/命名一致**：`AssessService(..., concurrency=...)` 与容器 `settings.provided.local_concurrency` 一致；`ConfirmDialog` 的 `v-model:open` 与 `@confirm` 在 GroupList 调用一致；`keeper-sidecar` 名称在 spec/stage-sidecar/externalBin/Rust `sidecar("keeper-sidecar")` 一致。✅
- **已知留待执行者确认**：settings_service 写 ark key 的真实方法名（Task4 Step3/4）、capabilities 现有结构（Task5 Step11）、Tauri 产物确切文件名（Task5 Step19）。
```
