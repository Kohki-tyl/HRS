# 設計

## 方針
- ### 多層アーキテクチャと依存関係逆転の原則: 
    システムを「プレゼンテーション(UI)」「アプリケーション」「ドメイン」「インフラストラクチャ」の4層に分離する。インフラ層はドメイン層のインターフェースに依存するようにし（DIP）、ビジネスロジックがデータベースなどの技術的詳細に依存することを防ぐ。
- ### リッチドメインモデル: 
    ビジネスルール（空室判定、状態遷移）はコントロール層ではなく、ドメイン層（エンティティ）にカプセル化する。コントロール層は、適切なドメインオブジェクトに処理を委譲（メッセージパッシング）する「進行役」に徹する。
- ### 日付ベースの在庫管理: 
    連泊を想定しない1泊の予約であっても、Room 自身が「いつ予約されているか（reserved_dates）」を管理することで、同一部屋の別日の予約を許容する柔軟な在庫管理を実現する。

## パッケージ図
```mermaid
flowchart TD
    LINE([LINE Messaging API]):::ext

    subgraph P[プレゼンテーション層 / UI]
        CI["ChatInterface «boundary»"]
        SM["SessionManager (対話状態管理)"]
    end
    subgraph A[アプリケーション層 / Application]
        RC["ReservationControl «control»"]
        KC["CheckInControl «control»"]
        OC["CheckOutControl «control»"]
        CC["CancelControl «control»"]
    end
    subgraph D[ドメイン層 / Domain]
        HT["Hotel «entity»"]
        RT["RoomType «entity»"]
        RM["Room «entity»"]
        RV["Reservation «entity»"]
        ST["ReservationStatus «enum»"]
        REPO_IF["ReservationRepository «interface»"]
    end
    subgraph I[インフラストラクチャ層 / Infrastructure]
        REPO_IMPL["MySQLReservationRepository «infra»"]
        DB[(MySQL Database)]:::ext
    end

    LINE -. Webhook .- CI
    CI --> SM
    CI --> RC
    CI --> KC
    CI --> OC
    CI --> CC
    
    RC --> HT
    RC --> REPO_IF
    KC --> REPO_IF
    OC --> REPO_IF
    CC --> REPO_IF
    
    %% クラス図特有の記号を通常の矢印に変更
    HT --> RT
    RT --> RM
    RV --> RM
    RV --> ST
    
    %% extends/implementsの表現を点線矢印に変更
    REPO_IMPL -. implements .-> REPO_IF
    REPO_IMPL --> DB

    classDef ext fill:#eee,stroke:#999;
```
| パッケージ  | 役割 |
| --- | --- |
| UI層 | LINE Webhookの受付、テキストの解釈、複数ターンに及ぶ対話セッション（状態）の保持、応答の送信を行う。|
| アプリケーション層 | ユースケース（予約・チェックイン等）の手順を表現する。DBから予約を復元し、ドメインに処理を命じ、結果をDBに保存する。|
| ドメイン層 | 「部屋の空き状況の確認」「予約のキャンセルに伴う在庫解放」などのコアな業務ルールを持つ。この層は他のどの層もインポートしない。|
| インフラ層 | ドメイン層で定義された ReservationRepository の契約（インターフェース）に従い、MySQLなどのRDBに対してデータの保存・復元（SQL発行）を行う。|

## クラス図
実装（Python）の型定義と、日付ごとの在庫管理ロジックを反映した完全版クラス図。
```mermaid
classDiagram
    %% Application Layer
    class ReservationControl {
        <<control>>
        +search_room(staying_date, num) List~RoomType~
        +reserve_room(date, num, type) Reservation
    }
    class CheckInControl {
        <<control>>
        +check_in(reservation_number) List~int~
    }

    %% Domain Layer (Core Logic)
    class ReservationRepository {
        <<interface>>
        +save(Reservation) void
        +find_by_id(reservation_number) Reservation
        +find_by_room_number(room_number) Reservation
    }
    class Hotel {
        <<entity>>
        +get_available_room_types(date, num) List~RoomType~
        +allocate_rooms(date, type, num) List~Room~
    }
    class RoomType {
        <<entity>>
        -type_name: str
        -price: int
        +check_stock(num, date) bool
        +reduce_stock(num, date) List~Room~
    }
    class Room {
        <<entity>>
        -room_number: int
        -reserved_dates: Set~date~
        -status: RoomStatus
        +is_vacant_on(date) bool
        +assign(date) void
        +cancel_assign(date) void
        +mark_using() void
        +mark_empty() void
    }
    class Reservation {
        <<entity>>
        -reservation_number: int
        -staying_date: date
        -status: ReservationStatus
        +mark_checked_in() void
        +check_out() void
        +cancel() void
    }

    %% Infrastructure Layer
    class MySQLReservationRepository {
        <<infra>>
        +save(Reservation) void
        +find_by_id(reservation_number) Reservation
    }

    %% Relationships
    ReservationControl ..> ReservationRepository
    ReservationControl --> Hotel
    Hotel "1" *-- "*" RoomType
    RoomType "1" o-- "*" Room
    Reservation "*" -- "*" Room : target
    MySQLReservationRepository ..|> ReservationRepository
```

## ステートマシン図
Reservation エンティティの status の変化を定義する。保守要件である「キャンセル」の導線を予め組み込んでおく。
```mermaid
stateDiagram-v2
    [*] --> CREATED : new Reservation()
    
    CREATED --> CHECKED_IN : mark_checked_in()
    CREATED --> CANCELLED : cancel()
    
    CHECKED_IN --> COMPLETED : check_out()
    
    CANCELLED --> [*]
    COMPLETED --> [*]

    note right of CREATED
        予約確定・未チェックイン
        （確保されたRoomは指定日に予約済）
    end note
    note right of CANCELLED
        キャンセル済
        （確保されていたRoomの該当日程を解放）
    end note
```
- ガード条件とカプセル化
各遷移メソッドは、不正な状態からの呼び出し（例：CHECKED_IN 状態から cancel() を呼ぶなど）に対してドメイン独自の例外（BureaucraticError など）を送出することで、業務ルールの破綻を防ぐ。

## UI（LINEボット）連携とセッション管理のアーキテクチャ
チャットボットUI特有の課題として、「1つのユースケース（例：予約）を完了させるために、ユーザーと複数回のやり取り（日付の入力→人数入力→確定）が必要になる」点が挙げられる。これを解決するため、プレゼンテーション層に SessionManager（状態ステートマシン） を導入する。

| 構成要素 | 役割 |
| --- | --- |
| Webhook Handler | LINEから送信されたJSONを解析し、ユーザーIDとメッセージテキストを抽出する。 |
| SessionManager | Redisやオンメモリ辞書を用いて、{user_id: {"state": "AWAITING_DATE", "context": {}}} のような形でユーザーごとの会話進行度を管理する。 |
| Intent Router | ユーザーのテキスト（「予約したい」など）を判別し、SessionManagerのステータスを初期化し、対応するControlを呼び出す。 |

- 処理フロー例
1. ーザー「予約したい」 -> Webhookが受信。
2. Routerが意図を「予約開始」と解釈。SessionManagerの状態を AWAITING_DATE に設定。
3. ChatInterfaceが「宿泊日を入力してください」と返信。
4. ユーザー「2026/07/01」 -> Webhookが受信。
5. SessionManagerが現在の状態(AWAITING_DATE)を確認。入力値を一時保存し、状態を AWAITING_ROOM_TYPE に進め、Control層に空室照会(search_room)を依頼する。
