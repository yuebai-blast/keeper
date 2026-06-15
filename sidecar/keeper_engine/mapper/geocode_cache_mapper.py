"""地理编码缓存的数据访问。复用共享 Database。"""

from __future__ import annotations

from datetime import datetime

from ..config.database import Database
from ..entity.geocode_cache import GeocodeCache


class GeocodeCacheMapper:
    """坐标→地名缓存的查与写。"""

    def __init__(self, database: Database) -> None:
        self._db = database

    def get(self, coord_key: str) -> str | None:
        with self._db.session() as session:
            row = session.get(GeocodeCache, coord_key)
            return row.location if row else None

    def put(self, coord_key: str, location: str) -> None:
        with self._db.session() as session:
            row = session.get(GeocodeCache, coord_key) or GeocodeCache(coord_key=coord_key)
            row.location = location
            row.updated_at = datetime.now()
            session.add(row)
            session.commit()
