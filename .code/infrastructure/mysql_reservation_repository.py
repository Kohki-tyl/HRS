import mysql.connector
from typing import Optional, List
from datetime import date

# ドメイン層への依存（インターフェースとエンティティの読み込み）
from domain import (
    ReservationRepository,
    Reservation,
    Guest,
    Payment,
    Room,
    ReservationStatus,
    PaymentStatus
)

class MySQLReservationRepository(ReservationRepository):
    """MySQLを使用して予約データを永続化するリポジトリの実装"""

    def __init__(self, db_config: dict):
        """データベース接続情報を辞書で受け取る"""
        self.db_config = db_config

    def _get_connection(self):
        """DB接続を取得する内部メソッド"""
        return mysql.connector.connect(**self.db_config)

    def save(self, reservation: Reservation) -> None:
        """予約情報を保存・更新する (INSERT または UPDATE)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 1. 予約本体・決済・顧客情報の保存 (ON DUPLICATE KEY UPDATEで更新も兼ねる)
            sql_reservation = """
                INSERT INTO reservations 
                (reservation_number, staying_date, guest_name, payment_amount, payment_status, reservation_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                payment_status = VALUES(payment_status),
                reservation_status = VALUES(reservation_status)
            """
            cursor.execute(sql_reservation, (
                reservation.reservation_number,
                reservation.staying_date,
                reservation.guest.name,
                reservation.payment.amount,
                reservation.payment.status.value,
                reservation.status.value
            ))

            # 2. 紐づく部屋情報の保存 (一旦既存の紐づきを消して、現在のオブジェクトの状態で作り直す)
            cursor.execute("DELETE FROM reservation_rooms WHERE reservation_number = %s", (reservation.reservation_number,))
            
            sql_rooms = "INSERT INTO reservation_rooms (reservation_number, room_number) VALUES (%s, %s)"
            room_data = [(reservation.reservation_number, room.room_number) for room in reservation.rooms]
            cursor.executemany(sql_rooms, room_data)

            # トランザクションのコミット
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    def find_by_id(self, reservation_number: int) -> Optional[Reservation]:
        """予約番号から予約情報を検索・復元する"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # 予約情報の取得
            cursor.execute("SELECT * FROM reservations WHERE reservation_number = %s", (reservation_number,))
            res_row = cursor.fetchone()
            if not res_row:
                return None

            # 紐づく部屋情報の取得
            cursor.execute("SELECT room_number FROM reservation_rooms WHERE reservation_number = %s", (reservation_number,))
            room_rows = cursor.fetchall()

            return self._reconstruct_reservation(res_row, room_rows)

        finally:
            cursor.close()
            conn.close()

    def find_by_room_number(self, room_number: int) -> Optional[Reservation]:
        """部屋番号から現在滞在中の予約情報を検索・復元する"""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # 部屋番号から、チェックイン済みの予約を逆引きする
            sql = """
                SELECT res.* FROM reservations res
                INNER JOIN reservation_rooms rr ON res.reservation_number = rr.reservation_number
                WHERE rr.room_number = %s AND res.reservation_status = %s
            """
            # ステータスが "CheckedIn" のものを対象とする
            cursor.execute(sql, (room_number, ReservationStatus.CHECKED_IN.value))
            res_row = cursor.fetchone()
            
            if not res_row:
                return None

            # 紐づく全部屋（同グループで複数部屋取っている可能性があるため）の取得
            cursor.execute("SELECT room_number FROM reservation_rooms WHERE reservation_number = %s", (res_row['reservation_number'],))
            room_rows = cursor.fetchall()

            return self._reconstruct_reservation(res_row, room_rows)

        finally:
            cursor.close()
            conn.close()

    def _reconstruct_reservation(self, res_row: dict, room_rows: List[dict]) -> Reservation:
        """DBの取得結果(辞書)からドメインオブジェクト(Entity)を再構築する内部ヘルパー"""
        
        # ゲストと決済の復元
        guest = Guest(name=res_row['guest_name'])
        payment = Payment(
            amount=res_row['payment_amount'],
            status=PaymentStatus(res_row['payment_status'])
        )
        
        staying_date = res_row['staying_date']
        
        # 部屋オブジェクトの復元 (該当の宿泊日を予約済・利用中としてセット)
        rooms = []
        reservation_status = ReservationStatus(res_row['reservation_status'])
        
        for r_row in room_rows:
            room = Room(room_number=r_row['room_number'])
            room.assign(staying_date) # 予約されている日として登録
            if reservation_status == ReservationStatus.CHECKED_IN:
                room.mark_using(staying_date)
            rooms.append(room)

        # 予約オブジェクトの組み立て
        return Reservation(
            reservation_number=res_row['reservation_number'],
            staying_date=staying_date,
            guest=guest,
            rooms=rooms,
            payment=payment,
            status=reservation_status
        )