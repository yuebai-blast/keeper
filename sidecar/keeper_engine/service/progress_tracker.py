"""评测实时进度的内存只读侧信道：按 project_id 存一份当前进度。

全局同一时刻只有一个评测在跑（前端 store.busy 串行化），故按 project_id 一份足够。
线程安全：评测跑在 FastAPI 线程池、轮询 GET 在另一线程读、tick 在层①/层②的
ThreadPoolExecutor 多线程里被调用，故读写全程加锁；get 返回副本避免读到半更新态。
进度纯瞬时、不持久化（DB 已落层①结果）。
"""

from __future__ import annotations

import threading

from ..enumeration.assess_phase import AssessPhase
from ..response.project_response import AssessProgress


class ProgressTracker:
    """按 project_id 维护一份评测进度，供进度端点轮询读取。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_project: dict[int, AssessProgress] = {}

    def begin(
        self, project_id: int, group_key: str, group_index: int,
        group_count: int, phase: AssessPhase, total: int,
    ) -> None:
        """开一组的某阶段（done 归零）。"""
        with self._lock:
            self._by_project[project_id] = AssessProgress(
                phase=phase.value, done=0, total=total,
                group_index=group_index, group_count=group_count, group_key=group_key,
            )

    def phase(self, project_id: int, phase: AssessPhase, total: int) -> None:
        """同一组内切阶段（层①→层②），done 归零；无记录则忽略。"""
        with self._lock:
            p = self._by_project.get(project_id)
            if p is not None:
                p.phase = phase.value
                p.done = 0
                p.total = total

    def tick(self, project_id: int) -> None:
        """当前阶段已处理 +1；无记录则忽略。"""
        with self._lock:
            p = self._by_project.get(project_id)
            if p is not None:
                p.done += 1

    def done(self, project_id: int) -> None:
        """标记本轮结束；无记录则忽略。"""
        with self._lock:
            p = self._by_project.get(project_id)
            if p is not None:
                p.phase = AssessPhase.DONE.value

    def get(self, project_id: int) -> AssessProgress:
        """读当前进度副本；无记录返回 IDLE 默认。"""
        with self._lock:
            p = self._by_project.get(project_id)
            if p is None:
                return AssessProgress(
                    phase=AssessPhase.IDLE.value, done=0, total=0,
                    group_index=0, group_count=0, group_key=None,
                )
            return p.model_copy()
