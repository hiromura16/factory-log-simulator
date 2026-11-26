"""資格情報を含まない初期設定と障害再現プリセットを生成する。"""

from pathlib import Path

from scripts.preset_catalog import write_catalog
from config import FieldRule, AnomalyRule
from models import Spec, Resource, Register


def business_fields(name):
    """業務リソースの種類に応じた項目定義を生成する。"""
    key = FieldRule(
        name="id", generator="record_id", primary_key=True, length=64
    )
    if name == "inventory":
        return [
            key,
            FieldRule(
                name="item_id",
                generator="template",
                template="ITEM-{sequence:06d}",
            ),
            FieldRule(
                name="on_hand",
                data_type="integer",
                generator="integer",
                minimum=100,
                maximum=1000,
            ),
            FieldRule(
                name="reserved",
                data_type="integer",
                generator="integer",
                minimum=0,
                maximum=50,
            ),
            FieldRule(
                name="available",
                data_type="integer",
                generator="difference",
                sources=["on_hand", "reserved"],
            ),
        ]
    return [
        key,
        FieldRule(
            name="order_no", generator="template", template="WO-{sequence:08d}"
        ),
        FieldRule(
            name="quantity",
            data_type="integer",
            generator="integer",
            minimum=1,
            maximum=100,
        ),
        FieldRule(
            name="status",
            generator="choice",
            choices=["planned", "running", "completed"],
        ),
        FieldRule(
            name="unit_price",
            data_type="decimal",
            generator="choice",
            choices=["10.00", "12.50", "99.99"],
            scale=2,
        ),
        FieldRule(
            name="amount",
            data_type="decimal",
            generator="product",
            sources=["quantity", "unit_price"],
            scale=2,
        ),
    ]


def build(kind, path):
    """指定した種類の入門・負荷・障害プリセットを組み立て、JSONとして出力する。

    開発用の生成処理であり、既存プリセットを書き換えるため実行先を確認する。
    """
    values = {}
    names = {
        "equipment": [
            "両プロトコル / 4設備",
            "OPC UAのみ",
            "Modbusのみ",
            "16設備 / 100ms更新",
            "32bit整数のレジスター",
            "ワード順を反転",
            "バイト順を反転",
            "コイル / 真偽値",
            "入力レジスター",
            "クライアント書き込み",
            "低速 / 5秒周期",
            "独自のデータ項目",
        ],
        "api": [
            "指図API / 固定200件",
            "在庫API",
            "複数コレクション",
            "1000件 / ページ50件",
            "差分更新 / 毎tick10件",
            "削除通知 / delta",
            "小さいページ / 10件",
            "短いカーソル期限",
            "高頻度の更新",
            "固定マスター",
            "任意の項目 / 平坦JSON",
            "大量データ / 1万件",
        ],
        "historian": [
            "4設備 / 過去1000時点",
            "1設備 / 長い履歴",
            "16設備 / 複数系列",
            "0.1秒サンプリング",
            "60秒サンプリング",
            "温度と圧力",
            "初期履歴なし / 逐次記録",
            "1日保持",
            "長期間保持",
            "遅い更新周期",
            "任意タグの名前",
            "集計検証 / 固定値",
        ],
        "logs": [
            "ローカル回転ログ / RFC5424",
            "JSON Lines",
            "プレーンログ",
            "RFC3164",
            "errorレベル",
            "warningレベル",
            "facility local1",
            "毎秒100件",
            "低頻度ログ",
            "小容量ローテーション",
            "独自メッセージ",
            "日本語ログ",
        ],
        "identification": [
            "RFID通過 / 100タグ",
            "10タグ / 少量確認",
            "1000タグ",
            "2つのゲート",
            "6工程の通過",
            "作業者を10名に変更",
            "Code128ラベル",
            "EAN13ラベル",
            "QRラベル",
            "毎秒100イベント",
            "低頻度の読取",
            "独自のイベント項目",
        ],
    }[kind]
    anomalies = {
        "equipment": [
            "突発値",
            "ドリフト",
            "固着",
            "欠測",
            "不正な型",
            "OPC Bad品質",
            "OPC Uncertain品質",
            "一時切断・復帰",
            "Modbus応答遅延",
            "Modbus桁あふれ",
            "未知の状態コード",
            "更新停止に近い低速",
        ],
        "api": [
            "429 Rate Limit",
            "503 Service Unavailable",
            "401 認証期限切れ",
            "応答遅延",
            "ページの重複",
            "ページの欠落",
            "JSONの途中切れ",
            "カーソル失効",
            "負の在庫",
            "数量と金額の不一致",
            "未知の状態",
            "項目の欠落",
        ],
        "historian": [
            "サンプル欠落",
            "Bad品質",
            "Uncertain品質",
            "過去時刻への逆転",
            "未来時刻",
            "突発値",
            "ドリフト",
            "固着",
            "NULL値",
            "不正な型",
            "欠測と品質異常の混在",
            "一定値 / 変化なし",
        ],
        "logs": [
            "エラー集中",
            "重複ログ",
            "壊れたヘッダー",
            "文字列へ異常値",
            "遅い出力",
            "warningの集中",
            "固着した値",
            "日本語と改行",
            "大きなメッセージ",
            "欠測値",
            "未知の状態",
            "送信エラーを保持",
        ],
        "identification": [
            "二重読取",
            "読取漏れ",
            "予定外の読取機",
            "未登録作業者",
            "二重読取と読取漏れ",
            "通過順の欠落",
            "短時間の大量読取",
            "タグ値の固着",
            "未知の状態",
            "欠測値",
            "作業者と読取機の不整合",
            "遅い読取",
        ],
    }[kind]
    for i, title in enumerate(names + anomalies):
        spec = Spec(name=("正常 / " if i < 12 else "異常 / ") + title)
        spec.generator.run_key = f"{kind}-preset-{i + 1:02d}"
        spec.generator.parameters["start_time"] = "2026-11-13T00:00:00+00:00"
        spec.generator.parameters["entity_count"] = 4
        if kind == "equipment":
            spec.generator.fields[2].generator = "sequence"
            spec.generator.fields[2].start = 1
            spec.generator.fields[2].modulo = 4
            if i == 1:
                spec.profile_id = "opc-only"
            if i == 2:
                spec.profile_id = "modbus-only"
            if i == 3:
                spec.equipment.devices = 16
                spec.interval_ms = 100
                spec.generator.fields[2].modulo = 16
            if i == 4:
                spec.equipment.registers[0] = Register(
                    field="sequence_no", encoding="uint32", address=10
                )
            if i == 5:
                spec.equipment.registers[0].word_order = "little"
            if i == 6:
                spec.equipment.registers[0].byte_order = "little"
            if i == 7:
                spec.generator.fields.append(
                    FieldRule(
                        name="active",
                        data_type="boolean",
                        generator="boolean",
                        probability=0.8,
                    )
                )
                spec.equipment.registers.append(
                    Register(
                        field="active", area="coil", encoding="bool", address=0
                    )
                )
            if i == 8:
                spec.equipment.registers[0].area = "input"
            if i == 9:
                spec.equipment.writable = True
            if i == 10:
                spec.interval_ms = 5000
            if i == 11:
                spec.generator.fields[5].name = "temperature"
                spec.equipment.registers[0].field = "temperature"
            if i in {12, 13, 14, 15, 16}:
                op = {
                    12: "set",
                    13: "ramp",
                    14: "freeze",
                    15: "null",
                    16: "set",
                }[i]
                v = {12: 250, 13: 1, 14: None, 15: None, 16: "SENSOR_ERROR"}[i]
                spec.generator.anomalies = [
                    AnomalyRule(
                        field="value",
                        operation=op,
                        value=v,
                        from_row=20,
                        to_row=79,
                        bypass_validation=i == 16,
                    )
                ]
            if i in {17, 18}:
                spec.equipment.quality = (
                    "BadSensorFailure"
                    if i == 17
                    else "UncertainLastUsableValue"
                )
                spec.equipment.quality_from_tick = 5
                spec.equipment.quality_until_tick = 10
            if i == 19:
                spec.equipment.offline_from_tick = 5
                spec.equipment.offline_ticks = 5
            if i == 20:
                spec.equipment.read_delay_ms = 1500
            if i == 21:
                spec.equipment.registers[0] = Register(
                    field="value", encoding="int16", scale=10000, address=10
                )
            if i == 22:
                spec.generator.anomalies = [
                    AnomalyRule(field="status", value="UNKNOWN", from_row=10)
                ]
            if i == 23:
                spec.interval_ms = 60000
        elif kind == "api":
            spec.generator.fields = business_fields("orders")
            if i in {1, 20}:
                spec.business.resources = [Resource(name="inventory")]
                spec.generator.fields = business_fields("inventory")
            if i == 2:
                other = spec.generator.model_copy(deep=True)
                other.fields = business_fields("inventory")
                spec.business.resources = [
                    Resource(name="orders"),
                    Resource(name="inventory", generator=other),
                ]
            if i == 3:
                spec.business.resources[0].rows = 1000
                spec.business.page_size = 50
            if i == 4:
                spec.business.updates_per_tick = 10
            if i == 5:
                spec.business.delete_every_ticks = 3
            if i == 6:
                spec.business.page_size = 10
            if i == 7:
                spec.business.cursor_ttl_seconds = 10
            if i == 8:
                spec.interval_ms = 100
            if i == 9:
                spec.business.updates_per_tick = 0
            if i == 11:
                spec.business.resources[0].rows = 10000
            if 12 <= i <= 19:
                spec.business.fault = [
                    "rate_limit",
                    "server_error",
                    "unauthorized",
                    "delay",
                    "duplicate_page",
                    "skip_page",
                    "truncate_json",
                    "cursor_expired",
                ][i - 12]
                spec.business.fault_every = 3
            if i == 20:
                spec.generator.anomalies = [
                    AnomalyRule(
                        field="on_hand", value=-10, from_row=20, to_row=39
                    )
                ]
            if i == 21:
                spec.generator.anomalies = [
                    AnomalyRule(
                        field="amount",
                        operation="add",
                        value="0.01",
                        from_row=20,
                        to_row=39,
                    )
                ]
            if i == 22:
                spec.generator.anomalies = [
                    AnomalyRule(
                        field="status", value="UNKNOWN", from_row=20, to_row=39
                    )
                ]
            if i == 23:
                spec.generator.anomalies = [
                    AnomalyRule(
                        field="quantity",
                        operation="omit",
                        from_row=20,
                        to_row=39,
                    )
                ]
        elif kind == "historian":
            if i == 1:
                spec.history.devices = 1
                spec.history.initial_samples = 10000
            if i == 2:
                spec.history.devices = 16
            if i == 3:
                spec.history.sample_seconds = 0.1
                spec.interval_ms = 100
            if i == 4:
                spec.history.sample_seconds = 60
            if i == 5:
                spec.generator.fields.append(
                    FieldRule(
                        name="pressure",
                        data_type="number",
                        generator="normal",
                        mean=100,
                        stddev=5,
                    )
                )
                spec.history.tags = ["value", "pressure"]
            if i == 6:
                spec.history.initial_samples = 0
            if i == 7:
                spec.history.retention_days = 1
            if i == 8:
                spec.history.retention_days = 365
            if i == 9:
                spec.interval_ms = 5000
            if i == 10:
                spec.generator.fields[5].name = "temperature"
                spec.history.tags = ["temperature"]
            if i in {11, 23}:
                spec.generator.fields[5].generator = "constant"
                spec.generator.fields[5].value = 50
            if i in {12, 22}:
                spec.history.missing_every = 5
            if i in {13, 14, 22}:
                spec.history.quality = "Uncertain" if i == 14 else "Bad"
                spec.history.bad_every = 3
            if i in {15, 16}:
                spec.history.shift_every = 5
                spec.history.timestamp_shift_seconds = (
                    -120 if i == 15 else 86400
                )
            if 17 <= i <= 21:
                spec.generator.anomalies = [
                    AnomalyRule(
                        field="value",
                        operation=["set", "ramp", "freeze", "null", "set"][
                            i - 17
                        ],
                        value=[250, 1, None, None, "BAD"][i - 17],
                        from_row=20,
                        to_row=100,
                        bypass_validation=i == 21,
                    )
                ]
        elif kind == "logs":
            if i in {1, 2, 3}:
                spec.logs.format = ["jsonl", "plain", "rfc3164"][i - 1]
            if i in {4, 12}:
                spec.logs.severity = 3
            if i in {5, 17}:
                spec.logs.severity = 4
            if i == 6:
                spec.logs.facility = 17
            if i == 7:
                spec.batch_size = 100
            if i in {8, 16}:
                spec.batch_size = 1
                spec.interval_ms = 5000
            if i == 9:
                spec.logs.rotate_mb = 1
                spec.logs.backups = 3
            if i == 10:
                spec.logs.message_template = "source={entity_id} sequence={sequence_no} measurement={value}"
            if i in {11, 19}:
                spec.logs.message_template = (
                    "設備={entity_id} 状態={status} 測定値={value}\n検証ログ"
                )
            if i == 13:
                spec.logs.duplicate_every = 3
            if i == 14:
                spec.logs.malformed_every = 3
            if i == 15:
                spec.generator.anomalies = [
                    AnomalyRule(
                        field="value", value="ERROR", bypass_validation=True
                    )
                ]
            if i == 18:
                spec.generator.anomalies = [
                    AnomalyRule(field="value", operation="freeze")
                ]
            if i == 20:
                spec.logs.message_template = (
                    "large-message " * 200
                ) + "{sequence}"
            if i == 21:
                spec.generator.anomalies = [
                    AnomalyRule(field="value", operation="null")
                ]
            if i == 22:
                spec.generator.anomalies = [
                    AnomalyRule(field="status", value="UNKNOWN")
                ]
        else:
            if i == 1:
                spec.identification.tags = 10
            if i == 2:
                spec.identification.tags = 1000
            if i == 3:
                spec.identification.readers = ["IN", "OUT"]
            if i == 4:
                spec.identification.readers = [
                    "IN",
                    "CUT",
                    "ASSEMBLY",
                    "CLEAN",
                    "TEST",
                    "OUT",
                ]
            if i == 5:
                spec.identification.operators = [
                    f"WORKER-{j:03d}" for j in range(1, 11)
                ]
            if i in {6, 7, 8}:
                spec.identification.barcode = ["code128", "ean13", "qr"][i - 6]
            if i == 9:
                spec.batch_size = 100
            if i in {10, 23}:
                spec.interval_ms = 5000
                spec.batch_size = 1
            if i == 12:
                spec.identification.duplicate_every = 3
            if i in {13, 17}:
                spec.identification.drop_every = 3
            if i in {14, 22}:
                spec.identification.wrong_reader_every = 3
            if i in {15, 22}:
                spec.identification.unauthorized_every = 3
            if i == 16:
                spec.identification.drop_every = 5
                spec.identification.duplicate_every = 3
            if i == 18:
                spec.batch_size = 1000
                spec.interval_ms = 100
            if i == 19:
                spec.generator.fields.append(
                    FieldRule(
                        name="tag_id", generator="constant", value="STUCK-TAG"
                    )
                )
            if i == 20:
                spec.generator.anomalies = [
                    AnomalyRule(field="status", value="UNKNOWN")
                ]
            if i == 21:
                spec.generator.anomalies = [
                    AnomalyRule(field="value", operation="null")
                ]
        if kind == "historian" and i == 5:
            spec.generator.fields[5].name = "temperature"
            spec.history.tags = ["temperature", "pressure"]
        if kind == "api" and i == 10:
            spec.generator.fields.append(
                FieldRule(
                    name="line_id",
                    generator="choice",
                    choices=["LINE-A", "LINE-B"],
                )
            )
        if kind == "identification" and i == 11:
            spec.generator.fields.append(
                FieldRule(
                    name="material_type",
                    generator="choice",
                    choices=["RAW", "WIP", "FINISHED"],
                )
            )
        if kind == "identification" and i == 17:
            spec.identification.readers = [
                "IN",
                "PREPARE",
                "PROCESS",
                "INSPECT",
                "PACK",
                "OUT",
            ]
        if kind == "logs" and i in {12, 17}:
            spec.batch_size = 100
        purpose = {
            "equipment": "設備を読み出し・購読する収集クライアント",
            "api": "MES/ERPの定期取得・ページング・差分収集",
            "historian": "期間指定、品質コード、欠測、集計と過去値取得",
            "logs": "ログ収集・パース・ローテーション・配送失敗の扱い",
            "identification": "所在・通過・作業者・重複排除と読取漏れ",
        }[kind]
        conditions = [
            f"更新周期{spec.interval_ms}ms、最大tick数{spec.max_ticks or '無制限'}。"
        ]
        checks = []
        if kind == "equipment":
            o = spec.equipment
            conditions += [
                f"{o.devices}設備を公開。プロファイルは{spec.profile_id}。OPC UAは生成項目ごとのNodeId、Modbusは0始まりのアドレスを使用。"
            ]
            conditions += [
                f"{m.field}: {m.area}[{m.address}] / {m.encoding} / 倍率{m.scale} / 加算{m.offset} / byte={m.byte_order}, word={m.word_order}。"
                for m in o.registers
            ]
            if o.quality_from_tick:
                conditions += [
                    f"tick {o.quality_from_tick}〜{o.quality_until_tick}でOPC品質を{o.quality}に変更。"
                ]
            if o.offline_ticks:
                conditions += [
                    f"tick {o.offline_from_tick}から{o.offline_ticks}tickの間、両リスナーを停止して再開。"
                ]
            if o.read_delay_ms:
                conditions += [
                    f"Modbusアクセスへ{o.read_delay_ms}msの応答遅延を追加。"
                ]
            checks = [
                "OPC UAは値・StatusCode・購読通知、Modbusは領域・レジスター幅・符号・倍率・順序を照合。",
                "書き込み許可時も次の生成tickで値を更新。数値の桁あふれはModbusのエラー応答を確認。",
            ]
        elif kind == "api":
            o = spec.business
            conditions += [
                f"{x.name}を{x.rows}件で初期化。" for x in o.resources
            ]
            conditions += [
                f"1tickごとに各コレクション最大{o.updates_per_tick}件を更新。既定ページ{o.page_size}件、カーソル寿命{o.cursor_ttl_seconds}秒。"
            ]
            if o.delete_every_ticks:
                conditions += [
                    f"{o.delete_every_ticks}tickごとに削除を記録し、deltaへ通知。"
                ]
            if o.fault != "none":
                conditions += [
                    f"取得APIの{o.fault_every}リクエストごとに{o.fault}を発生。管理画面の操作は対象外。遅延設定{o.fault_delay_ms}ms。"
                ]
            checks = [
                "ページ間でIDの欠落・重複がないか、snapshotを保持して全件取得できるかを確認。",
                "最終ページのdeltaリンクで更新と削除を取得。429はRetry-After、期限切れカーソルは再同期を確認。",
            ]
        elif kind == "historian":
            o = spec.history
            conditions += [
                f"{o.devices}設備×{', '.join(o.tags)}を{o.sample_seconds}秒間隔で保存。過去{o.initial_samples}時点を初回に作成し、その後1tickに1時点ずつ追加。保持{o.retention_days}日。"
            ]
            if o.missing_every:
                conditions += [
                    f"{o.missing_every}時点ごとのサンプルを保存せず欠測にする。"
                ]
            if o.bad_every:
                conditions += [
                    f"{o.bad_every}時点ごとに品質{o.quality}を記録。"
                ]
            if o.shift_every:
                conditions += [
                    f"{o.shift_every}時点ごとに時刻を{o.timestamp_shift_seconds}秒ずらす。元の時刻軸からの単発シフト。"
                ]
            checks = [
                "rawの時刻・値・品質を照合し、同時刻の複数サンプルもカーソルで取得。",
                "mean/min/max/sum/count/last、Goodのみの集計、欠測補完none/null/previousの違いを確認。欠測は0として扱わない。",
            ]
        elif kind == "logs":
            o = spec.logs
            conditions += [
                f"1tickに{spec.batch_size}件、書式{o.format}、facility={o.facility}、severity={o.severity}。回転上限{o.rotate_mb}MiB、バックアップ{o.backups}本。"
            ]
            conditions += [f"本文テンプレート: {o.message_template[:120]}。"]
            if o.duplicate_every:
                conditions += [
                    f"{o.duplicate_every}件ごとに同じevent_idと本文を重複出力。"
                ]
            if o.malformed_every:
                conditions += [
                    f"{o.malformed_every}件ごとにヘッダーを意図的に破損。"
                ]
            checks = [
                "PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。",
                "TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。",
            ]
        else:
            o = spec.identification
            conditions += [
                f"{o.tags}タグを{', '.join(o.readers)}の順に通過させ、{len(o.operators)}名の疑似作業者を割り当てる。1tickに{spec.batch_size}イベント、ラベル方式{o.barcode}。"
            ]
            for key, label in [
                ("duplicate_every", "同一event_idの二重読取"),
                ("drop_every", "読取漏れ"),
                ("wrong_reader_every", "予定外の読取機"),
                ("unauthorized_every", "未登録作業者"),
            ]:
                n = getattr(o, key)
                if n:
                    conditions += [f"{n}件ごとに{label}を発生。"]
            checks = [
                "tag_id・EPC・reader_id・operator_id・lot_idで通過を追跡し、event_idで重複を判定。",
                "ラベルAPIでCode128/EAN13/QRのPNGを取得。実機リーダーのLLRP・RF無線通信は模擬せず、取り込み対象の読取イベントを再現。",
            ]
        for a in spec.generator.anomalies:
            conditions += [
                f"項目{a.field}へ{a.operation}、値={a.value!r}を生成位置{a.from_row}〜{a.to_row if a.to_row is not None else '以降'}で適用。異常後の型検証を迂回={a.bypass_validation}。"
            ]
        prerequisites = "公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。"
        if kind == "logs" and i == 23:
            prerequisites += " 配送エラーの再現には接続できない送信先を別途指定。既定のファイル出力では配送エラーにならない。"
        if kind == "equipment" and i in {15, 22}:
            checks.append(
                "Modbusでは、欠測または未知の状態で変換できない番地を含む読取要求は例外4を返します。"
                "他の番地だけを対象とする要求は引き続き読み取れます。"
            )
        spec.description = (
            f"【想定】\n{purpose}の検証。{title}を想定。\n\n【生成内容・条件】\n"
            + "\n".join(conditions)
            + "\n\n【確認事項】\n"
            + "\n".join(checks)
            + "\n\n【実行前】\n"
            + prerequisites
        )
        values[f"{i + 1:02d}-" + ("normal" if i < 12 else "anomaly")] = (
            Spec.model_validate(spec.model_dump())
        )
    path = Path(path)
    path.mkdir(exist_ok=True)
    for identity, spec in values.items():
        (path / (identity + ".json")).write_text(
            spec.model_dump_json(indent=2) + "\n"
        )
    write_catalog(path)
    return values


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kind",
        choices=["equipment", "api", "historian", "logs", "identification"],
        default=Path(__file__)
        .resolve()
        .parent.name.replace("factory-", "")
        .replace("-simulator", "")
        .replace("log", "logs"),
    )
    args = parser.parse_args()
    print(
        f"{len(build(args.kind, Path(__file__).resolve().parent / 'presets'))} presets written"
    )
