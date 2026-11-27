-- Sample data. Run after schema.sql:  mysql -u root -p < seed.sql

-- Tariff (sample values, editable from the Tariff page)
INSERT INTO tariff_slabs (connection_type, from_unit, to_unit, rate_per_unit) VALUES
('DOMESTIC',     1, 100, 0.00),
('DOMESTIC',   101, 200, 2.35),
('DOMESTIC',   201, 400, 4.70),
('DOMESTIC',   401, 500, 6.30),
('DOMESTIC',   501, NULL, 8.40),
('COMMERCIAL',   1, 100, 5.00),
('COMMERCIAL', 101, NULL, 8.50);

INSERT INTO fixed_charges (connection_type, amount) VALUES
('DOMESTIC', 50.00),
('COMMERCIAL', 150.00);

INSERT INTO consumers (service_no, name, address, phone, email, connection_type, initial_reading) VALUES
('TN0001', 'Arun Kumar',   '12, Gandhi Street, Thanjavur',    '9876543210', 'arun@example.com',  'DOMESTIC',   1200),
('TN0002', 'Priya S',      '45, Anna Nagar, Trichy',          '9876501234', 'priya@example.com', 'DOMESTIC',    850),
('TN0003', 'Sri Murugan Stores', '3, Main Bazaar, Kumbakonam', '9894012345', NULL,               'COMMERCIAL', 5000);
