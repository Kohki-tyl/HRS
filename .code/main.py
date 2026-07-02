import os
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 各層のモジュールをインポート
from domain import Hotel, RoomType, Room
from infrastructure import MySQLReservationRepository
from application import ReservationControl, CheckInControl, CheckOutControl
from ui import SessionManager, ChatInterface

app = FastAPI()

# ==========================================
# 1. LINE APIの初期設定
# ==========================================
# ※実際の運用では環境変数から取得します
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


# ==========================================
# 2. 依存性の注入 (DI) とシステムの初期化
# ==========================================

# --- インフラストラクチャ層 ---
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "password",  # ご自身のMySQLパスワードに変更してください
    "database": "hrs_db"
}
repository = MySQLReservationRepository(db_config)

# --- ドメイン層 (初期データの用意) ---
# 本来はDBや管理者画面からロードしますが、今回はメモリ上で初期化します
rooms_standard = [Room(room_number=101), Room(room_number=102)]
rooms_suite = [Room(room_number=201)]
room_types = [
    RoomType(type_name="Standard", price=10000, total_rooms=2, rooms=rooms_standard),
    RoomType(type_name="Suite", price=50000, total_rooms=1, rooms=rooms_suite)
]
hotel = Hotel(hotel_name="Grand Hotel", room_types=room_types)

# --- アプリケーション層 ---
res_ctrl = ReservationControl(repository, hotel)
ci_ctrl = CheckInControl(repository)
co_ctrl = CheckOutControl(repository)

# --- プレゼンテーション層 (UI層) ---
session_manager = SessionManager()
chat_interface = ChatInterface(res_ctrl, ci_ctrl, co_ctrl, session_manager)


# ==========================================
# 3. Webhook エンドポイント
# ==========================================

@app.post("/callback")
async def callback(request: Request):
    """LINEプラットフォームからのWebhookを受信するエンドポイント"""
    signature = request.headers.get("X-Line-Signature")
    body = await request.body()
    
    try:
        # 署名の検証とイベントのハンドリング
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature. Check your channel secret.")
    
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """テキストメッセージを受信した際の処理"""
    user_id = event.source.user_id
    user_text = event.message.text
    
    # 構築したChatInterface（UI層）に処理を委譲して、返信テキストを取得
    reply_text = chat_interface.handle_message(user_id, user_text)
    
    # LINEユーザーへ結果を返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )