import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setenv("MIN_AVAILABLE_GIB", "0")
    monkeypatch.delenv("APP_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("AUTO_START", raising=False)
