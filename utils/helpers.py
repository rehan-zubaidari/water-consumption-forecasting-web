from models.konsumsi_aktual import KonsumsiAktual
from models import db

def get_rute_options():
    rute_list = db.session.query(KonsumsiAktual.rute).distinct().all()
    return sorted([r[0] for r in rute_list if r[0]])

def get_kode_options():
    kode_list = db.session.query(KonsumsiAktual.kode).distinct().all()
    return sorted([k[0] for k in kode_list if k[0]])

def get_jenis_bangunan_options():
    jenis_list = db.session.query(KonsumsiAktual.jenis_bangunan).distinct().all()
    return sorted([j[0] for j in jenis_list if j[0]])

def get_kategori_golongan_options():
    golongan_list = db.session.query(KonsumsiAktual.kategori_golongan).distinct().all()
    return sorted([g[0] for g in golongan_list if g[0]])
