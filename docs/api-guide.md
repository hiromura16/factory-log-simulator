# ログシミュレーターのAPI

[Swagger UI](http://127.0.0.1:3643/docs)で操作ごとのリクエストと応答を確認できます。[OpenAPI JSON](http://127.0.0.1:3643/openapi.json)はAPIクライアントへの読み込み、[ReDoc](http://127.0.0.1:3643/redoc)はモデル参照に使えます。

## 最初のリクエスト

VM内でアプリに向けて実行します。別のURLで開いている場合は同じHTTPアドレスに読み替えます。

```sh
base='http://127.0.0.1:3643'
curl -fsS "$base/healthz"
curl -fsS "$base/api/info"
curl -fsS "$base/api/preview" \
  -H 'Content-Type: application/json' \
  --data-binary @docs/examples/logs-beginner.json
```

アプリの応答、種類と設定情報、合成データの一部を確認できます。`records` に見本があります。

## 操作を選ぶ

| 目的 | メソッドとパス | 結果や注意点 |
| --- | --- | --- |
| アプリの応答確認 | GET /healthz | 接続先とは別にアプリの応答を調べます。 |
| 設定スキーマを取得 | GET /api/info | 設定の型や既定値の確認に使います。 |
| 生成値の確認 | POST /api/preview | データの一部を作り、外部には書き込みません。 |
| 公開・出力設定を一覧・保存 | GET／POST /api/profiles | 取得認証と配送先に使います。秘密値は一覧に含みません。 |
| ひな型を一覧・保存 | GET /api/presets、POST /api/presets/{identity} | 保存しても実行は始まりません。 |
| 公開・生成を始める | POST /api/start | バックグラウンド実行を開始します。 |
| 状態を調べる・停止する | GET /api/state、POST /api/stop | 停止後も保存済みデータや設定は残ります。 |

## このアプリで取得できる結果

`GET /source/events` は新しいイベントから返し、`GET /source/logs/download` は直近N件の本文を古い順にUTF-8テキストで返します。`status` は完全一致の配送状態です。

## 認証とPOST

管理画面の認証を設定した環境では、管理APIにも同じ認証が必要です。接続先の資格情報は環境側で管理します。

公開データの取得用認証は「公開・出力設定」で選びます。

| 取得設定 | ヘッダー |
| --- | --- |
| none | 不要 |
| basic | Authorization: Basic。curlでは `-u "$SOURCE_USER"` を指定し、パスワードを入力します。 |
| bearer | Authorization: Bearer |
| api_key | X-API-Key |

401では取得用の認証方式とヘッダーを照合します。保存済みデータの取得設定を復元できない503では公開プロファイルを確認します。

POSTには `Content-Type: application/json` を付けます。入力のない停止操作をcurlで呼ぶ場合は `--data '{}'` を付けます。ブラウザーからの変更操作は同一オリジンで実行します。

## 実行前に接続先と操作を確認する

外部の宛先への書き込み・送信、公開の開始、SQLのテーブル作成や行の変更には実行前の確認が必要です。プレビューと計画は生成・送信・書き込みを開始しません。

1. 実行パス（例 `/api/runs`、`/api/table/prepare`、`/api/start`）と送信するJSONを `{"path":"…","payload":{…}}` の形で `POST /api/operations/plan` に渡します。
2. 応答の `summary` にある操作、出力先、版、テーブル・件数を確認します。ログの開始URLに `profile_revision` を使う場合は、計画のJSONにも同じ値を指定します。
3. `confirmation_required` が `true` のときは、同じ設定と `X-Operation-Confirmation` ヘッダーで実行します。トークンは短時間で失効し、1回だけ使用できます。設定または接続先の版が変わると再確認が必要です。

428は確認が必要な応答です。CLIは `plan` コマンドで確認用ファイルを作成できます。

## エラーの見方

| HTTP | 確認すること |
| --- | --- |
| 422 | `detail` の場所と説明を読み、JSONのキー・型・値を直します。 |
| 403 / 413 / 415 | 操作元、リクエストサイズ、Content-Typeを確認します。 |
| 409 | 実行中、接続の変更、データの競合を操作の説明と照合します。 |
| 500 | サーバー側の予期しないエラーです。再実行前に対象と履歴を確認します。 |

[設定リファレンス](settings-reference.md) · [JSONの書き方](template-guide.md)

[CLI・MCPの使い方](mcp.md)

確認プランと実行には同じ管理APIの権限が必要です。トークンは送信内容と接続先の取り違えを防ぎます。管理権限を持つクライアントは計画と実行の両方を呼べるため、承認者を分ける運用では管理資格情報の配布も制限してください。MCPは既定で見本・検証・参照だけを公開します。
