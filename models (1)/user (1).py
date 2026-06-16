from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db  # gunakan relative import dari __init__.py


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    employee_id = db.Column(db.String(50), unique=True, nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=True)
    verification_code = db.Column(db.String(10), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)           # Email link activated
    is_phone_verified = db.Column(db.Boolean, default=False)     # OTP sudah diinput
    profile_picture = db.Column(db.String(200), nullable=True)

    #kolom baru
    nik = db.Column(db.String(16), unique=True, nullable=True)  # 16 digit NIK
    address = db.Column(db.String(255), nullable=True)
    position = db.Column(db.String(100), nullable=True)          # untuk field posisi di kiri
    education = db.Column(db.String(50), nullable=True)          # pendidikan terakhir
    family_contact = db.Column(db.String(50), nullable=True)     # kontak keluarga
    social_media = db.Column(db.String(200), nullable=True)      # media sosial


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'
