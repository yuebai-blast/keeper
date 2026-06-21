"""值对象：层② 大模型对单张候选的打分结果。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..enumeration.edit_verdict import EditVerdict


class Score(BaseModel):
    """层② 大模型对单张候选的 0–100 审美打分 + 可解释理由 + 具体瑕疵 + 修图建议。"""

    path: str
    score: float = Field(ge=0, le=100)
    reason: str = Field(default="", description="中文短理由（打这个分的主要依据）")
    flaws: str = Field(default="", description="模型列出的具体瑕疵，逗号分隔；无则空")
    editable: str = Field(
        default=EditVerdict.READY.value,
        description="修图判定：ready/worth_editing/not_worth/unfixable",
    )
    edit_advice: str = Field(
        default="",
        description="修图建议：能修怎么修 / 修不了或不划算的原因，≤40 字",
    )
    is_junk: bool = Field(
        default=False,
        description="层②判定是否为非摄影杂图/垃圾图（截图/地图/纯色/聊天记录等）",
    )
