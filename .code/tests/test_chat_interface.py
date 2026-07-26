"""ChatInterface（LINE 予約対話の状態機械）のテスト

利用者の予約フロー（予約→日付→部屋選択→氏名→確認→確定）と、
初期ルーティング・入力バリデーション・中止を検証する。
"""
from datetime import date, timedelta

import pytest

from domain import Hotel, Room, RoomType, ReservationStatus
from application import ReservationControl, CancelControl
from infrastructure import SQLiteReservationRepository
from ui import SessionManager, ChatInterface

USER = "U_test"


@pytest.fixture
def chat():
    hotel = Hotel("Test Hotel", room_types=[
        RoomType("Standard", 10000, rooms=[Room(101), Room(102)]),
        RoomType("Suite", 50000, rooms=[Room(201)]),
    ])
    repo = SQLiteReservationRepository(":memory:")
    res_ctrl = ReservationControl(repo, hotel)
    cancel_ctrl = CancelControl(repo)
    return ChatInterface(res_ctrl, cancel_ctrl, SessionManager()), repo


def test_full_reservation_flow(chat):
    ci, repo = chat
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    assert "予約" in ci.handle_message(USER, "予約")
    assert "空室状況" in ci.handle_message(USER, tomorrow)
    assert "お名前" in ci.handle_message(USER, "Standard 1, Suite 1")
    assert "承ります" in ci.handle_message(USER, "早稲田太郎")

    reply = ci.handle_message(USER, "はい")
    assert "予約が完了" in reply
    # 料金は 10000 + 50000
    assert "60000" in reply

    # リポジトリに保存されている
    saved = repo.find_all()
    assert len(saved) == 1
    assert saved[0].guest.name == "早稲田太郎"
    assert saved[0].get_amount() == 60000


def test_init_routing_checkin_guided_to_front(chat):
    ci, _ = chat
    reply = ci.handle_message(USER, "チェックイン")
    assert "フロント" in reply


def test_init_unknown_prompts_reservation(chat):
    ci, _ = chat
    assert "予約" in ci.handle_message(USER, "こんにちは")


def test_invalid_date_format_reprompts(chat):
    ci, _ = chat
    ci.handle_message(USER, "予約")
    reply = ci.handle_message(USER, "７月１日")
    assert "形式" in reply


def test_past_date_reprompts(chat):
    ci, _ = chat
    ci.handle_message(USER, "予約")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    reply = ci.handle_message(USER, yesterday)
    assert "過去" in reply


def test_room_selection_format_error(chat):
    ci, _ = chat
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    ci.handle_message(USER, "予約")
    ci.handle_message(USER, tomorrow)
    reply = ci.handle_message(USER, "スタンダードを1つ")
    assert "形式" in reply


def test_room_selection_options_follow_available_stock(chat):
    ci, _ = chat
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    ci.handle_message(USER, "予約")
    ci.handle_message(USER, tomorrow)

    assert ci.get_room_selection_options(USER) == [
        ("Standard", 1),
        ("Standard", 2),
        ("Suite", 1),
    ]


def test_cancel_keyword_resets(chat):
    ci, _ = chat
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    ci.handle_message(USER, "予約")
    ci.handle_message(USER, tomorrow)
    reply = ci.handle_message(USER, "キャンセル")
    assert "中断" in reply
    # リセット後、初期状態から予約を開始できる
    assert "宿泊日を選択" in ci.handle_message(USER, "予約")


def test_confirm_requires_affirmative(chat):
    ci, _ = chat
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    ci.handle_message(USER, "予約")
    ci.handle_message(USER, tomorrow)
    ci.handle_message(USER, "Standard 1")
    ci.handle_message(USER, "山田花子")
    # 「はい」以外では確定しない
    reply = ci.handle_message(USER, "うーん")
    assert "確定" in reply


# ========== キャンセルフロー (UC4) ==========

def _reserve_tomorrow(ci, user=USER):
    """USER が明日の予約を1件作成し、予約番号を返す"""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    ci.handle_message(user, "予約")
    ci.handle_message(user, tomorrow)
    ci.handle_message(user, "Standard 1")
    ci.handle_message(user, "山田太郎")
    reply = ci.handle_message(user, "はい")
    return int("".join(c for c in reply.split("予約番号: ")[1].split("\n")[0] if c.isdigit()))


def test_cancel_flow_success(chat):
    ci, repo = chat
    num = _reserve_tomorrow(ci)
    assert repo.find_by_id(num).status == ReservationStatus.CREATED

    assert "キャンセル" in ci.handle_message(USER, "予約キャンセル")
    reply = ci.handle_message(USER, str(num))
    assert "本人確認" in reply
    reply = ci.handle_message(USER, "山田太郎")
    assert "キャンセルします" in reply  # 確認プロンプト
    done = ci.handle_message(USER, "はい")
    assert "キャンセルしました" in done
    assert repo.find_by_id(num).status == ReservationStatus.CANCELLED


def test_cancel_rejects_other_user(chat):
    """他人（別の LINE userId）は本人の予約をキャンセルできない"""
    ci, repo = chat
    num = _reserve_tomorrow(ci)  # 予約者は USER

    ci.handle_message("U_other", "予約キャンセル")
    reply = ci.handle_message("U_other", str(num))
    assert "見つかりません" in reply
    # 予約は残っている
    assert repo.find_by_id(num).status == ReservationStatus.CREATED


def test_cancel_decline_keeps_reservation(chat):
    ci, repo = chat
    num = _reserve_tomorrow(ci)
    ci.handle_message(USER, "予約キャンセル")
    ci.handle_message(USER, str(num))
    ci.handle_message(USER, "山田太郎")
    reply = ci.handle_message(USER, "いいえ")
    assert "取りやめ" in reply
    assert repo.find_by_id(num).status == ReservationStatus.CREATED


def test_cancel_number_non_numeric(chat):
    ci, _ = chat
    ci.handle_message(USER, "予約キャンセル")
    assert "数字" in ci.handle_message(USER, "あ")


def test_cancel_not_found(chat):
    ci, _ = chat
    ci.handle_message(USER, "予約キャンセル")
    assert "見つかりません" in ci.handle_message(USER, "999999")


def test_confirmation_shows_total_amount(chat):
    ci, _ = chat
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    ci.handle_message(USER, "予約")
    ci.handle_message(USER, tomorrow)
    ci.handle_message(USER, "Standard 1, Suite 1")

    reply = ci.handle_message(USER, "山田太郎")

    assert "合計金額" in reply
    assert "60,000円" in reply


def test_reservation_confirmation_lists_only_requester(chat):
    ci, _ = chat
    own_number = _reserve_tomorrow(ci, USER)
    _reserve_tomorrow(ci, "U_other")

    reply = ci.handle_message(USER, "予約確認")

    assert str(own_number) in reply
    assert reply.count("予約番号:") == 1


def test_cancel_requires_matching_name(chat):
    ci, repo = chat
    num = _reserve_tomorrow(ci)
    ci.handle_message(USER, "予約キャンセル")
    assert "本人確認" in ci.handle_message(USER, str(num))

    reply = ci.handle_message(USER, "別人の名前")

    assert "一致しません" in reply
    assert repo.find_by_id(num).status == ReservationStatus.CREATED


def test_menu_command_switches_active_flow_without_double_confirmation(chat):
    ci, _ = chat
    ci.handle_message(USER, "予約キャンセル")

    reply = ci.handle_message(USER, "予約確認")

    assert "ご予約は見つかりません" in reply


def test_cancel_candidates_only_include_owned_cancellable_reservations(chat):
    ci, _ = chat
    own_number = _reserve_tomorrow(ci, USER)
    _reserve_tomorrow(ci, "U_other")

    candidates = ci.get_cancellable_reservations(USER)

    assert [reservation.reservation_number for reservation in candidates] == [own_number]
