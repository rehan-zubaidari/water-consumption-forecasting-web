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

def forecast_rute_a101(df):
    try:
        # Filter & urutkan data berdasarkan tanggal
        df_rute = df[df['RUTE-DESA'] == 'RUTE: A101'].copy()
        df_rute['TANGGAL'] = pd.to_datetime(df_rute['TANGGAL'])
        df_rute = df_rute.sort_values(by='TANGGAL')
        df_rute.set_index('TANGGAL', inplace=True)

        # Agregasi per bulan (MS = Month Start)
        df_rute = df_rute.groupby(pd.Grouper(freq='MS')).sum()

        # Optional: isi missing value jika ada
        df_rute = df_rute.ffill()  # atau .interpolate()

        series = df_rute['KONSUMSI']

        if len(series) < 20:
            raise ValueError("Data terlalu pendek untuk ARIMA. Minimal 20 data bulanan diperlukan")

        # === Uji Stasioneritas (ADF Test) ===
        result = adfuller(series)
        print("=== Hasil Uji ADF ===")
        print(f"ADF Statistic : {result[0]}")
        print(f"p-value       : {result[1]}")
        for key, value in result[4].items():
            print(f"Critical Value {key} : {value}")
        if result[1] < 0.05:
            print(">> Data sudah stasioner")
        else:
            print(">> Data belum stasioner. Mungkin perlu differencing")

        
        # 1. Fungsi untuk membuat data stasioner & hitung d-nya
        def make_stationary(series):
            d = 0
            while True:
                result = adfuller(series)
                if result[1] < 0.05:
                    break
                series = series.diff().dropna()
                d += 1
                if d > 2:  # batas aman
                    break
            return series, d

        series_stationary, best_d = make_stationary(series)
        print(f"Nilai differencing (d) terbaik: {best_d}")

         # === Decompose Plot ===
        decomp = seasonal_decompose(series, model='additive')
        decomp.plot()
        plt.tight_layout()
        plt.savefig("static/decomposition_plot.png")
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
        plt.savefig("static/acf_pacf_plot.png")
        plt.close()

        # === Split Train (80%) & Test (20%) ===
        train_size = int(len(series) * 0.8)
        train, test = series[:train_size], series[train_size:]

        # === Grid Search ARIMA (p,d,q) ===
        best_score, best_cfg = float("inf"), None
        best_model = None
        best_mape = float("inf")
        best_aic = float("inf")

        p_values = range(3, 6)
        q_values = range(3, 6)

        print("\n=== Grid Search ARIMA berdasarkan MAPE dan AIC ===")
        for p, q in product(p_values, q_values):
            try:
                model = ARIMA(train, order=(p, best_d, q)).fit()
                pred = model.predict(start=test.index[0], end=test.index[-1]) 

                # Evaluasi MAPE dan AIC
                mape = mean_absolute_percentage_error(test, pred) * 100
                aic = model.aic

                print(f"ARIMA({p},{best_d},{q}) MAPE={mape:.2f}%, AIC={aic:.2f}")

                # Pemilihan model terbaik: utamakan MAPE terendah, lalu AIC
                if (mape < best_mape) or (np.isclose(mape, best_mape) and aic < best_aic):
                    best_mape = mape
                    best_aic = aic
                    best_cfg = (p, best_d, q)
                    best_model = model

            except Exception as e:
                continue

        print(f"\n>> Best ARIMA{best_cfg} dengan MAPE: {best_mape:.2f}%, AIC: {best_aic:.2f}")

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

        # Cetak hasil evaluasi ke terminal
        print("\n=== Evaluasi Model Terbaik ===")
        for k, v in evaluasi.items():
            if isinstance(v, (int, float)):
                print(f"{k:<20}: {v:.2f}")
            else:
                print(f"{k:<20}: {v}")


        # === Evaluasi Model Manual (misalnya ARIMA(2,1,2)) ===
        manual_order = (4, 1, 4)  
        try:
            manual_model = ARIMA(train, order=manual_order).fit()
            manual_pred = manual_model.predict(start=test.index[0], end=test.index[-1])
            manual_mae = mean_absolute_error(test, manual_pred)
            manual_mse = mean_squared_error(test, manual_pred)
            manual_rmse = np.sqrt(manual_mse)
            manual_mape = mean_absolute_percentage_error(test, manual_pred) * 100
            manual_aic = manual_model.aic

            evaluasi_manual = {
                "Manual_Order_(p,d,q)": manual_order,
                "MAE": manual_mae,
                "MSE": manual_mse,
                "RMSE": manual_rmse,
                "MAPE (%)": manual_mape,
                "AIC": manual_aic
            }

            print("\n=== Evaluasi Model Manual ===")
            for k, v in evaluasi_manual.items():
                if isinstance(v, (int, float)):
                    print(f"{k:<20}: {v:.2f}")
                else:
                    print(f"{k:<20}: {v}")

        except Exception as e:
            print(f"\n>> Gagal menjalankan ARIMA manual {manual_order}: {e}")
            evaluasi_manual = None

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

        # Ganti dengan parameter manual
        manual_order = (4, 1, 4)  # (p, d, q)

        # Latih model dengan seluruh data (bukan hanya training)
        final_manual_model = ARIMA(series, order=manual_order).fit()

        # Jumlah langkah prediksi ke depan
        forecast_steps = 72

        # Prediksi 72 bulan ke depan
        future_manual_forecast = final_manual_model.forecast(steps=forecast_steps)

        # Buat tanggal untuk hasil prediksi (mulai dari bulan setelah data terakhir)
        future_manual_dates = pd.date_range(
            start=series.index[-1] + pd.DateOffset(months=1),
            periods=forecast_steps,
            freq='MS'  # MS = Month Start
        )

        # Buat DataFrame hasil forecast
        forecast_manual_df = pd.DataFrame({
            'TANGGAL': future_manual_dates,
            'PREDIKSI_KONSUMSI': future_manual_forecast
        })


        plt.figure(figsize=(12, 5))
        plt.plot(train.index, train.values, label="Training Data")
        plt.plot(test.index, test.values, label="Testing Data", linestyle='--', color='green')
        plt.plot(forecast_df['TANGGAL'], forecast_df['PREDIKSI_KONSUMSI'], label="Forecast", color='orange')
        plt.title("Forecast Konsumsi Air - RUTE A101")
        plt.xlabel("Tanggal")
        plt.ylabel("Konsumsi")
        plt.legend()
        plt.tight_layout()
        plt.savefig("static/forecast_plot_a101.png")
        plt.close()


        # Plot hasil forecast manual
        plt.figure(figsize=(12, 5))
        plt.plot(series, label="Data Aktual")
        plt.plot(forecast_manual_df['TANGGAL'], forecast_manual_df['PREDIKSI_KONSUMSI'], label="Forecast (Manual Order)", color='red')
        plt.title("Forecast Konsumsi Air - RUTE A101 (Manual Order)")
        plt.xlabel("Tanggal")
        plt.ylabel("Konsumsi")
        plt.legend()
        plt.tight_layout()
        plt.savefig("static/forecast_plot_a101_manual.png")
        plt.close()

        return forecast_df, evaluasi,  evaluasi_manual,  forecast_manual_df

    except Exception as e:
        print(f"Error saat forecasting RUTE A101: {e}")
        return None, None
    


    # routenya
#@app.route('/forecasting-konsumsi', methods=["GET", "POST"])
#def forecasting_konsumsi():
    data = KonsumsiAktual.query.all()
    
    df_konsumsi = pd.DataFrame([
        {
            'TANGGAL': f"{d.tahun}-{bulan_to_num(d.bulan)}-01",
            'KONSUMSI': d.konsumsi,
            'RUTE-DESA': d.rute
        }
        for d in data
    ])
    
    # Panggil fungsi forecast_rute_a101 sekali saja
    hasil_forecast, hasil_evaluasi, hasil_evaluasi_manual, hasil_forecast_manual = forecast_rute_a101(df_konsumsi)

    # Cetak hasil evaluasi di terminal
    if hasil_evaluasi:
        print("=== Evaluasi Model ===")
        for k, v in hasil_evaluasi.items():
            if isinstance(v, (int, float)):
                print(f"{k} : {v:.2f}")
            else:
                print(f"{k} : {v}")

    if hasil_forecast is None:
        flash("Terjadi kesalahan saat proses forecasting. Pastikan data sudah benar.", "danger")
        return redirect(url_for("forecasting_konsumsi"))
    
    # PAGINATION
    page = int(request.args.get("page", 1))
    per_page = 25
    total_pages = int(np.ceil(len(hasil_forecast) / per_page))
    start = (page - 1) * per_page
    end = start + per_page
    paginated_forecast = hasil_forecast.iloc[start:end]

    # Tambahkan path ke gambar setelah hasil forecast berhasil
    acf_pacf_plot_path = ACF_PACF_PLOT
    forecast_plot_path = FORECAST_PLOT
    forecast_manual_plot_path = FORECAST_MANUAL_PLOT
    decomposition_plot_path = "static/decomposition_plot.png"

    return render_template(
        'forecasting_konsumsi.html',
        active_page="forecasting_konsumsi",
        forecast_df=paginated_forecast.iterrows(),
        evaluasi=hasil_evaluasi,  # <-- tampilkan ke HTML juga
        evaluasi_manual=hasil_evaluasi_manual,
        forecast_manual_df=hasil_forecast_manual,
        acf_pacf_plot=acf_pacf_plot_path,
        forecast_plot=forecast_plot_path,
        forecast_manual_plot=forecast_manual_plot_path,
        decomposition_plot=decomposition_plot_path,
        page=page,
        total_pages=total_pages,
        per_page=per_page
        
    )