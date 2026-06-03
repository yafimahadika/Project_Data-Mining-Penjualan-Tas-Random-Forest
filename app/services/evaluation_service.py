import json

from app.db import query
from app.services.model_training import ensure_training_table


def _load_json(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def get_evaluation_context():
    ensure_training_table()
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
        SELECT accuracy, precision_score, recall_score, f1_score,
               train_rows, test_rows, trained_at
        FROM model_training_results
        ORDER BY trained_at ASC
        LIMIT 12
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
        labels = _load_json(latest["labels_json"], [])
        matrix = _load_json(latest["confusion_matrix_json"], [])
        feature_columns = _load_json(latest["feature_columns_json"], [])
        latest["labels"] = labels
        latest["confusion_matrix"] = matrix
        latest["feature_columns"] = feature_columns
        latest["correct_predictions"] = sum(
            matrix[index][index]
            for index in range(min(len(labels), len(matrix)))
            if index < len(matrix[index])
        )
        latest["evaluated_predictions"] = sum(sum(row) for row in matrix)
        latest["incorrect_predictions"] = (
            latest["evaluated_predictions"] - latest["correct_predictions"]
        )

    chart_data = {
        "labels": [str(row["trained_at"]) for row in history],
        "accuracy": [float(row["accuracy"]) * 100 for row in history],
        "precision": [float(row["precision_score"]) * 100 for row in history],
        "recall": [float(row["recall_score"]) * 100 for row in history],
        "f1": [float(row["f1_score"]) * 100 for row in history],
    }

    return {
        "latest": latest,
        "history": history,
        "label_rows": label_rows,
        "chart_data": chart_data,
    }
