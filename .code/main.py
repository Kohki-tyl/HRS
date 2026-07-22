import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 各層のモジュールをインポート
from domain import Hotel, RoomType, Room, Reservation, Guest, Payment
from infrastructure import MySQLReservationRepository, MemoryReservationRepository
from application import ReservationControl, CheckInControl, CheckOutControl
from ui import SessionManager, ChatInterface, FrontDeskTerminal

app = FastAPI()

# ==========================================
# 0. 静的ファイルの設定
# ==========================================
# UI層の静的ファイル（CSS、JS）を配信
ui_static_path = Path(__file__).parent / "ui" / "static"
if ui_static_path.exists():
    app.mount("/static", StaticFiles(directory=str(ui_static_path)), name="static")
# ※実際の運用では環境変数から取得します
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


# ==========================================
# 2. 依存性の注入 (DI) とシステムの初期化
# ==========================================

# --- インフラストラクチャ層 ---
# テスト検証用: インメモリDB を使用
# 本番運用時は MySQLReservationRepository に切り替えてください
repository = MemoryReservationRepository()

# MySQL 版（本番運用用）
# db_config = {
#     "host": "localhost",
#     "user": "root",
#     "password": "password",
#     "database": "hrs_db"
# }
# repository = MySQLReservationRepository(db_config, initialize_schema=False)

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
    """アプリケーション起動時の初期化・テストデータ作成

    1. テーブルを用意する
    2. (インメモリDB モード時) デモ用のテスト予約を作成する

    空室状況はその都度 DB から判定する（DB引き）ため、起動時の在庫復元は不要。
    """
    from datetime import date

    repository.initialize_schema()

    # テスト用データを作成（インメモリDB モードのときのみ）
    if isinstance(repository, MemoryReservationRepository):
        print("\n" + "="*60)
        print("🔧 インメモリDB モードで実行しています")
        print("="*60)
        
        # テスト用予約データを作成
        test_reservations = [
            {
                "reservation_number": 100001,
                "staying_date": date(2026, 7, 22),
                "guest_name": "田中太郎",
                "room_numbers": [101],
                "amount": 10000
            },
            {
                "reservation_number": 100002,
                "staying_date": date(2026, 7, 22),
                "guest_name": "佐藤花子",
                "room_numbers": [201],
                "amount": 50000
            },
            {
                "reservation_number": 100003,
                "staying_date": date(2026, 7, 23),
                "guest_name": "鈴木次郎",
                "room_numbers": [102],
                "amount": 10000
            }
        ]
        
        for test_data in test_reservations:
            try:
                # テスト用予約を作成
                rooms = [Room(room_number=rn) for rn in test_data["room_numbers"]]
                reservation = Reservation(
                    reservation_number=test_data["reservation_number"],
                    staying_date=test_data["staying_date"],
                    guest=Guest(name=test_data["guest_name"]),
                    rooms=rooms,
                    payment=Payment(amount=test_data["amount"])
                )
                repository.save(reservation)
            except Exception as e:
                print(f"⚠️  テストデータ作成エラー: {e}")
        
        print(f"✅ テスト用予約 {len(test_reservations)} 件を作成しました")
        print("\n【テスト用予約番号】")
        for test_data in test_reservations:
            print(f"  - 予約番号: {test_data['reservation_number']}, "
                  f"ゲスト: {test_data['guest_name']}, "
                  f"部屋: {test_data['room_numbers']}")
        print("="*60 + "\n")


# ==========================================
# 3.5 フロントデスク Web UI エンドポイント
# ==========================================

@app.get("/front")
async def get_front_desk_page():
    """受付係用のフロントデスク Web UI を返す"""
    template_path = Path(__file__).parent / "ui" / "templates" / "front_desk.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="フロントデスク画面が見つかりません")
    return FileResponse(template_path, media_type="text/html; charset=utf-8")


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

@app.get("/front/reservations")
async def get_reservations_list():
    """予約一覧を取得するエンドポイント"""
    try:
        reservations = repository.list_all()
        
        # 予約データをJSON形式に変換
        reservations_data = []
        for res in reservations:
            reservations_data.append({
                "reservation_number": res.reservation_number,
                "number": res.reservation_number,
                "guest_name": res.guest.name if res.guest else "N/A",
                "guest": {
                    "name": res.guest.name if res.guest else "N/A"
                },
                "check_in_date": str(res.staying_date) if hasattr(res, 'staying_date') else "N/A",
                "check_in_date_planned": str(res.staying_date) if hasattr(res, 'staying_date') else "N/A",
                "room_number": res.rooms[0].room_number if res.rooms else "N/A",
                "room": {
                    "number": res.rooms[0].room_number if res.rooms else "N/A"
                },
                "total_amount": res.payment.amount if res.payment else 0,
                "payment": {
                    "total_amount": res.payment.amount if res.payment else 0
                },
                "status": res.status.value if hasattr(res.status, 'value') else str(res.status)
            })
        
        return {
            "status": "success",
            "reservations": reservations_data
        }
    except Exception as e:
        print(f"Error fetching reservations: {e}")
        return {
            "status": "error",
            "message": str(e),
            "reservations": []
        }