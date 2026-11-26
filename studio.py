"""共通の管理画面、設定保存、取得APIの認証と実行状態を組み立てる。

ルートと入力モデルにはコメントを使い、公開スキーマへの説明追加を避ける。
"""

import base64
import hmac
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from models import Profile, Spec, TITLES, SECRETS
from config import ConfigurationError
from generation import generate_record, sample_offsets, validate_generation
from store import Store
from api_support import (
    install_error_handlers, install_help,
    management_credentials, unauthorized_management,
)
from controller import Controller


# 接続ファイル取込の名前とBase64本文を制限する入力契約。
class Upload(BaseModel):
    name: str = Field(
        pattern=r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+){0,3}$", max_length=160
    )
    content_base64: str = Field(max_length=1500000)


def schemas(kind):
    """アプリ種類に応じた表示用スキーマを作り、非該当の項目を画面から隠す。"""
    from helptext import HELP

    result = {
        "spec": Spec.model_json_schema(),
        "profile": Profile.model_json_schema(),
    }
    translations = {
        "generator": "任意項目とデータ異常",
        "equipment": "設備プロトコル設定",
        "business": "業務API設定",
        "history": "時系列保存設定",
        "logs": "ログ設定",
        "identification": "作業者・RFID設定",
        "auth_mode": "取得APIの認証方式",
        "opc_auth": "OPC UAの認証",
        "opc_security": "OPC UAの通信保護",
        "area": "Modbusの領域",
        "encoding": "レジスターの型",
        "byte_order": "1ワード内のバイト順",
        "word_order": "複数ワードの順序",
        "quality": "品質コード",
        "format": "ログ書式",
        "tcp_framing": "TCPのメッセージ境界",
        "barcode": "ラベルの方式",
        "output": "送信・保存方式",
    }
    hints = {
        "auth_mode": "noneは取得用APIの認証なし、basicはユーザーとパスワード、bearerはAuthorization: Bearer、api_keyはX-API-Key。管理画面の認証は別に設定します。",
        "opc_auth": "anonymousは匿名読取、usernameは専用ユーザーで認証。username時はSignAndEncryptが必要です。",
        "opc_security": "noneは署名・暗号化なし。sign_encryptはBasic256Sha256で署名と暗号化。証明書と秘密鍵を配置し、クライアントも対応する証明書で接続します。",
        "output": "captureは永続記録だけ、fileはローカル回転ログ、udp/tcp/tlsはSyslog。UDP/TCPは受信アプリの処理完了を保証しません。MQTTはQoS1のブローカーACK、HTTPは2xx受付まで。",
        "area": "holding=FC3、input=FC4、coil=FC1、discrete=FC2。アドレスは0始まりです。",
        "encoding": "16bit整数は1レジスター、32bit/float32は2、float64は4。signedは負数対応。boolはcoil/discrete用。",
        "byte_order": "bigは通常の上位バイト先頭、littleは16bitワード内のバイトを反転。",
        "word_order": "bigは上位ワード先頭、littleは複数ワードを逆順にします。",
        "tcp_framing": "octet_countingはRFC6587の「UTF-8バイト数 空白 本文」。newlineは末尾改行。受信側と方式を合わせます。",
        "quality": "Goodは正常、Badは利用不適、Uncertainは確実でない値。設備用はOPC UAの実StatusCodeへ変換します。",
        "barcode": "code128は任意のタグ文字列、ean13はチェックディジット付き13桁、qrは二次元コード。PNGをラベルAPIから取得できます。",
    }

    def annotate(schema):
        """既存説明を尊重しながら、日本語の項目名と補助説明を再帰的に付ける。"""
        for name, prop in schema.get("properties", {}).items():
            if name in translations:
                prop["title"] = translations[name]
            elif name in HELP:
                prop["title"] = HELP[name][0]
            if name in hints:
                prop.setdefault("description", hints[name])
            elif name in HELP:
                prop.setdefault("description", HELP[name][1])
            prop.setdefault(
                "description",
                (
                    prop.get("title", name)
                    + "の設定。現在の型と選択肢に合わせて指定します。"
                ),
            )
        for child in schema.get("$defs", {}).values():
            annotate(child)

    for schema in result.values():
        annotate(schema)
    from helptext import annotated_schemas

    prior = annotated_schemas()["run"].get("$defs", {})
    for name, definition in result["spec"].get("$defs", {}).items():
        for field, prop in definition.get("properties", {}).items():
            for annotation in ["title", "description"]:
                source = (
                    prior.get(name, {}).get("properties", {}).get(field, {})
                )
                if annotation in source:
                    prop[annotation] = source[annotation]
    result["spec"]["$defs"]["FieldRule"]["properties"]["primary_key"][
        "ui_hidden"
    ] = True
    gen = result["spec"]["$defs"]["RunSpec"]["properties"]
    visible = {
        "run_key",
        "seed",
        "parameters",
        "fields",
        "anomalies",
        "start_sequence",
    }
    for name, prop in gen.items():
        prop["ui_hidden"] = name not in visible
    for name in ["equipment", "business", "history", "logs", "identification"]:
        result["spec"]["properties"][name]["ui_hidden"] = (
            name
            != {
                "equipment": "equipment",
                "api": "business",
                "historian": "history",
                "logs": "logs",
                "identification": "identification",
            }[kind]
        )
    for prop in result["spec"]["properties"].values():
        if prop.get("const") is not None:
            prop["ui_hidden"] = True
    profile = result["profile"]["properties"]
    common = {
        "id",
        "name",
        "auth_mode",
        "username",
        "password",
        "token",
        "clear_secrets",
    }
    specific = {
        "equipment": {
            "opc_enabled",
            "opc_port",
            "namespace_uri",
            "opc_auth",
            "opc_username",
            "opc_password",
            "opc_security",
            "certificate_file",
            "private_key_file",
            "trusted_client_certificates",
            "modbus_enabled",
            "modbus_port",
        },
        "api": {"allow_writes"},
        "historian": set(),
        "logs": {
            "output",
            "host",
            "port",
            "tls_verify",
            "ca_file",
            "timeout_seconds",
        },
        "identification": {
            "output",
            "host",
            "port",
            "url",
            "topic",
            "output_username",
            "mqtt_tls",
            "output_password",
            "output_token",
            "tls_verify",
            "ca_file",
            "timeout_seconds",
        },
    }[kind]
    for name, prop in profile.items():
        prop["ui_hidden"] = name not in common | specific
    if kind in {"logs", "identification"}:
        profile["output"]["enum"] = (
            ["capture", "file", "udp", "tcp", "tls"]
            if kind == "logs"
            else ["capture", "mqtt", "http"]
        )
    return result


def create_app(kind):
    """保存領域・コントローラー・認証・管理ルートを一つのFastAPIアプリへ束ねる。"""
    root = Path(__file__).resolve().parent
    store = Store(os.environ.get("DATA_DIR", "./data"))
    controller = Controller(kind, store)
    try:
        store.profile()
    except KeyError:
        store.save_profile(
            Profile(output="file" if kind == "logs" else "capture")
        )
    if kind == "equipment":
        for identity, label, opc, modbus in [
            ("opc-only", "OPC UAのみ", True, False),
            ("modbus-only", "Modbus TCPのみ", False, True),
        ]:
            try:
                store.profile(identity)
            except KeyError:
                store.save_profile(
                    Profile(
                        id=identity,
                        name=label,
                        opc_enabled=opc,
                        modbus_enabled=modbus,
                    )
                )
    store.seed(root / "presets")

    @asynccontextmanager
    async def lifespan(app):
        """操作を待ち、終了時は実行スレッドを止めて保存済み設定を保持する。"""
        yield
        controller.stop_event.set()
        if controller.thread:
            await __import__("asyncio").to_thread(controller.thread.join, 15)

    app = FastAPI(title=TITLES[kind], version="0.3.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.controller = controller
    app.state.store = store

    # 入力エラーから位置・種類・説明だけを返し、生の入力値は含めない。
    # 入力値の制約違反を422応答へ変換する。
    @app.exception_handler(ValueError)
    async def invalid_value(request, exc):
        return JSONResponse({"detail": str(exc) if isinstance(exc, ConfigurationError) else "設定値の形式または組み合わせを確認してください。"}, 422)

    # 変更系要求のOrigin・JSON形式・容量を検査し、共通の応答ヘッダーを付ける。
    credentials = management_credentials()
    install_error_handlers(app)

    @app.middleware("http")
    async def protect(request, call_next):
        denied = unauthorized_management(request, credentials, True)
        if denied is not None:
            return denied
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and (
                urlsplit(origin).netloc != request.headers.get("host")
                or urlsplit(origin).scheme != request.url.scheme
            ):
                return JSONResponse(
                    {"detail": "別サイトからの操作は禁止されています"}, 403
                )
            if (
                request.headers.get("content-type", "").split(";")[0]
                != "application/json"
            ):
                return JSONResponse(
                    {"detail": "application/jsonが必要です"}, 415
                )
            if len(await request.body()) > 2 * 1024**2:
                return JSONResponse(
                    {"detail": "JSONは2MiB以下にしてください"}, 413
                )
        result = await call_next(request)
        result.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
            }
        )
        return result

    def authorize(request):
        """取得APIのnone・Basic・Bearer・APIキー認証を評価する。

        管理画面全体のログイン制御ではない。秘密値比較には定数時間比較を使う。
        """
        try:
            p = controller.source_profile()
        except KeyError:
            raise HTTPException(503, "保存済みの公開設定を確認してください") from None
        mode = p.auth_mode
        ok = mode == "none"
        if mode == "basic":
            try:
                ok = (
                    bool(p.password)
                    and request.headers.get("authorization", "").startswith(
                        "Basic "
                    )
                    and hmac.compare_digest(
                        base64.b64decode(
                            request.headers.get("authorization", "")[6:],
                            validate=True,
                        ),
                        (
                            p.username + ":" + p.password.get_secret_value()
                        ).encode(),
                    )
                )
            except Exception:
                ok = False
        elif mode == "bearer":
            ok = bool(p.token) and hmac.compare_digest(
                request.headers.get("authorization", "").encode(),
                ("Bearer " + p.token.get_secret_value()).encode(),
            )
        elif mode == "api_key":
            ok = bool(p.token) and hmac.compare_digest(
                request.headers.get("x-api-key", "").encode(),
                p.token.get_secret_value().encode(),
            )
        if not ok:
            raise HTTPException(
                401,
                "取得用認証が必要です",
                headers={"WWW-Authenticate": 'Basic realm="Factory Source"'}
                if mode == "basic"
                else {},
            )

    app.mount("/static", StaticFiles(directory=root / "static"), name="static")
    install_help(app, root, True, kind, credentials)

    # 静的な管理画面の入口を返す。
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(root / "static/index.html")

    # プロセスの応答状態とサービス種類を返す。
    @app.get(
        "/healthz",
        summary='動作確認',
        tags=['動作確認・監視'],
    )
    def health():
        """アプリがHTTPに応答することを示します。接続先や下流の処理結果は別に確認します。"""
        return {"status": "ok", "service": kind, "version": "0.3.0"}

    # 種類別の接続先案内、表示スキーマ、既定設定を返す。
    @app.get(
        "/api/info",
        summary='アプリ情報・既定値',
        tags=['動作確認・監視'],
    )
    def info():
        """このアプリに適用される設定、既定値、接続先の案内を返します。秘密情報は含みません。"""
        return {
            "kind": kind,
            "title": TITLES[kind],
            "schemas": schemas(kind),
            "defaults": Spec().model_dump(mode="json"),
            "source_paths": {
                "equipment": [
                    "opc.tcp://HOST:PORT/factory/",
                    "Modbus TCP device IDs 1..N",
                ],
                "api": [
                    "/source/rest/orders",
                    "/source/odata/orders",
                    "/source/odata/$metadata",
                ],
                "historian": [
                    "/source/history/tags",
                    "/source/history/raw",
                    "/source/history/aggregate",
                ],
                "logs": ["/source/events", "/source/logs/download"],
                "identification": ["/source/events", "/source/labels/0.png"],
            }[kind],
        }

    # コントローラーの現在状態を取得する。
    @app.get(
        "/api/state",
        summary='現在の実行状態',
        tags=['実行・出力'],
    )
    def state():
        """開始時刻、状態、生成数と処理中のエラーを返します。停止状態でも保存済みデータは残ります。"""
        return controller.snapshot()

    # 秘密値を除いた保存プロファイル一覧を返す。
    @app.get(
        "/api/profiles",
        summary='公開・出力設定の一覧',
        tags=['接続・公開設定'],
    )
    def profiles():
        """保存済み設定と版を返します。パスワードやトークンの値は含みません。"""
        return {"profiles": store.profiles()}

    # アプリ種類ごとの出力方式と接続先を検証してプロファイルを保存する。
    @app.post(
        "/api/profiles",
        summary='公開・出力設定を保存',
        tags=['接続・公開設定'],
    )
    def profile(p: Profile):
        """同じIDで新しい版を保存します。取得認証と出力先は選んだ方式の設定から解決します。"""
        if set(p.clear_secrets) - SECRETS:
            raise HTTPException(422, "削除する認証情報名を確認してください")
        if p.output in {"udp", "tcp", "tls", "mqtt"} and (
            not p.host or any(c in p.host for c in "/@?# \r\n")
        ):
            raise HTTPException(422, "送信先ホスト名・IPを指定してください")
        if p.output == "http" and not p.url:
            raise HTTPException(422, "HTTP送信先URLが必要です")
        if p.url:
            value = urlsplit(p.url)
            if (
                value.scheme not in {"http", "https"}
                or not value.hostname
                or value.username
                or value.password
            ):
                raise HTTPException(
                    422, "認証を含まないHTTP(S) URLを指定してください"
                )
        if kind == "logs" and p.output not in {
            "capture",
            "file",
            "udp",
            "tcp",
            "tls",
        }:
            raise HTTPException(
                422, "ログはfile/capture/UDP/TCP/TLSから選択してください"
            )
        if kind == "identification" and p.output not in {
            "capture",
            "mqtt",
            "http",
        }:
            raise HTTPException(
                422, "識別イベントはcapture/MQTT/HTTPから選択してください"
            )
        return store.save_profile(p)

    # 保存済みの実行プリセット一覧を返す。
    @app.get(
        "/api/presets",
        summary='ひな型一覧',
        tags=['設定・ひな型'],
    )
    def presets():
        """同梱・保存済みのひな型と内容を返します。読み取りで生成や実行は始まりません。"""
        return {"presets": store.presets()}

    # 指定IDのプリセットを検証済み設定で保存する。
    @app.post(
        "/api/presets/{identity}",
        summary='ひな型を保存',
        tags=['設定・ひな型'],
    )
    def preset(identity: str, spec: Spec):
        """IDは英数字・下線・ハイフンで64文字以内です。JSONを検証し、同じIDならひな型を更新します。"""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identity):
            raise HTTPException(422, "プリセットIDを確認してください")
        validate_generation(spec.generator)
        return store.save_preset(identity, spec)

    # 境界サンプルを生成し、実行を始めずにデータと異常の影響を確認する。
    @app.post(
        "/api/preview",
        summary='実行前に生成の見本を見る',
        tags=['設定・ひな型'],
    )
    def preview(spec: Spec):
        """入力を検証し、先頭や異常条件の境界で合成した値を records に返します。writes は false です。実行先へ出力しません。"""
        validate_generation(spec.generator)
        offsets = sorted({0, 1, 2, *sample_offsets(spec.generator)})[:12]
        records, hits = [], []
        log_preview = None
        driver = None
        if kind in {"logs", "identification"}:
            from drivers import EventDriver, syslog_tcp_frame

            preview_controller = Controller(kind, store)
            preview_controller.spec = spec
            driver = EventDriver(preview_controller)
        if kind == "logs":
            try:
                profile, revision = store.profile(spec.profile_id)
            except KeyError:
                output, revision = None, None
            else:
                output = profile.output
            log_preview = {
                "format": spec.logs.format,
                "profile_id": spec.profile_id,
                "profile_revision": revision,
                "output": output,
                "tcp_framing": spec.logs.tcp_framing if output in {"tcp", "tls"} else None,
                "timestamp_is_sample": True,
                "samples": [],
            }
        for offset in offsets:
            trace = []
            if driver is None:
                row = generate_record(
                    spec.generator, spec.generator.start_sequence + offset, trace=trace
                )
            else:
                row = driver.event(offset, trace=trace)
            if log_preview is not None:
                payload, malformed = driver.log_payload(
                    row, offset, at=datetime(2000, 1, 1, tzinfo=timezone.utc)
                )
                row["_formatted_log"] = payload
                data = payload.encode("utf-8")
                samples = log_preview["samples"]
                every = spec.logs.duplicate_every
                samples.append({
                    "sequence": offset,
                    "payload": payload,
                    "message_bytes": len(data),
                    "wire_bytes": len(syslog_tcp_frame(data, spec.logs.tcp_framing))
                    if output in {"tcp", "tls"} else None,
                    "duplicate": bool(every and (offset + 1) % every == 0),
                    "malformed": malformed,
                })
            records.append(row)
            hits.append(trace)
        result = {
            "records": records,
            "anomaly_hits": hits,
            "sequences": offsets,
            "writes": False,
            "validated_spec": spec.model_dump(mode="json"),
            "compact_spec": {"version": spec.version, **spec.model_dump(mode="json", exclude_defaults=True)},
        }
        if log_preview is not None:
            result["log_preview"] = log_preview
        return result

    # 設定をコントローラーへ渡してバックグラウンド実行を開始する。
    @app.post(
        "/api/start",
        summary='生成・公開を開始',
        tags=['実行・出力'],
        responses={409: {'description': 'すでに実行中です'}},
    )
    def start(spec: Spec, profile_revision: int | None = Query(default=None, ge=1)):
        """設定を確定しバックグラウンドに開始を依頼します。現在の状態は GET /api/state で確認します。"""
        try:
            return controller.start(spec, revision=profile_revision)
        except KeyError:
            raise HTTPException(404, "指定した出力先の版が見つかりません") from None
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from None

    # 停止を要求し、停止待ちを含む現在状態を返す。
    @app.post(
        "/api/stop",
        summary='生成・公開を停止',
        tags=['実行・出力'],
    )
    def stop():
        """新しい生成を停止します。保存済みのデータと設定は残ります。curlではJSONの空オブジェクトを送れます。"""
        return controller.stop()

    # 実行状態のカウンターをPrometheus向けテキストで返す。
    @app.get(
        "/metrics", response_class=PlainTextResponse,
        summary='Prometheus向けメトリクス',
        tags=['動作確認・監視'],
    )
    def metrics():
        """生成や実行状態のカウンターをPrometheus向けテキストで返します。"""
        return f'source_ticks{{kind="{kind}"}} {controller.tick}\nsource_records{{kind="{kind}"}} {controller.produced}\n'

    # 接続専用領域に制限してファイルを排他的に作り、原子的に置き換える。
    @app.post(
        "/api/connection-files",
        summary='接続補助ファイルを配置',
        tags=['接続・公開設定'],
    )
    def upload(value: Upload):
        """相対名とBase64を含むJSONを受け付けます。デコード後1MiBまで。同名は置き換え、ファイルは権限600で保存します。"""
        folder = store.root / "connection-files"
        folder.mkdir(exist_ok=True, mode=0o700)
        target = (folder / value.name).resolve()
        if (
            not target.is_relative_to(folder.resolve())
            or ".." in Path(value.name).parts
        ):
            raise HTTPException(422, "相対パスを確認してください")
        try:
            data = base64.b64decode(value.content_base64, validate=True)
        except ValueError:
            raise HTTPException(422, "Base64が不正です") from None
        if len(data) > 1024**2:
            raise HTTPException(413, "ファイルは1MiB以下です")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temp = target.with_name(target.name + "." + secrets.token_hex(5))
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target)
        return {"name": value.name, "bytes": len(data), "permissions": "600"}

    # 取得認証後に、任意の配送状態で絞った最近のイベントを返す。
    @app.get(
        "/source/events",
        summary='最近のイベントを取得',
        tags=['公開データの取得'],
    )
    def events(request: Request, limit: int = 100, status: str | None = None):
        """新しい順に返します。limit は1〜1000、既定100件です。status は完全一致で、payload は文字列です。"""
        authorize(request)
        if not 1 <= limit <= 1000:
            raise HTTPException(422, "limitは1〜1000")
        with store.db() as db:
            where = " WHERE status=?" if status else ""
            args = [status, limit] if status else [limit]
            rows = db.execute(
                "SELECT seq,event_id,payload,status,created_at FROM events"
                + where
                + " ORDER BY seq DESC LIMIT ?",
                args,
            ).fetchall()
        return {"events": [dict(r) for r in rows]}

    # 取得認証後に、上限内のログ本文を時系列順のテキストとして返す。
    @app.get(
        "/source/logs/download",
        summary='ログをUTF-8テキストで取得',
        tags=['公開データの取得'],
        response_class=Response,
        responses={200: {'description': 'ログをUTF-8テキストで取得', 'content': {'text/plain': {'schema': {'type': 'string'}}}}},
    )
    def logs(request: Request, limit: int = 1000):
        """最後の指定件数を古い順に返します。limit は1〜10000、既定1000件です。"""
        authorize(request)
        if not 1 <= limit <= 10000:
            raise HTTPException(422, "limitは1〜10000")
        with store.db() as db:
            rows = db.execute(
                "SELECT payload FROM events ORDER BY seq DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return Response(
            "\n".join(r[0] for r in reversed(rows)) + "\n",
            media_type="text/plain; charset=utf-8",
        )

    # 識別タグの範囲と形式を確認し、バーコードまたはQRのPNGを返す。
    @app.get(
        "/source/labels/{number}.png",
        summary='標準タグのラベル画像を取得',
        tags=['公開データの取得'],
        response_class=Response,
        responses={200: {'description': '標準タグのラベル画像を取得', 'content': {'image/png': {'schema': {'type': 'string', 'format': 'binary'}}}}, 404: {'description': '指定したタグが見つかりません'}},
    )
    def label(request: Request, number: int, format: str = ""):
        """0始まりの番号を指定します。format は qr、code128、ean13 を選べ、空欄はひな型の設定に従います。"""
        authorize(request)
        if (
            kind != "identification"
            or not 0 <= number < controller.source_spec().identification.tags
        ):
            raise HTTPException(404, "タグがありません")
        import io

        options = controller.source_spec().identification
        mode = format or options.barcode
        output = io.BytesIO()
        text = f"TAG-{number:06d}"
        if mode == "qr":
            import qrcode

            qrcode.make(text).save(output, format="PNG")
        elif mode in {"code128", "ean13"}:
            import barcode
            from barcode.writer import ImageWriter

            value = (
                f"{490000000000 + number:012d}" if mode == "ean13" else text
            )
            barcode.get(mode, value, writer=ImageWriter()).write(output)
        else:
            raise HTTPException(422, "code128/ean13/qrから選択してください")
        return Response(output.getvalue(), media_type="image/png")

    if kind in {"api", "historian"}:
        from data_api import register_data_routes

        register_data_routes(app, controller, authorize)
    return app
