from unittest.mock import patch

from dependency_injector import providers
from fastapi.testclient import TestClient

from keeper_engine.app import create_app
from keeper_engine.config.settings import Settings


def _client(tmp_path):
    # 不用 with TestClient(...)：避免触发 lifespan（建表/模型预热）。
    app = create_app()
    s = Settings(home=tmp_path)
    app.container.settings.override(providers.Object(s))
    return TestClient(app), s


def test_thumbnail_rejects_path_outside_workspace(tmp_path):
    client, _ = _client(tmp_path)
    with patch("keeper_engine.util.imaging.cached_thumbnail") as m:
        r = client.get("/thumbnail", params={"path": "/etc/passwd"})
    assert r.status_code == 404
    m.assert_not_called()  # 白名单在解码前就拦下


def test_thumbnail_allows_path_inside_workspace(tmp_path):
    client, s = _client(tmp_path)
    inside = s.workspace_dir / "proj" / "x.jpg"
    with patch("keeper_engine.util.imaging.cached_thumbnail", return_value=b"JPEGDATA") as m:
        r = client.get("/thumbnail", params={"path": str(inside)})
    assert r.status_code == 200
    assert r.content == b"JPEGDATA"
    m.assert_called_once()
