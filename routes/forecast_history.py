from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from models.master import db, Rute, Kode, JenisBangunan, KategoriGolongan, Forecast
from utils.helpers_history import sync_master_tables
from models.konsumsi_aktual import KonsumsiAktual
from sqlalchemy import extract
import json
from sqlalchemy import func

forecast_history_bp = Blueprint("forecast_history", __name__, url_prefix="/history")

MONTH_MAP = {
    1: "JANUARI",
    2: "FEBRUARI",
    3: "MARET",
    4: "APRIL",
    5: "MEI",
    6: "JUNI",
    7: "JULI",
    8: "AGUSTUS",
    9: "SEPTEMBER",
    10: "OKTOBER",
    11: "NOVEMBER",
    12: "DESEMBER"
}
def bulan_int_ke_string(bulan_int):
    bulan_list = ["JANUARI","FEBRUARI","MARET","APRIL","MEI","JUNI",
                  "JULI","AGUSTUS","SEPTEMBER","OKTOBER","NOVEMBER","DESEMBER"]
    return bulan_list[bulan_int-1]
# -------------------------------
# Halaman utama history forecast
# -------------------------------
@forecast_history_bp.route("/forecast", methods=['GET'])
def forecasting_page():
    # Sinkronkan master dulu biar data dropdown selalu terisi
    sync_master_tables()

    # Ambil parameter filter dari request
    tahun = request.args.get("tahun", type=int)
    bulan = request.args.get("bulan", type=int)
    rute = request.args.get("rute")
    kode = request.args.get("kode")
    kategori = request.args.get("kategori_golongan")
    jenis = request.args.get("jenis_bangunan")

    query = Forecast.query

    if tahun:
        query = query.filter(Forecast.tahun == tahun)
    if bulan:
        query = query.filter(Forecast.bulan == bulan)
    if rute:
        rute_obj = Rute.query.filter_by(rute=rute).first()
        if rute_obj:
            query = query.filter(Forecast.rute_id == rute_obj.id)
    if kode:
        kode_obj = Kode.query.filter_by(kode=kode).first()
        if kode_obj:
            query = query.filter(Forecast.kode_id == kode_obj.id)
    if kategori:
        kategori_obj = KategoriGolongan.query.filter_by(golongan=kategori).first()
        if kategori_obj:
            query = query.filter(Forecast.kategori_golongan_id == kategori_obj.id)
    if jenis:
        jenis_obj = JenisBangunan.query.filter_by(jenis=jenis).first()
        if jenis_obj:
            query = query.filter(Forecast.jenis_bangunan_id == jenis_obj.id)

    forecasts = query.order_by(Forecast.tanggal_entry.desc()).all()

    history_data = []
    for f in forecasts:
        history_data.append({
            "id": f.id,
            "rute": f.rute.rute if f.rute else '',
            "kode": f.kode.kode if f.kode else '',
            "kategori_golongan": f.kategori_golongan.golongan if f.kategori_golongan else '',
            "jenis_bangunan": f.jenis_bangunan.jenis if f.jenis_bangunan else '',
            "prediksi": f.prediksi if f.prediksi is not None else '',
            "tahun": f.tahun,
            "bulan": f.bulan,
            "aktual": f.aktual if f.aktual is not None else '',
            "tanggal": f.tanggal_entry.strftime("%Y-%m-%d"),
            "periode": f.periode.strftime("%Y-%m")
        })

    # Kalau hasil kosong dan ada filter → kasih flash message
    if not history_data and (tahun or bulan or rute or kode or kategori or jenis):
        flash("Data forecast untuk filter ini belum tersedia", "warning")

    # Ambil semua opsi untuk dropdown filter
    all_rutes = [r.rute for r in Rute.query.order_by(Rute.rute).all()]
    all_kode = [k.kode for k in Kode.query.order_by(Kode.kode).all()]
    all_kategori_golongan = [g.golongan for g in KategoriGolongan.query.order_by(KategoriGolongan.golongan).all()]
    all_jenis_bangunan = [j.jenis for j in JenisBangunan.query.order_by(JenisBangunan.jenis).all()]

    return render_template(
        "history_forecast.html",
        history_data=history_data,
        history_data_json=json.dumps(history_data),
        all_rutes=all_rutes,
        all_kode=all_kode,
        all_kategori_golongan=all_kategori_golongan,
        all_jenis_bangunan=all_jenis_bangunan,
        active_page="history_forecast"
    )


# -------------------------------
# Tambah data forecast via JSON
# -------------------------------
@forecast_history_bp.route("/forecast/add", methods=["POST"])
def add_forecast():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request harus berisi JSON"}), 400

    try:
        rute_str = data.get("rute")
        kode_str = data.get("kode")
        kategori_str = data.get("kategori_golongan")
        jenis_str = data.get("jenis_bangunan")
        tahun = int(data.get("tahun")) if data.get("tahun") else None
        bulan = int(data.get("bulan")) if data.get("bulan") else None
        prediksi = float(data.get("prediksi")) if data.get("prediksi") else None
        aktual = float(data.get("aktual")) if data.get("aktual") else None

        # Ambil object master
        rute_obj = Rute.query.filter_by(rute=rute_str).first() if rute_str else None
        kode_obj = Kode.query.filter_by(kode=kode_str).first() if kode_str else None
        kategori_obj = KategoriGolongan.query.filter_by(golongan=kategori_str).first() if kategori_str else None
        jenis_obj = JenisBangunan.query.filter_by(jenis=jenis_str).first() if jenis_str else None

        # Cek apakah record forecast untuk kombinasi ini sudah ada
        existing_forecast = Forecast.query.filter_by(
            rute_id=rute_obj.id if rute_obj else None,
            kode_id=kode_obj.id if kode_obj else None,
            kategori_golongan_id=kategori_obj.id if kategori_obj else None,
            jenis_bangunan_id=jenis_obj.id if jenis_obj else None,
            tahun=tahun,
            bulan=bulan
        ).first()

        if existing_forecast:
            existing_forecast.prediksi = prediksi
            existing_forecast.aktual = aktual
        else:
            new_forecast = Forecast(
                rute_id=rute_obj.id if rute_obj else None,
                kode_id=kode_obj.id if kode_obj else None,
                kategori_golongan_id=kategori_obj.id if kategori_obj else None,
                jenis_bangunan_id=jenis_obj.id if jenis_obj else None,
                tahun=tahun,
                bulan=bulan,
                prediksi=prediksi,
                aktual=aktual
            )
            db.session.add(new_forecast)

        db.session.commit()
        return jsonify({"message": "Forecast berhasil ditambahkan!"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# -------------------------------
# Ambil data forecast by filter (API)
# -------------------------------
@forecast_history_bp.route("/forecast/filter", methods=["GET"])
def filter_forecast_history():
    rute = request.args.get("rute")
    kode = request.args.get("kode")
    kategori = request.args.get("kategori_golongan")
    jenis = request.args.get("jenis_bangunan")
    tahun = request.args.get("tahun", type=int)

    query = Forecast.query
    if rute:
        rute_obj = Rute.query.filter_by(rute=rute).first()
        if rute_obj:
            query = query.filter_by(rute_id=rute_obj.id)
    if kode:
        kode_obj = Kode.query.filter_by(kode=kode).first()
        if kode_obj:
            query = query.filter_by(kode_id=kode_obj.id)
    if kategori:
        kategori_obj = KategoriGolongan.query.filter_by(golongan=kategori).first()
        if kategori_obj:
            query = query.filter_by(kategori_golongan_id=kategori_obj.id)
    if jenis:
        jenis_obj = JenisBangunan.query.filter_by(jenis=jenis).first()
        if jenis_obj:
            query = query.filter_by(jenis_bangunan_id=jenis_obj.id)
    if tahun:
        query = query.filter_by(tahun=tahun)

    results = query.all()
    return jsonify([{
        "id": f.id,
        "rute": f.rute.rute if f.rute else None,
        "kode": f.kode.kode if f.kode else None,
        "kategori_golongan": f.kategori_golongan.golongan if f.kategori_golongan else None,
        "jenis_bangunan": f.jenis_bangunan.jenis if f.jenis_bangunan else None,
        "tahun": f.tahun,
        "bulan": f.bulan,
        "prediksi": f.prediksi,
        "aktual": f.aktual,
        "tanggal": f.tanggal_entry.strftime("%Y-%m")
    } for f in results])


# -------------------------------
# Delete forecast
# -------------------------------
@forecast_history_bp.route('/delete-forecast', methods=['POST'])
def delete_forecast():
    rute = request.form.get('rute')
    kode = request.form.get('kode')
    kategori_golongan = request.form.get('kategori_golongan')
    jenis_bangunan = request.form.get('jenis_bangunan')
    tanggal = request.form.get('tanggal')  # format yyyy-mm dari <input type="month">

    # Safety: minimal 1 filter harus diisi
    if not any([rute, kode, kategori_golongan, jenis_bangunan, tanggal]):
        flash("Pilih minimal 1 filter sebelum menghapus data forecast!", "warning")
        return redirect(url_for('forecast_history.forecasting_page'))

    query = Forecast.query

    if rute:
        rute_obj = Rute.query.filter_by(rute=rute).first()
        if rute_obj:
            query = query.filter(Forecast.rute_id == rute_obj.id)

    if kode:
        kode_obj = Kode.query.filter_by(kode=kode).first()
        if kode_obj:
            query = query.filter(Forecast.kode_id == kode_obj.id)

    if kategori_golongan:
        kategori_obj = KategoriGolongan.query.filter_by(golongan=kategori_golongan).first()
        if kategori_obj:
            query = query.filter(Forecast.kategori_golongan_id == kategori_obj.id)

    if jenis_bangunan:
        jenis_obj = JenisBangunan.query.filter_by(jenis=jenis_bangunan).first()
        if jenis_obj:
            query = query.filter(Forecast.jenis_bangunan_id == jenis_obj.id)

    if tanggal:
        try:
            tahun, bulan = tanggal.split("-")
            query = query.filter(extract('year', Forecast.periode) == int(tahun))
            query = query.filter(extract('month', Forecast.periode) == int(bulan))
        except ValueError:
            flash("Format tanggal tidak valid", "warning")
            return redirect(url_for('forecast_history.forecasting_page'))

    deleted_rows = query.delete(synchronize_session=False)
    db.session.commit()

    if deleted_rows > 0:
        flash(f"Berhasil menghapus {deleted_rows} data forecast sesuai filter", "success")
        return redirect(url_for('forecast_history.forecasting_page'))
    else:
        flash("Tidak ada data forecast yang cocok dengan filter", "warning")

    return redirect(url_for('forecast_history.forecasting_page'))


# -------------------------------
# Detail forecast
# -------------------------------
@forecast_history_bp.route('/forecast-detail/<int:forecast_id>')
def forecast_detail(forecast_id):
    forecast = Forecast.query.get_or_404(forecast_id)

    bulan_aktual = MONTH_MAP.get(forecast.bulan)

    aktual_value = None
    aktual_available = False

    if forecast.tahun and bulan_aktual:
        query = db.session.query(func.sum(KonsumsiAktual.konsumsi))
        query = query.filter(KonsumsiAktual.tahun == forecast.tahun,
                            KonsumsiAktual.bulan == bulan_aktual)

        # Tentukan filter sesuai unit yang dipilih
        if forecast.rute:
            query = query.filter(KonsumsiAktual.rute == forecast.rute.rute)
        elif forecast.kode:
            query = query.filter(KonsumsiAktual.kode == forecast.kode.kode)
        elif forecast.jenis_bangunan:
            query = query.filter(KonsumsiAktual.jenis_bangunan == forecast.jenis_bangunan.jenis)
        elif forecast.kategori_golongan:
            query = query.filter(KonsumsiAktual.kategori_golongan == forecast.kategori_golongan.golongan)

        aktual_value = query.scalar() or 0

    forecast_dict = {
        "id": forecast.id,
        "tanggal": forecast.tanggal_entry.strftime("%Y-%m-%d") if forecast.tanggal_entry else "",
        "periode": forecast.periode.strftime("%Y-%m") if forecast.periode else "",
        "rute": forecast.rute.rute if forecast.rute else "",
        "kode": forecast.kode.kode if forecast.kode else "",
        "kategori_golongan": forecast.kategori_golongan.golongan if forecast.kategori_golongan else "",
        "jenis_bangunan": forecast.jenis_bangunan.jenis if forecast.jenis_bangunan else "",
        "prediksi": forecast.prediksi if forecast.prediksi is not None else "",
        "aktual": aktual_value if aktual_value is not None else "",
        "aktual": aktual_value if aktual_value is not None else "",
        "aktual_available": aktual_available,
        "tanggal_entry": forecast.tanggal_entry.strftime("%Y-%m-%d %H:%M:%S") if forecast.tanggal_entry else ""
    }

    # Related data = forecast lain dengan kode/rute yang sama (opsional)
    related_query = Forecast.query.filter(
        Forecast.id != forecast.id,
        Forecast.rute_id == forecast.rute_id,
        Forecast.kode_id == forecast.kode_id,
        Forecast.kategori_golongan_id == forecast.kategori_golongan_id,
        Forecast.jenis_bangunan_id == forecast.jenis_bangunan_id,
        Forecast.tahun == forecast.tahun  # tetap batasi tahun sama
    ).order_by(Forecast.tanggal_entry.desc()).limit(12).all()

    related_data = []
    for f in related_query:
        related_aktual = None
        if f.tahun and f.bulan:
            query = db.session.query(func.sum(KonsumsiAktual.konsumsi).label("total_konsumsi")).filter(
            KonsumsiAktual.tahun == f.tahun,
            KonsumsiAktual.bulan == bulan_int_ke_string(f.bulan)
        )
            if f.rute:
                query = query.filter(KonsumsiAktual.rute == f.rute.rute)
            if f.kode:
                query = query.filter(KonsumsiAktual.kode == f.kode.kode)
            if f.kategori_golongan:
                query = query.filter(KonsumsiAktual.kategori_golongan == f.kategori_golongan.golongan)
            if f.jenis_bangunan:
                query = query.filter(KonsumsiAktual.jenis_bangunan == f.jenis_bangunan.jenis)

            konsumsi_related = query.scalar()  # ambil hasil sum
            if konsumsi_related is not None:
                related_aktual = konsumsi_related

        related_data.append({
            "tanggal": f.tanggal_entry.strftime("%Y-%m-%d") if f.tanggal_entry else "",
            "periode": f.periode.strftime("%Y-%m") if f.periode else "",
            "rute": f.rute.rute if f.rute else "",
            "kode": f.kode.kode if f.kode else "",
            "kategori_golongan": f.kategori_golongan.golongan if f.kategori_golongan else "",
            "jenis_bangunan": f.jenis_bangunan.jenis if f.jenis_bangunan else "",
            "prediksi": f.prediksi if f.prediksi is not None else "",
            "aktual": related_aktual if related_aktual is not None else "",
            "is_simulasi": forecast.is_simulasi if hasattr(forecast, "is_simulasi") else 0
        })
    print("=== DEBUG FORECAST DETAIL ===")
    print("Tahun :", forecast.tahun)
    print("Bulan :", forecast.bulan)
    print("Rute  :", forecast.rute.rute if forecast.rute else None)
    print("Kode  :", forecast.kode.kode if forecast.kode else None)
    print("Kategori :", forecast.kategori_golongan.golongan if forecast.kategori_golongan else None)
    print("Jenis :", forecast.jenis_bangunan.jenis if forecast.jenis_bangunan else None)
    print("Bulan forecast (angka):", forecast.bulan)
    print("Bulan aktual (string):", bulan_aktual)
    print("Aktual value:", aktual_value)

    return render_template(
        "detail_forecast.html",
        active_page="history_forecast",
        forecast=forecast_dict,                     # buat metadata
        forecast_json=json.dumps(forecast_dict),    # buat JS (chart + export)
        related_data=related_data,
        related_data_json=json.dumps(related_data)  # buat tabel + JS
    )