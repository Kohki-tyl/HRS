# LINE Messaging API 設定手順

HRS の LINE 側は、利用者によるホテル予約を担当する。Webhook の受信先は
`POST /callback`、設定確認用URLは `GET /health` である。

## 1. LINE公式アカウントとMessaging APIチャネルを用意する

1. [LINE Official Account Manager](https://manager.line.biz/) でLINE公式アカウントを作成する。
2. Official Account ManagerでMessaging APIを有効化し、管理するProviderを選択する。
3. [LINE Developers Console](https://developers.line.biz/console/) を開き、作成されたMessaging APIチャネルを選択する。

Messaging APIチャネルはLINE Developers Consoleから直接新規作成できないため、
Official Account Managerから有効化する。

## 2. 秘密情報を取得する

LINE Developers Consoleで次の値を取得する。

- Basic settings: `Channel secret`
- Messaging API: `Channel access token`

値はGitにコミットしない。漏えいした場合は、ConsoleからSecretの再発行またはTokenの失効・再発行を行う。

PowerShellでは、サーバーを起動する同じターミナルで次のように設定する。

```powershell
$env:LINE_CHANNEL_ACCESS_TOKEN = "取得したChannel access token"
$env:LINE_CHANNEL_SECRET = "取得したChannel secret"
```

## 3. ローカルサーバーを起動する

`.code` ディレクトリで実行する。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで `http://localhost:8000/health` を開き、次を確認する。

```json
{"status":"ok","line_configured":true,"line_webhook_path":"/callback"}
```

## 4. HTTPSで外部公開する

LINE Platformからlocalhostへ直接接続することはできない。開発用トンネルまたはHTTPS対応の
ホスティングを使用し、次の公開URLを用意する。

```text
https://公開ホスト名/callback
```

Webhook URLは有効なHTTPS URLである必要がある。本番では固定URLを使用する。

## 5. LINE Developers Consoleを設定する

Messaging APIタブで次を設定する。

1. Webhook URLに `https://公開ホスト名/callback` を入力する。
2. `Verify` を押し、Successになることを確認する。
3. `Use webhook` を有効にする。
4. 必要に応じて `Webhook redelivery` を有効にする。

公式アカウント側の応答設定では、Webhookと二重返信にならないよう、既定のあいさつ・応答メッセージの利用方針を確認する。

## 6. 疎通確認する

1. Messaging APIタブのQRコードから公式アカウントを友だち追加する。
2. LINEで `予約` と送信する。
3. Botから宿泊日の入力案内が返ることを確認する。
4. `YYYY-MM-DD`、部屋指定、氏名、`はい` の順で入力し、予約番号が返ることを確認する。

Webhookは受信したリクエスト本文を変更せず、`X-Line-Signature` とChannel secretで署名検証する。
HRSではLINE公式SDKの `WebhookHandler` が検証を行う。

## トラブルシューティング

- `/health` の `line_configured` が `false`: 2つの環境変数を設定後、サーバーを再起動する。
- Verifyが失敗する: 公開URL、HTTPS、トンネル稼働状況、`/callback` の付け忘れを確認する。
- `400 Invalid signature`: 異なるチャネルのChannel secretを設定していないか確認する。
- 返信だけ失敗する: Channel access tokenの有効性と、Messaging APIチャネルのTokenであることを確認する。
- Botと自動応答が二重に返る: Official Account Managerの応答設定を確認する。
