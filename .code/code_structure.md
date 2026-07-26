HRS/ code/
│
├── main.py                         # 本番用エントリーポイント（FastAPI起動、LINE Webhook受付、各層の結合/DI。永続化はSQLite）
├── web_frontdesk.py                # 管理者フロントデスク（Web UI・API）を生成するファクトリ（LINE非依存）。main.py と debug_web.py が共用
│
├── debug_web.py                    # デバッグ用: LINEなしで管理者フロントデスク画面を起動（python debug_web.py → /front）
├── debug_chat.py                   # デバッグ用: 利用者チャット（予約・予約キャンセル）をターミナルで実行
├── debug_front.py                  # デバッグ用: 受付係のフロント端末（チェックイン・チェックアウト）をターミナルで実行
├── debug_setup.py                  # debug_chat / debug_front が共有する SQLite・ホテル定義のセットアップ
├── debug_cli.py                    # デバッグ用: 全ユースケースをCUIで確認（インメモリDBを使用）
│
├── requirements.txt                # 依存関係（fastapi, uvicorn, line-bot-sdk, pytest, httpx2）
├── conftest.py                     # pytest 共通設定（.code をパスに追加）
│
├── ui/                             # プレゼンテーション層（2チャネルのユーザーインタフェース）
│   ├── __init__.py
│   ├── session_manager.py          # LINE対話の進行状態（予約・キャンセルフロー）を管理
│   ├── chat_interface.py           # 【利用者/LINE】UC1 予約・UC4 予約キャンセルの対話（キャンセル詳細は Cancel_Feature.md）
│   ├── front_desk_terminal.py      # 【受付係/フロント端末】UC2 チェックイン・UC3 チェックアウト（照会と確定を分離）
│   ├── templates/front_desk.html   # 管理者フロントデスク画面（ログイン・サイドバー・一覧・詳細）
│   └── static/                     # 画面の CSS / JS（app.js, style.css）
│
├── application/                    # アプリケーション層（ユースケースの進行制御）
│   ├── __init__.py
│   ├── reservation_control.py      # 予約手続きの制御（予約番号の採番、空室のDB引き、予約者 line_user_id の保存）
│   ├── checkin_control.py          # チェックイン手続きの制御
│   ├── checkout_control.py         # チェックアウト（一括精算・空室化）手続きの制御
│   └── cancel_control.py           # 予約キャンセルの制御（UC4。詳細は Cancel_Feature.md）
│
├── domain/                         # ドメイン層（システムの中核となる業務ルールとデータ）
│   ├── __init__.py                 # 各パッケージの外部公開窓口
│   ├── models.py                   # Hotel, RoomType, Room, Reservation, Payment, Guest, 列挙型(Status), 例外(BureaucraticError)
│   └── repository_interface.py     # 永続化の「契約」を定義する抽象クラス（ReservationRepository）
│
├── infrastructure/                 # インフラストラクチャ層（技術的詳細・データアクセス）
│   ├── __init__.py
│   └── sqlite_reservation_repository.py # SQLiteでデータを保存・復元する具象クラス（永続化はこれに統一。列追加のマイグレーションを含む）
│
└── tests/                          # 自動テスト（pytest）
    ├── test_domain_models.py       # ドメイン: 状態遷移ガード（チェックイン/アウト/キャンセル）・空室判定
    ├── test_sqlite_repository.py   # インフラ: 保存・検索・復元、既存DBのマイグレーション
    ├── test_db_availability.py     # DB引きの空室判定・再起動・キャンセルでの在庫解放
    ├── test_cancel_control.py      # キャンセル: 本人確認・状態/期限ガード・情報秘匿
    ├── test_chat_interface.py      # LINE 予約/キャンセル対話の状態機械
    ├── test_front_desk_terminal.py # 受付係の照会→確定
    └── test_web_frontdesk.py       # 管理者Webエンドポイントの通し（認証・一覧・候補・確定）
