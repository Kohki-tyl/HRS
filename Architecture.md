# アーキテクチャ設計

## 方針
非機能要件に対する設計方針は以下の通り。
- ### 保守性（UI変更への対応）: 
    UI層（LINEボットやテキストUI）とアプリケーション層（コントロール）を完全に分離する。これにより、UIがLINEからWeb画面やスマホアプリに変わっても、ビジネスロジックは一切変更せずに済む。
- ### 開発の容易性（独立した並行開発）: 
    各層（パッケージ）の間に「インターフェース」を設ける。これにより、例えばUI担当グループは「コントローラーのダミー（モック）」を使って開発を進め、DB担当グループは「ロジック抜きでSQLのテストだけ行う」といった独立開発が可能になる。
- ### 永続性とネットワーク（MySQL等の利用）: 
    ビジネスロジック（ドメイン層）にSQLを直接書くのではなく、インフラストラクチャ層（データアクセス層）に隔離する。

## パッケージ図
```mermaid
classDiagram
    namespace UI {
        class ChatInterface { <<boundary>> }
    }
    namespace Application {
        class ReservationControl { <<control>> }
        class CheckInControl { <<control>> }
        class CheckOutControl { <<control>> }
    }
    namespace Domain {
        class Hotel { <<entity>> }
        class RoomType { <<entity>> }
        class Room { <<entity>> }
        class Reservation { <<entity>> }
        class Payment { <<entity>> }
        class ReservationRepository { <<interface>> }
    }
    namespace Infrastructure {
        class ReservationRepositoryImpl { <<infra>> }
        class DatabaseConnector { <<infra>> }
    }

    ChatInterface ..> ReservationControl
    ChatInterface ..> CheckInControl
    ChatInterface ..> CheckOutControl
    
    ReservationControl ..> ReservationRepository
    ReservationControl ..> Hotel
    
    ReservationRepositoryImpl ..|> ReservationRepository
    ReservationRepositoryImpl ..> Reservation
    ReservationRepositoryImpl ..> DatabaseConnector
```
| パッケージ  | 役割 |
| --- | --- |
| UI層 | ユーザーとの対話（標準入出力やLINE API）のみを担当し、ロジックは持たずアプリケーション層を呼び出します。|
| アプリケーション層 | システム分析で定義したユースケース（コントロール）の進行を管理します。|
| ドメイン層 | システム分析で定義したエンティティ群です。ルールや状態（在庫を減らす、ステータスを変える等）を持ちます。この層は他のどの層にも依存しません。|
| インフラ層 | MySQLなどのデータベースへのアクセス（SQLの実行）をカプセル化します。

## クラス図
パッケージ間の通信をインターフェース（<<interface>>）を用いて疎結合にするためのクラス図です。
```mermaid
classDiagram
    %% Presentation Layer
    class ChatInterface {
        <<boundary>>
        +inputQuery(conditions): void
        +showPrice(amount): void
        +notifyCompletion(): void
    }

    %% Application Layer
    class ReservationControl {
        <<control>>
        +reserveRoom(date, num, type): void
    }
    class CheckInControl {
        <<control>>
        +checkIn(resNum): void
    }
    class CheckOutControl {
        <<control>>
        +checkOut(roomNum): void
    }

    %% Domain Layer (Entities & Repository Interface)
    class ReservationRepository {
        <<abstract>>
        +save(Reservation)*
        +findById(int)*
    }
    class Hotel {
        <<entity>>
        +getAvailableRoomTypes(date, num): List~RoomType~
    }
    class RoomType {
        <<entity>>
        -price: int
        -vacancy: int
        +checkStock(num): bool
        +reduceStock(num): void
    }
    class Room {
        <<entity>>
        -roomNumber: int
        -status: str
        +assign(): void
        +markUsing(): void
        +markEmpty(): void
    }
    class Reservation {
        <<entity>>
        -reservationNumber: int
        -status: str
        +markCheckedIn(): void
        +checkOut(): void
        +getAmount(): int
    }
    class Payment {
        <<entity>>
        -amount: int
        -status: str
        +markPaid(): void
    }

    %% Infrastructure Layer
    class MySQLReservationRepository {
        <<infra>>
        -connection: mysql_connector
        +save(Reservation): void
        +findById(int): Reservation
    }

    %% Relationships
    ChatInterface ..> ReservationControl
    ChatInterface ..> CheckInControl
    ChatInterface ..> CheckOutControl

    ReservationControl ..> ReservationRepository
    ReservationControl --> Hotel
    
    Hotel *-- RoomType
    RoomType o-- Room
    
    Reservation "*" -- "1" Room : 対象
    Reservation "1" -- "1" Payment : 決済
    
    MySQLReservationRepository ..|> ReservationRepository : implements
```