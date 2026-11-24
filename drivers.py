"""業務・履歴・イベントの生成処理を実行コントローラーへ接続する。

通信ライブラリは必要な経路で読み込み、送信完了の意味はプロトコルごとに異なる。
"""

import asyncio
import hashlib
import json
import logging
import logging.handlers
import os
import socket
import ssl
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import (
    Request,
    build_opener,
    ProxyHandler,
    HTTPSHandler,
    HTTPRedirectHandler,
)
from connection_security import connection_file
from generation import generate_record, record_key, render


class NoRedirect(HTTPRedirectHandler):
    """HTTP送信先の自動転送を禁止するハンドラー。"""

    def redirect_request(self, *args, **kwargs):
        """転送用リクエストを作らず、元の送信先以外へ追従させない。"""
        return None


class Base:
    """コントローラー参照とプロトコル情報を共有する最小基底ドライバー。"""

    def __init__(self, c):
        """コントローラー参照と公開用プロトコル情報の格納先を設定する。"""
        self.c = c
        self.information = {}

    async def start(self):
        """開始時に必要な処理を派生ドライバーで実装するための空のフック。"""
        pass

    async def close(self):
        """終了時の解放処理を派生ドライバーで実装するための空のフック。"""
        pass


class BusinessDriver(Base):
    """REST・限定OData取得に使う業務レコードと変更履歴を生成する。"""

    async def start(self):
        """保存済み進捗から初期レコードを500件ずつ生成して保存する。

        各バッチで停止要求と資源制限を確認し、行と進捗を一緒に確定する。
        """
        self.information = {
            "rest": "/source/rest/{collection}",
            "odata": "/source/odata/{collection}",
            "delta": "/source/rest/{collection}/delta",
            "odata_scope": "$top/$skip/$filter comparisons and/or/$orderby/$select/$skiptoken; not full OData",
        }
        for res in self.c.spec.business.resources:
            progress_key = "init-" + self.c.ds + "-" + res.name
            beginning = self.c.store.meta(progress_key) or 0
            g = res.generator or self.c.spec.generator
            for start in range(beginning, res.rows, 500):
                if self.c.stop_event.is_set():
                    return
                self.c.guard()
                rows = []
                for i in range(start, min(start + 500, res.rows)):
                    row = generate_record(g, g.start_sequence + i)
                    row["id"] = record_key(g, g.start_sequence + i)
                    rows.append(row)
                self.c.store.put(
                    self.c.ds,
                    res.name,
                    rows,
                    progress=(progress_key, min(start + 500, res.rows)),
                )

    async def step(self, tick):
        """更新対象を巡回し、元のIDを維持した変更行と指定周期の削除行を追記する。"""
        opts = self.c.spec.business
        for res in opts.resources:
            g = res.generator or self.c.spec.generator
            rows = []
            for j in range(min(opts.updates_per_tick, res.rows)):
                index = (tick * opts.updates_per_tick + j) % res.rows
                row = generate_record(
                    g.model_copy(
                        update={"seed": (g.seed + tick + 1) % 2147483647}
                    ),
                    g.start_sequence + index,
                )
                row["id"] = record_key(g, g.start_sequence + index)
                rows.append(row)
                self.c.observe({"collection": res.name, **row})
            if (
                opts.delete_every_ticks
                and tick
                and tick % opts.delete_every_ticks == 0
            ):
                index = tick % res.rows
                rows.append(
                    {
                        "id": record_key(g, g.start_sequence + index),
                        "_deleted": True,
                    }
                )
            if rows:
                self.c.store.put(self.c.ds, res.name, rows)


class HistorianDriver(Base):
    """時刻基準と生成位置を永続化して履歴サンプルを継続生成する。"""

    async def start(self):
        """保存した時刻基準・位置を復元し、不足する初期履歴を補う。"""
        self.options = self.c.spec.history
        self.anchor = self.c.store.meta("history-anchor-" + self.c.ds)
        if self.anchor is None:
            self.anchor = (
                time.time()
                - self.options.initial_samples * self.options.sample_seconds
            )
            self.c.store.meta("history-anchor-" + self.c.ds, self.anchor)
        self.index = self.c.store.meta("history-index-" + self.c.ds) or 0
        while self.index < self.options.initial_samples:
            if self.c.stop_event.is_set():
                return
            if self.index % 500 == 0:
                self.c.guard()
            self.write(self.index, observe=False)
            self.index += 1
        self.information = {
            "raw": "/source/history/raw",
            "aggregate": "/source/history/aggregate",
            "tags": "/source/history/tags",
            "interface": "REST; not PI/Influx wire protocol",
        }

    def write(self, index, observe=True):
        """欠測・時刻ずれ・品質異常を反映し、サンプルと次位置を同一取引で保存する。"""
        opts = self.options
        missing = opts.missing_every and (index + 1) % opts.missing_every == 0
        ts = self.anchor + index * opts.sample_seconds
        if opts.shift_every and (index + 1) % opts.shift_every == 0:
            ts += opts.timestamp_shift_seconds
        rows = []
        for device in range(0 if missing else opts.devices):
            record = self.c.record(index * opts.devices + device)
            if opts.source_time_field and record.get(opts.source_time_field):
                ts = datetime.fromisoformat(
                    record[opts.source_time_field]
                ).timestamp()
            for field in opts.tags:
                value = record.get(field)
                quality = (
                    opts.quality
                    if opts.bad_every and (index + 1) % opts.bad_every == 0
                    else "Good"
                )
                if value is None:
                    quality = "Bad"
                elif isinstance(value, str):
                    try:
                        value = float(value)
                    except ValueError:
                        quality = "Bad"
                tag = f"device-{device + 1:03d}.{field}"
                rows.append(
                    (
                        self.c.ds,
                        tag,
                        ts,
                        json.dumps(value, allow_nan=False),
                        quality,
                    )
                )
                if observe:
                    self.c.observe(
                        {
                            "tag": tag,
                            "timestamp": datetime.fromtimestamp(
                                ts, timezone.utc
                            ).isoformat(),
                            "value": value,
                            "quality": quality,
                        }
                    )
        with self.c.store.db() as db:
            db.executemany(
                "INSERT INTO samples(ds,tag,ts,value,quality) VALUES(?,?,?,?,?)",
                rows,
            )
            db.execute(
                "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("history-index-" + self.c.ds, json.dumps(index + 1)),
            )

    async def step(self, tick):
        """次の履歴を生成し、100tickごとに保持期間を過ぎた同一データセットを削除する。"""
        self.write(self.index)
        self.index += 1
        if tick % 100 == 0:
            with self.c.store.db() as db:
                db.execute(
                    "DELETE FROM samples WHERE ds=? AND ts<?",
                    (
                        self.c.ds,
                        time.time() - self.options.retention_days * 86400,
                    ),
                )


class DeliveryLogHandler(logging.handlers.RotatingFileHandler):
    """ファイル書き込み失敗を、保存済みの未配送キューへ伝える。"""

    def handleError(self, record):
        """本文を標準エラーへ出さず、元の例外を配送ループへ返す。"""
        raise


def syslog_tcp_frame(data, framing):
    """文字数でなくUTF-8のバイト数でTCP/TLSのメッセージ境界を組み立てる。"""
    if framing == "octet_counting":
        return str(len(data)).encode("ascii") + b" " + data
    return data + b"\n"


class EventDriver(Base):
    """ログ・識別イベントを永続キューに保存して設定先へ配送する。"""

    async def start(self):
        """配送先識別子とデータセット別連番を復元し、必要なら回転ログを開く。"""
        self.target = hashlib.sha256(
            json.dumps(
                {
                    k: getattr(self.c.profile, k)
                    for k in [
                        "id",
                        "output",
                        "host",
                        "port",
                        "url",
                        "topic",
                        "output_username",
                    ]
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        self.index_key = "event-index-" + self.c.ds
        # 同じ配送先でも、新しいデータセットには独立した論理時計を持たせる。
        self.index = self.c.store.meta(self.index_key) or 0
        self.mqtt = None
        self.handler = None
        if self.c.kind == "logs" and self.c.profile.output == "file":
            folder = Path(
                os.environ.get("LOG_DIR", str(self.c.store.root / "logs"))
            )
            folder.mkdir(parents=True, exist_ok=True)
            self.handler = DeliveryLogHandler(
                folder / "events.log",
                maxBytes=self.c.spec.logs.rotate_mb * 1024**2,
                backupCount=self.c.spec.logs.backups,
                encoding="utf-8",
            )
            self.handler.setFormatter(logging.Formatter("%(message)s"))
        self.information = {
            "events": "/source/events",
            "delivery_boundary": "UDP/TCP: socket accepted; TLS/HTTP/MQTT: transport-specific ack; file: local flush; capture: no external send",
        }

    def event(self, sequence, *, trace=None):
        """共通生成行に識別イベントのID・読取機・バーコード等を補う。

        明示された既存項目は維持し、異常周期に当たる識別子だけを置き換える。
        """
        if trace is None:
            row = self.c.record(sequence)
        else:
            g = self.c.spec.generator
            row = generate_record(g, g.start_sequence + sequence, trace=trace)
        row.setdefault(
            "event_id",
            row.get("id", record_key(self.c.spec.generator, sequence)),
        )
        if self.c.kind == "identification":
            opts = self.c.spec.identification
            index = sequence % opts.tags
            reader = (sequence // opts.tags) % len(opts.readers)
            row.setdefault("tag_id", f"TAG-{index:06d}")
            row.setdefault("epc", f"{0x300000000000000000000000 + index:024X}")
            row.setdefault("reader_id", opts.readers[reader])
            row.setdefault(
                "operator_id", opts.operators[index % len(opts.operators)]
            )
            row.setdefault("event_type", "passage")
            row.setdefault(
                "direction",
                "IN"
                if reader == 0
                else "OUT"
                if reader == len(opts.readers) - 1
                else "MOVE",
            )
            row.setdefault("lot_id", f"LOT-{index // 10:05d}")
            base = f"{490000000000 + index:012d}"
            digit = (
                -sum(
                    int(v) * (1 if i % 2 == 0 else 3)
                    for i, v in enumerate(base)
                )
            ) % 10
            row.setdefault("barcode", base + str(digit))
            if (
                opts.wrong_reader_every
                and (sequence + 1) % opts.wrong_reader_every == 0
            ):
                row["reader_id"] = "UNKNOWN-READER"
            if (
                opts.unauthorized_every
                and (sequence + 1) % opts.unauthorized_every == 0
            ):
                row["operator_id"] = "UNREGISTERED-WORKER"
        return row

    def log_message(self, row, sequence, *, at=None):
        """生成行を指定のJSONL・平文・Syslog書式の一メッセージに整形する。"""
        opts = self.c.spec.logs
        message = render(opts.message_template, {**row, "sequence": sequence})
        if opts.format == "jsonl":
            return json.dumps(
                {
                    "timestamp": (at or datetime.now(timezone.utc)).isoformat(),
                    "severity": opts.severity,
                    "facility": opts.facility,
                    "host": opts.hostname,
                    "app": opts.app_name,
                    **row,
                    "message": message,
                },
                ensure_ascii=False,
            )
        if opts.format == "plain":
            return (at or datetime.now(timezone.utc)).isoformat() + " " + message
        priority = opts.facility * 8 + opts.severity
        if opts.format == "rfc3164":
            return (
                f"<{priority}>"
                + (at or datetime.now()).strftime("%b %d %H:%M:%S")
                + " "
                + opts.hostname
                + " "
                + opts.app_name
                + ": "
                + message
            )
        return (
            f"<{priority}>1 "
            + (at or datetime.now(timezone.utc)).isoformat().replace("+00:00", "Z")
            + " "
            + opts.hostname
            + " "
            + opts.app_name
            + " - EVENT - \ufeff"
            + message
        )

    def log_payload(self, row, sequence, *, at=None):
        """配送時と同じ破損設定を、本文見本にも反映する。"""
        payload = self.log_message(row, sequence, at=at)
        options = self.c.spec.logs
        malformed = bool(
            options.malformed_every and (sequence + 1) % options.malformed_every == 0
        )
        if malformed:
            payload = "BROKEN-HEADER " + payload[8:]
        return payload, malformed

    async def step(self, tick):
        """欠落・重複・破損を模擬してイベントと次連番を保存し、配送を試みる。"""
        for j in range(self.c.spec.batch_size):
            sequence = self.index
            self.index += 1
            opts = (
                self.c.spec.identification
                if self.c.kind == "identification"
                else self.c.spec.logs
            )
            if (
                self.c.kind == "identification"
                and opts.drop_every
                and (sequence + 1) % opts.drop_every == 0
            ):
                self.c.store.meta(self.index_key, self.index)
                continue
            row = self.event(sequence)
            payload = (
                self.log_payload(row, sequence)[0]
                if self.c.kind == "logs"
                else json.dumps(row, ensure_ascii=False, allow_nan=False)
            )
            entries = [(row["event_id"], payload)]
            if (
                opts.duplicate_every
                and (sequence + 1) % opts.duplicate_every == 0
            ):
                entries.append((row["event_id"] + "-duplicate", payload))
            with self.c.store.db() as db:
                db.executemany(
                    "INSERT OR IGNORE INTO events(target,event_id,payload,status,created_at) VALUES(?,?,?,?,?)",
                    [
                        (
                            self.target,
                            key,
                            body,
                            "captured"
                            if self.c.profile.output == "capture"
                            else "pending",
                            time.time(),
                        )
                        for key, body in entries
                    ],
                )
                db.execute(
                    "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (self.index_key, json.dumps(self.index)),
                )
            self.c.observe(row)
        await self.flush()

    def context(self):
        """出力用CAを読み込み、明示された検証設定でTLSコンテキストを作る。"""
        p = self.c.profile
        ctx = ssl.create_default_context(
            cafile=connection_file(p.ca_file) if p.ca_file else None
        )
        if not p.tls_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def send(self, payload):
        """出力方式に応じて一件を送信またはローカルへ書き込む。

        UDP/TCPの成功は受信アプリの処理完了を意味しない。HTTPは受付応答、MQTTはQoS1 ACKを確認する。
        """
        p = self.c.profile
        data = payload.encode()
        if p.output == "file":
            self.handler.emit(
                logging.LogRecord(
                    "factory", logging.INFO, "", 0, payload, (), None
                )
            )
            self.handler.flush()
            return
        if p.output == "udp":
            if len(data) > 65000:
                raise ValueError("UDPログは65000 bytes以下にしてください")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(data, (p.host, p.port or 514))
            return
        if p.output in {"tcp", "tls"}:
            wire = syslog_tcp_frame(data, self.c.spec.logs.tcp_framing)
            with socket.create_connection(
                (p.host, p.port or (6514 if p.output == "tls" else 514)),
                timeout=p.timeout_seconds,
            ) as sock:
                if p.output == "tls":
                    with self.context().wrap_socket(
                        sock, server_hostname=p.host
                    ) as secure:
                        secure.sendall(wire)
                else:
                    sock.sendall(wire)
            return
        if p.output == "http":
            headers = {"Content-Type": "application/json"}
            if p.output_token:
                headers["Authorization"] = (
                    "Bearer " + p.output_token.get_secret_value()
                )
            opener = build_opener(
                ProxyHandler({}),
                HTTPSHandler(context=self.context()),
                NoRedirect(),
            )
            with opener.open(
                Request(p.url, data=data, headers=headers),
                timeout=p.timeout_seconds,
            ) as r:
                if r.status not in {200, 201, 202, 204}:
                    raise RuntimeError("HTTP rejected")
                body = r.read(65536)
                if body:
                    try:
                        ack = json.loads(body)
                    except (ValueError, UnicodeError):
                        ack = {}
                    if isinstance(ack, dict) and (
                        ack.get("failed")
                        or ack.get("errors")
                        or ("accepted" in ack and ack["accepted"] != 1)
                    ):
                        raise RuntimeError("HTTP partial rejection")
            return
        if p.output == "mqtt":
            if self.mqtt is None:
                import paho.mqtt.client as mqtt

                self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
                if p.output_username:
                    self.mqtt.username_pw_set(
                        p.output_username,
                        p.output_password.get_secret_value()
                        if p.output_password
                        else None,
                    )
                if p.mqtt_tls:
                    self.mqtt.tls_set_context(self.context())
                self.mqtt.connect(
                    p.host, p.port or (8883 if p.mqtt_tls else 1883), 30
                )
                self.mqtt.loop_start()
            ack = self.mqtt.publish(p.topic, data, qos=1)
            ack.wait_for_publish(timeout=p.timeout_seconds)
            if not ack.is_published():
                raise TimeoutError("MQTT acknowledgement timeout")

    async def flush(self):
        """未配送の最大100件を順に送り、失敗時はその位置で中断する。

        成功後に配送済みへ更新するため、送信直後の中断では再送が起こり得る。
        """
        if self.c.profile.output == "capture":
            return
        with self.c.store.db() as db:
            rows = db.execute(
                "SELECT * FROM events WHERE target=? AND status='pending' ORDER BY seq LIMIT 100",
                (self.target,),
            ).fetchall()
        for row in rows:
            try:
                await asyncio.to_thread(self.send, row["payload"])
            except Exception as exc:
                self.information["last_delivery_error"] = type(exc).__name__
                break
            with self.c.store.db() as db:
                db.execute(
                    "UPDATE events SET status='delivered' WHERE seq=?",
                    (row["seq"],),
                )

    async def close(self):
        """回転ログとMQTT接続・ネットワークループを終了する。"""
        if self.handler:
            self.handler.close()
        if self.mqtt:
            self.mqtt.disconnect()
            self.mqtt.loop_stop()


def create_driver(c):
    """アプリの種類からドライバーを選び、設備ライブラリは必要時だけ読み込む。"""
    if c.kind == "equipment":
        from equipment import EquipmentDriver

        return EquipmentDriver(c)
    return {
        "api": BusinessDriver,
        "historian": HistorianDriver,
        "logs": EventDriver,
        "identification": EventDriver,
    }[c.kind](c)
