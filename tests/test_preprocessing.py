import unittest
from unittest.mock import patch

import pandas as pd

from app.services.preprocessing import (
    BATCH_SIZE, add_group_modes, most_common, replace_preprocessed_rows, run_preprocessing,
)


class PreprocessingTests(unittest.TestCase):
    def test_group_modes_preserve_ties_missing_values_and_order_groups(self):
        frame = pd.DataFrame([
            ("a", "one", "Z"), ("a", "one", "A"), ("a", "one", "A"),
            ("a", "two", "Z"), ("a", "two", "A"),
            ("b", "three", None), ("b", "three", None),
        ], columns=["buyer", "order", "sku"])
        keys = ["buyer", "order"]
        expected = frame.groupby(keys, as_index=False).agg(sku=("sku", most_common))
        result = add_group_modes(frame[keys].drop_duplicates(), frame, keys, {"sku": "sku"})
        pd.testing.assert_frame_equal(result.fillna("<missing>"), expected.fillna("<missing>"))

    @patch("app.services.preprocessing.get_db")
    def test_large_result_uses_small_batches(self, get_db):
        connection = get_db.return_value
        values = [("buyer",)] * (BATCH_SIZE * 2 + 3)
        replace_preprocessed_rows(values)
        cursor = connection.cursor.return_value
        self.assertEqual([len(call.args[1]) for call in cursor.executemany.call_args_list],
                         [BATCH_SIZE, BATCH_SIZE, 3])
        cursor.execute.assert_called_once_with("DELETE FROM preprocessed_sales")
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()
        cursor.close.assert_called_once()

    @patch("app.services.preprocessing.get_db")
    def test_later_batch_failure_rolls_back_entire_replacement(self, get_db):
        connection = get_db.return_value
        cursor = connection.cursor.return_value
        cursor.executemany.side_effect = [None, RuntimeError("write failed")]
        with self.assertRaises(RuntimeError):
            replace_preprocessed_rows([("buyer",)] * (BATCH_SIZE + 1))
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        cursor.close.assert_called_once()

    @patch("app.services.preprocessing.replace_preprocessed_rows")
    @patch("app.services.preprocessing.query")
    @patch("app.services.preprocessing.ensure_preprocessed_table")
    def test_features_aggregate_multiple_product_lines_once_per_order(self, ensure, query, replace):
        base = dict(buyer_username="buyer", payment_method="COD", city=None,
                    province="Jawa", sku_reference="B", order_created_at="2026-06-01")
        query.return_value = [
            dict(base, order_number="one", quantity=1, total_payment_rupiah=100000),
            dict(base, order_number="one", quantity=2, total_payment_rupiah=100000, sku_reference="A"),
            dict(base, order_number="two", quantity=1, total_payment_rupiah=200000,
                 payment_method="Transfer", order_created_at="2026-06-04"),
        ]
        self.assertEqual(run_preprocessing(), {"processed_rows": 1})
        row = replace.call_args.args[0][0]
        self.assertEqual(row[:7], ("buyer", 2, 4, 300000, 150000, 1, 1))
        self.assertEqual(row[7:], ("COD", None, "Jawa", "A", 3, "Pelanggan Premium"))


if __name__ == "__main__":
    unittest.main()
