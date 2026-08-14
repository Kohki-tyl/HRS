"""SQLiteReservationRepository のテスト

実際に SQL を発行して保存・検索・復元の振る舞いを検証する。
"""
import sqlite3
from datetime import date

import pytest

from domain import (
    Guest, Payment, Reservation, Room,
    ReservationStatus, PaymentStatus, RoomStatus,
)
from infrastructure import SQLiteReservationRepository


def make_reservation(
    number=1001,
    staying_date=date(2026, 7, 1),
    guest_name="Taro",
    room_numbers=(101,),
    amount=10000,
    status=ReservationStatus.CREATED,
    payment_status=PaymentStatus.PENDING,
):
    return Reservation(
        reservation_number=number,
        staying_date=staying_date,
        guest=Guest(name=guest_name),
        rooms=[Room(room_number=n) for n in room_numbers],
        payment=Payment(amount=amount, status=payment_status),
        status=status,
    )


@pytest.fixture
def repo():
    # 接続限りのインメモリ DB。テストごとに新しく作られる。
    return SQLiteReservationRepository(":memory:")


def test_save_then_find_by_id_roundtrips_all_fields(repo):
    repo.save(make_reservation(room_numbers=(101, 201), amount=60000, guest_name="早稲田太郎"))

    loaded = repo.find_by_id(1001)

    assert loaded is not None
    assert loaded.reservation_number == 1001
    assert loaded.staying_date == date(2026, 7, 1)
    assert loaded.guest.name == "早稲田太郎"
    assert loaded.get_amount() == 60000
    assert loaded.status == ReservationStatus.CREATED
    assert loaded.payment.status == PaymentStatus.PENDING
    assert sorted(loaded.get_room_numbers()) == [101, 201]


def test_find_by_id_returns_none_when_absent(repo):
    assert repo.find_by_id(999999) is None


def test_save_updates_existing_reservation(repo):
    repo.save(make_reservation())

    # チェックイン相当の状態遷移を保存し直す
    updated = make_reservation(status=ReservationStatus.CHECKED_IN)
    repo.save(updated)

    loaded = repo.find_by_id(1001)
    assert loaded.status == ReservationStatus.CHECKED_IN
    # 重複して行が増えていないこと
    assert sorted(loaded.get_room_numbers()) == [101]


def test_find_by_room_number_only_returns_checked_in(repo):
    # CREATED のうちは部屋番号で引いても滞在中とはみなさない
    repo.save(make_reservation(status=ReservationStatus.CREATED))
    assert repo.find_by_room_number(101) is None

    repo.save(make_reservation(status=ReservationStatus.CHECKED_IN))
    found = repo.find_by_room_number(101)
    assert found is not None
    assert found.reservation_number == 1001


def test_find_by_room_number_reconstructs_rooms_as_in_use(repo):
    repo.save(make_reservation(room_numbers=(101, 201), status=ReservationStatus.CHECKED_IN))

    found = repo.find_by_room_number(201)

    assert found is not None
    assert sorted(found.get_room_numbers()) == [101, 201]
    # CHECKED_IN の復元では Room が IN_USE になっている
    assert all(room.status == RoomStatus.IN_USE for room in found.rooms)


def test_find_by_room_number_none_after_checkout(repo):
    repo.save(make_reservation(
        status=ReservationStatus.COMPLETED,
        payment_status=PaymentStatus.PAID,
    ))
    assert repo.find_by_room_number(101) is None


# ========== 既存 DB のマイグレーション（guest_line_user_id 列の追加）==========

def test_migration_adds_guest_line_user_id_column(tmp_path):
    """列導入前の旧スキーマ DB に対し、初期化時に列が追加され、旧予約は所有者 NULL になる"""
    db = str(tmp_path / "old.db")

    # 旧スキーマ（guest_line_user_id 列なし）を手動で作成し、旧予約を1件入れる
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE reservations (
            reservation_number INTEGER PRIMARY KEY,
            staying_date TEXT NOT NULL,
            guest_name TEXT NOT NULL,
            payment_amount INTEGER NOT NULL,
            payment_status TEXT NOT NULL,
            reservation_status TEXT NOT NULL
        );
        CREATE TABLE reservation_rooms (
            reservation_number INTEGER NOT NULL,
            room_number INTEGER NOT NULL,
            PRIMARY KEY (reservation_number, room_number)
        );
        """
    )
    conn.execute(
        "INSERT INTO reservations VALUES (?, ?, ?, ?, ?, ?)",
        (500001, "2026-07-01", "旧太郎", 10000, "Pending", "Created"),
    )
    conn.execute("INSERT INTO reservation_rooms VALUES (?, ?)", (500001, 101))
    conn.commit()
    conn.close()

    # リポジトリ生成時のスキーマ初期化でマイグレーションが走る
    repo = SQLiteReservationRepository(db)

    # 列が追加されている
    check = sqlite3.connect(db)
    cols = [r[1] for r in check.execute("PRAGMA table_info(reservations)").fetchall()]
    check.close()
    assert "guest_line_user_id" in cols

    # 旧予約は所有者 NULL（= LINE セルフキャンセル対象外）として復元される
    loaded = repo.find_by_id(500001)
    assert loaded is not None
    assert loaded.guest.name == "旧太郎"
    assert loaded.guest.line_user_id is None
