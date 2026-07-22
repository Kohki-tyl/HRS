from abc import ABC, abstractmethod
from datetime import date
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
    def find_by_staying_date(self, staying_date: date) -> List[Reservation]:
        """指定した宿泊日に部屋を押さえている予約（キャンセル以外）を返す

        在庫（空室状況）は、この結果から「予約済みの部屋番号」を導出して判定する。
        Room 側は在庫状態を持たず、DB の予約が唯一の在庫の真実となる。
        """
        pass

    @abstractmethod
    def find_all(self) -> List[Reservation]:
        """すべての予約を返す（フロントデスクの予約一覧表示用）"""
        pass
