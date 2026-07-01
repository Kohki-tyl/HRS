# 概念モデル (ドメイン分析)

ホテル予約システム (HRS) のドメイン分析の成果物である概念モデルをまとめた。
本システムは, LINE Messaging APIを用いて, ホテルの予約・チェックイン・チェックアウトを行うチャットボット型システムである。

概念モデルは, 対象とする問題領域の本質的な概念と概念間の関係のみを表す。実装技術 (LINE API, チャットボット等) やシステムそのものは, 概念モデルには含めていない。

<br>

## 前提条件

- 客は1泊のみ宿泊し, 翌日に必ずチェックアウトする (連泊は想定しない)。
- 1つの予約は1つ以上の部屋を対象とする (団体予約を許す)。予約時に対象の部屋を確定する。
- 予約番号, 部屋番号, 宿泊料は, 必ずシステムが扱う要素とする。
- 宿泊料は部屋種別ごとの料金とし (当面は種別が1つで実質定額), 1予約の支払い額は割り当てた部屋の料金の合計とする。
- チェックアウトの支払いは現金のみとする。現金の受領完了は受付係が確認し, システムへ通知する。
- 利用者とシステムの対話は, すべて LINE を通じて行う (LINE は実装・チャネルであり, 概念モデルには登場させない)。

余力があれば後に変更してもいいかも...

<br>
<br>

## クラス図

```mermaid
classDiagram
    class Guest {
        name
    }
    class Reservation {
        reservationNumber : int
        roomNumber : int
        stayingDate : date
        status : str
    }
    class Hotel {
        hotel_name : str
    }
    class RoomType {
        type_name
        price
    }
    class Room {
        room_number
    }
    class Payment {
        stayingDate : date
        reservationNumber : int
        roomNumber : int
        amount : int
        status : str
    }
    class Hotel {
        hotel_name
    }
    class Receptionist {
        name
    }

    Guest "1" -- "*" Reservation : 予約者
    Reservation "*" -- "1..*" Room : 対象
    Reservation "1" -- "0..1" Payment : 紐づく決済
    Room "*" -- "1" RoomType : 種別
    Hotel "1" o-- "*" Room : 所有者
    Hotel "1" o-- "*" Receptionist : 雇用
    Receptionist "1" -- "*" Payment : 確認

```

制約:
- **同一の部屋は, 同一の宿泊日について複数の予約に割り当てられない** (同一宿泊日での二重割当の禁止)。多重度 `* — 1..*` は時期 (宿泊日) をまたいだ再利用を許すため, 同一宿泊日の重複はこの制約で防ぐ。
- 1つの予約に割り当てられる部屋はすべて, その予約の宿泊日 (staying_date) を共有する。
- ある宿泊日・種別の割り当て済み部屋数は, その種別の部屋数を超えない (超過予約の禁止)。

<br>

### クラスの説明

## クラスの説明

| クラス | 役割 | 属性 | 説明 |
| --- | --- | --- | --- |
| Guest | もの <br>(主体) | name | 予約を行う客。 |
| Receptionist | もの <br>(主体) | name | ホテルの受付係。 |
| Reservation | こと | reservatioNumber, roomNumber, stayingData, status | 客と部屋を結ぶ予約という事象。連泊なしのため日付は宿泊日 (チェックイン日) 1つで足りる。|
| RoomType | もの <br>(概念) | typeName, price | 部屋の種類（シングル、ツイン、スイートなど）。price（宿泊料）は部屋タイプごとに設定される。|
| Room | もの <br>(対象) | roomNumber, status | 予約の対象となる具体的な部屋。ホテル（Hotel）に保有され、特定の部屋タイプ（RoomType）に属する。statusは空室状況などを表す。|
| Hotel | もの <br>(場所) | hotel_name | 部屋を保有する全体としての概念。|
| Payment | こと <br> | stayingDate, reservationNumber, roomNumber, amount, status | 予約（Reservation）に1対1で紐づく決済という事象。宿泊日、部屋番号、金額（amount）、支払状態（status）を管理する。|

<br>

### 関連と多重度

| 関連 | 多重度 | 読み方 |
| --- | --- | --- |
| Hotel *— Room | 1 対 * | 1つのホテルは複数の部屋を保有する (コンポジション)。|
| Hotel *— Receptionist | 1 対 * | 1つのホテルは複数の受付係を保有する (コンポジション)。|
| RoomType — Room | 1 対 * | 1つの部屋タイプは、該当する複数の具体的な部屋を保有する 。|
| Guest — Reservation (予約者) | 1 対 * | 1人の客は複数の予約を行いうるが, 1つの予約は1人の客に帰属する。|
| Reservation — Room (対象) | 1 対 * | 1つの予約は1つ以上の部屋を対象とする。1つの部屋は, 宿泊日が異なれば複数の予約の対象となりうる。|
| Reservation -- Payment (紐づく決済) | 1 対 1 | 1つの予約に対して、決済は必ず1つだけ一意に紐づく。。|

## オブジェクト図

利用者の早稲田太郎が 2026/07/01 の宿泊でGrand Hotelの **2室を予約 (団体予約)**, 部屋101・102 (シングル) を予約時に確定し, チェックインで予約ごとに1件の支払い (8000 × 2 = 16000円) が発生, 受付係 山田が現金受領を確認した状況を表す。

```mermaid
flowchart TB
    G["g1 : Guest<br/>name = 早稲田太郎"]
    RV["rv1 : Reservation<br/>reservation_number = 0001<br/>staying_date = 2026/07/01<br/>status = 利用済"]
    R1["r101 : Room<br/>room_number = 101"]
    R2["r102 : Room<br/>room_number = 102"]
    RT["t1 : RoomType<br/>type_name = シングル<br/>price = 8000"]
    PM["p1 : Payment<br/>amount = 16000<br/>status = 精算済"]
    HT["h1 : Hotel<br/>hotel_name = Grand Hotel"]
    RC["山田 : Receptionist<br/>name = 山田"]

    G ---|予約者| RV
    RV ---|対象| R1
    RV ---|対象| R2
    R1 ---|種別| RT
    R2 ---|種別| RT
    RV ---|紐づく決済| PM
    HT ---|所有者| R1
    HT ---|所有者| R2
    HT ---|雇用| RC
    RC ---|確認| PM
```
<br>

この図により, 各クラスがインスタンス化可能であること, および多重度・制約と矛盾しないことを確認できる。

<br>

---
## 今後の検討事項

- **部屋番号の通知タイミング.** 部屋は予約時に確定するため, 部屋番号を予約時に伝えるか, チェックイン時に伝えるかは UX の選択として決める。
- **設計への申し送り.** status は列挙型 (Enum) として実装する。超過予約・二重割当の保証は予約処理が担う。予約時の部屋確定は同時実行の競合に注意し, ロック等を設計する。物理的な部屋状態 (清掃中・整備中など, 予約から導出できない状態) が必要になった場合は, その時点で Room に状態を追加する。
- 予約のキャンセル・変更を概念・機能として加えるか (現状は対象外)。
