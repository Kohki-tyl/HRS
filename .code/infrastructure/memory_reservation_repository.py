from typing import Dict, Optional
from domain.models import Reservation
from domain.repository_interface import ReservationRepository


class MemoryReservationRepository(ReservationRepository):
    """インメモリで予約情報を保管・検索するリポジトリ実装
    
    テスト・デバッグ用。アプリケーション再起動でデータは消える。
    """

    def __init__(self):
        # 予約番号をキーにして予約情報を保持する辞書
        self.reservations: Dict[int, Reservation] = {}
        # 部屋番号をキーにして予約番号を保持する辞書（チェックイン中の予約を素早く検索）
        self.room_to_reservation: Dict[int, int] = {}

    def save(self, reservation: Reservation) -> None:
        """予約情報を保存・更新する"""
        reservation_number = reservation.reservation_number
        self.reservations[reservation_number] = reservation
        
        # チェックイン済みなら部屋から予約への逆マッピングを更新
        if reservation.is_checked_in():
            for room in reservation.rooms:
                self.room_to_reservation[room.room_number] = reservation_number
        else:
            # チェックアウト済みなら逆マッピングを削除
            for room in reservation.rooms:
                self.room_to_reservation.pop(room.room_number, None)

    def find_by_id(self, reservation_number: int) -> Optional[Reservation]:
        """予約番号から予約情報を検索・復元する"""
        return self.reservations.get(reservation_number)

    def find_by_room_number(self, room_number: int) -> Optional[Reservation]:
        """部屋番号から現在滞在中の予約情報を検索・復元する"""
        reservation_number = self.room_to_reservation.get(room_number)
        if reservation_number is None:
            return None
        return self.reservations.get(reservation_number)

    def list_all(self) -> list[Reservation]:
        """すべての予約情報を返す（デバッグ用）"""
        return list(self.reservations.values())

    def clear(self) -> None:
        """すべてのデータをクリアする（テスト用）"""
        self.reservations.clear()
        self.room_to_reservation.clear()

    def initialize_schema(self) -> None:
        """テーブル初期化（インメモリなので何もしない）"""
        pass
