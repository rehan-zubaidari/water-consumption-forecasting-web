from models.master import db, Rute, Kode, JenisBangunan, KategoriGolongan, Forecast
from models.konsumsi_aktual import KonsumsiAktual


def sync_master_tables():
    # Hapus data lama di master table sebelum sinkronisasi
    #db.session.query(Rute).delete()
    #db.session.query(Kode).delete()
    #db.session.query(JenisBangunan).delete()
    #db.session.query(KategoriGolongan).delete()
    #db.session.commit()

    # --- Rute dari KonsumsiAktual dan Forecast ---
    """
        Sinkronisasi data master (Rute, Kode, JenisBangunan, KategoriGolongan)
        dari tabel KonsumsiAktual dan Forecast.
        """

    # --- Rute ---
    semua_rute_data = (
        db.session.query(KonsumsiAktual.rute).distinct().all() +
        db.session.query(Rute.rute).join(Forecast, Forecast.rute_id == Rute.id).distinct().all()
    )
    rute_list = sorted({str(r[0]).strip() for r in semua_rute_data if r and r[0]})

    for rute_name in rute_list:
        if not Rute.query.filter_by(rute=rute_name).first():
            db.session.add(Rute(rute=rute_name))

    # --- Kode ---
    semua_kode_data = (
        db.session.query(KonsumsiAktual.kode).distinct().all() +
        db.session.query(Kode.kode).join(Forecast, Forecast.kode_id == Kode.id).distinct().all()
    )
    kode_list = sorted({str(k[0]).strip() for k in semua_kode_data if k and k[0]})

    for kode_name in kode_list:
        if not Kode.query.filter_by(kode=kode_name).first():
            db.session.add(Kode(kode=kode_name))

    # --- Jenis Bangunan ---
    semua_jenis_data = (
        db.session.query(KonsumsiAktual.jenis_bangunan).distinct().all() +
        db.session.query(JenisBangunan.jenis).join(Forecast, Forecast.jenis_bangunan_id == JenisBangunan.id).distinct().all()
    )
    jenis_list = sorted({str(j[0]).strip() for j in semua_jenis_data if j and j[0]})

    for jenis_name in jenis_list:
        if not JenisBangunan.query.filter_by(jenis=jenis_name).first():
            db.session.add(JenisBangunan(jenis=jenis_name))

    # --- Kategori Golongan ---
    semua_golongan_data = (
        db.session.query(KonsumsiAktual.kategori_golongan).distinct().all() +
        db.session.query(KategoriGolongan.golongan).join(Forecast, Forecast.kategori_golongan_id == KategoriGolongan.id).distinct().all()
    )
    golongan_list = sorted({str(g[0]).strip() for g in semua_golongan_data if g and g[0]})

    for golongan_name in golongan_list:
        if not KategoriGolongan.query.filter_by(golongan=golongan_name).first():
            db.session.add(KategoriGolongan(golongan=golongan_name))

    # Commit semua perubahan
    db.session.commit()