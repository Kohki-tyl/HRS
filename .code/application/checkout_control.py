from typing import Optional
from domain import Reservation, ReservationRepository, BureaucraticError

class CheckOutControl:
    """UC3: チェックアウト手続きを行う の進行を管理するコントロール"""

    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def search_information(self, room_number: int) -> Optional[Reservation]:
        """部屋番号から現在滞在中の予約（精算情報含む）を照会する"""
        return self.repository.find_by_room_number(room_number)

    def check_out(self, room_number: int) -> None:
        """支払い完了と一括チェックアウト処理を実行する"""
        reservation = self.repository.find_by_room_number(room_number)
        
        if not reservation:
            raise BureaucraticError(f"部屋番号 {room_number} に紐づく滞在中の予約が見つかりません。")
        
        # 予約エンティティにチェックアウト（一括精算・空室化）を委譲
        reservation.check_out()
        
        # 状態変化をリポジトリに保存
        self.repository.save(reservation)