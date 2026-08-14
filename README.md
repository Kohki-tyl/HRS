# HRS（ホテル予約システム）

LINE Messaging API と Web フロントデスク画面を用いて、ホテルの**予約・チェックイン・チェックアウト・予約キャンセル**を行うシステムである。

- 利用者は **LINE** で「予約」「予約キャンセル」を行う。
- 受付係は **Web フロントデスク画面**で「チェックイン」「チェックアウト」「予約一覧」を行う。

## 技術スタック

- Python 3.12 以上（3.13 で動作確認）
- FastAPI / Uvicorn（Web サーバ・LINE Webhook）
- line-bot-sdk v3（LINE Messaging API 連携）
- SQLite（予約データの永続化。Python 標準ライブラリ）
- pytest（自動テスト）

依存関係は [requirements.txt](docs/setup/text/requirements.txt) にまとめている。

## ディレクトリ構成

実装は [.code/](.code/) 以下にある。各モジュールの役割は [code_structure.md](docs/development/markdown/code_structure.md) を参照。

---

## 実行環境・再現手順

外部の閲覧者（教員等）が手元で再現できるよう、セットアップから各実行方法までを示す。以下は Windows の PowerShell を例にしているが、macOS / Linux でも読み替えて実行できる。

### 1. 前提

- Python 3.12 以上がインストールされていること（`python --version` で確認）。
- LINE 連携を試す場合のみ LINE 公式アカウントと Channel の設定が必要（[LINE_SETUP.md](docs/setup/markdown/LINE_SETUP.md) 参照）。**テストと管理者画面・ターミナルデバッグは LINE 設定なしで動作する。**

### 2. セットアップ（仮想環境と依存関係）

```powershell
cd .code
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
python -m pip install -r ../docs/setup/text/requirements.txt
```

### 3. 自動テストの実行（LINE 設定不要）

```powershell
cd .code
python -m pytest scripts/tests -q
```

ドメイン層（状態遷移・空室判定）、UI 層（LINE 予約/キャンセル対話・フロント端末）、Web エンドポイントを通しで検証する。

### 4. 管理者フロントデスク画面を試す（LINE 設定不要）

LINE を使わずに、受付係向けの Web 画面と API を起動できる。

```powershell
cd .code
python -m scripts.debug.debug_web
```

- ブラウザで `http://127.0.0.1:8000/front` を開く。
- ログインパスワードは環境変数 `ADMIN_PASSWORD`（既定 `hrs-admin`）。
- 初回起動時、デモ用の予約（本日分・翌日分）が自動投入される。
- 予約一覧・チェックイン・チェックアウトを操作できる。

### 5. LINE の予約／キャンセル対話をターミナルで試す（LINE 設定不要）

LINE の代わりに、ターミナルの入力を利用者メッセージに見立てて対話を確認できる。

```powershell
cd .code
python -m scripts.debug.debug_chat     # 利用者（予約・予約キャンセル）
python -m scripts.debug.debug_front    # 受付係（チェックイン・チェックアウト）
```

`scripts/debug/debug_chat.py` と `scripts/debug/debug_front.py` は同じ SQLite ファイルを共有するため、別々のターミナルで同時に起動すると予約→チェックインの連携を確認できる。

### 6. 本番相当（LINE Webhook 込み）で起動する

LINE と実際に連携する場合は、依存関係のインストールに加えて Channel の秘密情報を与える。ルートの `.env.example`（Git 管理対象）を `.env`（Git 管理対象外）へコピーして編集し、`--env-file` で読み込ませる方法を推奨する。

```powershell
Copy-Item .env.example .env
# .env を編集して Channel access token / Channel secret を設定
cd .code
python -m uvicorn scripts.startup.main:app --env-file ../.env --reload --host 0.0.0.0 --port 8000
```

環境変数を直接与えてもよい。

```powershell
cd .code
$env:LINE_CHANNEL_ACCESS_TOKEN = "＜Channel access token＞"
$env:LINE_CHANNEL_SECRET = "＜Channel secret＞"
$env:ADMIN_PASSWORD = "＜管理者パスワード＞"
uvicorn scripts.startup.main:app --reload
```

- LINE の Webhook URL は `https://＜公開ホスト名＞/callback` の形式（ngrok 等で公開する）。
- 稼働状態と LINE 設定の有無は `GET /health` で確認できる。
- 管理者画面は `GET /front`。

### 7. 環境変数一覧

| 変数 | 用途 | 既定値 |
| --- | --- | --- |
| `ADMIN_PASSWORD` | 管理者フロントデスク画面のログインパスワード | `hrs-admin`（開発用） |
| `HRS_DB_PATH` | SQLite データファイルのパス | `.code/hrs.db` |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API のアクセストークン（LINE 連携時のみ） | （未設定） |
| `LINE_CHANNEL_SECRET` | LINE Webhook の署名検証用シークレット（LINE 連携時のみ） | （未設定） |

ルートの `.env.example` をコピーして `.env` を作り、上記のように `--env-file ../.env` で読み込ませるか、PowerShell の環境変数として直接与える。`.env` はアプリ側で自動読み込みされないため、`--env-file` を付けない起動方法では環境変数として設定するか、デプロイ先の秘密情報管理へ登録すること。`.env` は Git 管理対象外であり、秘密情報を Issue や Pull Request に貼らないこと。

---

## LINE Messaging API

LINE 公式アカウント、Webhook、Channel secret、Channel access token の設定方法は [LINE_SETUP.md](docs/setup/markdown/LINE_SETUP.md) を参照。

## ドキュメント

| ドキュメント | 内容 |
| --- | --- |
| [Requirements_Analysis.md](docs/design/markdown/Requirements_Analysis.md) | 要求分析（ユースケース・アクティビティ図） |
| [Domain_Analysis.md](docs/design/markdown/Domain_Analysis.md) | 概念モデル（ドメイン分析） |
| [System_Analysis.md](docs/design/markdown/System_Analysis.md) | システム分析（ロバストネス分析・コミュニケーション図） |
| [Architecture.md](docs/design/markdown/Architecture.md) | アーキテクチャ設計（多層・パッケージ・クラス図・状態遷移） |
| [Design.md](docs/design/markdown/Design.md) | 詳細設計（型付きクラス図・状態遷移・シーケンス図） |
| [Cancel_Feature.md](docs/design/markdown/Cancel_Feature.md) | 予約キャンセル機能（UC4）の仕様・設計・実装（集約） |
| [Cancel_Feature_Proposal.md](docs/design/markdown/Cancel_Feature_Proposal.md) | 予約キャンセル機能の提案（検討の経緯） |
| [E2E_Test_Checklist.md](docs/testing/markdown/E2E_Test_Checklist.md) | 実機テスト（LINE〜管理者画面）のチェックリスト |
| [E2E_Test_Report_2026-07-26.md](docs/testing/markdown/E2E_Test_Report_2026-07-26.md) | 実機テストの実施結果 |
| [code_structure.md](docs/development/markdown/code_structure.md) | 実装のディレクトリ構成 |
| [TODO.md](docs/project/markdown/TODO.md) | 今後の対応項目 |
| [debuglist.md](docs/project/markdown/debuglist.md) | 修正項目の記録 |

将来対応する項目は [TODO.md](docs/project/markdown/TODO.md) にまとめている。
