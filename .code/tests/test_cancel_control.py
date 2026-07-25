"""CancelControl（予約キャンセル UC4）のテスト

本人確認（LINE userId 一致）と、ドメインのガード（状態・期限）が
コントロール経由で正しく効くことを検証する。
"""
from datetime import date, timedelta

import pytest

from domain import Guest, Room, Payment, Reservation, ReservationStatus, BureaucraticError
from application import CancelControl
from infrastructure import SQLiteReservationRepository

OWNER = "U_owner"
OTHER = "U_other"


@pytest.fixture
def repo():
    return SQLiteReservationRepository(":memory:")


def save_reservation(repo, number=100001, staying_date=None, line_user_id=OWNER,
                     status=ReservationStatus.CREATED, rooms=(101,)):
    repo.save(Reservation(
        reservation_number=number,
        staying_date=staying_date or (date.today() + timedelta(days=2)),
        guest=Guest("早稲田太郎", line_user_id=line_user_id),
        rooms=[Room(n) for n in rooms],
        payment=Payment(10000),
        status=status,
    ))


def test_owner_can_cancel(repo):
    save_reservation(repo, 100001)
    result = CancelControl(repo).cancel(100001, requester_user_id=OWNER)
    assert result.status == ReservationStatus.CANCELLED
    assert repo.find_by_id(100001).status == ReservationStatus.CANCELLED


def test_other_user_cannot_cancel(repo):
    save_reservation(repo, 100002, line_user_id=OWNER)
    with pytest.raises(BureaucraticError):
        CancelControl(repo).cancel(100002, requester_user_id=OTHER)
    # 予約は残っている
    assert repo.find_by_id(100002).status == ReservationStatus.CREATED


def test_search_hides_other_users_reservation(repo):
    save_reservation(repo, 100003, line_user_id=OWNER)
    cc = CancelControl(repo)
    assert cc.search_reservation(100003, requester_user_id=OWNER) is not None
    # 他人からは「見つからない」扱い（情報漏れ防止）
    assert cc.search_reservation(100003, requester_user_id=OTHER) is None


def test_cancel_not_found(repo):
    with pytest.raises(BureaucraticError):
        CancelControl(repo).cancel(999999, requester_user_id=OWNER)


def test_cannot_cancel_after_checkin(repo):
    save_reservation(repo, 100004, status=ReservationStatus.CHECKED_IN)
    with pytest.raises(BureaucraticError):
        CancelControl(repo).cancel(100004, requester_user_id=OWNER)


def test_cannot_cancel_on_staying_date(repo):
    # 宿泊日当日は期限切れ
    save_reservation(repo, 100005, staying_date=date.today())
    with pytest.raises(BureaucraticError):
        CancelControl(repo).cancel(100005, requester_user_id=OWNER)


def test_cancel_frees_stock(repo):
    """キャンセルすると、その宿泊日の予約から除外され在庫が戻る（DB引き）"""
    d = date.today() + timedelta(days=2)
    save_reservation(repo, 100006, staying_date=d, rooms=(201,))
    assert 100006 in {r.reservation_number for r in repo.find_by_staying_date(d)}

    CancelControl(repo).cancel(100006, requester_user_id=OWNER)
    # キャンセル後は find_by_staying_date に現れない
    assert 100006 not in {r.reservation_number for r in repo.find_by_staying_date(d)}
