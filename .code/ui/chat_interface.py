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
                staying_date = datetime.strptime(text.strip(), "%Y-%m-%d").date()
                
                # 日付をもとに空室状況を取得
                stocks = self.res_ctrl.get_available_stocks(staying_date)
                if not stocks:
                    self.session_manager.clear_session(user_id)
                    return "申し訳ありません。ご希望の日程でご用意できる部屋がありません。"
                
                self.session_manager.update_context(user_id, "staying_date", staying_date)
                self.session_manager.update_state(user_id, SessionState.RES_AWAITING_ROOMS_SELECTION)
                
                # 空室状況のテキスト生成
                stock_text = "\n".join([f"・{name}: 残り {cnt} 室" for name, cnt in stocks.items()])
                return (
                    f"{staying_date} の空室状況です。\n{stock_text}\n\n"
                    "希望する部屋と数をカンマ区切りで入力してください。\n"
                    "（例: Standard 1, Suite 1）"
                )

            elif state == SessionState.RES_AWAITING_ROOMS_SELECTION:
                # 入力テキスト例: "Standard 1, Suite 1" を辞書に変換する
                requested_rooms = {}
                try:
                    parts = text.split(",")
                    for part in parts:
                        name, count_str = part.strip().split()
                        requested_rooms[name] = int(count_str)
                except Exception:
                    return "形式が正しくありません。「Standard 1, Suite 1」のように入力してください。"
                
                self.session_manager.update_context(user_id, "requested_rooms", requested_rooms)
                self.session_manager.update_state(user_id, SessionState.RES_AWAITING_NAME)
                return "ありがとうございます。\n最後にご予約者様のお名前を入力してください。"

            elif state == SessionState.RES_AWAITING_NAME:
                guest_name = text.strip()
                ctx = session["context"]
                res_num = random.randint(100000, 999999)
                
                # コントロール層へ辞書(requested_rooms)を渡す
                reservation = self.res_ctrl.reserve_rooms(
                    reservation_number=res_num,
                    staying_date=ctx["staying_date"],
                    guest_name=guest_name,
                    requested_rooms=ctx["requested_rooms"]
                )
                
                self.session_manager.clear_session(user_id)
                return f"ご予約が完了しました！\n予約番号: {reservation.reservation_number}\n料金: {reservation.get_amount()}円"
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