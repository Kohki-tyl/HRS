HRS/ code/
│
├── main.py                         # 本番用エントリーポイント（FastAPI起動、LINE Webhook受付、フロント端末API、各層の結合/DI）
├── debug_cli.py                    # デバッグ用エントリーポイント（ターミナル上でCUI操作、インメモリDBを使用）
│
├── ui/                             # プレゼンテーション層（2チャネルのユーザーインタフェース）
│   ├── __init__.py
│   ├── session_manager.py          # LINEボット特有の「会話の進行状態（セッション）」を管理（予約フローのみ）
│   ├── chat_interface.py           # 【利用者/LINE】UC1 予約の対話・ルーティング・返信テキストの生成
│   └── front_desk_terminal.py      # 【受付係/フロント端末】UC2 チェックイン・UC3 チェックアウト（照会と確定を分離、セッション不要）
│
├── application/                    # アプリケーション層（ユースケースの進行制御）
│   ├── __init__.py
│   ├── reservation_control.py      # 予約手続きの制御（予約番号の採番、過去日付や0室以下のバリデーションを含む）
│   ├── checkin_control.py          # チェックイン手続きの制御
│   ├── checkout_control.py         # チェックアウト（一括精算・空室化）手続きの制御
│   └── cancel_control.py           # 予約キャンセルの制御（保守拡張の受け皿）
│
├── domain/                         # ドメイン層（システムの中核となる業務ルールとデータ）
│   ├── __init__.py                 # 各パッケージの外部公開窓口
│   ├── models.py                   # Hotel, RoomType, Room, Reservation, Payment, Guest, 列挙型(Status), 例外(BureaucraticError)
│   └── repository_interface.py     # 永続化の「契約」を定義する抽象クラス（ReservationRepository）
│
└── infrastructure/                 # インフラストラクチャ層（技術的詳細・データアクセス）
    ├── __init__.py
    └── mysql_reservation_repository.py # MySQLを使用してデータを保存・復元する具象クラス
