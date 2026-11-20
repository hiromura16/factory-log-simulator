# Dokploy配備ガイド

この文書は手動配備の手順です。この変更ではデプロイしません。Lakehouseや他アプリと独立したDokployプロジェクトで動かします。オンプレ方式・Cloudflare方式とも生成器はオンプレPoCホストに置き、接続先のみ別途検証します。

## 実装に基づく構成
サービス app、Compose ./compose.yaml、build context .、Python 3.12 slimのdigest固定Dockerfile、非root UID1000、単一uvicornワーカー、内部8080。APP_PORTとBIND_IPでホスト側を指定します。既定loopback、traefik.enable=falseを維持します。管理UI・操作API・healthzは認証がありません。直接インターネット公開しないでください。
app-data:/dataはDB・source.key・outboxを保持します。プロジェクト名を固定し別アプリのvolumeを共有しません。root FS read-only、tmpfs /tmp、cap_drop、512MiB/1CPU、PID128、停止猶予60秒、ログ回転は既存設定のままです。生成ガードはメモリ余力既定6GiBとディスク余力2GiB。起動と生成成功は別です。

## プロキシの3つの範囲
1. ベースイメージpullはDocker daemon/BuildKitの通信です。build.argsでは制御できません。ホストproxyと信頼CAは管理者が別途承認・設定します。この作業はdaemon設定を変更しません。
2. ビルド中のpipはCompose build.argsのHTTP_PROXY/HTTPS_PROXY/NO_PROXYと小文字3種を使います。未設定ならDockerクライアント既定を継承し得ます。直接接続を指定するには6変数すべてを明示的に空にします。DockerfileにARG/ENVは追加せず、Docker標準proxy引数を利用します。上下の値を矛盾させないでください。
3. 実行時配送へproxyを一律注入しません。HTTP配送はProxyHandler({})で環境proxyを明示無効化しています。HTTP(S)proxy経由配送は未対応です。Syslog UDP/TCP/TLS・MQTTもHTTPproxy対象外。直接到達可能な承認済み試験先で確認し、接続制限を回避しません。
例示proxyは http://proxy.example.invalid:3128、除外例は localhost,127.0.0.1,::1。これは説明用で実接続しません。ビルダーのlocalhostは管理PCではありません。資格情報入りURLや実ホスト名はGit・画面写真・ログに残さず、非公開環境設定で管理します。
docker compose configは展開値を出すため共有ログでは--quietを使用。Gitは.env.example以外の.env類、Docker contextは.env*を除外済み。TLS検証無効化やtrusted-hostで回避しません。

## Dokployでの配備
1. 許可されたPoCサーバーのDocker/Compose、空き容量、GitHub読取接続を確認。独立プロジェクトを作りComposeサービスを作成します。UI名は版によって異なります。
2. 当リポジトリのレビュー済みrevisionと./compose.yamlを指定。Dockerfile方式の別ビルドと二重設定しません。
3. 非公開環境設定へAPP_PORT（空いているホストポート）、BIND_IP=127.0.0.1、AUTO_START=0を入力。必要ならAPP_MEMORY/APP_CPUS/MIN_AVAILABLE_GIBを設定。ログ版の追加設定は下記参照。
4. ビルドproxyが必要な場合だけ6変数を入力し、Compose補間に渡ることを確認。runtime環境欄への一律注入はしません。
5. 対象ブランチの自動デプロイを明示的に無効化し（既定で有効の場合があります）、ドメイン公開を有効化せず、volume・port・contextをプレビュー。所有者承認後に手動build/deployします。
6. ホスト上でcurl -fsS http://127.0.0.1:<APP_PORT>/healthzを実行。UIは認証済みSSHトンネルなど許可された経路で確認。DockerfileのHEALTHCHECKも同じ/healthzを使います。
7. captureプロファイル、小規模合成プリセット、生成停止状態を確認。AUTO_START=0は初回自動開始を抑えるだけで、保存済み実行状態の強制停止ではありません。更新前はUIで停止します。
8. 承認された配送先へ少量だけ生成し受信側を確認します。HTTP応答/MQTT PUBACK/Syslog送信完了は下流保存保証ではありません。実個人情報や業務資格情報は使いません。

## ローカルスモーク（fresh clone専用）
以下の起動は許可済みの独立試験環境で利用者が実施します。既存配備には実行しません。
```sh
uv sync --frozen
uv run pytest -q
uv run python scripts/init_local.py --env-file .env
# .envをローカル編集: AUTO_START=0、空きAPP_PORT、loopback維持
# ログ版はLOG_DIRとUID1000書込可否を確認
docker compose --env-file .env -p synthetic-smoke config --quiet
docker compose --env-file .env -p synthetic-smoke build
docker compose --env-file .env -p synthetic-smoke up -d
# 別端末で指定ポートの /healthz とUIを確認
docker compose --env-file .env -p synthetic-smoke ps
docker compose --env-file .env -p synthetic-smoke stop
```
health、UI表示、停止状態、captureイベントを確認。単体試験だけでは実配送、Dokploy操作、proxy実接続を保証しません。volumeは自動削除せずdown -v/pruneを使いません。

## 更新・復旧
生成停止後、DBとsource.keyを同時点で秘密情報としてバックアップ。レビュー済みrevisionへ更新しhealth/captureを再確認。問題時は旧revisionと同じvolumeへ戻します。スキーマ互換性不明なら停止して復旧計画を確認。鍵だけ・DBだけの復旧は避けます。

## アプリ固有設定
リポジトリ hiromura16/factory-log-simulator、.env.exampleのAPP_PORT=3643。
LOG_DIRはDocker実行ホスト上の専用絶対パスを指定し、事前作成とUID1000書込権限を管理者が確認。init_local.pyが作るdata/logsは作成者所有なのでコンテナから書けるとは限りません。/logsにマウントしevents.logと回転ログを保存します。管理PCのパスは使いません。

## 固定イメージの事前取得（任意）
実際のDockerfileのFROMと同じ固定参照です。配備に使用する同じDockerホスト・ビルダーで必要に応じて取得します。キャッシュ済みでもregistryのメタデータ照会・認証・通信を省略できる保証はありません。

```sh
docker pull python:3.12-slim@sha256:05a994d2344eb364cc186910f4fc8786a38215f39f00d0acc25bff33a08f4177
```

非公開の設定へ入力する合成例（上下ペアは同値）：
```dotenv
HTTP_PROXY=http://proxy.example.invalid:3128
http_proxy=http://proxy.example.invalid:3128
HTTPS_PROXY=http://proxy.example.invalid:3128
https_proxy=http://proxy.example.invalid:3128
NO_PROXY=localhost,127.0.0.1,::1
no_proxy=localhost,127.0.0.1,::1
```
