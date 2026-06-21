from fastapi import FastAPI
from fastapi.testclient import TestClient

from keeper_engine.middleware.auth import AuthMiddleware


def _client(token: str) -> TestClient:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, token=token)

    @app.get("/x")
    def x():  # noqa: ANN202
        return {"ok": True}

    return TestClient(app)


def test_empty_token_passes_all():
    c = _client("")
    assert c.get("/x").status_code == 200


def test_correct_header_passes():
    c = _client("secret")
    assert c.get("/x", headers={"X-Keeper-Token": "secret"}).status_code == 200


def test_wrong_header_401():
    c = _client("secret")
    assert c.get("/x", headers={"X-Keeper-Token": "nope"}).status_code == 401


def test_missing_token_401():
    c = _client("secret")
    assert c.get("/x").status_code == 401


def test_query_token_passes():
    c = _client("secret")
    assert c.get("/x", params={"token": "secret"}).status_code == 200


def test_options_passes_without_token():
    c = _client("secret")
    assert c.options("/x").status_code != 401
