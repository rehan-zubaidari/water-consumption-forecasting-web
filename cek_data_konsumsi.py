from app import app
from models import db
from models.konsumsi_aktual import KonsumsiAktual

with app.app_context():
    data = KonsumsiAktual.query.all()
    print(f"Jumlah data yang berhasil diimport: {len(data)}")
    
    # Tampilkan 5 baris pertama
    for item in data[:5]:
        print(item.tahun, item.bulan, item.rute, item.konsumsi)
