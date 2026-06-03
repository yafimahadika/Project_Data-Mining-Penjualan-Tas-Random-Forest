USE project_maria;

INSERT INTO customers (name, gender, age, city) VALUES
('Ayu Lestari', 'P', 27, 'Jakarta'),
('Rizky Pratama', 'L', 31, 'Bandung'),
('Nadia Putri', 'P', 24, 'Depok'),
('Dimas Saputra', 'L', 35, 'Bekasi');

INSERT INTO transactions (customer_id, product_category, quantity, total_amount, purchase_channel, purchase_date) VALUES
(1, 'Tote Bag', 2, 450000, 'Marketplace', '2026-01-12'),
(2, 'Backpack', 1, 650000, 'Online', '2026-01-18'),
(3, 'Sling Bag', 3, 720000, 'Offline', '2026-02-05'),
(4, 'Handbag', 1, 520000, 'Marketplace', '2026-02-11');

INSERT INTO predictions (customer_id, predicted_segment, confidence) VALUES
(1, 'Pelanggan Potensial', 0.84000),
(2, 'Pelanggan Premium', 0.91000),
(3, 'Pelanggan Aktif', 0.79000),
(4, 'Pelanggan Potensial', 0.76000);

INSERT INTO model_metrics (accuracy, precision_score, recall_score, f1_score) VALUES
(0.87500, 0.86000, 0.85000, 0.85500);
