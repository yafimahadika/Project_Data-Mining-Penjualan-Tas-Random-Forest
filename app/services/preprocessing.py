from math import ceil

import pandas as pd

from app.db import get_db, query


def ensure_preprocessed_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
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
        )
        """
    )
    conn.commit()
    cursor.close()


def get_preprocessing_summary():
    ensure_preprocessed_table()
    summary = {
        "raw_rows": 0,
        "finished_rows": 0,
        "canceled_rows": 0,
        "unique_buyers": 0,
        "duplicate_orders": 0,
        "missing_username": 0,
        "missing_sku": 0,
        "ready_rows": 0,
        "last_processed": None,
    }

    raw = query("SELECT COUNT(*) AS total FROM shopee_orders", fetchone=True)
    if not raw:
        return summary

    summary.update(
        {
            "raw_rows": raw["total"],
            "finished_rows": query(
                "SELECT COUNT(*) AS total FROM shopee_orders WHERE order_status = 'Selesai'",
                fetchone=True,
            )["total"],
            "canceled_rows": query(
                "SELECT COUNT(*) AS total FROM shopee_orders WHERE order_status = 'Batal'",
                fetchone=True,
            )["total"],
            "unique_buyers": query(
                "SELECT COUNT(DISTINCT buyer_username) AS total FROM shopee_orders WHERE buyer_username IS NOT NULL",
                fetchone=True,
            )["total"],
            "duplicate_orders": query(
                """
                SELECT COALESCE(SUM(total_duplicate), 0) AS total
                FROM (
                    SELECT COUNT(*) - 1 AS total_duplicate
                    FROM shopee_orders
                    GROUP BY order_number
                    HAVING COUNT(*) > 1
                ) duplicates
                """,
                fetchone=True,
            )["total"],
            "missing_username": query(
                "SELECT COUNT(*) AS total FROM shopee_orders WHERE buyer_username IS NULL",
                fetchone=True,
            )["total"],
            "missing_sku": query(
                "SELECT COUNT(*) AS total FROM shopee_orders WHERE sku_reference IS NULL",
                fetchone=True,
            )["total"],
            "ready_rows": query("SELECT COUNT(*) AS total FROM preprocessed_sales", fetchone=True)["total"],
        }
    )
    processed = query(
        "SELECT MAX(processed_at) AS processed_at FROM preprocessed_sales",
        fetchone=True,
    )
    summary["last_processed"] = processed["processed_at"] if processed else None
    return summary


def most_common(series):
    mode = series.dropna().mode()
    return None if mode.empty else mode.iloc[0]


def run_preprocessing():
    ensure_preprocessed_table()
    rows = query(
        """
        SELECT order_number, buyer_username, quantity, total_payment_rupiah,
               payment_method, city, province, sku_reference, order_created_at
        FROM shopee_orders
        WHERE order_status = 'Selesai'
          AND buyer_username IS NOT NULL
          AND order_number IS NOT NULL
        """
    )
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE preprocessed_sales")

    if not rows:
        conn.commit()
        cursor.close()
        return {"processed_rows": 0}

    frame = pd.DataFrame(rows)
    frame["total_payment_rupiah"] = pd.to_numeric(frame["total_payment_rupiah"])
    frame["quantity"] = pd.to_numeric(frame["quantity"])
    frame["order_created_at"] = pd.to_datetime(frame["order_created_at"], errors="coerce")
    frame["is_cod"] = frame["payment_method"].fillna("").str.contains("COD", case=False).astype(int)
    frame["is_online"] = 1 - frame["is_cod"]

    order_level = (
        frame.groupby(["buyer_username", "order_number"], as_index=False)
        .agg(
            total_payment_rupiah=("total_payment_rupiah", "max"),
            quantity=("quantity", "sum"),
            order_created_at=("order_created_at", "min"),
            payment_method=("payment_method", most_common),
            city=("city", most_common),
            province=("province", most_common),
            sku_reference=("sku_reference", most_common),
            is_cod=("is_cod", "max"),
            is_online=("is_online", "max"),
        )
    )

    customer_level = (
        order_level.groupby("buyer_username", as_index=False)
        .agg(
            total_orders=("order_number", "nunique"),
            total_quantity=("quantity", "sum"),
            total_spent_rupiah=("total_payment_rupiah", "sum"),
            average_order_rupiah=("total_payment_rupiah", "mean"),
            cod_orders=("is_cod", "sum"),
            online_orders=("is_online", "sum"),
            first_order=("order_created_at", "min"),
            last_order=("order_created_at", "max"),
            dominant_payment_method=("payment_method", most_common),
            dominant_city=("city", most_common),
            dominant_province=("province", most_common),
            dominant_sku=("sku_reference", most_common),
        )
    )

    customer_level["days_since_first_order"] = (
        customer_level["last_order"] - customer_level["first_order"]
    ).dt.days.fillna(0)
    spent_q75 = customer_level["total_spent_rupiah"].quantile(0.75)
    frequency_threshold = max(2, ceil(customer_level["total_orders"].quantile(0.75)))

    def label(row):
        if row["total_spent_rupiah"] >= spent_q75 and row["total_orders"] >= frequency_threshold:
            return "Pelanggan Premium"
        if row["total_orders"] >= frequency_threshold:
            return "Pelanggan Aktif"
        if row["total_spent_rupiah"] >= spent_q75:
            return "Pelanggan Potensial"
        return "Pelanggan Reguler"

    customer_level["segment_label"] = customer_level.apply(label, axis=1)

    insert_sql = """
        INSERT INTO preprocessed_sales (
            buyer_username, total_orders, total_quantity, total_spent_rupiah,
            average_order_rupiah, cod_orders, online_orders, dominant_payment_method,
            dominant_city, dominant_province, dominant_sku, days_since_first_order,
            segment_label
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = [
        (
            row["buyer_username"],
            int(row["total_orders"]),
            int(row["total_quantity"]),
            float(row["total_spent_rupiah"]),
            float(row["average_order_rupiah"]),
            int(row["cod_orders"]),
            int(row["online_orders"]),
            row["dominant_payment_method"],
            row["dominant_city"],
            row["dominant_province"],
            row["dominant_sku"],
            int(row["days_since_first_order"]),
            row["segment_label"],
        )
        for _, row in customer_level.iterrows()
    ]
    cursor.executemany(insert_sql, values)
    conn.commit()
    cursor.close()
    return {"processed_rows": len(values)}
