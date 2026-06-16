import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Backend non-GUI (tidak pakai Tkinter)
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error
from statsmodels.tsa.seasonal import seasonal_decompose
from itertools import product
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import time
import logging
logger = logging.getLogger(__name__)



def forecast_rute_a101(df):
    logger.info("=== Mulai proses forecasting RUTE A101 ===")
    try:
        # Filter & urutkan data berdasarkan tanggal
        df_rute = df[df['RUTE'] == 'RUTE: A101'].copy()
        df_rute['TANGGAL'] = pd.to_datetime(df_rute['TANGGAL'])
        df_rute = df_rute.sort_values(by='TANGGAL')
        df_rute.set_index('TANGGAL', inplace=True)

        # Agregasi per bulan (MS = Month Start)
        df_rute = df_rute.groupby(pd.Grouper(freq='MS')).sum()

        # Optional: isi missing value jika ada
        df_rute = df_rute.ffill()  # atau .interpolate()

        series = df_rute['KONSUMSI']
        logger.info("Step 1: Data filtering & aggregasi selesai")

        # === Split Train (80%) & Test (20%) ===
        train_size = int(len(series) * 0.8)
        train, test = series[:train_size], series[train_size:]

        if len(series) < 20:
            logger.info(f"Jumlah data bulanan: {len(series)}")
            raise ValueError("Data terlalu pendek untuk ARIMA. Minimal 20 data bulanan diperlukan")

        # === Uji Stasioneritas (ADF Test) ===
        result = adfuller(series)
        logger.info("=== Hasil Uji ADF ===")
        logger.info(f"ADF Statistic : {result[0]}")
        logger.info(f"p-value       : {result[1]}")
        for key, value in result[4].items():
            logger.info(f"Critical Value {key} : {value}")
        if result[1] < 0.05:
            logger.warning(">> Data sudah stasioner")
        else:
            logger.warning("Data belum stasioner. Mungkin perlu differencing")

        # 1. Fungsi untuk membuat data stasioner & hitung d-nya
        def make_stationary(series):
            d = 0
            while True:
                result = adfuller(series)
                if result[1] < 0.05:
                    break
                series = series.diff().dropna()
                d += 1
                if d < 3:  # batas aman
                    break
            return series, d

        series_stationary, best_d = make_stationary(series)
        logger.info(f"Nilai differencing (d) terbaik: {best_d}")
        logger.info("Step 2: Uji stasioneritas selesai")

         # === Decompose Plot ===
        decomp = seasonal_decompose(series, model='additive')
        decomp.plot()
        plt.tight_layout()
        plt.close()

        # === Plot ACF dan PACF ===
        plt.figure(figsize=(12,5))
        plt.subplot(121)
        plot_acf(series, ax=plt.gca(), lags=17)
        plt.title("Autocorrelation (ACF)")
        plt.subplot(122)
        plot_pacf(series, ax=plt.gca(), lags=17)
        plt.title("Partial Autocorrelation (PACF)")
        plt.tight_layout()
        plt.close()

        logger.info("Step 3: Decomposition & ACF-PACF plot selesai")

        # === Grid Search ARIMA (p,d,q) ===
        best_score, best_cfg = float("inf"), None
        best_model = None
        best_mape = float("inf")
        best_aic = float("inf")

        p_values = range(3, 6)
        q_values = range(3, 6)

        logger.info("\n=== Grid Search ARIMA berdasarkan MAPE dan AIC ===")
        for p, q in product(p_values, q_values):
            try:
                model = ARIMA(train, order=(p, best_d, q)).fit()
                pred = model.predict(start=test.index[0], end=test.index[-1]) 

                # Evaluasi MAPE dan AIC
                mape = mean_absolute_percentage_error(test, pred) * 100
                aic = model.aic

                logger.debug(f"ARIMA({p},{best_d},{q}) MAPE={mape:.2f}%, AIC={aic:.2f}")

                # Pemilihan model terbaik: utamakan MAPE terendah, lalu AIC
                if (mape < best_mape) or (np.isclose(mape, best_mape) and aic < best_aic):
                    best_mape = mape
                    best_aic = aic
                    best_cfg = (p, best_d, q)
                    best_model = model

            except Exception as e:
                continue

        logger.info(f"Best ARIMA{best_cfg} dengan MAPE: {best_mape:.2f}%, AIC: {best_aic:.2f}")
        logger.info("Step 4: Grid search ARIMA selesai, model terbaik: %s", best_cfg)

         # Prediksi untuk test data (data historis bagian test)
        pred_test = best_model.predict(start=test.index[0], end=test.index[-1])

        # Buat DataFrame prediksi historis (train + test)
        pred_hist = pd.concat([
            train.rename('DATA_ASLI'),
            pred_test.rename('PREDIKSI')
        ], axis=1)

        # Gabungkan prediksi historis lengkap dengan data asli di train
        pred_hist = pred_hist.reset_index().rename(columns={'index': 'TANGGAL'})
        # Kalau mau, bisa gabungkan data asli dan prediksi ke dalam 1 kolom prediksi lengkap:
        pred_hist['PREDIKSI_KONSUMSI'] = pred_hist['PREDIKSI'].combine_first(pred_hist['DATA_ASLI'])
        pred_hist = pred_hist[['TANGGAL', 'PREDIKSI_KONSUMSI']]

        # === Forecast ke Depan (6 Tahun / 72 Bulan) ===
        # Re-train model untuk seluruh data jika ingin forecast ke depan
        final_model = ARIMA(series, order=best_cfg).fit()
        forecast_steps = 72
        future_forecast = final_model.forecast(steps=forecast_steps)
        future_dates = pd.date_range(start=series.index[-1] + pd.DateOffset(months=1), periods=forecast_steps, freq='MS')
        forecast_df = pd.DataFrame({
            'TANGGAL': future_dates,
            'PREDIKSI_KONSUMSI': future_forecast
        })

        logger.info("Step 5: Forecast ke depan selesai")

         # Gabungkan prediksi historis + forecast ke depan
        hasil_akhir = pd.concat([pred_hist, forecast_df], ignore_index=True)

        # === Evaluasi Model Terbaik ===
        pred = best_model.predict(start=test.index[0], end=test.index[-1])
        mae = mean_absolute_error(test, pred)
        mse = mean_squared_error(test, pred)
        rmse = np.sqrt(mse)
        mape = mean_absolute_percentage_error(test, pred) * 100
        aic = best_model.aic

        evaluasi = {
            "Best_Order_(p,d,q)": best_cfg,
            "MAE": mae,
            "MSE": mse,
            "RMSE": rmse,
            "MAPE (%)": mape,
            "AIC": aic
        }
        logger.info(f"Evaluasi model: MAE={mae:.2f}, RMSE={rmse:.2f}, MAPE={mape:.2f}%, AIC={aic:.2f}")

        # Generate timestamp unik, misal format 'YYYYmmdd_HHMMSS'
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        logger.info("Step 6: Simpan semua plot selesai")
        logger.info("=== Forecasting RUTE A101 selesai tanpa error ===")

        # Return juga path file plot supaya bisa dipakai di template HTML
        return hasil_akhir, evaluasi

    except Exception as e:
        logger.exception("Error saat forecasting RUTE A101")
        return None, None