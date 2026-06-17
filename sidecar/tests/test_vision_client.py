"""VisionClient 线程安全测试——pyiqa 推理在并发线程池下不得因共享可变状态而损坏。

背景（回归）：pyiqa 的 topiq_nr-face 内部用 facexlib 的 FaceRestoreHelper，后者把每次调用的
中间结果挂在实例属性（self.det_faces 等）上，是**有状态、非线程安全**的。层① 评分由
AssessService 用 ThreadPoolExecutor 并发逐张跑，两张「有脸」照片并发调用 topiq_face_score 时
会竞争同一个 face_helper，导致其中一张抛 `AttributeError: 'numpy.ndarray' object has no
attribute 'append'` 而被吞进 errors——表现为「三张图固定只出两张结果」。

本测试用一个模拟「并发进入即损坏」的假 pyiqa 模型，验证 _run_pyiqa 已对同一模型串行化。
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from keeper_engine.client.vision_client import VisionClient
from keeper_engine.config.settings import Settings


class _StatefulMetric:
    """模拟 facexlib face_helper：并发进入即视为共享状态被破坏，抛错。"""

    def __init__(self) -> None:
        self._inside = False
        self._lock = threading.Lock()
        self.max_concurrent = 0
        self.calls = 0

    def __call__(self, _img):
        with self._lock:
            if self._inside:
                # 与真实 facexlib 一样：并发改写共享中间状态 → 崩
                raise AttributeError("'numpy.ndarray' object has no attribute 'append'")
            self._inside = True
            self.max_concurrent = 1
        try:
            time.sleep(0.02)  # 拉长临界区，逼出竞争窗口
            self.calls += 1
            return 0.5
        finally:
            with self._lock:
                self._inside = False


def test_pyiqa_face_score_is_serialized_under_concurrency():
    vc = VisionClient(Settings())
    metric = _StatefulMetric()
    vc._topiq_face = metric  # 注入假模型，绕过真实权重加载

    img = Image.new("RGB", (256, 256))

    def work(_i):
        return vc.topiq_face_score(img)

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(work, range(8)))

    assert results == [0.5] * 8
    assert metric.calls == 8
    assert metric.max_concurrent == 1  # 同一 pyiqa 模型的调用必须串行
