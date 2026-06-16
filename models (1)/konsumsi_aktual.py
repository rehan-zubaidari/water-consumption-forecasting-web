from models import db
from datetime import datetime

class KonsumsiAktual(db.Model):
    __tablename__ = "konsumsi_aktual"

    id = db.Column(db.Integer, primary_key=True)
    tahun = db.Column(db.Integer)
    bulan = db.Column(db.String(20))
    rute = db.Column(db.String(50))
    kode = db.Column(db.String(10))
    jenis_bangunan = db.Column(db.String(100))
    jumlah_sr = db.Column(db.Integer)
    kategori_golongan = db.Column(db.String(20))
    konsumsi = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

     # Tambahkan kolom baru
    upload_file = db.Column(db.String(100))

    #tabel dummy history forecasting
    is_simulasi = db.Column(db.Boolean, default=False)