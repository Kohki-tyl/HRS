HRS/.code/
│
├── scripts/
│   ├── startup/
│   │   ├── main.py                 # FastAPI・LINE Webhook・DI
│   │   └── server.py               # コンテナ／PaaS向け本番起動入口
│   ├── debug/
│   │   ├── debug_web.py            # LINEなしで管理者画面を起動
│   │   ├── debug_chat.py           # 利用者チャットをターミナルで実行
│   │   ├── debug_front.py          # フロント端末をターミナルで実行
│   │   └── debug_setup.py          # チャット／フロント共通のSQLite・ホテル定義
│   ├── shared/
│   │   └── web_frontdesk.py        # 管理者Web UI・APIを生成する共有ファクトリ
│   └── tests/                       # 自動テスト（pytest）
│       ├── conftest.py              # pytest共通設定（.codeをimportパスに追加）
│       ├── test_domain_models.py    # ドメインの状態遷移・空室判定
│       ├── test_sqlite_repository.py
│       ├── test_db_availability.py
│       ├── test_cancel_control.py
│       ├── test_chat_interface.py
│       ├── test_front_desk_terminal.py
│       ├── test_startup_server.py
│       └── test_web_frontdesk.py
│
├── ui/                             # プレゼンテーション層（2チャネルのユーザーインタフェース）
│   ├── __init__.py
│   ├── session_manager.py          # LINE対話の進行状態（予約・キャンセルフロー）を管理
│   ├── chat_interface.py           # 【利用者/LINE】UC1 予約・UC4 予約キャンセルの対話（詳細は docs/design/markdown/Cancel_Feature.md）
│   ├── front_desk_terminal.py      # 【受付係/フロント端末】UC2 チェックイン・UC3 チェックアウト（照会と確定を分離）
│   ├── templates/front_desk.html   # 管理者フロントデスク画面（ログイン・サイドバー・一覧・詳細）
│   └── static/                     # 画面の CSS / JS（app.js, style.css）
│
├── application/                    # アプリケーション層（ユースケースの進行制御）
│   ├── __init__.py
│   ├── reservation_control.py      # 予約手続きの制御（予約番号の採番、空室のDB引き、予約者 line_user_id の保存）
│   ├── checkin_control.py          # チェックイン手続きの制御
│   ├── checkout_control.py         # チェックアウト（一括精算・空室化）手続きの制御
│   └── cancel_control.py           # 予約キャンセルの制御（UC4。詳細は docs/design/markdown/Cancel_Feature.md）
│
├── domain/                         # ドメイン層（システムの中核となる業務ルールとデータ）
│   ├── __init__.py                 # 各パッケージの外部公開窓口
│   ├── models.py                   # Hotel, RoomType, Room, Reservation, Payment, Guest, 列挙型(Status), 例外(BureaucraticError)
│   └── repository_interface.py     # 永続化の「契約」を定義する抽象クラス（ReservationRepository）
│
└── infrastructure/                 # インフラストラクチャ層（技術的詳細・データアクセス）
│   ├── __init__.py
│   └── sqlite_reservation_repository.py # SQLiteでデータを保存・復元する具象クラス（永続化はこれに統一。列追加のマイグレーションを含む）
