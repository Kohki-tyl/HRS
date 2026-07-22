from abc import ABC, abstractmethod
from typing import Optional, List
from domain.models import Reservation

class ReservationRepository(ABC):
    """予約情報の永続化を担うリポジトリのインターフェース """

    @abstractmethod
    def save(self, reservation: Reservation) -> None:
        """予約情報を保存・更新する """
        pass

    @abstractmethod
    def find_by_id(self, reservation_number: int) -> Optional[Reservation]:
        """予約番号から予約情報を検索・復元する """
        pass

    @abstractmethod
    def find_by_room_number(self, room_number: int) -> Optional[Reservation]:
        """部屋番号から現在滞在中の予約情報を検索・復元する """
        pass

    @abstractmethod
    def find_active_reservations(self) -> List[Reservation]:
        """部屋・日付を押さえている予約（キャンセル以外）をすべて返す

        Room の在庫 (reserved_dates) は永続化されないため、起動時に
        Hotel の在庫を DB から復元する用途で使う。キャンセル済み
        (CANCELLED) は該当日を解放しているため除外する。
        """
        pass
