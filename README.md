"# HRS" 

## 技術スタック ##
python 3.12+

## 仕様 ##
LINEのAPIを用いてホテル予約・チェックイン・チェックアウトを行うチャットボットシステム

## LINE Messaging API

LINE公式アカウント、Webhook、Channel secret、Channel access tokenの設定方法は
[LINE_SETUP.md](.code/LINE_SETUP.md) を参照してください。

ローカル実機テストでは、Git管理対象の `.env.example` を、Git管理対象外の `.env` にコピーして秘密情報を設定します。

```powershell
Copy-Item .env.example .env
# .envを編集後
cd .code
python -m uvicorn main:app --env-file ../.env --reload --host 0.0.0.0 --port 8000
```

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

## 自動テスト

依存関係をインストール後、次のコマンドでテストを実行できます。

```powershell
cd .code
python -m pytest tests -q
```

将来対応する項目は [TODO.md](TODO.md) にまとめています。
