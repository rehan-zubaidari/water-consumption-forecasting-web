
from models import db
from datetime import datetime

class Rute(db.Model):
    __tablename__ = "rute"
    id = db.Column(db.Integer, primary_key=True)
    rute = db.Column(db.String(50), nullable=True, unique=True)

    def __repr__(self):
        return f"<Rute {self.rute}>"

class Kode(db.Model):
    __tablename__ = "kode"
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String(10), nullable=True, unique=True)

    def __repr__(self):
        return f"<Kode {self.kode}>"

class JenisBangunan(db.Model):
    __tablename__ = "jenis_bangunan"
    id = db.Column(db.Integer, primary_key=True)
    jenis = db.Column(db.String(100), nullable=True, unique=True)

    def __repr__(self):
        return f"<JenisBangunan {self.jenis}>"

class KategoriGolongan(db.Model):
    __tablename__ = "kategori_golongan"
    id = db.Column(db.Integer, primary_key=True)
    golongan = db.Column(db.String(20), nullable=True, unique=True)

    def __repr__(self):
        return f"<KategoriGolongan {self.golongan}>"

class Forecast(db.Model):
    __tablename__ = "forecast"
    id = db.Column(db.Integer, primary_key=True)
    rute_id = db.Column(db.Integer, db.ForeignKey("rute.id"), nullable=True)
    kode_id = db.Column(db.Integer, db.ForeignKey("kode.id"), nullable=True)
    kategori_golongan_id = db.Column(db.Integer, db.ForeignKey("kategori_golongan.id"), nullable=True)
    jenis_bangunan_id = db.Column(db.Integer, db.ForeignKey("jenis_bangunan.id"), nullable=True)
    
    tahun = db.Column(db.Integer, nullable=False)
    bulan = db.Column(db.Integer, nullable=False)
    periode = db.Column(db.Date, nullable=False)    # periode yang diprediksi
    prediksi = db.Column(db.Float, nullable=False)
    aktual = db.Column(db.Float, nullable=True)
    tanggal_entry = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relasi opsional
    rute = db.relationship("Rute", backref=db.backref("forecasts", lazy=True))
    kode = db.relationship("Kode", backref=db.backref("forecasts", lazy=True))
    kategori_golongan = db.relationship("KategoriGolongan", backref=db.backref("forecasts", lazy=True))
    jenis_bangunan = db.relationship("JenisBangunan", backref=db.backref("forecasts", lazy=True))
