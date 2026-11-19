"""暗号化プロファイル、プリセット、生成履歴をSQLiteへ永続化する。"""

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
    """暗号化設定と生成データを同じ保存領域で管理する。

    暗号鍵とDBは対で保管する。DBだけ残り鍵がない場合は新しい鍵で上書きしない。
    """

    def __init__(self, root):
        """保存領域・暗号鍵・SQLite表を準備し、既存データの鍵欠落を拒否する。"""
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
        """WALとFULL同期を設定した接続を開き、取引終了後に必ず閉じる。

        with節が正常終了した場合に確定し、例外時はSQLiteの取引を巻き戻す。
        """
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
        """値が渡された場合は保存し、キーに対応するJSONを返す。

        Noneは読取指定として扱い、未登録のキーではNoneを返す。
        """
        with self.db() as c:
            if value is not None:
                c.execute(
                    "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, json.dumps(value)),
                )
            r = c.execute(
                "SELECT value FROM meta WHERE key=?", (key,)
            ).fetchone()
        return json.loads(r[0]) if r else None

    def profile(self, identity="default", revision=None):
        """指定リビジョンまたは最新のプロファイルを復号して返す。

        存在しないIDはKeyErrorとし、復号・モデル検証の失敗を隠さない。
        """
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
        """秘密値を除き、設定済みの秘密項目名だけを公開用辞書へ含める。"""
        d = p.model_dump(mode="json", exclude=SECRETS | {"clear_secrets"})
        d["configured_secrets"] = [k for k in SECRETS if getattr(p, k)]
        if revision:
            d["revision"] = revision
        return d

    def save_profile(self, p):
        """秘密値の維持・明示消去を区別し、新リビジョンとして暗号化保存する。

        接続先や認証の範囲が変わった場合は、旧秘密値を自動で引き継がない。
        """
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
                    (
                        p.id,
                        rev + 1,
                        self.fernet.encrypt(json.dumps(d).encode()),
                    ),
                )
            return self.public(saved, rev + 1)

    def profiles(self):
        """全IDの最新リビジョンを秘密値なしの公開形式で返す。"""
        with self.db() as c:
            ids = [
                r[0]
                for r in c.execute(
                    "SELECT DISTINCT id FROM profiles ORDER BY id"
                )
            ]
        return [self.public(*self.profile(i)) for i in ids]

    def save_preset(self, identity, spec):
        """検証済み設定をID単位で保存し、保存した内容を返す。"""
        with self.db() as c:
            c.execute(
                "INSERT INTO presets VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (identity, spec.model_dump_json()),
            )
        return {"id": identity, "spec": spec.model_dump(mode="json")}

    def presets(self):
        """保存済みプリセットをモデルで再検証し、ID順で返す。"""
        with self.db() as c:
            return [
                {
                    "id": r["id"],
                    "spec": Spec.model_validate_json(r["data"]).model_dump(
                        mode="json"
                    ),
                }
                for r in c.execute("SELECT * FROM presets ORDER BY id")
            ]

    def seed(self, path):
        """同名の保存済みプリセットを上書きせず、未登録JSONだけを取り込む。"""
        ids = {p["id"] for p in self.presets()}
        for file in sorted(Path(path).glob("*.json")):
            if file.stem not in ids:
                self.save_preset(
                    file.stem, Spec.model_validate_json(file.read_text())
                )

    def token(self, data):
        """カーソル本文をURL安全な形式に符号化し、HMAC署名を付ける。

        署名は改ざん検知であり暗号化ではないため、本文に秘密値を含めない。
        """
        raw = base64.urlsafe_b64encode(
            json.dumps(data, separators=(",", ":")).encode()
        ).rstrip(b"=")
        sig = hmac.new(self.key, raw, hashlib.sha256).digest()
        return (
            raw + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")
        ).decode()

    def untoken(self, token):
        """署名と有効期限を確認してカーソル本文を返す。

        期限切れはTimeoutError、不正形式や署名不一致はValueErrorで区別する。
        """
        try:
            raw, sig = token.encode().split(b".")
            expected = base64.urlsafe_b64encode(
                hmac.new(self.key, raw, hashlib.sha256).digest()
            ).rstrip(b"=")
            if not hmac.compare_digest(sig, expected):
                raise ValueError()
            d = json.loads(
                base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))
            )
            if d.get("exp", 0) < time.time():
                raise TimeoutError("カーソルが期限切れです")
            return d
        except TimeoutError:
            raise
        except Exception:
            raise ValueError("カーソルが不正です") from None

    def put(self, ds, res, rows, progress=None):
        """行の変更履歴と任意の進捗を同一取引で追記する。

        進捗だけ先に進めないことで、初期生成の再開位置と保存結果をそろえる。
        """
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
        """データセットとリソースの最新変更番号を返し、未登録なら0とする。"""
        with self.db() as c:
            return c.execute(
                "SELECT coalesce(max(rev),0) FROM changes WHERE ds=? AND res=?",
                (ds, res),
            ).fetchone()[0]
