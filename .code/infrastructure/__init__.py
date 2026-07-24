"""インフラストラクチャ層の外部公開窓口

永続化は SQLite に統一している。SQLiteReservationRepository は Python 標準
ライブラリ (sqlite3) だけで動作する。
"""

from .sqlite_reservation_repository import SQLiteReservationRepository

__all__ = [
    "SQLiteReservationRepository",
]
