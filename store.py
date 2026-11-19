"""Persistent encrypted profiles, editable presets and source data."""

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet
from models import Profile, Spec, SECRETS


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        key = self.root / "source.key"
        if not key.exists():
            if (self.root / "settings.sqlite3").exists():
                raise RuntimeError("暗号鍵をバックアップから復元してください")
            fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        self.key = key.read_bytes()
        self.fernet = Fernet(self.key)
        self.lock = threading.RLock()
        with self.db() as c:
            c.executescript(
                "CREATE TABLE IF NOT EXISTS profiles(id TEXT,revision INTEGER,data BLOB,PRIMARY KEY(id,revision));CREATE TABLE IF NOT EXISTS presets(id TEXT PRIMARY KEY,data TEXT);CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE IF NOT EXISTS changes(rev INTEGER PRIMARY KEY AUTOINCREMENT,ds TEXT,res TEXT,id TEXT,payload TEXT,changed_at TEXT,deleted INTEGER DEFAULT 0);CREATE INDEX IF NOT EXISTS changes_scope ON changes(ds,res,id,rev);CREATE INDEX IF NOT EXISTS changes_revision ON changes(ds,res,rev);CREATE TABLE IF NOT EXISTS samples(seq INTEGER PRIMARY KEY AUTOINCREMENT,ds TEXT,tag TEXT,ts REAL,value TEXT,quality TEXT);CREATE INDEX IF NOT EXISTS samples_time ON samples(ds,tag,ts,seq);CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,target TEXT,event_id TEXT,payload TEXT,status TEXT DEFAULT 'pending',created_at REAL, UNIQUE(target,event_id));"
            )
        (self.root / "settings.sqlite3").chmod(0o600)

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.root / "settings.sqlite3", timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
        try:
            with c:
                yield c
        finally:
            c.close()

    def meta(self, key, value=None):
        with self.db() as c:
            if value is not None:
                c.execute(
                    "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, json.dumps(value)),
                )
            r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else None

    def profile(self, identity="default", revision=None):
        with self.db() as c:
            r = c.execute(
                "SELECT revision,data FROM profiles WHERE id=?"
                + (" AND revision=?" if revision else "")
                + " ORDER BY revision DESC LIMIT 1",
                ([identity, revision] if revision else [identity]),
            ).fetchone()
        if not r:
            raise KeyError(identity)
        return Profile.model_validate_json(self.fernet.decrypt(r["data"])), r[
            "revision"
        ]

    def public(self, p, revision=None):
        d = p.model_dump(mode="json", exclude=SECRETS | {"clear_secrets"})
        d["configured_secrets"] = [k for k in SECRETS if getattr(p, k)]
        if revision:
            d["revision"] = revision
        return d

    def save_profile(self, p):
        with self.lock:
            try:
                old, rev = self.profile(p.id)
            except KeyError:
                old, rev = None, 0
            scope = [
                "auth_mode",
                "username",
                "opc_auth",
                "opc_username",
                "output",
                "host",
                "port",
                "url",
                "output_username",
            ]
            same = old is not None and all(
                getattr(old, k) == getattr(p, k) for k in scope
            )
            d = p.model_dump(mode="json", exclude=SECRETS)
            for k in SECRETS:
                v = getattr(p, k)
                if k in p.clear_secrets:
                    v = None
                elif v is None and same:
                    v = getattr(old, k)
                d[k] = v.get_secret_value() if v else None
            d["clear_secrets"] = []
            saved = Profile.model_validate(d)
            if saved.auth_mode == "basic" and not saved.password:
                raise ValueError("Basic認証のパスワードが必要です")
            if saved.auth_mode in {"bearer", "api_key"} and not saved.token:
                raise ValueError("トークンが必要です")
            with self.db() as c:
                c.execute(
                    "INSERT INTO profiles VALUES(?,?,?)",
                    (p.id, rev + 1, self.fernet.encrypt(json.dumps(d).encode())),
                )
            return self.public(saved, rev + 1)

    def profiles(self):
        with self.db() as c:
            ids = [
                r[0] for r in c.execute("SELECT DISTINCT id FROM profiles ORDER BY id")
            ]
        return [self.public(*self.profile(i)) for i in ids]

    def save_preset(self, identity, spec):
        with self.db() as c:
            c.execute(
                "INSERT INTO presets VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (identity, spec.model_dump_json()),
            )
        return {"id": identity, "spec": spec.model_dump(mode="json")}

    def presets(self):
        with self.db() as c:
            return [
                {
                    "id": r["id"],
                    "spec": Spec.model_validate_json(r["data"]).model_dump(mode="json"),
                }
                for r in c.execute("SELECT * FROM presets ORDER BY id")
            ]

    def seed(self, path):
        ids = {p["id"] for p in self.presets()}
        for file in sorted(Path(path).glob("*.json")):
            if file.stem not in ids:
                self.save_preset(file.stem, Spec.model_validate_json(file.read_text()))

    def token(self, data):
        raw = base64.urlsafe_b64encode(
            json.dumps(data, separators=(",", ":")).encode()
        ).rstrip(b"=")
        sig = hmac.new(self.key, raw, hashlib.sha256).digest()
        return (raw + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")).decode()

    def untoken(self, token):
        try:
            raw, sig = token.encode().split(b".")
            expected = base64.urlsafe_b64encode(
                hmac.new(self.key, raw, hashlib.sha256).digest()
            ).rstrip(b"=")
            if not hmac.compare_digest(sig, expected):
                raise ValueError()
            d = json.loads(base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4)))
            if d.get("exp", 0) < time.time():
                raise TimeoutError("カーソルが期限切れです")
            return d
        except TimeoutError:
            raise
        except Exception:
            raise ValueError("カーソルが不正です") from None

    def put(self, ds, res, rows, progress=None):
        with self.db() as c:
            c.executemany(
                "INSERT INTO changes(ds,res,id,payload,changed_at,deleted) VALUES(?,?,?,?,?,?)",
                [
                    (
                        ds,
                        res,
                        str(row["id"]),
                        json.dumps(row, ensure_ascii=False, allow_nan=False),
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        int(row.get("_deleted", False)),
                    )
                    for row in rows
                ],
            )
            if progress:
                c.execute(
                    "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (progress[0], json.dumps(progress[1])),
                )

    def maximum(self, ds, res):
        with self.db() as c:
            return c.execute(
                "SELECT coalesce(max(rev),0) FROM changes WHERE ds=? AND res=?",
                (ds, res),
            ).fetchone()[0]
