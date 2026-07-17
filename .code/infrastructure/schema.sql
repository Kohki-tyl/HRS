CREATE TABLE IF NOT EXISTS reservations (
    reservation_number INT PRIMARY KEY,
    staying_date DATE NOT NULL,
    guest_name VARCHAR(255) NOT NULL,
    payment_amount INT NOT NULL,
    payment_status VARCHAR(50) NOT NULL,
    reservation_status VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS reservation_rooms (
    reservation_number INT NOT NULL,
    room_number INT NOT NULL,
    PRIMARY KEY (reservation_number, room_number),
    FOREIGN KEY (reservation_number) REFERENCES reservations(reservation_number) ON DELETE CASCADE
);
