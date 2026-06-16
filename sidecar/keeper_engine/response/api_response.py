"""统一响应包装 ApiResponse（全局规范：前后端交互恒 HTTP 200，业务结果由 code 表达）。

结构固定三字段：`code`（0=成功，非 0 见 BizCode）、`data`（业务数据）、`msg`（描述/错误信息）。
桌面端 ↔ sidecar 的所有 JSON 端点返回值都被自动包成本结构（见 web/envelope.EnvelopeRoute），
异常由 app 的异常处理器统一构造为本结构。`/thumbnail` 因返回二进制图片豁免，不走本包装。
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

from ..enumeration.biz_code import BizCode

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一返回结构体。成功用 success()，失败用 fail()。"""

    code: int  # 业务码：0=成功，非 0 见 BizCode
    data: T | None = None  # 业务数据（成功时有值，失败通常为 None）
    msg: str | None = None  # 描述/错误信息（失败时给可读信息，成功可为 None）

    @classmethod
    def success(cls, data: T | None = None) -> "ApiResponse[T]":
        """成功响应（code=0）。"""
        return cls(code=BizCode.SUCCESS.code, data=data, msg=None)

    @classmethod
    def fail(cls, biz: BizCode, msg: str | None = None) -> "ApiResponse[T]":
        """失败响应：按 BizCode 取 code，msg 缺省用枚举默认中文描述。"""
        return cls(code=biz.code, data=None, msg=msg or biz.message)
