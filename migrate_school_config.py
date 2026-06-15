"""
Run once to add/update the school_config table:
    python migrate_school_config.py
"""
import os
from app import create_app
from models import db, SchoolConfig

app = create_app()
with app.app_context():
    # Use ALTER TABLE for any new columns that may not exist yet
    with db.engine.connect() as conn:
        existing = [row[0] for row in conn.execute(
            db.text("SHOW COLUMNS FROM school_config")
        )]
        new_cols = {
            'logo_filename':     "VARCHAR(200) DEFAULT NULL",
            'sig1_image':        "VARCHAR(200) DEFAULT NULL",
            'sig2_image':        "VARCHAR(200) DEFAULT NULL",
            'sig3_image':        "VARCHAR(200) DEFAULT NULL",
        }
        for col, defn in new_cols.items():
            if col not in existing:
                conn.execute(db.text(f"ALTER TABLE school_config ADD COLUMN {col} {defn}"))
                print(f"  Added column: {col}")
        conn.commit()

    # Seed default row if empty
    if not SchoolConfig.query.first():
        db.session.add(SchoolConfig())
        db.session.commit()
        print("Default school config created.")
    else:
        print("school_config table already up-to-date.")

    # Create upload directories
    base = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    for sub in ('logos', 'signatures'):
        path = os.path.join(base, sub)
        os.makedirs(path, exist_ok=True)
        print(f"  Directory ready: {path}")

print("Migration complete.")

# Add HOD columns to streams table if missing
with app.app_context():
    with db.engine.connect() as conn:
        existing = [row[0] for row in conn.execute(db.text("SHOW COLUMNS FROM streams"))]
        for col, defn in [('hod_name', 'VARCHAR(120) DEFAULT NULL'),
                           ('hod_signature', 'VARCHAR(200) DEFAULT NULL')]:
            if col not in existing:
                conn.execute(db.text(f"ALTER TABLE streams ADD COLUMN {col} {defn}"))
                print(f"  Added to streams: {col}")
        conn.commit()
    print("Stream HOD columns ready.")
