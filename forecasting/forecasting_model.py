import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_absolute_error, mean_squared_error
from datetime import datetime
from models import KonsumsiAktual
from models import db

def generate_forecast_plot(rute, kode=None, jenis_bangunan=None, kategori_golongan=None):
    print("=== DEBUG FUNGSI generate_forecast_plot ===")
    print("RUTE:", rute)
    print("KODE:", kode)
    print("JENIS:", jenis_bangunan)
    print("GOLONGAN:", kategori_golongan)

    query = KonsumsiAktual.query.filter_by(rute=rute)
    if jenis_bangunan:
        query = query.filter_by(jenis_bangunan=jenis_bangunan)
    if kategori_golongan:
        query = query.filter_by(kategori_golongan=kategori_golongan)

    data = query.all()
    print("JUMLAH DATA HISTORIS DITEMUKAN:", len(data))

    if not data:
        return None, None, None, None, []

    df = pd.DataFrame([{
        "bulan": f"{d.bulan}-{d.tahun}",
        "konsumsi": d.konsumsi
    } for d in data])

    df["bulan"] = pd.to_datetime(df["bulan"], format="%m-%Y")
    df.set_index("bulan", inplace=True)
    df = df.sort_index()

    # ARIMA
    model = ARIMA(df["konsumsi"], order=(1,1,1))
    model_fit = model.fit()

    # Forecast ke depan 72 bulan
    pred_steps = 72
    future_forecast = model_fit.forecast(steps=pred_steps)

    # Evaluasi (menggunakan data training)
    pred_train = model_fit.predict(start=1, end=len(df)-1)
    mae = mean_absolute_error(df["konsumsi"][1:], pred_train)
    mape = np.mean(np.abs((df["konsumsi"][1:] - pred_train) / df["konsumsi"][1:])) * 100
    rmse = np.sqrt(mean_squared_error(df["konsumsi"][1:], pred_train))

    # Plot
    fig, ax = plt.subplots()
    df["konsumsi"].plot(ax=ax, label="Data Aktual")
    future_index = pd.date_range(start="2025-01-01", periods=pred_steps, freq='MS')
    pd.Series(future_forecast.values, index=future_index).plot(ax=ax, label="Prediksi 2025-2030", style='--')
    ax.legend()
    plt.title(f"Forecast Konsumsi Air - {rute}")
    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    forecast_plot = base64.b64encode(img.read()).decode('utf-8')

    # Format hasil prediksi
    hasil_prediksi = []
    for i in range(pred_steps):
        pred_date = future_index[i]
        hasil_prediksi.append({
            "rute": rute,
            "kode": kode,
            "jenis_bangunan": jenis_bangunan,
            "kategori_golongan": kategori_golongan,
            "konsumsi": round(float(future_forecast[i]), 2),
            "tahun": pred_date.year,
            "bulan": pred_date.strftime("%B")  # misalnya: "January"
        })

    return forecast_plot, mae, mape, rmse, hasil_prediksi
