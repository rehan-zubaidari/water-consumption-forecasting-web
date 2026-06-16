import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from itertools import product
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import os
import re
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import logging
logger = logging.getLogger(__name__)

# Map nama bulan ke nomor bulan
bulan_map = {
    "JANUARI":1, "FEBRUARI":2, "MARET":3, "APRIL":4, "MEI":5, "JUNI":6,
    "JULI":7, "AGUSTUS":8, "SEPTEMBER":9, "OKTOBER":10, "NOVEMBER":11, "DESEMBER":12
}


def safe_filename(text):
    return re.sub(r'[\\/*?:"<>|]', '_', text)


def forecast_konsumsi(df, filter_column=None, filter_value=None, tahun=None, bulan=None, save_dir="static/plots"):
    logger.info(f"Mulai forecasting untuk filter {filter_column} = {filter_value}")
    safe_value = safe_filename(str(filter_value))

    try:
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        df_filtered = df.copy()

        # Filter kolom selain tahun/bulan untuk menentukan subset data
        if filter_column and filter_value:
            df_filtered = df_filtered[df_filtered[filter_column] == filter_value].copy()

        # Siapkan kolom tanggal
        df_filtered['TANGGAL'] = pd.to_datetime(df_filtered['TANGGAL'])
        df_filtered = df_filtered.sort_values(by='TANGGAL')
        df_filtered.set_index('TANGGAL', inplace=True)

        # Agregasi bulanan
        df_filtered = df_filtered.groupby(pd.Grouper(freq='MS')).sum()
        df_filtered = df_filtered.ffill()
        series = df_filtered['KONSUMSI']

        # Tambahkan debug sementara
        print("=== Debug series ===")
        print(series.describe())
        print("Jumlah NaN:", series.isna().sum())
        print("Nilai <= 0:", series[series <= 0])

        if len(series) < 20:
            empty_forecast = pd.DataFrame(
                columns=["TANGGAL", "PREDIKSI_KONSUMSI"]
            )
            return empty_forecast, None

        # Uji stasioneritas
        def make_stationary(series):
            d = 0
            while True:
                result = adfuller(series)
                if result[1] < 0.05:
                    break
                series = series.diff().dropna()
                d += 1
                if d < 3:
                    break
            return series, d

        series_stationary, best_d = make_stationary(series)
        logger.info(f"Nilai d terpilih: {best_d}")

        # === Plot ACF & PACF ===
        fig, ax = plt.subplots(1,2,figsize=(12,5))
        plot_acf(series_stationary, ax=ax[0], lags=16)
        plot_pacf(series_stationary, ax=ax[1], lags=16, method="ywm")
        plt.suptitle("ACF & PACF")
        plt.tight_layout()
        acf_pacf_path = os.path.join(save_dir, f"{safe_value}_acf_pacf.png")
        plt.savefig(acf_pacf_path)
        plt.close()

        # Tentukan range p,q khusus untuk Golongan II
        if filter_value == "Gol. II":
            p_range = range(1, 3)  # p=1,2
            q_range = range(1, 3)  # q=1,2
        else:
            p_range = range(1, 4)  # p=2,3,4
            q_range = range(1, 4)  # q=2,3,4

        # Grid search ARIMA (p,q 2-4)
        best_mape = float("inf")
        best_aic = float("inf")
        best_cfg = None
        best_model = None

        train_size = int(len(series) * 0.8)
        train, test = series[:train_size], series[train_size:]

        for p, q in product(p_range, q_range):
            try:
                model = ARIMA(train, order=(p, best_d, q)).fit()
                pred = model.predict(start=test.index[0], end=test.index[-1])
                mape = mean_absolute_percentage_error(test, pred) * 100
                aic = model.aic
                if (mape < best_mape) or (np.isclose(mape, best_mape) and aic < best_aic):
                    best_mape = mape
                    best_aic = aic
                    best_cfg = (p, best_d, q)
                    best_model = model
            except:
                continue

        logger.info(f"Model terbaik: {best_cfg} dengan MAPE {best_mape:.2f}%")

        # Evaluasi model terbaik
        pred = best_model.predict(start=test.index[0], end=test.index[-1])
        mae = mean_absolute_error(test, pred)
        mse = mean_squared_error(test, pred)
        rmse = np.sqrt(mse)

        evaluasi = {
            "Best_Order_(p,d,q)": best_cfg,
            "MAE": mae,
            "MSE": mse,
            "RMSE": rmse,
            "MAPE (%)": best_mape,
            "AIC": best_aic
        }

        # Logging hasil evaluasi lengkap
        logger.info("=== Evaluasi Model Terbaik ===")
        logger.info(f"Order (p,d,q): {best_cfg}")
        logger.info(f"MAPE   : {best_mape:.2f}%")
        logger.info(f"MAE    : {mae:.2f}")
        logger.info(f"MSE    : {mse:.2f}")
        logger.info(f"RMSE   : {rmse:.2f}")
        logger.info(f"AIC    : {best_aic:.2f}")
        logger.info("=============================")

        # === Plot Train vs Test vs Prediksi ===
        plt.figure(figsize=(10,6))
        plt.plot(train.index, train, label="Train")
        plt.plot(test.index, test, label="Test", color="orange")
        plt.plot(test.index, pred, label="Prediksi", color="green")
        plt.legend()
        plt.title(f"Train-Test-Prediksi ARIMA {best_cfg}")
        path_train_test = os.path.join(save_dir, f"{safe_value}_train_test_pred.png")
        plt.savefig(path_train_test)
        plt.close()

        # Forecast 72 bulan ke depan (dimulai setelah data terakhir)
        final_model = ARIMA(series, order=best_cfg).fit()
        forecast_steps = 72
        future_forecast = final_model.forecast(steps=forecast_steps)
        future_dates = pd.date_range(start=series.index[-1] + pd.DateOffset(months=1),
                                     periods=forecast_steps, freq='MS')
        forecast_df = pd.DataFrame({
            'TANGGAL': future_dates,
            'PREDIKSI_KONSUMSI': future_forecast
        })

        # === Plot Data Aktual vs Forecast ===
        plt.figure(figsize=(12,6))
        plt.plot(series.index, series, label="Aktual")
        plt.plot(future_dates, future_forecast, label="Forecast", color="red")
        plt.legend()
        plt.title(f"Aktual vs Forecast ({filter_value})")
        path_forecast = os.path.join(save_dir, f"{safe_value}_actual_forecast.png")
        plt.savefig(path_forecast)
        plt.close()

        # === Seasonal Decompose Plot ===
        decomposition = seasonal_decompose(series, model="additive", period=12)
        fig = decomposition.plot()
        fig.set_size_inches(12,8)
        path_decompose = os.path.join(save_dir, f"{safe_value}_decompose.png")
        plt.savefig(path_decompose)
        plt.close()

        # Gabungkan data aktual & prediksi
        df_actual = df_filtered.reset_index()[['TANGGAL', 'KONSUMSI']]
        df_actual.rename(columns={'KONSUMSI':'PREDIKSI_KONSUMSI'}, inplace=True)
        df_combined = pd.concat([df_actual, forecast_df], ignore_index=True)
        df_combined = df_combined.sort_values('TANGGAL')

        # Filter tahun/bulan sesuai permintaan user
        if tahun:
            df_combined = df_combined[df_combined['TANGGAL'].dt.year == int(tahun)]
        if bulan:
            bulan_num = bulan_map.get(bulan.upper())
            if bulan_num:
                df_combined = df_combined[df_combined['TANGGAL'].dt.month == bulan_num]

        logger.info(f"Forecast selesai. Total baris (aktual + prediksi): {len(df_combined)}")
        return df_combined, evaluasi

    except Exception as e:
        logger.exception(f"Error saat forecasting: {e}")
        return None, None


def jalankan_semua_forecast(df, filter_list, tahun=None, bulan=None):
    hasil = {}
    logger.info(f"Menjalankan semua forecast untuk {len(filter_list)} filter...")

    for filter_column, filter_value in filter_list:
        logger.info(f"=== Mulai forecast {filter_column} = {filter_value} ===")
        forecast_df, evaluasi = forecast_konsumsi(
            df, filter_column, filter_value,
            tahun=tahun,
            bulan=bulan
        )
        hasil[(filter_column, filter_value)] = (forecast_df, evaluasi)

    logger.info("=== Semua forecast selesai ===")
    return hasil