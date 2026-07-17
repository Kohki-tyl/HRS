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
        for res in self.db.values():
            if room_number in res.get_room_numbers() and res.status == ReservationStatus.CHECKED_IN:
                return res
        return None

# ==========================================
# 2. 初期セットアップ (DI)
# ==========================================
def setup_system():
    rooms_standard = [Room(room_number=101), Room(room_number=102)]
    rooms_suite = [Room(room_number=201)]
    room_types = [
        RoomType(type_name="Standard", price=10000, rooms=rooms_standard),
        RoomType(type_name="Suite", price=50000, rooms=rooms_suite)
    ]
    hotel = Hotel(hotel_name="Debug Hotel", room_types=room_types)

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
    print("=" * 50)
    print(" HRS デバッグターミナル起動 (複数タイプ一括予約対応版)")
    print("=" * 50)

    while True:
        print("\n[操作を選択] 1:予約  2:チェックイン  3:チェックアウト  0:終了")
        choice = input(">> ")

        if choice == "0":
            print("デバッグを終了します。")
            break

        # --- UC1: 予約 (複数部屋タイプ対応) ---
        elif choice == "1":
            try:
                date_str = input("宿泊日 (YYYY-MM-DD) [例: 2026-07-01]: ")
                staying_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                # アプリケーション層から日付ベースの空室状況（辞書）を取得
                stocks = res_ctrl.get_available_stocks(staying_date)
                if not stocks:
                    print("✕ 申し訳ありません。ご希望の日程でご用意できる部屋がありません。")
                    continue
                
                print("\n--- 空室状況 ---")
                for type_name, stock in stocks.items():
                    print(f"・{type_name}: 残り {stock['count']} 室（1室 {stock['price']}円）")
                print("----------------")
                
                # ユーザーからテキスト入力（カンマ区切り）を受け取る
                req_str = input("希望する部屋と数を入力 (例: Standard 1, Suite 1): ")
                
                # 文字列をパースして辞書 {type_name: count} に変換
                requested_rooms = {}
                for part in req_str.split(","):
                    name, count_str = part.strip().split()
                    requested_rooms[name] = int(count_str)

                guest_name = input("ご予約者名: ")

                # アプリケーション層へ一括予約を依頼（予約番号の採番もアプリケーション層が行う）
                res = res_ctrl.reserve_rooms(staying_date, guest_name, requested_rooms)
                
                print("-" * 20)
                print(f"【予約完了】 予約番号: {res.reservation_number} / 料金: {res.get_amount()}円")
                print(f"（内部データ確認: 確保された部屋 -> {res.get_room_numbers()}）")
                print("-" * 20)

            except ValueError:
                print("✕ 入力形式が正しくありません。「Standard 1, Suite 1」のように入力してください。")
            except BureaucraticError as e:
                print(f"✕ 業務ルールエラー: {e}")
            except Exception as e:
                print(f"✕ エラー発生: {e}")

        # --- UC2: チェックイン ---
        elif choice == "2":
            try:
                res_num = int(input("予約番号を入力: "))
                
                reservation = ci_ctrl.search_reservation(res_num)
                if not reservation:
                    print("✕ 該当する予約が見つかりません。")
                    continue
                if reservation.status != ReservationStatus.CREATED:
                    print(f"✕ この予約は現在「{reservation.status.value}」状態のため、チェックインできません。")
                    continue
                
                print("\n--- 予約詳細確認 ---")
                print(f"ご予約者様: {reservation.guest.name}")
                print(f"ご宿泊日程: {reservation.staying_date}")
                print(f"予定お部屋: {reservation.get_room_numbers()}")
                print("--------------------")
                
                confirm = input("以上の内容でチェックインを確定しますか？ (y/n): ")
                if confirm.lower() == 'y':
                    assigned_rooms = ci_ctrl.check_in(res_num)
                    print("-" * 20)
                    print(f"【チェックイン完了】 鍵をお渡しください。お部屋番号: {assigned_rooms}")
                    print("-" * 20)
                else:
                    print("手続きを中断しました。")

            except BureaucraticError as e:
                print(f"✕ 業務ルールエラー: {e}")
            except Exception as e:
                print(f"✕ エラー発生: {e}")

        # --- UC3: チェックアウト ---
        elif choice == "3":
            try:
                room_num = int(input("退室する部屋番号を入力: "))
                
                reservation = co_ctrl.search_information(room_num)
                if not reservation:
                    print("✕ 該当するお部屋の滞在情報が見つかりません。")
                    continue
                
                print("\n--- チェックアウト精算 ---")
                print(f"ご宿泊者様: {reservation.guest.name}")
                print(f"ご請求額  : {reservation.get_amount()} 円")
                print("--------------------------")
                
                confirm = input("上記金額の支払いを受け取り、チェックアウトを確定しますか？ (y/n): ")
                if confirm.lower() == 'y':
                    co_ctrl.check_out(room_num)
                    print("-" * 20)
                    print("【チェックアウト完了】 お気をつけてお帰りください。")
                    print("-" * 20)
                else:
                    print("手続きを中断しました。")

            except BureaucraticError as e:
                print(f"✕ 業務ルールエラー: {e}")
            except Exception as e:
                print(f"✕ エラー発生: {e}")
        else:
            print("無効な入力です。")

if __name__ == "__main__":
    main()