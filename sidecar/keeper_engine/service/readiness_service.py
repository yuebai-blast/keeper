"""分组 / 层① 模型的就绪态 + 启动期加载（逐模块报进度、带下载速度与停滞检测）。

启动即一次性加载全部模型（不静默降级）：
  - 依赖缺失（DependencyMissing，Python 包未装）→ 致命、**不可重试**（不允许运行）。
  - 权重下载/加载失败、或下载长时间停滞（多为网络）→ **可重试**：前端给重试按钮。
进度经 /health 暴露：当前模块（current/total/step）+ 实时下载速度与已下载量 + 估算百分比。
完整性以「能否成功加载」为准：启动先清理残留 .partial，失败再清一次以便重试干净重下。
各模块状态经 mapper 持久化到 sqlite，供前端展示与诊断。
"""

from __future__ import annotations

import logging
import threading

from ..client.vision_client import MODULE_EXPECTED_MB, VisionClient
from ..config.settings import Settings
from ..exception.errors import DependencyMissing
from ..mapper.model_module_mapper import ModelModuleMapper
from .download_monitor import DownloadMonitor

logger = logging.getLogger("keeper_engine.service.readiness")

_WEIGHT_SUFFIXES = (".onnx", ".safetensors", ".bin", ".pth", ".pt")
_STALL_LIMIT_SECONDS = 90.0  # 下载零增长超过此值视为卡死（载入模型不下载的耗时一般远小于此）
_EXPECTED_TOTAL_BYTES = sum(MODULE_EXPECTED_MB.values()) * 1024 * 1024


class ReadinessService:
    """模型就绪状态机：loading / ready / error，带进度、下载速度、可重试与首次下载标记。DI 单例。"""

    def __init__(self, vision: VisionClient, settings: Settings, mapper: ModelModuleMapper) -> None:
        self._vision = vision
        self._settings = settings
        self._mapper = mapper
        self._lock = threading.Lock()
        self._monitor: DownloadMonitor | None = None
        self._cur_key = ""
        self.status = "loading"
        self.detail = ""
        self.retryable = False
        self.first_run = self._detect_first_run()
        self.current = 0
        self.total = len(MODULE_EXPECTED_MB)
        self.step = ""

    def _detect_first_run(self) -> bool:
        root = self._settings.models_dir
        if not root.exists():
            return True
        return not any(any(root.rglob(f"*{suffix}")) for suffix in _WEIGHT_SUFFIXES)

    def snapshot(self) -> dict:
        mon = self._monitor
        downloaded = mon.downloaded_bytes if mon else 0
        speed = mon.speed_bytes_per_s if mon else 0.0
        if self.status == "ready":
            percent = 100
        elif downloaded > 0:
            percent = min(99, int(downloaded / _EXPECTED_TOTAL_BYTES * 100))
        else:
            percent = 0
        return {
            "status": self.status,
            "detail": self.detail,
            "retryable": self.retryable,
            "first_run": self.first_run,
            "progress": {
                "current": self.current,
                "total": self.total,
                "step": self.step,
                "downloaded_mb": round(downloaded / 1024 / 1024, 1),
                "speed_mbps": round(speed / 1024 / 1024, 2),
                "percent": percent,
            },
            "modules": [{"name": m.name, "status": m.status} for m in self._mapper.all()],
        }

    def start_warmup(self) -> None:
        """启动后台预热线程，不阻塞调用方（在 app lifespan 里调用）。"""
        threading.Thread(target=self._warmup, name="keeper-warmup", daemon=True).start()

    def _on_step(self, current: int, total: int, key: str, label: str) -> None:
        self.current, self.total, self.step, self._cur_key = current, total, label, key
        self._mapper.upsert(key, "downloading")

    def _warmup(self) -> None:
        """清理 .partial → 启动监控 → 子线程 eager 加载 → 主循环监控停滞 → 收尾。"""
        self._vision.cleanup_partials()
        monitor = DownloadMonitor(self._settings.models_dir)
        monitor.start()
        self._monitor = monitor

        result: dict = {}

        def run() -> None:
            try:
                self._vision.load_all(self._on_step)
                result["ok"] = True
            except DependencyMissing as e:
                result["err"] = ("fatal", str(e))
            except Exception as e:  # noqa: BLE001 —— 下载/加载失败可重试，经就绪态上报
                result["err"] = ("retry", f"{type(e).__name__}: {e}")

        loader = threading.Thread(target=run, name="keeper-load", daemon=True)
        loader.start()

        while loader.is_alive():
            loader.join(timeout=0.5)
            if loader.is_alive() and monitor.stalled_seconds() > _STALL_LIMIT_SECONDS:
                # 下载长时间零增长 → 判卡死，转可重试 error（加载线程为 daemon，挂起随重试/退出释放）
                monitor.stop()
                self._fail("retry", f"{self.step} 下载停滞超过 {int(_STALL_LIMIT_SECONDS)} 秒，可能网络中断，请重试")
                return

        monitor.stop()
        if result.get("ok"):
            self.step = ""
            self.status = "ready"
            for key in MODULE_EXPECTED_MB:
                self._mapper.upsert(key, "ready")
            logger.info("readiness: 全部模型就绪")
        else:
            kind, msg = result["err"]
            detail = f"运行依赖缺失，无法启动：{msg}" if kind == "fatal" else msg
            self._fail(kind, detail)

    def _fail(self, kind: str, detail: str) -> None:
        self.status = "error"
        self.retryable = kind == "retry"
        self.detail = detail
        self._mapper.upsert(self._cur_key or "?", "error", detail)
        if kind == "retry":
            self._vision.cleanup_partials()  # 删废弃半成品，便于重试时干净重下
            logger.error("readiness: 模型加载失败（可重试）：%s", detail)
        else:
            logger.error("readiness: 依赖缺失，拒绝运行：%s", detail)

    def retry(self) -> bool:
        """重新预热——仅在「可重试的 error」时生效；返回是否已触发。"""
        with self._lock:
            if self.status != "error" or not self.retryable:
                return False
            self.status, self.detail, self.current, self.step = "loading", "", 0, ""
            self.start_warmup()
            return True

    def reload(self) -> bool:
        """强制重新加载（运行时发现模型不可用时的修复入口）；预热中则忽略。返回是否已触发。"""
        with self._lock:
            if self.status == "loading":
                return False
            self.status, self.detail = "loading", ""
            self.retryable, self.current, self.step = False, 0, ""
            self.start_warmup()
            return True
