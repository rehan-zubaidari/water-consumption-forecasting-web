from models import db, Rute, Kode, KategoriGolongan, JenisBangunan, Forecast
from datetime import datetime

def simpan_forecast_ke_db(forecast_df, rute_value=None, kode_value=None,
                          kategori_value=None, jenis_value=None):
    """
    Simpan hasil forecast ke database.
    - Menghapus batch lama untuk filter yang sama
    - Menyimpan seluruh 72 bulan forecast
    """

    # --- Pastikan referensi ada di tabel masing-masing ---
    def get_or_create(model, field_name, value):
        if value is None:
            return None
        obj = model.query.filter(getattr(model, field_name)==value).first()
        if not obj:
            obj = model(**{field_name: value})
            db.session.add(obj)
            db.session.flush()
        return obj

    rute_obj = get_or_create(Rute, "rute", rute_value) if rute_value else None
    kode_obj = get_or_create(Kode, "kode", kode_value) if kode_value else None
    kategori_obj = get_or_create(KategoriGolongan, "golongan", kategori_value) if kategori_value else None
    jenis_obj = get_or_create(JenisBangunan, "jenis", jenis_value) if jenis_value else None

    # --- Hapus batch lama untuk filter yang sama ---
    query = Forecast.query
    if rute_obj:
        query = query.filter_by(rute_id=rute_obj.id)
    else:
        query = query.filter(Forecast.rute_id.is_(None))

    if kode_obj:
        query = query.filter_by(kode_id=kode_obj.id)
    else:
        query = query.filter(Forecast.kode_id.is_(None))

    if kategori_obj:
        query = query.filter_by(kategori_golongan_id=kategori_obj.id)
    else:
        query = query.filter(Forecast.kategori_golongan_id.is_(None))

    if jenis_obj:
        query = query.filter_by(jenis_bangunan_id=jenis_obj.id)
    else:
        query = query.filter(Forecast.jenis_bangunan_id.is_(None))

    # Hapus batch lama
    query.delete()
    db.session.commit()

    # --- Insert batch forecast terbaru ---
    for _, row in forecast_df.iterrows():
        tahun, bulan = map(int, row['TANGGAL'].strftime("%Y-%m").split('-'))
        periode = row['TANGGAL'].date()

        new_forecast = Forecast(
            rute_id=rute_obj.id if rute_obj else None,
            kode_id=kode_obj.id if kode_obj else None,
            kategori_golongan_id=kategori_obj.id if kategori_obj else None,
            jenis_bangunan_id=jenis_obj.id if jenis_obj else None,
            tahun=tahun,
            bulan=bulan,
            periode=periode,
            prediksi=row['PREDIKSI_KONSUMSI'],
            aktual=None,
            tanggal_entry=datetime.now()
        )
        db.session.add(new_forecast)

    db.session.commit()
