import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'martyrs-memorial-erp-secret-2024')

    # ── Database ──────────────────────────────────────────────────────────────
    # quote_plus encodes special chars in password (e.g. @ -> %40)
    _db_url = os.environ.get('DATABASE_URL', '')
    if _db_url and _db_url.startswith('mysql'):
        SQLALCHEMY_DATABASE_URI = _db_url
    elif os.environ.get('DB_HOST'):
        _user = os.environ.get('DB_USER', 'root')
        _pwd  = quote_plus(os.environ.get('DB_PASSWORD', ''))
        _host = os.environ.get('DB_HOST', 'localhost')
        _port = os.environ.get('DB_PORT', '3306')
        _name = os.environ.get('DB_NAME', 'school_erp')
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{_user}:{_pwd}@{_host}:{_port}/{_name}"
        )
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///school_erp.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # ── File Upload Configurations ───────────────────────────────────────────
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    TEACHER_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'teachers')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # Allowed extensions
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}

    # ── Mail ──────────────────────────────────────────────────────────────────
    MAIL_SERVER   = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS  = os.environ.get('MAIL_USE_TLS',  'true').lower() == 'true'
    MAIL_USE_SSL  = os.environ.get('MAIL_USE_SSL',  'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get(
        'MAIL_DEFAULT_SENDER',
        os.environ.get('MAIL_USERNAME', 'noreply@martyrsmemorial.edu.np')
    )

    # ── WhatsApp (Twilio) ─────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID    = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN     = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_WHATSAPP_FROM  = os.environ.get('TWILIO_WHATSAPP_FROM', '+14155238886')  # sandbox default
    SCHOOL_URL            = os.environ.get('SCHOOL_URL', '')

    # ── School info ───────────────────────────────────────────────────────────
    ACADEMIC_YEAR   = '2024-2025'
    SCHOOL_NAME     = "Martyrs' Memorial College"
    SCHOOL_TAGLINE  = "Excellence in Education Since 1975"
    SCHOOL_ADDRESS  = "Biratnagar, Morang, Nepal"
    SCHOOL_PHONE    = "+977-021-123456"
    SCHOOL_EMAIL    = "info@martyrsmemorial.edu.np"