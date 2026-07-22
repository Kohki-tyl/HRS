"""DB引き（空室状況を DB の予約から判定する）方式のテスト

在庫をメモリに持たず、その宿泊日の予約をリポジトリから引いて空室を求める。
そのため、Hotel を組み直した（＝再起動した）だけで在庫復元をしなくても
空室状況が正しく、二重予約が起きないことを確認する。
"""
from datetime import date, timedelta

import pytest

from domain import Hotel, Room, RoomType, ReservationStatus, BureaucraticError
from application import ReservationControl, CancelControl, CheckInControl, CheckOutControl
from infrastructure import SQLiteReservationRepository


def build_hotel():
    return Hotel(hotel_name="Test Hotel", room_types=[
        RoomType(type_name="Standard", price=10000, rooms=[Room(101), Room(102)]),
        RoomType(type_name="Suite", price=50000, rooms=[Room(201)]),
    ])


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "hrs_test.db")


def test_find_by_staying_date_filters_date_and_cancelled(db_path):
    repo = SQLiteReservationRepository(db_path)
    ctrl = ReservationControl(repo, build_hotel())
    d1 = date.today() + timedelta(days=1)
    d2 = date.today() + timedelta(days=2)

    r1 = ctrl.reserve_rooms(d1, "A", {"Standard": 1})
    ctrl.reserve_rooms(d2, "B", {"Standard": 1})
    # d1 の予約をキャンセル
    CancelControl(repo).cancel(r1.reservation_number)
    ctrl.reserve_rooms(d1, "C", {"Suite": 1})

    d1_active = repo.find_by_staying_date(d1)
    # d1 は キャンセルされた r1 を除き、C の Suite 予約のみ
    assert [r.guest.name for r in d1_active] == ["C"]
    # d2 は B のみ
    assert [r.guest.name for r in repo.find_by_staying_date(d2)] == ["B"]


def test_available_stock_reflects_db(db_path):
    repo = SQLiteReservationRepository(db_path)
    ctrl = ReservationControl(repo, build_hotel())
    d = date.today() + timedelta(days=1)

    # 初期: Standard 2, Suite 1
    stocks = ctrl.get_available_stocks(d)
    assert stocks["Standard"]["count"] == 2
    assert stocks["Suite"]["count"] == 1

    # Suite を1室予約 → Suite は満室で一覧から消える
    ctrl.reserve_rooms(d, "早稲田太郎", {"Suite": 1})
    stocks = ctrl.get_available_stocks(d)
    assert "Suite" not in stocks
    assert stocks["Standard"]["count"] == 2


def test_availability_survives_restart_without_restore(db_path):
    """Hotel を組み直しても（再起動）、在庫復元なしで空室状況が正しいこと（本命）"""
    d = date.today() + timedelta(days=1)

    # 1回目: Suite を予約
    ctrl1 = ReservationControl(SQLiteReservationRepository(db_path), build_hotel())
    ctrl1.reserve_rooms(d, "早稲田太郎", {"Suite": 1})

    # 2回目: まっさらな Hotel と 新しいリポジトリ接続（在庫復元は一切しない）
    ctrl2 = ReservationControl(SQLiteReservationRepository(db_path), build_hotel())
    stocks = ctrl2.get_available_stocks(d)
    assert "Suite" not in stocks  # DB から判定するので満室のまま

    # 二重予約は拒否される
    with pytest.raises(BureaucraticError):
        ctrl2.reserve_rooms(d, "佐藤花子", {"Suite": 1})


def test_cancel_frees_stock(db_path):
    repo = SQLiteReservationRepository(db_path)
    ctrl = ReservationControl(repo, build_hotel())
    d = date.today() + timedelta(days=1)

    res = ctrl.reserve_rooms(d, "早稲田太郎", {"Suite": 1})
    assert "Suite" not in ctrl.get_available_stocks(d)

    CancelControl(repo).cancel(res.reservation_number)
    # キャンセルすると Suite が空室に戻る
    assert ctrl.get_available_stocks(d)["Suite"]["count"] == 1


def test_completed_stay_still_blocks_same_day(db_path):
    """チェックアウト済み(COMPLETED)でも、その日の同じ部屋は再予約できない"""
    repo = SQLiteReservationRepository(db_path)
    ctrl = ReservationControl(repo, build_hotel())
    today = date.today()

    res = ctrl.reserve_rooms(today, "早稲田太郎", {"Suite": 1})
    reservation = repo.find_by_id(res.reservation_number)
    reservation.mark_checked_in()
    reservation.check_out()
    repo.save(reservation)
    assert repo.find_by_id(res.reservation_number).status == ReservationStatus.COMPLETED

    # COMPLETED は非キャンセルなので、その日の Suite はなお満室
    assert "Suite" not in ctrl.get_available_stocks(today)


def test_all_or_nothing_allocation(db_path):
    """複数タイプ要求で一部でも不足なら、何も確保しない（All or Nothing）"""
    repo = SQLiteReservationRepository(db_path)
    ctrl = ReservationControl(repo, build_hotel())
    d = date.today() + timedelta(days=1)

    # Standard 1 + Suite 2 (Suite は1室しかない) → 失敗
    with pytest.raises(BureaucraticError):
        ctrl.reserve_rooms(d, "早稲田太郎", {"Standard": 1, "Suite": 2})

    # 失敗後、在庫は一切減っていない
    stocks = ctrl.get_available_stocks(d)
    assert stocks["Standard"]["count"] == 2
    assert stocks["Suite"]["count"] == 1
