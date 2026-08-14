"""管理者フロントデスク（Web UI）の FastAPI アプリを生成するファクトリ

LINE には依存しない。本番エントリ (scripts/startup/main.py) と、LINE を使わずに
起動できるデバッグサーバ (scripts/debug/debug_web.py) の両方がこのファクトリを使うことで、
管理者向けエンドポイントの定義を一箇所に集約する（実装の二重化を防ぐ）。
"""
import os
import secrets
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from domain import Reservation, Room, Guest, Payment, ReservationStatus, ReservationRepository
from ui import FrontDeskTerminal

_CODE_ROOT = Path(__file__).resolve().parents[2]
_STATIC_DIR = _CODE_ROOT / "ui" / "static"
_TEMPLATE = _CODE_ROOT / "ui" / "templates" / "front_desk.html"


class LoginRequest(BaseModel):
    password: str


def serialize_reservation(res: Reservation) -> dict:
    """予約エンティティを画面表示用の JSON へ変換する"""
    return {
        "reservation_number": res.reservation_number,
        "guest_name": res.guest.name if res.guest else "",
        "staying_date": str(res.staying_date),
        "room_numbers": res.get_room_numbers(),
        "total_amount": res.get_amount(),
        "status": res.status.value,
    }


def seed_demo_reservations(repository: ReservationRepository) -> int:
    """DB が空のときにデモ用の予約を投入する（本日分はチェックイン画面のデモに使える）"""
    if repository.find_all():
        return 0
    today = date.today()
    tomorrow = today + timedelta(days=1)
    demo = [
        (100001, today, "田中太郎", [101], 10000),
        (100002, today, "佐藤花子", [201], 50000),
        (100003, tomorrow, "鈴木次郎", [102], 10000),
    ]
    for number, staying_date, name, room_numbers, amount in demo:
        reservation = Reservation(
            reservation_number=number,
            staying_date=staying_date,
            guest=Guest(name=name),
            rooms=[Room(room_number=n) for n in room_numbers],
            payment=Payment(amount=amount),
        )
        repository.save(reservation)
    return len(demo)


def create_frontdesk_app(
    repository: ReservationRepository,
    front_desk: FrontDeskTerminal,
    *,
    admin_password: str | None = None,
    seed_demo: bool = False,
) -> FastAPI:
    """管理者フロントデスクのエンドポイントを備えた FastAPI アプリを生成する

    - GET  /front                       画面（HTML）
    - POST /front/login                 パスワード認証（トークン発行）
    - GET  /front/reservations          予約一覧（予約日順・要ログイン）
    - GET  /front/checkin/candidates    本日の未チェックイン予約（要ログイン）
    - GET  /front/checkout/candidates   宿泊中の予約（要ログイン）
    - POST /front/check-in/search|confirm    チェックイン照会・確定（要ログイン）
    - POST /front/check-out/search|confirm   チェックアウト照会・確定（要ログイン）
    """
    app = FastAPI()

    password = admin_password if admin_password is not None else os.environ.get("ADMIN_PASSWORD", "hrs-admin").strip()
    token = secrets.token_urlsafe(24)

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    def require_admin(x_admin_token: str = Header(default="")):
        """管理者トークンを検証する依存関数。フロントデスクの各 API を保護する。"""
        if not secrets.compare_digest(x_admin_token, token):
            raise HTTPException(status_code=401, detail="認証が必要です。ログインしてください。")

    @app.on_event("startup")
    def _on_startup():
        repository.initialize_schema()
        if seed_demo:
            seed_demo_reservations(repository)

    @app.get("/front")
    async def get_front_desk_page():
        """受付係用のフロントデスク Web UI を返す"""
        if not _TEMPLATE.exists():
            raise HTTPException(status_code=404, detail="フロントデスク画面が見つかりません")
        return FileResponse(_TEMPLATE, media_type="text/html; charset=utf-8")

    @app.post("/front/login")
    async def front_login(req: LoginRequest):
        """管理者パスワードを検証し、成功時にトークンを発行する"""
        if not secrets.compare_digest(req.password, password):
            raise HTTPException(status_code=401, detail="パスワードが違います。")
        return {"token": token}

    @app.get("/front/reservations", dependencies=[Depends(require_admin)])
    async def get_reservations_list():
        """全予約を予約日順に並べて返す（予約一覧機能）"""
        reservations = sorted(
            repository.find_all(),
            key=lambda r: (str(r.staying_date), r.reservation_number),
        )
        return {"reservations": [serialize_reservation(r) for r in reservations]}

    @app.get("/front/checkin/candidates", dependencies=[Depends(require_admin)])
    async def get_checkin_candidates():
        """本日分の、まだチェックインしていない予約を返す（チェックイン機能）"""
        todays = [
            r for r in repository.find_by_staying_date(date.today())
            if r.status == ReservationStatus.CREATED
        ]
        todays.sort(key=lambda r: r.reservation_number)
        return {"reservations": [serialize_reservation(r) for r in todays]}

    @app.get("/front/checkout/candidates", dependencies=[Depends(require_admin)])
    async def get_checkout_candidates():
        """現在チェックイン中（宿泊中）の予約を返す（チェックアウト機能）"""
        staying = [r for r in repository.find_all() if r.status == ReservationStatus.CHECKED_IN]
        staying.sort(key=lambda r: r.reservation_number)
        return {"reservations": [serialize_reservation(r) for r in staying]}

    @app.post("/front/check-in/search", dependencies=[Depends(require_admin)])
    async def front_search_reservation(reservation_number: str):
        """受付係が予約番号を入力し、予約内容を照会する"""
        return {"message": front_desk.input_reservation_number(reservation_number)}

    @app.post("/front/check-in/confirm", dependencies=[Depends(require_admin)])
    async def front_confirm_check_in(reservation_number: str):
        """受付係が内容確認後、チェックインを確定する"""
        return {"message": front_desk.input_check_in(reservation_number)}

    @app.post("/front/check-out/search", dependencies=[Depends(require_admin)])
    async def front_search_information(room_number: str):
        """受付係が部屋番号を入力し、請求額を照会する"""
        return {"message": front_desk.input_room_number(room_number)}

    @app.post("/front/check-out/confirm", dependencies=[Depends(require_admin)])
    async def front_confirm_check_out(room_number: str):
        """受付係が支払い受領後、チェックアウトを確定する"""
        return {"message": front_desk.input_check_out(room_number)}

    return app
