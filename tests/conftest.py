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
