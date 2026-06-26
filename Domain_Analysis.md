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
    class Guest {
        name : str
    }
    class Reservation {
        reservationNumber : int
        stayingDate : date
        status : str
    }
    class Hotel {
        hotel_name : str
    }
    class RoomType {
        typeName : str
        price : int
    }
    class Room {
        roomNumber : int
        status : str
    }
    class Receptionist{
        name : str
    }
    class Payment {
        stayingDate : date
        roomNumber : int
        amount : int
        status : str
    }
    Hotel "1" *-- "*" Room : 
    Hotel "1" *-- "*" Receptionist : 
    RoomType "1" -- "*" Room : 
    Guest "1" -- "*" Reservation : 予約者
    Reservation "*" -- "*" Room : 対象
    Reservation "1" -- "1" Payment : 紐づく決済
```

制約: 同一の部屋について, 同一の宿泊日 (stayingDate) を対象とする予約は高々1つである (二重予約の禁止)。


### クラスの説明

| クラス | 役割 | 属性 | 説明 |
| --- | --- | --- | --- |
| Guest | もの <br>(主体) | name | 予約を行う客。 |
| Receptionist | もの <br>(主体) | name | ホテルの受付係。 |
| Reservation | こと | reservatioNumber, stayingData, status | 客と部屋を結ぶ予約という事象。連泊なしのため日付は宿泊日 (チェックイン日) 1つで足りる。|
| RoomType | もの <br>(概念) | typeName, price | 部屋の種類（シングル、ツイン、スイートなど）。price（宿泊料）は部屋タイプごとに設定される。|
| Room | もの <br>(対象) | roomNumber, status | 予約の対象となる具体的な部屋。ホテル（Hotel）に保有され、特定の部屋タイプ（RoomType）に属する。statusは空室状況などを表す。|
| Hotel | もの <br>(場所) | hotel_name | 部屋を保有する全体としての概念。|
| Payment | こと <br> | stayingDate, roomNumber, amount, status | 予約（Reservation）に1対1で紐づく決済という事象。宿泊日、部屋番号、金額（amount）、支払状態（status）を管理する。|


### 関連と多重度

| 関連 | 多重度 | 読み方 |
| --- | --- | --- |
| Hotel *— Room | 1 対 * | 1つのホテルは複数の部屋を保有する (コンポジション)。|
| Hotel *— Receptionist | 1 対 * | 1つのホテルは複数の受付係を保有する (コンポジション)。|
| RoomType — Room | 1 対 * | 1つの部屋タイプは、該当する複数の具体的な部屋を保有する 。|
| Guest — Reservation (予約者) | 1 対 * | 1人の客は複数の予約を行いうるが, 1つの予約は1人の客に帰属する。|
| Reservation — Room (対象) | * 対 * | 1つの予約は1つ以上の部屋を対象とする。1つの部屋は, 宿泊日が異なれば複数の予約の対象となりうる。|
| Reservation -- Payment (紐づく決済) | 1 対 1 | 1つの予約に対して、決済は必ず1つだけ一意に紐づく。。|

## オブジェクト図

グランドホテルが2つの部屋を保有し, 2人の客がそれぞれ異なる日に異なる部屋を予約した状況（未チェックイン）を表す。

```mermaid
flowchart TB
    H["Grand Hotel : Hotel<br/>hotel_name = &quot;Grand Hotel&quot;"]
    
    RT1["Standard : RoomType<br/>typeName = &quot;Standard&quot;<br/>price = 10000"]
    RT2["Suite : RoomType<br/>typeName = &quot;Suite&quot;<br/>price = 50000"]

    G1["Guest1 : Guest<br/>name = &quot;Taro Waseda&quot;"]
    G2["Guest2 : Guest<br/>name = &quot;Hanako Sato&quot;"]
    
    RV1["Reservation1 : Reservation<br/>reservationNumber = 012345<br/>stayingDate = 2026/07/01<br/>status = &quot;Confirmed&quot;" ]
    RV2["Reservation2 : Reservation<br/>reservationNumber = 012346<br/>stayingDate = 2026/07/04<br/>status = &quot;Confirmed&quot;"]
    
    R1["Room101 : Room<br/>roomNumber = 101<br/>status = &quot;Occupied&quot;"]
    R2["Room1102 : Room<br/>roomNumber = 1102<br/>status = &quot;Occupied&quot;"]

    G1 ---|予約者| RV1
    G2 ---|予約者| RV2
    RV1 ---|対象| R1
    RV2 ---|対象| R2
    
    H --- R1
    H --- R2
    
    RT1 --- R1
    RT2 --- R2
```

この図により, 各クラスがインスタンス化可能であること, および多重度・制約と矛盾しないことを確認できる。

---
