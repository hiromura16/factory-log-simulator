"""Build-only proxy contract using synthetic values, no network requests."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")


def test_proxy_contract():
    app = json.loads((ROOT / "compose.yaml").read_text())["services"]["app"]
    assert app["build"]["args"] == list(KEYS)
    assert not set(KEYS).intersection(app["environment"])
    lines = (ROOT / "Dockerfile").read_text().splitlines()
    assert not any(line.startswith(("ARG " + k, "ENV " + k)) for line in lines for k in KEYS)
    assert ".env*" in (ROOT / ".dockerignore").read_text().splitlines()
    example = (ROOT / ".env.example").read_text()
    assert all("# " + k + "=" in example for k in KEYS)


def test_compose_render(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker Compose is required for render validation")
    empty = tmp_path / "empty.env"
    empty.write_text("")
    env = {k: v for k, v in os.environ.items() if k not in KEYS}
    env.update(APP_PORT="3643", LOG_DIR=str(tmp_path / "logs"))
    cmd = ["docker", "compose", "--env-file", str(empty), "-f", str(ROOT / "compose.yaml"), "config", "--format", "json"]
    before = json.loads(subprocess.check_output(cmd, env=env))
    assert not before["services"]["app"]["build"].get("args")
    env.update({k: ("localhost,127.0.0.1,::1" if k.lower() == "no_proxy" else "http://proxy.example.invalid:3128") for k in KEYS})
    after = json.loads(subprocess.check_output(cmd, env=env))
    assert after["services"]["app"]["build"]["args"] == {k: env[k] for k in KEYS}
    before["services"]["app"]["build"].pop("args", None)
    del after["services"]["app"]["build"]["args"]
    assert before == after
