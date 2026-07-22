import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Any

# ドメイン層への依存（インターフェースとエンティティの読み込み）
from domain import (
    ReservationRepository,
    Reservation,
    Guest,
    Payment,
    Room,
    ReservationStatus,
    PaymentStatus,
)

# MySQL 版 (schema.sql) と同じ構造を SQLite の型で表現したもの
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reservations (
    reservation_number INTEGER PRIMARY KEY,
    staying_date TEXT NOT NULL,
    guest_name TEXT NOT NULL,
    payment_amount INTEGER NOT NULL,
    payment_status TEXT NOT NULL,
    reservation_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservation_rooms (
    reservation_number INTEGER NOT NULL,
    room_number INTEGER NOT NULL,
    PRIMARY KEY (reservation_number, room_number),
    FOREIGN KEY (reservation_number) REFERENCES reservations(reservation_number) ON DELETE CASCADE
);
"""


class SQLiteReservationRepository(ReservationRepository):
    """SQLite を使用して予約データを永続化するリポジトリの実装

    MySQL を用意せずに、テストやローカルの複数プロセス実行で
    MySQLReservationRepository と同じ契約 (ReservationRepository) を
    満たす具象を使うためのもの。上位層のコードは一切変更せずに
    差し替えられる（依存関係逆転の原則の確認になる）。

    db_path に ":memory:" を渡すと、その接続限りのインメモリ DB になる
    （テストで1接続を保持する用途）。
    """

    def __init__(self, db_path: str = ":memory:", initialize_schema: bool = True):
        self.db_path = db_path if db_path == ":memory:" else str(Path(db_path))
        # ":memory:" は接続ごとに別 DB になってしまうため、単一接続を保持する
        self._shared_conn = sqlite3.connect(self.db_path) if self.db_path == ":memory:" else None
        if self._shared_conn is not None:
            self._shared_conn.row_factory = sqlite3.Row
        if initialize_schema:
            self.initialize_schema()

    def _get_connection(self):
        """DB接続を取得する内部メソッド"""
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _release(self, conn) -> None:
        """共有接続 (:memory:) は閉じない。ファイル接続のみ閉じる。"""
        if conn is not self._shared_conn:
            conn.close()

    def initialize_schema(self) -> None:
        """予約・部屋割り当て用のテーブルを作成する"""
        conn = self._get_connection()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._release(conn)

    def save(self, reservation: Reservation) -> None:
        """予約情報を保存・更新する (INSERT または UPDATE)"""
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO reservations
                (reservation_number, staying_date, guest_name, payment_amount, payment_status, reservation_status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(reservation_number) DO UPDATE SET
                    guest_name = excluded.guest_name,
                    payment_amount = excluded.payment_amount,
                    payment_status = excluded.payment_status,
                    reservation_status = excluded.reservation_status
                """,
                (
                    reservation.reservation_number,
                    reservation.staying_date.isoformat(),
                    reservation.guest.name,
                    reservation.payment.amount,
                    reservation.payment.status.value,
                    reservation.status.value,
                ),
            )

            conn.execute(
                "DELETE FROM reservation_rooms WHERE reservation_number = ?",
                (reservation.reservation_number,),
            )

            room_data = [(reservation.reservation_number, room.room_number) for room in reservation.rooms]
            if room_data:
                conn.executemany(
                    "INSERT INTO reservation_rooms (reservation_number, room_number) VALUES (?, ?)",
                    room_data,
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._release(conn)

    def find_by_id(self, reservation_number: int) -> Optional[Reservation]:
        """予約番号から予約情報を検索・復元する"""
        conn = self._get_connection()
        try:
            res_row = conn.execute(
                "SELECT * FROM reservations WHERE reservation_number = ?", (reservation_number,)
            ).fetchone()
            if not res_row:
                return None

            room_rows = conn.execute(
                "SELECT room_number FROM reservation_rooms WHERE reservation_number = ?", (reservation_number,)
            ).fetchall()
            return self._reconstruct_reservation(res_row, room_rows)
        finally:
            self._release(conn)

    def find_by_room_number(self, room_number: int) -> Optional[Reservation]:
        """部屋番号から現在滞在中の予約情報を検索・復元する"""
        conn = self._get_connection()
        try:
            res_row = conn.execute(
                """
                SELECT res.* FROM reservations res
                INNER JOIN reservation_rooms rr ON res.reservation_number = rr.reservation_number
                WHERE rr.room_number = ? AND res.reservation_status = ?
                """,
                (room_number, ReservationStatus.CHECKED_IN.value),
            ).fetchone()
            if not res_row:
                return None

            room_rows = conn.execute(
                "SELECT room_number FROM reservation_rooms WHERE reservation_number = ?",
                (res_row["reservation_number"],),
            ).fetchall()
            return self._reconstruct_reservation(res_row, room_rows)
        finally:
            self._release(conn)

    def find_active_reservations(self) -> List[Reservation]:
        """キャンセル以外の予約をすべて復元して返す（在庫復元用）"""
        conn = self._get_connection()
        try:
            res_rows = conn.execute(
                "SELECT * FROM reservations WHERE reservation_status != ?",
                (ReservationStatus.CANCELLED.value,),
            ).fetchall()

            reservations = []
            for res_row in res_rows:
                room_rows = conn.execute(
                    "SELECT room_number FROM reservation_rooms WHERE reservation_number = ?",
                    (res_row["reservation_number"],),
                ).fetchall()
                reservations.append(self._reconstruct_reservation(res_row, room_rows))
            return reservations
        finally:
            self._release(conn)

    def _reconstruct_reservation(self, res_row, room_rows) -> Reservation:
        """DBの取得結果からドメインオブジェクト(Entity)を再構築する内部ヘルパー"""
        guest = Guest(name=res_row["guest_name"])
        payment = Payment(
            amount=int(res_row["payment_amount"]),
            status=PaymentStatus(res_row["payment_status"]),
        )

        staying_date = self._parse_date(res_row["staying_date"])
        reservation_status = ReservationStatus(res_row["reservation_status"])

        rooms = []
        for r_row in room_rows:
            room = Room(room_number=int(r_row["room_number"]))
            room.assign(staying_date)
            if reservation_status == ReservationStatus.CHECKED_IN:
                room.mark_using()
            rooms.append(room)

        return Reservation(
            reservation_number=int(res_row["reservation_number"]),
            staying_date=staying_date,
            guest=guest,
            rooms=rooms,
            payment=payment,
            status=reservation_status,
        )

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d").date()
