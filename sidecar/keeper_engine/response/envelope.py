"""统一响应包装的 web 层接线：成功自动包 ApiResponse，异常统一翻译成 HTTP 200 + ApiResponse。

全局规范：前后端交互恒返回 HTTP 200，业务成败由响应体 `code` 表达（见 response/api_response.py）。
- EnvelopeRoute：作为各 APIRouter 的 route_class，把 controller 的 JSON 返回值就地包成
  `{code:0, data:<原返回>, msg:null}`；非 JSON（如 /thumbnail 的 image/jpeg）原样放行。
  controller 代码无需改动，继续 `return 业务对象`。
- install_exception_handlers：把领域异常按 BizCode 统一构造为 ApiResponse 并以 HTTP 200 返回。
  例外：/thumbnail 解码失败抛的 HTTPException(404) 仍走 Starlette 默认处理器（二进制端点豁免）。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute

from ..enumeration.biz_code import BizCode
from ..exception.errors import (
    BizException,
    DependencyMissing,
    ScorerError,
    VisionUnavailable,
)
from .api_response import ApiResponse


def _envelope(code: int, data: Any, msg: str | None) -> JSONResponse:
    """构造统一结构体的 JSONResponse（恒 HTTP 200）。以 ApiResponse 为唯一结构来源。"""
    return JSONResponse(status_code=200, content=ApiResponse(code=code, data=data, msg=msg).model_dump())


class EnvelopeRoute(APIRoute):
    """把成功的 JSON 响应自动包成 ApiResponse；二进制等非 JSON 响应原样放行。"""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            # 端点内抛出的异常向上冒泡到 app 的异常处理器统一包装，这里只处理成功响应。
            response = await original(request)
            content_type = response.headers.get("content-type", "")
            # 只包 JSON；/thumbnail 的 image/jpeg 等二进制原样返回。
            if content_type.startswith("application/json") and hasattr(response, "body"):
                data = json.loads(response.body)
                return _envelope(BizCode.SUCCESS.code, data, None)
            return response

        return handler


def install_exception_handlers(app: FastAPI) -> None:
    """注册领域异常 → ApiResponse 的统一映射（一律 HTTP 200）。"""

    @app.exception_handler(BizException)
    async def _biz(_: Request, exc: BizException) -> JSONResponse:
        return _envelope(exc.biz.code, None, exc.msg)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 把 pydantic 校验错误压成一句可读信息放进 msg。
        return _envelope(BizCode.VALIDATION_ERROR.code, None, str(exc.errors()))

    @app.exception_handler(VisionUnavailable)
    async def _vision(_: Request, exc: VisionUnavailable) -> JSONResponse:
        # DependencyMissing 是 VisionUnavailable 子类：缺依赖不可重试，其余可重试。
        biz = BizCode.MODEL_DEPENDENCY_MISSING if isinstance(exc, DependencyMissing) else BizCode.MODEL_NOT_READY
        return _envelope(biz.code, None, f"{biz.message}：{exc}")

    @app.exception_handler(ScorerError)
    async def _scorer(_: Request, exc: ScorerError) -> JSONResponse:
        return _envelope(BizCode.SCORER_FAILED.code, None, f"{BizCode.SCORER_FAILED.message}：{exc}")

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        # 兜底：未预期异常一律 INTERNAL_ERROR，不泄漏堆栈细节给前端。
        return _envelope(BizCode.INTERNAL_ERROR.code, None, f"{BizCode.INTERNAL_ERROR.message}：{exc}")
