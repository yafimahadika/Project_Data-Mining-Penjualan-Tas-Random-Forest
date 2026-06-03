CREATE DATABASE IF NOT EXISTS project_maria
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE project_maria;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'pimpinan') NOT NULL DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    gender ENUM('L', 'P') NOT NULL,
    age INT NOT NULL,
    city VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    product_category VARCHAR(100) NOT NULL,
    quantity INT NOT NULL,
    total_amount DECIMAL(14, 2) NOT NULL,
    purchase_channel ENUM('Online', 'Offline', 'Marketplace') NOT NULL,
    purchase_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transactions_customer
        FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    predicted_segment VARCHAR(80) NOT NULL,
    confidence DECIMAL(6, 5),
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_predictions_customer
        FOREIGN KEY (customer_id) REFERENCES customers(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL DEFAULT 'Random Forest',
    accuracy DECIMAL(6, 5) NOT NULL,
    precision_score DECIMAL(6, 5),
    recall_score DECIMAL(6, 5),
    f1_score DECIMAL(6, 5),
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shopee_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_file VARCHAR(120) NOT NULL,
    order_number VARCHAR(50) NOT NULL,
    order_status VARCHAR(40) NOT NULL,
    cancel_reason TEXT,
    tracking_number VARCHAR(80),
    shipping_option VARCHAR(150),
    shipment_type VARCHAR(80),
    order_created_at DATETIME NOT NULL,
    paid_at DATETIME,
    completed_at DATETIME,
    payment_method VARCHAR(100),
    product_name VARCHAR(255),
    sku_reference VARCHAR(150),
    variation_name VARCHAR(120),
    price_after_discount_raw DECIMAL(14, 3) DEFAULT 0,
    price_after_discount_rupiah DECIMAL(16, 2) DEFAULT 0,
    quantity INT DEFAULT 0,
    returned_quantity INT DEFAULT 0,
    total_product_price_raw DECIMAL(14, 3) DEFAULT 0,
    total_product_price_rupiah DECIMAL(16, 2) DEFAULT 0,
    total_payment_raw DECIMAL(14, 3) DEFAULT 0,
    total_payment_rupiah DECIMAL(16, 2) DEFAULT 0,
    buyer_username VARCHAR(120),
    recipient_name VARCHAR(120),
    city VARCHAR(120),
    province VARCHAR(120),
    buyer_note TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_shopee_order_number (order_number),
    INDEX idx_shopee_status (order_status),
    INDEX idx_shopee_buyer (buyer_username),
    INDEX idx_shopee_created_at (order_created_at)
);

CREATE TABLE IF NOT EXISTS shopee_customer_segments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    buyer_username VARCHAR(120) NOT NULL UNIQUE,
    total_orders INT NOT NULL DEFAULT 0,
    total_quantity INT NOT NULL DEFAULT 0,
    total_spent_rupiah DECIMAL(16, 2) NOT NULL DEFAULT 0,
    average_order_rupiah DECIMAL(16, 2) NOT NULL DEFAULT 0,
    first_order_at DATETIME,
    last_order_at DATETIME,
    segment_label VARCHAR(80) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preprocessed_sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    buyer_username VARCHAR(120) NOT NULL UNIQUE,
    total_orders INT NOT NULL DEFAULT 0,
    total_quantity INT NOT NULL DEFAULT 0,
    total_spent_rupiah DECIMAL(16, 2) NOT NULL DEFAULT 0,
    average_order_rupiah DECIMAL(16, 2) NOT NULL DEFAULT 0,
    cod_orders INT NOT NULL DEFAULT 0,
    online_orders INT NOT NULL DEFAULT 0,
    dominant_payment_method VARCHAR(100),
    dominant_city VARCHAR(120),
    dominant_province VARCHAR(120),
    dominant_sku VARCHAR(150),
    days_since_first_order INT NOT NULL DEFAULT 0,
    segment_label VARCHAR(80) NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_preprocessed_segment (segment_label)
);

CREATE TABLE IF NOT EXISTS model_training_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL DEFAULT 'Random Forest',
    total_rows INT NOT NULL,
    train_rows INT NOT NULL,
    test_rows INT NOT NULL,
    accuracy DECIMAL(6, 5) NOT NULL,
    precision_score DECIMAL(6, 5) NOT NULL,
    recall_score DECIMAL(6, 5) NOT NULL,
    f1_score DECIMAL(6, 5) NOT NULL,
    labels_json LONGTEXT NOT NULL,
    confusion_matrix_json LONGTEXT NOT NULL,
    classification_report_text LONGTEXT NOT NULL,
    feature_columns_json LONGTEXT NOT NULL,
    model_path VARCHAR(255),
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prediction_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    buyer_username VARCHAR(120),
    total_orders INT NOT NULL DEFAULT 0,
    total_quantity INT NOT NULL DEFAULT 0,
    total_spent_rupiah DECIMAL(16, 2) NOT NULL DEFAULT 0,
    average_order_rupiah DECIMAL(16, 2) NOT NULL DEFAULT 0,
    cod_orders INT NOT NULL DEFAULT 0,
    online_orders INT NOT NULL DEFAULT 0,
    days_since_first_order INT NOT NULL DEFAULT 0,
    dominant_payment_method VARCHAR(100),
    dominant_province VARCHAR(120),
    dominant_sku VARCHAR(150),
    predicted_segment VARCHAR(80) NOT NULL,
    confidence DECIMAL(8, 6),
    probabilities_json LONGTEXT,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_prediction_segment (predicted_segment),
    INDEX idx_prediction_time (predicted_at)
);

INSERT INTO users (name, username, password_hash, role)
SELECT 'Administrator', 'admin', 'scrypt:32768:8:1$pCBrgylWOD5GtxVY$0e7a2901a25756b1483d3f05c5fd28289175b5d4a5b8e0dd3d9e9380935c252437efcd310b2ee2dee1d0d158e5753ec9e3df6563f7b090ce9541633f56d1803c', 'admin'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');
