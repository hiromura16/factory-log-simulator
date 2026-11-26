"""実行ごとに独立した保存先と既知の環境設定を用意する。"""

import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """各テストに一時ディレクトリを割り当てる。

    外部のパスワード設定や自動起動の影響を避け、ディスク空き容量の
    しきい値を無効にする。環境変数の変更はpytestがテスト後に戻す。
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.setenv("MIN_AVAILABLE_GIB", "0")
    monkeypatch.delenv("APP_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("AUTO_START", raising=False)


@pytest.fixture
def confirmed_start():
    """実行する設定と出力先の版を確認してから開始する。"""
    def start(client, payload, *, profile_revision=None):
        path = "/api/start"
        plan = {"path": path, "payload": payload}
        if profile_revision is not None:
            plan["profile_revision"] = profile_revision
            path += f"?profile_revision={profile_revision}"
        response = client.post("/api/operations/plan", json=plan)
        assert response.status_code == 200, response.text
        token = response.json()["confirmation_token"]
        headers = {"X-Operation-Confirmation": token} if token else {}
        return client.post(path, json=payload, headers=headers)

    return start
