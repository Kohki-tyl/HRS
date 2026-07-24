"""ChatInterface（LINE 予約対話の状態機械）のテスト

利用者の予約フロー（予約→日付→部屋選択→氏名→確認→確定）と、
初期ルーティング・入力バリデーション・中止を検証する。
"""
from datetime import date, timedelta

import pytest

from domain import Hotel, Room, RoomType
from application import ReservationControl
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
    return ChatInterface(res_ctrl, SessionManager()), repo


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


def test_cancel_keyword_resets(chat):
    ci, _ = chat
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    ci.handle_message(USER, "予約")
    ci.handle_message(USER, tomorrow)
    reply = ci.handle_message(USER, "キャンセル")
    assert "中断" in reply
    # リセット後、初期状態から予約を開始できる
    assert "宿泊希望日" in ci.handle_message(USER, "予約")


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
