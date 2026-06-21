from pathlib import Path

from keeper_engine.config.settings import Settings


def test_auth_token_default_empty(monkeypatch):
    monkeypatch.delenv("KEEPER_AUTH_TOKEN", raising=False)
    assert Settings().auth_token == ""


def test_auth_token_from_env(monkeypatch):
    monkeypatch.setenv("KEEPER_AUTH_TOKEN", "abc123")
    assert Settings().auth_token == "abc123"


def test_models_dir_defaults_to_home_subdir(monkeypatch):
    monkeypatch.delenv("KEEPER_MODELS_DIR", raising=False)
    monkeypatch.setenv("KEEPER_HOME", "/tmp/kh")
    s = Settings()
    assert s.models_dir == Path("/tmp/kh/models")
    assert s.workspace_dir == Path("/tmp/kh/workspace")  # 其余派生仍跟随 home


def test_models_dir_env_override(monkeypatch):
    monkeypatch.setenv("KEEPER_HOME", "/tmp/kh")
    monkeypatch.setenv("KEEPER_MODELS_DIR", "/tmp/cache/models")
    s = Settings()
    assert s.models_dir == Path("/tmp/cache/models")
    assert s.workspace_dir == Path("/tmp/kh/workspace")  # home 派生不受 models 覆盖影响
