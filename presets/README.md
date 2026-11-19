# プリセット一覧

通常12種類・異常12種類。各JSONはフォームで編集・保存できます。認証情報は含みません。

## 01-normal / 正常 / ローカル回転ログ / RFC5424

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。ローカル回転ログ / RFC5424を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 02-normal / 正常 / JSON Lines

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。JSON Linesを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式jsonl、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 03-normal / 正常 / プレーンログ

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。プレーンログを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式plain、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 04-normal / 正常 / RFC3164

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。RFC3164を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc3164、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 05-normal / 正常 / errorレベル

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。errorレベルを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=3。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 06-normal / 正常 / warningレベル

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。warningレベルを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=4。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 07-normal / 正常 / facility local1

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。facility local1を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=17、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 08-normal / 正常 / 毎秒100件

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。毎秒100件を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに100件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 09-normal / 正常 / 低頻度ログ

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。低頻度ログを想定。

【生成内容・条件】
更新周期5000ms、最大tick数無制限。
1tickに1件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 10-normal / 正常 / 小容量ローテーション

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。小容量ローテーションを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限1MiB、バックアップ3本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 11-normal / 正常 / 独自メッセージ

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。独自メッセージを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: source={entity_id} sequence={sequence_no} measurement={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 12-normal / 正常 / 日本語ログ

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。日本語ログを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: 設備={entity_id} 状態={status} 測定値={value}
検証ログ。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 13-anomaly / 異常 / エラー集中

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。エラー集中を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに100件、書式rfc5424、facility=16、severity=3。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 14-anomaly / 異常 / 重複ログ

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。重複ログを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。
3件ごとに同じevent_idと本文を重複出力。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 15-anomaly / 異常 / 壊れたヘッダー

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。壊れたヘッダーを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。
3件ごとにヘッダーを意図的に破損。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 16-anomaly / 異常 / 文字列へ異常値

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。文字列へ異常値を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。
項目valueへset、値='ERROR'を生成位置0〜以降で適用。異常後の型検証を迂回=True。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 17-anomaly / 異常 / 遅い出力

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。遅い出力を想定。

【生成内容・条件】
更新周期5000ms、最大tick数無制限。
1tickに1件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 18-anomaly / 異常 / warningの集中

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。warningの集中を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに100件、書式rfc5424、facility=16、severity=4。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 19-anomaly / 異常 / 固着した値

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。固着した値を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。
項目valueへfreeze、値=Noneを生成位置0〜以降で適用。異常後の型検証を迂回=False。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 20-anomaly / 異常 / 日本語と改行

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。日本語と改行を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: 設備={entity_id} 状態={status} 測定値={value}
検証ログ。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 21-anomaly / 異常 / 大きなメッセージ

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。大きなメッセージを想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: large-message large-message large-message large-message large-message large-message large-message large-message large-me。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 22-anomaly / 異常 / 欠測値

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。欠測値を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。
項目valueへnull、値=Noneを生成位置0〜以降で適用。異常後の型検証を迂回=False。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 23-anomaly / 異常 / 未知の状態

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。未知の状態を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。
項目statusへset、値='UNKNOWN'を生成位置0〜以降で適用。異常後の型検証を迂回=False。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。

## 24-anomaly / 異常 / 送信エラーを保持

【想定】
ログ収集・パース・ローテーション・配送失敗の扱いの検証。送信エラーを保持を想定。

【生成内容・条件】
更新周期1000ms、最大tick数無制限。
1tickに5件、書式rfc5424、facility=16、severity=6。回転上限10MiB、バックアップ5本。
本文テンプレート: entity={entity_id} status={status} value={value}。

【確認事項】
PRI・時刻・UTF-8・複数行のパースと、ローテーション後の継続収集を確認。
TCPはoctet counting/newlineを受信側と合わせる。UDP/TCPの送信完了は受信アプリの処理完了を保証しない。失敗時はpendingを保持。

【実行前】
公開・認証・送信先は別のプロファイルで指定し、保存後に停止・開始して適用。各条件はフォームとJSONで編集可能。 配送エラーの再現には接続できない送信先を別途指定。既定のファイル出力では配送エラーにならない。
