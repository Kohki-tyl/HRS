"""在庫復元 (restore_hotel_stock) と find_active_reservations のテスト

再起動で在庫が失われ二重予約が起きる問題を、DB からの復元で防げることを
確認する。SQLite の1ファイルを共有することで「別プロセスでの再起動」を再現する。
"""
from datetime import date, timedelta

import pytest

from domain import Guest, Hotel, Payment, Reservation, Room, RoomType, ReservationStatus
from application import ReservationControl, CancelControl, restore_hotel_stock
from infrastructure import SQLiteReservationRepository


def build_hotel():
    return Hotel(hotel_name="Test Hotel", room_types=[
        RoomType(type_name="Standard", price=10000, rooms=[Room(101), Room(102)]),
        RoomType(type_name="Suite", price=50000, rooms=[Room(201)]),
    ])


@pytest.fixture
def db_path(tmp_path):
    # 複数の「起動」で共有するファイル DB
    return str(tmp_path / "hrs_test.db")


def test_find_active_reservations_excludes_cancelled(db_path):
    repo = SQLiteReservationRepository(db_path)
    repo.save(Reservation(1, date(2026, 7, 1), Guest("A"), [Room(101)], Payment(10000)))
    repo.save(Reservation(2, date(2026, 7, 2), Guest("B"), [Room(102)],
                          Payment(10000), status=ReservationStatus.CANCELLED))
    repo.save(Reservation(3, date(2026, 7, 3), Guest("C"), [Room(201)],
                          Payment(50000), status=ReservationStatus.COMPLETED))

    active = repo.find_active_reservations()

    numbers = sorted(r.reservation_number for r in active)
    assert numbers == [1, 3]  # CANCELLED の 2 は除外


def test_restore_marks_rooms_reserved(db_path):
    repo = SQLiteReservationRepository(db_path)
    repo.save(Reservation(1, date(2026, 7, 1), Guest("A"), [Room(101), Room(201)], Payment(60000)))

    hotel = build_hotel()
    # 復元前は空室
    assert hotel.find_room(101).is_vacant_on(date(2026, 7, 1))

    restored = restore_hotel_stock(hotel, repo)

    assert restored == 2
    assert not hotel.find_room(101).is_vacant_on(date(2026, 7, 1))
    assert not hotel.find_room(201).is_vacant_on(date(2026, 7, 1))
    # 別日はなお空室
    assert hotel.find_room(101).is_vacant_on(date(2026, 7, 2))


def test_restart_prevents_double_booking(db_path):
    """再起動しても同じ部屋・同じ日を二重予約できないこと（本命の回帰テスト）"""
    staying = date.today() + timedelta(days=3)

    # --- 1回目の起動: Suite(201) を予約 ---
    hotel1 = build_hotel()
    repo1 = SQLiteReservationRepository(db_path)
    restore_hotel_stock(hotel1, repo1)
    ctrl1 = ReservationControl(repo1, hotel1)
    ctrl1.reserve_rooms(staying, "早稲田太郎", {"Suite": 1})
    assert hotel1.get_room_type("Suite").get_available_count(staying) == 0

    # --- 2回目の起動: 新しい Hotel をメモリ上に組み直す（在庫は空に戻る）---
    hotel2 = build_hotel()
    repo2 = SQLiteReservationRepository(db_path)
    # 復元しなければ在庫が復活してしまう
    assert hotel2.get_room_type("Suite").get_available_count(staying) == 1
    # 復元すると押さえ済みになる
    restore_hotel_stock(hotel2, repo2)
    assert hotel2.get_room_type("Suite").get_available_count(staying) == 0

    # 二重予約は拒否される
    from domain import BureaucraticError
    ctrl2 = ReservationControl(repo2, hotel2)
    with pytest.raises(BureaucraticError):
        ctrl2.reserve_rooms(staying, "佐藤花子", {"Suite": 1})


def test_completed_stay_stays_reserved_after_restart(db_path):
    """チェックアウト済み (COMPLETED) の日は、再起動後もなお押さえられている"""
    # チェックインは宿泊日当日のみ可能なため、宿泊日は本日にする
    staying = date.today()
    repo = SQLiteReservationRepository(db_path)
    ctrl = ReservationControl(repo, build_hotel())

    # Suite を予約 → チェックイン → チェックアウト (COMPLETED)
    res = ctrl.reserve_rooms(staying, "早稲田太郎", {"Suite": 1})
    reservation = repo.find_by_id(res.reservation_number)
    reservation.mark_checked_in()
    reservation.check_out()
    repo.save(reservation)
    assert repo.find_by_id(res.reservation_number).status == ReservationStatus.COMPLETED

    # 再起動して復元 → その日はなお押さえられている（別の客に売れない）
    hotel2 = build_hotel()
    restore_hotel_stock(hotel2, SQLiteReservationRepository(db_path))
    assert hotel2.get_room_type("Suite").get_available_count(staying) == 0


def test_cancelled_reservation_releases_date_after_restart(db_path):
    """キャンセル (CANCELLED) した日は、再起動後の復元で解放される"""
    staying = date.today() + timedelta(days=3)
    repo = SQLiteReservationRepository(db_path)
    ctrl = ReservationControl(repo, build_hotel())

    res = ctrl.reserve_rooms(staying, "早稲田太郎", {"Suite": 1})
    CancelControl(repo).cancel(res.reservation_number)
    assert repo.find_by_id(res.reservation_number).status == ReservationStatus.CANCELLED

    # 再起動して復元 → キャンセル済みの日は空室に戻っている
    hotel2 = build_hotel()
    restore_hotel_stock(hotel2, SQLiteReservationRepository(db_path))
    assert hotel2.get_room_type("Suite").get_available_count(staying) == 1
