from typing import Optional
from domain import Reservation, ReservationRepository, BureaucraticError

class CancelControl:
    """予約のキャンセルの進行を管理するコントロール（保守拡張の受け皿）

    Architecture.md のステートマシン図にある CREATED -> CANCELLED の導線に対応する。
    """

    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def search_reservation(self, reservation_number: int) -> Optional[Reservation]:
        """予約番号から予約情報を照会する"""
        return self.repository.find_by_id(reservation_number)

    def cancel(self, reservation_number: int) -> Reservation:
        """キャンセル処理を実行し、対象の予約を返す"""
        reservation = self.repository.find_by_id(reservation_number)

        if not reservation:
            raise BureaucraticError(f"予約番号 {reservation_number} が見つかりません。")

        # 予約エンティティにキャンセル処理を委譲（内部で Room の該当日を解放）
        reservation.cancel()

        # 状態が変化したため、リポジトリに再保存
        self.repository.save(reservation)
        return reservation
