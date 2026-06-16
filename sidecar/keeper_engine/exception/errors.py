"""领域异常集中定义。

不静默降级（CLAUDE.md）：本地模型依赖缺失/加载失败、层② 打分不可用，一律抛出对应异常，
绝不悄悄退化。各 client/service 抛这里的异常，由 app 的异常处理器统一翻译成 HTTP 200 + ApiResponse。
"""

from __future__ import annotations

from ..enumeration.biz_code import BizCode


class BizException(RuntimeError):
    """业务异常：携带 BizCode（业务码 + 默认中文描述），由异常处理器包成 ApiResponse。

    service/controller 需要中断并返回业务错误时抛它（替代过去的 HTTPException）。
    `msg` 缺省用枚举默认描述，需要更具体上下文时显式传入。
    """

    def __init__(self, biz: BizCode, msg: str | None = None) -> None:
        self.biz = biz
        self.msg = msg or biz.message
        super().__init__(self.msg)


class VisionUnavailable(RuntimeError):
    """本地模型不可用（权重下载/加载失败）。通常可重试（网络等）。绝不静默降级，一律抛出。"""


class DependencyMissing(VisionUnavailable):
    """运行依赖缺失（Python 包未安装）——属于「不允许运行」，重试也无用，不可恢复。"""


class ScorerError(RuntimeError):
    """层② 打分不可用（缺 key / 网络 / 接口或解析错误）。不静默降级，一律抛出。"""
