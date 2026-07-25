from typing import Optional
from domain import Reservation, ReservationRepository, BureaucraticError

class CancelControl:
    """予約のキャンセル (UC4) の進行を管理するコントロール

    Architecture.md のステートマシン図にある CREATED -> CANCELLED の導線に対応する。
    セルフキャンセルの本人確認として, キャンセルは「予約者の LINE userId」と
    「要求者の userId」が一致する場合のみ許可する (認可はコントロールの責務)。
    状態・期限のガードはドメイン (Reservation.cancel) が担う。
    """

    def __init__(self, repository: ReservationRepository):
        self.repository = repository

    def search_reservation(self, reservation_number: int, requester_user_id: Optional[str] = None) -> Optional[Reservation]:
        """予約番号から予約を照会する。要求者本人の予約でなければ None を返す。

        本人でない予約を「見つからない」と同じ扱いにすることで, 予約番号から
        他人の予約情報が漏れることを防ぐ。
        """
        reservation = self.repository.find_by_id(reservation_number)
        if reservation is None or not self._is_owner(reservation, requester_user_id):
            return None
        return reservation

    def cancel(self, reservation_number: int, requester_user_id: Optional[str] = None) -> Reservation:
        """キャンセル処理を実行し、対象の予約を返す。

        本人確認 (userId 一致) を行ったうえで, キャンセルを予約へ委譲する。
        状態 (CREATED のみ) と期限 (宿泊日の前日まで) のガードはドメインが送出する。
        """
        reservation = self.repository.find_by_id(reservation_number)
        if reservation is None or not self._is_owner(reservation, requester_user_id):
            raise BureaucraticError(f"予約番号 {reservation_number} が見つかりません。")

        # 予約エンティティにキャンセル処理を委譲（内部で状態・期限を検査し、Room の該当日を解放）
        reservation.cancel()

        # 状態が変化したため、リポジトリに再保存
        self.repository.save(reservation)
        return reservation

    @staticmethod
    def _is_owner(reservation: Reservation, requester_user_id: Optional[str]) -> bool:
        """要求者が予約者本人かを判定する。

        予約に紐づく LINE userId と要求者の userId が一致すれば本人。
        LINE userId を持たない予約 (受付・デモ等) は requester_user_id=None のときのみ一致とみなす。
        """
        return reservation.guest.line_user_id == requester_user_id
