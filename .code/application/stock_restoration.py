from domain import Hotel, ReservationRepository

def restore_hotel_stock(hotel: Hotel, repository: ReservationRepository) -> int:
    """DB に残る予約から Hotel の在庫 (Room.reserved_dates) を復元する

    Room / RoomType の在庫はメモリ上にしか存在せず永続化されない。
    プロセスを起動し直すと在庫が空に戻り、既存予約と同じ部屋・同じ
    宿泊日を二重に予約できてしまう。これを防ぐため、起動時に
    キャンセル以外の予約が押さえている (部屋, 宿泊日) を Hotel の
    Room へ再登録する。

    戻り値は復元した (部屋, 宿泊日) の件数。
    """
    restored = 0
    for reservation in repository.find_active_reservations():
        for room_number in reservation.get_room_numbers():
            room = hotel.find_room(room_number)
            if room and room.is_vacant_on(reservation.staying_date):
                room.assign(reservation.staying_date)
                restored += 1
    return restored
