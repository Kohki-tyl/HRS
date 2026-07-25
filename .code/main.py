import os
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
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# 各層のモジュールをインポート
from domain import Hotel, RoomType, Room
from infrastructure import SQLiteReservationRepository
from application import ReservationControl, CheckInControl, CheckOutControl, CancelControl
from ui import SessionManager, ChatInterface, FrontDeskTerminal
from web_frontdesk import create_frontdesk_app

# ==========================================
# 1. 依存性の注入 (DI) とシステムの初期化
# ==========================================

# --- インフラストラクチャ層 ---
# 永続化は SQLite に統一する。DB ファイルのパスは環境変数 HRS_DB_PATH で上書き可能。
db_path = os.environ.get("HRS_DB_PATH", str(Path(__file__).parent / "hrs.db"))
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
# 管理者向けエンドポイントの定義は web_frontdesk.create_frontdesk_app に集約している。
app = create_frontdesk_app(repository, front_desk, seed_demo=True)


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

    # LINEユーザーへ結果を返信
    with ApiClient(line_configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )
