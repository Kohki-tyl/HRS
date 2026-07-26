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
    MENU_COMMANDS = ("予約", "予約確認", "予約キャンセル")
    RESERVATION_STATES = (
        SessionState.RES_AWAITING_DATE,
        SessionState.RES_AWAITING_ROOMS_SELECTION,
        SessionState.RES_AWAITING_NAME,
        SessionState.RES_AWAITING_CONFIRM,
    )

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
            # メニューボタンはどの状態からでも新しい機能へ切り替えられる。
            if text in self.MENU_COMMANDS and state != SessionState.INIT:
                self.session_manager.clear_session(user_id)
                return self._handle_init(user_id, text)

            # 「キャンセル」は予約入力中の中断だけに使う。予約キャンセル手続き内の
            # 「いいえ」と混同して二重確認にならないよう、対象状態を限定する。
            if text in self.RESTART_KEYWORDS and state != SessionState.INIT:
                self.session_manager.clear_session(user_id)
                return "手続きを中断しました。\n下のメニューから次の操作を選んでください。"

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
            elif state == SessionState.CANCEL_AWAITING_NAME:
                return self._handle_cancel_name(user_id, text)
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
        if text == "予約キャンセル":
            self.session_manager.update_state(user_id, SessionState.CANCEL_AWAITING_RES_NUM)
            return (
                "予約のキャンセルですね。\n"
                "下の一覧からキャンセルする予約を選んでください。\n"
                "予約番号（数字）を直接入力することもできます。"
            )

        if text == "予約確認":
            return self._notify_reservations(user_id)

        if text == "予約":
            self.session_manager.update_state(user_id, SessionState.RES_AWAITING_DATE)
            return (
                "ご予約ですね。\n"
                "下の「宿泊日を選択」から日付を選んでください。\n"
                "「YYYY-MM-DD」形式で直接入力することもできます。"
            )

        if "チェックイン" in text or "チェックアウト" in text:
            return (
                "チェックイン・チェックアウトの手続きは、フロントにて受付係が承ります。\n"
                "ご到着の際は、予約番号をフロントにお伝えください。"
            )

        return self.initial_guidance()

    def initial_guidance(self) -> str:
        return (
            "HRSホテル予約サービスへようこそ。\n\n"
            "・予約: 空室を検索して新しく予約します\n"
            "・予約確認: ご自身の予約を確認します\n"
            "・予約キャンセル: 予約を取り消します\n\n"
            "下のメニューからご希望の操作を選んでください。"
        )

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
        self.session_manager.update_context(user_id, "available_stocks", stocks)
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
        amount = self.res_ctrl.calculate_amount(ctx["requested_rooms"])
        return (
            "以下の内容でご予約を承ります。\n"
            f"宿泊日: {ctx['staying_date']}\n"
            f"お部屋: {rooms_text}\n"
            f"お名前: {ctx['guest_name']} 様\n"
            f"合計金額: {amount:,}円\n\n"
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
        self.session_manager.update_state(user_id, SessionState.CANCEL_AWAITING_NAME)
        return "本人確認のため、ご予約時のお名前を入力してください。"

    def _handle_cancel_name(self, user_id: str, text: str) -> str:
        ctx = self.session_manager.get_context(user_id)
        reservation = self.cancel_ctrl.search_reservation(ctx["cancel_number"], requester_user_id=user_id)
        if not reservation or not reservation.guest or reservation.guest.name.strip() != text.strip():
            self.session_manager.clear_session(user_id)
            return self._notify_error("予約番号またはお名前が一致しません。")

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
            "下のボタンから希望する部屋タイプと室数を選んでください。\n"
            "複数タイプを組み合わせる場合は、カンマ区切りで直接入力できます。\n"
            "（例: Standard 1, Suite 1）"
        )

    def _notify_reservation_number(self, reservation) -> str:
        return (
            "ご予約が完了しました！\n"
            f"予約番号: {reservation.reservation_number}\n"
            f"料金: {reservation.get_amount()}円\n\n"
            "ご到着の際は、フロントにて予約番号をお伝えください。"
        )

    def _notify_reservations(self, user_id: str) -> str:
        reservations = self.res_ctrl.find_reservations_by_line_user_id(user_id)
        if not reservations:
            return "ご予約は見つかりませんでした。\n新しい予約は下のメニューからお申し込みいただけます。"

        status_labels = {
            ReservationStatus.CREATED: "予約済み",
            ReservationStatus.CHECKED_IN: "チェックイン済み",
            ReservationStatus.COMPLETED: "チェックアウト済み",
            ReservationStatus.CANCELLED: "キャンセル済み",
        }
        details = []
        for reservation in reservations:
            rooms = ", ".join(map(str, reservation.get_room_numbers()))
            details.append(
                f"予約番号: {reservation.reservation_number}\n"
                f"宿泊日: {reservation.staying_date}\n"
                f"お部屋: {rooms}\n"
                f"料金: {reservation.get_amount():,}円\n"
                f"状態: {status_labels.get(reservation.status, reservation.status.value)}"
            )
        return "ご予約内容です。\n\n" + "\n\n".join(details)

    def get_cancellable_reservations(self, user_id: str):
        """キャンセル選択ボタンへ表示できる本人の予約を返す。"""
        return [
            reservation
            for reservation in self.res_ctrl.find_reservations_by_line_user_id(user_id)
            if reservation.status == ReservationStatus.CREATED
            and reservation.is_within_cancel_period()
        ]

    def get_room_selection_options(self, user_id: str) -> list[tuple[str, int]]:
        """空室数に応じた部屋タイプ・室数の選択肢を返す。"""
        stocks = self.session_manager.get_context(user_id).get("available_stocks", {})
        return [
            (type_name, count)
            for type_name, stock in stocks.items()
            for count in range(1, int(stock["count"]) + 1)
        ]

    def _notify_error(self, message: str) -> str:
        return f"{message}\n\n最初からやり直してください。"
