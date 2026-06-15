"""模型模块状态的数据访问（SQLModel / sqlite）。

复用共享 Database（统一数据根 ~/.keeper/keeper.db）。engine 跨线程复用（预热在后台线程写、
/health 在请求线程读），故 check_same_thread=False（见 config.database）；每次操作新开 Session。
建表由 Database.create_all() 统一负责（app 启动时调）。
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from ..config.database import Database
from ..entity.model_module import ModelModule


class ModelModuleMapper:
    """模型模块下载/加载状态的增改查。"""

    def __init__(self, database: Database) -> None:
        self._db = database

    def upsert(self, name: str, status: str, detail: str = "", downloaded_bytes: int = 0) -> None:
        """按 name 插入或更新一条模块状态。"""
        with self._db.session() as session:
            row = session.get(ModelModule, name) or ModelModule(name=name)
            row.status = status
            row.detail = detail
            row.downloaded_bytes = downloaded_bytes
            row.updated_at = datetime.now()
            session.add(row)
            session.commit()

    def all(self) -> list[ModelModule]:
        """返回全部模块状态（按 name 升序）。"""
        with self._db.session() as session:
            return list(session.exec(select(ModelModule).order_by(ModelModule.name)))
