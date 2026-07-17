import os
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 各層のモジュールをインポート
from domain import Hotel, RoomType, Room
from infrastructure import MySQLReservationRepository
from application import ReservationControl, CheckInControl, CheckOutControl
from ui import SessionManager, ChatInterface, FrontDeskTerminal

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
# import 時に DB へ接続しないよう、スキーマ作成は起動時 (startup) に明示的に行う
repository = MySQLReservationRepository(db_config, initialize_schema=False)

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

# --- プレゼンテーション層 (UI層) ---
# 予約は利用者が LINE で、チェックイン・チェックアウトは受付係がフロント端末で行う
session_manager = SessionManager()
chat_interface = ChatInterface(res_ctrl, session_manager)
front_desk = FrontDeskTerminal(ci_ctrl, co_ctrl)


# ==========================================
# 3. 起動時処理
# ==========================================

@app.on_event("startup")
def on_startup():
    """アプリケーション起動時に一度だけテーブルを用意する"""
    repository.initialize_schema()


# ==========================================
# 4. Webhook エンドポイント
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


# ==========================================
# 5. フロント端末 エンドポイント（受付係の操作）
# ==========================================

@app.post("/front/check-in/search")
async def front_search_reservation(reservation_number: str):
    """受付係が予約番号を入力し、予約内容を照会する"""
    return {"message": front_desk.input_reservation_number(reservation_number)}

@app.post("/front/check-in/confirm")
async def front_confirm_check_in(reservation_number: str):
    """受付係が内容確認後、チェックインを確定する"""
    return {"message": front_desk.input_check_in(reservation_number)}

@app.post("/front/check-out/search")
async def front_search_information(room_number: str):
    """受付係が部屋番号を入力し、請求額を照会する"""
    return {"message": front_desk.input_room_number(room_number)}

@app.post("/front/check-out/confirm")
async def front_confirm_check_out(room_number: str):
    """受付係が支払い受領後、チェックアウトを確定する"""
    return {"message": front_desk.input_check_out(room_number)}