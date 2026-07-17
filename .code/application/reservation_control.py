from datetime import date
import random
from domain import Hotel, Reservation, Guest, Payment, ReservationRepository, BureaucraticError

class ReservationControl:
    """UC1: 部屋を予約する の進行を管理するコントロール"""

    # 予約番号の採番範囲（6桁）
    RESERVATION_NUMBER_MIN = 100000
    RESERVATION_NUMBER_MAX = 999999
    # 採番の衝突時に再試行する回数
    NUMBER_ISSUE_ATTEMPTS = 100

    def __init__(self, repository: ReservationRepository, hotel: Hotel):
        self.repository = repository
        self.hotel = hotel

    # 「各部屋タイプの残り空室数と料金」を辞書で返す
    def get_available_stocks(self, staying_date: date) -> dict[str, dict]:
        """宿泊日の各部屋タイプの空室状況を {type_name: {"count": 残室数, "price": 料金}} で返す"""
        if staying_date < date.today():
            raise BureaucraticError("過去の日付は指定できません。")

        stocks = {}
        for room_type in self.hotel.room_types:
            count = room_type.get_available_count(staying_date)
            if count > 0:
                stocks[room_type.type_name] = {"count": count, "price": room_type.price}
        return stocks

    # requested_rooms として {"Standard": 1, "Suite": 1} を受け取る
    def reserve_rooms(
        self,
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
        total_amount = self._calculate_amount(requested_rooms)

        # 3. 予約オブジェクトの生成と保存
        reservation = Reservation(
            reservation_number=self._issue_reservation_number(),
            staying_date=staying_date,
            guest=Guest(name=guest_name),
            rooms=assigned_rooms,
            payment=Payment(amount=total_amount)
        )
        self.repository.save(reservation)
        return reservation

    def _calculate_amount(self, requested_rooms: dict[str, int]) -> int:
        total_amount = 0
        for type_name, count in requested_rooms.items():
            if count > 0:
                total_amount += self.hotel.get_room_type(type_name).price * count
        return total_amount

    def _issue_reservation_number(self) -> int:
        """未使用の予約番号を発行する"""
        for _ in range(self.NUMBER_ISSUE_ATTEMPTS):
            candidate = random.randint(self.RESERVATION_NUMBER_MIN, self.RESERVATION_NUMBER_MAX)
            if not self.repository.find_by_id(candidate):
                return candidate
        raise BureaucraticError("予約番号を発行できませんでした。時間をおいて再度お試しください。")
