import pytest
from fastapi.testclient import TestClient

from controller import Controller
from models import Spec
from studio import create_app


@pytest.mark.parametrize("previously_running", [False, True])
def test_startup_waits_for_explicit_start(monkeypatch, tmp_path, previously_running):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # 旧環境の変数と実行記録が残ったままでも、起動段階では出力しない。
    monkeypatch.setenv("AUTO_START", "1")
    spec = Spec().model_dump(mode="json")
    app = create_app("logs")
    if previously_running:
        app.state.store.meta("desired", {"running": True, "spec": spec, "revision": 1})

    starts = []

    def record_start(self, requested, revision=None):
        starts.append(requested.model_dump(mode="json"))
        return self.snapshot()

    monkeypatch.setattr(Controller, "start", record_start)
    with TestClient(app) as client:
        state = client.get("/api/state").json()
        assert state["status"] == "stopped"
        assert state["produced"] == 0
        assert starts == []
        if previously_running:
            assert app.state.store.meta("desired")["spec"] == spec
        assert client.post("/api/start", json=spec).status_code == 200
        assert starts == [spec]
