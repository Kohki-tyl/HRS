HRS/ code/
│
├── main.py                         # 本番用エントリーポイント（FastAPI起動、LINE Webhook受付、各層の結合/DI）
├── debug_cli.py                    # デバッグ用エントリーポイント（ターミナル上でCUI操作、インメモリDBを使用）
│
├── ui/                             # プレゼンテーション層（ユーザーとの対話管理）
│   ├── __init__.py
│   ├── session_manager.py          # 【新規】LINEボット特有の「会話の進行状態（セッション）」を管理
│   └── chat_interface.py           # メッセージの解釈、ルーティング、返信テキストの生成（旧 line_interface.py）
│
├── application/                    # アプリケーション層（ユースケースの進行制御）
│   ├── __init__.py
│   ├── reservation_control.py      # 予約手続きの制御（過去日付や0室以下のバリデーションを含む）
│   ├── checkin_control.py          # チェックイン手続きの制御
│   └── checkout_control.py         # チェックアウト（一括精算・空室化）手続きの制御
│   # (cancel_control.py)           # ※演習6（保守）を取り入れる際に追加予定
│
├── domain/                         # ドメイン層（システムの中核となる業務ルールとデータ）
│   ├── __init__.py                 # 各パッケージの外部公開窓口
│   ├── models.py                   # Hotel, Room, Reservation, 列挙型(Status), 例外(BureaucraticError)など
│   └── repository_interface.py     # 永続化の「契約」を定義する抽象クラス（ReservationRepository）
│
└── infrastructure/                 # インフラストラクチャ層（技術的詳細・データアクセス）
    ├── __init__.py
    └── mysql_reservation_repository.py # MySQLを使用してデータを保存・復元する具象クラス