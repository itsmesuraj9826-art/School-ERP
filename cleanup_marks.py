"""
One-time script: round all existing Result marks to nearest 0.5
Run once from the project root:  python cleanup_marks.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, Result

def snap(v):
    try:
        return round(round(float(v or 0) * 2) / 2, 1)
    except (ValueError, TypeError):
        return 0.0

app = create_app()
with app.app_context():
    results = Result.query.all()
    fixed = 0
    for r in results:
        new_m = snap(r.marks_obtained)
        new_p = snap(r.practical_marks)
        if new_m != r.marks_obtained or new_p != r.practical_marks:
            r.marks_obtained  = new_m
            r.practical_marks = new_p
            fixed += 1
    db.session.commit()
    print(f"Done — fixed {fixed} of {len(results)} records.")
