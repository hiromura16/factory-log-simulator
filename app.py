"""アプリ固有の種類を指定して共通スタジオをASGIアプリとして公開する。"""

from studio import create_app

app = create_app("logs")
