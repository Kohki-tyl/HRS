from typing import List, Optional
from domain import Reservation, ReservationRepository, BureaucraticError

class CheckInControl:
    """UC2: チェックイン手続きを行う の進行を管理するコントロール"""

    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def search_reservation(self, reservation_number: int) -> Optional[Reservation]:
        """予約番号から予約情報を照会する"""
        return self.repository.find_by_id(reservation_number)

    def check_in(self, reservation_number: int) -> List[int]:
        """チェックイン処理を実行し、割り当てられた部屋番号リストを返す"""
        reservation = self.repository.find_by_id(reservation_number)
        
        if not reservation:
            raise BureaucraticError(f"予約番号 {reservation_number} が見つかりません。")
        
        # 予約エンティティにチェックイン処理を委譲（内部でRoomのステータス等も変化）
        reservation.mark_checked_in()
        
        # 状態が変化したため、リポジトリに再保存
        self.repository.save(reservation)
        
        # 鍵を渡すために部屋番号のリストを返す
        return reservation.get_room_numbers()