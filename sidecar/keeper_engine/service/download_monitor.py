"""下载进度监控：周期采样缓存目录总字节数，算下载速度与累计已下载量。

不 hook 任何框架下载内部（三类模型走四套不同下载机制，无统一回调）——统一以「目录字节
增长」反映下载进度，稳健通用、不随上游升级失效。另提供停滞检测，供就绪态判断「卡死」。
"""

from __future__ import annotations

import threading
import time
from pathlib import Path


def _dir_size(root: Path) -> int:
    """目录下所有文件字节数之和（含正在写入的 .partial）。"""
    if not root.exists():
        return 0
    total = 0
    for p in root.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


class DownloadMonitor:
    """后台采样目录大小：downloaded_bytes（自 start 基线起的增量）、speed、停滞时长。"""

    def __init__(self, root: Path, interval: float = 0.6) -> None:
        self._root = root
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._baseline = 0
        self._current = 0
        self._speed = 0.0
        self._last_change = time.monotonic()

    def start(self) -> None:
        self._baseline = _dir_size(self._root)
        self._current = self._baseline
        self._last_change = time.monotonic()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="keeper-dlmon", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        prev, prev_t = self._current, time.monotonic()
        while not self._stop.wait(self._interval):
            size = _dir_size(self._root)
            now = time.monotonic()
            dt = now - prev_t
            delta = size - prev
            self._speed = delta / dt if dt > 0 else 0.0
            if delta > 0:
                self._last_change = now
            self._current = size
            prev, prev_t = size, now

    @property
    def downloaded_bytes(self) -> int:
        return max(0, self._current - self._baseline)

    @property
    def speed_bytes_per_s(self) -> float:
        return max(0.0, self._speed)

    def stalled_seconds(self) -> float:
        """距上次字节增长的秒数——长时间无增长即疑似下载卡死。"""
        return time.monotonic() - self._last_change
