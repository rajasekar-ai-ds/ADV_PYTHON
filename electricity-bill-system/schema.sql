-- Electricity Bill Management System - MySQL schema
-- The application creates/selects the configured database before running this file.

-- Admin users who log in to the system
CREATE TABLE admins (
    admin_id      INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

-- Tariff slabs: price per unit for each range of units, per connection type
-- Example (domestic): units 1-100 at 0.00, 101-200 at 2.25, ...
CREATE TABLE tariff_slabs (
    slab_id         INT AUTO_INCREMENT PRIMARY KEY,
    connection_type ENUM('DOMESTIC','COMMERCIAL') NOT NULL,
    from_unit       INT NOT NULL,
    to_unit         INT NULL,              -- NULL means "and above"
    rate_per_unit   DECIMAL(6,2) NOT NULL,
    CHECK (from_unit >= 1),
    CHECK (to_unit IS NULL OR to_unit >= from_unit),
    CHECK (rate_per_unit >= 0)
);

-- Fixed monthly charge per connection type
CREATE TABLE fixed_charges (
    connection_type ENUM('DOMESTIC','COMMERCIAL') PRIMARY KEY,
    amount          DECIMAL(8,2) NOT NULL CHECK (amount >= 0)
);

CREATE TABLE consumers (
    consumer_id     INT AUTO_INCREMENT PRIMARY KEY,
    service_no      VARCHAR(20)  NOT NULL UNIQUE,   -- printed on the bill
    name            VARCHAR(100) NOT NULL,
    address         VARCHAR(255) NOT NULL,
    phone           VARCHAR(15)  NOT NULL,
    email           VARCHAR(100),
    connection_type ENUM('DOMESTIC','COMMERCIAL') NOT NULL DEFAULT 'DOMESTIC',
    initial_reading INT NOT NULL DEFAULT 0 CHECK (initial_reading >= 0),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE meter_readings (
    reading_id    INT AUTO_INCREMENT PRIMARY KEY,
    consumer_id   INT NOT NULL,
    reading_date  DATE NOT NULL,
    reading_value INT  NOT NULL CHECK (reading_value >= 0),
    FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id) ON DELETE CASCADE
);

-- One bill per meter reading
CREATE TABLE bills (
    bill_id          INT AUTO_INCREMENT PRIMARY KEY,
    consumer_id      INT NOT NULL,
    reading_id       INT NOT NULL UNIQUE,
    previous_reading INT NOT NULL,
    current_reading  INT NOT NULL,
    units_consumed   INT NOT NULL CHECK (units_consumed >= 0),
    energy_charge    DECIMAL(10,2) NOT NULL,
    fixed_charge     DECIMAL(10,2) NOT NULL,
    total_amount     DECIMAL(10,2) NOT NULL,
    bill_date        DATE NOT NULL,
    due_date         DATE NOT NULL,
    status           ENUM('UNPAID','PAID') NOT NULL DEFAULT 'UNPAID',
    FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id) ON DELETE CASCADE,
    FOREIGN KEY (reading_id)  REFERENCES meter_readings(reading_id) ON DELETE CASCADE
);

CREATE TABLE payments (
    payment_id   INT AUTO_INCREMENT PRIMARY KEY,
    bill_id      INT NOT NULL UNIQUE,              -- a bill is paid once, in full
    amount_paid  DECIMAL(10,2) NOT NULL,
    payment_date DATE NOT NULL,
    method       ENUM('CASH','UPI','CARD','NET_BANKING') NOT NULL,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE
);

-- Trigger: when a payment is recorded, mark its bill as PAID automatically
DELIMITER //
CREATE TRIGGER trg_payment_marks_bill_paid
AFTER INSERT ON payments
FOR EACH ROW
BEGIN
    UPDATE bills SET status = 'PAID' WHERE bill_id = NEW.bill_id;
END //
DELIMITER ;

-- View used by the bills list and dashboard
CREATE VIEW v_bill_details AS
SELECT b.bill_id, b.bill_date, b.due_date, b.units_consumed, b.total_amount, b.status,
       c.consumer_id, c.service_no, c.name, c.connection_type,
       (b.status = 'UNPAID' AND b.due_date < CURDATE()) AS is_overdue
FROM bills b
JOIN consumers c ON c.consumer_id = b.consumer_id;

-- Indexes for the common lookups
CREATE INDEX idx_readings_consumer_date ON meter_readings(consumer_id, reading_date);
CREATE INDEX idx_bills_status ON bills(status);
