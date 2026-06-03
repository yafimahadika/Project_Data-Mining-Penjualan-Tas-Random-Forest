from pathlib import Path
from math import ceil

import mysql.connector
import pandas as pd
from dotenv import load_dotenv
import os


load_dotenv()

FILES = [
    Path(r"C:\Users\Bicom\Downloads\Juni 2024.xlsx"),
    Path(r"C:\Users\Bicom\Downloads\Juli 2024.xlsx"),
]

MONEY_MULTIPLIER = 1000
BATCH_SIZE = 500


def clean_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return None if value in {"", "-"} else value
    return value


def parse_datetime(value):
    value = clean_value(value)
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def number(value, default=0):
    value = clean_value(value)
    if value is None:
        return default
    return float(value)


def integer(value, default=0):
    value = clean_value(value)
    if value is None:
        return default
    return int(value)


def connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "project_maria"),
    )


def ensure_tables(cursor):
    cursor.execute(
        """
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
        )
        """
    )
    cursor.execute(
        """
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
        )
        """
    )


def segment_label(row, spent_q75, frequency_threshold):
    if row["total_spent_rupiah"] >= spent_q75 and row["total_orders"] >= frequency_threshold:
        return "Pelanggan Premium"
    if row["total_orders"] >= frequency_threshold:
        return "Pelanggan Aktif"
    if row["total_spent_rupiah"] >= spent_q75:
        return "Pelanggan Potensial"
    return "Pelanggan Reguler"


def main():
    frames = []
    for path in FILES:
        if not path.exists():
            raise FileNotFoundError(path)
        df = pd.read_excel(path, sheet_name="orders")
        df["source_file"] = path.name
        frames.append(df)

    orders = pd.concat(frames, ignore_index=True)
    conn = connection()
    cursor = conn.cursor()
    ensure_tables(cursor)
    cursor.execute("TRUNCATE TABLE shopee_customer_segments")
    cursor.execute("TRUNCATE TABLE shopee_orders")

    insert_sql = """
        INSERT INTO shopee_orders (
            source_file, order_number, order_status, cancel_reason, tracking_number,
            shipping_option, shipment_type, order_created_at, paid_at, completed_at,
            payment_method, product_name, sku_reference, variation_name,
            price_after_discount_raw, price_after_discount_rupiah, quantity,
            returned_quantity, total_product_price_raw, total_product_price_rupiah,
            total_payment_raw, total_payment_rupiah, buyer_username, recipient_name,
            city, province, buyer_note
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """

    rows = []
    for _, row in orders.iterrows():
        price_raw = number(row.get("Harga Setelah Diskon"))
        total_product_raw = number(row.get("Total Harga Produk"))
        total_payment_raw = number(row.get("Total Pembayaran"))
        rows.append(
            (
                row["source_file"],
                clean_value(row.get("No. Pesanan")),
                clean_value(row.get("Status Pesanan")),
                clean_value(row.get("Alasan Pembatalan")),
                clean_value(row.get("No. Resi")),
                clean_value(row.get("Opsi Pengiriman")),
                clean_value(row.get("Antar ke counter/ pick-up")),
                parse_datetime(row.get("Waktu Pesanan Dibuat")),
                parse_datetime(row.get("Waktu Pembayaran Dilakukan")),
                parse_datetime(row.get("Waktu Pesanan Selesai")),
                clean_value(row.get("Metode Pembayaran")),
                clean_value(row.get("Nama Produk")),
                clean_value(row.get("Nomor Referensi SKU")),
                clean_value(row.get("Nama Variasi")),
                price_raw,
                price_raw * MONEY_MULTIPLIER,
                integer(row.get("Jumlah")),
                integer(row.get("Returned quantity")),
                total_product_raw,
                total_product_raw * MONEY_MULTIPLIER,
                total_payment_raw,
                total_payment_raw * MONEY_MULTIPLIER,
                clean_value(row.get("Username (Pembeli)")),
                clean_value(row.get("Nama Penerima")),
                clean_value(row.get("Kota/Kabupaten")),
                clean_value(row.get("Provinsi")),
                clean_value(row.get("Catatan dari Pembeli")),
            )
        )

    for start in range(0, len(rows), BATCH_SIZE):
        cursor.executemany(insert_sql, rows[start:start + BATCH_SIZE])

    finished = orders[orders["Status Pesanan"].eq("Selesai")].copy()
    finished["order_created_at"] = pd.to_datetime(
        finished["Waktu Pesanan Dibuat"], errors="coerce"
    )
    finished["total_payment_rupiah"] = (
        pd.to_numeric(finished["Total Pembayaran"], errors="coerce").fillna(0)
        * MONEY_MULTIPLIER
    )
    finished["quantity"] = pd.to_numeric(finished["Jumlah"], errors="coerce").fillna(0)

    order_level = (
        finished.dropna(subset=["Username (Pembeli)"])
        .groupby(["Username (Pembeli)", "No. Pesanan"], as_index=False)
        .agg(
            total_payment_rupiah=("total_payment_rupiah", "max"),
            quantity=("quantity", "sum"),
            order_created_at=("order_created_at", "min"),
        )
    )
    customer_level = (
        order_level.groupby("Username (Pembeli)", as_index=False)
        .agg(
            total_orders=("No. Pesanan", "nunique"),
            total_quantity=("quantity", "sum"),
            total_spent_rupiah=("total_payment_rupiah", "sum"),
            first_order_at=("order_created_at", "min"),
            last_order_at=("order_created_at", "max"),
        )
    )
    customer_level["average_order_rupiah"] = (
        customer_level["total_spent_rupiah"] / customer_level["total_orders"]
    )

    spent_q75 = customer_level["total_spent_rupiah"].quantile(0.75)
    order_q75 = customer_level["total_orders"].quantile(0.75)
    frequency_threshold = max(2, ceil(order_q75))
    customer_level["segment_label"] = customer_level.apply(
        lambda item: segment_label(item, spent_q75, frequency_threshold),
        axis=1,
    )

    segment_sql = """
        INSERT INTO shopee_customer_segments (
            buyer_username, total_orders, total_quantity, total_spent_rupiah,
            average_order_rupiah, first_order_at, last_order_at, segment_label
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    segment_rows = [
        (
            row["Username (Pembeli)"],
            int(row["total_orders"]),
            int(row["total_quantity"]),
            float(row["total_spent_rupiah"]),
            float(row["average_order_rupiah"]),
            row["first_order_at"].to_pydatetime(),
            row["last_order_at"].to_pydatetime(),
            row["segment_label"],
        )
        for _, row in customer_level.iterrows()
    ]
    for start in range(0, len(segment_rows), BATCH_SIZE):
        cursor.executemany(segment_sql, segment_rows[start:start + BATCH_SIZE])
    conn.commit()
    cursor.close()
    conn.close()

    print(f"Imported order rows: {len(rows)}")
    print(f"Imported customer segments: {len(segment_rows)}")
    print(f"Finished unique orders: {order_level['No. Pesanan'].nunique()}")
    print(f"Finished revenue rupiah: {order_level['total_payment_rupiah'].sum():,.0f}")


if __name__ == "__main__":
    main()
