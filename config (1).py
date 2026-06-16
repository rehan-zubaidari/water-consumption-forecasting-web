
import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kunci-rahasia-rea'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'database_pengguna.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Konfigurasi Email
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'rehan.210180037@mhs.unimal.ac.id'  # email pengirim
    MAIL_PASSWORD = 'mbldbsskhifmcbhg'  # App Password, bukan password Gmail biasa
    MAIL_DEFAULT_SENDER = 'rehan.210180037@mhs.unimal.ac.id'  # disamakan dengan MAIL_USERNAME
