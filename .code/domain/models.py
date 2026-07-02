from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Set

class RoomStatus(Enum):
    VACANT = "Vacant"
    OCCUPIED = "Occupied"

class ReservationStatus(Enum):
    CREATED = "Created"
    CHECKED_IN = "CheckedIn"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class PaymentStatus(Enum):
    UNPAID = "Unpaid"
    PAID = "Paid"

@dataclass
class Guest:
    name: str

@dataclass
class Room:
    room_number: int
    # 予約された日付を保持する集合 (Set)
    reserved_dates: Set[date] = field(default_factory=set)
    
    # チェックインされた（滞在中の）日付を管理する場合
    occupied_dates: Set[date] = field(default_factory=set)

    def is_vacant_on(self, staying_date: date) -> bool:
        return staying_date not in self.reserved_dates

    def assign(self, staying_date: date) -> None:
        if not self.is_vacant_on(staying_date):
            raise ValueError(f"部屋番号 {self.room_number} は {staying_date} に既に予約されています。")
        self.reserved_dates.add(staying_date)

    def mark_using(self, staying_date: date) -> None:
        self.occupied_dates.add(staying_date)

    def mark_empty(self, staying_date: date) -> None:
        self.occupied_dates.discard(staying_date)

@dataclass
class RoomType:
    type_name: str
    price: int
    total_rooms: int
    rooms: List[Room] = field(default_factory=list)

    def get_available_count(self, staying_date: date) -> int:
        return len([r for r in self.rooms if r.is_vacant_on(staying_date)])

    def check_stock(self, number_of_rooms: int, staying_date: date) -> bool:
        # 指定日に空いている部屋をフィルタリング
        vacant_rooms = [r for r in self.rooms if r.is_vacant_on(staying_date)]
        return len(vacant_rooms) >= number_of_rooms

    def reduce_stock(self, number_of_rooms: int, staying_date: date) -> List[Room]:
        vacant_rooms = [r for r in self.rooms if r.is_vacant_on(staying_date)]
        if len(vacant_rooms) < number_of_rooms:
            raise ValueError(f"{staying_date} の選択された部屋タイプの在庫が不足しています。")
        
        assigned_rooms = vacant_rooms[:number_of_rooms]
        for room in assigned_rooms:
            room.assign(staying_date)  # 部屋自身に日付を登録させる
        return assigned_rooms

@dataclass
class Hotel:
    hotel_name: str
    room_types: List[RoomType] = field(default_factory=list)

    def get_available_room_types(self, staying_date: date, number_of_rooms: int) -> List[RoomType]:
        available_types = []
        for room_type in self.room_types:
            if room_type.check_stock(number_of_rooms, staying_date):
                available_types.append(room_type)
        return available_types

    def allocate_rooms(self, staying_date: date, requested_rooms: dict[str, int]) -> List[Room]:
        assigned_rooms = []
        
        # 1. 事前チェック: 要求された全タイプの在庫が足りているか確認（All or Nothing）
        for type_name, count in requested_rooms.items():
            if count <= 0:
                continue
            room_type = next((rt for rt in self.room_types if rt.type_name == type_name), None)
            if not room_type or not room_type.check_stock(count, staying_date):
                raise ValueError(f"【在庫不足】{type_name} は {count} 部屋ご用意できません。")

        # 2. 確保実行: 全て足りている場合のみ、実際の在庫を減らす
        for type_name, count in requested_rooms.items():
            if count <= 0:
                continue
            room_type = next(rt for rt in self.room_types if rt.type_name == type_name)
            assigned_rooms.extend(room_type.reduce_stock(count, staying_date))
            
        return assigned_rooms

@dataclass
class Payment:
    amount: int
    status: PaymentStatus = PaymentStatus.UNPAID

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
        
        self.status = ReservationStatus.CHECKED_IN
        for room in self.rooms:
            room.mark_using(self.staying_date)

    def check_out(self) -> None:
        if self.status != ReservationStatus.CHECKED_IN:
            raise BureaucraticError("チェックインされていない予約です。")

        for room in self.rooms:
            room.mark_empty(self.staying_date)
            
        self.payment.mark_paid()
        self.status = ReservationStatus.COMPLETED

    def get_amount(self) -> int:
        return self.payment.amount

    def get_room_numbers(self) -> List[int]:
        return [room.room_number for room in self.rooms]


class BureaucraticError(Exception):
    pass