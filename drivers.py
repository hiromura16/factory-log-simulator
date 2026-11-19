"""Source drivers. Network libraries are imported only by the relevant app."""

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
    def redirect_request(self, *args, **kwargs):
        return None


class Base:
    def __init__(self, c):
        self.c = c
        self.information = {}

    async def start(self):
        pass

    async def close(self):
        pass


class BusinessDriver(Base):
    async def start(self):
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
        opts = self.c.spec.business
        for res in opts.resources:
            g = res.generator or self.c.spec.generator
            rows = []
            for j in range(min(opts.updates_per_tick, res.rows)):
                index = (tick * opts.updates_per_tick + j) % res.rows
                row = generate_record(
                    g.model_copy(update={"seed": (g.seed + tick + 1) % 2147483647}),
                    g.start_sequence + index,
                )
                row["id"] = record_key(g, g.start_sequence + index)
                rows.append(row)
                self.c.observe({"collection": res.name, **row})
            if opts.delete_every_ticks and tick and tick % opts.delete_every_ticks == 0:
                index = tick % res.rows
                rows.append(
                    {"id": record_key(g, g.start_sequence + index), "_deleted": True}
                )
            if rows:
                self.c.store.put(self.c.ds, res.name, rows)


class HistorianDriver(Base):
    async def start(self):
        self.options = self.c.spec.history
        self.anchor = self.c.store.meta("history-anchor-" + self.c.ds)
        if self.anchor is None:
            self.anchor = (
                time.time() - self.options.initial_samples * self.options.sample_seconds
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
        opts = self.options
        missing = opts.missing_every and (index + 1) % opts.missing_every == 0
        ts = self.anchor + index * opts.sample_seconds
        if opts.shift_every and (index + 1) % opts.shift_every == 0:
            ts += opts.timestamp_shift_seconds
        rows = []
        for device in range(0 if missing else opts.devices):
            record = self.c.record(index * opts.devices + device)
            if opts.source_time_field and record.get(opts.source_time_field):
                ts = datetime.fromisoformat(record[opts.source_time_field]).timestamp()
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
                    (self.c.ds, tag, ts, json.dumps(value, allow_nan=False), quality)
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
                "INSERT INTO samples(ds,tag,ts,value,quality) VALUES(?,?,?,?,?)", rows
            )
            db.execute(
                "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("history-index-" + self.c.ds, json.dumps(index + 1)),
            )

    async def step(self, tick):
        self.write(self.index)
        self.index += 1
        if tick % 100 == 0:
            with self.c.store.db() as db:
                db.execute(
                    "DELETE FROM samples WHERE ds=? AND ts<?",
                    (self.c.ds, time.time() - self.options.retention_days * 86400),
                )


class EventDriver(Base):
    async def start(self):
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
        # A new dataset has its own logical clock, even on the same destination.
        self.index = self.c.store.meta(self.index_key) or 0
        self.mqtt = None
        self.handler = None
        if self.c.kind == "logs" and self.c.profile.output == "file":
            folder = Path(os.environ.get("LOG_DIR", str(self.c.store.root / "logs")))
            folder.mkdir(parents=True, exist_ok=True)
            self.handler = logging.handlers.RotatingFileHandler(
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

    def event(self, sequence):
        row = self.c.record(sequence)
        row.setdefault(
            "event_id", row.get("id", record_key(self.c.spec.generator, sequence))
        )
        if self.c.kind == "identification":
            opts = self.c.spec.identification
            index = sequence % opts.tags
            reader = (sequence // opts.tags) % len(opts.readers)
            row.setdefault("tag_id", f"TAG-{index:06d}")
            row.setdefault("epc", f"{0x300000000000000000000000 + index:024X}")
            row.setdefault("reader_id", opts.readers[reader])
            row.setdefault("operator_id", opts.operators[index % len(opts.operators)])
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
                -sum(int(v) * (1 if i % 2 == 0 else 3) for i, v in enumerate(base))
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

    def log_message(self, row, sequence):
        opts = self.c.spec.logs
        message = render(opts.message_template, {**row, "sequence": sequence})
        if opts.format == "jsonl":
            return json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
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
            return datetime.now(timezone.utc).isoformat() + " " + message
        priority = opts.facility * 8 + opts.severity
        if opts.format == "rfc3164":
            return (
                f"<{priority}>"
                + datetime.now().strftime("%b %d %H:%M:%S")
                + " "
                + opts.hostname
                + " "
                + opts.app_name
                + ": "
                + message
            )
        return (
            f"<{priority}>1 "
            + datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            + " "
            + opts.hostname
            + " "
            + opts.app_name
            + " - EVENT - \ufeff"
            + message
        )

    async def step(self, tick):
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
                self.log_message(row, sequence)
                if self.c.kind == "logs"
                else json.dumps(row, ensure_ascii=False, allow_nan=False)
            )
            if (
                self.c.kind == "logs"
                and opts.malformed_every
                and (sequence + 1) % opts.malformed_every == 0
            ):
                payload = "BROKEN-HEADER " + payload[8:]
            entries = [(row["event_id"], payload)]
            if opts.duplicate_every and (sequence + 1) % opts.duplicate_every == 0:
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
        p = self.c.profile
        ctx = ssl.create_default_context(
            cafile=connection_file(p.ca_file) if p.ca_file else None
        )
        if not p.tls_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def send(self, payload):
        p = self.c.profile
        data = payload.encode()
        if p.output == "file":
            self.handler.emit(
                logging.LogRecord("factory", logging.INFO, "", 0, payload, (), None)
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
            wire = (
                (str(len(data)).encode() + b" " + data)
                if self.c.spec.logs.tcp_framing == "octet_counting"
                else data + b"\n"
            )
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
                headers["Authorization"] = "Bearer " + p.output_token.get_secret_value()
            opener = build_opener(
                ProxyHandler({}), HTTPSHandler(context=self.context()), NoRedirect()
            )
            with opener.open(
                Request(p.url, data=data, headers=headers), timeout=p.timeout_seconds
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
                self.mqtt.connect(p.host, p.port or (8883 if p.mqtt_tls else 1883), 30)
                self.mqtt.loop_start()
            ack = self.mqtt.publish(p.topic, data, qos=1)
            ack.wait_for_publish(timeout=p.timeout_seconds)
            if not ack.is_published():
                raise TimeoutError("MQTT acknowledgement timeout")

    async def flush(self):
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
                    "UPDATE events SET status='delivered' WHERE seq=?", (row["seq"],)
                )

    async def close(self):
        if self.handler:
            self.handler.close()
        if self.mqtt:
            self.mqtt.disconnect()
            self.mqtt.loop_stop()


def create_driver(c):
    if c.kind == "equipment":
        from equipment import EquipmentDriver

        return EquipmentDriver(c)
    return {
        "api": BusinessDriver,
        "historian": HistorianDriver,
        "logs": EventDriver,
        "identification": EventDriver,
    }[c.kind](c)
