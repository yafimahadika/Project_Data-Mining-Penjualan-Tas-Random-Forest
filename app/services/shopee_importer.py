from math import ceil, isfinite
from pathlib import Path
import re

import pandas as pd

from app.db import get_db

MONEY_MULTIPLIER = 1000
BATCH_SIZE = 500


def clean_value(value):
    if isinstance(value, str):
        value = value.strip()
        return None if value in {"", "-"} else value
    if value is None or pd.isna(value):
        return None
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
    if isinstance(value, str):
        value = re.sub(r"(?i)^rp\.?\s*", "", value).replace(" ", "").replace("\u00a0", "")
        # Shopee exports text money with Indonesian thousands/decimal separators.
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", value):
            value = value.replace(".", "")
    result = float(value)
    if not isfinite(result):
        raise ValueError("Angka harus bernilai terbatas.")
    return result


def integer(value, default=0):
    value = clean_value(value)
    if value is None:
        return default
    result = number(value)
    if not result.is_integer():
        raise ValueError("Jumlah produk harus berupa bilangan bulat.")
    return int(result)


def segment_label(row, spent_q75, frequency_threshold):
    if row["total_spent_rupiah"] >= spent_q75 and row["total_orders"] >= frequency_threshold:
        return "Pelanggan Premium"
    if row["total_orders"] >= frequency_threshold:
        return "Pelanggan Aktif"
    if row["total_spent_rupiah"] >= spent_q75:
        return "Pelanggan Potensial"
    return "Pelanggan Reguler"


def prepare_excel_rows(path, source_name=None):
    path = Path(path)
    source_file = source_name or path.name
    try:
        from python_calamine import CalamineWorkbook
    except ImportError:
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            sheet = orders_sheet_name(workbook.sheet_names)
            orders = pd.read_excel(workbook, sheet_name=sheet, dtype=object)
    else:
        # Read directly to avoid pandas converting every cell of the 50-column export.
        with CalamineWorkbook.from_path(path) as workbook:
            sheet = orders_sheet_name(workbook.sheet_names)
            data = workbook.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
        if not data:
            raise ValueError("Sheet orders tidak berisi data pesanan.")
        orders = pd.DataFrame(data[1:], columns=data[0], dtype=object).replace("", None)
    orders.columns = orders.columns.astype(str).str.strip()
    if "Total Harga Produk" not in orders and "Subtotal Pesanan" in orders:
        orders = orders.rename(columns={"Subtotal Pesanan": "Total Harga Produk"})
    required = {"No. Pesanan", "Status Pesanan", "Waktu Pesanan Dibuat", "Harga Setelah Diskon",
                "Jumlah", "Total Harga Produk", "Total Pembayaran", "Username (Pembeli)"}
    missing = sorted(required - set(orders.columns))
    if missing:
        raise ValueError("Kolom wajib belum tersedia: " + ", ".join(missing))
    orders = orders.dropna(how="all")
    if orders.empty:
        raise ValueError("Sheet orders tidak berisi data pesanan.")
    # Parse entire columns once instead of calling pandas once per cell.
    for column in ("Waktu Pesanan Dibuat", "Waktu Pembayaran Dilakukan", "Waktu Pesanan Selesai"):
        if column in orders:
            orders[column] = pd.to_datetime(orders[column], format="mixed", errors="coerce")
    rows = []
    for excel_index, values in zip(orders.index, orders.itertuples(index=False, name=None)):
        row = dict(zip(orders.columns, values))
        try:
            if not clean_value(row.get("No. Pesanan")) or not clean_value(row.get("Status Pesanan")):
                raise ValueError("No. Pesanan dan Status Pesanan wajib diisi.")
            if pd.isna(row.get("Waktu Pesanan Dibuat")):
                raise ValueError("Waktu Pesanan Dibuat kosong atau tidak valid.")
            price_rupiah = number(row.get("Harga Setelah Diskon"))
            total_product_rupiah = number(row.get("Total Harga Produk"))
            total_payment_rupiah = number(row.get("Total Pembayaran"))
            rows.append(
                (
                    source_file,
                    clean_value(row.get("No. Pesanan")),
                    clean_value(row.get("Status Pesanan")),
                    clean_value(row.get("Alasan Pembatalan")),
                    clean_value(row.get("No. Resi")),
                    clean_value(row.get("Opsi Pengiriman")),
                    clean_value(row.get("Antar ke counter/ pick-up")),
                    row["Waktu Pesanan Dibuat"].to_pydatetime(),
                    datetime_or_none(row.get("Waktu Pembayaran Dilakukan")),
                    datetime_or_none(row.get("Waktu Pesanan Selesai")),
                    clean_value(row.get("Metode Pembayaran")),
                    clean_value(row.get("Nama Produk")),
                    clean_value(row.get("Nomor Referensi SKU")),
                    clean_value(row.get("Nama Variasi")),
                    price_rupiah / MONEY_MULTIPLIER,
                    price_rupiah,
                    integer(row.get("Jumlah")),
                    integer(row.get("Returned quantity")),
                    total_product_rupiah / MONEY_MULTIPLIER,
                    total_product_rupiah,
                    total_payment_rupiah / MONEY_MULTIPLIER,
                    total_payment_rupiah,
                    clean_value(row.get("Username (Pembeli)")),
                    clean_value(row.get("Nama Penerima")),
                    clean_value(row.get("Kota/Kabupaten")),
                    clean_value(row.get("Provinsi")),
                    clean_value(row.get("Catatan dari Pembeli")),
                )
            )
        except (ValueError, TypeError, OverflowError) as error:
            raise ValueError(f"Baris Excel {excel_index + 2}: {error}") from error
    return rows


def orders_sheet_name(sheet_names):
    sheets = {name.strip().lower(): name for name in sheet_names}
    if "orders" not in sheets:
        raise ValueError("File harus memiliki sheet 'orders' dari ekspor pesanan Shopee.")
    return sheets["orders"]


def datetime_or_none(value):
    return None if value is None or pd.isna(value) else value.to_pydatetime()


def import_excel_file(path, source_name=None):
    path = Path(path)
    source_file = source_name or path.name
    # Validate everything before replacing an existing import.
    rows = prepare_excel_rows(path, source_file)
    conn = get_db()
    cursor = conn.cursor()
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

    try:
        cursor.execute(
            "DELETE FROM shopee_orders WHERE source_file IN (%s, %s)",
            (source_file, path.name),
        )
        for start in range(0, len(rows), BATCH_SIZE):
            cursor.executemany(insert_sql, rows[start:start + BATCH_SIZE])
        rebuild_customer_segments(commit=False)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
    return len(rows)


def rebuild_customer_segments(commit=True):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("DELETE FROM shopee_customer_segments")
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
        if commit:
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
    high_spend = customer_level["total_spent_rupiah"] >= spent_q75
    frequent = customer_level["total_orders"] >= frequency_threshold
    customer_level["segment_label"] = "Pelanggan Reguler"
    customer_level.loc[high_spend, "segment_label"] = "Pelanggan Potensial"
    customer_level.loc[frequent, "segment_label"] = "Pelanggan Aktif"
    customer_level.loc[high_spend & frequent, "segment_label"] = "Pelanggan Premium"

    segment_sql = """
        INSERT INTO shopee_customer_segments (
            buyer_username, total_orders, total_quantity, total_spent_rupiah,
            average_order_rupiah, first_order_at, last_order_at, segment_label
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    segment_rows = [
        (
            row.buyer_username,
            int(row.total_orders),
            int(row.total_quantity),
            float(row.total_spent_rupiah),
            float(row.average_order_rupiah),
            datetime_or_none(row.first_order_at),
            datetime_or_none(row.last_order_at),
            row.segment_label,
        )
        for row in customer_level.itertuples(index=False)
    ]
    plain_cursor = conn.cursor()
    for start in range(0, len(segment_rows), BATCH_SIZE):
        plain_cursor.executemany(segment_sql, segment_rows[start:start + BATCH_SIZE])
    if commit:
        conn.commit()
    plain_cursor.close()
    cursor.close()
