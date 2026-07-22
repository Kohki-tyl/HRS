"""インフラストラクチャ層の外部公開窓口

SQLiteReservationRepository は標準ライブラリだけで動くが、
MySQLReservationRepository は mysql-connector-python を必要とする。
MySQL ドライバが未導入の環境でも SQLite 版を使えるよう、
MySQLReservationRepository は実際に参照された時点で読み込む。
"""

from .sqlite_reservation_repository import SQLiteReservationRepository

__all__ = [
    "MySQLReservationRepository",
    "SQLiteReservationRepository",
]


def __getattr__(name):
    if name == "MySQLReservationRepository":
        from .mysql_reservation_repository import MySQLReservationRepository
        return MySQLReservationRepository
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
