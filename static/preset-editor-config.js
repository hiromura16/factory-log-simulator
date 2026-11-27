"use strict";

(() => {
  function field(path, label, type, options = {}) {
    return { path, label, type, ...options };
  }

  function choices(labels) {
    return Object.entries(labels).map(([value, label]) => ({ value, label }));
  }

  const generatorOptions = choices({
    record_id: "一意のレコードID", uuid: "UUID", sequence: "連番",
    integer: "ランダムな整数", uniform: "一様乱数", normal: "正規分布",
    choice: "候補から選択", boolean: "真偽値", constant: "固定値",
    template: "テンプレート", timestamp: "時刻", reference: "別の項目を参照",
    sum: "合計", difference: "差", product: "積", ratio: "比率",
  });

  const anomalyOptions = choices({
    set: "値の置き換え", add: "加算", multiply: "乗算", ramp: "段階変化",
    freeze: "値の固定", null: "欠損値", copy_from: "別項目からコピー",
    timestamp_shift: "時刻のずれ", omit: "項目を省略",
  });

  function generationSections(prefix) {
    return [
      {
        title: "データ項目と再現性",
        description: "同じシードと設定で同じ合成値を得られます。生成方式ごとの細かい条件はJSONで調整できます。",
        fields: [
          field(prefix + "run_key", "生成の識別子", "text", {
            help: "連番や一意IDの基準です。プリセットの保存IDとは別に指定します。",
          }),
          field(prefix + "seed", "乱数シード", "integer", { min: 0, max: 2147483647, default: 42 }),
          field(prefix + "parameters", "共通パラメーター", "json", {
            help: "JSONオブジェクトで定義します。対応する生成条件から $パラメーター名 で参照できます。",
          }),
          field(prefix + "fields", "生成する項目", "table", {
            default: { name: "new_field", data_type: "string", generator: "constant", value: "" },
            columns: [
              field("name", "項目名", "text"),
              field("data_type", "データ型", "select", {
                options: choices({
                  string: "文字列", integer: "整数", number: "数値", decimal: "小数",
                  boolean: "真偽値", datetime: "日時", json: "JSON",
                }),
              }),
              field("generator", "生成方式", "select", { options: generatorOptions }),
              field("template", "テンプレート", "text", {
                help: "テンプレート方式で参照できる例は {sequence} です。",
              }),
              field("value", "固定値（JSON）", "json"),
            ],
          }),
        ],
      },
      {
        title: "データの異常ルール",
        description: "対象の値を変える条件を追加します。位置は0始まりです。条件式や終了位置はJSONで調整できます。",
        fields: [
          field(prefix + "anomalies", "異常ルール", "table", {
            default: { field: "", operation: "null", from_row: 0, every: 1, enabled: true },
            columns: [
              field("enabled", "有効", "boolean", {default: true}),
              field("field", "対象項目", "text"),
              field("operation", "変更方法", "select", { options: anomalyOptions }),
              field("from_row", "開始位置", "integer", { min: 0, max: 100000000 }),
              field("every", "何件ごと", "integer", { min: 1, max: 100000000 }),
              field("value", "値（JSON）", "json"),
            ],
          }),
        ],
      },
    ];
  }

  const facilityOptions = [
    "kern · カーネル", "user · ユーザープログラム", "mail · メール", "daemon · デーモン",
    "auth · 認証", "syslog · Syslog内部", "lpr · 印刷", "news · ネットニュース",
    "uucp · UUCP", "clock · 時計", "authpriv · 認証（非公開）", "ftp · FTP",
    "ntp · NTP", "audit · 監査", "alert · 警報", "clock2 · 時計",
    "local0", "local1", "local2", "local3", "local4", "local5", "local6", "local7",
  ].map((name, value) => ({ value, label: value + " · " + name }));

  const severityOptions = [
    "emergency · 緊急", "alert · 即時対応", "critical · 重大", "error · エラー",
    "warning · 警告", "notice · 通知", "info · 情報", "debug · デバッグ",
  ].map((name, value) => ({ value, label: value + " · " + name }));

  const outputs = {
    capture: "アプリ内記録", file: "回転ファイル", udp: "Syslog UDP",
    tcp: "Syslog TCP", tls: "Syslog TLS",
  };

  function summarize(spec, preview) {
    const logs = spec?.logs || {};
    const format = logs.format ?? "rfc5424";
    const facility = logs.facility ?? 16;
    const severity = logs.severity ?? 6;
    const duplicateEvery = logs.duplicate_every ?? 0;
    const rotate = logs.rotate_mb ?? 10;
    const backups = logs.backups ?? 5;
    const rows = [];

    if (["rfc5424", "rfc3164"].includes(format)
        && Number.isInteger(facility) && facility >= 0 && facility <= 23
        && Number.isInteger(severity) && severity >= 0 && severity <= 7) {
      rows.push({
        label: "SyslogのPRI",
        value: "<" + (facility * 8 + severity) + ">（facility " + facility + " × 8 + severity " + severity + "）",
      });
    }
    const number = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 2 });
    let rate = null;
    if (Number.isFinite(spec?.batch_size) && spec.batch_size > 0
        && Number.isFinite(spec?.interval_ms) && spec.interval_ms > 0) {
      rate = spec.batch_size * 1000 / spec.interval_ms;
      if (Number.isInteger(duplicateEvery) && duplicateEvery > 0) rate *= 1 + 1 / duplicateEvery;
      rows.push({ label: "生成レートの目安", value: number.format(rate) + " 行／秒（重複を含む、処理時間を除く）" });
    }
    if (Number.isInteger(rotate) && rotate > 0 && Number.isInteger(backups) && backups > 0) {
      rows.push({
        label: "回転ファイルの上限内訳",
        value: rotate + " MiB × " + (backups + 1) + " 本（現行1本 ＋ 旧世代）／" + rotate * (backups + 1) + " MiB目安",
      });
    }

    const plan = preview?.log_preview;
    if (!plan?.samples?.length) return rows;
    rows.push({
      label: "出力先",
      value: (outputs[plan.output] ?? "未登録") + (plan.tcp_framing ? "／" + plan.tcp_framing : ""),
    });
    for (const sample of plan.samples.slice(0, 3)) {
      rows.push({
        label: "ログ見本 #" + sample.sequence + "（固定の見本時刻）",
        value: sample.payload.length > 700 ? sample.payload.slice(0, 700) + "…" : sample.payload,
      });
      const flags = [sample.duplicate ? "重複あり" : "", sample.malformed ? "不正ヘッダー" : ""].filter(Boolean);
      rows.push({
        label: "見本 #" + sample.sequence + " のサイズ",
        value: number.format(sample.message_bytes) + " B（UTF-8）"
          + (sample.wire_bytes == null ? "" : "／TCP境界込み " + number.format(sample.wire_bytes) + " B")
          + (flags.length ? "／" + flags.join("、") : ""),
      });
    }
    if (rate !== null && Number.isFinite(rate)) {
      const average = plan.samples.reduce((sum, sample) => sum + sample.message_bytes, 0) / plan.samples.length;
      const bytesPerHour = (average + 1) * rate * 3600;
      rows.push({ label: "1時間の本文量の目安", value: number.format(bytesPerHour / 1024 ** 2) + " MiB（見本と設定レートから算出）" });
      if (plan.output === "file" && bytesPerHour > 0 && Number.isInteger(rotate) && rotate > 0) {
        rows.push({ label: "ファイル1本が回転する間隔の目安", value: number.format(rotate * 1024 ** 2 / bytesPerHour * 60) + " 分" });
      }
    }
    return rows;
  }

  window.FactoryPresetConfig = {
    title: "ログプリセット",
    description: "ログの書式、重要度、ファイルの回転と異常の出し方をまとめて編集します。見本では送信・ファイル出力をしません。",
    summarize,
    sections: [
      {
        title: "出力先と発生ペース",
        description: "ローカル回転ファイル、UDP、TCP、TLSや記録のみを出力プロファイルで選びます。アドレス、ポート、証明書は出力プロファイルの画面で管理します。",
        fields: [
          field("profile_id", "出力プロファイル", "connection", { default: "default" }),
          field("interval_ms", "発生間隔（ms）", "integer", { min: 10, max: 60000, default: 1000 }),
          field("batch_size", "1回に生成する行数", "integer", { min: 1, max: 1000, default: 5 }),
          field("max_ticks", "発生回数の上限", "integer", {
            min: 0, max: 100000000, default: 0, help: "0は回数制限なし。",
          }),
          field("storage_limit_mb", "ストレージ使用量の上限（MiB）", "integer", {
            min: 16, max: 102400, default: 1024,
            help: "アプリの保存領域がこの容量に達すると停止します。",
          }),
        ],
      },
      {
        title: "ログの書式と本文",
        fields: [
          field("logs.format", "ログの書式", "select", {
            default: "rfc5424",
            options: choices({
              rfc5424: "RFC 5424 · Syslog（構造化ヘッダー）", rfc3164: "RFC 3164 · Syslog（従来形式）",
              jsonl: "JSON Lines · 1行1オブジェクト", plain: "プレーンテキスト",
            }),
          }),
          field("logs.facility", "Facility（発生元の分類）", "select", {
            options: facilityOptions, default: 16,
            when: { path: "logs.format", equals: ["rfc5424", "rfc3164", "jsonl"] },
          }),
          field("logs.severity", "Severity（重要度）", "select", {
            options: severityOptions, default: 6,
            when: { path: "logs.format", equals: ["rfc5424", "rfc3164", "jsonl"] },
          }),
          field("logs.hostname", "模擬ホスト名", "text", {
            placeholder: "factory-device",
            when: { path: "logs.format", equals: ["rfc5424", "rfc3164", "jsonl"] },
          }),
          field("logs.app_name", "模擬アプリ名", "text", {
            placeholder: "mes-demo",
            when: { path: "logs.format", equals: ["rfc5424", "rfc3164", "jsonl"] },
          }),
          field("logs.message_template", "本文テンプレート", "textarea", {
            placeholder: "entity={entity_id} status={status} value={value}",
            help: "生成項目や {sequence} を参照できます。未定義の項目や型の合わない書式は検証で表示します。",
          }),
        ],
      },
      {
        title: "通信境界・ローテーション",
        fields: [
          field("logs.tcp_framing", "TCP／TLSのメッセージ境界", "select", {
            default: "octet_counting",
            options: choices({ octet_counting: "バイト数 ＋ 空白 ＋ 本文", newline: "末尾改行で区切る" }),
            help: "受信側と同じ境界方式を選びます。RFC 6587のバイト数はUTF-8で数えます。",
          }),
          field("logs.rotate_mb", "回転ファイル1本の上限（MiB）", "integer", {
            min: 1, max: 100, default: 10, help: "出力先が回転ファイルのときだけ使用します。",
          }),
          field("logs.backups", "保存する旧世代の本数", "integer", { min: 1, max: 30, default: 5 }),
        ],
      },
      {
        title: "収集側の異常テスト",
        fields: [
          field("logs.duplicate_every", "何行ごとに重複させるか", "integer", {
            min: 0, default: 0, help: "0で無効。指定間隔で同じ本文をもう1行発生させます。",
          }),
          field("logs.malformed_every", "何行ごとにヘッダーを崩すか", "integer", {
            min: 0, default: 0, help: "0で無効。受信側の不正ログ処理を確認できます。",
          }),
        ],
      },
      ...generationSections("generator."),
    ],
  };
})();
