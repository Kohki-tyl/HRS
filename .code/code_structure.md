hrs-project/
│
├── main.py                 # アプリケーションの起動エントリーポイント（FastAPIやFlaskなど）
│
├── ui/                     # UI層（Boundary）
│   ├── __init__.py
│   └── line_interface.py   # LINE Messaging APIのWebhook受付、Flex Message等の送信
│
├── application/            # アプリケーション層（Control）
│   ├── __init__.py
│   ├── reservation_control.py
│   ├── checkin_control.py
│   └── checkout_control.py
│
├── domain/                 # ドメイン層（Entity & Repository Interface）
│   ├── __init__.py
│   ├── models.py           # Hotel, Room, Reservation, Payment などのクラス定義
│   └── repository_interface.py # クラステンプレート・抽象クラス（abcモジュールを使用）
│
└── infrastructure/         # インフラストラクチャ層（Data Access）
    ├── __init__.py
    ├── database.py         # MySQLとの接続管理（SQLAlchemyやmysql-connector）
    └── reservation_repository.py # repository_interfaceの具象実装