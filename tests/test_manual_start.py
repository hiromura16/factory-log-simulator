import pytest
from fastapi.testclient import TestClient

from controller import Controller
from models import Profile, Spec
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


@pytest.mark.parametrize(
    ("running", "saved_revision", "add_open_revision", "expected"),
    [
        (True, 1, True, 200),
        (False, 1, True, 200),
        (False, None, False, 200),
        (False, None, True, 503),
        (False, 9, False, 503),
    ],
)
def test_stored_events_keep_source_auth(
    monkeypatch, tmp_path, running, saved_revision, add_open_revision, expected
):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app("logs")
    store = app.state.store
    store.save_profile(Profile(id="protected", auth_mode="bearer", token="fixture-token"))
    if add_open_revision:
        store.save_profile(Profile(id="protected", auth_mode="none"))
    saved = {
        "running": running,
        "spec": Spec(profile_id="protected").model_dump(mode="json"),
    }
    if saved_revision is not None:
        saved["revision"] = saved_revision
    store.meta("desired", saved)
    with store.db() as db:
        db.execute(
            "INSERT INTO events(target,event_id,payload,created_at) VALUES(?,?,?,?)",
            ("capture", "fixture-id", "saved-event", 0),
        )
    with TestClient(app) as client:
        for _ in range(2):
            assert client.get("/api/state").json()["status"] == "stopped"
            for route in ("/source/events", "/source/logs/download"):
                assert client.get(route).status_code == (401 if expected == 200 else 503)
                response = client.get(route, headers={"Authorization": "Bearer fixture-token"})
                assert response.status_code == expected
                assert ("saved-event" in response.text) == (expected == 200)
            assert client.post("/api/stop", json={}).status_code == 200
            assert store.meta("desired") == {**saved, "running": False}


@pytest.mark.parametrize("saved", [None, {"running": False, "spec": None},
                                  {"running": False, "spec": {}}])
def test_old_events_without_source_auth_metadata_fail_closed(monkeypatch, tmp_path, saved):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    app = create_app("logs")
    store = app.state.store
    if saved is not None:
        store.meta("desired", saved)
    with store.db() as db:
        db.execute(
            "INSERT INTO events(target,event_id,payload,created_at) VALUES(?,?,?,?)",
            ("capture", "fixture-id", "saved-event", 0),
        )
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/source/events").status_code == 503
        assert client.get("/source/logs/download").status_code == 503
