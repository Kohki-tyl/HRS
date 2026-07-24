"""管理者フロントデスク画面を LINE なしで起動するデバッグ用 Web サーバ

LINE Messaging API（line-bot-sdk）を使わずに、受付係向けの Web UI と
その API を起動・確認できる。Web エンドポイントの自動テストからも
create_debug_app() を使って同じアプリを検証する。

起動:
    python debug_web.py
    → http://127.0.0.1:8000/front  （既定パスワード: hrs-admin）

環境変数:
    ADMIN_PASSWORD  管理者ログインのパスワード（既定 hrs-admin）
    HRS_DB_PATH     SQLite ファイルのパス（既定 hrs_debug_web.db）
"""
import os
from pathlib import Path
from typing import Tuple

from fastapi import FastAPI

from domain import Hotel, RoomType, Room
from infrastructure import SQLiteReservationRepository
from application import CheckInControl, CheckOutControl
from ui import FrontDeskTerminal
from web_frontdesk import create_frontdesk_app


def build_hotel() -> Hotel:
    """デバッグ用のホテル定義（Standard 101,102 / Suite 201）"""
    return Hotel(hotel_name="Debug Hotel", room_types=[
        RoomType(type_name="Standard", price=10000, rooms=[Room(101), Room(102)]),
        RoomType(type_name="Suite", price=50000, rooms=[Room(201)]),
    ])


def create_debug_app(
    db_path: str = "hrs_debug_web.db",
    admin_password: str = "hrs-admin",
    seed_demo: bool = True,
) -> Tuple[FastAPI, SQLiteReservationRepository]:
    """LINE 非依存の管理者フロントデスクアプリと、そのリポジトリを返す

    テストからはファイル DB（tmp_path 等）を渡して独立した状態を作る。
    """
    repository = SQLiteReservationRepository(db_path)
    front_desk = FrontDeskTerminal(CheckInControl(repository), CheckOutControl(repository))
    app = create_frontdesk_app(
        repository, front_desk, admin_password=admin_password, seed_demo=seed_demo
    )
    return app, repository


# uvicorn 用のモジュールレベル app（`uvicorn debug_web:app` でも起動可）
_DB_PATH = os.environ.get("HRS_DB_PATH", str(Path(__file__).with_name("hrs_debug_web.db")))
_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "hrs-admin").strip()
app, repository = create_debug_app(db_path=_DB_PATH, admin_password=_ADMIN_PASSWORD, seed_demo=True)


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print(" HRS 管理者フロントデスク デバッグサーバ（LINE 不要）")
    print("=" * 60)
    print(f" URL     : http://127.0.0.1:8000/front")
    print(f" DB      : {_DB_PATH}")
    print(f" パスワード: {_ADMIN_PASSWORD}")
    print("=" * 60)
    uvicorn.run(app, host="127.0.0.1", port=8000)
