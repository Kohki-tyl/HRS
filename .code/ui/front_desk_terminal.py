import logging

from domain import BureaucraticError, ReservationStatus
from application import CheckInControl, CheckOutControl

logger = logging.getLogger(__name__)

class FrontDeskTerminal:
    """受付係が操作するフロント端末のバウンダリ

    「チェックイン手続きを行う」(UC2)・「チェックアウト手続きを行う」(UC3) を担当する。
    利用者との対話ではなく受付係の1操作ごとに完結するため, SessionManager を介さず
    該当するコントロールを直接呼び出す。

    照会 (input_reservation_number / input_room_number) と確定 (input_check_in /
    input_check_out) を分離しているのは, 受付係が提示内容を利用者と確認したうえで
    確定操作を行うという業務手順 (UC2 基本系列 3-4, UC3 基本系列 3-6) に対応するため。
    """

    # 予約ステータスの表示名。ドメインの語彙を受付係向けの表示に変換するのは
    # バウンダリの責務であるため、対応表は UI 層に置く。
    STATUS_LABELS = {
        ReservationStatus.CREATED: "予約済み",
        ReservationStatus.CHECKED_IN: "チェックイン済み",
        ReservationStatus.COMPLETED: "チェックアウト済み",
        ReservationStatus.CANCELLED: "キャンセル済み",
    }

    def __init__(self, ci_ctrl: CheckInControl, co_ctrl: CheckOutControl):
        self.ci_ctrl = ci_ctrl
        self.co_ctrl = co_ctrl

    # ==========================================
    # 1. チェックイン (UC2)
    # ==========================================
    def input_reservation_number(self, text: str) -> str:
        """予約番号を照会し、受付係に提示する予約内容を返す"""
        try:
            reservation_number = self._parse_number(text)
        except ValueError:
            return self._notify_error("予約番号は数字で入力してください。")

        try:
            reservation = self.ci_ctrl.search_reservation(reservation_number)
        except Exception:
            logger.exception("予約照会中に予期しない例外が発生しました: reservation_number=%s", reservation_number)
            return self._notify_error("システムエラーが発生しました。")

        if not reservation:
            return self._notify_error(f"予約番号 {reservation_number} の予約が見つかりません。")

        if reservation.status != ReservationStatus.CREATED:
            return self._notify_error(
                f"この予約は現在「{self._status_label(reservation.status)}」のため、チェックインできません。"
            )

        return self._notify_reservation_detail(reservation)

    def input_check_in(self, text: str) -> str:
        """受付係の確定操作を受け、チェックインを実行して部屋番号を返す"""
        try:
            reservation_number = self._parse_number(text)
        except ValueError:
            return self._notify_error("予約番号は数字で入力してください。")

        try:
            room_numbers = self.ci_ctrl.check_in(reservation_number)
        except BureaucraticError as e:
            return self._notify_error(str(e))
        except Exception:
            logger.exception("チェックイン処理中に予期しない例外が発生しました: reservation_number=%s", reservation_number)
            return self._notify_error("システムエラーが発生しました。")

        return self._notify_room_number(room_numbers)

    # ==========================================
    # 2. チェックアウト (UC3)
    # ==========================================
    def input_room_number(self, text: str) -> str:
        """部屋番号から滞在情報を照会し、請求額を提示する"""
        try:
            room_number = self._parse_number(text)
        except ValueError:
            return self._notify_error("部屋番号は数字で入力してください。")

        try:
            reservation = self.co_ctrl.search_information(room_number)
        except Exception:
            logger.exception("滞在情報の照会中に予期しない例外が発生しました: room_number=%s", room_number)
            return self._notify_error("システムエラーが発生しました。")

        if not reservation:
            return self._notify_error(f"部屋番号 {room_number} に紐づく滞在中の予約が見つかりません。")

        return self._notify_price(reservation)

    def input_check_out(self, text: str) -> str:
        """支払い受領後の確定操作を受け、チェックアウト（一括精算・空室化）を実行する"""
        try:
            room_number = self._parse_number(text)
        except ValueError:
            return self._notify_error("部屋番号は数字で入力してください。")

        try:
            self.co_ctrl.check_out(room_number)
        except BureaucraticError as e:
            return self._notify_error(str(e))
        except Exception:
            logger.exception("チェックアウト処理中に予期しない例外が発生しました: room_number=%s", room_number)
            return self._notify_error("システムエラーが発生しました。")

        return self._notify_completion()

    def _parse_number(self, text: str) -> int:
        return int(text.strip())

    def _status_label(self, status: ReservationStatus) -> str:
        return self.STATUS_LABELS.get(status, status.value)

    # ==========================================
    # 3. 端末への表示テキストの生成 (notify_*)
    # ==========================================
    def _notify_reservation_detail(self, reservation) -> str:
        return (
            "--- 予約詳細 ---\n"
            f"ご予約者様: {reservation.guest.name} 様\n"
            f"ご宿泊日程: {reservation.staying_date}\n"
            f"予定お部屋: {', '.join(map(str, reservation.get_room_numbers()))}\n"
            "----------------\n"
            "内容を利用者様とご確認のうえ、チェックインを確定してください。"
        )

    def _notify_room_number(self, room_numbers) -> str:
        return (
            "チェックインが完了しました。\n"
            f"お部屋番号は【 {', '.join(map(str, room_numbers))} 】です。\n"
            "鍵と部屋番号を利用者様にお渡しください。"
        )

    def _notify_price(self, reservation) -> str:
        return (
            "--- チェックアウト精算 ---\n"
            f"ご宿泊者様: {reservation.guest.name} 様\n"
            f"ご利用お部屋: {', '.join(map(str, reservation.get_room_numbers()))}\n"
            f"ご請求額: {reservation.get_amount()} 円\n"
            "--------------------------\n"
            "料金をご請求のうえ、支払い受領後にチェックアウトを確定してください。"
        )

    def _notify_completion(self) -> str:
        return "チェックアウトが完了しました。\nご利用誠にありがとうございました。"

    def _notify_error(self, message: str) -> str:
        return f"【エラー】{message}"
