"""在线反查地名：GPS 经纬度 → 可读地名（拍摄地展示用）。

本地优先的让步点之一：照片永不出本地，但「拍摄地」需要把**坐标**（非照片）发给地理编码服务。
默认 OpenStreetMap Nominatim（无需 key，与 EXIF 同为 WGS-84）；服务地址/UA/语言走 settings，
便于换高德等。结果按坐标（固定精度取整）缓存到 sqlite，避免重复联网。

失败一律静默返回 None（拍摄地获取不到就不展示，绝不阻断导入流程）——与「不静默降级」的
区别：这里地名只是锦上添花的展示信息，不是产品能力，拿不到属正常。
"""

from __future__ import annotations

import httpx

from ..config.settings import Settings
from ..mapper.geocode_cache_mapper import GeocodeCacheMapper

# 反查地名时，从 Nominatim 的 address 里按此优先级挑层级拼出简洁地名（最多 3 段）
_ADDRESS_KEYS = ("state", "city", "county", "town", "suburb", "district")
_COORD_PRECISION = 3  # 坐标取整精度（~100m）：同一地点共享缓存


class GeocodeClient:
    """坐标→地名反查（带 sqlite 缓存）。"""

    def __init__(self, settings: Settings, cache: GeocodeCacheMapper) -> None:
        self._settings = settings
        self._cache = cache

    def reverse(self, lat: float, lon: float) -> str | None:
        """反查一个坐标的地名；命中缓存直接返回，失败返回 None（不抛）。"""
        if not self._settings.geocode_enabled:
            return None
        key = f"{round(lat, _COORD_PRECISION)},{round(lon, _COORD_PRECISION)}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached or None  # 空串=曾查过但无结果，仍命中缓存不再联网

        location = self._fetch(lat, lon)
        self._cache.put(key, location or "")
        return location or None

    def _fetch(self, lat: float, lon: float) -> str | None:
        try:
            resp = httpx.get(
                self._settings.geocode_url,
                params={"lat": lat, "lon": lon, "format": "jsonv2",
                        "accept-language": self._settings.geocode_lang, "zoom": 12},
                headers={"User-Agent": self._settings.geocode_user_agent},
                timeout=6.0,
            )
            resp.raise_for_status()
            return self._format(resp.json())
        except Exception:
            return None

    @staticmethod
    def _format(data: dict) -> str | None:
        """从反查结果拼出简洁地名：最多 3 个行政层级，用「·」连接。"""
        addr = data.get("address", {}) or {}
        parts: list[str] = []
        for k in _ADDRESS_KEYS:
            v = addr.get(k)
            if v and v not in parts:
                parts.append(v)
            if len(parts) >= 3:
                break
        if parts:
            return "·".join(parts)
        display = (data.get("display_name") or "").split(",")[0].strip()
        return display or None
