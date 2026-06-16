from flask import Blueprint, request, jsonify
from models.master import Forecast
from models import db
import pandas as pd
import logging

from utils.forecasting import forecast_rute_a101
from utils.forecast_filters import forecast_konsumsi, jalankan_semua_forecast
from models import KonsumsiAktual

# Logging
logger = logging.getLogger(__name__)

# Blueprint
forecast_bp = Blueprint('forecast', __name__)

# ==========================
# Load Data Konsumsi
# ==========================
def load_data():
    """
    Load data konsumsi dari database via SQLAlchemy model
    """
    try:
        data = KonsumsiAktual.query.all()
        df = pd.DataFrame([{
            "TANGGAL": row.TANGGAL,
            "RUTE": row.RUTE,
            "KATEGORI": row.KATEGORI,
            "KONSUMSI": row.KONSUMSI
        } for row in data])
        df['TANGGAL'] = pd.to_datetime(df['TANGGAL'])
        logger.info(f"Data berhasil dimuat: {len(df)} baris")
        return df
    except Exception as e:
        logger.exception(f"Gagal load data dari database: {e}")
        return None


# ==========================
# 1️⃣ Route khusus RUTE A101
# ==========================
@forecast_bp.route('/forecast/a101', methods=['GET'])
def forecast_a101():
    df = load_data()
    if df is None:
        return jsonify({"error": "Gagal memuat data"}), 500
    
    tahun = request.args.get('tahun', type=int)
    bulan = request.args.get('bulan', type=int)
    
    forecast_df, evaluasi = forecast_rute_a101(df, tahun=tahun, bulan=bulan)
    if forecast_df is None:
        return jsonify({"error": "Gagal melakukan forecasting"}), 500
    
    try:
        for _, row in forecast_df.iterrows():
            #  Perbaikan: rute selalu terisi dan bersih
            rute_value = (row.get("Rute") or "A101").replace("RUTE:", "").strip().upper()
            kode_value = row.get("Kode") or ""
            kategori_value = row.get("Kategori_Golongan") or row.get("Kategori") or ""
            jenis_value = row.get("Jenis_Bangunan") or ""
            prediksi_value = row.get("PREDIKSI_KONSUMSI") or row.get("PREDIKSI") or 0

            new_forecast = Forecast(
                rute=rute_value,
                kode=kode_value,
                kategori_golongan=kategori_value,
                jenis_bangunan=jenis_value,
                tahun=tahun or 0,
                bulan=bulan or 0,
                prediksi=prediksi_value,
                aktual=None
            )
            db.session.add(new_forecast)
        db.session.commit()
        logger.info("Semua forecast A101 berhasil disimpan")
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Gagal simpan forecast A101: {e}")

    return jsonify({
        "evaluasi": evaluasi,
        "forecast": forecast_df.to_dict(orient='records')
    })


# ==========================
# 2️⃣ Route untuk 1 filter
# ==========================
@forecast_bp.route('/forecast/filter', methods=['GET'])
def forecast_filter():
    df = load_data()
    if df is None:
        return jsonify({"error": "Gagal memuat data"}), 500
    
    filter_column = request.args.get('kolom')
    filter_value = request.args.get('nilai')
    tahun = request.args.get('tahun', type=int)
    bulan = request.args.get('bulan', type=int)

    if not filter_column or not filter_value:
        return jsonify({"error": "Parameter kolom dan nilai wajib diisi"}), 400

    forecast_df, evaluasi = forecast_konsumsi(df, filter_column, filter_value, tahun=tahun, bulan=bulan)
    if forecast_df is None:
        return jsonify({"error": f"Gagal forecasting untuk {filter_value}"}), 500

    try:
        for _, row in forecast_df.iterrows():
            rute_value = (row.get("Rute") or filter_value).replace("RUTE:", "").strip().upper()
            kode_value = row.get("Kode") or ""
            kategori_value = row.get("Kategori_Golongan") or row.get("Kategori") or ""
            jenis_value = row.get("Jenis_Bangunan") or ""
            prediksi_value = row.get("PREDIKSI_KONSUMSI") or row.get("PREDIKSI") or 0

            new_forecast = Forecast(
                rute=rute_value,
                kode=kode_value,
                kategori_golongan=kategori_value,
                jenis_bangunan=jenis_value,
                tahun=tahun or 0,
                bulan=bulan or 0,
                prediksi=prediksi_value,
                aktual=None
            )
            db.session.add(new_forecast)
        db.session.commit()
        logger.info("Semua forecast filter berhasil disimpan")
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Gagal simpan forecast filter: {e}")

    return jsonify({
        "evaluasi": evaluasi,
        "forecast": forecast_df.to_dict(orient='records')
    })


# =======================================
# 3️⃣ Route untuk semua filter sekaligus
# =======================================
@forecast_bp.route('/forecast/all', methods=['POST'])
def forecast_all():
    df = load_data()
    if df is None:
        return jsonify({"error": "Gagal memuat data"}), 500

    body = request.get_json()
    filter_list = body.get('filter_list', [])
    tahun = body.get('tahun')
    bulan = body.get('bulan')

    if not filter_list:
        return jsonify({"error": "filter_list wajib diisi"}), 400

    # Terapkan kombinasi filter (AND)
    filtered_df = df.copy()
    for f in filter_list:
        col, val = f.get('kolom'), f.get('nilai')
        if col and val:
            filtered_df = filtered_df[filtered_df[col] == val]

    # Jalankan forecast untuk hasil kombinasi
    forecast_df, evaluasi = forecast_konsumsi(filtered_df, None, None, tahun=tahun, bulan=bulan)

    # Simpan ke DB
    if forecast_df is not None:
        try:
            for _, row in forecast_df.iterrows():
                new_forecast = Forecast(
                    rute=(row.get("Rute") or "").replace("RUTE:", "").strip().upper(),
                    kode=row.get("Kode") or "",
                    kategori_golongan=row.get("Kategori_Golongan") or row.get("Kategori") or "",
                    jenis_bangunan=row.get("Jenis_Bangunan") or "",
                    tahun=tahun or 0,
                    bulan=bulan or 0,
                    prediksi=row.get("PREDIKSI_KONSUMSI") or row.get("PREDIKSI") or 0,
                    aktual=None
                )
                db.session.add(new_forecast)
            db.session.commit()
            logger.info("Forecast kombinasi filter berhasil disimpan")
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Gagal simpan forecast kombinasi: {e}")

    return jsonify({
        "evaluasi": evaluasi,
        "forecast": forecast_df.to_dict(orient='records') if forecast_df is not None else None
    })
