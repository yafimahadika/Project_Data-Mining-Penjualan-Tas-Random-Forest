from datetime import datetime
from io import BytesIO

import pandas as pd

from app.db import query


def _rupiah(value):
    return f"Rp {float(value or 0):,.0f}".replace(",", ".")


def _rows(sql, params=None):
    try:
        return query(sql, params or ())
    except Exception:
        return []


def _one(sql, params=None):
    try:
        return query(sql, params or (), fetchone=True) or {}
    except Exception:
        return {}


def get_report_context():
    raw_orders = _one("SELECT COUNT(*) AS total FROM shopee_orders").get("total", 0)
    finished_orders = _one(
        """
        SELECT COUNT(*) AS total
        FROM (
            SELECT order_number
            FROM shopee_orders
            WHERE order_status = 'Selesai'
            GROUP BY order_number
        ) finished_orders
        """
    ).get("total", 0)
    customers = _one("SELECT COUNT(*) AS total FROM shopee_customer_segments").get("total", 0)
    ready_rows = _one("SELECT COUNT(*) AS total FROM preprocessed_sales").get("total", 0)
    prediction_total = _one("SELECT COUNT(*) AS total FROM prediction_results").get("total", 0)
    revenue = _one(
        """
        SELECT COALESCE(SUM(order_payment), 0) AS total
        FROM (
            SELECT order_number, MAX(total_payment_rupiah) AS order_payment
            FROM shopee_orders
            WHERE order_status = 'Selesai'
            GROUP BY order_number
        ) order_totals
        """
    ).get("total", 0)
    latest_model = _one(
        """
        SELECT accuracy, precision_score, recall_score, f1_score, trained_at, total_rows, train_rows, test_rows
        FROM model_training_results
        ORDER BY trained_at DESC
        LIMIT 1
        """
    )
    segment_rows = _rows(
        """
        SELECT segment_label, COUNT(*) AS total,
               SUM(total_spent_rupiah) AS revenue,
               AVG(average_order_rupiah) AS average_order
        FROM preprocessed_sales
        GROUP BY segment_label
        ORDER BY total DESC
        """
    )
    prediction_rows = _rows(
        """
        SELECT predicted_segment, COUNT(*) AS total, AVG(confidence) AS average_confidence
        FROM prediction_results
        GROUP BY predicted_segment
        ORDER BY total DESC
        """
    )
    top_products = _rows(
        """
        SELECT COALESCE(sku_reference, variation_name, product_name, 'Tanpa SKU') AS product_name,
               SUM(quantity) AS total_quantity,
               SUM(total_product_price_rupiah) AS total_revenue
        FROM shopee_orders
        WHERE order_status = 'Selesai'
        GROUP BY COALESCE(sku_reference, variation_name, product_name, 'Tanpa SKU')
        ORDER BY total_quantity DESC
        LIMIT 8
        """
    )
    payment_rows = _rows(
        """
        SELECT payment_method, COUNT(DISTINCT order_number) AS total_orders
        FROM shopee_orders
        WHERE order_status = 'Selesai'
        GROUP BY payment_method
        ORDER BY total_orders DESC
        LIMIT 8
        """
    )
    province_rows = _rows(
        """
        SELECT dominant_province AS province, COUNT(*) AS total_customers
        FROM preprocessed_sales
        GROUP BY dominant_province
        ORDER BY total_customers DESC
        LIMIT 8
        """
    )

    summary = {
        "raw_orders": raw_orders,
        "finished_orders": finished_orders,
        "customers": customers,
        "ready_rows": ready_rows,
        "prediction_total": prediction_total,
        "revenue": revenue,
        "revenue_display": _rupiah(revenue),
        "accuracy": f"{latest_model['accuracy'] * 100:.2f}%" if latest_model else "Belum Training",
    }

    chart_data = {
        "segments": {
            "labels": [row["segment_label"] for row in segment_rows],
            "values": [int(row["total"]) for row in segment_rows],
        },
        "products": {
            "labels": [row["product_name"] for row in top_products],
            "values": [int(row["total_quantity"] or 0) for row in top_products],
        },
        "payments": {
            "labels": [row["payment_method"] or "Tidak Diketahui" for row in payment_rows],
            "values": [int(row["total_orders"]) for row in payment_rows],
        },
    }

    return {
        "summary": summary,
        "latest_model": latest_model,
        "segment_rows": segment_rows,
        "prediction_rows": prediction_rows,
        "top_products": top_products,
        "payment_rows": payment_rows,
        "province_rows": province_rows,
        "chart_data": chart_data,
        "generated_at": datetime.now(),
    }


def build_report_excel():
    context = get_report_context()
    output = BytesIO()

    summary_rows = [
        {"Keterangan": "Total baris dataset", "Nilai": context["summary"]["raw_orders"]},
        {"Keterangan": "Order selesai", "Nilai": context["summary"]["finished_orders"]},
        {"Keterangan": "Pembeli selesai", "Nilai": context["summary"]["customers"]},
        {"Keterangan": "Data siap training", "Nilai": context["summary"]["ready_rows"]},
        {"Keterangan": "Riwayat prediksi manual", "Nilai": context["summary"]["prediction_total"]},
        {"Keterangan": "Total penjualan", "Nilai": context["summary"]["revenue_display"]},
        {"Keterangan": "Akurasi model terakhir", "Nilai": context["summary"]["accuracy"]},
        {"Keterangan": "Tanggal laporan", "Nilai": context["generated_at"].strftime("%Y-%m-%d %H:%M:%S")},
    ]
    model = context["latest_model"] or {}
    model_rows = [
        {
            "Akurasi": float(model.get("accuracy", 0)) if model else None,
            "Precision": float(model.get("precision_score", 0)) if model else None,
            "Recall": float(model.get("recall_score", 0)) if model else None,
            "F1-score": float(model.get("f1_score", 0)) if model else None,
            "Total Data": model.get("total_rows"),
            "Train": model.get("train_rows"),
            "Test": model.get("test_rows"),
            "Waktu Training": model.get("trained_at"),
        }
    ]
    manual_predictions = _rows(
        """
        SELECT buyer_username, total_orders, total_quantity, total_spent_rupiah,
               dominant_payment_method, dominant_province, dominant_sku,
               predicted_segment, confidence, predicted_at
        FROM prediction_results
        ORDER BY predicted_at DESC
        """
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="Ringkasan")
        pd.DataFrame(context["segment_rows"]).to_excel(writer, index=False, sheet_name="Segmentasi")
        pd.DataFrame(model_rows).to_excel(writer, index=False, sheet_name="Metrik Model")
        pd.DataFrame(manual_predictions).to_excel(writer, index=False, sheet_name="Prediksi Manual")
        pd.DataFrame(context["top_products"]).to_excel(writer, index=False, sheet_name="Produk Teratas")
        pd.DataFrame(context["payment_rows"]).to_excel(writer, index=False, sheet_name="Pembayaran")
        pd.DataFrame(context["province_rows"]).to_excel(writer, index=False, sheet_name="Provinsi")

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            for column_cells in worksheet.columns:
                max_length = max(len(str(cell.value or "")) for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(max_length + 3, 42)

    output.seek(0)
    filename = f"laporan_segmentasi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return output, filename
