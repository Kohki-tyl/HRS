"""管理者フロントデスク Web エンドポイントの通しテスト

LINE（line-bot-sdk）に依存しない debug_web のアプリを FastAPI TestClient で
起動し、ブラウザ（front_desk.html / app.js）が呼ぶのと同じ HTTP エンドポイントを
一通り検証する。認証・予約一覧・チェックイン/アウト候補・確定までを確認する。
"""
import pytest
from fastapi.testclient import TestClient

from debug_web import create_debug_app

PASSWORD = "test-pw"


@pytest.fixture
def env(tmp_path):
    app, repo = create_debug_app(db_path=str(tmp_path / "web.db"),
                                 admin_password=PASSWORD, seed_demo=True)
    with TestClient(app) as client:
        yield client, repo


def token_of(client):
    res = client.post("/front/login", json={"password": PASSWORD})
    assert res.status_code == 200
    return {"X-Admin-Token": res.json()["token"]}


# ========== 認証 ==========

def test_login_rejects_wrong_password(env):
    client, _ = env
    assert client.post("/front/login", json={"password": "nope"}).status_code == 401


def test_protected_endpoints_require_token(env):
    client, _ = env
    assert client.get("/front/reservations").status_code == 401
    assert client.get("/front/checkin/candidates").status_code == 401
    assert client.get("/front/checkout/candidates").status_code == 401


# ========== 画面・静的ファイル ==========

def test_front_page_and_assets_served(env):
    client, _ = env
    page = client.get("/front")
    assert page.status_code == 200
    assert "フロントデスク" in page.text
    # 画面が参照する静的ファイルが配信される
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


# ========== 予約一覧 ==========

def test_reservations_sorted_by_date(env):
    client, _ = env
    headers = token_of(client)
    rows = client.get("/front/reservations", headers=headers).json()["reservations"]
    assert len(rows) == 3
    dates = [r["staying_date"] for r in rows]
    assert dates == sorted(dates)
    assert all("room_numbers" in r for r in rows)


# ========== チェックイン → チェックアウト の通し ==========

def test_checkin_then_checkout_flow(env):
    client, _ = env
    headers = token_of(client)

    # 本日分の未チェックイン（デモの 100001, 100002）
    candidates = client.get("/front/checkin/candidates", headers=headers).json()["reservations"]
    numbers = {r["reservation_number"] for r in candidates}
    assert {100001, 100002} <= numbers

    # 100001（部屋 101）をチェックイン確定
    res = client.post("/front/check-in/confirm",
                      params={"reservation_number": 100001}, headers=headers)
    assert res.status_code == 200
    assert "完了" in res.json()["message"]

    # チェックイン候補から消える
    after = client.get("/front/checkin/candidates", headers=headers).json()["reservations"]
    assert 100001 not in {r["reservation_number"] for r in after}

    # チェックアウト候補（宿泊中）に現れる
    staying = client.get("/front/checkout/candidates", headers=headers).json()["reservations"]
    assert 100001 in {r["reservation_number"] for r in staying}

    # 部屋 101 でチェックアウト確定
    res = client.post("/front/check-out/confirm",
                      params={"room_number": 101}, headers=headers)
    assert res.status_code == 200
    assert "完了" in res.json()["message"]

    # チェックアウト候補から消える
    final = client.get("/front/checkout/candidates", headers=headers).json()["reservations"]
    assert 100001 not in {r["reservation_number"] for r in final}


def test_checkout_candidates_initially_empty(env):
    client, _ = env
    headers = token_of(client)
    # 初期状態ではチェックイン前なので宿泊中はいない
    staying = client.get("/front/checkout/candidates", headers=headers).json()["reservations"]
    assert staying == []
