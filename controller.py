"""Bounded background runtime. Protocols run only for this app's settings."""

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
from generation import generate_record, validate_generation


class Controller:
    def __init__(self, kind, store):
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
        with self.lock:
            return {
                "status": self.status,
                "tick": self.tick,
                "produced": self.produced,
                "requests": self.requests,
                "error": self.error,
                "dataset_id": self.ds,
                "recent": list(self.recent)[-30:],
                "elapsed_seconds": round(time.time() - self.started, 2)
                if self.started
                else 0,
                "spec": self.spec.model_dump(mode="json") if self.spec else None,
                "protocols": getattr(self.driver, "information", {}),
            }

    def start(self, spec, revision=None):
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise RuntimeError("実行中です。設定変更前に停止してください")
            validate_generation(spec.generator)
            if (
                self.kind == "equipment"
                and spec.equipment.devices * len(spec.generator.fields) > 5000
            ):
                raise ValueError("1実行の設備ノードは5000項目以下にしてください")
            profile, revision = self.store.profile(spec.profile_id, revision)
            if profile.auth_mode == "basic" and not profile.password:
                raise ValueError("取得APIのBasic認証パスワードが必要です")
            if profile.auth_mode in {"bearer", "api_key"} and not profile.token:
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
                            r.model_dump(mode="json") for r in spec.business.resources
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
        self.stop_event.set()
        self.store.meta(
            "desired",
            {
                "running": False,
                "spec": self.spec.model_dump(mode="json") if self.spec else None,
            },
        )
        if self.thread:
            self.thread.join(timeout=15)
        if self.thread and self.thread.is_alive():
            self.status = "stopping"
        return self.snapshot()

    def guard(self):
        if shutil.disk_usage(self.store.root).free < 2 * 1024**3:
            raise RuntimeError("disk_space_low")
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:") and int(line.split()[1]) < int(
                float(os.environ.get("MIN_AVAILABLE_GIB", "6")) * 1024**2
            ):
                raise RuntimeError("host_memory_headroom_low")
        if (
            sum(p.stat().st_size for p in self.store.root.rglob("*") if p.is_file())
            > self.spec.storage_limit_mb * 1024**2
        ):
            raise RuntimeError("storage_limit")

    def record(self, sequence):
        return generate_record(
            self.spec.generator, self.spec.generator.start_sequence + sequence
        )

    def observe(self, row):
        with self.lock:
            self.recent.append(row)
            self.produced += 1

    async def run(self):
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
                str(exc)
                if isinstance(exc, ValueError)
                or str(exc)
                in {"disk_space_low", "host_memory_headroom_low", "storage_limit"}
                else type(exc).__name__
            )
            self.status = "failed"
        finally:
            if self.driver:
                try:
                    await self.driver.close()
                except Exception:
                    pass

    def source_spec(self):
        if self.spec:
            return self.spec
        desired = self.store.meta("desired")
        return (
            Spec.model_validate(desired["spec"])
            if desired and desired.get("spec")
            else Spec()
        )
