"""共享 SQLite 引擎：全部 mapper 复用同一 engine（统一数据根 ~/.keeper/keeper.db）。

engine 跨线程复用（预热在后台线程写、请求线程读、工作流在请求线程读写），故
check_same_thread=False；每次操作新开 Session。建表统一走 create_all()——app 启动时调一次，
调用前 import 全部实体以完成 SQLModel 元数据注册。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .settings import Settings


class Database:
    """持有共享 engine，提供 Session 与建表。由 DI 以单例注入各 mapper。"""

    def __init__(self, settings: Settings) -> None:
        db_path = Path(settings.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )

    def create_all(self) -> None:
        """建立全部已注册的 SQLModel 表（先 import 实体包，确保元数据已注册）。"""
        from .. import entity  # noqa: F401 —— 触发各实体模块导入，注册到 SQLModel.metadata

        SQLModel.metadata.create_all(self.engine)
        self._apply_additive_migrations()

    def _apply_additive_migrations(self) -> None:
        """对已存在的表补齐新增列（SQLite ALTER TABLE ADD COLUMN，纯增量、不丢数据）。

        create_all 只建缺失的表，不会给已有表加列。新增可空列时，对老库执行加列以平滑升级。
        仅做「加列」这类绝对安全的迁移；改/删列等破坏性变更不在此处理。
        """
        # (表名, 列名, 列 DDL 类型)；新增可空列即可，无需默认值（缺省 NULL）
        additive = [("project_photo", "assess_error", "VARCHAR")]
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())
        with self.engine.begin() as conn:
            for table, column, ddl_type in additive:
                if table not in existing_tables:
                    continue
                cols = {c["name"] for c in inspector.get_columns(table)}
                if column not in cols:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))

    def session(self) -> Session:
        """新开一个 Session（调用方用 with 管理生命周期）。"""
        return Session(self.engine)
