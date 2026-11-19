"""Export the annotated, versioned contracts used by the UI."""

# 管理画面が使う注釈付きスキーマをJSONファイルへ書き出す。
import sys
import json
from pathlib import Path
from importlib import import_module

# 作業ディレクトリではなく、このスクリプトの位置から実装を探す。
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
schemas = import_module("studio").schemas

# リポジトリの名前をアプリ種別に変換する。ログ種別だけ内部名が複数形。
kind = root.name.replace("factory-", "").replace("-simulator", "")
if kind == "log":
    kind = "logs"
# 生成先を作り、同名の契約ファイルは現行スキーマで上書きする。
folder = root / "contracts"
folder.mkdir(exist_ok=True)
for name, value in schemas(kind).items():
    (folder / (name + ".schema.json")).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
