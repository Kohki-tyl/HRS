import os
from datetime import date, timedelta
from pathlib import Path
from fastapi import Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction,
    DatetimePickerAction,
)
from linebot.v3.webhooks import FollowEvent, MessageEvent, PostbackEvent, TextMessageContent

# 各層のモジュールをインポート
from domain import Hotel, RoomType, Room
from infrastructure import SQLiteReservationRepository
from application import ReservationControl, CheckInControl, CheckOutControl, CancelControl
from ui import SessionManager, SessionState, ChatInterface, FrontDeskTerminal
from scripts.shared.web_frontdesk import create_frontdesk_app

# ==========================================
# 1. 依存性の注入 (DI) とシステムの初期化
# ==========================================

# --- インフラストラクチャ層 ---
# 永続化は SQLite に統一する。DB ファイルのパスは環境変数 HRS_DB_PATH で上書き可能。
_CODE_ROOT = Path(__file__).resolve().parents[2]
db_path = os.environ.get("HRS_DB_PATH", str(_CODE_ROOT / "hrs.db"))
repository = SQLiteReservationRepository(db_path)

# --- ドメイン層 (初期データの用意) ---
# 本来はDBや管理者画面からロードしますが、今回はメモリ上で初期化します
rooms_standard = [Room(room_number=101), Room(room_number=102)]
rooms_suite = [Room(room_number=201)]
room_types = [
    RoomType(type_name="Standard", price=10000, rooms=rooms_standard),
    RoomType(type_name="Suite", price=50000, rooms=rooms_suite)
]
hotel = Hotel(hotel_name="Grand Hotel", room_types=room_types)

# --- アプリケーション層 ---
res_ctrl = ReservationControl(repository, hotel)
ci_ctrl = CheckInControl(repository)
co_ctrl = CheckOutControl(repository)
cancel_ctrl = CancelControl(repository)

# --- プレゼンテーション層 (UI層) ---
# 予約・キャンセルは利用者が LINE で、チェックイン・チェックアウトは受付係がフロント端末で行う
session_manager = SessionManager()
chat_interface = ChatInterface(res_ctrl, cancel_ctrl, session_manager)
front_desk = FrontDeskTerminal(ci_ctrl, co_ctrl)

# 管理者フロントデスク（ログイン・予約一覧・チェックイン/アウト）を含む app を生成。
# 管理者向けエンドポイントの定義は
# scripts.shared.web_frontdesk.create_frontdesk_app に集約している。
seed_demo = os.environ.get("HRS_SEED_DEMO", "false").strip().lower() in {
    "1", "true", "yes", "on",
}
app = create_frontdesk_app(repository, front_desk, seed_demo=seed_demo)


# ==========================================
# 2. LINE Messaging API の設定
# ==========================================
# LINE の秘密情報は必ず環境変数から取得する。
# 未設定でもフロントデスク画面は起動できるが、LINE Webhook は 503 を返す。
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "").strip()
LINE_CONFIGURED = bool(LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET)

# SDK オブジェクトはデコレータ登録に必要なため生成するが、未設定時は callback で遮断する。
line_configuration = Configuration(
    access_token=LINE_CHANNEL_ACCESS_TOKEN or "LINE_NOT_CONFIGURED"
)
handler = WebhookHandler(LINE_CHANNEL_SECRET or "LINE_NOT_CONFIGURED")


# ==========================================
# 3. 稼働状態・Webhook エンドポイント
# ==========================================

@app.get("/health")
async def health():
    """稼働状態を返す。秘密情報そのものは返さない。"""
    return {
        "status": "ok",
        "line_configured": LINE_CONFIGURED,
        "line_webhook_path": "/callback",
    }

@app.post("/callback")
async def callback(request: Request):
    """LINEプラットフォームからのWebhookを受信するエンドポイント"""
    if not LINE_CONFIGURED:
        raise HTTPException(
            status_code=503,
            detail="LINE_CHANNEL_ACCESS_TOKEN と LINE_CHANNEL_SECRET を設定してください。",
        )

    signature = request.headers.get("X-Line-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="X-Line-Signature header is required.")
    body = await request.body()

    try:
        # 署名の検証とイベントのハンドリング
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Check your channel secret.")

    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """テキストメッセージを受信した際の処理"""
    user_id = event.source.user_id
    user_text = event.message.text

    # 構築したChatInterface（UI層）に処理を委譲して、返信テキストを取得
    reply_text = chat_interface.handle_message(user_id, user_text)

    _reply_text(event.reply_token, user_id, reply_text)


@handler.add(PostbackEvent)
def handle_postback(event):
    """日付選択アクションの結果を予約対話へ渡す。"""
    user_id = event.source.user_id
    params = event.postback.params or {}
    selected_date = params.get("date")
    if event.postback.data != "action=select_staying_date" or not selected_date:
        reply_text = chat_interface.initial_guidance()
    else:
        reply_text = chat_interface.handle_message(user_id, selected_date)
    _reply_text(event.reply_token, user_id, reply_text)


@handler.add(FollowEvent)
def handle_follow(event):
    """友だち追加時に機能案内と操作ボタンを表示する。"""
    user_id = event.source.user_id
    session_manager.clear_session(user_id)
    _reply_text(event.reply_token, user_id, chat_interface.initial_guidance())


def _reply_text(reply_token: str, user_id: str, reply_text: str) -> None:
    """会話状態に合ったクイックリプライを付けて返信する。"""
    message = TextMessage(text=reply_text, quick_reply=_quick_reply_for(user_id))
    with ApiClient(line_configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[message],
            )
        )


def _quick_reply_for(user_id: str) -> QuickReply:
    state = session_manager.get_state(user_id)
    if state == SessionState.RES_AWAITING_DATE:
        today = date.today()
        return QuickReply(items=[
            QuickReplyItem(action=DatetimePickerAction(
                label="宿泊日を選択",
                data="action=select_staying_date",
                mode="date",
                initial=(today + timedelta(days=1)).isoformat(),
                min=today.isoformat(),
                max=(today + timedelta(days=365)).isoformat(),
            )),
            QuickReplyItem(action=MessageAction(label="中止", text="キャンセル")),
        ])
    if state == SessionState.RES_AWAITING_ROOMS_SELECTION:
        options = chat_interface.get_room_selection_options(user_id)
        items = [
            QuickReplyItem(action=MessageAction(
                label=f"{type_name} {count}室",
                text=f"{type_name} {count}",
            ))
            for type_name, count in options[:12]
        ]
        items.append(QuickReplyItem(action=MessageAction(label="中止", text="キャンセル")))
        return QuickReply(items=items)
    if state == SessionState.RES_AWAITING_CONFIRM:
        return QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="予約を確定", text="はい")),
            QuickReplyItem(action=MessageAction(label="予約を中止", text="キャンセル")),
        ])
    if state == SessionState.CANCEL_AWAITING_CONFIRM:
        return QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="キャンセルを確定", text="はい")),
            QuickReplyItem(action=MessageAction(label="取りやめる", text="いいえ")),
        ])
    if state == SessionState.CANCEL_AWAITING_RES_NUM:
        reservations = chat_interface.get_cancellable_reservations(user_id)
        items = [
            QuickReplyItem(action=MessageAction(
                label=f"{reservation.staying_date:%m/%d} #{reservation.reservation_number}",
                text=str(reservation.reservation_number),
            ))
            for reservation in reservations[:12]
        ]
        items.append(QuickReplyItem(action=MessageAction(label="中止", text="キャンセル")))
        return QuickReply(items=items)
    if state == SessionState.INIT:
        return QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="予約", text="予約")),
            QuickReplyItem(action=MessageAction(label="予約確認", text="予約確認")),
            QuickReplyItem(action=MessageAction(label="予約キャンセル", text="予約キャンセル")),
        ])
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="手続きを中止", text="キャンセル")),
    ])
