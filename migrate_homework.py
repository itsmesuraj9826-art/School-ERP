"""
Run this once to create the homework_diary table:
    python migrate_homework.py
"""
from app import create_app
from models import db

app = create_app()
with app.app_context():
    db.create_all()
    print("homework_diary table created (or already exists).")
