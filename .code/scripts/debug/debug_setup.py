"""デバッグ用の共通セットアップ（LINE API を使わないローカル実行）

客のチャット (scripts/debug/debug_chat.py) とフロント端末
(scripts/debug/debug_front.py) を別々のターミナルで動かすため、
両者が同じ SQLite ファイルを共有する。
空室状況はその都度 DB から判定する（DB引き）。
"""
from pathlib import Path

from domain import Room, RoomType, Hotel
from infrastructure import SQLiteReservationRepository

# 両ターミナルが共有するデバッグ用 DB
_CODE_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = str(_CODE_ROOT / "hrs_debug.db")


def build_hotel() -> Hotel:
    """ホテルの初期データ（両ターミナルで同一の定義を使う）"""
    rooms_standard = [Room(room_number=101), Room(room_number=102)]
    rooms_suite = [Room(room_number=201)]
    room_types = [
        RoomType(type_name="Standard", price=10000, rooms=rooms_standard),
        RoomType(type_name="Suite", price=50000, rooms=rooms_suite),
    ]
    return Hotel(hotel_name="Debug Hotel", room_types=room_types)


def build_repository() -> SQLiteReservationRepository:
    return SQLiteReservationRepository(DB_PATH)
