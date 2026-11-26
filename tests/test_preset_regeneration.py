"""配布プリセットとカタログが再生成できることを確認する。"""

import tomllib
from pathlib import Path

from build_presets import build


def test_preset_generator_reproduces_the_shipped_library(tmp_path):
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    kind = project["project"]["name"].removeprefix("factory-").removesuffix("-simulator")
    build("logs" if kind == "log" else kind, tmp_path)

    shipped = root / "presets"
    assert sorted(p.name for p in tmp_path.glob("*.json")) == sorted(
        p.name for p in shipped.glob("*.json")
    )
    for path in sorted(tmp_path.iterdir()):
        assert path.read_bytes() == (shipped / path.name).read_bytes(), path.name
