from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import semua model agar dikenali saat migrasi
from .user import User
from .konsumsi_aktual import KonsumsiAktual

from .master import db, Rute, Kode, JenisBangunan, KategoriGolongan, Forecast