"""客のチャット（LINE ボット相当）をターミナルで動かすデバッグ用エントリーポイント

LINE Messaging API には接続せず、ターミナルの入力を Webhook のテキストに見立てて
ChatInterface へ渡す。scripts/startup/main.py の handle_message が行う処理と同じ。

    python -m scripts.debug.debug_chat
"""
import sys

from application import ReservationControl, CancelControl
from ui import SessionManager, ChatInterface
from scripts.debug.debug_setup import DB_PATH, build_hotel, build_repository

# LINE の userId に相当する識別子
DEBUG_USER_ID = "debug_line_user"


def main():
    hotel = build_hotel()
    repository = build_repository()
    # 空室状況はその都度 DB から判定する（DB引き）ため、起動時の在庫復元は不要

    res_ctrl = ReservationControl(repository, hotel)
    cancel_ctrl = CancelControl(repository)
    session_manager = SessionManager()
    chat_interface = ChatInterface(res_ctrl, cancel_ctrl, session_manager)

    print("=" * 60)
    print(" HRS 客用チャット（LINE ボット相当 / API 未接続）")
    print("=" * 60)
    print(f" DB      : {DB_PATH}")
    print(" 部屋    : Standard 101,102 (10000円) / Suite 201 (50000円)")
    print("-" * 60)
    print(" 「予約」と入力すると予約手続きが始まります。")
    print(" 終了するには Ctrl+C または「exit」と入力してください。")
    print("=" * 60)

    while True:
        try:
            text = input("\n[あなた] ")
        except (EOFError, KeyboardInterrupt):
            print("\nチャットを終了します。")
            return

        if text.strip().lower() in ("exit", "quit"):
            print("チャットを終了します。")
            return

        # scripts/startup/main.py の Webhook ハンドラと同じ呼び出し
        reply = chat_interface.handle_message(DEBUG_USER_ID, text)
        print(f"[BOT ] {reply}")


if __name__ == "__main__":
    sys.exit(main())
