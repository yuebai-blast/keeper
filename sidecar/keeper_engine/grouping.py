"""分组（漏斗前的第 0 步）：把相似连拍聚成「瞬间组」。

信号（详见 docs/product-flow.md）：
  - 语义相似：DINOv2 特征余弦相似度（视觉上是不是同一画面）。
  - 时间邻近：EXIF 拍摄时间，越近越可能是同一串连拍（指数衰减）。
  - 人脸聚类：本轮先不做——它需要 InsightFace 的 ArcFace 识别 embedding（非商用授权，
    见 vision.py 注释）。聚类逻辑留了口子，日后把人脸 ID 相似度并进 combined 即可。

综合相似度 = 语义余弦 × 时间衰减；距离 = 1 − 综合相似度；complete-linkage 层次聚类按阈值切。
阈值都是可调旋钮，集中在下方常量。
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Sequence

import numpy as np

from . import imaging, vision
from .models import Group

# ── 可调旋钮 ────────────────────────────────────────────────────────────────
GROUP_DISTANCE_THRESHOLD = 0.4   # 1 − 综合相似度；越小分得越细（同组要求越像）
TIME_TAU_SECONDS = 120.0         # 时间衰减常数：Δt = TAU 时时间因子衰减到 e⁻¹≈0.37
LINKAGE_METHOD = "complete"      # complete-linkage：组内任意两张都要够像，连拍组更紧


def embed_photo(path: str, companions: Sequence[str] = ()) -> tuple[np.ndarray, datetime | None]:
    """加载一张图，返回 (DINOv2 归一特征, 拍摄时间)。读图/推理失败抛异常。"""
    img = imaging.load_for_analysis(path, tuple(companions))
    return vision.embed_image(img), imaging.read_capture_time(img)


def group_photos(photo_paths: Sequence[str]) -> list[Group]:
    """对一批照片分组（便捷封装：逐张加载+embed，任一失败即抛）。

    需要逐张容错的场景（如 /group 端点）改用 embed_photo + cluster 自行收集错误。
    """
    embeddings, times = [], []
    for p in photo_paths:
        emb, t = embed_photo(p)
        embeddings.append(emb)
        times.append(t)
    return cluster(list(photo_paths), embeddings, times)


def cluster(
    paths: list[str], embeddings: Sequence[np.ndarray], times: Sequence[datetime | None]
) -> list[Group]:
    """把已算好的特征+时间聚成瞬间组（纯函数，不碰 IO/模型，便于单测）。

    embeddings 须为 L2 归一化向量（点积即余弦）。返回的 Group 按首次出现顺序编号 g1、g2…。
    """
    n = len(paths)
    if n == 0:
        return []
    if n == 1:
        return [Group(id="g1", photos=[paths[0]])]

    e = np.stack(embeddings).astype(np.float32)
    sem = np.clip(e @ e.T, -1.0, 1.0)  # 余弦相似度矩阵

    secs = np.array([t.timestamp() if t is not None else np.nan for t in times], dtype=np.float64)
    dt = np.abs(secs[:, None] - secs[None, :])
    time_factor = np.exp(-dt / TIME_TAU_SECONDS)
    time_factor[np.isnan(time_factor)] = 1.0  # 任一方无时间 → 不衰减，只靠语义

    dist = 1.0 - sem * time_factor
    np.fill_diagonal(dist, 0.0)
    dist = np.clip((dist + dist.T) / 2.0, 0.0, None)  # 对称化、非负

    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    z = linkage(squareform(dist, checks=False), method=LINKAGE_METHOD)
    labels = fcluster(z, t=GROUP_DISTANCE_THRESHOLD, criterion="distance")

    members: OrderedDict[int, list[int]] = OrderedDict()
    for idx, lab in enumerate(labels):
        members.setdefault(int(lab), []).append(idx)
    ordered = sorted(members.values(), key=lambda idxs: idxs[0])  # 按首次出现排序
    return [
        Group(id=f"g{k + 1}", photos=[paths[i] for i in idxs])
        for k, idxs in enumerate(ordered)
    ]
