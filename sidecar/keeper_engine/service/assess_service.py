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
