import json
from pathlib import Path

import joblib
import pandas as pd
from flask import current_app

from app.db import get_db, query
from app.services.model_training import CATEGORICAL_FEATURES, NUMERIC_FEATURES


MODEL_FILENAME = "random_forest_segmentasi.joblib"


def ensure_prediction_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
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
        )
        """
    )
    conn.commit()
    cursor.close()


def get_model_path():
    latest = query(
        """
        SELECT model_path
        FROM model_training_results
        WHERE model_path IS NOT NULL
        ORDER BY trained_at DESC
        LIMIT 1
        """,
        fetchone=True,
    )
    if latest and latest.get("model_path"):
        path = Path(latest["model_path"])
        if path.exists():
            return path
    return Path(current_app.root_path).parent / "models" / MODEL_FILENAME


def get_latest_training():
    return query(
        """
        SELECT accuracy, precision_score, recall_score, f1_score, trained_at, total_rows
        FROM model_training_results
        ORDER BY trained_at DESC
        LIMIT 1
        """,
        fetchone=True,
    )


def get_prediction_options():
    options = {
        "payment_methods": [],
        "provinces": [],
        "skus": [],
    }
    try:
        options["payment_methods"] = [
            row["value"]
            for row in query(
                """
                SELECT dominant_payment_method AS value
                FROM preprocessed_sales
                WHERE dominant_payment_method IS NOT NULL AND dominant_payment_method <> ''
                GROUP BY dominant_payment_method
                ORDER BY COUNT(*) DESC, dominant_payment_method
                LIMIT 20
                """
            )
        ]
        options["provinces"] = [
            row["value"]
            for row in query(
                """
                SELECT dominant_province AS value
                FROM preprocessed_sales
                WHERE dominant_province IS NOT NULL AND dominant_province <> ''
                GROUP BY dominant_province
                ORDER BY COUNT(*) DESC, dominant_province
                LIMIT 25
                """
            )
        ]
        options["skus"] = [
            row["value"]
            for row in query(
                """
                SELECT dominant_sku AS value
                FROM preprocessed_sales
                WHERE dominant_sku IS NOT NULL AND dominant_sku <> ''
                GROUP BY dominant_sku
                ORDER BY COUNT(*) DESC, dominant_sku
                LIMIT 25
                """
            )
        ]
    except Exception:
        pass
    return options


def get_prediction_history(limit=8):
    ensure_prediction_table()
    rows = query(
        """
        SELECT id, buyer_username, total_orders, total_quantity, total_spent_rupiah,
               dominant_payment_method, dominant_province, dominant_sku,
               predicted_segment, confidence, predicted_at
        FROM prediction_results
        ORDER BY predicted_at DESC, id DESC
        LIMIT %s
        """,
        (limit,),
    )
    return rows


def get_prediction_result(result_id):
    ensure_prediction_table()
    row = query(
        """
        SELECT *
        FROM prediction_results
        WHERE id = %s
        """,
        (result_id,),
        fetchone=True,
    )
    if row and row.get("probabilities_json"):
        row["probabilities"] = json.loads(row["probabilities_json"])
    return row


def get_prediction_context(result_id=None):
    ensure_prediction_table()
    model_path = get_model_path()
    return {
        "latest_training": get_latest_training(),
        "model_available": model_path.exists(),
        "model_path": str(model_path),
        "options": get_prediction_options(),
        "history": get_prediction_history(),
        "selected_result": get_prediction_result(result_id) if result_id else None,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
    }


def _number(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip().replace(".", "").replace(",", ".")
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    return int(round(_number(value, default)))


def predict_segment(form_data):
    ensure_prediction_table()
    model_path = get_model_path()
    if not model_path.exists():
        raise ValueError("Model belum tersedia. Jalankan menu Training Model terlebih dahulu.")

    total_orders = max(_integer(form_data.get("total_orders")), 0)
    total_quantity = max(_integer(form_data.get("total_quantity")), 0)
    total_spent = max(_number(form_data.get("total_spent_rupiah")), 0)
    average_order = _number(form_data.get("average_order_rupiah"))
    if average_order <= 0 and total_orders > 0:
        average_order = total_spent / total_orders
    cod_orders = max(_integer(form_data.get("cod_orders")), 0)
    online_orders = max(_integer(form_data.get("online_orders")), 0)
    days_since_first_order = max(_integer(form_data.get("days_since_first_order")), 0)

    payload = {
        "total_orders": total_orders,
        "total_quantity": total_quantity,
        "total_spent_rupiah": total_spent,
        "average_order_rupiah": average_order,
        "cod_orders": cod_orders,
        "online_orders": online_orders,
        "days_since_first_order": days_since_first_order,
        "dominant_payment_method": form_data.get("dominant_payment_method") or "Tidak Diketahui",
        "dominant_province": form_data.get("dominant_province") or "Tidak Diketahui",
        "dominant_sku": form_data.get("dominant_sku") or "Tidak Diketahui",
    }

    frame = pd.DataFrame([payload], columns=NUMERIC_FEATURES + CATEGORICAL_FEATURES)
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].fillna("Tidak Diketahui").astype(str)

    model = joblib.load(model_path)
    predicted_segment = str(model.predict(frame)[0])
    probabilities = []
    confidence = None
    if hasattr(model, "predict_proba"):
        proba_values = model.predict_proba(frame)[0]
        classes = [str(label) for label in model.classes_]
        probabilities = [
            {"label": label, "value": float(value)}
            for label, value in sorted(
                zip(classes, proba_values),
                key=lambda item: item[1],
                reverse=True,
            )
        ]
        confidence = probabilities[0]["value"] if probabilities else None

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        INSERT INTO prediction_results (
            buyer_username, total_orders, total_quantity, total_spent_rupiah,
            average_order_rupiah, cod_orders, online_orders, days_since_first_order,
            dominant_payment_method, dominant_province, dominant_sku,
            predicted_segment, confidence, probabilities_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            form_data.get("buyer_username") or None,
            payload["total_orders"],
            payload["total_quantity"],
            payload["total_spent_rupiah"],
            payload["average_order_rupiah"],
            payload["cod_orders"],
            payload["online_orders"],
            payload["days_since_first_order"],
            payload["dominant_payment_method"],
            payload["dominant_province"],
            payload["dominant_sku"],
            predicted_segment,
            confidence,
            json.dumps(probabilities),
        ),
    )
    result_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    return {
        "id": result_id,
        "predicted_segment": predicted_segment,
        "confidence": confidence,
        "probabilities": probabilities,
    }
