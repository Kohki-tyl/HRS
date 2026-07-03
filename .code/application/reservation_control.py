from datetime import date
from typing import List
from domain import Hotel, RoomType, Reservation, Guest, Payment, ReservationRepository, BureaucraticError

class ReservationControl:
    def __init__(self, repository: ReservationRepository, hotel: Hotel):
        self.repository = repository
        self.hotel = hotel

    # 「各部屋タイプの残り空室数」を辞書で返す
    def get_available_stocks(self, staying_date: date) -> dict[str, int]:
        """宿泊日の各部屋タイプの空室状況を {type_name: vacant_count} で返す"""
        if staying_date < date.today():
            raise BureaucraticError("過去の日付は指定できません。")
            
        stocks = {}
        for room_type in self.hotel.room_types:
            count = room_type.get_available_count(staying_date)
            if count > 0:
                stocks[room_type.type_name] = count
        return stocks

    # requested_rooms として {"Standard": 1, "Suite": 1} を受け取る
    def reserve_rooms(
        self, 
        reservation_number: int, 
        staying_date: date, 
        guest_name: str, 
        requested_rooms: dict[str, int]
    ) -> Reservation:
        
        if staying_date < date.today():
            raise BureaucraticError("過去の日付での予約はできません。")
        if not requested_rooms or all(c <= 0 for c in requested_rooms.values()):
            raise BureaucraticError("最低1室以上を指定してください。")

        # 1. ホテルに一括確保を委譲
        assigned_rooms = self.hotel.allocate_rooms(staying_date, requested_rooms)
        
        # 2. 料金の計算（複数タイプの合計）
        total_amount = 0
        for type_name, count in requested_rooms.items():
            if count > 0:
                room_type = next(t for t in self.hotel.room_types if t.type_name == type_name)
                total_amount += room_type.price * count
                
        # 3. 予約オブジェクトの生成と保存
        reservation = Reservation(
            reservation_number=reservation_number,
            staying_date=staying_date,
            guest=Guest(name=guest_name),
            rooms=assigned_rooms,
            payment=Payment(amount=total_amount)
        )
        self.repository.save(reservation)
        return reservation