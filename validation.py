"""生成項目と、利用するプロトコルの参照・型を検査する。"""

from contextlib import contextmanager
from types import SimpleNamespace

from generation import (
    GenerationError,
    encode_json,
    generate_record,
    generation_context,
    sample_offsets,
    validate_generation,
)

NUMERIC = {"integer", "number", "decimal"}
MEASUREMENTS = NUMERIC | {"boolean"}
IDENTIFICATION_PREVIEW_READERS = 8


def validate_source_spec(kind, spec, *, modbus_enabled=True):
    """プレビュー・保存・開始に共通の、外部接続を行わない検証を実施する。"""
    with _generator_error_path():
        validate_generation(spec.generator, kind=kind)

    if kind == "api":
        _validate_resources(spec)
    elif kind == "equipment":
        _validate_equipment(spec, modbus_enabled)
    elif kind == "historian":
        _validate_history(spec)
    elif kind == "logs":
        _validate_log_template(spec)
    elif kind == "identification":
        _validate_identification_preview(spec)
    return spec


@contextmanager
def _generator_error_path():
    """共通生成器が返す相対パスをスタジオの設定に合わせる。"""
    try:
        yield
    except GenerationError as exc:
        raise GenerationError(str(exc), path=("generator", *exc.path), code=exc.code) from None


def _validate_log_template(spec):
    """実配送と同じ本文の参照・書式を、接続や保存をせず検査する。"""
    from drivers import EventDriver

    def record(offset):
        with _generator_error_path():
            return generate_record(spec.generator, spec.generator.start_sequence + offset)

    # EventDriver の開始や配送を呼ばず、整形に必要な入力だけを渡す。
    driver = EventDriver(SimpleNamespace(kind="logs", spec=spec, record=record))
    for offset in sorted({0, 1, 2, *sample_offsets(spec.generator)}):
        row = driver.event(offset)
        with generation_context("logs", "message_template"):
            driver.log_message(row, offset)


def _validate_identification_preview(spec):
    """読取機ごとの見本も、他の代表行と同じように検査する。"""
    options = spec.identification
    count = min(len(options.readers), IDENTIFICATION_PREVIEW_READERS)
    offsets = {0, 1, 2, *(index * options.tags for index in range(count))}
    with _generator_error_path():
        for offset in sorted(offsets.difference(sample_offsets(spec.generator))):
            encode_json(generate_record(spec.generator, spec.generator.start_sequence + offset))


def _validate_resources(spec):
    """初期件数は共通生成器の rows ではなく各コレクションの設定を使う。"""
    checked_shared_sizes = {spec.generator.rows}
    for index, resource in enumerate(spec.business.resources):
        if resource.generator is None:
            if resource.rows in checked_shared_sizes:
                continue
            checked_shared_sizes.add(resource.rows)
        generator = resource.generator or spec.generator
        try:
            validate_generation(
                generator.model_copy(update={"rows": resource.rows}), kind="api"
            )
        except GenerationError as exc:
            source = (
                "共通のデータ定義" if resource.generator is None else "専用のデータ定義"
            )
            raise GenerationError(
                f"{resource.name} の{source}を確認してください。{exc}",
                path=("business", "resources", index, "generator", *exc.path),
                code=exc.code,
            ) from None


def _field_label(name):
    """識別子以外の入力値をエラーメッセージへ転載しない。"""
    if name.isascii() and name.isidentifier() and len(name) <= 63:
        return f"「{name}」"
    return "指定した項目"


def _validate_equipment(spec, modbus_enabled):
    """設定ミスを拒否し、生成中の欠測や未知のコードは変換時に扱う。"""
    fields = {field.name: field.data_type for field in spec.generator.fields}
    if spec.equipment.devices * len(fields) > 5000:
        raise GenerationError(
            "1実行の設備ノードは5000項目以下にしてください",
            path=("equipment", "devices"),
        )
    if not modbus_enabled:
        return
    for index, mapping in enumerate(spec.equipment.registers):
        path = ("equipment", "registers", index, "field")
        dtype = fields.get(mapping.field)
        if dtype is None:
            raise GenerationError(
                f"レジスターが参照する生成項目{_field_label(mapping.field)}がありません",
                path=path,
            )
        if dtype not in MEASUREMENTS and not (
            dtype == "string" and mapping.enum_values
        ):
            raise GenerationError(
                f"{_field_label(mapping.field)}は{dtype}型です。数値・真偽値の項目か、"
                "文字列を数値に変換する対応表を設定してください",
                path=path,
            )


def _validate_history(spec):
    """タグ名と記録時刻の参照を検査し、履歴に設定ミスを混ぜない。"""
    fields = {field.name: field.data_type for field in spec.generator.fields}
    for index, tag in enumerate(spec.history.tags):
        path = ("history", "tags", index)
        dtype = fields.get(tag)
        if dtype is None:
            raise GenerationError(
                f"履歴タグが参照する生成項目{_field_label(tag)}がありません", path=path
            )
        if dtype not in MEASUREMENTS:
            raise GenerationError(
                f"履歴タグ{_field_label(tag)}には数値または真偽値の項目を指定してください",
                path=path,
            )
    source_time = spec.history.source_time_field
    if source_time and fields.get(source_time) != "datetime":
        raise GenerationError(
            f"記録時刻{_field_label(source_time)}にはデータ定義にある日時型の項目を指定してください",
            path=("history", "source_time_field"),
        )
