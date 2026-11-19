"""Source studio with generic schema forms and durable configuration."""

import base64
import hmac
import os
import re
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from models import Profile, Spec, TITLES, SECRETS
from generation import generate_record, sample_offsets, validate_generation
from store import Store
from controller import Controller


class Upload(BaseModel):
    name: str = Field(
        pattern=r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+){0,3}$", max_length=160
    )
    content_base64: str = Field(max_length=1500000)


def schemas(kind):
    from helptext import HELP

    result = {"spec": Spec.model_json_schema(), "profile": Profile.model_json_schema()}
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
        "auth_mode": "noneは取得用APIの認証なし、basicはユーザーとパスワード、bearerはAuthorization: Bearer、api_keyはX-API-Key。管理画面はログイン不要です。",
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
                source = prior.get(name, {}).get("properties", {}).get(field, {})
                if annotation in source:
                    prop[annotation] = source[annotation]
    result["spec"]["$defs"]["FieldRule"]["properties"]["primary_key"]["ui_hidden"] = (
        True
    )
    gen = result["spec"]["$defs"]["RunSpec"]["properties"]
    visible = {"run_key", "seed", "parameters", "fields", "anomalies", "start_sequence"}
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
        "logs": {"output", "host", "port", "tls_verify", "ca_file", "timeout_seconds"},
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
    root = Path(__file__).resolve().parent
    store = Store(os.environ.get("DATA_DIR", "./data"))
    controller = Controller(kind, store)
    try:
        store.profile()
    except KeyError:
        store.save_profile(Profile(output="file" if kind == "logs" else "capture"))
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
                        id=identity, name=label, opc_enabled=opc, modbus_enabled=modbus
                    )
                )
    store.seed(root / "presets")

    @asynccontextmanager
    async def lifespan(app):
        desired = store.meta("desired")
        if desired and desired.get("running") and desired.get("spec"):
            controller.start(
                Spec.model_validate(desired["spec"]), desired.get("revision")
            )
        elif desired is None and os.environ.get("AUTO_START") == "1":
            defaults = next(iter(store.presets()), None)
            controller.start(
                Spec.model_validate(defaults["spec"]) if defaults else Spec()
            )
        yield
        # Shutdown preserves the user's desired running/stopped state.
        controller.stop_event.set()
        if controller.thread:
            await __import__("asyncio").to_thread(controller.thread.join, 15)

    app = FastAPI(title=TITLES[kind], lifespan=lifespan)
    app.state.controller = controller
    app.state.store = store

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse(
            {
                "detail": [
                    {"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ]
            },
            422,
        )

    @app.exception_handler(ValueError)
    async def invalid_value(request, exc):
        return JSONResponse({"detail": str(exc)}, 422)

    @app.middleware("http")
    async def protect(request, call_next):
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
                return JSONResponse({"detail": "application/jsonが必要です"}, 415)
            if len(await request.body()) > 2 * 1024**2:
                return JSONResponse({"detail": "JSONは2MiB以下にしてください"}, 413)
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
        p = controller.profile or store.profile()[0]
        mode = p.auth_mode
        ok = mode == "none"
        if mode == "basic":
            try:
                ok = (
                    bool(p.password)
                    and request.headers.get("authorization", "").startswith("Basic ")
                    and hmac.compare_digest(
                        base64.b64decode(
                            request.headers.get("authorization", "")[6:], validate=True
                        ),
                        (p.username + ":" + p.password.get_secret_value()).encode(),
                    )
                )
            except Exception:
                ok = False
        elif mode == "bearer":
            ok = bool(p.token) and hmac.compare_digest(
                request.headers.get("authorization", ""),
                "Bearer " + p.token.get_secret_value(),
            )
        elif mode == "api_key":
            ok = bool(p.token) and hmac.compare_digest(
                request.headers.get("x-api-key", ""), p.token.get_secret_value()
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

    @app.get("/")
    def index():
        return FileResponse(root / "static/index.html")

    @app.get("/healthz")
    def health():
        return {"status": "ok", "service": kind, "version": "0.1.0"}

    @app.get("/api/info")
    def info():
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

    @app.get("/api/state")
    def state():
        return controller.snapshot()

    @app.get("/api/profiles")
    def profiles():
        return {"profiles": store.profiles()}

    @app.post("/api/profiles")
    def profile(p: Profile):
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
                raise HTTPException(422, "認証を含まないHTTP(S) URLを指定してください")
        if kind == "logs" and p.output not in {"capture", "file", "udp", "tcp", "tls"}:
            raise HTTPException(
                422, "ログはfile/capture/UDP/TCP/TLSから選択してください"
            )
        if kind == "identification" and p.output not in {"capture", "mqtt", "http"}:
            raise HTTPException(
                422, "識別イベントはcapture/MQTT/HTTPから選択してください"
            )
        return store.save_profile(p)

    @app.get("/api/presets")
    def presets():
        return {"presets": store.presets()}

    @app.post("/api/presets/{identity}")
    def preset(identity: str, spec: Spec):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", identity):
            raise HTTPException(422, "プリセットIDを確認してください")
        validate_generation(spec.generator)
        return store.save_preset(identity, spec)

    @app.post("/api/preview")
    def preview(spec: Spec):
        validate_generation(spec.generator)
        offsets = sorted({0, 1, 2, *sample_offsets(spec.generator)})[:12]
        records = []
        hits = []
        for offset in offsets:
            trace = []
            row = generate_record(
                spec.generator, spec.generator.start_sequence + offset, trace=trace
            )
            if kind in {"logs", "identification"}:
                from drivers import EventDriver

                preview_controller = Controller(kind, store)
                preview_controller.spec = spec
                driver = EventDriver(preview_controller)
                row = driver.event(offset)
                if kind == "logs":
                    row["_formatted_log"] = driver.log_message(row, offset)
            records.append(row)
            hits.append(trace)
        return {
            "records": records,
            "anomaly_hits": hits,
            "sequences": offsets,
            "writes": False,
            "validated_spec": spec.model_dump(mode="json"),
        }

    @app.post("/api/start")
    def start(spec: Spec):
        try:
            return controller.start(spec)
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from None

    @app.post("/api/stop")
    def stop():
        return controller.stop()

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        return f'source_ticks{{kind="{kind}"}} {controller.tick}\nsource_records{{kind="{kind}"}} {controller.produced}\n'

    @app.post("/api/connection-files")
    def upload(value: Upload):
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

    @app.get("/source/events")
    def events(request: Request, limit: int = 100, status: str | None = None):
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

    @app.get("/source/logs/download")
    def logs(request: Request, limit: int = 1000):
        authorize(request)
        if not 1 <= limit <= 10000:
            raise HTTPException(422, "limitは1〜10000")
        with store.db() as db:
            rows = db.execute(
                "SELECT payload FROM events ORDER BY seq DESC LIMIT ?", (limit,)
            ).fetchall()
        return Response(
            "\n".join(r[0] for r in reversed(rows)) + "\n",
            media_type="text/plain; charset=utf-8",
        )

    @app.get("/source/labels/{number}.png")
    def label(request: Request, number: int, format: str = ""):
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

            value = f"{490000000000 + number:012d}" if mode == "ean13" else text
            barcode.get(mode, value, writer=ImageWriter()).write(output)
        else:
            raise HTTPException(422, "code128/ean13/qrから選択してください")
        return Response(output.getvalue(), media_type="image/png")

    if kind in {"api", "historian"}:
        from data_api import register_data_routes

        register_data_routes(app, controller, authorize)
    return app
