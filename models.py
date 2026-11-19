"""各模擬ソースの設定と公開・認証プロファイルを定義する。

クラスコメントは開発者向けであり、公開スキーマの説明や既定値を変更しない。
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from config import RunSpec


# 未知の設定項目を拒否するアプリ共通入力モデル。
class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# 取得API認証、設備公開条件とイベント送信先をまとめる。
class Profile(Model):
    id: str = Field(
        default="default",
        pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="保存用ID。同じIDで保存すると新しい版になります。",
    )
    name: str = Field(
        default="既定の公開設定",
        max_length=120,
        description="公開先・認証・配送先を管理するプロファイルの表示名。",
    )
    auth_mode: Literal["none", "basic", "bearer", "api_key"] = "none"
    username: str = Field(
        default="source",
        max_length=120,
        description="データ取得API専用のBasic認証ユーザー。管理画面はログイン不要です。",
    )
    password: SecretStr | None = Field(
        default=None,
        description="取得APIのBasic認証パスワード。空欄は同じ認証方式の保存値を維持。暗号化保存し、読み戻しません。",
    )
    token: SecretStr | None = Field(
        default=None,
        description="BearerまたはX-API-Keyで受け付ける値。値は暗号化保存し、JSON書き出しには含めません。",
    )
    allow_writes: bool = Field(
        default=False,
        description="取得APIのPOST/PATCH/DELETEを許可。既定は読み取りのみ。操作するのはこのツールの疑似データです。",
    )
    opc_enabled: bool = Field(
        default=True,
        description="OPC UAのバイナリーサーバーを公開します。HTTP送信とは異なり、収集側から読まれたり購読されたりする方式です。",
    )
    opc_port: int = Field(
        default=4840,
        ge=1024,
        le=65535,
        description="コンテナ内のOPC UA待受ポート。ホストへの公開ポートはComposeで設定します。",
    )
    namespace_uri: str = Field(
        default="urn:factory:equipment:simulator",
        max_length=255,
        description="NodeIdを識別する名前空間URI。クライアントはnamespace URIからindexを取得してください。",
    )
    opc_auth: Literal["anonymous", "username"] = "anonymous"
    opc_username: str = Field(
        default="reader",
        max_length=120,
        description="OPC UAのユーザー名認証で使用するユーザー。",
    )
    opc_password: SecretStr | None = Field(
        default=None,
        description="OPC UAユーザーのパスワード。ユーザー名認証時はSignAndEncryptを必須にします。",
    )
    opc_security: Literal["none", "sign_encrypt"] = "none"
    certificate_file: str = Field(
        default="",
        description="connection-files内のサーバー証明書。OPC UAはapplication URI入りのDER/PEM証明書を使用します。",
    )
    private_key_file: str = Field(
        default="",
        description="connection-files内のサーバー秘密鍵。ファイルは権限600で保存します。",
    )
    trusted_client_certificates: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="SignAndEncryptで信頼するクライアントのleaf証明書。connection-files内のDER/PEMパスを配列で指定。指紋と有効期間を検証します。",
    )
    modbus_enabled: bool = Field(
        default=True,
        description="Modbus TCPサーバーを公開。TCPにはユーザー名・パスワード認証はありません。接続元制限はホストで行います。",
    )
    modbus_port: int = Field(
        default=1502,
        ge=1024,
        le=65535,
        description="コンテナ内のModbus TCP待受。非特権ユーザーのため既定は1502です。",
    )
    output: Literal["capture", "file", "udp", "tcp", "tls", "mqtt", "http"] = (
        "capture"
    )
    host: str = Field(
        default="",
        max_length=255,
        description="Syslog/MQTT送信先のホスト。http://やポートは含めません。",
    )
    port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description="送信先ポート。未指定はSyslog514/TLS6514、MQTT1883/TLS8883を使用。",
    )
    topic: str = Field(
        default="factory/identification",
        max_length=255,
        description="RFID・バーコードイベントをMQTTで配信するトピック。",
    )
    url: str = Field(
        default="",
        max_length=2048,
        description="HTTP送信先URL。HTTP APIへ1イベントずつJSONをPOSTします。",
    )
    output_username: str = Field(
        default="",
        max_length=255,
        description="MQTT送信用のユーザー。取得APIの認証とは別です。",
    )
    mqtt_tls: bool = Field(
        default=False,
        description="MQTT接続でTLSを使用。既定ポートは有効時8883、無効時1883。CAと検証設定も適用します。",
    )
    output_password: SecretStr | None = Field(
        default=None,
        description="MQTT送信先パスワード。暗号化して保存します。",
    )
    output_token: SecretStr | None = Field(
        default=None,
        description="HTTP送信時のBearerトークン。空欄なら認証ヘッダーを付けません。",
    )
    tls_verify: bool = Field(
        default=True,
        description="送信先のTLS証明書とホスト名を検証。Syslog TLS / HTTPS / MQTT TLSに適用します。",
    )
    ca_file: str = Field(
        default="",
        description="送信先CA証明書。connection-files内のPEM。未指定はシステム信頼ストア。",
    )
    timeout_seconds: int = Field(
        default=10, ge=1, le=60, description="接続・受信ACKの最大待機秒数。"
    )
    clear_secrets: list[str] = Field(
        default_factory=list,
        description='明示的に消す秘密情報名の配列。例: ["token"]。空欄による維持と区別します。',
    )


# 生成項目とModbus領域・アドレス・型変換を対応付ける。
class Register(Model):
    field: str = Field(
        default="value",
        description="生成データの項目名。OPC UAノードやModbusレジスターへ対応付けます。",
    )
    area: Literal["holding", "input", "coil", "discrete"] = "holding"
    address: int = Field(
        default=0,
        ge=0,
        le=65535,
        description="0始まりのプロトコルアドレス。40001表記とは異なり、先頭のholding registerは0です。",
    )
    encoding: Literal[
        "uint16", "int16", "uint32", "int32", "float32", "float64", "bool"
    ] = "float32"
    byte_order: Literal["big", "little"] = "big"
    word_order: Literal["big", "little"] = "big"
    scale: float = Field(
        default=1,
        description="レジスターへ入れる値=生成値×scale+offset。読取側は逆変換します。",
    )
    offset: float = Field(default=0, description="倍率適用後に加える値。")
    enum_values: dict[str, int] = Field(
        default_factory=dict,
        description='文字列を数値へ変換する対応表。例: {"ok":0,"warning":1,"stopped":2}。',
    )


# 設備数、公開値、レジスター対応と通信・品質異常を定義する。
class Equipment(Model):
    devices: int = Field(
        default=4,
        ge=1,
        le=247,
        description="模擬設備数。Modbus device IDは1から設備数まで。OPC UAにも同数の設備オブジェクトを公開。",
    )
    registers: list[Register] = Field(
        default_factory=lambda: [
            Register(),
            Register(field="sequence_no", address=2, encoding="uint32"),
            Register(
                field="status",
                address=4,
                encoding="uint16",
                enum_values={"ok": 0, "warning": 1, "stopped": 2},
            ),
        ],
        max_length=100,
        description="データ項目とレジスターの対応表。領域内でアドレス幅が重複しないよう指定します。",
    )
    quality: Literal[
        "Good", "BadSensorFailure", "UncertainLastUsableValue"
    ] = "Good"
    quality_from_tick: int = Field(
        default=0,
        ge=0,
        description="このtick以降に品質コードを適用します。0は開始直後。",
    )
    quality_until_tick: int = Field(
        default=0,
        ge=0,
        description="0は最後まで。このtickを過ぎるとGoodへ戻ります。",
    )
    offline_from_tick: int = Field(
        default=0,
        ge=0,
        description="0は切断なし。このtick以降、指定期間だけプロトコル待受を停止し再接続を試験。",
    )
    offline_ticks: int = Field(
        default=5,
        ge=1,
        le=10000,
        description="切断状態を続けるtick数。その後は同じノード・アドレスで待受を再開。",
    )
    read_delay_ms: int = Field(
        default=0,
        ge=0,
        le=5000,
        description="Modbusの読取応答を遅延させる時間。OPC UAでは更新周期を使用してください。",
    )
    writable: bool = Field(
        default=False,
        description="クライアントの書き込みを許可。生成周期の次の更新で生成値へ戻ります。",
    )

    @model_validator(mode="after")
    def overlap(self):
        """同じ領域のアドレス重複、範囲外とbit領域の型不一致を拒否する。"""
        used = set()
        for r in self.registers:
            width = {"uint32": 2, "int32": 2, "float32": 2, "float64": 4}.get(
                r.encoding, 1
            )
            if r.area in {"coil", "discrete"} and r.encoding != "bool":
                raise ValueError("coil/discreteの型はboolです")
            for address in range(r.address, r.address + width):
                if address > 65535 or (r.area, address) in used:
                    raise ValueError(
                        "レジスターのアドレス幅が重複・範囲外です"
                    )
                used.add((r.area, address))
        return self


# 業務コレクション名、初期件数と専用の生成条件を定義する。
class Resource(Model):
    name: str = Field(
        default="orders",
        pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$",
        description="コレクション名。REST/ODataのURLの末尾になります。",
    )
    rows: int = Field(
        default=200,
        ge=1,
        le=1000000,
        description="最初に用意する業務レコード数。",
    )
    generator: RunSpec | None = Field(
        default=None,
        description="このコレクション専用の項目・生成条件。nullは共通データ定義を使用。",
    )


# 業務レコードの更新、ページ取得とHTTP障害模擬を設定する。
class Business(Model):
    resources: list[Resource] = Field(
        default_factory=lambda: [Resource()],
        min_length=1,
        max_length=30,
        description="公開するコレクション。指図・在庫・実績等を別URLと独自の列定義で用意できます。",
    )
    updates_per_tick: int = Field(
        default=2,
        ge=0,
        le=10000,
        description="各tickで更新するレコード数。0は固定データ。idは維持し、値・revisionを更新します。",
    )
    delete_every_ticks: int = Field(
        default=0,
        ge=0,
        description="0は削除なし。指定tickごとに1件を論理削除し、deltaの削除通知を試験。",
    )
    cursor_ttl_seconds: int = Field(
        default=600,
        ge=1,
        le=86400,
        description="署名付きページングカーソルの有効期限。期限切れは410です。",
    )
    page_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="既定のページ件数。snapshot基準のページングで更新中も同じ集合を読みます。",
    )
    fault: Literal[
        "none",
        "rate_limit",
        "server_error",
        "unauthorized",
        "delay",
        "duplicate_page",
        "skip_page",
        "truncate_json",
        "cursor_expired",
    ] = "none"
    fault_every: int = Field(
        default=5,
        ge=1,
        description="データ取得APIへのリクエスト何回ごとに異常を返すか。管理UIの通信は含みません。",
    )
    fault_delay_ms: int = Field(
        default=1000, ge=0, le=10000, description="API異常=delayの待機時間。"
    )


# 時系列タグ、サンプル間隔、品質・欠測と保持期間を設定する。
class History(Model):
    tags: list[str] = Field(
        default_factory=lambda: ["value"],
        min_length=1,
        max_length=100,
        description="保存する生成項目。タグ名はdevice-001.value等になります。",
    )
    devices: int = Field(
        default=4, ge=1, le=1000, description="時系列を作る設備数。"
    )
    initial_samples: int = Field(
        default=1000,
        ge=0,
        le=1000000,
        description="開始時に作る過去サンプルの時点数。タグ・設備数を掛けた総点数は上限で検証します。",
    )
    sample_seconds: float = Field(
        default=1,
        ge=0.01,
        le=86400,
        description="疑似イベント時刻のサンプリング間隔秒。更新周期とは別に指定できます。",
    )
    source_time_field: str = Field(
        default="",
        description="空欄はサンプリング間隔から時刻を計算。生成項目名を指定するとその日時と異常ルールを使用します。",
    )
    shift_every: int = Field(
        default=0,
        ge=0,
        description="指定時点ごとにタイムスタンプをずらします。0は変更なし。",
    )
    timestamp_shift_seconds: float = Field(
        default=0, description="時刻をずらす秒数。負数は遅延・順序逆転。"
    )
    retention_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        description="サンプルの保持期間。古いサンプルを定期的に削除します。",
    )
    quality: Literal["Good", "Bad", "Uncertain"] = "Good"
    bad_every: int = Field(
        default=0,
        ge=0,
        description="0は品質コード変更なし。指定時点ごとにqualityの異常コードを付加します。",
    )
    missing_every: int = Field(
        default=0,
        ge=0,
        description="指定時点ごとにサンプルを保存しません。欠測とNULLを区別する試験。",
    )


# ログの書式、回転、重複と破損の模擬条件を定義する。
class Logs(Model):
    format: Literal["jsonl", "plain", "rfc5424", "rfc3164"] = "rfc5424"
    facility: int = Field(
        default=16,
        ge=0,
        le=23,
        description="Syslog facility。local0=16。severityと合わせてPRIを作ります。",
    )
    severity: int = Field(
        default=6,
        ge=0,
        le=7,
        description="Syslog severity。0=emergency、3=error、4=warning、6=info、7=debug。",
    )
    hostname: str = Field(
        default="factory-device",
        pattern=r"^[A-Za-z0-9_.-]{1,255}$",
        description="ログに記載する模擬ホスト名。実ホストの個人情報は読み取りません。",
    )
    app_name: str = Field(
        default="mes-demo",
        pattern=r"^[A-Za-z0-9_.-]{1,48}$",
        description="Syslog APP-NAME。",
    )
    message_template: str = Field(
        default="entity={entity_id} status={status} value={value}",
        max_length=6000,
        description="生成項目とsequenceを参照するメッセージ書式。",
    )
    tcp_framing: Literal["octet_counting", "newline"] = "octet_counting"
    rotate_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="ローカルファイルのローテーション容量MiB。",
    )
    backups: int = Field(
        default=5,
        ge=1,
        le=30,
        description="ローテーションで残す過去ファイル数。",
    )
    duplicate_every: int = Field(
        default=0, ge=0, description="指定件ごとに同じログを二重出力。"
    )
    malformed_every: int = Field(
        default=0,
        ge=0,
        description="指定件ごとにヘッダーを壊し、収集側パーサーの隔離を試験。",
    )


# タグ・読取機・作業者と識別イベント異常を定義する。
class Identification(Model):
    tags: int = Field(
        default=100,
        ge=1,
        le=100000,
        description="模擬タグ・品目の種類数。同じタグが複数読取機を通過します。",
    )
    readers: list[str] = Field(
        default_factory=lambda: [
            "GATE-IN",
            "ASSEMBLY",
            "INSPECTION",
            "GATE-OUT",
        ],
        min_length=1,
        max_length=100,
        description="通過順に並べた読取機・工程・ゾーン名。",
    )
    operators: list[str] = Field(
        default_factory=lambda: ["WORKER-001", "WORKER-002", "WORKER-003"],
        min_length=1,
        max_length=10000,
        description="架空の作業者ID一覧。実在者の個人情報は使用しません。",
    )
    barcode: Literal["code128", "ean13", "qr"] = "code128"
    duplicate_every: int = Field(
        default=0,
        ge=0,
        description="指定件ごとに同じevent_idを再送し、二重読取を再現します。",
    )
    drop_every: int = Field(
        default=0,
        ge=0,
        description="指定件ごとにイベントを生成結果から落とし、読取漏れを再現。",
    )
    wrong_reader_every: int = Field(
        default=0,
        ge=0,
        description="指定件ごとに予定外の読取機名を出力します。",
    )
    unauthorized_every: int = Field(
        default=0, ge=0, description="指定件ごとに未登録作業者を出力します。"
    )


# 共通生成設定と各ソース固有の条件、実行周期・資源上限を束ねる。
class Spec(Model):
    version: Literal[1] = 1
    name: str = Field(
        default="小さく試す",
        max_length=120,
        description="設定・プリセットの表示名。",
    )
    description: str = Field(
        default="",
        max_length=2000,
        description="想定状況、生成内容、確認事項、実行条件を記載します。選択時に全文を表示。",
    )
    profile_id: str = Field(
        default="default",
        pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="公開・認証・送信先の保存済みプロファイルID。",
    )
    interval_ms: int = Field(
        default=1000,
        ge=10,
        le=60000,
        description="1tickの更新周期。実際の速度はデータ数・接続先・生成内容に依存します。",
    )
    batch_size: int = Field(
        default=5,
        ge=1,
        le=1000,
        description="ログ/RFIDの1tickあたりイベント数。設備・履歴は設備数を使用します。",
    )
    max_ticks: int = Field(
        default=0,
        ge=0,
        le=100000000,
        description="0は停止操作まで継続。指定するとそのtick数で終了します。",
    )
    storage_limit_mb: int = Field(
        default=1024,
        ge=16,
        le=102400,
        description="このアプリのデータ領域の上限MiB。超過時は停止し、既存記録を保持。",
    )
    generator: RunSpec = Field(
        default_factory=RunSpec,
        description="共通の任意項目・分布・乱数シード・時刻・データ異常定義。",
    )
    equipment: Equipment = Field(default_factory=Equipment)
    business: Business = Field(default_factory=Business)
    history: History = Field(default_factory=History)
    logs: Logs = Field(default_factory=Logs)
    identification: Identification = Field(default_factory=Identification)

    @model_validator(mode="after")
    def bounded(self):
        """コレクション名の一意性と初期履歴200万点の上限を検証する。"""
        if len({r.name for r in self.business.resources}) != len(
            self.business.resources
        ):
            raise ValueError("コレクション名は重複できません")
        if (
            self.history.initial_samples
            * self.history.devices
            * len(self.history.tags)
            > 2000000
        ):
            raise ValueError("初期履歴は合計200万点以下にしてください")
        return self


SECRETS = {
    "password",
    "token",
    "opc_password",
    "output_password",
    "output_token",
}
TITLES = {
    "equipment": "OPC UA / Modbus 設備模擬",
    "api": "MES / ERP 業務API模擬",
    "historian": "ヒストリアン / 履歴再生",
    "logs": "ログ / Syslog 発生器",
    "identification": "作業者・RFID・バーコード",
}
