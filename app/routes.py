from functools import wraps
from math import ceil
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from app.db import get_db, query
from app.services.evaluation_service import get_evaluation_context
from app.services.model_training import get_training_context, train_random_forest
from app.services.prediction_service import get_prediction_context, predict_segment
from app.services.preprocessing import get_preprocessing_summary, run_preprocessing
from app.services.report_service import build_report_excel, get_report_context
from app.services.shopee_importer import import_excel_file, rebuild_customer_segments

main_bp = Blueprint("main", __name__)


def compact_rupiah(value):
    value = float(value or 0)
    return f"Rp {value:,.0f}".replace(",", ".")


@main_bp.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.login"))


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if not session.get("user_id"):
            return redirect(url_for("main.login"))
        return view(**kwargs)

    return wrapped_view


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        user = query(
            "SELECT id, name, username, password_hash, role FROM users WHERE username = %s",
            (username,),
            fetchone=True,
        )

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session.permanent = remember
            return redirect(url_for("main.dashboard"))

        error = "Username atau password tidak sesuai."

    return render_template("login.html", error=error)


@main_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    stats = {
        "customers": 0,
        "transactions": 0,
        "segments": 0,
        "revenue": 0,
        "revenue_display": "Rp 0",
        "average_order": 0,
        "accuracy": "-",
    }
    chart_data = {
        "monthlySales": {"labels": [], "values": []},
        "segments": {"labels": [], "values": []},
        "channels": {"labels": [], "values": []},
        "categories": {"labels": [], "values": []},
    }
    recent_transactions = []
    top_segments = []

    try:
        stats["customers"] = query(
            "SELECT COUNT(*) AS total FROM shopee_customer_segments",
            fetchone=True,
        )["total"]
        stats["transactions"] = query(
            """
            SELECT COUNT(*) AS total
            FROM (
                SELECT order_number
                FROM shopee_orders
                WHERE order_status = 'Selesai'
                GROUP BY order_number
            ) finished_orders
            """,
            fetchone=True,
        )["total"]
        stats["segments"] = stats["customers"]
        revenue_row = query(
            """
            SELECT COALESCE(SUM(order_payment), 0) AS total
            FROM (
                SELECT order_number, MAX(total_payment_rupiah) AS order_payment
                FROM shopee_orders
                WHERE order_status = 'Selesai'
                GROUP BY order_number
            ) order_totals
            """,
            fetchone=True,
        )
        stats["revenue"] = float(revenue_row["total"])
        stats["revenue_display"] = compact_rupiah(stats["revenue"])
        stats["average_order"] = (
            stats["revenue"] / stats["transactions"] if stats["transactions"] else 0
        )
        latest_metric = query(
            "SELECT accuracy FROM model_metrics ORDER BY trained_at DESC LIMIT 1",
            fetchone=True,
        )
        stats["accuracy"] = f"{latest_metric['accuracy'] * 100:.2f}%" if latest_metric else "Belum Training"

        monthly_sales = query(
            """
            SELECT DATE_FORMAT(order_month, '%b %Y') AS label,
                   SUM(order_payment) AS total
            FROM (
                SELECT order_number,
                       MIN(order_created_at) AS order_month,
                       MAX(total_payment_rupiah) AS order_payment
                FROM shopee_orders
                WHERE order_status = 'Selesai'
                GROUP BY order_number
            ) order_totals
            GROUP BY YEAR(order_month), MONTH(order_month), label
            ORDER BY YEAR(order_month), MONTH(order_month)
            """
        )
        chart_data["monthlySales"] = {
            "labels": [row["label"] for row in monthly_sales],
            "values": [float(row["total"]) for row in monthly_sales],
        }

        segment_rows = query(
            """
            SELECT segment_label AS label, COUNT(*) AS total
            FROM shopee_customer_segments
            GROUP BY segment_label
            ORDER BY total DESC
            """
        )
        chart_data["segments"] = {
            "labels": [row["label"] for row in segment_rows],
            "values": [int(row["total"]) for row in segment_rows],
        }
        top_segments = segment_rows[:4]

        channel_rows = query(
            """
            SELECT payment_method AS label, COUNT(DISTINCT order_number) AS total
            FROM shopee_orders
            WHERE order_status = 'Selesai'
            GROUP BY payment_method
            ORDER BY total DESC
            LIMIT 6
            """
        )
        chart_data["channels"] = {
            "labels": [row["label"] for row in channel_rows],
            "values": [int(row["total"]) for row in channel_rows],
        }

        category_rows = query(
            """
            SELECT COALESCE(sku_reference, 'Tanpa SKU') AS label, SUM(quantity) AS total
            FROM shopee_orders
            WHERE order_status = 'Selesai'
            GROUP BY COALESCE(sku_reference, 'Tanpa SKU')
            ORDER BY total DESC
            LIMIT 8
            """
        )
        chart_data["categories"] = {
            "labels": [row["label"] for row in category_rows],
            "values": [int(row["total"]) for row in category_rows],
        }

        recent_transactions = query(
            """
            SELECT order_number, buyer_username AS name,
                   GROUP_CONCAT(DISTINCT COALESCE(sku_reference, variation_name, product_name)
                                ORDER BY sku_reference SEPARATOR ', ') AS product_category,
                   MAX(total_payment_rupiah) AS total_amount,
                   MAX(payment_method) AS purchase_channel,
                   MIN(order_created_at) AS purchase_date
            FROM shopee_orders
            WHERE order_status = 'Selesai'
            GROUP BY order_number, buyer_username
            ORDER BY purchase_date DESC
            LIMIT 5
            """
        )
    except Exception:
        stats["database_error"] = True

    return render_template(
        "dashboard.html",
        page_title="Dashboard",
        stats=stats,
        chart_data=chart_data,
        recent_transactions=recent_transactions,
        top_segments=top_segments,
    )


@main_bp.route("/dataset")
@login_required
def dataset():
    rows = []
    search = request.args.get("search", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    sort = request.args.get("sort", "order_created_at")
    direction = request.args.get("direction", "desc").lower()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = request.args.get("per_page", 5, type=int)
    allowed_sizes = [5, 10, 20, 25, 50, 100]
    if per_page not in allowed_sizes:
        per_page = 5

    sort_map = {
        "order_created_at": "order_created_at",
        "buyer_username": "buyer_username",
        "order_status": "order_status",
        "sku_reference": "sku_reference",
        "quantity": "quantity",
        "total_payment_rupiah": "total_payment_rupiah",
        "payment_method": "payment_method",
        "city": "city",
        "province": "province",
    }
    sort_column = sort_map.get(sort, "order_created_at")
    direction = "asc" if direction == "asc" else "desc"
    next_direction = "desc" if direction == "asc" else "asc"

    where_parts = []
    params = []
    if search:
        where_parts.append(
            """
            (
                order_number LIKE %s OR buyer_username LIKE %s OR order_status LIKE %s
                OR sku_reference LIKE %s OR variation_name LIKE %s OR product_name LIKE %s
                OR payment_method LIKE %s OR city LIKE %s OR province LIKE %s
            )
            """
        )
        like = f"%{search}%"
        params.extend([like] * 9)
    if start_date:
        where_parts.append("DATE(order_created_at) >= %s")
        params.append(start_date)
    if end_date:
        where_parts.append("DATE(order_created_at) <= %s")
        params.append(end_date)

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    total_rows = 0
    total_pages = 1
    try:
        count_row = query(
            f"SELECT COUNT(*) AS total FROM shopee_orders {where_sql}",
            tuple(params),
            fetchone=True,
        )
        total_rows = count_row["total"] if count_row else 0
        total_pages = max(ceil(total_rows / per_page), 1)
        page = min(page, total_pages)
        offset = (page - 1) * per_page
        rows = query(
            f"""
            SELECT id, source_file, order_number,
                   buyer_username AS name, order_status, city, province,
                   sku_reference, variation_name, product_name,
                   COALESCE(sku_reference, variation_name, product_name) AS product_category,
                   quantity, total_payment_rupiah AS total_amount,
                   payment_method AS purchase_channel,
                   order_created_at AS purchase_date
            FROM shopee_orders
            {where_sql}
            ORDER BY {sort_column} {direction}, id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [per_page, offset]),
        )
    except Exception:
        pass

    return render_template(
        "dataset.html",
        rows=rows,
        page_title="Dataset",
        filters={
            "search": search,
            "start_date": start_date,
            "end_date": end_date,
            "sort": sort,
            "direction": direction,
            "next_direction": next_direction,
            "page": page,
            "per_page": per_page,
            "allowed_sizes": allowed_sizes,
            "total_rows": total_rows,
            "total_pages": total_pages,
        },
    )


@main_bp.route("/dataset/upload", methods=["POST"])
@login_required
def dataset_upload():
    upload = request.files.get("dataset_file")
    if not upload or not upload.filename:
        flash("Pilih file Excel terlebih dahulu.", "warning")
        return redirect(url_for("main.dataset"))

    filename = secure_filename(upload.filename)
    if not filename.lower().endswith(".xlsx"):
        flash("Format file harus .xlsx.", "danger")
        return redirect(url_for("main.dataset"))

    upload_dir = Path(current_app.root_path).parent / current_app.config["UPLOAD_FOLDER"]
    try:
        started_at = perf_counter()
        upload_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="dataset-", dir=upload_dir) as temporary_dir:
            path = Path(temporary_dir) / filename
            upload.save(path)
            imported_rows = import_excel_file(path, upload.filename)
        elapsed = perf_counter() - started_at
        flash(f"Dataset {filename} berhasil diupload. {imported_rows} baris diproses dalam {elapsed:.1f} detik.", "success")
    except Exception as error:
        current_app.logger.exception("Gagal mengimpor dataset")
        flash(f"Gagal upload dataset: {error}", "danger")

    return redirect(url_for("main.dataset"))


@main_bp.route("/dataset/<int:row_id>/edit", methods=["POST"])
@login_required
def dataset_edit(row_id):
    total_amount = request.form.get("total_amount", "0").replace(".", "").replace(",", ".")
    quantity = request.form.get("quantity", 0, type=int)
    order_created_at = request.form.get("order_created_at", "").replace("T", " ")
    try:
        total_amount_value = float(total_amount or 0)
        query(
            """
            UPDATE shopee_orders
            SET buyer_username = %s,
                order_status = %s,
                sku_reference = %s,
                quantity = %s,
                total_payment_rupiah = %s,
                total_payment_raw = %s,
                payment_method = %s,
                city = %s,
                province = %s,
                order_created_at = %s
            WHERE id = %s
            """,
            (
                request.form.get("buyer_username"),
                request.form.get("order_status"),
                request.form.get("sku_reference"),
                quantity,
                total_amount_value,
                total_amount_value / 1000,
                request.form.get("payment_method"),
                request.form.get("city"),
                request.form.get("province"),
                order_created_at,
                row_id,
            ),
            commit=True,
        )
        rebuild_customer_segments()
        flash("Data berhasil diperbarui.", "success")
    except Exception as error:
        flash(f"Gagal memperbarui data: {error}", "danger")

    return redirect(url_for("main.dataset", **request.args))


@main_bp.route("/dataset/<int:row_id>/delete", methods=["POST"])
@login_required
def dataset_delete(row_id):
    try:
        query("DELETE FROM shopee_orders WHERE id = %s", (row_id,), commit=True)
        rebuild_customer_segments()
        flash("Data berhasil dihapus.", "success")
    except Exception as error:
        flash(f"Gagal menghapus data: {error}", "danger")

    return redirect(url_for("main.dataset", **request.args))


@main_bp.route("/dataset/bulk-delete", methods=["POST"])
@login_required
def dataset_bulk_delete():
    delete_mode = request.form.get("delete_mode", "selected")
    try:
        if delete_mode == "all":
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("TRUNCATE TABLE shopee_orders")
            cursor.execute("TRUNCATE TABLE shopee_customer_segments")
            cursor.execute("TRUNCATE TABLE preprocessed_sales")
            conn.commit()
            cursor.close()
            flash("Semua dataset berhasil dihapus.", "success")
            return redirect(url_for("main.dataset"))

        selected_ids = [
            int(item)
            for item in request.form.get("selected_ids", "").split(",")
            if item.strip().isdigit()
        ]
        if not selected_ids:
            flash("Pilih minimal satu data terlebih dahulu.", "warning")
            return redirect(url_for("main.dataset", **request.args))

        placeholders = ", ".join(["%s"] * len(selected_ids))
        query(
            f"DELETE FROM shopee_orders WHERE id IN ({placeholders})",
            tuple(selected_ids),
            commit=True,
        )
        rebuild_customer_segments()
        flash(f"{len(selected_ids)} data berhasil dihapus.", "success")
    except Exception as error:
        flash(f"Gagal menghapus dataset: {error}", "danger")
    return redirect(url_for("main.dataset", **request.args))


@main_bp.route("/pra-pemrosesan")
@login_required
def preprocessing():
    summary = get_preprocessing_summary()
    feature_rows = []
    segment_rows = []
    preview_rows = []
    try:
        feature_rows = [
            {"name": "total_orders", "type": "Numerik", "description": "Jumlah order selesai per pembeli"},
            {"name": "total_quantity", "type": "Numerik", "description": "Total item tas yang dibeli"},
            {"name": "total_spent_rupiah", "type": "Numerik", "description": "Total nilai transaksi selesai"},
            {"name": "average_order_rupiah", "type": "Numerik", "description": "Rata-rata nilai transaksi"},
            {"name": "cod_orders", "type": "Numerik", "description": "Jumlah order dengan pembayaran COD"},
            {"name": "online_orders", "type": "Numerik", "description": "Jumlah order non-COD"},
            {"name": "dominant_payment_method", "type": "Kategori", "description": "Metode pembayaran dominan"},
            {"name": "dominant_province", "type": "Kategori", "description": "Provinsi pembeli dominan"},
            {"name": "dominant_sku", "type": "Kategori", "description": "SKU produk paling sering dibeli"},
        ]
        segment_rows = query(
            """
            SELECT segment_label, COUNT(*) AS total
            FROM preprocessed_sales
            GROUP BY segment_label
            ORDER BY total DESC
            """
        )
        preview_rows = query(
            """
            SELECT buyer_username, total_orders, total_quantity, total_spent_rupiah,
                   average_order_rupiah, dominant_payment_method, dominant_province,
                   dominant_sku, segment_label
            FROM preprocessed_sales
            ORDER BY total_spent_rupiah DESC
            LIMIT 10
            """
        )
    except Exception:
        pass

    return render_template(
        "preprocessing.html",
        page_title="Pra-pemrosesan",
        summary=summary,
        feature_rows=feature_rows,
        segment_rows=segment_rows,
        preview_rows=preview_rows,
    )


@main_bp.route("/pra-pemrosesan/proses", methods=["POST"])
@login_required
def preprocessing_process():
    try:
        started_at = perf_counter()
        result = run_preprocessing()
        elapsed = perf_counter() - started_at
        flash(f"Pra-pemrosesan selesai. {result['processed_rows']} data pembeli siap training dalam {elapsed:.1f} detik.", "success")
    except Exception as error:
        current_app.logger.exception("Pra-pemrosesan gagal")
        flash(f"Pra-pemrosesan gagal: {error}", "danger")
    return redirect(url_for("main.preprocessing"))


@main_bp.route("/training")
@login_required
def training():
    return render_template("training.html", page_title="Training Model", **get_training_context())


@main_bp.route("/training/proses", methods=["POST"])
@login_required
def training_process():
    try:
        test_size = request.form.get("test_size", 0.2, type=float)
        n_estimators = request.form.get("n_estimators", 150, type=int)
        max_depth_value = request.form.get("max_depth", "").strip()
        max_depth = int(max_depth_value) if max_depth_value else None
        result = train_random_forest(
            test_size=test_size,
            n_estimators=n_estimators,
            max_depth=max_depth,
        )
        message = (
            f"Training selesai. Akurasi {result['accuracy'] * 100:.2f}% "
            f"dari {result['test_rows']} data uji."
        )
        if result.get("note"):
            message = f"{message} Catatan: {result['note']}."
        flash(message, "success")
    except Exception as error:
        flash(f"Training gagal: {error}", "danger")
    return redirect(url_for("main.training"))


@main_bp.route("/training/<int:training_id>/delete", methods=["POST"])
@login_required
def training_delete(training_id):
    try:
        query("DELETE FROM model_training_results WHERE id = %s", (training_id,), commit=True)
        query("DELETE FROM model_metrics ORDER BY trained_at DESC LIMIT 1", commit=True)
        flash("Riwayat training berhasil dihapus.", "success")
    except Exception as error:
        flash(f"Gagal menghapus riwayat training: {error}", "danger")
    return redirect(url_for("main.training"))


@main_bp.route("/prediksi")
@login_required
def prediction():
    result_id = request.args.get("result_id", type=int)
    return render_template(
        "prediction.html",
        page_title="Prediksi",
        **get_prediction_context(result_id=result_id),
    )


@main_bp.route("/prediksi/proses", methods=["POST"])
@login_required
def prediction_process():
    try:
        result = predict_segment(request.form)
        confidence = result["confidence"] * 100 if result["confidence"] is not None else 0
        flash(
            f"Prediksi selesai. Segmentasi: {result['predicted_segment']} "
            f"dengan confidence {confidence:.2f}%.",
            "success",
        )
        return redirect(url_for("main.prediction", result_id=result["id"]))
    except Exception as error:
        flash(f"Prediksi gagal: {error}", "danger")
        return redirect(url_for("main.prediction"))


@main_bp.route("/prediksi/<int:prediction_id>/delete", methods=["POST"])
@login_required
def prediction_delete(prediction_id):
    try:
        query("DELETE FROM prediction_results WHERE id = %s", (prediction_id,), commit=True)
        flash("Riwayat prediksi berhasil dihapus.", "success")
    except Exception as error:
        flash(f"Gagal menghapus riwayat prediksi: {error}", "danger")
    return redirect(url_for("main.prediction"))


@main_bp.route("/evaluasi")
@login_required
def evaluation():
    return render_template(
        "evaluation.html",
        page_title="Evaluasi Model",
        **get_evaluation_context(),
    )


@main_bp.route("/laporan")
@login_required
def report():
    return render_template("report.html", page_title="Laporan", **get_report_context())


@main_bp.route("/laporan/download")
@login_required
def report_download():
    output, filename = build_report_excel()
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@main_bp.route("/users")
@login_required
def users():
    user_rows = []
    try:
        user_rows = query(
            "SELECT name, username, role, created_at FROM users ORDER BY created_at DESC"
        )
    except Exception:
        pass

    return render_template(
        "module_page.html",
        page_title="Manajemen User",
        eyebrow="Admin",
        title="Manajemen User",
        description="Mengelola akun Admin dan Pimpinan untuk akses dashboard internal.",
        icon="bi-person-gear",
        user_rows=user_rows,
    )
