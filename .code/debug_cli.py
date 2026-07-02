import random
from datetime import datetime
from typing import Optional

# ドメインとアプリケーションのインポート
from domain import (
    Room, RoomType, Hotel, Reservation, 
    ReservationRepository, BureaucraticError, ReservationStatus
)
from application import ReservationControl, CheckInControl, CheckOutControl

# ==========================================
# 1. デバッグ用のダミーリポジトリ（インメモリ）
# ==========================================
class InMemoryReservationRepository(ReservationRepository):
    def __init__(self):
        self.db = {}

    def save(self, reservation: Reservation) -> None:
        self.db[reservation.reservation_number] = reservation

    def find_by_id(self, reservation_number: int) -> Optional[Reservation]:
        return self.db.get(reservation_number)

    def find_by_room_number(self, room_number: int) -> Optional[Reservation]:
        # 部屋番号から、現在「チェックイン済み」の予約を探す
        for res in self.db.values():
            if room_number in res.get_room_numbers() and res.status == ReservationStatus.CHECKED_IN:
                return res
        return None

# ==========================================
# 2. 初期セットアップ (DI)
# ==========================================
def setup_system():
    # 部屋とホテルの初期化
    rooms_standard = [Room(room_number=101), Room(room_number=102)]
    rooms_suite = [Room(room_number=201)]
    room_types = [
        RoomType(type_name="Standard", price=10000, total_rooms=2, rooms=rooms_standard),
        RoomType(type_name="Suite", price=50000, total_rooms=1, rooms=rooms_suite)
    ]
    hotel = Hotel(hotel_name="Debug Hotel", room_types=room_types)

    # リポジトリとコントロールの初期化
    repository = InMemoryReservationRepository()
    res_ctrl = ReservationControl(repository, hotel)
    ci_ctrl = CheckInControl(repository)
    co_ctrl = CheckOutControl(repository)
    
    return res_ctrl, ci_ctrl, co_ctrl

# ==========================================
# 3. CUI（ターミナルUI）のメインループ
# ==========================================
def main():
    res_ctrl, ci_ctrl, co_ctrl = setup_system()
    print("=" * 40)
    print(" HRS デバッグターミナル起動")
    print("=" * 40)

    while True:
        print("\n[操作を選択] 1:予約  2:チェックイン  3:チェックアウト  0:終了")
        choice = input(">> ")

        if choice == "0":
            print("デバッグを終了します。")
            break

        # --- UC1: 予約 ---
        elif choice == "1":
            try:
                date_str = input("宿泊日 (YYYY-MM-DD) [例: 2026-07-01]: ")
                staying_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                count = int(input("希望部屋数: "))

                available_types = res_ctrl.search_room(staying_date, count)
                if not available_types:
                    print("✕ 申し訳ありません。空室がありません。")
                    continue
                
                print("○ 空室のある部屋タイプ:", [t.type_name for t in available_types])
                type_name = input("希望の部屋タイプを入力: ")
                guest_name = input("ご予約者名: ")
                
                res_num = random.randint(100000, 999999)
                res = res_ctrl.reserve_room(res_num, staying_date, guest_name, type_name, count)
                
                print("-" * 20)
                print(f"【予約完了】 予約番号: {res.reservation_number} / 料金: {res.get_amount()}円")
                print(f"（内部データ確認: 確保された部屋 -> {res.get_room_numbers()}）")
                print("-" * 20)
            except ValueError:
                print("✕ 入力形式が正しくありません。")
            except Exception as e:
                print(f"✕ エラー発生: {e}")

        # --- UC2: チェックイン ---
        elif choice == "2":
            try:
                res_num = int(input("予約番号を入力: "))
                assigned_rooms = ci_ctrl.check_in(res_num)
                print("-" * 20)
                print(f"【チェックイン完了】 お部屋番号: {assigned_rooms}")
                print("-" * 20)
            except BureaucraticError as e:
                print(f"✕ 業務ルールエラー: {e}")
            except Exception as e:
                print(f"✕ エラー発生: {e}")

        # --- UC3: チェックアウト ---
        elif choice == "3":
            try:
                room_num = int(input("退室する部屋番号を入力: "))
                
                # 事前に料金を取得して表示
                reservation = co_ctrl.search_information(room_num)
                if reservation:
                    print(f"ご請求額は {reservation.get_amount()}円 です。")
                    
                co_ctrl.check_out(room_num)
                print("-" * 20)
                print("【チェックアウト完了】 お気をつけてお帰りください。")
                print("-" * 20)
            except BureaucraticError as e:
                print(f"✕ 業務ルールエラー: {e}")
            except Exception as e:
                print(f"✕ エラー発生: {e}")
        else:
            print("無効な入力です。")

if __name__ == "__main__":
    main()