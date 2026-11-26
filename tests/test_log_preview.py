"""ログプレビューとローカル配送の、永続キュー上の境界を検証する。"""

import asyncio

from fastapi.testclient import TestClient

from controller import Controller
from drivers import EventDriver, syslog_tcp_frame
from models import Profile, Spec
from store import Store
from studio import create_app


def test_log_preview_uses_actual_format_and_does_not_send(monkeypatch):
    """マルチバイト本文と破損・重複を表示し、実配送と進捗には触れない。"""
    def no_send(*args, **kwargs):
        raise AssertionError("プレビューで配送してはいけません")

    monkeypatch.setattr(EventDriver, "send", no_send)
    app = create_app("logs")
    with TestClient(app) as client:
        app.state.store.save_profile(Profile(id="fixture", output="tcp", host="localhost"))
        spec = Spec(profile_id="fixture")
        spec.logs.message_template = "疑似ログ"
        spec.logs.malformed_every = 2
        spec.logs.duplicate_every = 2
        spec.generator.start_sequence = 34
        before = client.get("/api/state").json()
        response = client.post("/api/preview", json=spec.model_dump(mode="json"))
        assert response.status_code == 200
        result = response.json()
        assert result["writes"] is False
        assert client.get("/api/state").json() == before
        assert result["log_preview"]["output"] == "tcp"
        assert result["log_preview"]["profile_revision"] == 1
        samples = result["log_preview"]["samples"]
        assert samples[0]["payload"].startswith("<134>1 2000-01-01")
        assert samples[1]["malformed"] and samples[1]["duplicate"]
        assert samples[1]["payload"].startswith("BROKEN-HEADER ")
        for sample, row in zip(samples, result["records"], strict=True):
            data = sample["payload"].encode("utf-8")
            assert row["_formatted_log"] == sample["payload"]
            assert sample["message_bytes"] == len(data)
            assert sample["wire_bytes"] == len(str(len(data))) + 1 + len(data)
            assert syslog_tcp_frame(data, "newline") == data + b"\n"
        with app.state.store.db() as conn:
            assert conn.execute("SELECT count(*) FROM events").fetchone()[0] == 0


def test_log_file_write_failure_stays_pending_until_success(tmp_path, monkeypatch):
    """回転失敗で配送済みと誤記録せず、成功した再試行だけを確定する。"""
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    store = Store(tmp_path / "store")
    controller = Controller("logs", store)
    controller.spec = Spec(batch_size=1)
    controller.profile = Profile(output="file")

    async def scenario():
        driver = EventDriver(controller)
        await driver.start()
        try:
            def fail_rotation(_record):
                raise OSError("synthetic rollover failure")

            with monkeypatch.context() as failure:
                failure.setattr(driver.handler, "shouldRollover", fail_rotation)
                await driver.step(0)
            with store.db() as conn:
                pending = conn.execute("SELECT status FROM events").fetchall()
                assert [row["status"] for row in pending] == ["pending"]
            assert driver.information["last_delivery_error"] == "OSError"
            await driver.flush()
            with store.db() as conn:
                delivered = conn.execute("SELECT status FROM events").fetchall()
                assert [row["status"] for row in delivered] == ["delivered"]
        finally:
            await driver.close()

    asyncio.run(scenario())
    assert len((tmp_path / "logs" / "events.log").read_text().splitlines()) == 1


def test_log_start_uses_the_confirmed_revision(monkeypatch, confirmed_start):
    """確認した版、または版を省略した時点の最新版を開始に使う。"""
    app = create_app("logs")
    calls = []

    def no_launch(spec, revision=None):
        calls.append((spec.profile_id, revision))
        return {"status": "mocked"}

    monkeypatch.setattr(app.state.controller, "start", no_launch)
    with TestClient(app) as client:
        for host in ("older.example.invalid", "newer.example.invalid"):
            response = client.post("/api/profiles", json={"output": "tcp", "host": host})
            assert response.status_code == 200, response.text
        assert confirmed_start(client, {}).status_code == 200
        assert confirmed_start(client, {}, profile_revision=2).status_code == 200
        assert client.post("/api/start?profile_revision=0", json={}).status_code == 422
        assert client.post("/api/start?profile_revision=99", json={}).status_code == 404
    assert calls == [("default", 3), ("default", 2)]
