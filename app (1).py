from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import check_password_hash
from datetime import datetime, UTC, timedelta
from werkzeug.utils import secure_filename
from utils.forecasting import forecast_rute_a101
from utils.forecast_filters import forecast_konsumsi
from utils.forecast_filters import jalankan_semua_forecast
from utils.helpers import get_rute_options, get_jenis_bangunan_options, get_kategori_golongan_options
from routes.forecast_routes import forecast_bp
from routes.forecast_history import forecast_history_bp
from models.master import Forecast
from models import Rute, Kode, JenisBangunan, KategoriGolongan, Forecast, db
from utils.save_forecast import simpan_forecast_ke_db
from io import StringIO
import random, time
import logging
import pandas as pd
import os
import json
import pytz

from config import Config
from models import db
from models.user import User
from models.konsumsi_aktual import KonsumsiAktual

# Di bagian atas file Python
ACF_PACF_PLOT = "static/acf_pacf_plot.png"
FORECAST_PLOT = "static/forecast_plot_a101.png"
FORECAST_MANUAL_PLOT = "static/forecast_plot_a101_manual.png"


wib = pytz.timezone('Asia/Jakarta')
now_wib = datetime.now(wib)

# Setup logging
logging.basicConfig(
    level=logging.INFO,  # Bisa ganti ke DEBUG, WARNING, ERROR sesuai kebutuhan
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),  # Simpan log ke file app.log
        logging.StreamHandler()           # Juga tampilkan di console
    ]
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

forecast_cache = {}

# Folder & ekstensi untuk unggah data konsumsi
UPLOAD_FOLDER_DATA = os.path.join(app.root_path, 'static', 'uploads', 'data')
ALLOWED_EXTENSIONS_DATA = {'csv'}
app.config['UPLOAD_FOLDER_DATA'] = UPLOAD_FOLDER_DATA

# Folder & ekstensi untuk unggah foto profil
UPLOAD_FOLDER_PROFILE = os.path.join(app.root_path, 'static', 'uploads', 'profile_pictures')
ALLOWED_EXTENSIONS_PROFILE = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER_PROFILE'] = UPLOAD_FOLDER_PROFILE

# Fungsi helper (umum, tapi param allowed_extensions dibedakan)
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
# ---------------------------------------------------

app.register_blueprint(forecast_bp)

# Register blueprint
app.register_blueprint(forecast_history_bp, url_prefix="/history")

# Setup email
mail = Mail(app)

# Setup token serializer untuk email verification
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Setup database & migrasi
db.init_app(app)
migrate = Migrate(app, db)


# Setup login manager
login_manager = LoginManager()
login_manager.login_view = 'login'  # Akan redirect ke /login kalau belum login
login_manager.init_app(app)

def bulan_to_num(bulan):
    mapping = {
        "JANUARI": "01",
        "FEBRUARI": "02",
        "MARET": "03",
        "APRIL": "04",
        "MEI": "05",
        "JUNI": "06",
        "JULI": "07",
        "AGUSTUS": "08",
        "SEPTEMBER": "09",
        "OKTOBER": "10",
        "NOVEMBER": "11",
        "DESEMBER": "12"
    }
    return mapping[bulan.upper()]

# Fungsi load user dari session
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        employee_id = request.form.get("employee_id", "").strip()
        birth_date = request.form.get("birth_date", "").strip()
        gender = request.form.get("gender", "").strip().lower()

        # Validasi sederhana
        if not all([full_name, employee_id, birth_date, gender]):
            flash("Semua field wajib diisi.")
            return redirect(url_for('signup'))

        # Cek jika ID pegawai sudah dipakai 
        existing_user = User.query.filter_by(employee_id=employee_id).first()
        if existing_user:
            flash("ID Pegawai sudah terdaftar.")
            return redirect(url_for('signup'))

        # Simpan ke session
        session['full_name'] = full_name
        session['employee_id'] = employee_id
        session['birth_date'] = birth_date
        session['gender'] = gender

        return redirect(url_for('signup_biodata'))

    return render_template("signup.html")


@app.route("/signup-biodata", methods=["GET", "POST"])
def signup_biodata():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Password dan konfirmasi tidak cocok.")
            return redirect(url_for("signup_biodata"))

        # Cek apakah email sudah terdaftar
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash(" Email sudah digunakan.")
            return redirect(url_for("signup_biodata"))

        # Simpan sementara ke session
        session['email'] = email
        session['password'] = password

        # Buat token dan kirim email aktivasi
        token = serializer.dumps(email, salt='email-activation')
        send_activation_email(email, token)

        flash("Link aktivasi telah dikirim ke email kamu. Silakan cek email sebelum melanjutkan.")
        return redirect(url_for("signup_biodata"))

    return render_template("signup_biodata.html")

def send_activation_email(email, token):
    link = url_for('activate_account', token=token, _external=True)
    msg = Message("Aktivasi Akun Anda", recipients=[email])
    msg.body = f"""
Hai, terima kasih sudah mendaftar di sistem Forecasting Konsumsi Air Minum di PERUMDA Aceh Tamiang.

Silakan klik link berikut untuk mengaktifkan akun Anda:
{link}

Catatan:
Link ini hanya berlaku selama 10 menit demi alasan keamanan.

Salam,
Admin Tirta Tamiang
"""
    mail.send(msg)


@app.route("/activate/<token>")
def activate_account(token):
    try:
        # Decode token dan ambil email
        email = serializer.loads(token, salt='email-activation', max_age=600)

        # Cek apakah user dengan email ini sudah ada di database
        user = User.query.filter_by(email=email).first()

        if user:
            if user.is_verified:
                flash("Akun sudah aktif. Silakan login.")
                return redirect(url_for("login"))
            else:
                # Verifikasi akun yang belum aktif
                user.is_verified = True
                db.session.commit()
        else:
            # Ambil data dari session
            full_name = session.get("full_name")
            employee_id = session.get("employee_id")
            birth_date_str = session.get("birth_date")
            gender = session.get("gender")
            password = session.get("password")

            # Cek apakah ada yang kosong (misalnya session kadaluarsa)
            if not all([full_name, employee_id, birth_date_str, gender, password]):
                flash("Session pendaftaran kadaluarsa. Silakan daftar ulang.")
                return redirect(url_for("signup"))

            # Format tanggal lahir
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")

            # Buat user baru
            user = User(
                full_name=full_name,
                employee_id=employee_id,
                birth_date=birth_date,
                gender=gender,
                email=email,
                phone_number="",  # Akan diisi nanti di route input nomor HP
                is_verified=True,  # Jika email sudah diverifikasi
                is_phone_verified=False  # Belum verifikasi nomor HP
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        
        logging.info(f"User signup: {user.full_name} - {user.employee_id}")

        # Simpan session untuk lanjut ke nomor HP
        session['user_id'] = user.id
        session['email'] = user.email
        session['email_verified'] = True

        flash("Email berhasil diverifikasi. Silakan lanjutkan dengan nomor handphone.")
        return render_template("activation_success.html")

    except Exception as e:
        print("Activation error:", e)
        flash("Link aktivasi tidak valid atau sudah kedaluwarsa.")
        return redirect(url_for("signup"))


@app.route("/signup-phone-number", methods=["GET", "POST"])
def signup_phone_number():
    if not session.get("email_verified"):
        flash("Silakan verifikasi email terlebih dahulu.")
        return redirect(url_for("signup"))

    if request.method == "POST":
        phone_number = request.form.get("phone_number")

        if not phone_number or not phone_number.isdigit() or len(phone_number) < 10:
            flash("Masukkan nomor HP yang valid (minimal 10 digit).")
            return redirect(url_for("signup_phone_number"))

        session['phone_number'] = phone_number

        otp_code = str(random.randint(100000, 999999)).zfill(6)
        session['otp_code_signup'] = otp_code
        session['otp_code_expiry'] = time.time() + 300

        email = session.get("email")
        if email:
            send_otp_email(email, otp_code)
            flash("Kode verifikasi telah dikirim ke email kamu.")
            return redirect(url_for("verification_code"))
        else:
            flash("Session email tidak ditemukan. Silakan daftar ulang.")
            return redirect(url_for("signup"))

    return render_template("signup_phone_number.html")

def send_otp_email(email, otp):
    msg = Message("Kode Verifikasi - Nomor HP", recipients=[email])
    msg.body = f"Hai, kode verifikasi kamu adalah: {otp}\nSilakan masukkan kode ini untuk verifikasi nomor handphone.\n\nKode berlaku selama 5 menit."
    mail.send(msg)


@app.route("/verification-code", methods=["GET", "POST"])
def verification_code():
    if request.method == "POST":
        kode_input = request.form.get("verification_code")  # Nama input form OTP

        # Cek apakah OTP masih berlaku
        if time.time() > session.get("otp_code_expiry", 0):
            flash("Kode verifikasi telah kedaluwarsa. Silakan kirim ulang.")
            return redirect(url_for("verification_code"))

        # Cek apakah OTP cocok
        if kode_input == session.get("otp_code_signup"):
            email = session.get("email")
            phone_number = session.get("phone_number")

            if not email or not phone_number:
                flash("Data session tidak lengkap. Silakan daftar ulang.")
                return redirect(url_for("signup"))

            user = User.query.filter_by(email=email).first()
            if not user:
                flash("User tidak ditemukan.")
                return redirect(url_for("signup"))

            # Simpan nomor HP & status verifikasi
            user.phone_number = phone_number
            user.verification_code = kode_input
            user.is_phone_verified = True
            db.session.commit()

            session.clear()
            session['verified_success'] = True
            flash("Akun berhasil dibuat.")
            return redirect(url_for("verified"))
        else:
            flash("Kode verifikasi salah.")
            return redirect(url_for("verification_code"))

    return render_template("signup_verification.html")


@app.route('/resend-code-signup')
def resend_code_signup():
    email = session.get('email')
    
    # Cek ke database juga
    user = User.query.filter_by(email=email).first()
    if not email or not user:
        session.clear()  # bersihkan jejak session
        flash('Data tidak ditemukan. Silakan daftar ulang.')
        return redirect(url_for('signup'))

    otp_code = str(random.randint(100000, 999999)).zfill(6)
    session['otp_code_signup'] = otp_code
    session['otp_code_expiry'] = time.time() + 300

    send_otp_email(email, otp_code)
    flash('Kode verifikasi baru telah dikirim ke email.')
    return redirect(url_for('verification_code'))


@app.route('/verified')
def verified():
    if not session.get('verified_success'):
        flash("Akses tidak sah.")
        return redirect(url_for('signup'))
    session.pop('verified_success', None)
    session.clear()
    return render_template('verified.html')


# <<<<  SELESAIII UNTUK HALAMAN SIGNUP SEMUA    >>>>


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("Email tidak ditemukan", "error")
            return redirect(url_for("login"))

        if not user.is_phone_verified:
            flash("Nomor HP kamu belum diverifikasi. Silakan input kode OTP")
            return redirect(url_for("verification_code"))

        if not user.check_password(password):
            flash("Password salah", "error")
            return redirect(url_for("login"))

        # Simpan informasi ke session
        session.clear()
        session['user_id'] = user.id
        session['user_name'] = user.full_name
        session['user_email'] = user.email
        session['login_time'] = datetime.utcnow().timestamp()
        session['user_profile_picture'] = f"uploads/profile_pictures/{user.profile_picture}" if user.profile_picture else "uploads/profile_pictures/default_profile.png"

        flash("Login berhasil. Selamat datang, {}!".format(user.full_name), "success")
        return redirect(url_for("dashboard"))  
    return render_template('login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            # Generate token untuk reset password
            token = serializer.dumps(email, salt='reset-password')

            # Buat link reset
            reset_link = url_for('reset_password_token', token=token, _external=True)

            # Kirim email
            msg = Message('Reset Your Password', recipients=[email])
            msg.body = f'''
Hai {user.full_name},

Kami menerima permintaan untuk mereset password akun kamu
Klik link di bawah ini untuk melanjutkan:

{reset_link}

Link ini berlaku selama 10 menit

Jika kamu tidak meminta ini, abaikan saja email ini
'''
            mail.send(msg)
            flash('Link reset password telah dikirim ke email kamu.')
        else:
            flash('Email tidak ditemukan!')

        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_token(token):
    if 'user_email' not in session:
        try:
            email = serializer.loads(token, salt='reset-password', max_age=600)
            session['user_email'] = email  # Simpan ke session
        except Exception:
            flash("Link tidak valid atau sudah kedaluwarsa.")
            return redirect(url_for('forgot_password'))

    # Ambil dari session supaya bisa dipakai di bawah
    email = session.get('user_email')

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash("Semua field wajib diisi.")
            return redirect(url_for('reset_password_token', token=token))

        if new_password != confirm_password:
            flash("Password dan konfirmasi tidak cocok.")
            return redirect(url_for('reset_password_token', token=token))

        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(new_password)
            db.session.commit()

            flash("Password berhasil diubah. Silakan verifikasi nomor handphone.")
            return redirect(url_for('reset_phone_number'))
        else:
            flash("Pengguna tidak ditemukan.")
            return redirect(url_for('forgot_password'))

    return render_template('reset_new_password.html', token=token)


@app.route('/reset-phone-number', methods=['GET', 'POST'])
def reset_phone_number():
    if request.method == 'POST':
        phone_number = request.form.get('new_phone_number')

        if not phone_number.isdigit() or len(phone_number) < 10:
            flash("Invalid phone number. Please enter a valid number.")
            return redirect(url_for('reset_phone_number'))

        session['reset_phone_number'] = phone_number

        user_email = session.get('user_email')
        if not user_email:
            flash('Session expired. Please log in again.')
            return redirect(url_for('login'))

        # Generate OTP dan simpan khusus untuk RESET
        otp_code = str(random.randint(100000, 999999)).zfill(6)
        session['otp_code_reset'] = otp_code
        session['otp_code_reset_expiry'] = time.time() + 300  # expired 5 menit

        msg = Message('Verification Code - Reset Phone Number', recipients=[user_email])
        msg.body = f'Your verification code is: {otp_code}'
        mail.send(msg)

        flash('Verification code has been sent to your email.')
        return redirect(url_for('verify_code'))

    return render_template('reset_phone_number.html')


@app.route('/verify-code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        entered_code = request.form.get('otp_code')

        if 'otp_code_reset' in session:
            # Proses reset nomor
            saved_code = session.get('otp_code_reset')
            expiry = session.get('otp_code_reset_expiry')
            user_email = session.get('user_email')
            new_phone_number = session.get('reset_phone_number')
            proses = 'reset'
        else:
            # Proses signup
            saved_code = session.get('otp_code_signup')
            expiry = session.get('otp_code_expiry')
            user_email = session.get('email')
            new_phone_number = session.get('phone_number')
            proses = 'signup'

        if not saved_code or not expiry or not user_email or not new_phone_number:
            flash('Kode verifikasi tidak tersedia. Silakan mulai ulang proses.')
            return redirect(url_for('reset_phone_number') if proses == 'reset' else url_for('signup_phone_number'))

        if time.time() > expiry:
            flash('Kode verifikasi sudah kedaluwarsa.')
            return redirect(url_for('reset_phone_number') if proses == 'reset' else url_for('signup_phone_number'))

        if entered_code == saved_code:
            flash('Verifikasi berhasil.')

            user = User.query.filter_by(email=user_email).first()
            if user:
                if proses == 'reset':
                    user.phone_number = new_phone_number
                    user.is_phone_verified = True
                    db.session.commit()

                    session['full_name'] = user.full_name
                    session['verified_success'] = True

                    # Hapus session terkait OTP reset
                    session.pop('otp_code_reset', None)
                    session.pop('otp_code_reset_expiry', None)
                    session.pop('reset_phone_number', None)
                    session.pop('resend_count_reset', None)

                    flash('Nomor handphone berhasil diperbarui.')
                    return redirect(url_for('verify_success'))

                else:  # proses signup
                    session['full_name'] = user.full_name
                    session['verified_success'] = True

                    # Hapus session terkait OTP signup
                    session.pop('otp_code_signup', None)
                    session.pop('otp_code_expiry', None)
                    session.pop('phone_number', None)
                    session.pop('resend_count_signup', None)

                    return redirect(url_for('verify_success'))

            else:
                flash('Pengguna tidak ditemukan.')
                return redirect(url_for('login'))

    else:
        return render_template('verify_code.html')


@app.route('/resend-code-reset')
def resend_code_reset():
    email = session.get('user_email')
    if not email:
        flash('Session expired. Please log in again.')
        return redirect(url_for('login'))

    # Opsi: Batasi jumlah pengiriman OTP (maks. 3x)
    resend_count = session.get('resend_count_reset', 0)
    if resend_count >= 3:
        flash("Kamu sudah mengirim kode terlalu sering. Coba lagi nanti.")
        return redirect(url_for('verify_code'))

    # Generate OTP baru
    otp_code = str(random.randint(100000, 999999)).zfill(6)
    session['otp_code_reset'] = otp_code
    session['otp_code_reset_expiry'] = time.time() + 300  # 5 menit

    # Tambahkan hitungan resend
    session['resend_count_reset'] = resend_count + 1

    # Kirim ke email
    msg = Message('Resend Verification Code - Reset Phone Number', recipients=[email])
    msg.body = f'Kode verifikasi terbaru untuk reset nomor HP kamu adalah: {otp_code}\nKode berlaku 5 menit.'
    mail.send(msg)

    flash('Kode verifikasi baru telah dikirim ke email kamu.')
    return redirect(url_for('verify_code'))

@app.route('/verify-success')
def verify_success():
    if not session.get('verified_success'):
        flash('Akses tidak valid.')
        return redirect(url_for('login'))

    full_name = session.get('full_name', 'Pengguna')
    return render_template('verify_success.html', full_name=full_name)


@app.route('/verify-clear')
def verify_clear():
    session.pop('verified_success', None)
    session.pop('resend_count_reset', None)
    session.pop('otp_code_reset', None)
    session.pop('otp_code_reset_expiry', None)
    session.pop('reset_phone_number', None)
    session.pop('user_email', None)
    return redirect(url_for('login'))

# <<<<  SELESAIII UNTUK HALAMAN LOGIN SEMUA    >>>>

# <<<<  UNTUK MASA AKTIF PAGE    >>>>
@app.before_request
def session_timeout():
    protected_routes = [
        'dashboard',
        'data_konsumsi_aktual',
        'download_konsumsi_aktual',
        'forecasting_konsumsi',
        'forecast_history',
        'unggah_data_konsumsi',
        'confirm_upload',
        'profil_saya',
        'upload_profile_picture',
        'logout',
    ]

    if request.endpoint in protected_routes and 'user_id' in session:
        login_time = session.get('login_time')
        current_time = datetime.utcnow().timestamp()

        if not login_time or (current_time - login_time) > 3600:
            session.clear()
            flash("Sesi Anda telah berakhir. Silakan login kembali.")
            return redirect(url_for('login'))

        # reset waktu kalau user masih aktif
        session['login_time'] = datetime.utcnow().timestamp()

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Silakan login terlebih dahulu.")
        return redirect(url_for('login'))

    return render_template(
        'dashboard.html',
        user_name=session['user_name'],
        active_page='dashboard'  
    )

@app.route("/data-konsumsi-aktual")
def data_konsumsi_aktual():
    page = request.args.get('page', 1, type=int)
    per_page = 28
    start_index = (page - 1) * per_page

    # ambil data filter dari query string
    tahun = request.args.get('tahun')
    bulan = request.args.get('bulan')
    rute = request.args.get('rute')
    kode = request.args.get('kode')
    kategori_golongan = request.args.get('kategori_golongan')
    jenis_bangunan = request.args.get('jenis_bangunan')

    # buat query dasar
    query = KonsumsiAktual.query

    if tahun:
        query = query.filter_by(tahun=tahun)
    if bulan:
        query = query.filter_by(bulan=bulan)
    if rute:
        query = query.filter_by(rute=rute)
    if kode:
        query = query.filter_by(kode=kode)
    if kategori_golongan:
        query = query.filter_by(kategori_golongan=kategori_golongan)
    if jenis_bangunan:
        query = query.filter_by(jenis_bangunan=jenis_bangunan)

    # Simpan filter ke dictionary untuk dikirim ke template dan pagination link
    filters = {k: v for k, v in {
        "tahun": tahun,
        "bulan": bulan,
        "rute": rute,
        "kode": kode,
        "kategori_golongan": kategori_golongan,
        "jenis_bangunan": jenis_bangunan
   }.items() if v}

    #Pagination
    query = query.order_by(KonsumsiAktual.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    data_page = pagination.items

    if not data_page:
        flash("Data tidak ditemukan")
    
    # --- Data untuk grafik (hanya sesuai data yang tampil di tabel halaman ini) ---
    chart_labels = [f"{row.bulan} {row.tahun}" for row in data_page]
    chart_data = [row.konsumsi for row in data_page]

    daftar_tahun = db.session.query(KonsumsiAktual.tahun).distinct().order_by(KonsumsiAktual.tahun.desc()).all()
    daftar_tahun = [str(t[0]) for t in daftar_tahun]
    daftar_bulan = ['JANUARI', 'FEBRUARI', 'MARET', 'APRIL', 'MEI', 'JUNI',
                    'JULI', 'AGUSTUS', 'SEPTEMBER', 'OKTOBER', 'NOVEMBER', 'DESEMBER']
    daftar_rute = ['RUTE: A101', 'RUTE: A102', 'RUTE: A103', 'RUTE: A104', 
                   'RUTE: A105', 'RUTE: A106', 'RUTE: A107', 'RUTE: A108', 
                   'RUTE: A109', 'RUTE: A110', 'RUTE: A111', 'RUTE: A112', 
                   'RUTE: A113', 'RUTE: A114', 'RUTE: A115', 'RUTE: A116', 
                   'RUTE: A117', 'RUTE: A118', 'RUTE: A119', 'RUTE: A120', 
                   'RUTE: A121', 'RUTE: A122', 'RUTE: A123', 'RUTE: A124', 
                   'RUTE: A125', 'RUTE: A126', 'RUTE: A127', 'RUTE: A128', 
                   'RUTE: A129', 'RUTE: A130', 'RUTE: A131', 'RUTE: A132', 
                   'RUTE: A133', 'RUTE: A134', 'RUTE: A135', 'RUTE: A136', 
                   'RUTE: A137', 'RUTE: A138', 'RUTE: A139', 'RUTE: A140', 
                   'RUTE: A141', 'RUTE: A142', 'RUTE: A143', 'RUTE: A144', 
                   'RUTE: A145', 'RUTE: A146', 'RUTE: A147', 'RUTE: A148', 
                   'RUTE: A149', 'RUTE: A150', 'RUTE: A151', 'RUTE: A152', 
                   'RUTE: A153', 'RUTE: A154', 'RUTE: A155', 'RUTE: HKM', 
                   'RUTE: RSUD', 'RUTE: RTN']
    daftar_kode = ['11', '12', '13', '36', '14', '22', '21', '24', '25', '26', 
                   '15', '23', '44', '32', '46', '31', '33', '48']
    daftar_kategori_golongan = ['Gol. I', 'Gol. II', 'Gol. III']
    daftar_jenis_bangunan = ['KAMAR MANDI UMUM', 'HIDRAN UMUM', 'RUMAH IBADAH', 'FIRE HYDRANT', 
                             'PANTI ASUHAN', 'YAYASAN SOSIAL', 'RUMAH TANGGA A',
                             'RUMAH TANGGA B', 'RUMAH TANGGA C', 'RUMAH TANGGA D',
                             'SEKOLAH NEGERI', 'RUMAH SAKIT PEMERINTAH', 'KLINIK PEMERINTAH', 
                             'INSTANSI PEMERINTAH', 'TNI / POLRI', 'NIAGA KECIL', 
                             'NIAGA MENENGAH', 'NIAGA BESAR']
    return render_template(
        "data_konsumsi_aktual.html",
        data=data_page,
        page=page,
        filters=filters,
        daftar_tahun=daftar_tahun,
        daftar_bulan=daftar_bulan,
        daftar_rute=daftar_rute, 
        daftar_kode=daftar_kode,
        daftar_kategori_golongan=daftar_kategori_golongan, 
        daftar_jenis_bangunan=daftar_jenis_bangunan,
        total_pages=pagination.pages,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_num=pagination.next_num,
        prev_num=pagination.prev_num,
        active_page="data_konsumsi_aktual",
        start_index=start_index,
        tahun=tahun,
        bulan=bulan,
        rute=rute,
        kode=kode,
        kategori_golongan=kategori_golongan,
        jenis_bangunan=jenis_bangunan,
        chart_labels=json.dumps(chart_labels, ensure_ascii=False),
        chart_data=json.dumps(chart_data, ensure_ascii=False)
    )


@app.route("/data-konsumsi-aktual/download")
def download_konsumsi_aktual():
    # ambil filter dari query string
    tahun = request.args.get('tahun')
    bulan = request.args.get('bulan')
    rute = request.args.get('rute')
    kode = request.args.get('kode')
    kategori_golongan = request.args.get('kategori_golongan')
    jenis_bangunan = request.args.get('jenis_bangunan')

    # query dasar
    query = KonsumsiAktual.query

    if tahun: query = query.filter(KonsumsiAktual.tahun == tahun)
    if bulan: query = query.filter(KonsumsiAktual.bulan == bulan)
    if rute: query = query.filter(KonsumsiAktual.rute == rute)
    if kode: query = query.filter(KonsumsiAktual.kode == kode)
    if kategori_golongan: query = query.filter(KonsumsiAktual.kategori_golongan == kategori_golongan)
    if jenis_bangunan: query = query.filter(KonsumsiAktual.jenis_bangunan == jenis_bangunan)

    data_all = query.order_by(KonsumsiAktual.id.desc()).all()

    # ubah ke list of lists untuk export
    bodyData = [
        [i+1, row.tahun, row.bulan, row.rute, row.kode,
         row.jenis_bangunan, row.jumlah_sr, row.kategori_golongan, row.konsumsi]
        for i, row in enumerate(data_all)
    ]

    return jsonify(bodyData)


@app.route('/forecasting-konsumsi', methods=['GET', 'POST'])
def forecasting_konsumsi():
    # Ambil parameter filter dari query string
    tahun = request.args.get('tahun')
    bulan = request.args.get('bulan')
    rute = request.args.get('rute')
    kode = request.args.get('kode')
    kategori_golongan = request.args.get('kategori_golongan')
    jenis_bangunan = request.args.get('jenis_bangunan')
    mode = request.args.get('mode')  

    # Ambil data dari database
    data = KonsumsiAktual.query.all()
    df_konsumsi = pd.DataFrame([{
        'TAHUN': d.tahun,
        'BULAN': d.bulan,
        'KONSUMSI': d.konsumsi,
        'RUTE': d.rute,
        'KODE': d.kode,
        'KATEGORI_GOLONGAN': d.kategori_golongan,
        'JENIS_BANGUNAN': d.jenis_bangunan
    } for d in data])

    # Konversi bulan string ke nomor bulan
    bulan_map = {
        "JANUARI":1, "FEBRUARI":2, "MARET":3, "APRIL":4, "MEI":5, "JUNI":6,
        "JULI":7, "AGUSTUS":8, "SEPTEMBER":9, "OKTOBER":10, "NOVEMBER":11, "DESEMBER":12
    }

    bulan_num = None
    if bulan:
        bulan = bulan.upper()
        bulan_num = bulan_map.get(bulan)

    df_konsumsi['BULAN_NUM'] = df_konsumsi['BULAN'].apply(lambda x: bulan_map.get(x.upper(), 0))
    df_konsumsi['TANGGAL'] = pd.to_datetime(
        df_konsumsi['BULAN_NUM'].astype(str) + '-' + df_konsumsi['TAHUN'].astype(str),
        format='%m-%Y'
    )
    df_konsumsi.drop(columns=['BULAN_NUM'], inplace=True)

    # ===============================
    # FILTER DASAR (UNTUK TRAINING)
    # ===============================
    df_train = df_konsumsi.copy()

    if rute:
        df_train = df_train[df_train["RUTE"] == rute]
    if kode:
        df_train = df_train[df_train["KODE"] == kode]
    if kategori_golongan:
        df_train = df_train[df_train["KATEGORI_GOLONGAN"] == kategori_golongan]
    if jenis_bangunan:
        df_train = df_train[df_train["JENIS_BANGUNAN"] == jenis_bangunan]

    cache_key = f"{rute}|{kode}|{kategori_golongan}|{jenis_bangunan}"

    # ===============================
    # DATA AKTUAL (2022–2024)
    # ===============================
    df_aktual_36 = None

    if mode in ["aktual", "forecast"] and not df_train.empty:
        df_aktual = df_train.copy()

        df_aktual["TANGGAL"] = pd.to_datetime(df_aktual["TANGGAL"])
        df_aktual = df_aktual.sort_values("TANGGAL")
        df_aktual.set_index("TANGGAL", inplace=True)

        df_train_forecast = df_train.copy()

        df_train_forecast["TANGGAL"] = pd.to_datetime(df_train_forecast["TANGGAL"])
        df_train_forecast = df_train_forecast.sort_values("TANGGAL")
        df_train_forecast.set_index("TANGGAL", inplace=True)

        # agregasi bulanan
        df_aktual_bulanan = (
            df_aktual
            .groupby(pd.Grouper(freq="MS"))["KONSUMSI"]
            .sum()
            .reset_index()
        )

        df_train_forecast = (
            df_train_forecast
            .groupby(pd.Grouper(freq="MS"))["KONSUMSI"]
            .sum()
            .reset_index()
        )

        # ambil 36 bulan (2022–2024)
        df_aktual_36 = df_aktual_bulanan[
            (df_aktual_bulanan["TANGGAL"] >= "2022-01-01") &
            (df_aktual_bulanan["TANGGAL"] <= "2024-12-01")
        ]

        # filter BULAN hanya untuk tampilan aktual
        if bulan_num:
            df_aktual_36 = df_aktual_36[
                df_aktual_36["TANGGAL"].dt.month == bulan_num
            ]

        if mode == "aktual" and not df_aktual_36.empty:
            flash("Data konsumsi aktual berhasil ditampilkan", "info")

    # ===============================
    # FORECAST
    # ===============================
    hasil_forecast_filter = None
    hasil_evaluasi_filter = None

    if mode == "forecast":
        try:
            if df_train_forecast is None or df_train_forecast.empty:
                flash("Data tidak mencukupi untuk proses forecasting", "warning")

            else:
                # === ambil dari cache atau hitung ulang ===
                if cache_key in forecast_cache:
                    hasil_forecast_full = forecast_cache[cache_key]
                    logger.info("Forecast diambil dari cache")
                else:
                    hasil_forecast_full, hasil_evaluasi_filter = forecast_konsumsi(
                        df_train_forecast   # ✅ FULL DATA
                    )
                    forecast_cache[cache_key] = hasil_forecast_full

                # === FILTER TAMPILAN ===
                hasil_forecast_filter = hasil_forecast_full.copy()

                if tahun:
                    hasil_forecast_filter = hasil_forecast_filter[
                        hasil_forecast_filter["TANGGAL"].dt.year == int(tahun)
                    ]

                if bulan_num:
                    hasil_forecast_filter = hasil_forecast_filter[
                        hasil_forecast_filter["TANGGAL"].dt.month == bulan_num
                    ]

                if hasil_forecast_filter.empty:
                    flash("Data forecasting tidak tersedia untuk filter yang dipilih", "warning")
                else:
                    flash(
                        "Proses forecasting berhasil dilakukan dan hasil forecasting konsumsi berhasil ditampilkan",
                        "success"
                    )

        except Exception as e:
            logger.exception(e)
            flash("Terjadi kesalahan saat proses forecasting", "danger")

    # Pastikan kolom TANGGAL forecast jadi datetime
    if hasil_forecast_filter is not None and not hasil_forecast_filter.empty:
        hasil_forecast_filter['TANGGAL'] = pd.to_datetime(hasil_forecast_filter['TANGGAL'])

    # Ambil hanya tanggal setelah data aktual terakhir
    if df_aktual_36 is not None and not df_aktual_36.empty:
        last_actual_date = df_aktual_36["TANGGAL"].max()
    if hasil_forecast_filter is not None:
        hasil_forecast_filter = hasil_forecast_filter[hasil_forecast_filter['TANGGAL'] > last_actual_date]

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 25

    # --- Pagination untuk filter ---
    forecast_df_filter = []              # PENTING
    forecast_df_filter_chart = None
    total_pages_filter = 0
    if hasil_forecast_filter is not None and not hasil_forecast_filter.empty:
        total_pages_filter = (len(hasil_forecast_filter) + per_page - 1) // per_page
        start, end = (page - 1) * per_page, (page * per_page)
        paginated_filter = hasil_forecast_filter.iloc[start:end]
        forecast_df_filter_chart = paginated_filter.copy()
        forecast_df_filter = paginated_filter.iterrows()

    # --- Pagination untuk default A101 ---
    forecast_df = forecast_df_chart = None
    total_pages_default = 0

    tanggal_aktual = []
    konsumsi_aktual = []

    if df_aktual_36 is not None and not df_aktual_36.empty:
        tanggal_aktual = df_aktual_36["TANGGAL"].dt.strftime("%Y-%m").tolist()
        konsumsi_aktual = df_aktual_36["KONSUMSI"].tolist()
        
    tanggal_forecast = []
    konsumsi_forecast = []

    if forecast_df_filter_chart is not None and not forecast_df_filter_chart.empty:
        tanggal_forecast = forecast_df_filter_chart["TANGGAL"].dt.strftime("%Y-%m").tolist()
        konsumsi_forecast = forecast_df_filter_chart["PREDIKSI_KONSUMSI"].tolist()

    # Data JSON untuk Chart.js
    if forecast_df_filter_chart is not None and not forecast_df_filter_chart.empty:
        forecast_df_filter_chart['TANGGAL'] = forecast_df_filter_chart['TANGGAL'].dt.strftime("%Y-%m")
        forecast_data_json = json.dumps({
            "tanggal_aktual": tanggal_aktual,
            "konsumsi_aktual": konsumsi_aktual,
            "tanggal_forecast": tanggal_forecast,
            "konsumsi_forecast": konsumsi_forecast
        }, default=str)

    else:
        forecast_data_json = json.dumps({}, default=str)

    # --- Dataset untuk download (tanpa pagination) ---
    if hasil_forecast_filter is not None and not hasil_forecast_filter.empty:
        download_data = [
            {"label": row["TANGGAL"].strftime("%Y-%m"), "value": row["PREDIKSI_KONSUMSI"]}
            for _, row in hasil_forecast_filter.iterrows()
        ]

    else:
        download_data = []

    forecast_download_json = json.dumps(download_data, default=str)

    # --- Dataset untuk download chart (seluruh data, tanpa pagination) ---
    if hasil_forecast_filter is not None and not hasil_forecast_filter.empty:
        download_chart_data = [
            {"label": row["TANGGAL"].strftime("%Y-%m"), "value": row["PREDIKSI_KONSUMSI"]}
            for _, row in hasil_forecast_filter.iterrows()
        ]
        
    else:
        download_chart_data = []

    # Kirim ke template
    forecast_download_json = json.dumps(download_chart_data, default=str)

    # Simpan forecast ke DB (jika ada)
    for df_save, r_val, k_val, kg_val, jb_val in [
        (hasil_forecast_filter, rute, kode, kategori_golongan, jenis_bangunan),

    ]:
        if df_save is not None and not df_save.empty:
            try:
                simpan_forecast_ke_db(
                    forecast_df=df_save,
                    rute_value=r_val,
                    kode_value=k_val,
                    kategori_value=kg_val,
                    jenis_value=jb_val
                )
            except Exception as e:
                db.session.rollback()
                logger.exception(f"Gagal menyimpan forecast: {e}")

    # Dropdown filters
    daftar_tahun = list(range(2025, 2031))
    bulan_order = [
        "JANUARI","FEBRUARI","MARET","APRIL","MEI","JUNI",
        "JULI","AGUSTUS","SEPTEMBER","OKTOBER","NOVEMBER","DESEMBER"
    ]
    daftar_bulan = sorted(df_konsumsi['BULAN'].unique().tolist(), key=lambda x: bulan_order.index(x))
    # Bersihkan spasi di depan & belakang, dan samakan huruf kapital
    daftar_rute = df_konsumsi['RUTE'].dropna().apply(lambda x: x.strip().upper()).unique().tolist()
    daftar_rute = sorted(daftar_rute)
    daftar_kode = sorted(df_konsumsi['KODE'].dropna().unique().tolist())
    daftar_kategori_golongan = sorted(df_konsumsi['KATEGORI_GOLONGAN'].dropna().unique().tolist())
    daftar_jenis_bangunan = sorted(df_konsumsi['JENIS_BANGUNAN'].dropna().unique().tolist())

    # Filters aktif
    filters = {k:v for k,v in {
        "tahun": tahun,
        "bulan": bulan,
        "rute": rute,
        "kode": kode,
        "kategori_golongan": kategori_golongan,
        "jenis_bangunan": jenis_bangunan
    }.items() if v}

    print("Forecast data JSON:", forecast_data_json)

    # --- Cek 5 entry terakhir di DB ---
    if request.method == "POST" and mode == "forecast":
        latest_entries = Forecast.query.order_by(Forecast.id.desc()).limit(5).all()
        for f in latest_entries:
            logger.info(
                f"[DB CHECK] id:{f.id}, jenis:{f.jenis_bangunan}, "
                f"tahun:{f.tahun}, bulan:{f.bulan}, prediksi:{f.prediksi}"
            )

    args = request.args.to_dict()
    args.pop("page", None)

    return render_template(
        'forecasting_konsumsi.html',
        active_page="forecasting_konsumsi",
        forecast_df=forecast_df,
        forecast_df_filter=forecast_df_filter,
        evaluasi_filter=hasil_evaluasi_filter,
        forecast_data_json=forecast_data_json,
        forecast_download_json=forecast_download_json,
        page=page,
        mode=mode,
        data_aktual=df_aktual_36,
        total_pages_filter=total_pages_filter,
        total_pages_default=total_pages_default,
        per_page=per_page,
        daftar_tahun=daftar_tahun,
        daftar_bulan=daftar_bulan,
        daftar_rute=daftar_rute,
        daftar_kode=daftar_kode,
        daftar_kategori_golongan=daftar_kategori_golongan,
        daftar_jenis_bangunan=daftar_jenis_bangunan,
        filters=filters,
        args=args
        
)


# ===== ROUTE UPLOAD DATA =====
@app.route('/unggah-data-konsumsi', methods=['GET', 'POST'])
def unggah_data_konsumsi():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("Tidak ada file dipilih!", "danger")
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash("Nama file kosong!", "danger")
            return redirect(request.url)

        if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_DATA):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER_DATA'], filename)
            file.save(filepath)
            # lanjut proses CSV...

            try:
                # Baca CSV
                df = pd.read_csv(filepath, sep=";")  # pakai ; sebagai pemisah

                # Ganti NaN jadi string kosong
                df = df.fillna("")

                # Validasi kolom wajib
                required_cols = ['Tahun', 'Bulan', 'Rute', 'Kode',
                                 'Kategori Golongan', 'Jenis Bangunan',
                                 'Jumlah SR', 'Konsumsi (M3)']
                for col in required_cols:
                    if col not in df.columns:
                        flash(f"Kolom {col} tidak ditemukan!", "danger")
                        return redirect(request.url)

                # Simpan ke session agar bisa dipakai saat konfirmasi
                session['preview_data'] = df.to_dict(orient="records")
                session['uploaded_file'] = filename
                session['upload_time'] = datetime.utcnow()

                # Preview (10 baris pertama)
                preview = df.head(10).to_html(classes='table table-striped', index=False, border=0, na_rep="")   # ⬅️ tambahin ini biar border bawaan hilang

                return render_template("upload_preview.html",
                                       active_page="unggah_data_konsumsi",
                                       tables=[preview],
                                       filename=filename)

            except Exception as e:
                flash(f"Error membaca file: {e}", "danger")
                return redirect(request.url)

        else:
            flash('Format file tidak didukung. Hanya CSV.', 'danger')
            return redirect(request.url)

    return render_template("upload_data.html",
                           active_page="unggah_data_konsumsi")


# ===== ROUTE KONFIRMASI =====
@app.route('/confirm-upload', methods=['POST'])
def confirm_upload():
    data = session.get('preview_data')
    filename = session.get('uploaded_file')  # ambil nama file dari session

    if not data or not filename:
        flash("Tidak ada data untuk disimpan!", "danger")
        return redirect(url_for("unggah_data_konsumsi"))

    try:
        from datetime import datetime, timedelta

        # --- Hapus data terbaru (misal 60 menit terakhir) ---
        def hapus_data_terbaru():
            waktu_akhir = datetime.utcnow()
            waktu_awal = waktu_akhir - timedelta(minutes=60)

            data_baru = KonsumsiAktual.query.filter(KonsumsiAktual.created_at >= waktu_awal).all()

            if not data_baru:
                print("Tidak ada data terbaru untuk dihapus")
                return

            for row in data_baru:
                db.session.delete(row)
            db.session.commit()
            print("Semua data terbaru berhasil dihapus.")

        # Panggil hapus data terbaru sebelum simpan data baru
        hapus_data_terbaru()

        # --- Simpan data baru ---
        for row in data:
            new_data = KonsumsiAktual(
                tahun=int(row['Tahun']) if str(row['Tahun']).strip() != "" else None,
                bulan=row['Bulan'] if row['Bulan'] != "" else None,
                rute=row['Rute'] if row['Rute'] != "" else None,
                kode=row['Kode'] if row['Kode'] != "" else 0,
                kategori_golongan=row['Kategori Golongan'] if row['Kategori Golongan'] != "" else None,
                jenis_bangunan=row['Jenis Bangunan'] if row['Jenis Bangunan'] != "" else None,
                jumlah_sr=int(row['Jumlah SR']) if str(row['Jumlah SR']).strip() != "" else 0,
                konsumsi=float(row['Konsumsi (M3)']) if str(row['Konsumsi (M3)']).strip() != "" else 0,
                is_simulasi=True,  
                created_at=datetime.utcnow()  # pastikan timestamp baru
            )
            db.session.add(new_data)

        db.session.commit()

        # setelah commit data
        logging.info("Upload file selesai. Semua data berhasil disimpan pada %s", datetime.now())

        session.pop('preview_data', None)
        session.pop('uploaded_file', None)
        flash("Data berhasil disimpan ke database!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Gagal menyimpan ke database: {e}", "danger")

    return redirect(url_for('data_konsumsi_aktual'))


# ===== ROUTE PROFIL =====
@app.route('/profil-saya', methods=['GET', 'POST'])
def profil_saya():
    # Ambil data user dari session
    user_id = session.get('user_id')
    if not user_id:
        flash("Silakan login terlebih dahulu.", "error")
        return redirect(url_for("login"))

    user = db.session.get(User, user_id)
    if not user:
        flash("Data user tidak ditemukan.", "error")
        return redirect(url_for("login"))

    if request.method == 'POST':
        # Update data user dari form
        user.full_name = request.form.get('full_name') or user.full_name
        user.employee_id = request.form.get('employee_id') or user.employee_id
        user.email = request.form.get('email') or user.email
        user.phone_number = request.form.get('phone_number') or user.phone_number
        user.address = request.form.get('address') or ''
        user.nik = request.form.get('nik') or ''
        user.birth_date = datetime.strptime(request.form['birth_date'], '%Y-%m-%d').date() if request.form.get('birth_date') else None
        user.gender = request.form.get('gender') or user.gender
        user.education = request.form.get('education') or ''
        user.family_contact = request.form.get('family_contact') or ''
        user.social_media = request.form.get('soacial_media') or ''
        user.position = request.form.get('position') or ''


        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if password:
            if password != confirm_password:
                flash("Password dan konfirmasi tidak sama", "error")
                return redirect(url_for('profil_saya'))
            user.set_password(password)

        db.session.commit()
        flash("Perubahan profil berhasil disimpan.", "success")
        return redirect(url_for('profil_saya'))

    return render_template('profile.html',
                           active_page="profil_saya",
                           user=user
                        )


# ===== ROUTE UPLOAD FOTO PROFIL =====
@app.route('/upload-profile-picture', methods=['POST'])
def upload_profile_picture():
    user_id = session.get('user_id')
    if not user_id:
        flash("Silakan login terlebih dahulu.", "error")
        return redirect(url_for("login"))

    user = db.session.get(User, user_id)
    if not user:
        flash("Data user tidak ditemukan.", "error")
        return redirect(url_for("login"))

    if 'profile_picture' not in request.files:
        flash("Tidak ada file yang diupload", "danger")
        return redirect(url_for('profil_saya'))

    file = request.files['profile_picture']
    if file.filename == '':
        flash("Nama file kosong!", "danger")
        return redirect(url_for('profil_saya'))

    if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_PROFILE):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER_PROFILE'], filename)
        file.save(filepath)

        # update user di database
        user.profile_picture = filename
        db.session.commit()

        # update session juga di sini
        session['user_profile_picture'] = f"uploads/profile_pictures/{filename}"
        session['user_name'] = user.full_name

        flash("Foto profil berhasil diupdate!", "success")
    else:
        flash("Format file tidak didukung!", "danger")

    return redirect(url_for('profil_saya'))


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    if request.method == 'POST':
        session.clear()
        flash("Anda berhasil logout. Sampai jumpa lagi!", "success")
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    user = db.session.get(User, user_id) if user_id else None

    return render_template('logout.html', active_page="logout", user=user)


if __name__ == "__main__":
    app.run(debug=True)