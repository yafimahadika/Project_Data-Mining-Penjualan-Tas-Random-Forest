import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from app.services.shopee_importer import import_excel_file, integer, number, prepare_excel_rows


class ShopeeImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "toko.xlsx"
        self.record = {
            "No. Pesanan": "ORDER-001", "Status Pesanan": "Selesai",
            "Waktu Pesanan Dibuat": "2026-06-01 00:05",
            "Harga Setelah Diskon": "109.000", "Jumlah": "2",
            "Subtotal Pesanan": "218.000", "Total Pembayaran": "1.423.800",
            "Username (Pembeli)": "pembeli-uji",
        }

    def write(self, records=None, sheet_name="orders"):
        pd.DataFrame(records if records is not None else [self.record]).to_excel(
            self.path, sheet_name=sheet_name, index=False,
        )

    def test_indonesian_money_and_numeric_excel_values(self):
        for value, expected in [
            ("1.423.800", 1423800), ("109.000", 109000),
            ("Rp 1.423.800,50", 1423800.5), ("1423800,50", 1423800.5),
            (1423800, 1423800), (109000.5, 109000.5),
            ("0", 0), (None, 0), ("-", 0), ("", 0),
        ]:
            with self.subTest(value=value):
                self.assertEqual(number(value), expected)
        for value in ("bukan angka", "inf", "-inf"):
            with self.assertRaises(ValueError):
                number(value)
        with self.assertRaises(ValueError):
            integer("1,5")

    def test_store_subtotal_and_money_not_multiplied(self):
        self.write()
        rows = prepare_excel_rows(self.path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][15], 109000)
        self.assertEqual(rows[0][19], 218000)
        self.assertEqual(rows[0][21], 1423800)
        self.assertEqual(rows[0][20], 1423.8)
        self.assertEqual(rows[0][7].isoformat(), "2026-06-01T00:05:00")
        self.assertIsNone(rows[0][8])
        self.assertEqual(rows[0][16], 2)

    def test_old_column_name_and_blank_rows(self):
        self.record["Total Harga Produk"] = self.record.pop("Subtotal Pesanan")
        self.write([self.record, {}, self.record])
        self.assertEqual(len(prepare_excel_rows(self.path)), 2)

    def test_required_columns_and_sheet(self):
        self.write(sheet_name="Sheet1")
        with self.assertRaisesRegex(ValueError, "sheet 'orders'"):
            prepare_excel_rows(self.path)
        self.record.pop("Jumlah")
        self.write()
        with self.assertRaisesRegex(ValueError, "Jumlah"):
            prepare_excel_rows(self.path)

    def test_invalid_row_reports_excel_line(self):
        self.record["Waktu Pesanan Dibuat"] = "salah"
        self.write()
        with self.assertRaisesRegex(ValueError, "Baris Excel 2"):
            prepare_excel_rows(self.path)

    @patch("app.services.shopee_importer.get_db")
    def test_validation_happens_before_database_changes(self, get_db):
        self.record["Total Pembayaran"] = "salah"
        self.write()
        with self.assertRaises(ValueError):
            import_excel_file(self.path)
        get_db.assert_not_called()

    @patch("app.services.shopee_importer.rebuild_customer_segments")
    @patch("app.services.shopee_importer.get_db")
    def test_database_failure_rolls_back_replacement(self, get_db, rebuild):
        self.write()
        connection = MagicMock()
        get_db.return_value = connection
        rebuild.side_effect = RuntimeError("segment failure")
        with self.assertRaises(RuntimeError):
            import_excel_file(self.path)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()
        connection.cursor.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
