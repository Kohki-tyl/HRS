from enum import Enum
from typing import Dict, Any

class SessionState(Enum):
    """LINE (利用者) との予約対話の進行状態

    チェックイン・チェックアウトは受付係がフロント端末 (FrontDeskTerminal) で
    1操作ずつ完結させるため, 多ターンのセッション状態を持たない。
    """
    INIT = "INIT"

    # 予約フロー (UC1) のステータス
    RES_AWAITING_DATE = "RES_AWAITING_DATE"
    RES_AWAITING_ROOMS_SELECTION = "RES_AWAITING_ROOMS_SELECTION"
    RES_AWAITING_NAME = "RES_AWAITING_NAME"
    RES_AWAITING_CONFIRM = "RES_AWAITING_CONFIRM"

    # キャンセルフロー (UC4) のステータス
    CANCEL_AWAITING_RES_NUM = "CANCEL_AWAITING_RES_NUM"
    CANCEL_AWAITING_CONFIRM = "CANCEL_AWAITING_CONFIRM"

class SessionManager:
    """ユーザーごとの会話の進行状態を管理するクラス"""

    def __init__(self):
        # 簡易的にインメモリ辞書で管理 {user_id: {"state": SessionState, "context": {}}}
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def get_session(self, user_id: str) -> Dict[str, Any]:
        """セッションを取得する（なければ初期状態で作成）"""
        if user_id not in self.sessions:
            self.sessions[user_id] = {"state": SessionState.INIT, "context": {}}
        return self.sessions[user_id]

    def get_state(self, user_id: str) -> SessionState:
        """現在の進行状態を取得する"""
        return self.get_session(user_id)["state"]

    def update_state(self, user_id: str, new_state: SessionState) -> None:
        """ステータスを更新する"""
        self.get_session(user_id)["state"] = new_state

    def get_context(self, user_id: str) -> Dict[str, Any]:
        """一時保存された入力値をまとめて取得する"""
        return self.get_session(user_id)["context"]

    def update_context(self, user_id: str, key: str, value: Any) -> None:
        """入力された値（日付や部屋数など）を一時保存する"""
        self.get_session(user_id)["context"][key] = value

    def clear_session(self, user_id: str) -> None:
        """会話が完了（またはエラー）した際にセッションを破棄する"""
        if user_id in self.sessions:
            del self.sessions[user_id]
