from abc import ABC, abstractmethod
from typing import Optional
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