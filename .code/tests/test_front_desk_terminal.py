"""FrontDeskTerminal（受付係のフロント端末）のテスト

UC2/UC3 の「照会 → 確定」の流れと、異常系（該当なし・不正入力・状態不整合）を検証する。
"""
from datetime import date, timedelta

import pytest

from domain import Guest, Room, Payment, Reservation, ReservationStatus
from application import CheckInControl, CheckOutControl
from infrastructure import SQLiteReservationRepository
from ui import FrontDeskTerminal


@pytest.fixture
def front():
    repo = SQLiteReservationRepository(":memory:")
    terminal = FrontDeskTerminal(CheckInControl(repo), CheckOutControl(repo))
    return terminal, repo


def save_reservation(repo, number, staying_date, rooms, amount=10000,
                     status=ReservationStatus.CREATED):
    repo.save(Reservation(
        reservation_number=number,
        staying_date=staying_date,
        guest=Guest("早稲田太郎"),
        rooms=[Room(n) for n in rooms],
        payment=Payment(amount),
        status=status,
    ))


# ========== チェックイン (UC2) ==========

def test_checkin_search_then_confirm(front):
    terminal, repo = front
    save_reservation(repo, 100001, date.today(), [101, 201], amount=60000)

    detail = terminal.input_reservation_number("100001")
    assert "予約詳細" in detail
    assert "早稲田太郎" in detail
    assert "101, 201" in detail

    done = terminal.input_check_in("100001")
    assert "チェックインが完了" in done
    assert "101, 201" in done
    # 状態が CHECKED_IN になっている
    assert repo.find_by_id(100001).status == ReservationStatus.CHECKED_IN


def test_checkin_search_not_found(front):
    terminal, _ = front
    reply = terminal.input_reservation_number("999999")
    assert "【エラー】" in reply
    assert "見つかりません" in reply


def test_checkin_search_non_numeric(front):
    terminal, _ = front
    reply = terminal.input_reservation_number("abc")
    assert "【エラー】" in reply
    assert "数字" in reply


def test_checkin_search_rejects_non_today(front):
    terminal, repo = front
    tomorrow = date.today() + timedelta(days=1)
    save_reservation(repo, 100002, tomorrow, [101])
    reply = terminal.input_reservation_number("100002")
    assert "【エラー】" in reply
    assert "本日はチェックイン" in reply


def test_checkin_search_rejects_already_checked_in(front):
    terminal, repo = front
    save_reservation(repo, 100003, date.today(), [102], status=ReservationStatus.CHECKED_IN)
    reply = terminal.input_reservation_number("100003")
    assert "【エラー】" in reply
    assert "チェックイン済み" in reply


# ========== チェックアウト (UC3) ==========

def test_checkout_search_then_confirm(front):
    terminal, repo = front
    # チェックイン済み（宿泊中）の予約
    save_reservation(repo, 100004, date.today(), [101], amount=10000,
                     status=ReservationStatus.CHECKED_IN)

    info = terminal.input_room_number("101")
    assert "精算" in info
    assert "10000" in info

    done = terminal.input_check_out("101")
    assert "チェックアウトが完了" in done
    assert repo.find_by_id(100004).status == ReservationStatus.COMPLETED


def test_checkout_search_not_staying(front):
    terminal, repo = front
    # CREATED（未チェックイン）は滞在中ではない
    save_reservation(repo, 100005, date.today(), [201], status=ReservationStatus.CREATED)
    reply = terminal.input_room_number("201")
    assert "【エラー】" in reply
    assert "見つかりません" in reply


def test_checkout_confirm_without_stay(front):
    terminal, _ = front
    reply = terminal.input_check_out("999")
    assert "【エラー】" in reply
