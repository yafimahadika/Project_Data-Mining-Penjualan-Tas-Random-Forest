import json
from pathlib import Path

import joblib
import pandas as pd
from flask import current_app
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.db import get_db, query

NUMERIC_FEATURES = [
    "total_orders",
    "total_quantity",
    "total_spent_rupiah",
    "average_order_rupiah",
    "cod_orders",
    "online_orders",
    "days_since_first_order",
]

CATEGORICAL_FEATURES = [
    "dominant_payment_method",
    "dominant_province",
    "dominant_sku",
]

TARGET_COLUMN = "segment_label"


def ensure_training_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
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
        )
        """
    )
    conn.commit()
    cursor.close()


def get_training_context():
    ensure_training_table()
    total_ready = query("SELECT COUNT(*) AS total FROM preprocessed_sales", fetchone=True)
    latest = query(
        """
        SELECT *
        FROM model_training_results
        ORDER BY trained_at DESC
        LIMIT 1
        """,
        fetchone=True,
    )
    history = query(
        """
        SELECT id, accuracy, precision_score, recall_score, f1_score,
               total_rows, train_rows, test_rows, trained_at
        FROM model_training_results
        ORDER BY trained_at DESC
        LIMIT 5
        """
    )
    label_rows = query(
        """
        SELECT segment_label, COUNT(*) AS total
        FROM preprocessed_sales
        GROUP BY segment_label
        ORDER BY total DESC
        """
    )
    if latest:
        latest["labels"] = json.loads(latest["labels_json"])
        latest["confusion_matrix"] = json.loads(latest["confusion_matrix_json"])
        latest["feature_columns"] = json.loads(latest["feature_columns_json"])
    return {
        "total_ready": total_ready["total"] if total_ready else 0,
        "latest": latest,
        "history": history,
        "label_rows": label_rows,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
    }


def train_random_forest(test_size=0.2, n_estimators=150, max_depth=None):
    ensure_training_table()
    rows = query(
        f"""
        SELECT {', '.join(NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN])}
        FROM preprocessed_sales
        """
    )
    if not rows:
        raise ValueError("Belum ada data pra-pemrosesan. Jalankan Pra-Pemrosesan terlebih dahulu.")

    frame = pd.DataFrame(rows)
    label_counts = frame[TARGET_COLUMN].value_counts()
    if len(label_counts) < 2:
        raise ValueError("Training membutuhkan minimal 2 label segmentasi.")
    rare_labels = label_counts[label_counts < 2].index.tolist()

    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].fillna("Tidak Diketahui").astype(str)

    x_data = frame[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y_data = frame[TARGET_COLUMN]

    if rare_labels:
        rare_mask = y_data.isin(rare_labels)
        common_x = x_data.loc[~rare_mask]
        common_y = y_data.loc[~rare_mask]
        rare_x = x_data.loc[rare_mask]
        rare_y = y_data.loc[rare_mask]
        common_label_count = common_y.nunique()
        if common_label_count < 1 or len(common_x) <= common_label_count:
            raise ValueError("Data belum cukup untuk membentuk data latih dan data uji.")

        test_count = round(len(common_x) * test_size)
        test_count = max(test_count, common_label_count)
        test_count = min(test_count, len(common_x) - common_label_count)
        adjusted_test_size = test_count / len(common_x)
        x_train_common, x_test, y_train_common, y_test = train_test_split(
            common_x,
            common_y,
            test_size=adjusted_test_size,
            random_state=42,
            stratify=common_y,
        )
        x_train = pd.concat([x_train_common, rare_x], ignore_index=True)
        y_train = pd.concat([y_train_common, rare_y], ignore_index=True)
    else:
        x_train, x_test, y_train, y_test = train_test_split(
            x_data,
            y_data,
            test_size=test_size,
            random_state=42,
            stratify=y_data,
        )

    preprocessor = ColumnTransformer(
        transformers=[
            ("category", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("numeric", "passthrough", NUMERIC_FEATURES),
        ]
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    random_state=42,
                    class_weight="balanced",
                ),
            ),
        ]
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    labels = sorted(y_data.unique().tolist())

    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions, average="weighted", zero_division=0)
    recall = recall_score(y_test, predictions, average="weighted", zero_division=0)
    f1 = f1_score(y_test, predictions, average="weighted", zero_division=0)
    matrix = confusion_matrix(y_test, predictions, labels=labels).tolist()
    report = classification_report(y_test, predictions, labels=labels, zero_division=0)

    model_dir = Path(current_app.root_path).parent / "models"
    model_dir.mkdir(exist_ok=True)
    model_path = model_dir / "random_forest_segmentasi.joblib"
    joblib.dump(model, model_path)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO model_training_results (
            total_rows, train_rows, test_rows, accuracy, precision_score,
            recall_score, f1_score, labels_json, confusion_matrix_json,
            classification_report_text, feature_columns_json, model_path
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            len(frame),
            len(x_train),
            len(x_test),
            float(accuracy),
            float(precision),
            float(recall),
            float(f1),
            json.dumps(labels),
            json.dumps(matrix),
            report,
            json.dumps(NUMERIC_FEATURES + CATEGORICAL_FEATURES),
            str(model_path),
        ),
    )
    cursor.execute(
        """
        INSERT INTO model_metrics (accuracy, precision_score, recall_score, f1_score)
        VALUES (%s, %s, %s, %s)
        """,
        (float(accuracy), float(precision), float(recall), float(f1)),
    )
    conn.commit()
    cursor.close()
    result = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "test_rows": len(x_test),
    }
    if rare_labels:
        result["note"] = (
            "Label dengan data kurang dari 2 dimasukkan seluruhnya ke data latih: "
            + ", ".join(rare_labels)
        )
    return result
