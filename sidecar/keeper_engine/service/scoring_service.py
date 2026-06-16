"""层② 大模型打分端点编排：对层① survivors 生成低清预览上云打分，再按保底数 N 组装 PK 候选集。

照片不出本地：只上传 make_preview 生成的低清 JPEG。
单张读图失败记入 errors；大模型不可用（缺 key / 网络）整体抛 SCORER_FAILED——不静默降级。
本端点只用 imaging + 远程 Ark，不依赖本地模型预热，故不设就绪门禁。
"""

from __future__ import annotations

from ..client.scorer import Preview, Scorer
from ..config.settings import Settings
from ..request.score_request import ScoreRequest
from ..response.common import PhotoError
from ..response.score_response import ScoreResponse
from ..util import imaging
from .params_service import ParamsService
from .ranking_service import RankingService


class ScoringService:
    """/score 编排：生成低清预览 → Scorer 打分 → 漏斗 + PK 组装。"""

    def __init__(
        self,
        scorer: Scorer,
        params: ParamsService,
        ranking: RankingService,
        settings: Settings,
    ) -> None:
        self._scorer = scorer
        self._params = params
        self._ranking = ranking
        self._settings = settings

    def score(self, req: ScoreRequest) -> ScoreResponse:
        previews: list[Preview] = []
        errors: list[PhotoError] = []
        for p in req.photos:
            try:
                img = imaging.load_for_analysis(p)
                previews.append(Preview(path=p, jpeg=imaging.make_preview(img)))
            except Exception as e:  # noqa: BLE001 —— 单张数据错误上报而非静默跳过
                errors.append(PhotoError(path=p, error=f"{type(e).__name__}: {e}"))

        model = req.model or self._settings.ark_model
        # 大模型不可用抛 ScorerError，由 app 异常处理器统一映射为 SCORER_FAILED（HTTP 200 + ApiResponse）。
        scores = self._scorer.score(previews, model)

        n = self._params.compute_n(req.group_total)
        pk_set = self._ranking.assemble_pk_set(req.group_id, scores, n)
        return ScoreResponse(group_id=req.group_id, scores=scores, pk=pk_set.entries, n=n, errors=errors)
