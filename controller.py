"""単一実行の開始・停止・資源制限とバックグラウンド処理を管理する。"""

import asyncio
import collections
import hashlib
import json
import os
import shutil
import threading
import time
from pathlib import Path
from models import Spec
from api_support import display_location, history_error
from generation import GenerationError, generate_record
from validation import validate_source_spec


class Controller:
    """生成設定・永続状態・プロトコルドライバーを一つの実行として管理する。"""

    def __init__(self, kind, store):
        """未実行状態と停止通知、状態参照用の再入可能ロックを用意する。"""
        self.kind, self.store = kind, store
        self.thread = None
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.recent = collections.deque(maxlen=100)
        self.status = "stopped"
        self.tick = 0
        self.produced = 0
        self.error = None
        self.requests = 0
        self.driver = None
        self.spec = None
        self.profile = None
        self.ds = ""
        self.started = 0

    def snapshot(self):
        """ロック中に状態を読み、直近30件と経過時間を返す。"""
        with self.lock:
            return {
                "status": self.status,
                "tick": self.tick,
                "produced": self.produced,
                "requests": self.requests,
                "error": self.error,
                "error_message": history_error(self.error),
                "dataset_id": self.ds,
                "recent": list(self.recent)[-30:],
                "elapsed_seconds": round(time.time() - self.started, 2)
                if self.started
                else 0,
                "spec": self.spec.model_dump(mode="json")
                if self.spec
                else None,
                "protocols": getattr(self.driver, "information", {}),
            }

    def start(self, spec, revision=None):
        """設定と認証要件を検証し、再開用設定を保存して実行スレッドを開始する。

        二重起動は拒否する。データセット識別子から表示名・説明を除き、同じ生成条件を追跡する。
        """
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise RuntimeError("実行中です。設定変更前に停止してください")
            validate_source_spec(self.kind, spec)
            profile, revision = self.store.profile(spec.profile_id, revision)
            if profile.auth_mode == "basic" and not profile.password:
                raise ValueError("取得APIのBasic認証パスワードが必要です")
            if (
                profile.auth_mode in {"bearer", "api_key"}
                and not profile.token
            ):
                raise ValueError("取得APIの認証トークンが必要です")
            if (
                self.kind == "equipment"
                and profile.opc_auth == "username"
                and not profile.opc_password
            ):
                raise ValueError("OPC UAパスワードが必要です")
            if (
                self.kind == "equipment"
                and profile.opc_auth == "username"
                and profile.opc_security != "sign_encrypt"
            ):
                raise ValueError(
                    "OPC UAユーザー名認証にはSignAndEncryptを指定してください"
                )
            self.spec, self.profile = spec, profile
            self.tick = 0
            self.produced = 0
            self.requests = 0
            self.error = None
            self.recent.clear()
            self.status = "starting"
            self.started = time.time()
            self.stop_event = threading.Event()
            self.ds = hashlib.sha256(
                json.dumps(
                    {
                        "kind": self.kind,
                        "generator": spec.generator.model_dump(
                            mode="json", exclude={"name", "description"}
                        ),
                        "resources": [
                            r.model_dump(mode="json")
                            for r in spec.business.resources
                        ],
                        "history": spec.history.model_dump(mode="json"),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:20]
            self.store.meta(
                "desired",
                {
                    "running": True,
                    "spec": spec.model_dump(mode="json"),
                    "revision": revision,
                },
            )
            self.thread = threading.Thread(
                target=lambda: asyncio.run(self.run()), daemon=True
            )
            self.thread.start()
        return self.snapshot()

    def stop(self):
        """停止を要求して希望状態を保存し、最大15秒待つ。

        スレッドが残る場合はstoppingとし、停止完了を装わない。
        """
        with self.lock:
            self.stop_event.set()
            desired = self.store.meta("desired")
            if desired:
                # 停止を繰り返しても、前回の公開設定と版を保持する。
                self.store.meta("desired", {**desired, "running": False})
            thread = self.thread
        if thread:
            thread.join(timeout=15)
            with self.lock:
                if self.thread is thread and thread.is_alive():
                    self.status = "stopping"
        return self.snapshot()

    def guard(self):
        """空きディスク・利用可能メモリ・データ領域上限を検査する。

        不足時はRuntimeErrorで生成を止め、既存データを削除しない。
        """
        if shutil.disk_usage(self.store.root).free < 2 * 1024**3:
            raise RuntimeError("disk_space_low")
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:") and int(line.split()[1]) < int(
                float(os.environ.get("MIN_AVAILABLE_GIB", "1")) * 1024**2
            ):
                raise RuntimeError("host_memory_headroom_low")
        if (
            sum(
                p.stat().st_size
                for p in self.store.root.rglob("*")
                if p.is_file()
            )
            > self.spec.storage_limit_mb * 1024**2
        ):
            raise RuntimeError("storage_limit")

    def record(self, sequence):
        """実行の開始連番を加えて共通生成器から一件を取得する。"""
        return generate_record(
            self.spec.generator, self.spec.generator.start_sequence + sequence
        )

    def observe(self, row):
        """観測した行を有界キューへ追加し、生成件数を更新する。"""
        with self.lock:
            self.recent.append(row)
            self.produced += 1

    async def run(self):
        """ドライバーを起動し、停止要求またはtick上限まで周期処理する。

        失敗は状態に記録し、秘密値を含み得る例外は型名へ縮約する。終了時は接続解放を試みる。
        """
        from drivers import create_driver

        try:
            self.driver = create_driver(self)
            await self.driver.start()
            self.status = "running"
            while not self.stop_event.is_set():
                self.guard()
                await self.driver.step(self.tick)
                self.tick += 1
                if self.spec.max_ticks and self.tick >= self.spec.max_ticks:
                    break
                await asyncio.to_thread(
                    self.stop_event.wait, self.spec.interval_ms / 1000
                )
            self.status = "stopped"
        except Exception as exc:
            self.error = (
                f"generation_error: {display_location(exc.path)}　{exc}" if isinstance(exc, GenerationError)
                else str(exc) if str(exc) in {"disk_space_low", "host_memory_headroom_low", "storage_limit"}
                else type(exc).__name__
            )
            self.status = "failed"
        finally:
            if self.driver:
                try:
                    await self.driver.close()
                except Exception:
                    pass

    def source_profile(self):
        """生成を再開せず、保存済みデータの取得用プロフィールを選ぶ。"""
        if self.profile is not None:
            return self.profile
        desired = self.store.meta("desired")
        saved = desired.get("spec") if desired else None
        if saved is None:
            with self.store.db() as db:
                if db.execute("SELECT 1 FROM events LIMIT 1").fetchone():
                    raise KeyError("missing saved source profile")
            return self.store.profile()[0]
        if not isinstance(saved, dict):
            raise KeyError("invalid source configuration")
        identity = saved.get("profile_id")
        revision = desired.get("revision")
        if not isinstance(identity, str) or not identity:
            raise KeyError("invalid source profile")
        if revision is not None and (type(revision) is not int or revision < 1):
            raise KeyError("invalid source profile revision")
        profile, stored_revision = self.store.profile(identity, revision)
        # 旧版の停止記録には版がない。版が1つと分かる場合だけ照合する。
        if revision is None and stored_revision != 1:
            raise KeyError("ambiguous source profile revision")
        return profile

    def source_spec(self):
        """現在の設定、保存された希望設定、既定設定の順で取得する。"""
        if self.spec:
            return self.spec
        desired = self.store.meta("desired")
        return (
            Spec.model_validate(desired["spec"])
            if desired and desired.get("spec")
            else Spec()
        )
