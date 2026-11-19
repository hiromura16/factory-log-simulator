"""Export the annotated, versioned contracts used by the UI."""

import sys
import json
from pathlib import Path
from importlib import import_module

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
schemas = import_module("studio").schemas

kind = root.name.replace("factory-", "").replace("-simulator", "")
if kind == "log":
    kind = "logs"
folder = root / "contracts"
folder.mkdir(exist_ok=True)
for name, value in schemas(kind).items():
    (folder / (name + ".schema.json")).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
