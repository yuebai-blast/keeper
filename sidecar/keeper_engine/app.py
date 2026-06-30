"""FastAPI app 工厂：建容器 → wire（由容器 wiring_config 自动完成）→ CORS → lifespan → 注册路由。

只监听 127.0.0.1，由 Tauri 壳经 localhost 调用。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config.settings import Settings
from .container import Container
from .controller import (
    assess_controller,
    group_controller,
    health_controller,
    project_controller,
    score_controller,
    settings_controller,
    thumbnail_controller,
)
from .middleware.auth import AuthMiddleware
from .response.envelope import install_exception_handlers


def _setup_logging(settings: Settings) -> None:
    """把 keeper_engine 的日志同时写到 stderr 与 {home}/sidecar.log（滚动）。

    打包（实机）态下 sidecar 的 stderr 不可见，排错全靠这个文件——尤其是各 service 里
    `logger.exception(...)` 打出的完整 traceback。幂等：重复调用不会叠加 handler。
    """
    root = logging.getLogger("keeper_engine")
    root.setLevel(logging.INFO)
    if any(getattr(h, "_keeper_log", False) for h in root.handlers):
        return  # 已装过（测试里可能多次 create_app），不重复加
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    stream._keeper_log = True  # type: ignore[attr-defined]
    root.addHandler(stream)

    try:
        settings.home.mkdir(parents=True, exist_ok=True)
        file = RotatingFileHandler(
            settings.log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file.setFormatter(fmt)
        file._keeper_log = True  # type: ignore[attr-defined]
        root.addHandler(file)
    except OSError:
        pass  # 日志文件不可写不致命，至少还有 stderr


def create_app() -> FastAPI:
    """构建并返回 FastAPI 应用（容器挂在 app.container 上，便于测试 override）。"""
    container = Container()
    settings = container.settings()
    _setup_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动自检日志（非敏感）：确认 Tauri 注入的 env 是否到位。
        logging.getLogger("keeper_engine.app").info(
            "[boot] home=%s models_dir=%s log=%s auth=%s",
            settings.home, settings.models_dir, settings.log_path,
            "on" if settings.auth_token else "off",
        )
        # 建全部 sqlite 表（模型状态 + 项目工作流），幂等。
        container.database().create_all()
        # 不阻塞启动；启动后立刻可应答 /health。首次需下载则停在 awaiting_consent 等用户确认，
        # 否则后台预热（报 loading → ready）。
        container.readiness_service().boot()
        yield

    app = FastAPI(title="Keeper Engine", version=__version__, lifespan=lifespan)
    app.container = container

    # 统一响应包装：领域异常 → HTTP 200 + ApiResponse（成功响应的自动包装在各 EnvelopeRoute）。
    install_exception_handlers(app)

    # 鉴权放在 CORS 之前注册 → CORS 处于最外层，能给 401 响应补上 CORS 头供前端读取。
    # token 为空（dev）时中间件整体放行。
    app.add_middleware(AuthMiddleware, token=settings.auth_token)

    # 桌面端 Tauri webview 经浏览器上下文跨源调用本服务，需放行本地来源。
    # 服务只绑 127.0.0.1（仅本机可达），故放行 localhost / tauri 来源是安全的。
    app.add_middleware(
        CORSMiddleware,  # type: ignore[arg-type]  # Starlette ParamSpec 签名导致 PyCharm 误报，运行无碍
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (
        health_controller,
        thumbnail_controller,
        group_controller,
        assess_controller,
        score_controller,
        project_controller,
        settings_controller,  # 仅自用版：商业版构建移除
    ):
        app.include_router(module.router)

    return app
