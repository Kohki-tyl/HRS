"# HRS" 

## 技術スタック ##
python 3.12+

## 仕様 ##
LINEのAPIを用いてホテル予約・チェックイン・チェックアウトを行うチャットボットシステム

## LINE Messaging API

LINE公式アカウント、Webhook、Channel secret、Channel access tokenの設定方法は
[LINE_SETUP.md](.code/LINE_SETUP.md) を参照してください。

Webhook URLは次の形式です。

```text
https://公開ホスト名/callback
```

稼働状態とLINE設定の有無は `GET /health` で確認できます。

## 管理者（フロントデスク）画面

受付係向けの Web 画面です。ブラウザで `GET /front` を開くとログイン画面が表示されます。

- ログインパスワードは環境変数 `ADMIN_PASSWORD` で設定します（既定は開発用の `hrs-admin`）。
- 機能: 予約一覧（予約番号・予約名・予約日で検索）、チェックイン（本日分）、チェックアウト（宿泊中）。
- 予約データの永続化は SQLite です。DB ファイルのパスは環境変数 `HRS_DB_PATH` で変更できます（既定は `.code/hrs.db`）。

起動例:

```powershell
cd .code
$env:ADMIN_PASSWORD = "your_password"
uvicorn main:app --reload
```
