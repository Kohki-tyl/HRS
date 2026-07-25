from datetime import datetime
import hashlib
import logging

from domain import BureaucraticError, ReservationStatus
from application import ReservationControl, CancelControl
from .session_manager import SessionManager, SessionState

logger = logging.getLogger(__name__)


def _mask_user_id(user_id: str) -> str:
    """LINE userId をログへ全文出力しないためのマスク表現を返す。

    個人を直接特定できないよう, SHA-256 の先頭のみを用いる。ログ間の突き合わせ
    (同一ユーザの追跡) はできるが, 元の userId は復元できない。
    """
    if not user_id:
        return "(none)"
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return f"uid:{digest[:8]}"

class ChatInterface:
    """LINEボットの対話管理とアプリケーション層へのルーティングを担うバウンダリ

    担当は利用者による「部屋を予約する」(UC1) のみ。チェックイン・チェックアウトは
    受付係がフロント端末 (FrontDeskTerminal) で行うため, ここでは受け付けない。
    """

    # 手続きを最初からやり直すためのキーワード
    RESTART_KEYWORDS = ("キャンセル", "中止", "やめる", "やり直し")
    # 確定を表す入力
    AFFIRMATIVE_WORDS = ("はい", "確定", "ok", "yes", "y")

    def __init__(
        self,
        res_ctrl: ReservationControl,
        cancel_ctrl: CancelControl,
        session_manager: SessionManager
    ):
        self.res_ctrl = res_ctrl
        self.cancel_ctrl = cancel_ctrl
        self.session_manager = session_manager

    def handle_message(self, user_id: str, text: str) -> str:
        """LINEから受け取ったテキストを処理し、返信テキストを生成する"""
        text = text.strip()
        state = self.session_manager.get_state(user_id)

        try:
            if text in self.RESTART_KEYWORDS and state != SessionState.INIT:
                self.session_manager.clear_session(user_id)
                return "手続きを中断しました。\n最初からやり直す場合は「予約」または「予約キャンセル」と入力してください。"

            if state == SessionState.INIT:
                return self._handle_init(user_id, text)
            elif state == SessionState.RES_AWAITING_DATE:
                return self._handle_date(user_id, text)
            elif state == SessionState.RES_AWAITING_ROOMS_SELECTION:
                return self._handle_rooms_selection(user_id, text)
            elif state == SessionState.RES_AWAITING_NAME:
                return self._handle_name(user_id, text)
            elif state == SessionState.RES_AWAITING_CONFIRM:
                return self._handle_confirm(user_id, text)
            elif state == SessionState.CANCEL_AWAITING_RES_NUM:
                return self._handle_cancel_number(user_id, text)
            elif state == SessionState.CANCEL_AWAITING_CONFIRM:
                return self._handle_cancel_confirm(user_id, text)
            else:
                # 未知の状態に陥った場合はセッションを捨てて案内に戻す
                logger.warning("未知のセッション状態です: user=%s, state=%s", _mask_user_id(user_id), state)
                self.session_manager.clear_session(user_id)
                return self._notify_error("セッションが不正な状態になりました。最初からやり直してください。")

        except BureaucraticError as e:
            self.session_manager.clear_session(user_id)
            return self._notify_error(str(e))
        except Exception:
            logger.exception("予約対話の処理中に予期しない例外が発生しました: user=%s", _mask_user_id(user_id))
            self.session_manager.clear_session(user_id)
            return self._notify_error("システムエラーが発生しました。")

    # ==========================================
    # 1. 初期状態（機能のルーティング）
    # ==========================================
    def _handle_init(self, user_id: str, text: str) -> str:
        # 「予約キャンセル」なども拾えるよう、キャンセルを予約より先に判定する
        if "キャンセル" in text:
            self.session_manager.update_state(user_id, SessionState.CANCEL_AWAITING_RES_NUM)
            return (
                "予約のキャンセルですね。\n"
                "キャンセルする予約番号（数字）を入力してください。"
            )

        if "予約" in text:
            self.session_manager.update_state(user_id, SessionState.RES_AWAITING_DATE)
            return (
                "ご予約ですね。\n"
                "宿泊希望日を「YYYY-MM-DD」の形式で入力してください。\n"
                "（例: 2026-07-01）"
            )

        if "チェックイン" in text or "チェックアウト" in text:
            return (
                "チェックイン・チェックアウトの手続きは、フロントにて受付係が承ります。\n"
                "ご到着の際は、予約番号をフロントにお伝えください。"
            )

        return "ご用件を「予約」または「予約キャンセル」と入力してください。"

    # ==========================================
    # 2. 予約フロー (UC1)
    # ==========================================
    def _handle_date(self, user_id: str, text: str) -> str:
        try:
            staying_date = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return "日付の形式が正しくありません。\n「YYYY-MM-DD」の形式で入力してください。（例: 2026-07-01）"

        try:
            stocks = self.res_ctrl.get_available_stocks(staying_date)
        except BureaucraticError as e:
            # 過去日など: 宿泊日の入力からやり直す（UC1 代替系列）
            return f"{e}\n宿泊希望日を入力し直してください。"

        if not stocks:
            return (
                "申し訳ありません。ご希望の日程でご用意できる部屋がありません。\n"
                "別の宿泊希望日を入力してください。"
            )

        self.session_manager.update_context(user_id, "staying_date", staying_date)
        self.session_manager.update_state(user_id, SessionState.RES_AWAITING_ROOMS_SELECTION)
        return self._notify_room_detail(staying_date, stocks)

    def _handle_rooms_selection(self, user_id: str, text: str) -> str:
        try:
            requested_rooms = self._parse_requested_rooms(text)
        except ValueError:
            return "形式が正しくありません。「Standard 1, Suite 1」のように入力してください。"

        self.session_manager.update_context(user_id, "requested_rooms", requested_rooms)
        self.session_manager.update_state(user_id, SessionState.RES_AWAITING_NAME)
        return "ありがとうございます。\nご予約者様のお名前を入力してください。"

    def _handle_name(self, user_id: str, text: str) -> str:
        if not text:
            return "お名前が入力されていません。ご予約者様のお名前を入力してください。"

        self.session_manager.update_context(user_id, "guest_name", text)
        self.session_manager.update_state(user_id, SessionState.RES_AWAITING_CONFIRM)

        ctx = self.session_manager.get_context(user_id)
        rooms_text = "、".join(f"{name} {count}室" for name, count in ctx["requested_rooms"].items())
        return (
            "以下の内容でご予約を承ります。\n"
            f"宿泊日: {ctx['staying_date']}\n"
            f"お部屋: {rooms_text}\n"
            f"お名前: {ctx['guest_name']} 様\n\n"
            "よろしければ「はい」、取り消す場合は「キャンセル」と入力してください。"
        )

    def _handle_confirm(self, user_id: str, text: str) -> str:
        if text.lower() not in self.AFFIRMATIVE_WORDS:
            return "ご予約を確定する場合は「はい」、取り消す場合は「キャンセル」と入力してください。"

        ctx = self.session_manager.get_context(user_id)
        # 在庫不足など (対話中に空室状況が変わった場合) は BureaucraticError となり、
        # handle_message 側で捕捉される。
        reservation = self.res_ctrl.reserve_rooms(
            staying_date=ctx["staying_date"],
            guest_name=ctx["guest_name"],
            requested_rooms=ctx["requested_rooms"],
            line_user_id=user_id,
        )

        self.session_manager.clear_session(user_id)
        return self._notify_reservation_number(reservation)

    # ==========================================
    # 2b. キャンセルフロー (UC4)
    # ==========================================
    def _handle_cancel_number(self, user_id: str, text: str) -> str:
        try:
            reservation_number = int(text)
        except ValueError:
            return "予約番号は数字で入力してください。"

        # 本人の予約のみ照会できる（他人の予約は「見つからない」と同じ扱い）
        reservation = self.cancel_ctrl.search_reservation(reservation_number, requester_user_id=user_id)
        if not reservation:
            self.session_manager.clear_session(user_id)
            return self._notify_error("該当する予約が見つかりません。予約番号をご確認ください。")

        # 確認を求める前に、キャンセル可能かを判定して案内する
        if reservation.status != ReservationStatus.CREATED:
            self.session_manager.clear_session(user_id)
            return self._notify_error("この予約はキャンセルできません（すでに手続き済み、またはキャンセル済みです）。")
        if not reservation.is_within_cancel_period():
            self.session_manager.clear_session(user_id)
            return self._notify_error("キャンセルはチェックインの前日までです。期限を過ぎています。")

        self.session_manager.update_context(user_id, "cancel_number", reservation_number)
        self.session_manager.update_state(user_id, SessionState.CANCEL_AWAITING_CONFIRM)
        rooms_text = ", ".join(map(str, reservation.get_room_numbers()))
        return (
            "以下の予約をキャンセルします。\n"
            f"予約番号: {reservation.reservation_number}\n"
            f"宿泊日: {reservation.staying_date}\n"
            f"お部屋: {rooms_text}\n"
            f"料金: {reservation.get_amount()}円\n\n"
            "よろしければ「はい」、やめる場合は「いいえ」と入力してください。"
        )

    def _handle_cancel_confirm(self, user_id: str, text: str) -> str:
        if text.lower() not in self.AFFIRMATIVE_WORDS:
            self.session_manager.clear_session(user_id)
            return "キャンセルを取りやめました。\nご用件があれば改めて入力してください。"

        ctx = self.session_manager.get_context(user_id)
        # 本人確認・状態・期限は cancel 側で再度検査される（BureaucraticError は handle_message で捕捉）
        reservation = self.cancel_ctrl.cancel(ctx["cancel_number"], requester_user_id=user_id)

        self.session_manager.clear_session(user_id)
        return (
            "予約をキャンセルしました。\n"
            f"予約番号: {reservation.reservation_number}\n"
            "ご利用ありがとうございました。"
        )

    def _parse_requested_rooms(self, text: str) -> dict[str, int]:
        """「Standard 1, Suite 1」形式のテキストを {type_name: count} に変換する"""
        requested_rooms: dict[str, int] = {}
        for part in text.split(","):
            name, count_str = part.strip().split()
            requested_rooms[name] = int(count_str)
        if not requested_rooms:
            raise ValueError("部屋が指定されていません。")
        return requested_rooms

    # ==========================================
    # 3. 応答メッセージの生成 (notify_*)
    # ==========================================
    def _notify_room_detail(self, staying_date, stocks: dict[str, dict]) -> str:
        stock_text = "\n".join(
            f"・{name}: 残り {stock['count']} 室（1室 {stock['price']}円）"
            for name, stock in stocks.items()
        )
        return (
            f"{staying_date} の空室状況です。\n{stock_text}\n\n"
            "希望する部屋と数をカンマ区切りで入力してください。\n"
            "（例: Standard 1, Suite 1）"
        )

    def _notify_reservation_number(self, reservation) -> str:
        return (
            "ご予約が完了しました！\n"
            f"予約番号: {reservation.reservation_number}\n"
            f"料金: {reservation.get_amount()}円\n\n"
            "ご到着の際は、フロントにて予約番号をお伝えください。"
        )

    def _notify_error(self, message: str) -> str:
        return f"{message}\n\n最初からやり直してください。"
