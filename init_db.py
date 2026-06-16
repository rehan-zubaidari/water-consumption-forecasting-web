# init_db.py
from app import app, db
from models.master import Rute, Kode, JenisBangunan, KategoriGolongan, Forecast

# Masuk ke application context
with app.app_context():
    db.create_all()
    print("Semua tabel berhasil dibuat!")