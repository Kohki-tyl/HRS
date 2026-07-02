from datetime import date
from typing import List
from domain import Hotel, RoomType, Reservation, Guest, Payment, ReservationRepository

class ReservationControl:
    """UC1: 部屋を予約する の進行を管理するコントロール"""
    
    def __init__(self, repository: ReservationRepository, hotel: Hotel):
        # 依存性逆転の原則(DIP)により、具象クラスではなくインターフェースを受け取る
        self.repository = repository
        self.hotel = hotel

    def search_room(self, staying_date: date, number_of_rooms: int) -> List[RoomType]:
        """宿泊日と部屋数を指定し、空室のある部屋タイプ一覧を取得する"""
        return self.hotel.get_available_room_types(staying_date, number_of_rooms)

    def reserve_room(
        self, 
        reservation_number: int, 
        staying_date: date, 
        guest_name: str, 
        type_name: str, 
        number_of_rooms: int
    ) -> Reservation:
        """部屋の確保と予約オブジェクトの生成・保存を行う"""
        
        # 1. ホテルに処理を委譲して具体的な部屋（日付指定）を確保
        assigned_rooms = self.hotel.allocate_rooms(staying_date, type_name, number_of_rooms)
        
        # 2. 料金の計算（選択された部屋タイプの価格 × 部屋数）
        room_type = next(t for t in self.hotel.room_types if t.type_name == type_name)
        total_amount = room_type.price * number_of_rooms
        
        # 3. 関連オブジェクトの生成
        guest = Guest(name=guest_name)
        payment = Payment(amount=total_amount)
        
        # 4. 予約エンティティの生成
        reservation = Reservation(
            reservation_number=reservation_number,
            staying_date=staying_date,
            guest=guest,
            rooms=assigned_rooms,
            payment=payment
        )
        
        # 5. リポジトリを介して保存（永続化）
        self.repository.save(reservation)
        return reservation