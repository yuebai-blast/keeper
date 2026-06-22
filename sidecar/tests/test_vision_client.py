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
import types
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


class _FakeDinoModel:
    """假 DINOv2 模型：仅需支持 .to(dev).eval() 链式调用。"""

    def to(self, _dev):
        return self

    def eval(self):
        return self


def _patch_transformers(monkeypatch, *, local_cached: bool):
    """用假 transformers 模块替换 sys.modules，记录每次 from_pretrained 的 kwargs。

    （不能用 monkeypatch.setattr 改 transformers 的属性——它是 _LazyModule，逐个 setattr 会被
    其惰性 __getattr__ 机制重置而失效；故整模块替换。）

    local_cached=True：本地已缓存——local_files_only=True 离线加载成功；
    local_cached=False：未缓存——local_files_only=True 抛 OSError（模拟 transformers 网络不可达
                        / 找不到缓存），只有允许联网（local_files_only=False）才成功。
    返回记录列表 calls，元素为 (kind, kwargs)。
    """
    import sys

    calls: list[tuple[str, dict]] = []

    def make(kind, result):
        def from_pretrained(_model_id, **kw):
            calls.append((kind, kw))
            if kw.get("local_files_only") and not local_cached:
                # 复刻 transformers 在网络不可达 / 未缓存时抛的错
                raise OSError(f"Can't load {kind} for 'facebook/dinov2-small'")
            return result

        return types.SimpleNamespace(from_pretrained=from_pretrained)

    fake = types.ModuleType("transformers")
    fake.AutoImageProcessor = make("proc", object())
    fake.AutoModel = make("model", _FakeDinoModel())
    monkeypatch.setitem(sys.modules, "transformers", fake)
    return calls


def test_load_dino_loads_from_cache_without_network(monkeypatch):
    """回归：模型已缓存时加载必须 local-first，绝不依赖网络。

    transformers 5.x 每次 from_pretrained 都会联网向 HF Hub 校验；网络不可达（连接/DNS 失败，
    区别于会自动回退缓存的 HTTP 错误）时它不回退本地缓存，直接抛
    'Can't load image processor for facebook/dinov2-small' → VisionUnavailable，
    用户即便已下载好模型也无法启动。修复后 _load_dino 先以 local_files_only=True 离线加载缓存。
    """
    calls = _patch_transformers(monkeypatch, local_cached=True)
    vc = VisionClient(Settings())
    vc._load_dino()

    assert vc._dino is not None
    # 首次尝试必须是离线加载（local_files_only=True），不触网
    assert calls, "未调用 from_pretrained"
    assert all(kw.get("local_files_only") is True for _, kw in calls), (
        f"已缓存场景下加载不应联网，期望全部 local_files_only=True，实际：{calls}"
    )


def test_load_dino_falls_back_to_download_when_not_cached(monkeypatch):
    """首次运行未缓存时，离线加载失败后应回退联网下载（保留首次拉取能力）。"""
    calls = _patch_transformers(monkeypatch, local_cached=False)
    vc = VisionClient(Settings())
    vc._load_dino()

    assert vc._dino is not None
    kinds_flags = [(kind, kw.get("local_files_only")) for kind, kw in calls]
    # 先离线尝试（True）失败，再联网下载（False）
    assert ("proc", True) in kinds_flags
    assert any(flag is not True for _, flag in kinds_flags), (
        f"未缓存时应回退联网下载，实际：{kinds_flags}"
    )


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
