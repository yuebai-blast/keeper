"""项目工作流端点：新建/预览、分组、评测、裁决、PK、确认、完成。

只接线（解析请求 → 调 service → 返回），业务在 ProjectService / PkService。
就绪/大模型门禁由所复用的引擎 service 抛 HTTPException（503/502），这里不重复判断。
"""

from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from ..container import Container
from ..request.project_request import (
    PkChooseRequest,
    PkStartRequest,
    ProjectCreateRequest,
    ProjectPreviewRequest,
    SelectionUpdateRequest,
)
from ..response.project_response import (
    CompleteResponse,
    GroupDetailResponse,
    PkView,
    ProjectDetailResponse,
    ProjectPreviewResponse,
    ProjectView,
)
from ..service.pk_service import PkService
from ..service.project_service import ProjectService

router = APIRouter(prefix="/projects")


@router.post("/preview", response_model=ProjectPreviewResponse)
@inject
def preview(
    req: ProjectPreviewRequest,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> ProjectPreviewResponse:
    return svc.preview(req.folder)


@router.post("", response_model=ProjectView)
@inject
def create(
    req: ProjectCreateRequest,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> ProjectView:
    return svc.create(req.name, req.source_folder)


@router.get("", response_model=list[ProjectView])
@inject
def list_projects(
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> list[ProjectView]:
    return svc.list_projects()


@router.get("/{project_id}", response_model=ProjectDetailResponse)
@inject
def get_project(
    project_id: int,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> ProjectDetailResponse:
    return svc.get_detail(project_id)


@router.post("/{project_id}/group", response_model=ProjectDetailResponse)
@inject
def group(
    project_id: int,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> ProjectDetailResponse:
    """分组需本地模型就绪，否则 503。"""
    return svc.group(project_id)


@router.get("/{project_id}/groups/{group_key}", response_model=GroupDetailResponse)
@inject
def get_group(
    project_id: int,
    group_key: str,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> GroupDetailResponse:
    return svc.get_group_detail(project_id, group_key)


@router.post("/{project_id}/groups/{group_key}/assess", response_model=GroupDetailResponse)
@inject
def assess_group(
    project_id: int,
    group_key: str,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> GroupDetailResponse:
    """层①需就绪（503）；层②缺 key/网络（502）。已评测则原样返回。"""
    return svc.assess_group(project_id, group_key)


@router.post("/{project_id}/groups/{group_key}/selection", response_model=GroupDetailResponse)
@inject
def update_selection(
    project_id: int,
    group_key: str,
    req: SelectionUpdateRequest,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> GroupDetailResponse:
    return svc.update_selection(project_id, group_key, req.changes)


@router.post("/{project_id}/groups/{group_key}/confirm", response_model=GroupDetailResponse)
@inject
def confirm_group(
    project_id: int,
    group_key: str,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> GroupDetailResponse:
    return svc.confirm_group(project_id, group_key)


@router.post("/{project_id}/confirm-all", response_model=ProjectDetailResponse)
@inject
def confirm_all(
    project_id: int,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> ProjectDetailResponse:
    """一键通过：未评测的组会触发层②大模型（可能 503/502）。"""
    return svc.confirm_all(project_id)


@router.post("/{project_id}/complete", response_model=CompleteResponse)
@inject
def complete(
    project_id: int,
    svc: ProjectService = Depends(Provide[Container.project_service]),
) -> CompleteResponse:
    """门禁：全组已确认，否则 400。"""
    return svc.complete(project_id)


# ── PK 擂台 ──────────────────────────────────────────────────────────────────

@router.post("/{project_id}/groups/{group_key}/pk/start", response_model=PkView)
@inject
def pk_start(
    project_id: int,
    group_key: str,
    req: PkStartRequest,
    svc: PkService = Depends(Provide[Container.pk_service]),
) -> PkView:
    return svc.start(project_id, group_key, req.pool, req.restart)


@router.post("/{project_id}/groups/{group_key}/pk/choose", response_model=PkView)
@inject
def pk_choose(
    project_id: int,
    group_key: str,
    req: PkChooseRequest,
    svc: PkService = Depends(Provide[Container.pk_service]),
) -> PkView:
    return svc.choose(project_id, group_key, req.outcome)


@router.post("/{project_id}/groups/{group_key}/pk/undo", response_model=PkView)
@inject
def pk_undo(
    project_id: int,
    group_key: str,
    svc: PkService = Depends(Provide[Container.pk_service]),
) -> PkView:
    return svc.undo(project_id, group_key)
