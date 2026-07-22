"""インフラストラクチャ層の外部公開窓口

SQLiteReservationRepository / MemoryReservationRepository は標準ライブラリ
だけで動くが、MySQLReservationRepository は mysql-connector-python を必要とする。
MySQL ドライバが未導入の環境でも他の2つを使えるよう、
MySQLReservationRepository は実際に参照された時点で読み込む。
"""

from .sqlite_reservation_repository import SQLiteReservationRepository
from .memory_reservation_repository import MemoryReservationRepository

__all__ = [
    "MySQLReservationRepository",
    "SQLiteReservationRepository",
    "MemoryReservationRepository",
]


def __getattr__(name):
    if name == "MySQLReservationRepository":
        from .mysql_reservation_repository import MySQLReservationRepository
        return MySQLReservationRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
