"""証明書・鍵の参照先を専用領域に制限し、接続用TLS設定を組み立てる。"""

import os
import ssl
from pathlib import Path
from generation import GenerationError


def secret(p, name):
    """秘密値のラッパーを接続直前に展開し、未設定なら空文字を返す。

    戻り値は平文のため、呼出側はログや画面へ渡さないこと。
    """
    value = getattr(p, name)
    return value.get_secret_value() if value else ""


def connection_file(value, *, directory=False):
    """実在するファイルまたはディレクトリを専用領域内で解決する。

    シンボリックリンク解決後も領域外ならGenerationErrorで拒否する。
    """
    root = Path(
        os.environ.get(
            "CONNECTION_FILES_DIR",
            str(
                Path(os.environ.get("DATA_DIR", "./data")) / "connection-files"
            ),
        )
    ).resolve()
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to(root) or not (
        path.is_dir() if directory else path.is_file()
    ):
        raise GenerationError(
            "証明書・鍵・設定ファイルはconnection-files領域に配置し、そのパスを指定してください"
        )
    return str(path)


def tls_context(p):
    """CAとクライアント証明書からTLSコンテキストを作る。

    verify以外では検証を無効にする既存仕様を保つ。証明書だけ指定された場合は拒否する。
    """
    context = ssl.create_default_context(
        cafile=connection_file(p.tls_ca_file) if p.tls_ca_file else None
    )
    if p.ssl_mode != "verify":
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    if p.tls_cert_file:
        if not p.tls_key_file:
            raise GenerationError(
                "クライアント証明書と秘密鍵を両方指定してください"
            )
        context.load_cert_chain(
            connection_file(p.tls_cert_file),
            connection_file(p.tls_key_file),
            secret(p, "tls_key_password") or None,
        )
    return context
