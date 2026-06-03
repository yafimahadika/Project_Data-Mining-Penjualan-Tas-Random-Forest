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

## Login Lokal

- Username: `admin`
- Password: `admin123`
