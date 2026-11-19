"""Create local environment settings without login credentials."""

# ローカル実行用の環境ファイルを作る。認証情報は入力・生成しない。
import argparse
import os
from pathlib import Path

# 先頭の英語docstringは既存の --help に使うため、そのまま渡す。
p = argparse.ArgumentParser(description=__doc__)
p.add_argument(
    "--private-dir", type=Path, help="Accepted for compatibility; not required"
)
p.add_argument("--env-file", type=Path, default=Path(".env"))
a = p.parse_args()
# 見本はスクリプトの位置から探す。ログ設定があれば出力先を絶対パスに置く。
root = Path(__file__).resolve().parent.parent
text = (root / ".env.example").read_text()
if "LOG_DIR=" in text:
    logs = (root / "data/logs").resolve()
    logs.mkdir(parents=True, exist_ok=True)
    text = text.replace("/absolute/source-data/logs", str(logs))
# 既存ファイルは上書きしない。新規作成時の権限は最大0600に絞る。
fd = os.open(a.env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(text)
print("Created " + str(a.env_file.resolve()) + "; no login required")
