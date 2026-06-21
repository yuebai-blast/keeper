"""缩略图端点：sidecar 解码（含 RAW/HEIC）并缩放，带磁盘缓存。"""

from __future__ import annotations

from pathlib import Path

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..config.settings import Settings
from ..container import Container
from ..response.envelope import EnvelopeRoute
from ..util import imaging

router = APIRouter(route_class=EnvelopeRoute)


@router.get("/thumbnail")
@inject
def thumbnail(
    path: str = Query(..., description="照片绝对路径"),
    size: int = Query(256, ge=32, le=2048, description="缩略图长边像素（放大预览用更大尺寸）"),
    settings: Settings = Depends(Provide[Container.settings]),
) -> Response:
    """生成并返回一张照片的缩略图 JPEG（桌面端画廊用）。

    sidecar 能解 RAW/HEIC 并缩放（webview 做不到）；只走 localhost，照片不出本地。
    缓存就近落在原图同目录的 `.thumbnails/`（随 workspace 一起清理）。读图失败 → 404。
    安全：仅放行 workspace 内路径（前端缩略图均为 workspace 副本），越权一律 404（不区分越权/不存在）。
    """
    canonical = Path(path).resolve()
    if not canonical.is_relative_to(settings.workspace_dir.resolve()):
        raise HTTPException(status_code=404, detail="not found")
    try:
        jpeg = imaging.cached_thumbnail(str(canonical), max_side=size)
    except Exception as e:  # noqa: BLE001 —— 路径无效/损坏当 404
        raise HTTPException(status_code=404, detail=f"{type(e).__name__}: {e}") from e
    return Response(content=jpeg, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})
