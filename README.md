# Project Maria

Website skripsi untuk implementasi data mining menggunakan algoritma Random Forest dalam prediksi segmentasi penjualan tas berdasarkan perilaku konsumen pada PT Inovasi Kreatif Mediatama.

## Stack

- Backend: Python Flask
- Machine Learning: scikit-learn, pandas, numpy
- Frontend: HTML, CSS, Bootstrap
- Database: MySQL lokal XAMPP
- Visualisasi: Chart.js

## Role Aplikasi

- Admin: mengelola dataset, training model, prediksi, dan data master.
- Pimpinan: melihat dashboard, grafik segmentasi, dan laporan hasil prediksi.

## Setup

1. Buat virtual environment.
2. Install dependency:

```bash
pip install -r requirements.txt
```

3. Salin konfigurasi:

```bash
copy .env.example .env
```

4. Jalankan MySQL dari XAMPP.
5. Import database:

```bash
C:\xampp\mysql\bin\mysql.exe -u root -p < database\schema.sql
C:\xampp\mysql\bin\mysql.exe -u root -p project_maria < database\sample_data.sql
```

6. Jalankan aplikasi:

```bash
python run.py
```

Aplikasi akan berjalan di `http://127.0.0.1:5000`.

## Upload dataset Shopee

- Gunakan file `.xlsx` ekspor toko dengan sheet `orders` (maksimal 32 MB per upload).
- Kolom `Subtotal Pesanan` dan `Total Harga Produk` didukung. Nominal teks seperti `1.423.800` atau `1.423.800,50` dibaca sebagai rupiah; sel angka Excel juga dibaca langsung sebagai rupiah.
- Baris kosong dilewati. File yang kolom wajib atau isi barisnya tidak valid akan ditolak sebelum mengganti data lama.
- Upload ulang dengan nama file yang sama mengganti data dari file tersebut. Jika penyimpanan gagal, perubahan upload dibatalkan.
- Jalankan `pip install -r requirements.txt` untuk memasang pembaca Excel cepat `python-calamine`, lalu jalankan ulang Flask. Jika pembaca ini belum tersedia, aplikasi memakai `openpyxl`.
- Tombol upload menampilkan status pemrosesan dan mencegah klik berulang. Pesan sukses menampilkan jumlah baris dan waktu proses server.

Pengujian importer: `python -m unittest discover -s tests -v`.

## Login Lokal

- Username: `admin`
- Password: `admin123`
