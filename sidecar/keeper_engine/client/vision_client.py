"""本地模型客户端——启动期一次性 eager 加载全部模型，运行时直接用已加载实例。

含：
  - DINOv2（语义特征）：分组用，embed_image 出归一向量做视觉相似聚类。
    选 v2 不选 v3：v2 是 Apache-2.0、HF 免门禁、自动下载即用、商用干净；v3 是 gated + 自定义许可。
  - InsightFace：分组用「检测 + 识别」实例取人脸身份；层① 用「检测 + 68 关键点」算锐度/闭眼。
    ⚠️ 识别模型（ArcFace，buffalo_l）仅限非商用研究——付费产品商用前需替换或单独授权。
  - pyiqa：TOPIQ-nr-face（有脸时评人脸质量）/ TOPIQ-nr（无脸时评整图）+ CLIP-IQA+（美学）。
    CLIP-IQA 的 CLIP backbone 经 pyiqa 自带下载落到 torch.hub 目录（即 models_dir 内）。

设计（改造后）：
  - 模型在启动期由 ReadinessService 调 `load_all()` 一次性加载到具名属性（单线程，无需锁）。
  - 运行时方法直接用属性；属性为空（未加载/已失效）即抛 VisionUnavailable，由上层进修复页重载。
  - 缺依赖抛 DependencyMissing（致命，不可重试）；权重下载/加载失败抛 VisionUnavailable（可重试）。
  - 模型缓存统一固定到 settings.models_dir（HF / torch / insightface / clip），可复现、便于监控与清理。
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from ..config.settings import Settings
from ..exception.errors import DependencyMissing, VisionUnavailable
from ..util import signals

logger = logging.getLogger("keeper_engine.client.vision")

PYIQA_MAX_SIDE = 1024  # pyiqa 输入长边上限，平衡精度与开销

# 层① 用检测 + 68 关键点（算锐度/闭眼）；分组用检测 + 识别（ArcFace，取人脸身份）。
DETECT_MODULES = ("detection", "landmark_3d_68")
GROUPING_FACE_MODULES = ("detection", "recognition")
GROUPING_FACE_DET_MIN = 0.5     # 人脸最低检测置信度（低于此当背景误检，不取其身份）
GROUPING_FACE_MIN_AREA = 0.005  # 人脸面积占比下限（过滤背景路人小脸，只留画面里的主要人物）

# 各模块首次下载占用的磁盘大小（MB），用于估算整体下载百分比 + 首次下载前告知用户体量。
# 数值按真实完整下载后的 ~/.keeper/models 实测标定（du 各子树），总量约 1.6 GB；
# 注意 InsightFace 会同时留下 buffalo_l.zip 与解包后的权重（约各占一半），故 face_group 偏大。
MODULE_EXPECTED_MB = {
    "dino": 90,          # facebook/dinov2-small 权重
    "face_group": 615,   # buffalo_l：下载的 .zip + 解包后的 onnx 权重一并占盘
    "face_detect": 0,    # 与 face_group 复用同一 buffalo_l 包，不重复计
    "topiq": 290,        # TOPIQ-nr：timm resnet50 backbone + koniq 权重
    "topiq_face": 385,   # TOPIQ-nr-face：人脸质量权重 + 人脸检测/解析预处理权重
    "clipiqa": 256,      # CLIP-IQA+：CLIP RN50 backbone + 学到的提示词
}


class VisionClient:
    """本地推理模型的统一入口；启动 eager 加载到具名属性，运行时直接引用。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._storage_ready = False
        # 具名模型属性（启动加载，运行时只读）
        self._dino = None          # (processor, model, device)
        self._face_group = None    # InsightFace app（检测 + 识别）
        self._face_detect = None   # InsightFace app（检测 + 关键点）
        self._topiq = None
        self._topiq_face = None
        self._clipiqa = None
        # pyiqa 模型自身非线程安全（topiq_nr-face 内部 facexlib FaceRestoreHelper 把每次调用的
        # 中间结果挂在实例属性上）。层① 用线程池并发逐张评分，同一模型的并发调用会竞争这份共享
        # 可变状态导致崩溃，故每个 pyiqa 模型配一把锁，调用时串行化（不同模型间仍可并行）。
        self._pyiqa_locks: dict[int, threading.Lock] = {}
        self._pyiqa_locks_guard = threading.Lock()

    # ── 启动期加载 ────────────────────────────────────────────────────────

    def load_all(self, report: Callable[[int, int, str, str], None] | None = None) -> None:
        """一次性加载全部模型（单线程，由就绪态预热调用）。

        report(序号1based, 总数, 模块key, 模块名)：每加载一个模块前回调，供报进度。
        各 _load_* 幂等：已加载的快速返回（重试时只补加载失败的）。失败按异常类型上抛。
        """
        self._ensure_storage_configured()
        steps: list[tuple[str, str, Callable[[], None]]] = [
            ("dino", "图像语义模型", self._load_dino),
            ("face_group", "人脸模型 · 分组", self._load_face_group),
            ("face_detect", "人脸模型 · 评分", self._load_face_detect),
            ("topiq", "画质评分模型", self._load_topiq),
            ("topiq_face", "人脸画质模型", self._load_topiq_face),
            ("clipiqa", "美学评分模型", self._load_clipiqa),
        ]
        total = len(steps)
        for i, (key, label, load) in enumerate(steps):
            if report is not None:
                report(i + 1, total, key, label)
            load()

    def cleanup_partials(self) -> None:
        """删除模型缓存目录下残留的 *.partial（中断下载的废弃半成品），以便重试时干净重下。"""
        root = self._settings.models_dir
        if not root.exists():
            return
        for p in root.rglob("*.partial"):
            try:
                p.unlink()
            except OSError:
                pass

    # ── 存储 / 设备 ────────────────────────────────────────────────────────

    def _models_root(self) -> Path:
        root = self._settings.models_dir
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _ensure_storage_configured(self) -> None:
        """把各框架的缓存目录指到 Keeper 自己的目录。在加载任何模型前调用一次即可。"""
        if self._storage_ready:
            return
        import os

        root = self._models_root()
        hf_home = root / "huggingface"
        hf_hub = hf_home / "hub"
        torch_home = root / "torch"
        for p in (hf_home, hf_hub, torch_home, root / "insightface"):
            p.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", str(hf_home))
        os.environ.setdefault("HF_HUB_CACHE", str(hf_hub))
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_hub))
        os.environ.setdefault("TORCH_HOME", str(torch_home))
        try:
            import torch.hub

            # pyiqa 的 CLIP backbone 下到 get_dir()/clip，即此目录下——一并落进 models_dir。
            torch.hub.set_dir(str(torch_home / "hub"))
        except Exception:
            pass
        self._storage_ready = True
        logger.info("vision: 模型缓存目录固定到 %s", root)

    def _torch_device(self):
        import torch

        forced = self._settings.device
        if forced == "cuda":
            if not torch.cuda.is_available():
                raise VisionUnavailable("KEEPER_DEVICE=cuda，但 torch 不支持 CUDA")
            return torch.device("cuda")
        if forced == "cpu" or not forced:
            if forced == "" and torch.cuda.is_available():
                return torch.device("cuda")
            return torch.device("cpu")
        return torch.device("cpu")

    # ── 各模型加载（幂等）────────────────────────────────────────────────

    def _load_dino(self) -> None:
        if self._dino is not None:
            return
        try:
            import torch  # noqa: F401
            from transformers import AutoImageProcessor, AutoModel
        except ImportError as e:
            raise DependencyMissing(f"DINOv2 依赖缺失：{e}（需 transformers + torch）") from e
        model_id = self._settings.dino_model
        dev = self._torch_device()
        logger.info("vision: 加载 DINOv2 %s（device=%s）…", model_id, dev.type)

        def _load(local_only: bool):
            proc = AutoImageProcessor.from_pretrained(model_id, local_files_only=local_only)
            model = AutoModel.from_pretrained(model_id, local_files_only=local_only)
            return proc, model

        try:
            # local-first：已缓存就离线加载，绝不因网络抖动失败。transformers 5.x 每次
            # from_pretrained 都会联网向 HF Hub 校验，连接/DNS 失败时它不回退本地缓存而是直接抛
            # 「Can't load image processor」——本地优先产品不能因此启动不了。仅首次未缓存才联网下载。
            try:
                proc, model = _load(local_only=True)
            except OSError:
                logger.info("vision: DINOv2 未命中本地缓存，联网下载 %s…", model_id)
                proc, model = _load(local_only=False)
            model = model.to(dev).eval()
        except Exception as e:
            raise VisionUnavailable(f"DINOv2 加载失败：{e}") from e
        self._dino = (proc, model, dev)

    def _onnx_providers(self) -> tuple[list[str], int]:
        import onnxruntime as ort

        forced = self._settings.device
        available = list(ort.get_available_providers())
        if forced == "cuda" or (forced == "" and "CUDAExecutionProvider" in available):
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"], 0
        return ["CPUExecutionProvider"], -1

    def _load_face(self, modules: tuple[str, ...]):
        try:
            from insightface.app import FaceAnalysis
        except ImportError as e:
            raise DependencyMissing(f"InsightFace 依赖缺失：{e}（需 insightface + onnxruntime）") from e
        providers, ctx_id = self._onnx_providers()
        pack = self._settings.face_pack
        root = str(self._models_root() / "insightface")
        logger.info("vision: 加载 InsightFace %s modules=%s…", pack, modules)
        try:
            app = FaceAnalysis(name=pack, root=root, providers=providers, allowed_modules=list(modules))
            app.prepare(ctx_id=ctx_id, det_size=(640, 640))
        except Exception as e:
            raise VisionUnavailable(f"InsightFace 加载失败：{e}") from e
        return app

    def _load_face_group(self) -> None:
        if self._face_group is None:
            self._face_group = self._load_face(GROUPING_FACE_MODULES)

    def _load_face_detect(self) -> None:
        if self._face_detect is None:
            self._face_detect = self._load_face(DETECT_MODULES)

    def _create_pyiqa(self, metric_name: str, label: str):
        try:
            import pyiqa  # noqa: F401
            import torch  # noqa: F401
        except ImportError as e:
            raise DependencyMissing(f"{label} 依赖缺失：{e}（需 pyiqa + timm）") from e
        dev = self._torch_device()
        logger.info("vision: 加载 %s（%s, device=%s）…", label, metric_name, dev.type)
        try:
            return pyiqa.create_metric(metric_name, device=dev, as_loss=False)
        except Exception as e:
            raise VisionUnavailable(f"{label} 加载失败：{e}") from e

    def _load_topiq(self) -> None:
        if self._topiq is None:
            self._topiq = self._create_pyiqa("topiq_nr", "TOPIQ-nr")

    def _load_topiq_face(self) -> None:
        if self._topiq_face is None:
            self._topiq_face = self._create_pyiqa("topiq_nr-face", "TOPIQ-nr-face")

    def _load_clipiqa(self) -> None:
        if self._clipiqa is None:
            self._clipiqa = self._create_pyiqa("clipiqa+", "CLIP-IQA+")

    # ── 运行时推理（直接用已加载实例）──────────────────────────────────────

    def embed_image(self, img: Image.Image) -> np.ndarray:
        """返回一张图的 DINOv2 语义特征（L2 归一化的 float32 向量）。"""
        if self._dino is None:
            raise VisionUnavailable("图像语义模型未加载")
        import torch

        proc, model, dev = self._dino
        inputs = proc(images=img.convert("RGB"), return_tensors="pt").to(dev)
        with torch.no_grad():
            out = model(**inputs)
        pooled = getattr(out, "pooler_output", None)
        feat = pooled[0] if pooled is not None else out.last_hidden_state[0, 0]
        v = feat.detach().cpu().numpy().astype(np.float32)
        n = float(np.linalg.norm(v))
        return v / n if n >= 1e-8 else v

    @staticmethod
    def _resize_for_pyiqa(img: Image.Image) -> Image.Image:
        img = img.convert("RGB")
        if max(img.size) <= PYIQA_MAX_SIDE:
            return img
        out = img.copy()
        out.thumbnail((PYIQA_MAX_SIDE, PYIQA_MAX_SIDE), Image.Resampling.LANCZOS)
        return out

    def _pyiqa_lock(self, model) -> threading.Lock:
        """取某个 pyiqa 模型对应的锁（按实例惰性建一把），用于并发下串行化其推理。"""
        with self._pyiqa_locks_guard:
            return self._pyiqa_locks.setdefault(id(model), threading.Lock())

    def _run_pyiqa(self, model, label: str, img: Image.Image) -> float:
        if model is None:
            raise VisionUnavailable(f"{label}未加载")
        import torch

        # 同一 pyiqa 模型的调用必须串行：其内部（如 facexlib face_helper）有非线程安全的共享状态。
        with self._pyiqa_lock(model), torch.no_grad():
            score = model(self._resize_for_pyiqa(img))
        return float(score.item() if hasattr(score, "item") else score)

    def topiq_score(self, img: Image.Image) -> float:
        """TOPIQ-nr 通用技术质量分（约 0–1，越高越好）。用于无脸照（风景/空镜）。"""
        return self._run_pyiqa(self._topiq, "画质评分模型", img)

    def topiq_face_score(self, face_img: Image.Image) -> float:
        """TOPIQ-nr-face 人脸质量分（约 0–1）。输入应为人脸裁剪，人像选片更贴合。"""
        return self._run_pyiqa(self._topiq_face, "人脸画质模型", face_img)

    def clipiqa_plus_score(self, img: Image.Image) -> float:
        """CLIP-IQA+ 美学分（约 0–1，越高越好）。"""
        return self._run_pyiqa(self._clipiqa, "美学评分模型", img)

    def extract_faces(
        self, img: Image.Image, max_dim: int = 1024, modules: tuple[str, ...] = DETECT_MODULES
    ) -> list[dict]:
        """返回每张脸的 {bbox, embedding(仅识别模块有值), kps, det_score, landmark_2d_68}。

        按 modules 选用已加载的 InsightFace 实例（分组用识别实例、层①用关键点实例）。
        对应实例未加载即抛 VisionUnavailable。无脸返回 []。
        """
        app = self._face_group if tuple(modules) == GROUPING_FACE_MODULES else self._face_detect
        if app is None:
            raise VisionUnavailable("人脸模型未加载")
        rgb = img.convert("RGB")
        w, h = rgb.size
        scale = 1.0
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            rgb = rgb.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        arr = np.array(rgb)[:, :, ::-1]  # RGB → BGR
        faces = app.get(arr)
        if not faces:
            return []

        inv = 1.0 / scale
        out: list[dict] = []
        for face in faces:
            embedding = None
            emb = getattr(face, "embedding", None)
            if emb is not None:
                emb = emb.astype(np.float32)
                n = float(np.linalg.norm(emb))
                if n >= 1e-8:
                    embedding = emb / n
            bbox = tuple(int(c * inv) for c in face.bbox.astype(int))
            kps = (face.kps * inv).astype(np.float32) if face.kps is not None else None
            lm68 = None
            lm = getattr(face, "landmark_3d_68", None)
            if lm is not None:
                lm68 = (lm[:, :2] * inv).astype(np.float32)
            out.append({
                "bbox": bbox,
                "embedding": embedding,
                "kps": kps,
                "det_score": float(face.det_score),
                "landmark_2d_68": lm68,
            })
        return out

    def face_embeddings(self, img: Image.Image) -> np.ndarray | None:
        """取一张照片中所有合格人脸的身份 embedding，堆叠成 (k×512) 已归一矩阵；无合格脸返回 None。"""
        faces = self.extract_faces(img, modules=GROUPING_FACE_MODULES)
        w, h = img.size
        area = float(w * h) or 1.0
        embs = []
        for f in faces:
            if f["det_score"] < GROUPING_FACE_DET_MIN or f.get("embedding") is None:
                continue
            x1, y1, x2, y2 = f["bbox"]
            if max(0.0, x2 - x1) * max(0.0, y2 - y1) / area < GROUPING_FACE_MIN_AREA:
                continue
            embs.append(f["embedding"])
        return np.stack(embs).astype(np.float32) if embs else None

    @staticmethod
    def eye_open_score(face: dict) -> float | None:
        """68 关键点估算睁眼程度（EAR 均值）。睁眼 0.25+，闭眼 <0.2。点序异常时返回 None。"""
        lm68 = face.get("landmark_2d_68")
        if lm68 is None or len(lm68) < 48:
            return None
        lm68 = np.asarray(lm68, dtype=np.float32)
        val = (signals.ear(lm68[36:42]) + signals.ear(lm68[42:48])) / 2.0
        if val > 0.55:
            return None
        return round(val, 4)
