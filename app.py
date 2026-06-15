import os
import random
import urllib.parse
from flask import Flask
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_mail import Mail
from config import Config
from models import db, User

_GREETINGS = [
    "Great to see you",
    "Welcome back",
    "Good to have you here",
    "Hope your day is going well",
    "Ready to make a difference today",
    "You're making education better",
    "Keep up the great work",
    "Another great day ahead",
    "Glad you're here",
    "Let's get things done",
]

login_manager = LoginManager()
migrate = Migrate()
mail = Mail()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        # FIXED: Using db.session.get() instead of User.query.get()
        return db.session.get(User, int(user_id))

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.teacher import teacher_bp
    from routes.student import student_bp
    from routes.parent import parent_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(parent_bp, url_prefix='/parent')

    app.jinja_env.globals['enumerate'] = enumerate

    # ── snap_marks filter: round to nearest 0.5, show as int if whole ──────
    def _snap_marks(v):
        """49.1 → '49'   65.5 → '65.5'   0.0 → '0'"""
        try:
            s = round(round(float(v or 0) * 2) / 2, 1)
            return str(int(s)) if s == int(s) else str(s)
        except (ValueError, TypeError):
            return '0'
    app.jinja_env.filters['snap_marks'] = _snap_marks

    @app.context_processor
    def inject_global_context():
        """Inject sidebar profile image, random greeting, and parent WhatsApp link."""
        if not current_user.is_authenticated:
            return dict(sidebar_photo=None, greeting=random.choice(_GREETINGS), parent_wa_text=None)

        # --- Sidebar profile photo ---
        sidebar_photo = None
        try:
            role = current_user.role
            if role == 'teacher':
                from models import Teacher
                t = Teacher.query.filter_by(user_id=current_user.id).first()
                if t and t.profile_image and t.profile_image != 'default_teacher.png':
                    sidebar_photo = t.profile_image
            elif role == 'student':
                from models import Student
                s = Student.query.filter_by(user_id=current_user.id).first()
                if s and s.profile_image and s.profile_image != 'default.png':
                    sidebar_photo = s.profile_image
            elif role == 'parent':
                from models import Parent
                p = Parent.query.filter_by(user_id=current_user.id).first()
                if p:
                    # Parents use their linked student's photo as avatar fallback
                    from models import Student
                    if p.student_id:
                        s = db.session.get(Student, p.student_id)
                        if s and s.profile_image and s.profile_image != 'default.png':
                            sidebar_photo = s.profile_image
        except Exception:
            pass

        # --- Random greeting (seeded by user+date so it changes each day) ---
        import datetime
        seed = current_user.id * 1000 + datetime.date.today().toordinal()
        greeting = _GREETINGS[seed % len(_GREETINGS)]

        # --- Parent WhatsApp text ---
        wa_text = None
        if current_user.role == 'parent':
            try:
                from models import Parent, Student, Class
                parent = Parent.query.filter_by(user_id=current_user.id).first()
                student_name = roll_no = class_info = None
                if parent and parent.student_id:
                    student = db.session.get(Student, parent.student_id)
                    if student:
                        su = db.session.get(User, student.user_id)
                        student_name = su.full_name if su else None
                        roll_no = student.roll_no
                        cls = db.session.get(Class, student.class_id) if student.class_id else None
                        class_info = f"{cls.name}-{cls.section}" if cls else None
                if student_name:
                    msg = (f"Hello, I am {current_user.full_name}, parent of {student_name}"
                           f" (Roll No: {roll_no}" + (f", Class: {class_info}" if class_info else "") + ")"
                           f" at Martyrs Memorial +2. I need help.")
                else:
                    msg = f"Hello, I am {current_user.full_name}, a parent at Martyrs Memorial +2. I need help."
                wa_text = urllib.parse.quote(msg)
            except Exception:
                pass

        return dict(sidebar_photo=sidebar_photo, greeting=greeting, parent_wa_text=wa_text)

    with app.app_context():
        db.create_all()
        # Ensure notes upload directory exists
        import os as _os
        _os.makedirs(_os.path.join(app.root_path, 'static', 'uploads', 'notes'), exist_ok=True)

        # Safe migrations — add columns that may not exist yet (MySQL-compatible)
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            existing_cols = [c['name'] for c in inspector.get_columns('attendance')]
            with db.engine.connect() as con:
                if 'leave_reason' not in existing_cols:
                    con.execute(text("ALTER TABLE attendance ADD COLUMN leave_reason VARCHAR(500)"))
                    con.commit()
                    app.logger.info("Migration: added leave_reason to attendance")
                if 'notif_sent' not in existing_cols:
                    con.execute(text("ALTER TABLE attendance ADD COLUMN notif_sent TINYINT(1) DEFAULT 0"))
                    con.commit()
                    app.logger.info("Migration: added notif_sent to attendance")
        except Exception as _e:
            app.logger.warning(f"Migration warning: {_e}")

    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    application = create_app()
    application.run(host='0.0.0.0', port=port, debug=True)
