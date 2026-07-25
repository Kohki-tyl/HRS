from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional, Set

class BureaucraticError(Exception):
    """業務ルールに反する操作が行われたことを表すドメイン例外"""
    pass

class RoomStatus(Enum):
    VACANT = "Vacant"
    IN_USE = "InUse"

class ReservationStatus(Enum):
    CREATED = "Created"
    CHECKED_IN = "CheckedIn"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class PaymentStatus(Enum):
    PENDING = "Pending"
    PAID = "Paid"

@dataclass
class Guest:
    name: str
    # 予約を行った LINE 利用者の識別子（予約者本人のみキャンセルできるようにするため）
    line_user_id: Optional[str] = None

@dataclass
class Room:
    room_number: int
    # 予約された日付を保持する集合 (Set)。同一部屋の別日予約を許容する。
    reserved_dates: Set[date] = field(default_factory=set)
    # 現在その部屋に滞在中かどうか (VACANT -> IN_USE -> VACANT)
    status: RoomStatus = RoomStatus.VACANT

    def is_vacant_on(self, staying_date: date) -> bool:
        return staying_date not in self.reserved_dates

    def assign(self, staying_date: date) -> None:
        if not self.is_vacant_on(staying_date):
            raise BureaucraticError(f"部屋番号 {self.room_number} は {staying_date} に既に予約されています。")
        self.reserved_dates.add(staying_date)

    def cancel_assign(self, staying_date: date) -> None:
        self.reserved_dates.discard(staying_date)

    def mark_using(self) -> None:
        self.status = RoomStatus.IN_USE

    def mark_empty(self) -> None:
        self.status = RoomStatus.VACANT

    def get_room_number(self) -> int:
        return self.room_number

@dataclass
class RoomType:
    type_name: str
    price: int
    rooms: List[Room] = field(default_factory=list)

    def get_available_count(self, staying_date: date) -> int:
        return len([r for r in self.rooms if r.is_vacant_on(staying_date)])

    def check_stock(self, number_of_rooms: int, staying_date: date) -> bool:
        # 指定日に空いている部屋をフィルタリング
        return self.get_available_count(staying_date) >= number_of_rooms

    def reduce_stock(self, number_of_rooms: int, staying_date: date) -> List[Room]:
        vacant_rooms = [r for r in self.rooms if r.is_vacant_on(staying_date)]
        if len(vacant_rooms) < number_of_rooms:
            raise BureaucraticError(f"{staying_date} の {self.type_name} は在庫が不足しています。")

        assigned_rooms = vacant_rooms[:number_of_rooms]
        for room in assigned_rooms:
            room.assign(staying_date)  # 部屋自身に日付を登録させる
        return assigned_rooms

@dataclass
class Hotel:
    hotel_name: str
    room_types: List[RoomType] = field(default_factory=list)

    def get_available_room_types(self, staying_date: date, number_of_rooms: int) -> List[RoomType]:
        return [rt for rt in self.room_types if rt.check_stock(number_of_rooms, staying_date)]

    def get_room_type(self, type_name: str) -> RoomType:
        room_type = next((rt for rt in self.room_types if rt.type_name == type_name), None)
        if not room_type:
            raise BureaucraticError(f"「{type_name}」という部屋タイプはありません。")
        return room_type

    def find_room(self, room_number: int) -> Optional[Room]:
        """部屋番号から自身が保有する Room を返す（無ければ None）"""
        for room_type in self.room_types:
            for room in room_type.rooms:
                if room.room_number == room_number:
                    return room
        return None

    def allocate_rooms(self, staying_date: date, requested_rooms: dict[str, int]) -> List[Room]:
        assigned_rooms = []

        # 1. 事前チェック: 要求された全タイプの在庫が足りているか確認（All or Nothing）
        for type_name, count in requested_rooms.items():
            if count <= 0:
                continue
            room_type = self.get_room_type(type_name)
            if not room_type.check_stock(count, staying_date):
                raise BureaucraticError(f"【在庫不足】{type_name} は {count} 部屋ご用意できません。")

        # 2. 確保実行: 全て足りている場合のみ、実際の在庫を減らす
        for type_name, count in requested_rooms.items():
            if count <= 0:
                continue
            assigned_rooms.extend(self.get_room_type(type_name).reduce_stock(count, staying_date))

        return assigned_rooms

@dataclass
class Payment:
    amount: int
    status: PaymentStatus = PaymentStatus.PENDING

    def get_amount(self) -> int:
        return self.amount

    def mark_paid(self) -> None:
        self.status = PaymentStatus.PAID

@dataclass
class Reservation:
    reservation_number: int
    staying_date: date
    guest: Guest
    rooms: List[Room]
    payment: Payment
    status: ReservationStatus = ReservationStatus.CREATED

    def mark_checked_in(self) -> None:
        if self.status != ReservationStatus.CREATED:
            raise BureaucraticError("この予約はチェックイン可能な状態ではありません。")

        # チェックインは宿泊日当日にのみ行う (UC2 備考)
        if self.staying_date != date.today():
            raise BureaucraticError(
                f"本日は {date.today()} です。宿泊日（{self.staying_date}）以外はチェックインできません。")

        self.status = ReservationStatus.CHECKED_IN
        for room in self.rooms:
            room.mark_using()

    def check_out(self) -> None:
        if self.status != ReservationStatus.CHECKED_IN:
            raise BureaucraticError("チェックインされていない予約です。")

        for room in self.rooms:
            room.mark_empty()

        self.payment.mark_paid()
        self.status = ReservationStatus.COMPLETED

    def cancel(self) -> None:
        if self.status != ReservationStatus.CREATED:
            raise BureaucraticError("チェックイン済み・完了済みの予約はキャンセルできません。")

        # キャンセルは宿泊日の前日まで（当日以降は不可）
        if self.staying_date <= date.today():
            raise BureaucraticError("キャンセルはチェックインの前日までにお願いします。")

        # 確保していた部屋の該当日を解放する
        for room in self.rooms:
            room.cancel_assign(self.staying_date)

        self.status = ReservationStatus.CANCELLED

    def get_amount(self) -> int:
        return self.payment.get_amount()

    def get_room_numbers(self) -> List[int]:
        return [room.get_room_number() for room in self.rooms]

    def is_checked_in(self) -> bool:
        """チェックイン状態か確認"""
        return self.status == ReservationStatus.CHECKED_IN
