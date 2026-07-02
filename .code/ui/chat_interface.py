from datetime import datetime
import random
from domain import BureaucraticError
from application import ReservationControl, CheckInControl, CheckOutControl
from .session_manager import SessionManager, SessionState

class ChatInterface:
    """LINEボットの対話管理とアプリケーション層へのルーティングを担うバウンダリ"""
    
    def __init__(
        self, 
        res_ctrl: ReservationControl, 
        ci_ctrl: CheckInControl, 
        co_ctrl: CheckOutControl,
        session_manager: SessionManager
    ):
        self.res_ctrl = res_ctrl
        self.ci_ctrl = ci_ctrl
        self.co_ctrl = co_ctrl
        self.session_manager = session_manager

    def handle_message(self, user_id: str, text: str) -> str:
        """LINEから受け取ったテキストを処理し、返信テキストを生成する"""
        session = self.session_manager.get_session(user_id)
        state = session["state"]

        try:
            # ==========================================
            # 1. 初期状態（機能のルーティング）
            # ==========================================
            if state == SessionState.INIT:
                if "予約" in text:
                    self.session_manager.update_state(user_id, SessionState.RES_AWAITING_DATE)
                    return "ご予約ですね。\n宿泊希望日を「YYYY-MM-DD」の形式で入力してください。\n（例: 2026-07-01）"
                
                elif "チェックイン" in text:
                    self.session_manager.update_state(user_id, SessionState.CI_AWAITING_RES_NUM)
                    return "チェックイン手続きを開始します。\n予約番号（数字）を入力してください。"
                
                elif "チェックアウト" in text:
                    self.session_manager.update_state(user_id, SessionState.CO_AWAITING_ROOM_NUM)
                    return "チェックアウト手続きを開始します。\nお部屋番号を入力してください。"
                
                else:
                    return "ご用件を「予約」「チェックイン」「チェックアウト」のいずれかで入力してください。"

            # ==========================================
            # 2. 予約フロー
            # ==========================================
            elif state == SessionState.RES_AWAITING_DATE:
                # 日付のパースと一時保存
                staying_date = datetime.strptime(text.strip(), "%Y-%m-%d").date()
                self.session_manager.update_context(user_id, "staying_date", staying_date)
                self.session_manager.update_state(user_id, SessionState.RES_AWAITING_COUNT)
                return f"{staying_date} ですね。\n希望する部屋数を数字で入力してください。"

            elif state == SessionState.RES_AWAITING_COUNT:
                count = int(text.strip())
                staying_date = session["context"]["staying_date"]
                
                # ここで初めて Application層 を呼び出し、空室を確認
                available_types = self.res_ctrl.search_room(staying_date, count)
                if not available_types:
                    self.session_manager.clear_session(user_id)
                    return "申し訳ありません。ご希望の日程・部屋数でご用意できる部屋がありません。最初からやり直してください。"
                
                self.session_manager.update_context(user_id, "count", count)
                self.session_manager.update_state(user_id, SessionState.RES_AWAITING_TYPE)
                
                type_names = [t.type_name for t in available_types]
                return f"以下の部屋タイプがご用意可能です。\n【 {', '.join(type_names)} 】\n\nご希望の部屋タイプを入力してください。"

            elif state == SessionState.RES_AWAITING_TYPE:
                type_name = text.strip()
                self.session_manager.update_context(user_id, "type_name", type_name)
                self.session_manager.update_state(user_id, SessionState.RES_AWAITING_NAME)
                return "ありがとうございます。\n最後にご予約者様のお名前を入力してください。"

            elif state == SessionState.RES_AWAITING_NAME:
                guest_name = text.strip()
                ctx = session["context"]
                
                # 予約番号の自動採番（実運用ではDBのシーケンス等を利用）
                res_num = random.randint(100000, 999999)
                
                # Application層 を呼び出し、予約を確定（DBへ保存）
                reservation = self.res_ctrl.reserve_room(
                    reservation_number=res_num,
                    staying_date=ctx["staying_date"],
                    guest_name=guest_name,
                    type_name=ctx["type_name"],
                    number_of_rooms=ctx["count"]
                )
                
                self.session_manager.clear_session(user_id)
                return f"ご予約が完了しました！\n\n予約番号: {reservation.reservation_number}\n宿泊料金: {reservation.get_amount()}円\n\n当日お待ちしております。"

            # ==========================================
            # 3. チェックインフロー
            # ==========================================
            elif state == SessionState.CI_AWAITING_RES_NUM:
                res_num = int(text.strip())
                # Application層 にチェックインを委譲
                assigned_rooms = self.ci_ctrl.check_in(res_num)
                self.session_manager.clear_session(user_id)
                return f"チェックインが完了しました。\nお部屋番号は【 {', '.join(map(str, assigned_rooms))} 】です。フロントにて鍵をお受け取りください。"

            # ==========================================
            # 4. チェックアウトフロー
            # ==========================================
            elif state == SessionState.CO_AWAITING_ROOM_NUM:
                room_num = int(text.strip())
                
                # 請求額計算のために情報を取得
                reservation = self.co_ctrl.search_information(room_num)
                if not reservation:
                    self.session_manager.clear_session(user_id)
                    return "該当するお部屋の滞在情報が見つかりません。フロントにお声がけください。"
                    
                amount = reservation.get_amount()
                
                # Application層 にチェックアウト（一括精算と空室化）を委譲
                self.co_ctrl.check_out(room_num)
                self.session_manager.clear_session(user_id)
                return f"チェックアウトが完了しました。\nご請求額は {amount}円 になります。ご利用誠にありがとうございました。"

        # ==========================================
        # エラーハンドリング
        # ==========================================
        except ValueError:
            return "入力形式が正しくありません。\n数字や指定された形式で入力してください。"
        except BureaucraticError as e:
            self.session_manager.clear_session(user_id)
            return f"手続きエラー: {str(e)}\n\n最初からやり直してください。"
        except Exception as e:
            self.session_manager.clear_session(user_id)
            return f"システムエラーが発生しました。\n最初からやり直してください。"