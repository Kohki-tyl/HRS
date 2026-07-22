"""フロント端末（受付係の操作）をターミナルで動かすデバッグ用エントリーポイント

FrontDeskTerminal を直接呼ぶ。照会 → 利用者と確認 → 確定 という
UC2 / UC3 の手順をそのまま辿る。

    python debug_front.py
"""
import sys

from application import CheckInControl, CheckOutControl
from ui import FrontDeskTerminal
from debug_setup import DB_PATH, build_repository


def _confirm(prompt: str) -> bool:
    return input(prompt).strip().lower() in ("y", "yes", "はい")


def handle_check_in(front: FrontDeskTerminal) -> None:
    """UC2: チェックイン手続き"""
    reservation_number = input("予約番号を入力: ")

    # 1. 照会して予約内容を提示する
    print()
    print(front.input_reservation_number(reservation_number))

    # 2. 受付係が利用者と内容を確認し、確定する
    if not _confirm("\n上記の内容でチェックインを確定しますか？ (y/n): "):
        print("手続きを中断しました。")
        return

    print()
    print(front.input_check_in(reservation_number))


def handle_check_out(front: FrontDeskTerminal) -> None:
    """UC3: チェックアウト手続き"""
    room_number = input("部屋番号を入力: ")

    # 1. 照会して請求額を提示する
    print()
    print(front.input_room_number(room_number))

    # 2. 料金を請求し、支払いを受け取ってから確定する
    if not _confirm("\n支払いを受け取り、チェックアウトを確定しますか？ (y/n): "):
        print("手続きを中断しました。")
        return

    print()
    print(front.input_check_out(room_number))


def main():
    repository = build_repository()
    front = FrontDeskTerminal(CheckInControl(repository), CheckOutControl(repository))

    print("=" * 60)
    print(" HRS フロント端末（受付係用 / API 未接続）")
    print("=" * 60)
    print(f" DB: {DB_PATH}")
    print("=" * 60)

    actions = {"1": handle_check_in, "2": handle_check_out}

    while True:
        print("\n[操作を選択] 1:チェックイン  2:チェックアウト  0:終了")
        try:
            choice = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nフロント端末を終了します。")
            return

        if choice == "0":
            print("フロント端末を終了します。")
            return

        action = actions.get(choice)
        if not action:
            print("無効な入力です。")
            continue

        try:
            action(front)
        except (EOFError, KeyboardInterrupt):
            print("\nフロント端末を終了します。")
            return


if __name__ == "__main__":
    sys.exit(main())
