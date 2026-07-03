from enum import Enum
from typing import Dict, Any

class SessionState(Enum):
    INIT = "INIT"
    
    # 予約フローのステータス
    RES_AWAITING_DATE = "RES_AWAITING_DATE"
    RES_AWAITING_COUNT = "RES_AWAITING_COUNT"
    RES_AWAITING_TYPE = "RES_AWAITING_TYPE"
    RES_AWAITING_NAME = "RES_AWAITING_NAME"
    
    # チェックインフローのステータス
    CI_AWAITING_RES_NUM = "CI_AWAITING_RES_NUM"
    
    # チェックアウトフローのステータス
    CO_AWAITING_ROOM_NUM = "CO_AWAITING_ROOM_NUM"

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

    def update_state(self, user_id: str, new_state: SessionState) -> None:
        """ステータスを更新する"""
        self.get_session(user_id)["state"] = new_state

    def update_context(self, user_id: str, key: str, value: Any) -> None:
        """入力された値（日付や人数など）を一時保存する"""
        self.get_session(user_id)["context"][key] = value

    def clear_session(self, user_id: str) -> None:
        """会話が完了（またはエラー）した際にセッションを破棄する"""
        if user_id in self.sessions:
            del self.sessions[user_id]