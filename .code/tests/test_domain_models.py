"""ドメイン層の単体テスト

設計の要である状態遷移のガード（Reservation の mark_checked_in / check_out /
cancel の不正遷移）と、空室判定（Room / RoomType の在庫ロジック）を直接検証する。
"""
from datetime import date, timedelta

import pytest

from domain import (
    Guest, Room, RoomType, Payment, Reservation,
    RoomStatus, ReservationStatus, PaymentStatus, BureaucraticError,
)


def make_reservation(status=ReservationStatus.CREATED, staying_date=None, rooms=None,
                     amount=10000, payment_status=PaymentStatus.PENDING):
    return Reservation(
        reservation_number=1,
        staying_date=staying_date or date.today(),
        guest=Guest("Taro"),
        rooms=rooms if rooms is not None else [Room(101)],
        payment=Payment(amount, payment_status),
        status=status,
    )


# ========== Reservation.mark_checked_in ==========

def test_mark_checked_in_success():
    res = make_reservation(staying_date=date.today(), rooms=[Room(101), Room(102)])
    res.mark_checked_in()
    assert res.status == ReservationStatus.CHECKED_IN
    assert all(room.status == RoomStatus.IN_USE for room in res.rooms)


@pytest.mark.parametrize("status", [
    ReservationStatus.CHECKED_IN, ReservationStatus.COMPLETED, ReservationStatus.CANCELLED,
])
def test_mark_checked_in_rejects_non_created(status):
    res = make_reservation(status=status, staying_date=date.today())
    with pytest.raises(BureaucraticError):
        res.mark_checked_in()


def test_mark_checked_in_rejects_non_today():
    res = make_reservation(staying_date=date.today() + timedelta(days=1))
    with pytest.raises(BureaucraticError):
        res.mark_checked_in()
    # 状態は変わらない
    assert res.status == ReservationStatus.CREATED


# ========== Reservation.check_out ==========

def test_check_out_success():
    res = make_reservation(status=ReservationStatus.CHECKED_IN,
                           rooms=[Room(101, status=RoomStatus.IN_USE)])
    res.check_out()
    assert res.status == ReservationStatus.COMPLETED
    assert res.payment.status == PaymentStatus.PAID
    assert all(room.status == RoomStatus.VACANT for room in res.rooms)


@pytest.mark.parametrize("status", [
    ReservationStatus.CREATED, ReservationStatus.COMPLETED, ReservationStatus.CANCELLED,
])
def test_check_out_rejects_not_checked_in(status):
    res = make_reservation(status=status)
    with pytest.raises(BureaucraticError):
        res.check_out()


# ========== Reservation.cancel ==========

def test_cancel_success():
    # キャンセルは前日まで可能。宿泊日を未来にする
    res = make_reservation(status=ReservationStatus.CREATED,
                           staying_date=date.today() + timedelta(days=2))
    res.cancel()
    assert res.status == ReservationStatus.CANCELLED
    # 確保していた部屋の該当日が解放されている
    assert all(room.is_vacant_on(res.staying_date) for room in res.rooms)


@pytest.mark.parametrize("status", [
    ReservationStatus.CHECKED_IN, ReservationStatus.COMPLETED, ReservationStatus.CANCELLED,
])
def test_cancel_rejects_non_created(status):
    res = make_reservation(status=status, staying_date=date.today() + timedelta(days=2))
    with pytest.raises(BureaucraticError):
        res.cancel()


def test_cancel_allowed_until_day_before():
    # 前日（宿泊日は明日）はキャンセル可能
    res = make_reservation(staying_date=date.today() + timedelta(days=1))
    res.cancel()
    assert res.status == ReservationStatus.CANCELLED


@pytest.mark.parametrize("staying_date", [date.today(), date.today() - timedelta(days=1)])
def test_cancel_rejects_on_or_after_staying_date(staying_date):
    # 宿泊日当日・過去は期限切れでキャンセル不可
    res = make_reservation(staying_date=staying_date)
    with pytest.raises(BureaucraticError):
        res.cancel()
    assert res.status == ReservationStatus.CREATED


# ========== Room の在庫・二重予約 ==========

def test_room_assign_and_double_booking():
    room = Room(101)
    d = date(2026, 7, 1)
    assert room.is_vacant_on(d)
    room.assign(d)
    assert not room.is_vacant_on(d)
    # 同一部屋・同一日は二重予約できない（Domain_Analysis の制約）
    with pytest.raises(BureaucraticError):
        room.assign(d)
    # 別日はなお空き
    assert room.is_vacant_on(date(2026, 7, 2))


def test_room_cancel_assign_releases_date():
    room = Room(101)
    d = date(2026, 7, 1)
    room.assign(d)
    room.cancel_assign(d)
    assert room.is_vacant_on(d)
    # 解放後は再度予約できる
    room.assign(d)
    assert not room.is_vacant_on(d)


# ========== RoomType.check_stock / 空室判定 ==========

def test_roomtype_check_stock_and_reduce():
    rt = RoomType("Standard", 10000, rooms=[Room(101), Room(102)])
    d = date(2026, 7, 1)
    assert rt.get_available_count(d) == 2
    assert rt.check_stock(2, d) is True
    assert rt.check_stock(3, d) is False

    assigned = rt.reduce_stock(1, d)
    assert len(assigned) == 1
    assert rt.get_available_count(d) == 1
    assert rt.check_stock(2, d) is False
    # 別日は影響を受けない
    assert rt.get_available_count(date(2026, 7, 2)) == 2


def test_roomtype_reduce_stock_insufficient():
    rt = RoomType("Suite", 50000, rooms=[Room(201)])
    d = date(2026, 7, 1)
    with pytest.raises(BureaucraticError):
        rt.reduce_stock(2, d)
    # 失敗時は在庫を減らさない
    assert rt.get_available_count(d) == 1


# ========== Hotel.allocate_rooms（複数タイプ一括・All or Nothing）==========

def test_hotel_allocate_rooms_all_or_nothing():
    hotel = _build_hotel()
    d = date(2026, 7, 1)
    # Standard 1 + Suite 2 → Suite が不足するため何も確保しない
    with pytest.raises(BureaucraticError):
        hotel.allocate_rooms(d, {"Standard": 1, "Suite": 2})
    assert hotel.get_room_type("Standard").get_available_count(d) == 2
    assert hotel.get_room_type("Suite").get_available_count(d) == 1


def test_hotel_allocate_rooms_success():
    hotel = _build_hotel()
    d = date(2026, 7, 1)
    rooms = hotel.allocate_rooms(d, {"Standard": 1, "Suite": 1})
    assert len(rooms) == 2
    assert hotel.get_room_type("Standard").get_available_count(d) == 1
    assert hotel.get_room_type("Suite").get_available_count(d) == 0


def _build_hotel():
    from domain import Hotel
    return Hotel("Test Hotel", room_types=[
        RoomType("Standard", 10000, rooms=[Room(101), Room(102)]),
        RoomType("Suite", 50000, rooms=[Room(201)]),
    ])
