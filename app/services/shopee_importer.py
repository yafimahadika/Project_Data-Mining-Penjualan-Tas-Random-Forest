from math import ceil
from pathlib import Path

import pandas as pd

from app.db import get_db

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


def segment_label(row, spent_q75, frequency_threshold):
    if row["total_spent_rupiah"] >= spent_q75 and row["total_orders"] >= frequency_threshold:
        return "Pelanggan Premium"
    if row["total_orders"] >= frequency_threshold:
        return "Pelanggan Aktif"
    if row["total_spent_rupiah"] >= spent_q75:
        return "Pelanggan Potensial"
    return "Pelanggan Reguler"


def import_excel_file(path, source_name=None):
    path = Path(path)
    source_file = source_name or path.name
    orders = pd.read_excel(path, sheet_name="orders")
    orders["source_file"] = source_file

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM shopee_orders WHERE source_file IN (%s, %s)",
        (source_file, path.name),
    )

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

    conn.commit()
    cursor.close()
    rebuild_customer_segments()
    return len(rows)


def rebuild_customer_segments():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("TRUNCATE TABLE shopee_customer_segments")
    cursor.execute(
        """
        SELECT buyer_username, order_number,
               MAX(total_payment_rupiah) AS total_payment_rupiah,
               SUM(quantity) AS quantity,
               MIN(order_created_at) AS order_created_at
        FROM shopee_orders
        WHERE order_status = 'Selesai' AND buyer_username IS NOT NULL
        GROUP BY buyer_username, order_number
        """
    )
    order_rows = cursor.fetchall()
    if not order_rows:
        conn.commit()
        cursor.close()
        return

    order_level = pd.DataFrame(order_rows)
    customer_level = (
        order_level.groupby("buyer_username", as_index=False)
        .agg(
            total_orders=("order_number", "nunique"),
            total_quantity=("quantity", "sum"),
            total_spent_rupiah=("total_payment_rupiah", "sum"),
            first_order_at=("order_created_at", "min"),
            last_order_at=("order_created_at", "max"),
        )
    )
    customer_level["average_order_rupiah"] = (
        customer_level["total_spent_rupiah"] / customer_level["total_orders"]
    )
    customer_level["total_orders"] = pd.to_numeric(customer_level["total_orders"])
    customer_level["total_quantity"] = pd.to_numeric(customer_level["total_quantity"])
    customer_level["total_spent_rupiah"] = pd.to_numeric(customer_level["total_spent_rupiah"])
    customer_level["average_order_rupiah"] = pd.to_numeric(customer_level["average_order_rupiah"])

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
            row["buyer_username"],
            int(row["total_orders"]),
            int(row["total_quantity"]),
            float(row["total_spent_rupiah"]),
            float(row["average_order_rupiah"]),
            row["first_order_at"],
            row["last_order_at"],
            row["segment_label"],
        )
        for _, row in customer_level.iterrows()
    ]
    plain_cursor = conn.cursor()
    for start in range(0, len(segment_rows), BATCH_SIZE):
        plain_cursor.executemany(segment_sql, segment_rows[start:start + BATCH_SIZE])
    conn.commit()
    plain_cursor.close()
    cursor.close()
