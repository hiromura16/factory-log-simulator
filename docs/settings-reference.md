# 設定リファレンス

画面の表示名、JSONキー、意味、制約、既定値を確認できます。
接続方式や選択した形式によって表示される設定が変わります。
共通形式の別アプリ用の項目も掲載しています。該当する出力方式で使う設定を選んでください。

[JSONの書き方](template-guide.md) · [ひな型の選び方](preset-guide.md)

## 公開・生成ひな型

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `$schema` | **エディターのスキーマ参照**　JSONエディターの補完に使うスキーマのファイルパスまたはURL。アプリは取得せず、保存済み設定にも含めません。 **画面に表示されません。** | 文字列 / null。省略可。既定 null。最長 2048 |
| `_comment` | **エディター用のメモ**　テンプレートに書ける編集者向けメモ。アプリの挙動を変えず、取込・保存・書き出しでは省かれます。 **画面に表示されません。** | 文字列 / null。省略可。既定 null。最長 4000 |
| `version` | **設定バージョン**　このアプリはバージョン2のプリセットJSONを使用します。 **画面に表示されません。** | 整数。省略可。既定 1。固定値 1 |
| `name` | **表示名**　設定・プリセットの表示名。 | 文字列。省略可。既定 "小さく試す"。最長 120 |
| `description` | **用途・メモ**　想定状況、生成内容、確認事項、実行条件を記載します。選択時に全文を表示。 | 文字列。省略可。既定 ""。最長 2000 |
| `profile_id` | **Profile Id**　公開・認証・送信先の保存済みプロファイルID。 | 文字列。省略可。既定 "default"。書式 "^[A-Za-z0-9_-]{1,64}$" |
| `interval_ms` | **Interval Ms**　1tickの更新周期。実際の速度はデータ数・接続先・生成内容に依存します。 | 整数。省略可。既定 1000。最小 10。最大 60000 |
| `batch_size` | **バッチ件数**　ログ/RFIDの1tickあたりイベント数。設備・履歴は設備数を使用します。 | 整数。省略可。既定 5。最小 1。最大 1000 |
| `max_ticks` | **Max Ticks**　0は停止操作まで継続。指定するとそのtick数で終了します。 | 整数。省略可。既定 0。最小 0。最大 100000000 |
| `storage_limit_mb` | **Storage Limit Mb**　このアプリのデータ領域の上限MiB。超過時は停止し、既存記録を保持。 | 整数。省略可。既定 1024。最小 16。最大 102400 |
| `generator` | **任意項目とデータ異常**　共通の任意項目・分布・乱数シード・時刻・データ異常定義。 | データの生成条件（RunSpec）。省略可 |
| `equipment` | **設備プロトコル設定**　設備プロトコル設定の設定。現在の型と選択肢に合わせて指定します。 **画面に表示されません。** | 設備と通信異常（Equipment）。省略可 |
| `business` | **業務API設定**　業務API設定の設定。現在の型と選択肢に合わせて指定します。 **画面に表示されません。** | 業務APIと模擬障害（Business）。省略可 |
| `history` | **時系列保存設定**　時系列保存設定の設定。現在の型と選択肢に合わせて指定します。 **画面に表示されません。** | 履歴と品質（History）。省略可 |
| `logs` | **ログ設定**　ログ設定の設定。現在の型と選択肢に合わせて指定します。 | ログ形式とローテーション（Logs）。省略可 |
| `identification` | **作業者・RFID設定**　作業者・RFID設定の設定。現在の型と選択肢に合わせて指定します。 **画面に表示されません。** | タグと読取経路（Identification）。省略可 |

### 異常データの条件（AnomalyRule）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `AnomalyRule.$schema` | **エディターのスキーマ参照**　JSONエディターの補完に使うスキーマのファイルパスまたはURL。アプリは取得せず、保存済み設定にも含めません。 **画面に表示されません。** | 文字列 / null。省略可。既定 null。最長 2048 |
| `AnomalyRule._comment` | **エディター用のメモ**　テンプレートに書ける編集者向けメモ。アプリの挙動を変えず、取込・保存・書き出しでは省かれます。 **画面に表示されません。** | 文字列 / null。省略可。既定 null。最長 4000 |
| `AnomalyRule.name` | **表示名**　一覧と実行履歴に表示する名前。業種や工場の種類を指定する必要はありません。 | 文字列。省略可。既定 "異常注入"。最短 1。最長 120 |
| `AnomalyRule.enabled` | **異常注入を有効にする**　無効なら、このルールまたは障害設定を適用しません。通常生成との比較に使用できます。 | 真偽値。省略可。既定 true |
| `AnomalyRule.field` | **異常を注入する項目名**　生成するデータ項目の名前。正常行の生成後に変更するため、先行項目だけでなく任意の生成項目を指定できます。 | 文字列。必須。書式 "^[A-Za-z_][A-Za-z0-9_]{0,62}$" |
| `AnomalyRule.operation` | **異常の作り方**　set=値を置換、add=加算、multiply=倍率、ramp=開始位置から増加するドリフト、freeze=開始位置の値に固着、null=NULL、copy_from=指定位置の値をコピー、timestamp_shift=秒単位の時刻ずらし、omit=項目自体を欠落。加算・倍率・ドリフトは元の値が欠測・非数値の行では適用しません。 | 文字列。省略可。既定 "set"。選択肢 "set" / "add" / "multiply" / "ramp" / "freeze" / "null" / "copy_from" / "timestamp_shift" / "omit" |
| `AnomalyRule.value` | **置換値 / 増分 / 倍率 / 秒数 JSON**　setの値、add/rampの増分、multiplyの倍率、timestamp_shiftの秒数、copy_fromの実行内コピー元位置（0始まり）を指定。$parameter参照も可能。freeze/null/omitでは使いません。 | JSON値。省略可。既定 null |
| `AnomalyRule.from_row` | **異常の開始位置（0始まり）**　この実行内のレコード位置。20なら21件目から適用。start_sequenceとは別で、分割実行時は実行内の位置として評価します。 | 整数。省略可。既定 0。最小 0。最大 100000000 |
| `AnomalyRule.to_row` | **異常の終了位置（含む）**　空欄は最後まで。例: from_row=20、to_row=29なら10件の異常期間です。 | 整数 / null。省略可。既定 null。最小 0。最大 100000000 |
| `AnomalyRule.every` | **何件ごとに異常を適用するか**　開始位置から何件ごとに適用するか。1は全件、10は10件ごと。probabilityと組み合わせて断続的な異常を作ります。 | 整数。省略可。既定 1。最小 1。最大 100000000 |
| `AnomalyRule.probability` | **異常が発生する確率**　適用位置・条件を満たした行に対する0〜1の確率。同じrun_keyとseedなら再現可能です。 | 数値。省略可。既定 1。最小 0。最大 1 |
| `AnomalyRule.when` | **異常を適用する条件**　生成後の値を比較し、一致する場合だけ異常を適用します。先に適用した異常の結果も参照できます。then_valueの指定は不要です。 | 異常を適用する条件（Predicate） / null。省略可。既定 null |
| `AnomalyRule.bypass_validation` | **型・必須検証を意図的に外す**　数値欄へ文字列、主キーへNULL等の不正値を作る場合に有効化。送信JSONは構文上有効のままですが、DBや受信側は拒否し得ます。omitはこの設定に関係なく項目を欠落させます。 | 真偽値。省略可。既定 false |

### 業務APIと模擬障害（Business）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `Business.resources` | **Resources**　公開するコレクション。指図・在庫・実績等を別URLと独自の列定義で用意できます。 **このアプリでは適用外。** | 配列［コレクション（Resource）］。省略可。最小件数 1。最大件数 30 |
| `Business.updates_per_tick` | **Updates Per Tick**　各tickで更新するレコード数。0は固定データ。idは維持し、値・revisionを更新します。 **このアプリでは適用外。** | 整数。省略可。既定 2。最小 0。最大 10000 |
| `Business.delete_every_ticks` | **Delete Every Ticks**　0は削除なし。指定tickごとに1件を論理削除し、deltaの削除通知を試験。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `Business.cursor_ttl_seconds` | **Cursor Ttl Seconds**　署名付きページングカーソルの有効期限。期限切れは410です。 **このアプリでは適用外。** | 整数。省略可。既定 600。最小 1。最大 86400 |
| `Business.page_size` | **Page Size**　既定のページ件数。snapshot基準のページングで更新中も同じ集合を読みます。 **このアプリでは適用外。** | 整数。省略可。既定 100。最小 1。最大 1000 |
| `Business.fault` | **Fault**　Faultの設定。現在の型と選択肢に合わせて指定します。 **このアプリでは適用外。** | 文字列。省略可。既定 "none"。選択肢 "none" / "rate_limit" / "server_error" / "unauthorized" / "delay" / "duplicate_page" / "skip_page" / "truncate_json" / "cursor_expired" |
| `Business.fault_every` | **Fault Every**　データ取得APIへのリクエスト何回ごとに異常を返すか。管理UIの通信は含みません。 **このアプリでは適用外。** | 整数。省略可。既定 5。最小 1 |
| `Business.fault_delay_ms` | **Fault Delay Ms**　API異常=delayの待機時間。 **このアプリでは適用外。** | 整数。省略可。既定 1000。最小 0。最大 10000 |

### 値を上書きする条件（Condition）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `Condition.field` | **比較する先行項目**　すでに生成された項目名。例: status。 | 文字列。必須。書式 "^[A-Za-z_][A-Za-z0-9_]{0,62}$" |
| `Condition.operator` | **比較方法**　eq/neは一致・不一致、gt/ge/lt/leは大小比較、inは配列に含まれるかを判定します。大小比較では欠測値や比較できない型は不一致になります。inの比較値はJSON配列、または配列を参照する共有パラメーターを指定します。 | 文字列。省略可。既定 "eq"。選択肢 "eq" / "ne" / "gt" / "ge" / "lt" / "le" / "in" |
| `Condition.value` | **固定値 / 比較値 JSON**　文字列は"sample"、数値は123、真偽値はtrue、空値はnull。"$parameter"で共有値を参照できます。 | JSON値。省略可。既定 null |
| `Condition.then_value` | **一致したときの値 JSON**　条件が真の場合に上書きする値。"$parameter"の参照も可能です。 | JSON値。省略可。既定 null |

### 設備と通信異常（Equipment）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `Equipment.devices` | **Devices**　模擬設備数。Modbus device IDは1から設備数まで。OPC UAにも同数の設備オブジェクトを公開。 **このアプリでは適用外。** | 整数。省略可。既定 4。最小 1。最大 247 |
| `Equipment.registers` | **Registers**　データ項目とレジスターの対応表。領域内でアドレス幅が重複しないよう指定します。 **このアプリでは適用外。** | 配列［Modbusレジスター（Register）］。省略可。最大件数 100 |
| `Equipment.quality` | **品質コード**　Goodは正常、Badは利用不適、Uncertainは確実でない値。設備用はOPC UAの実StatusCodeへ変換します。 **このアプリでは適用外。** | 文字列。省略可。既定 "Good"。選択肢 "Good" / "BadSensorFailure" / "UncertainLastUsableValue" |
| `Equipment.quality_from_tick` | **Quality From Tick**　このtick以降に品質コードを適用します。0は開始直後。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `Equipment.quality_until_tick` | **Quality Until Tick**　0は最後まで。このtickを過ぎるとGoodへ戻ります。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `Equipment.offline_from_tick` | **Offline From Tick**　0は切断なし。このtick以降、指定期間だけプロトコル待受を停止し再接続を試験。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `Equipment.offline_ticks` | **Offline Ticks**　切断状態を続けるtick数。その後は同じノード・アドレスで待受を再開。 **このアプリでは適用外。** | 整数。省略可。既定 5。最小 1。最大 10000 |
| `Equipment.read_delay_ms` | **Read Delay Ms**　Modbusの読取応答を遅延させる時間。OPC UAでは更新周期を使用してください。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0。最大 5000 |
| `Equipment.writable` | **Writable**　クライアントの書き込みを許可。生成周期の次の更新で生成値へ戻ります。 **このアプリでは適用外。** | 真偽値。省略可。既定 false |

### 実行処理の障害（FaultOptions）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `FaultOptions.enabled` | **異常注入を有効にする**　無効なら、このルールまたは障害設定を適用しません。通常生成との比較に使用できます。 **このアプリでは適用外。** | 真偽値。省略可。既定 false |
| `FaultOptions.stage` | **障害を注入する段階**　before_batch: SQL/ファイルは処理前、ストリームはoutbox記録後の送信前。after_write: SQLはCOMMIT前、ファイルはマニフェスト前、ストリームは送信ACK後の配送済み記録前。 **このアプリでは適用外。** | 文字列。省略可。既定 "before_batch"。選択肢 "before_batch" / "after_write" |
| `FaultOptions.action` | **障害の動作**　none=処理障害なし（不正ファイル指定だけ使う場合等）、fail=意図的な例外で停止、delay=指定時間だけ待機。ストリームの再試行を指定するとfailを再試行でき、ACK消失時には重複送信し得ます。 **このアプリでは適用外。** | 文字列。省略可。既定 "none"。選択肢 "none" / "fail" / "delay" |
| `FaultOptions.from_batch` | **障害の開始バッチ（1始まり）**　2なら2バッチ目から注入。バッチ件数を小さくすると、正常分を先に配送・確定してから障害を発生させられます。 **このアプリでは適用外。** | 整数。省略可。既定 1。最小 1。最大 100000000 |
| `FaultOptions.every_batches` | **何バッチごとに障害を発生させるか**　1は毎バッチ、5は開始バッチから5バッチごと。最大回数と組み合わせて一過性・継続障害を作れます。 **このアプリでは適用外。** | 整数。省略可。既定 1。最小 1。最大 100000000 |
| `FaultOptions.max_occurrences` | **障害の最大回数**　1は1回だけ。0は回数制限なし。再試行時も回数に含みます。永続的な障害は0、一過性の障害は1等を指定。 **このアプリでは適用外。** | 整数。省略可。既定 1。最小 0。最大 1000000 |
| `FaultOptions.delay_ms` | **模擬遅延 ms**　action=delayの待機時間。実行時間の上限と停止要求を確認しながら待機します。実際の接続先を遅くする設定ではありません。 **このアプリでは適用外。** | 整数。省略可。既定 1000。最小 0。最大 60000 |
| `FaultOptions.artifact_mode` | **意図的に不正なファイルを作る**　ファイルツール専用。JSON切断 / 不正UTF-8 / CSVヘッダー不一致 / 画像切断 / 拡張子不一致 / マニフェストSHA256不一致。取り込み側の検知・隔離を試験します。 **このアプリでは適用外。** | 文字列。省略可。既定 "none"。選択肢 "none" / "truncate_json" / "invalid_json_utf8" / "csv_header_mismatch" / "truncate_image" / "wrong_image_extension" / "manifest_checksum_mismatch" |

### 項目と値の生成方法（FieldRule）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `FieldRule.$schema` | **エディターのスキーマ参照**　JSONエディターの補完に使うスキーマのファイルパスまたはURL。アプリは取得せず、保存済み設定にも含めません。 **画面に表示されません。** | 文字列 / null。省略可。既定 null。最長 2048 |
| `FieldRule._comment` | **エディター用のメモ**　テンプレートに書ける編集者向けメモ。アプリの挙動を変えず、取込・保存・書き出しでは省かれます。 **画面に表示されません。** | 文字列 / null。省略可。既定 null。最長 4000 |
| `FieldRule.name` | **項目名**　英字または下線で始まる英数字・下線、63文字まで。SQLの列名・CSVヘッダー・JSONキーになります。項目間参照にもこの名前を使います。 | 文字列。必須。書式 "^[A-Za-z_][A-Za-z0-9_]{0,62}$" |
| `FieldRule.data_type` | **値の型**　string / integer / number / decimal / boolean / datetime / json。decimalは正確な小数文字列、日時はUTC ISO形式。SQL保存時は対応する列の型に変換します。 | 文字列。省略可。既定 "string"。選択肢 "string" / "integer" / "number" / "decimal" / "boolean" / "datetime" / "json" |
| `FieldRule.generator` | **生成ルール**　record_id=再現可能なキー、uuid=UUID、sequence=連番、integer/uniform/normal=分布、choice=重み付き選択、boolean=確率、constant=固定、template=書式、timestamp=時刻、reference/四則演算=先行項目から派生。 | 文字列。省略可。既定 "constant"。選択肢 "record_id" / "uuid" / "sequence" / "integer" / "uniform" / "normal" / "choice" / "boolean" / "constant" / "template" / "timestamp" / "reference" / "sum" / "difference" / "product" / "ratio" |
| `FieldRule.primary_key` | **SQL 主キー**　テーブル作成時の主キー定義。upsert / update / deleteには接続先と一致する主キーが必要です。複数の項目を指定すると複合キーになります。 **画面に表示されません。** | 真偽値。省略可。既定 false |
| `FieldRule.length` | **文字数の上限**　stringの最大文字数。生成結果を検証し、新規SQLテーブルの列長にも使用します。1〜4000。 | 整数。省略可。既定 255。最小 1。最大 4000 |
| `FieldRule.precision` | **小数の精度**　decimal全体の桁数。1〜38。SQLのNUMERIC(precision,scale)に対応します。 | 整数。省略可。既定 18。最小 1。最大 38 |
| `FieldRule.scale` | **小数桁数 / 丸め桁数**　decimalの小数桁数、numberの丸め桁数。decimalでは精度以下に指定します。 | 整数。省略可。既定 3。最小 0。最大 18 |
| `FieldRule.minimum` | **最小値 / パラメーター参照**　integer / uniformの最小値。数値または$countのような共有パラメーター参照。 | 整数 / 数値 / 文字列。省略可。既定 0 |
| `FieldRule.maximum` | **最大値 / パラメーター参照**　integer / uniformの最大値。integerは両端を含みます。数値または$parameter。 | 整数 / 数値 / 文字列。省略可。既定 100 |
| `FieldRule.mean` | **平均**　正規分布normalの平均値。例: 50、または$value_mean。 | 整数 / 数値 / 文字列。省略可。既定 50 |
| `FieldRule.stddev` | **標準偏差**　normalのばらつき。0なら常に平均値。0以上、または共有パラメーター参照。 | 整数 / 数値 / 文字列。省略可。既定 5 |
| `FieldRule.start` | **開始値 / 開始日時**　sequenceでは数値、timestampではタイムゾーン付きISO日時。例: 2026-11-13T09:00:00+09:00。$start_timeで参照も可能。 | 整数 / 数値 / 文字列。省略可。既定 0 |
| `FieldRule.step` | **増分 / 秒間隔**　sequenceは開始値に足す量、timestampは時刻を進める秒数。小数・負数・$parameterも指定できます。 | 整数 / 数値 / 文字列。省略可。既定 1 |
| `FieldRule.group_size` | **同じ連番値を使う件数**　sequence / timestampの増分を適用する前にまとめる件数。10なら0〜9番が同じ時刻・連番値になります。1以上または$parameter。 | 整数 / 文字列。省略可。既定 1 |
| `FieldRule.modulo` | **連番値の繰り返し周期**　0は繰り返さない。10なら連番のインデックスが0〜9を繰り返します。sequence / timestampに適用。 | 整数 / 文字列。省略可。既定 0 |
| `FieldRule.probability` | **true の確率**　boolean生成器のtrueの割合。0〜1、または$parameter。例: 0.02。 | 数値 / 文字列。省略可。既定 0.5 |
| `FieldRule.choices` | **選択肢 JSON / 参照**　例: ["ok","warning","ng"]、または"$statuses"。型はデータ型と合わせてください。 | 配列［JSON値］ / 文字列。省略可 |
| `FieldRule.weights` | **選択肢の重み JSON**　例: [95,4,1]。選択肢と同じ個数で、0以上かつ合計が正。空の配列[]なら均等に選びます。 | 配列［数値］。省略可 |
| `FieldRule.value` | **固定値 / 比較値 JSON**　文字列は"sample"、数値は123、真偽値はtrue、空値はnull。"$parameter"で共有値を参照できます。 | JSON値。省略可。既定 null |
| `FieldRule.template` | **文字列テンプレート**　例: DEV-{entity_no:05d}。先行項目、共有パラメーター、{sequence}、{record_id}を参照できます。属性アクセスや任意コードは実行しません。 | 文字列。省略可。既定 "{sequence}"。最長 2048 |
| `FieldRule.sources` | **参照元の項目名 JSON**　例: ["amount","unit_price"]。referenceは先頭、sum / difference / product / ratioは指定した先行項目を使用します。ratioは2項目で分母0不可。 | 配列［文字列］。省略可。最大件数 32 |
| `FieldRule.null_probability` | **NULL の確率**　生成結果をNULLに置き換える確率。0〜1。SQL主キーには指定できません。 | 数値。省略可。既定 0。最小 0。最大 1 |
| `FieldRule.condition` | **条件による値の上書き**　有効にすると先行項目と比較し、一致する場合にthen_valueを採用。条件不一致時は通常の生成値を使用します。 | 値を上書きする条件（Condition） / null。省略可。既定 null |

### ファイルの形式と完了通知（FileOptions）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `FileOptions.formats` | **出力形式 JSON**　["json","csv","image"]から1つ以上。画像だけ、JSONとCSVだけ、など自由に組み合わせられます。 **このアプリでは適用外。** | 配列［文字列］。省略可。最小件数 1。最大件数 3。選択肢 "json" / "csv" / "image" |
| `FileOptions.records_per_file` | **ファイルあたりの件数**　JSON配列 / JSONL / CSVを分割する最大件数。objectモードは常に1レコード1ファイル。メモリ上限のため小さくなる場合があります。 **このアプリでは適用外。** | 整数。省略可。既定 100。最小 1。最大 10000 |
| `FileOptions.path_template` | **出力サブディレクトリ**　例: {run_key}/{job_id}。共有パラメーターも使用可能。相対パスのみ、..は禁止。job_idを含めると再実行時の衝突を避けられます。 **このアプリでは適用外。** | 文字列。省略可。既定 "{run_key}/{job_id}"。最長 512 |
| `FileOptions.filename_template` | **ファイル名テンプレート**　例: {sequence:010d}-{record_id}。拡張子は自動付加。バッチ先頭の項目・共有値・run_key・job_idを参照可能。重複名はエラーになるので連番等を含めます。 **このアプリでは適用外。** | 文字列。省略可。既定 "{sequence:010d}-{record_id}"。最長 256 |
| `FileOptions.json_mode` | **JSON の格納形式**　array=配列、object=1レコード1ファイル、jsonl=1行1レコード。 **このアプリでは適用外。** | 文字列。省略可。既定 "array"。選択肢 "array" / "object" / "jsonl" |
| `FileOptions.json_pretty` | **JSON の整形**　array / objectを字下げして見やすくします。JSONLでは無効。ファイルサイズが増えます。 **このアプリでは適用外。** | 真偽値。省略可。既定 false |
| `FileOptions.json_template` | **JSON 構造テンプレート**　nullなら生成行をそのまま出力。例: {"device":"$row.entity_id","metrics":{"value":"$row.value"},"key":"$meta.record_key"}。$parameters.xも利用可能。 **このアプリでは適用外。** | JSON値。省略可。既定 null |
| `FileOptions.compression` | **JSON / CSV 圧縮**　noneまたはgzip。gzip時は.json.gz / .csv.gz等になり、画像・sidecar・manifestは圧縮しません。 **このアプリでは適用外。** | 文字列。省略可。既定 "none"。選択肢 "none" / "gzip" |
| `FileOptions.csv_delimiter` | **CSV 区切り文字**　1文字。例: , または ;。タブ区切りはJSON編集で\tを指定できます。 **このアプリでは適用外。** | 文字列。省略可。既定 ","。最短 1。最長 1 |
| `FileOptions.csv_quotechar` | **CSV 引用文字**　通常は二重引用符。1文字で指定します。区切り・改行を含む値はCSVライターが処理します。 **このアプリでは適用外。** | 文字列。省略可。既定 "\""。最短 1。最長 1 |
| `FileOptions.csv_quoting` | **CSV 引用規則**　minimal=必要なセル、all=全セル、nonnumeric=文字列セルを引用します。 **このアプリでは適用外。** | 文字列。省略可。既定 "minimal"。選択肢 "minimal" / "all" / "nonnumeric" |
| `FileOptions.csv_header` | **CSV ヘッダー行**　有効なら最初に項目名を書き込みます。列順はデータ項目の順序です。 **このアプリでは適用外。** | 真偽値。省略可。既定 true |
| `FileOptions.csv_null_value` | **CSV のNULL表現**　空文字が既定。例: NULL、\N。JSON値はJSON文字列としてセルへ保存します。 **このアプリでは適用外。** | 文字列。省略可。既定 ""。最長 255 |
| `FileOptions.csv_newline` | **CSV 改行コード**　LFまたはCRLF。読み込み先の仕様に合わせて指定します。 **このアプリでは適用外。** | 文字列。省略可。既定 "LF"。選択肢 "LF" / "CRLF" |
| `FileOptions.csv_encoding` | **CSV 文字コード**　utf-8-sigはBOM付きUTF-8でExcel等向け。utf-8はBOMなし。 **このアプリでは適用外。** | 文字列。省略可。既定 "utf-8-sig"。選択肢 "utf-8" / "utf-8-sig" |
| `FileOptions.write_sidecars` | **画像のメタデータ保存**　画像ごとの.meta.jsonにレコード・record_key・疑似欠陥ラベルを保存。画像は実物の検査写真ではなく人工パターンです。 **このアプリでは適用外。** | 真偽値。省略可。既定 true |
| `FileOptions.write_manifest` | **完了マニフェスト保存**　各バッチの全ファイル保存後に.ready.jsonを最後に作成します。下流はこれを取り込みの目印にできます。SHA256とサイズを記録します。 **このアプリでは適用外。** | 真偽値。省略可。既定 true |
| `FileOptions.image` | **疑似検査画像の条件**　格子・グラデーション・ドットの人工画像を再現可能に生成します。外部画像検索やAI APIは使用しません。 **このアプリでは適用外。** | 画像の生成（ImageOptions）。省略可 |

### 履歴と品質（History）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `History.tags` | **Tags**　保存する生成項目。タグ名はdevice-001.value等になります。 **このアプリでは適用外。** | 配列［文字列］。省略可。最小件数 1。最大件数 100 |
| `History.devices` | **Devices**　時系列を作る設備数。 **このアプリでは適用外。** | 整数。省略可。既定 4。最小 1。最大 1000 |
| `History.initial_samples` | **Initial Samples**　開始時に作る過去サンプルの時点数。タグ・設備数を掛けた総点数は上限で検証します。 **このアプリでは適用外。** | 整数。省略可。既定 1000。最小 0。最大 1000000 |
| `History.sample_seconds` | **Sample Seconds**　疑似イベント時刻のサンプリング間隔秒。更新周期とは別に指定できます。 **このアプリでは適用外。** | 数値。省略可。既定 1。最小 0.01。最大 86400 |
| `History.source_time_field` | **Source Time Field**　空欄はサンプリング間隔から時刻を計算。生成項目名を指定するとその日時と異常ルールを使用します。 **このアプリでは適用外。** | 文字列。省略可。既定 "" |
| `History.shift_every` | **Shift Every**　指定時点ごとにタイムスタンプをずらします。0は変更なし。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `History.timestamp_shift_seconds` | **Timestamp Shift Seconds**　時刻をずらす秒数。負数は遅延・順序逆転。 **このアプリでは適用外。** | 数値。省略可。既定 0 |
| `History.retention_days` | **Retention Days**　サンプルの保持期間。古いサンプルを定期的に削除します。 **このアプリでは適用外。** | 整数。省略可。既定 90。最小 1。最大 3650 |
| `History.quality` | **品質コード**　Goodは正常、Badは利用不適、Uncertainは確実でない値。設備用はOPC UAの実StatusCodeへ変換します。 **このアプリでは適用外。** | 文字列。省略可。既定 "Good"。選択肢 "Good" / "Bad" / "Uncertain" |
| `History.bad_every` | **Bad Every**　0は品質コード変更なし。指定時点ごとにqualityの異常コードを付加します。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `History.missing_every` | **Missing Every**　指定時点ごとにサンプルを保存しません。欠測とNULLを区別する試験。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |

### タグと読取経路（Identification）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `Identification.tags` | **Tags**　模擬タグ・品目の種類数。同じタグが複数読取機を通過します。 **このアプリでは適用外。** | 整数。省略可。既定 100。最小 1。最大 100000 |
| `Identification.readers` | **Readers**　通過順に並べた読取機・工程・ゾーン名。 **このアプリでは適用外。** | 配列［文字列］。省略可。最小件数 1。最大件数 100 |
| `Identification.operators` | **Operators**　架空の作業者ID一覧。実在者の個人情報は使用しません。 **このアプリでは適用外。** | 配列［文字列］。省略可。最小件数 1。最大件数 10000 |
| `Identification.barcode` | **ラベルの方式**　code128は任意のタグ文字列、ean13はチェックディジット付き13桁、qrは二次元コード。PNGをラベルAPIから取得できます。 **このアプリでは適用外。** | 文字列。省略可。既定 "code128"。選択肢 "code128" / "ean13" / "qr" |
| `Identification.duplicate_every` | **Duplicate Every**　指定件ごとに同じevent_idを再送し、二重読取を再現します。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `Identification.drop_every` | **Drop Every**　指定件ごとにイベントを生成結果から落とし、読取漏れを再現。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `Identification.wrong_reader_every` | **Wrong Reader Every**　指定件ごとに予定外の読取機名を出力します。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |
| `Identification.unauthorized_every` | **Unauthorized Every**　指定件ごとに未登録作業者を出力します。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0 |

### 画像の生成（ImageOptions）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `ImageOptions.width` | **画像の幅 px**　32〜4096ピクセル。大きな画像とノイズは生成負荷が増えます。 **このアプリでは適用外。** | 整数。省略可。既定 320。最小 32。最大 4096 |
| `ImageOptions.height` | **画像の高さ px**　32〜4096ピクセル。出力容量と生成速度に影響します。 **このアプリでは適用外。** | 整数。省略可。既定 240。最小 32。最大 4096 |
| `ImageOptions.format` | **画像形式**　png=可逆圧縮、jpeg=非可逆圧縮。JSON / CSVと同じrecord_keyで対応付けます。 **このアプリでは適用外。** | 文字列。省略可。既定 "png"。選択肢 "png" / "jpeg" |
| `ImageOptions.pattern` | **人工画像パターン**　grid=格子、gradient=色の傾斜、dots=点群。背景色と前景色を変更できます。 **このアプリでは適用外。** | 文字列。省略可。既定 "grid"。選択肢 "grid" / "gradient" / "dots" |
| `ImageOptions.noise` | **画素ノイズ強度**　0はなし、1〜64は各RGB成分に加える最大ゆらぎ。CPU負荷が高くなるため小さい値から試します。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0。最大 64 |
| `ImageOptions.defect_probability` | **疑似欠陥の確率**　0〜1。選ばれた画像に傷状の線を描き、sidecarにsynthetic_defectを記録します。 **このアプリでは適用外。** | 数値。省略可。既定 0.05。最小 0。最大 1 |
| `ImageOptions.every` | **画像生成の間引き**　1は全レコード、10はシーケンス番号が10の倍数のときのみ生成。大量の表データと少数画像を組み合わせられます。 **このアプリでは適用外。** | 整数。省略可。既定 1。最小 1。最大 1000000 |
| `ImageOptions.quality` | **JPEG 品質**　10〜100。PNGでは品質設定の効果はありません。 **このアプリでは適用外。** | 整数。省略可。既定 90。最小 10。最大 100 |
| `ImageOptions.background` | **背景色**　#RRGGBB形式。例: #182a3a。 **このアプリでは適用外。** | 文字列。省略可。既定 "#182a3a"。書式 "^#[0-9A-Fa-f]{6}$" |
| `ImageOptions.foreground` | **パターン色**　格子・点・グラデーション終端の#RRGGBB色。 **このアプリでは適用外。** | 文字列。省略可。既定 "#55a69b"。書式 "^#[0-9A-Fa-f]{6}$" |
| `ImageOptions.defect_color` | **疑似欠陥の色**　傷状の線に使う#RRGGBB色。 **このアプリでは適用外。** | 文字列。省略可。既定 "#ef463c"。書式 "^#[0-9A-Fa-f]{6}$" |

### ログ形式とローテーション（Logs）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `Logs.format` | **ログ書式**　png=可逆圧縮、jpeg=非可逆圧縮。JSON / CSVと同じrecord_keyで対応付けます。 | 文字列。省略可。既定 "rfc5424"。選択肢 "jsonl" / "plain" / "rfc5424" / "rfc3164" |
| `Logs.facility` | **Facility**　Syslog facility。local0=16。severityと合わせてPRIを作ります。 | 整数。省略可。既定 16。最小 0。最大 23 |
| `Logs.severity` | **Severity**　Syslog severity。0=emergency、3=error、4=warning、6=info、7=debug。 | 整数。省略可。既定 6。最小 0。最大 7 |
| `Logs.hostname` | **Hostname**　ログに記載する模擬ホスト名。実ホストの個人情報は読み取りません。 | 文字列。省略可。既定 "factory-device"。書式 "^[A-Za-z0-9_.-]{1,255}$" |
| `Logs.app_name` | **App Name**　Syslog APP-NAME。 | 文字列。省略可。既定 "mes-demo"。書式 "^[A-Za-z0-9_.-]{1,48}$" |
| `Logs.message_template` | **Message Template**　生成項目とsequenceを参照するメッセージ書式。 | 文字列。省略可。既定 "entity={entity_id} status={status} value={value}"。最長 6000 |
| `Logs.tcp_framing` | **TCPのメッセージ境界**　octet_countingはRFC6587の「UTF-8バイト数 空白 本文」。newlineは末尾改行。受信側と方式を合わせます。 | 文字列。省略可。既定 "octet_counting"。選択肢 "octet_counting" / "newline" |
| `Logs.rotate_mb` | **Rotate Mb**　ローカルファイルのローテーション容量MiB。 | 整数。省略可。既定 10。最小 1。最大 100 |
| `Logs.backups` | **Backups**　ローテーションで残す過去ファイル数。 | 整数。省略可。既定 5。最小 1。最大 30 |
| `Logs.duplicate_every` | **Duplicate Every**　指定件ごとに同じログを二重出力。 | 整数。省略可。既定 0。最小 0 |
| `Logs.malformed_every` | **Malformed Every**　指定件ごとにヘッダーを壊し、収集側パーサーの隔離を試験。 | 整数。省略可。既定 0。最小 0 |

### 異常を適用する条件（Predicate）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `Predicate.field` | **比較する先行項目**　すでに生成された項目名。例: status。 | 文字列。必須。書式 "^[A-Za-z_][A-Za-z0-9_]{0,62}$" |
| `Predicate.operator` | **比較方法**　eq/neは一致・不一致、gt/ge/lt/leは大小比較、inは配列に含まれるかを判定します。大小比較では欠測値や比較できない型は不一致になります。inの比較値はJSON配列、または配列を参照する共有パラメーターを指定します。 | 文字列。省略可。既定 "eq"。選択肢 "eq" / "ne" / "gt" / "ge" / "lt" / "le" / "in" |
| `Predicate.value` | **固定値 / 比較値 JSON**　文字列は"sample"、数値は123、真偽値はtrue、空値はnull。"$parameter"で共有値を参照できます。 | JSON値。省略可。既定 null |

### Modbusレジスター（Register）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `Register.field` | **比較する先行項目**　生成データの項目名。OPC UAノードやModbusレジスターへ対応付けます。 **このアプリでは適用外。** | 文字列。省略可。既定 "value" |
| `Register.area` | **Modbusの領域**　holding=FC3、input=FC4、coil=FC1、discrete=FC2。アドレスは0始まりです。 **このアプリでは適用外。** | 文字列。省略可。既定 "holding"。選択肢 "holding" / "input" / "coil" / "discrete" |
| `Register.address` | **Address**　0始まりのプロトコルアドレス。40001表記とは異なり、先頭のholding registerは0です。 **このアプリでは適用外。** | 整数。省略可。既定 0。最小 0。最大 65535 |
| `Register.encoding` | **レジスターの型**　16bit整数は1レジスター、32bit/float32は2、float64は4。signedは負数対応。boolはcoil/discrete用。 **このアプリでは適用外。** | 文字列。省略可。既定 "float32"。選択肢 "uint16" / "int16" / "uint32" / "int32" / "float32" / "float64" / "bool" |
| `Register.byte_order` | **1ワード内のバイト順**　bigは通常の上位バイト先頭、littleは16bitワード内のバイトを反転。 **このアプリでは適用外。** | 文字列。省略可。既定 "big"。選択肢 "big" / "little" |
| `Register.word_order` | **複数ワードの順序**　bigは上位ワード先頭、littleは複数ワードを逆順にします。 **このアプリでは適用外。** | 文字列。省略可。既定 "big"。選択肢 "big" / "little" |
| `Register.scale` | **小数桁数 / 丸め桁数**　レジスターへ入れる値=生成値×scale+offset。読取側は逆変換します。 **このアプリでは適用外。** | 数値。省略可。既定 1 |
| `Register.offset` | **Offset**　倍率適用後に加える値。 **このアプリでは適用外。** | 数値。省略可。既定 0 |
| `Register.enum_values` | **Enum Values**　文字列を数値へ変換する対応表。例: {"ok":0,"warning":1,"stopped":2}。 **このアプリでは適用外。** | オブジェクト。省略可 |

### コレクション（Resource）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `Resource.name` | **表示名**　コレクション名。REST/ODataのURLの末尾になります。 **このアプリでは適用外。** | 文字列。省略可。既定 "orders"。書式 "^[A-Za-z_][A-Za-z0-9_]{0,62}$" |
| `Resource.rows` | **生成レコード数**　最初に用意する業務レコード数。 **このアプリでは適用外。** | 整数。省略可。既定 200。最小 1。最大 1000000 |
| `Resource.generator` | **任意項目とデータ異常**　このコレクション専用の項目・生成条件。nullは共通データ定義を使用。 **このアプリでは適用外。** | データの生成条件（RunSpec） / null。省略可。既定 null |

### データの生成条件（RunSpec）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `RunSpec.$schema` | **エディターのスキーマ参照**　JSONエディターの補完に使うスキーマのファイルパスまたはURL。アプリは取得せず、保存済み設定にも含めません。 **画面に表示されません。** | 文字列 / null。省略可。既定 null。最長 2048 |
| `RunSpec._comment` | **エディター用のメモ**　テンプレートに書ける編集者向けメモ。アプリの挙動を変えず、取込・保存・書き出しでは省かれます。 **画面に表示されません。** | 文字列 / null。省略可。既定 null。最長 4000 |
| `RunSpec.version` | **設定バージョン**　このアプリはバージョン2のプリセットJSONを使用します。 **画面に表示されません。** | 整数。省略可。既定 2。固定値 2 |
| `RunSpec.name` | **表示名**　一覧と実行履歴に表示する名前。業種や工場の種類を指定する必要はありません。 **画面に表示されません。** | 文字列。省略可。既定 "カスタムデータ"。最短 1。最長 120 |
| `RunSpec.description` | **用途・メモ**　このプリセットの用途、変更した設定、実行前の条件を記録できます。選択欄にも表示します。接続先のパスワード等は記載せず、接続プロファイルへ保存してください。 **画面に表示されません。** | 文字列。省略可。既定 ""。最長 1000 |
| `RunSpec.connection_id` | **接続プロファイル**　この実行に使用する保存済みの接続先。プリセットにはIDだけが入ります。認証情報は接続プロファイル側で管理します。 **画面に表示されません。** | 文字列。省略可。既定 "default"。書式 "^[A-Za-z0-9_-]{1,64}$" |
| `RunSpec.connection_revision` | **接続リビジョン固定**　通常はnull。実行開始時に接続設定の版を固定するので、実行中の接続先変更に影響されません。指定すると過去の版を使用します。 **画面に表示されません。** | 整数 / null。省略可。既定 null。最小 1 |
| `RunSpec.run_key` | **実行キー**　再現性と重複判定の単位。英数字・ハイフン・下線。seedとシーケンスが同じなら同じrecord_idになります。別のデータ系列には別のキーを指定します。 | 文字列。省略可。既定 "trial-001"。書式 "^[A-Za-z0-9_-]{1,64}$" |
| `RunSpec.seed` | **乱数シード**　同じ実行キー・シード・シーケンス・項目名なら同じ値。0〜2147483647。 | 整数。省略可。既定 42。最小 0。最大 2147483647 |
| `RunSpec.rows` | **生成レコード数**　1〜1億件。SQLは行数、ファイルはレコード数、ストリームはイベント数。画像は間引き設定により少なくなります。全件をメモリには保持しません。 **画面に表示されません。** | 整数。省略可。既定 30。最小 1。最大 100000000 |
| `RunSpec.target_rate` | **目標レコード数 / 秒**　0は速度制限なし。バッチ単位で調整する目標値です。実際の速度はDB・ディスク・通信・生成条件で変わります。まず少量で測定してください。 **画面に表示されません。** | 整数。省略可。既定 10。最小 0。最大 1000000 |
| `RunSpec.batch_size` | **バッチ件数**　1〜10000。SQLはトランザクション、ストリームは送信単位。ファイルはファイルあたり件数を使用。メモリ量やDBパラメーター上限に合わせて内部で縮小する場合があります。 **画面に表示されません。** | 整数。省略可。既定 1000。最小 1。最大 10000 |
| `RunSpec.start_sequence` | **開始シーケンス**　0から始まる連番。途中から再開したり、分割した負荷試験に使用します。run_key / seedも合わせると同じデータを再現できます。 | 整数。省略可。既定 0。最小 0。最大 1000000000 |
| `RunSpec.max_duration_seconds` | **実行時間の上限 秒**　この時間を超えると停止要求になります。進行中のDBトランザクションや通信の完了後に止まります。完了件数は履歴で確認できます。 **画面に表示されません。** | 整数。省略可。既定 3600。最小 1。最大 86400 |
| `RunSpec.max_output_mb` | **出力量の上限 MiB**　ファイルとストリーム本文の論理上限。SQLのDB容量上限ではありません。サーバー側のメモリ・空き容量保護も常時有効です。 **画面に表示されません。** | 整数。省略可。既定 1024。最小 1。最大 1048576 |
| `RunSpec.initial_delay_seconds` | **開始前の待機 秒**　実行開始後、生成を始めるまでの待機時間。複数のソースの開始時刻をずらせます。実行時間の上限にはこの待機も含まれます。 **画面に表示されません。** | 数値。省略可。既定 0。最小 0。最大 3600 |
| `RunSpec.jitter_ms` | **送信間隔のゆらぎ ms**　速度調整の待機に0〜指定値の再現可能なゆらぎを加えます。目標速度が0の場合は適用しません。 **画面に表示されません。** | 整数。省略可。既定 0。最小 0。最大 60000 |
| `RunSpec.burst_rows` | **バーストのレコード数**　0は通常送信。例: 1000にすると1000件単位でバースト間待機を適用。バッチはこの値以下に調整します。 **画面に表示されません。** | 整数。省略可。既定 0。最小 0。最大 1000000 |
| `RunSpec.burst_pause_ms` | **バースト間の待機 ms**　バーストの境界で加える待機。目標速度の制限と両方が適用されます。 **画面に表示されません。** | 整数。省略可。既定 0。最小 0。最大 3600000 |
| `RunSpec.parameters` | **共有パラメーター JSON**　任意のキーとJSON値。例: {"count":100,"states":["ok","ng"]}。生成条件では$countや$statesで参照。テンプレートは{count}でも参照できます。 | オブジェクト。省略可 |
| `RunSpec.fields` | **データ項目**　上から順に生成します。項目名・型・生成器・詳細条件を自由に変更できます。他の項目を参照する場合は参照元を先に置きます。 | 配列［項目と値の生成方法（FieldRule）］。省略可。最小件数 1。最大件数 100 |
| `RunSpec.sql` | **SQL 書き込み設定**　スキーマ・テーブル・操作を指定。データの列定義は共通のデータ項目から作成します。 **画面に表示されません。** | SQLの書き込み（SqlOptions）。省略可 |
| `RunSpec.files` | **ファイル設定**　形式・分割・命名・JSON構造・CSV仕様・画像条件を設定します。既存ファイルは上書きしません。 **画面に表示されません。** | ファイルの形式と完了通知（FileOptions）。省略可 |
| `RunSpec.stream` | **ストリーム設定**　メタデータの付加・本文形式・トピックを実行ごとに指定します。認証と配送方式は接続プロファイル側で管理します。 **画面に表示されません。** | 本文と配送（StreamOptions）。省略可 |
| `RunSpec.anomalies` | **データ異常の注入ルール**　正常データを生成した後、指定した行位置・割合・条件で異常を注入します。複数ルールは上から順に適用。異常を含むプリセットは意図的にDB制約や受信検証で拒否される場合があります。 | 配列［異常データの条件（AnomalyRule）］。省略可。最大件数 64 |
| `RunSpec.faults` | **処理障害・不正ファイルのシミュレーション**　この実行だけに障害を注入します。外部のサーバーやネットワーク設定は変更しません。SQLのロールバック、ファイル未完了、配送ACK消失、遅延等を再現できます。 **画面に表示されません。** | 実行処理の障害（FaultOptions）。省略可 |
| `RunSpec.task` | **実行タスク**　通常はgenerate。未配送の再送は履歴画面の操作から起動します。 **画面に表示されません。** | 文字列。省略可。既定 "generate"。選択肢 "generate" / "retry" |

### SQLの書き込み（SqlOptions）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `SqlOptions.schema_name` | **スキーマ / 所有者**　空欄はDBユーザーの既定スキーマ。SQL Serverは例: synthetic、Oracleは所有者名、PostgreSQLはpublic。MySQL / SQLiteでは通常空欄。スキーマ自体は自動作成しません。 **このアプリでは適用外。** | 文字列。省略可。既定 ""。書式 "^$\|^[A-Za-z_][A-Za-z0-9_]{0,62}$" |
| `SqlOptions.table` | **テーブル名**　英数字と下線の識別子。既存テーブルを選ぶ場合、生成項目と列名・型を合わせます。未作成ならDDLを確認して作成できます。 **このアプリでは適用外。** | 文字列。省略可。既定 "sample_records"。書式 "^[A-Za-z_][A-Za-z0-9_]{0,62}$" |
| `SqlOptions.operation` | **SQL 操作**　insert=追加のみ、upsert=主キーで追加/更新、update=既存行更新、delete=主キー一致行削除。DDLやDROPは実行しません。同時に同じ主キーへ書く別アプリがある場合は競合し得ます。 **このアプリでは適用外。** | 文字列。省略可。既定 "upsert"。選択肢 "insert" / "upsert" / "update" / "delete" |

### 本文と配送（StreamOptions）

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `StreamOptions.envelope` | **配送メタデータを追加**　JSONオブジェクトにrecord_key / run_key / sequenceを追加。重複排除や追跡に推奨。本文が配列やスカラーの場合は無効にします。 **このアプリでは適用外。** | 真偽値。省略可。既定 true |
| `StreamOptions.metadata_key` | **メタデータの項目名**　既定は_source。生成項目や本文テンプレートのキーと重複させないでください。 **このアプリでは適用外。** | 文字列。省略可。既定 "_source"。書式 "^[A-Za-z_][A-Za-z0-9_]{0,62}$" |
| `StreamOptions.http_body` | **HTTP 本文単位**　array=バッチをJSON配列、single=1件ずつ、ndjson=改行区切りJSON。MQTTは常に1イベント1メッセージです。 **このアプリでは適用外。** | 文字列。省略可。既定 "array"。選択肢 "array" / "single" / "ndjson" |
| `StreamOptions.topic_template` | **配送先名のテンプレート**　空欄は接続プロファイルの配送先名。MQTT / Kafka / NATS / AMQPのトピック・subject・routing keyを項目ごとに変えられます。例: data.{entity_id}。各プロトコルの命名規則に合わせます。 **このアプリでは適用外。** | 文字列。省略可。既定 ""。最長 512 |
| `StreamOptions.payload_template` | **送信本文のJSON構造**　nullなら生成行。例: {"device":"$row.entity_id","values":["$row.value"],"source":"$parameters.site"}。配列やスカラーならメタデータ追加を無効にします。 **このアプリでは適用外。** | JSON値。省略可。既定 null |
| `StreamOptions.delivery_attempts` | **1バッチの送信試行数**　1〜10回。失敗したバッチは永続outboxに残ります。受信済みでも応答が失われた場合は重複し得るためrecord_keyを使います。 **このアプリでは適用外。** | 整数 / null。省略可。既定 null。最小 1。最大 10 |
| `StreamOptions.retry_backoff_ms` | **再試行の基準待機 ms**　同一バッチの再試行間隔。試行ごとに2倍、最大60秒。0は待機なし。 **このアプリでは適用外。** | 整数 / null。省略可。既定 null。最小 0。最大 60000 |

## 公開・出力設定

| JSONキー | 画面名と用途 | 型・入力条件 |
| --- | --- | --- |
| `id` | **接続ID**　保存用ID。同じIDで保存すると新しい版になります。 | 文字列。省略可。既定 "default"。書式 "^[A-Za-z0-9_-]{1,64}$" |
| `name` | **表示名**　公開先・認証・配送先を管理するプロファイルの表示名。 | 文字列。省略可。既定 "既定の公開設定"。最長 120 |
| `auth_mode` | **取得APIの認証方式**　noneは取得用APIの認証なし、basicはユーザーとパスワード、bearerはAuthorization: Bearer、api_keyはX-API-Key。管理画面の認証は別に設定します。 | 文字列。省略可。既定 "none"。選択肢 "none" / "basic" / "bearer" / "api_key" |
| `username` | **ユーザー名**　データ取得API専用のBasic認証ユーザー。管理画面の認証は別に設定します。 | 文字列。省略可。既定 "source"。最長 120 |
| `password` | **パスワード**　取得APIのBasic認証パスワード。空欄は同じ認証方式の保存値を維持。暗号化保存し、読み戻しません。 **秘密値。** | 文字列 / null。省略可。既定 null |
| `token` | **Token**　BearerまたはX-API-Keyで受け付ける値。値は暗号化保存し、JSON書き出しには含めません。 **秘密値。** | 文字列 / null。省略可。既定 null |
| `allow_writes` | **Allow Writes**　取得APIのPOST/PATCH/DELETEを許可。既定は読み取りのみ。操作するのはこのツールの疑似データです。 **画面に表示されません。** | 真偽値。省略可。既定 false |
| `opc_enabled` | **Opc Enabled**　OPC UAのバイナリーサーバーを公開します。HTTP送信とは異なり、収集側から読まれたり購読されたりする方式です。 **画面に表示されません。** | 真偽値。省略可。既定 true |
| `opc_port` | **Opc Port**　コンテナ内のOPC UA待受ポート。ホストへの公開ポートはComposeで設定します。 **画面に表示されません。** | 整数。省略可。既定 4840。最小 1024。最大 65535 |
| `namespace_uri` | **Namespace Uri**　NodeIdを識別する名前空間URI。クライアントはnamespace URIからindexを取得してください。 **画面に表示されません。** | 文字列。省略可。既定 "urn:factory:equipment:simulator"。最長 255 |
| `opc_auth` | **OPC UAの認証**　anonymousは匿名読取、usernameは専用ユーザーで認証。username時はSignAndEncryptが必要です。 **画面に表示されません。** | 文字列。省略可。既定 "anonymous"。選択肢 "anonymous" / "username" |
| `opc_username` | **Opc Username**　OPC UAのユーザー名認証で使用するユーザー。 **画面に表示されません。** | 文字列。省略可。既定 "reader"。最長 120 |
| `opc_password` | **Opc Password**　OPC UAユーザーのパスワード。ユーザー名認証時はSignAndEncryptを必須にします。 **画面に表示されません。** | 文字列 / null。省略可。既定 null |
| `opc_security` | **OPC UAの通信保護**　noneは署名・暗号化なし。sign_encryptはBasic256Sha256で署名と暗号化。証明書と秘密鍵を配置し、クライアントも対応する証明書で接続します。 **画面に表示されません。** | 文字列。省略可。既定 "none"。選択肢 "none" / "sign_encrypt" |
| `certificate_file` | **Certificate File**　connection-files内のサーバー証明書。OPC UAはapplication URI入りのDER/PEM証明書を使用します。 **画面に表示されません。** | 文字列。省略可。既定 "" |
| `private_key_file` | **Private Key File**　connection-files内のサーバー秘密鍵。ファイルは権限600で保存します。 **画面に表示されません。** | 文字列。省略可。既定 "" |
| `trusted_client_certificates` | **Trusted Client Certificates**　SignAndEncryptで信頼するクライアントのleaf証明書。connection-files内のDER/PEMパスを配列で指定。指紋と有効期間を検証します。 **画面に表示されません。** | 配列［文字列］。省略可。最大件数 100 |
| `modbus_enabled` | **Modbus Enabled**　Modbus TCPサーバーを公開。TCPにはユーザー名・パスワード認証はありません。接続元制限はホストで行います。 **画面に表示されません。** | 真偽値。省略可。既定 true |
| `modbus_port` | **Modbus Port**　コンテナ内のModbus TCP待受。非特権ユーザーのため既定は1502です。 **画面に表示されません。** | 整数。省略可。既定 1502。最小 1024。最大 65535 |
| `output` | **送信・保存方式**　captureは永続記録だけ、fileはローカル回転ログ、udp/tcp/tlsはSyslog。UDP/TCPは受信アプリの処理完了を保証しません。MQTTはQoS1のブローカーACK、HTTPは2xx受付まで。 | 文字列。省略可。既定 "capture"。選択肢 "capture" / "file" / "udp" / "tcp" / "tls" |
| `host` | **ホスト**　Syslog/MQTT送信先のホスト。http://やポートは含めません。 | 文字列。省略可。既定 ""。最長 255 |
| `port` | **ポート**　送信先ポート。未指定はSyslog514/TLS6514、MQTT1883/TLS8883を使用。 | 整数 / null。省略可。既定 null。最小 1。最大 65535 |
| `topic` | **配送先トピック / subject / routing key**　RFID・バーコードイベントをMQTTで配信するトピック。 **画面に表示されません。** | 文字列。省略可。既定 "factory/identification"。最長 255 |
| `url` | **送信URL**　HTTP送信先URL。HTTP APIへ1イベントずつJSONをPOSTします。 **画面に表示されません。** | 文字列。省略可。既定 ""。最長 2048 |
| `output_username` | **Output Username**　MQTT送信用のユーザー。取得APIの認証とは別です。 **画面に表示されません。** | 文字列。省略可。既定 ""。最長 255 |
| `mqtt_tls` | **Mqtt Tls**　MQTT接続でTLSを使用。既定ポートは有効時8883、無効時1883。CAと検証設定も適用します。 **画面に表示されません。** | 真偽値。省略可。既定 false |
| `output_password` | **Output Password**　MQTT送信先パスワード。暗号化して保存します。 **画面に表示されません。** | 文字列 / null。省略可。既定 null |
| `output_token` | **Output Token**　HTTP送信時のBearerトークン。空欄なら認証ヘッダーを付けません。 **画面に表示されません。** | 文字列 / null。省略可。既定 null |
| `tls_verify` | **Tls Verify**　送信先のTLS証明書とホスト名を検証。Syslog TLS / HTTPS / MQTT TLSに適用します。 | 真偽値。省略可。既定 true |
| `ca_file` | **Ca File**　送信先CA証明書。connection-files内のPEM。未指定はシステム信頼ストア。 | 文字列。省略可。既定 "" |
| `timeout_seconds` | **接続・通信タイムアウト 秒**　接続・受信ACKの最大待機秒数。 | 整数。省略可。既定 10。最小 1。最大 60 |
| `clear_secrets` | **削除する保存済み認証情報 JSON**　明示的に消す秘密情報名の配列。例: ["token"]。空欄による維持と区別します。 | 配列［文字列］。省略可 |
