"""保存済みテンプレートを、アプリの状態や接続先に触れず検証する。"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import ConfigurationError  # noqa: E402
from generation import GenerationError  # noqa: E402
from models import Spec  # noqa: E402
from validation import validate_source_spec  # noqa: E402

KIND = "logs"
MAX_BYTES = 2 * 1024 * 1024


def validate_template(payload):
    """このアプリで使う設定と、代表行の生成を検証する。"""
    return validate_source_spec(KIND, Spec.model_validate(payload))


def location(parts):
    """配列の位置を、JSON編集時に探せる0始まりのパスとして表示する。"""
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else "." + str(part)
        for part in parts
    )


def read_template(path):
    """Web画面と同じサイズ上限で、ファイルまたは標準入力を読む。"""
    if path == "-":
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    else:
        with Path(path).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise GenerationError("JSONは2MiB以下にしてください")
    return json.loads(raw.decode("utf-8-sig"))


def show_validation_errors(exc):
    """入力値を表示せず、設定の位置と直すべき制約を出力する。"""
    messages = {
        "extra_forbidden": "設定にない項目です。キー名を確認してください",
        "missing": "必須項目です",
        "literal_error": "選択肢から指定してください",
        "string_pattern_mismatch": "文字の形式を確認してください",
        "string_too_long": "文字数を減らしてください",
        "string_too_short": "必要な文字数を入力してください",
        "too_short": "必要な要素を追加してください",
        "too_long": "要素数を減らしてください",
        "less_than_equal": "上限以下にしてください",
        "greater_than_equal": "下限以上にしてください",
        "finite_number": "有限の数を指定してください",
    }
    for error in exc.errors(include_input=False, include_url=False):
        kind = error["type"]
        message = messages.get(kind)
        if message is None:
            cause = error.get("ctx", {}).get("error")
            message = (
                str(cause) if isinstance(cause, ConfigurationError)
                else "この項目の型と制約を確認してください"
            )
        print(f"{location(error['loc'])}  {message}", file=sys.stderr)


def main():
    """検証成功は0、読込・入力エラーは1を返す。"""
    profile_note = (
        "保存済みの公開プロファイルは読み込まないため、Modbusの割当も確認します。"
        if KIND == "equipment" else None
    )
    parser = argparse.ArgumentParser(description=__doc__, epilog=profile_note)
    parser.add_argument("file", metavar="JSON", help="テンプレートのパス。- は標準入力")
    parser.add_argument(
        "--compact", action="store_true",
        help="既定値とエディター用の注釈を除いたJSONを標準出力へ出す",
    )
    args = parser.parse_args()
    try:
        spec = validate_template(read_template(args.file))
    except OSError:
        print("ファイルを開けません。パスと読み取り権限を確認してください。", file=sys.stderr)
        return 1
    except UnicodeDecodeError:
        print("UTF-8のJSONを指定してください。", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"{error.lineno}行 {error.colno}列  JSONの構文を確認してください。", file=sys.stderr)
        return 1
    except ValidationError as error:
        show_validation_errors(error)
        return 1
    except GenerationError as error:
        print(f"{location(error.path)}  {error}", file=sys.stderr)
        return 1
    except (ArithmeticError, RecursionError, TypeError, ValueError):
        print("入力の型、範囲、JSONの入れ子を確認してください。", file=sys.stderr)
        return 1

    if args.compact:
        payload = {"version": spec.version, **spec.model_dump(mode="json", exclude_defaults=True)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("設定と代表行の生成を検証しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
