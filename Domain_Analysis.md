# 概念モデル (ドメイン分析)

ホテル予約システム (HRS) のドメイン分析の成果物である概念モデルをまとめた。
本システムは, LINE Messaging APIを用いて, ホテルの予約・チェックイン・チェックアウトを行うチャットボット型システムである。

概念モデルは, 対象とする問題領域の本質的な概念と概念間の関係のみを表す。実装技術 (LINE API, チャットボット等) やシステムそのものは, 概念モデルには含めていない。


## 前提条件

- 客は1泊のみ宿泊し, 翌日に必ずチェックアウトする (連泊は想定しない)。
- 1つの予約は, 1泊を対象とする。
- 予約番号, 部屋番号, 宿泊料 (料金) は, 必ずシステムが扱う要素とする。

余力があれば後に変更してもいいかも...


## クラス図

```mermaid
classDiagram
    class user {
        name
    }
    class Reservation {
        reservation_number
        checkInDate
    }
    class Hotel {
        hotel_name
    }
    class Room {
        room_number
        price
        vacant
    }
    class receptionist {
        name : str
    }

    Hotel "1" o-- "*" Room
    Hotel "1" o-- "*" receptionist
    user "1" -- "*" Reservation : 予約者
    Reservation "*" -- "*" Room
```

制約: 同一の部屋について, 同一の宿泊日 (checkInDate) を対象とする予約は高々1つである (二重予約の禁止)。


### クラスの説明

| クラス | 役割 | 属性 | 説明 |
| --- | --- | --- | --- |
| user | もの <br>(主体) | name | 予約を行う客。 |
| receptionist | もの <br>(主体) | name | ホテルの受付係。 |
| Reservation | こと | reservation_number, checkInDate | 客と部屋を結ぶ予約という事象。連泊なしのため日付は宿泊日 (チェックイン日) 1つで足りる。|
| Room | もの <br>(対象) | room_number, price, vacant | 予約の対象となる部屋。price は宿泊料の源泉となる。vacantは宿泊可能ラベル（T/F）。|
| Hotel | もの <br>(場所) | hotel_name | 部屋を保有する全体としての概念。|


### 関連と多重度

| 関連 | 多重度 | 読み方 |
| --- | --- | --- |
| Hotel ◇— Room | 1 対 * | 1つのホテルは複数の部屋を保有する (集約)。|
| Hotel ◇— receptionist | 1 対 * | 1つのホテルは複数の受付係を雇用する (集約)。|
| user — Reservation (予約者) | 1 対 * | 1人の客は複数の予約を行いうるが, 1つの予約は1人の客に帰属する。|
| Reservation — Room | * 対 * | 1つの予約は1つ以上の部屋を対象とする。1つの部屋は, 宿泊日が異なれば複数の予約の対象となりうる。|


## オブジェクト図

グランドホテルが2つの部屋を保有し, 2人の客がそれぞれ異なる日に異なる部屋を予約した状況を表す。

```mermaid
flowchart TB
    H["Grand Hotel : Hotel<br/>hotel_name = Grand Hotel"]
    G1["Guest1 : user<br/>name = Taro Waseda"]
    G2["Guest2 : user<br/>name = Hanako Sato"]
    RV1["Reservation1 : Reservation<br/>reservation_number = 012345<br/>checkInDate = 2026/07/01"]
    RV2["Reservation2 : Reservation<br/>reservation_number = 012346<br/>checkInDate = 2026/07/04"]
    R1["Room101 : Room<br/>room_number = 101<br/>price = 10000<br/>vacant = True"]
    R2["Room1102 : Room<br/>room_number = 1102<br/>price = 50000<br/>vacant = True"]

    G1 ---|予約者| RV1
    G2 ---|予約者| RV2
    RV1 ---|対象| R1
    RV2 ---|対象| R2
    H ---|所有者| R1
    H ---|所有者| R2
```

この図により, 各クラスがインスタンス化可能であること, および多重度・制約と矛盾しないことを確認できる。


## LINE API の位置づけ

LINE Messaging API は実装・チャネルであるため, 概念モデルには登場させない。後続の各工程では次のように扱う。

- 要求分析: user がアクタとしてLINEを通じてシステムを利用する。「予約する」「チェックインする」「チェックアウトする」がユースケースとなる。
- システム分析: チャットUIに対応する境界 (バウンダリ) クラスを置き, 外部システムとしての LINE Messaging API との連携を明確化する。
- 設計・実装: LINE Messaging API (Webhookによるメッセージ受信, 応答メッセージ送信) をPythonで実装する。客の識別にはLINEのユーザ識別子を利用する設計が考えられる。

## 今後の検討事項

- 宿泊料 (料金) をRoomに持たせるか, 予約時点の金額をReservationに記録するか。
- 宿泊料の支払い方法 (チャット上での決済か, 現地払いか)。
- ホテル側で部屋データを登録・管理する管理者を概念に含めるか。

---
