import sqlite3

# Ganti sesuai path database SQLite-mu
conn = sqlite3.connect("db_forecasting_air.db")  
c = conn.cursor()

# Hapus tabel forecast lama
c.execute("DROP TABLE IF EXISTS forecast;")
# Hapus temporary table yang bikin error
c.execute("DROP TABLE IF EXISTS _alembic_tmp_jenis_bangunan;")

conn.commit()
conn.close()
print("Tabel lama berhasil dihapus.")
