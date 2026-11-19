import json
import time
from fastapi.testclient import TestClient
from models import Profile, Spec, Resource
from store import Store
from studio import create_app
from config import FieldRule


def wait(c):
    for _ in range(200):
        s = c.get("/api/state").json()
        if s["status"] != "starting":
            return s
        time.sleep(0.02)
    raise AssertionError("startup timeout")


def test_profiles_secrets_presets_without_login(tmp_path):
    store = Store(tmp_path / "vault")
    store.save_profile(Profile(password="actual-test-private-value", auth_mode="basic"))
    assert "actual-test-private-value" not in json.dumps(store.profiles())
    assert (
        b"actual-test-private-value"
        not in (tmp_path / "vault/settings.sqlite3").read_bytes()
    )
    store.save_profile(Profile(auth_mode="basic"))
    assert store.profile()[0].password.get_secret_value() == "actual-test-private-value"
    assert store.profile(revision=1)[1] == 1
    app = create_app("api")
    with TestClient(app) as c:
        assert c.get("/api/info").status_code == 200
        for path in ["/", "/static/app.js", "/metrics"]:
            response = c.get(path)
            assert response.status_code == 200
            assert "www-authenticate" not in response.headers
        assert (
            c.post(
                "/api/start", json={}, headers={"Origin": "https://bad.test"}
            ).status_code
            == 403
        )
        r = c.post("/api/profiles", json={"password": "must-not-echo", "port": -1})
        assert r.status_code == 422 and "must-not-echo" not in r.text
        spec = Spec(name="custom")
        spec.generator.fields = [
            FieldRule(name="custom", generator="constant", value="自由な値")
        ]
        assert (
            c.post("/api/preview", json=spec.model_dump(mode="json")).json()["records"][
                0
            ]["custom"]
            == "自由な値"
        )
        assert (
            c.post("/api/presets/custom", json=spec.model_dump(mode="json")).status_code
            == 200
        )
        assert any(p["id"] == "custom" for p in c.get("/api/presets").json()["presets"])


def test_snapshot_pages_filter_delta_and_source_auth():
    app = create_app("api")
    with TestClient(app) as c:
        spec = Spec(max_ticks=1)
        spec.business.resources = [Resource(name="orders", rows=12)]
        spec.business.updates_per_tick = 0
        assert (
            c.post("/api/start", json=spec.model_dump(mode="json")).status_code == 200
        )
        assert wait(c)["status"] in {"running", "stopped"}
        first = c.get("/source/rest/orders?limit=5").json()
        assert len(first["value"]) == 5 and first["count"] == 12
        second = c.get(first["next"]).json()
        assert not (
            {v["id"] for v in first["value"]} & {v["id"] for v in second["value"]}
        )
        controller = app.state.controller
        row = {**first["value"][0], "value": 999}
        controller.store.put(controller.ds, "orders", [row])
        rest = c.get(second["next"]).json()
        assert len(rest["value"]) == 2
        delta = c.get(rest["delta"]).json()
        assert any(v.get("value") == 999 for v in delta["value"])
        assert c.get("/source/odata/$metadata").status_code == 200
        filtered = c.get(
            "/source/odata/orders",
            params={
                "$filter": "value ge 0 and value lt 1000",
                "$top": 3,
                "$orderby": "value desc",
            },
        ).json()
        assert len(filtered["value"]) == 3
        assert (
            c.get(
                "/source/rest/orders",
                params={"filter": "id eq 'x' ; DROP TABLE changes"},
            ).status_code
            == 422
        )
        bad = first["next"] + "x"
        assert c.get(bad).status_code in {400, 409}
        c.post("/api/stop", json={})
        c.post(
            "/api/profiles",
            json=Profile(auth_mode="bearer", token="source-test-token").model_dump(
                mode="json"
            )
            | {"token": "source-test-token"},
        )
        c.post("/api/start", json=spec.model_dump(mode="json"))
        wait(c)
        assert c.get("/source/rest/orders").status_code == 401
        assert (
            c.get(
                "/source/rest/orders",
                headers={"Authorization": "Bearer source-test-token"},
                auth=None,
            ).status_code
            == 200
        )


def test_historian_raw_aggregate_gap_and_resume():
    app = create_app("historian")
    with TestClient(app) as c:
        s = Spec(max_ticks=1)
        s.history.initial_samples = 10
        s.history.devices = 1
        s.history.missing_every = 3
        s.generator.fields[5].generator = "constant"
        s.generator.fields[5].value = 50
        c.post("/api/start", json=s.model_dump(mode="json"))
        assert wait(c)["status"] in {"running", "stopped"}
        rows = c.get(
            "/source/history/raw", params={"tag": "device-001.value", "limit": 100}
        ).json()["values"]
        assert 5 < len(rows) < 11
        q = {
            "tag": "device-001.value",
            "start": rows[0]["timestamp"],
            "end": rows[-1]["timestamp"],
            "interval_seconds": 2,
            "function": "mean",
            "fill": "null",
        }
        result = c.get("/source/history/aggregate", params=q)
        assert result.status_code == 200 and all(
            p["value"] in {None, 50} for p in result.json()["values"]
        )
        assert (
            c.get(
                "/source/history/raw",
                params={"tag": "device-001.value", "start": "2026-01-01"},
            ).status_code
            == 422
        )
        c.post("/api/stop", json={})


def test_fault_response_and_builtins():
    app = create_app("api")
    with TestClient(app) as c:
        s = Spec(max_ticks=1)
        s.business.fault = "rate_limit"
        s.business.fault_every = 1
        s.business.resources[0].rows = 2
        c.post("/api/start", json=s.model_dump(mode="json"))
        wait(c)
        r = c.get("/source/rest/orders")
        assert r.status_code == 429 and r.headers["Retry-After"] == "2"


def test_missing_source_credentials_are_rejected_before_start():
    app = create_app("api")
    with TestClient(app) as c:
        for mode in ["basic", "bearer", "api_key"]:
            assert c.post("/api/profiles", json={"auth_mode": mode}).status_code == 422
            assert c.get("/api/profiles").json()["profiles"][0]["auth_mode"] == "none"
            assert c.get("/api/state").json()["status"] == "stopped"
