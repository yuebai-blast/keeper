# 设计：并发补全 / 分组列表分区 / 一键通过模态框 / Windows 兼容 / 打包发布

日期：2026-06-16

本设计覆盖 5 个相对独立的任务。每个任务**单独验证、单独 commit（不 push）**，按下文顺序推进。

---

## 任务 1 — 并发（实现缺失部分）

### 现状（已确认）

| 环节 | 位置 | 并发情况 |
| :-- | :-- | :-- |
| 层② LLM 打分 | `client/scorer.py` `LocalDirectScorer.score` | ✅ 已并发：`ThreadPoolExecutor(max_workers=ark_concurrency)`，组内逐张并发，默认并发 4 |
| 层① 本地评分 | `service/assess_service.py` `AssessService.assess` | ❌ 串行：`for photo in req.photos` 逐张 |
| 跨组评测 | `service/project_service.py` `confirm_all` | ❌ 串行：逐组 `assess_group` |

### 目标

把**层① 组内逐张评分**改为并发；跨组**不做**并行（避免本地模型过度并发打爆 CPU/内存，风险/收益不划算，仅在注释/文档说明）。

### 设计

- 新增配置 `local_concurrency`（`config/settings.py`，环境变量 `KEEPER_LOCAL_CONCURRENCY`，默认 `2`，保守）。
- `AssessService.assess` 用 `ThreadPoolExecutor(max_workers=local_concurrency)` 并行调用 `PrescreenService.assess_photo`。torch / onnxruntime 的 C++ 推理执行时释放 GIL，多线程能拿到真实收益。
  - 保持现有容错语义：单张 `VisionUnavailable` 仍整体抛 `MODEL_NOT_READY`；单张其它异常记入 `errors` 不中断。并发下需收集每个 future 的成功/异常，**保持结果与输入同序**（survivors/scores 顺序不能乱）。
- **线程安全（关键风险）**：DINOv2 forward / pyiqa / InsightFace（onnxruntime session）并发调用的安全性不一致。采用「先验证后放开」：
  - 写并发-vs-串行**结果一致性测试**（同一组照片，串行结果与并发结果逐项相等）。
  - 对验证中表现不安全的模型调用，在 `VisionClient` 内加 **per-model 锁**，只锁住该次推理的最小段，尽量保留 C++ 段的并行。
  - 默认并发度保守（2），并暴露环境变量旋钮，便于在真实机器上标定。
- `confirm_all` 跨组保持串行；在该方法注释说明「为何不跨组并行」。

### 验证

- `mise run test`（含新增并发一致性测试）。
- `mise run lint`。
- 手动/脚本对一组多张照片跑 `/assess`，确认结果与串行一致、耗时下降。

---

## 任务 2 — 分组列表分两区

### 目标

`GroupList.vue` 把分组分成两块区域：**未处理在上、已处理在下方**。

### 设计

- 「已处理」= 状态 `confirmed`；「未处理」= `pending` / `assessed`。
- 两个 computed：`pendingGroups`、`confirmedGroups`，分别渲染为两个区块，各带小标题（如「待处理 N」「已处理 M」）与计数。
- 已处理区视觉弱化（降低不透明度 / 置灰边框），但保留进入组详情入口（确认后仍可改回）。
- 任一区为空则不渲染该区标题（避免空标题）。
- 组序号展示：保持稳定可读（如各区内从 1 开始或沿用全局序号，取实现简单且不误导者；实现时确定并在代码注释说明）。

### 验证

- `mise run app` 手动查看：含已确认与未确认组的项目，两区分明、已处理在下、入口可用。

---

## 任务 3 — 一键通过模态框

### 目标

把「一键通过所有分组」的原生 `window.confirm` 换成应用内样式化模态框，讲清含义与费用。

### 设计

- 新增可复用组件 `components/ConfirmDialog.vue`：遮罩 + 居中卡片，含标题、正文（支持多行/要点）、确认/取消按钮，emit `confirm`/`cancel`，受 `v-model`（或 `open` prop）控制；视觉与产品现有风格（CSS 变量 `--surface`/`--line`/`--amber` 等）一致；支持 Esc/点遮罩取消。
- 一键通过弹框文案讲清：
  1. **含义**：对尚未评测的分组自动跑层①+层② 评分，并按大模型的选择把所有分组标记为「已确认」。
  2. **费用**：会调用在线大模型，**可能产生费用**。
  3. 标记后仍可逐组改回，但需重新逐组检查。
- `GroupList.vue` 的 `submit()`（提交并完成）的 confirm 也一并换成该组件，统一观感。

### 验证

- `mise run app` 手动：点「一键通过」「提交并完成」均弹出新模态框，确认/取消/Esc/点遮罩行为正确。

---

## 任务 4 — Windows 兼容

### 目标

让 sidecar 能在 Windows 上正常安装依赖并 `python -m keeper_engine.main` 跑起来，修掉已知不兼容点。

### 设计

- **依赖修正（`sidecar/pyproject.toml`）**：现状 `onnxruntime-gpu[cuda,cudnn] ; sys_platform == 'win32'` 强制所有 Windows 装 CUDA 版，无 NVIDIA 卡的机器装不上/跑不起。改为：
  - 默认全平台 `onnxruntime`（CPU），与 `KEEPER_DEVICE` 默认 CPU 一致。
  - CUDA 作为可选能力（按 `KEEPER_DEVICE=cuda` 由用户自备环境，或留 extra），不绑死到 win32。
  - 改完跑 `mise run install` 重解析 `uv.lock`。
- **权限语义（`service/settings_service.py`）**：`os.chmod(f, 0o600)` 在 Windows 上不产生 POSIX 语义。加平台判断：Windows 上跳过（或退化为尽力而为）并在注释说明「Windows 机密文件保护语义不同、依赖用户目录 ACL」，POSIX 上维持 0600。
- **路径**：确认所有路径拼接走 `pathlib`（已基本如此），排查是否有硬编码 `/`、`~` 展开、临时目录假设。
- **依赖可用性**：确认 `uvicorn[standard]`、`pillow-heif`、`rawpy`、`opencv-contrib-python`、torch CPU wheel 在 Windows 有 wheel（均有）。
- 产出：记录已知平台差异（如机密文件权限、可选 CUDA）。

### 验证

- 在 CI 的 Windows job（任务 5）里至少跑通 `uv sync` + import 冒烟 + `mise run test`（能力所及）。
- 本地无 Windows 机时，以 CI 结果为准；代码层面静态排查 + lint。

---

## 任务 5 — 打包 + CI/CD + 安装

### 目标

tag 推送触发三平台编译产物流水线；app 自动拉起打包后的 sidecar；提供安装文档。**本轮不做代码签名/公证**，只出未签名产物 + 文档说明绕过方式。

### 设计

#### 5.1 sidecar 打包（PyInstaller）

- 用 PyInstaller 把 Python 服务冻结成单可执行 `keeper-sidecar`（onefile 或 onedir，按 torch/onnxruntime 体积与启动速度权衡，实现时定）。
- 处理 torch / onnxruntime / pyiqa / insightface / rawpy / opencv 的 hidden imports 与数据文件（PyInstaller 对这些库需 hook/`--collect-all`）。
- **模型权重不进包**，仍运行时下载到 `~/.keeper/models`（保持现有 readiness 预热流程）。
- 打包命令沉淀为 mise task（如 `mise run bundle-sidecar`），不散落脚本。
- 产物按 Tauri sidecar 命名规范带 target triple 后缀（如 `keeper-sidecar-aarch64-apple-darwin`）。

#### 5.2 app 自动拉起 sidecar

- `tauri.conf.json` 配 `bundle.externalBin`（或 `app` 下对应字段）指向 sidecar 可执行；Rust 壳通过 `tauri-plugin-shell` 的 sidecar API 在启动时 spawn，应用退出时终止子进程。
- 端口：固定 `127.0.0.1:8761`（与现状一致），或由壳分配空闲端口再经 `VITE_SIDECAR_URL` 注入（实现时取简单可靠者；若固定端口需处理占用冲突，至少给出清晰报错）。
- 前端 `components/SplashView.vue` 文案从「请手动 `mise run sidecar`」改为「正在启动本地推理服务…」自动等待；连接失败给出可读错误。
- **dev 模式不破坏**：开发仍可 `mise run sidecar` + `mise run app`（壳在 dev 下可不 spawn，或 spawn dev sidecar，实现时定，保证 `mise run app` 体验不退化）。

#### 5.3 GitHub Actions

- **PR / push 到主分支**：`lint` + `test`（sidecar），快反馈。
- **Tag 推送（`v*`）**：matrix 三产物
  - macOS arm64（Apple 芯片）：`macos-14`
  - macOS x86_64（Intel）：`macos-13`
  - Windows x86_64：`windows-latest`
  - 每个 job：checkout → 装 mise（锁定版本工具链）→ `mise run install` → `mise run bundle-sidecar` → `tauri build`（出 .dmg / NSIS .exe + .msi）→ 上传到 GitHub Release（按 tag）。
- 工作流文件放 `.github/workflows/`（如 `ci.yml` + `release.yml`）。

#### 5.4 安装文档

- README 增「下载与安装」段：
  - 三平台下载哪个产物（Apple 芯片 vs Intel vs Windows）。
  - 首次启动需联网下载约 1.6 GB 模型（一次性）。
  - macOS 未签名：Gatekeeper 拦截的绕过方式（右键打开 / `xattr -dr com.apple.quarantine`）。
  - Windows 未签名：SmartScreen「仍要运行」说明。

### 验证

- CI：tag 推送后三 job 全绿、Release 出现三平台产物。
- 至少在本机（macOS arm64）下载产物安装、启动、自动拉起 sidecar、跑通一次选片流程。
- Windows/Intel 以 CI 构建成功为底线（无对应物理机时不强求端到端手测，文档注明）。

---

## 任务间依赖与顺序

1. 任务 1（sidecar 并发）— 独立。
2. 任务 2（前端分区）— 独立。
3. 任务 3（前端模态框）— 独立，可与任务 2 同区域协作。
4. 任务 4（Windows 兼容）— 为任务 5 的 Windows 构建打底。
5. 任务 5（打包/CI/安装）— 最重，依赖任务 4 的 Windows 修正与 sidecar 自动拉起。

每完成一个任务：跑对应验证 → 通过后 `git commit`（中文提交信息，不 push）→ 进入下一个。

## 不做（本轮明确排除）

- 跨组并行评测（任务 1）。
- 代码签名 / Apple 公证 / Windows 代码签名（任务 5），只出未签名产物 + 绕过文档。
- 模型权重随包分发（仍运行时下载）。
- `CloudRelayScorer`、拍摄地离线反查等既有 backlog。
