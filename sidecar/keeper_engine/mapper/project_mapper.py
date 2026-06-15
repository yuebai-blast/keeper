"""项目实体的数据访问。复用共享 Database；更新走 merge（实例可能脱离 Session）。"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from ..config.database import Database
from ..entity.project import Project


class ProjectMapper:
    """项目的增改查。"""

    def __init__(self, database: Database) -> None:
        self._db = database

    def create(self, project: Project) -> Project:
        """插入新项目，返回带自增 id 的实例。"""
        with self._db.session() as session:
            session.add(project)
            session.commit()
            session.refresh(project)
            return project

    def get(self, project_id: int) -> Project | None:
        with self._db.session() as session:
            return session.get(Project, project_id)

    def get_by_name(self, name: str) -> Project | None:
        with self._db.session() as session:
            return session.exec(select(Project).where(Project.name == name)).first()

    def all(self) -> list[Project]:
        """全部项目，按创建时间倒序（最近的在前）。"""
        with self._db.session() as session:
            return list(session.exec(select(Project).order_by(Project.created_at.desc())))

    def update(self, project: Project) -> Project:
        """保存改动（merge 一个可能脱离 Session 的实例）。自动刷新 updated_at。"""
        project.updated_at = datetime.now()
        with self._db.session() as session:
            merged = session.merge(project)
            session.commit()
            session.refresh(merged)
            return merged
