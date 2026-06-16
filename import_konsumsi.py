import csv
import codecs

from app import app
from models import db
from models.konsumsi_aktual import KonsumsiAktual

with app.app_context():
    with codecs.open('static/uploads/DATA_KONSUMSI_AKTUAL.csv', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        print(reader.fieldnames)
        reader.fieldnames = [field.strip() for field in reader.fieldnames]
        for row in reader:
            data = KonsumsiAktual(
                tahun=int(row['Tahun']),
                bulan=row['Bulan'],
                rute=row['Rute'],
                kode=row['Kode'],
                jenis_bangunan=row['Jenis Bangunan'],
                jumlah_sr=int(row['Jumlah SR']),
                kategori_golongan=row['Kategori Golongan'],
                konsumsi=float(row['Konsumsi (M3)']),
                is_simulasi=True 
            )
            db.session.add(data)
        db.session.commit()
        print("Import selesai")