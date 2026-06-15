"""
Run once to migrate the database schema:
    python migrate_school_config.py
"""
import os
from app import create_app
from models import db, SchoolConfig

app = create_app()

with app.app_context():

    # ── 1. school_config — add ALL new columns first, before any ORM query ──
    with db.engine.connect() as conn:
        existing = [row[0] for row in conn.execute(db.text("SHOW COLUMNS FROM school_config"))]

        school_config_cols = {
            # signature / logo columns
            'logo_filename':             "VARCHAR(200) DEFAULT NULL",
            'sig1_image':                "VARCHAR(200) DEFAULT NULL",
            'sig2_image':                "VARCHAR(200) DEFAULT NULL",
            'sig3_image':                "VARCHAR(200) DEFAULT NULL",
            # document customisation columns
            'doc_id_color':              "VARCHAR(20) DEFAULT '#1565c0'",
            'doc_principal_name':        "VARCHAR(150) DEFAULT ''",
            'doc_principal_title':       "VARCHAR(100) DEFAULT 'Principal'",
            'doc_exam_controller':       "VARCHAR(150) DEFAULT ''",
            'doc_exam_controller_title': "VARCHAR(100) DEFAULT 'Controller of Examinations'",
            'doc_bonafide_text':         "TEXT",
            'doc_character_text':        "TEXT",
            'doc_admit_instructions':    "TEXT",
        }
        for col, defn in school_config_cols.items():
            if col not in existing:
                conn.execute(db.text(f"ALTER TABLE school_config ADD COLUMN {col} {defn}"))
                print(f"  Added to school_config: {col}")
        conn.commit()
    print("school_config columns ready.")

    # ── 2. Seed default row if table is empty ───────────────────────────────
    if not SchoolConfig.query.first():
        db.session.add(SchoolConfig())
        db.session.commit()
        print("Default school config row created.")
    else:
        print("school_config row already exists.")

    # ── 3. Upload directories ───────────────────────────────────────────────
    base = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    for sub in ('logos', 'signatures'):
        path = os.path.join(base, sub)
        os.makedirs(path, exist_ok=True)
        print(f"  Directory ready: {path}")

    # ── 4. streams — HOD columns ────────────────────────────────────────────
    with db.engine.connect() as conn:
        existing = [row[0] for row in conn.execute(db.text("SHOW COLUMNS FROM streams"))]
        for col, defn in [('hod_name', 'VARCHAR(120) DEFAULT NULL'),
                           ('hod_signature', 'VARCHAR(200) DEFAULT NULL')]:
            if col not in existing:
                conn.execute(db.text(f"ALTER TABLE streams ADD COLUMN {col} {defn}"))
                print(f"  Added to streams: {col}")
        conn.commit()
    print("streams columns ready.")

    # ── 5. students — guardian_email ────────────────────────────────────────
    with db.engine.connect() as conn:
        existing = [row[0] for row in conn.execute(db.text("SHOW COLUMNS FROM students"))]
        if 'guardian_email' not in existing:
            conn.execute(db.text("ALTER TABLE students ADD COLUMN guardian_email VARCHAR(120) DEFAULT NULL"))
            print("  Added to students: guardian_email")
        conn.commit()
    print("students columns ready.")

print("\nMigration complete.")
