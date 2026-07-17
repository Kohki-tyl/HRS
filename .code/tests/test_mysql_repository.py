from datetime import date

from domain import Guest, Payment, Reservation, Room
from infrastructure import MySQLReservationRepository


class DummyCursor:
    def __init__(self, reservation_row=None, room_rows=None):
        self.reservation_row = reservation_row
        self.room_rows = room_rows or []
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def executemany(self, query, params):
        self.executed.append((query, params))

    def fetchone(self):
        return self.reservation_row

    def fetchall(self):
        return self.room_rows

    def close(self):
        return None


class DummyConnection:
    def __init__(self, reservation_row=None, room_rows=None):
        self.cursor_obj = DummyCursor(reservation_row=reservation_row, room_rows=room_rows)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, dictionary=False):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        return None


def test_save_and_find_by_id():
    reservation_row = {
        "reservation_number": 1001,
        "staying_date": date(2026, 7, 1),
        "guest_name": "Taro",
        "payment_amount": 10000,
        "payment_status": "Pending",
        "reservation_status": "Created",
    }
    conn = DummyConnection(reservation_row=reservation_row, room_rows=[{"room_number": 101}])

    repo = MySQLReservationRepository({"host": "localhost", "database": "hrs_db"}, initialize_schema=False)
    repo._get_connection = lambda: conn

    reservation = Reservation(
        reservation_number=1001,
        staying_date=date(2026, 7, 1),
        guest=Guest(name="Taro"),
        rooms=[Room(room_number=101)],
        payment=Payment(amount=10000),
    )

    repo.save(reservation)
    loaded = repo.find_by_id(1001)

    assert loaded is not None
    assert loaded.reservation_number == 1001
    assert loaded.guest.name == "Taro"
    assert loaded.payment.amount == 10000
    assert loaded.rooms[0].room_number == 101
