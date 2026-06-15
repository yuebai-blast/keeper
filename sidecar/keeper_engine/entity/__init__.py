"""数据库实体（SQLModel table 映射）。

这里集中 import 全部实体，使 `from .. import entity` 即可触发它们注册到 SQLModel.metadata，
供 Database.create_all() 统一建表。
"""

from .geocode_cache import GeocodeCache
from .model_module import ModelModule
from .photo_group import PhotoGroup
from .pk_state import PkState
from .project import Project
from .project_photo import ProjectPhoto

__all__ = [
    "GeocodeCache",
    "ModelModule",
    "PhotoGroup",
    "PkState",
    "Project",
    "ProjectPhoto",
]
