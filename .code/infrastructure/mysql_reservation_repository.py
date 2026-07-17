import mysql.connector
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


class MySQLReservationRepository(ReservationRepository):
    """MySQLを使用して予約データを永続化するリポジトリの実装"""

    def __init__(self, db_config: dict, initialize_schema: bool = True):
        """データベース接続情報を辞書で受け取る"""
        self.db_config = db_config
        self._schema_path = Path(__file__).with_name("schema.sql")
        if initialize_schema:
            self.initialize_schema()

    def _get_connection(self):
        """DB接続を取得する内部メソッド"""
        return mysql.connector.connect(**self.db_config)

    def initialize_schema(self) -> None:
        """予約・部屋割り当て用のテーブルを作成する"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            schema_sql = self._schema_path.read_text(encoding="utf-8")
            for statement in [s.strip() for s in schema_sql.split(";") if s.strip()]:
                cursor.execute(statement)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def save(self, reservation: Reservation) -> None:
        """予約情報を保存・更新する (INSERT または UPDATE)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            sql_reservation = """
                INSERT INTO reservations
                (reservation_number, staying_date, guest_name, payment_amount, payment_status, reservation_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                guest_name = VALUES(guest_name),
                payment_amount = VALUES(payment_amount),
                payment_status = VALUES(payment_status),
                reservation_status = VALUES(reservation_status)
            """
            cursor.execute(
                sql_reservation,
                (
                    reservation.reservation_number,
                    reservation.staying_date,
                    reservation.guest.name,
                    reservation.payment.amount,
                    reservation.payment.status.value,
                    reservation.status.value,
                ),
            )

            cursor.execute(
                "DELETE FROM reservation_rooms WHERE reservation_number = %s",
                (reservation.reservation_number,),
            )

            sql_rooms = "INSERT INTO reservation_rooms (reservation_number, room_number) VALUES (%s, %s)"
            room_data = [(reservation.reservation_number, room.room_number) for room in reservation.rooms]
            if room_data:
                cursor.executemany(sql_rooms, room_data)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def find_by_id(self, reservation_number: int) -> Optional[Reservation]:
        """予約番号から予約情報を検索・復元する"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM reservations WHERE reservation_number = %s", (reservation_number,))
            res_row = cursor.fetchone()
            if not res_row:
                return None

            cursor.execute("SELECT room_number FROM reservation_rooms WHERE reservation_number = %s", (reservation_number,))
            room_rows = cursor.fetchall() or []
            return self._reconstruct_reservation(res_row, room_rows)
        finally:
            cursor.close()
            conn.close()

    def find_by_room_number(self, room_number: int) -> Optional[Reservation]:
        """部屋番号から現在滞在中の予約情報を検索・復元する"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT res.* FROM reservations res
                INNER JOIN reservation_rooms rr ON res.reservation_number = rr.reservation_number
                WHERE rr.room_number = %s AND res.reservation_status = %s
            """
            cursor.execute(sql, (room_number, ReservationStatus.CHECKED_IN.value))
            res_row = cursor.fetchone()
            if not res_row:
                return None

            cursor.execute("SELECT room_number FROM reservation_rooms WHERE reservation_number = %s", (res_row["reservation_number"],))
            room_rows = cursor.fetchall() or []
            return self._reconstruct_reservation(res_row, room_rows)
        finally:
            cursor.close()
            conn.close()

    def _reconstruct_reservation(self, res_row: dict, room_rows: List[dict]) -> Reservation:
        """DBの取得結果(辞書)からドメインオブジェクト(Entity)を再構築する内部ヘルパー"""
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
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        return datetime.strptime(str(value), "%Y-%m-%d").date()