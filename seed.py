"""
Seed script - drops and recreates the database with sample data.
Run: cd school_erp && python seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from models import db, User, Student, Teacher, Parent, Class, Stream, Subject, Attendance, Exam, Result, Fee, Notice, TimeTable
from datetime import date, time, timedelta
import random

app = create_app()

def seed_all():
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("✅ Tables created...")

        # ── Admin ──────────────────────────────────────────────
        admin = User(username='admin', email='msuraj24@tbc.edu.np',
                     full_name='Principal Administrator', role='admin', phone='9800000001')
        admin.set_password('suraj@123')
        db.session.add(admin)
        db.session.flush()

        # ── NEB Streams ────────────────────────────────────────
        stream_data = [
            ('Science', 'SCI', 'Pure and Applied Sciences — Physics, Chemistry, Biology, Mathematics'),
            ('Management', 'MGT', 'Business and Commerce — Accountancy, Economics, Business Studies'),
            ('Humanities', 'HUM', 'Social Sciences, History, Geography, Sociology, Psychology'),
            ('Education', 'EDU', 'Education and Pedagogy — Teacher Training, Child Development'),
            ('Law', 'LAW', 'Legal Studies, Constitutional Law, Human Rights'),
        ]
        streams = []
        for name, code, desc in stream_data:
            s = Stream(name=name, code=code, description=desc)
            db.session.add(s)
            streams.append(s)
        db.session.flush()

        stream_map = {s.name: s for s in streams}

        # ── Teachers ───────────────────────────────────────────
        teacher_data = [
            ('Ramesh Sharma',  'teacher1@martyrs.edu.np', 'teacher123', 'TCH001', 'Mathematics',   'MSc Mathematics',          'Science'),
            ('Sita Thapa',     'teacher2@martyrs.edu.np', 'teacher123', 'TCH002', 'English',        'MA English Literature',     'Humanities'),
            ('Binod Karki',    'teacher3@martyrs.edu.np', 'teacher123', 'TCH003', 'Physics',        'BSc Physics',               'Science'),
            ('Puja Rai',       'teacher4@martyrs.edu.np', 'teacher123', 'TCH004', 'Nepali',         'MA Nepali',                 'Humanities'),
            ('Subash Limbu',   'teacher5@martyrs.edu.np', 'teacher123', 'TCH005', 'Economics',      'MA Economics',              'Management'),
            ('Anita Gurung',   'teacher6@martyrs.edu.np', 'teacher123', 'TCH006', 'Chemistry',      'MSc Chemistry',             'Science'),
            ('Bikram Thapa',   'teacher7@martyrs.edu.np', 'teacher123', 'TCH007', 'Accountancy',    'MBS Accountancy',           'Management'),
        ]
        teachers = []
        for i, (name, email, pwd, eid, subj, qual, dept) in enumerate(teacher_data):
            u = User(username=email.split('@')[0], email=email, full_name=name, role='teacher', phone=f'98000{i+10:05d}')
            u.set_password(pwd)
            db.session.add(u)
            db.session.flush()
            t = Teacher(user_id=u.id, employee_id=eid, subject=subj, qualification=qual,
                        department=dept, salary=30000 + i*2000,
                        joining_date=date(2020, 1, (i % 12) + 1))
            db.session.add(t)
            teachers.append(t)
        db.session.flush()

        # ── Classes (Grade 11 & 12 with streams) ───────────────
        class_configs = [
            ('11', 'A', 'Science'),
            ('11', 'B', 'Management'),
            ('11', 'C', 'Humanities'),
            ('12', 'A', 'Science'),
            ('12', 'B', 'Management'),
            ('12', 'C', 'Humanities'),
            ('9',  'A', None),
            ('9',  'B', None),
            ('10', 'A', None),
            ('10', 'B', None),
        ]
        classes = []
        for name, section, stream_name in class_configs:
            stream = stream_map.get(stream_name) if stream_name else None
            cls = Class(
                name=name, section=section,
                stream_id=stream.id if stream else None,
                academic_year='2081-2082',
                capacity=40,
                room_no=f'{name}{section}-R'
            )
            db.session.add(cls)
            classes.append(cls)
        db.session.flush()

        # Assign class teachers
        for i, cls in enumerate(classes):
            cls.class_teacher_id = teachers[i % len(teachers)].id

        # ── Subjects ───────────────────────────────────────────
        subject_configs = {
            'Science': [
                ('Physics',    'PHY', 75, 'theory',    75, 0),
                ('Chemistry',  'CHE', 75, 'both',      50, 25),
                ('Mathematics','MAT', 100,'theory',    100,0),
                ('English',    'ENG', 75, 'theory',    75, 0),
                ('Nepali',     'NEP', 75, 'theory',    75, 0),
                ('Computer Sc','CS',  50, 'both',      35, 15),
            ],
            'Management': [
                ('Accountancy',     'ACC', 100,'theory',100, 0),
                ('Economics',       'ECO', 75, 'theory',75,  0),
                ('Business Studies','BUS', 75, 'theory',75,  0),
                ('English',         'ENG', 75, 'theory',75,  0),
                ('Nepali',          'NEP', 75, 'theory',75,  0),
                ('Mathematics',     'MAT', 75, 'theory',75,  0),
            ],
            'Humanities': [
                ('Sociology',    'SOC', 75, 'theory', 75, 0),
                ('Political Sc', 'POL', 75, 'theory', 75, 0),
                ('History',      'HIS', 75, 'theory', 75, 0),
                ('English',      'ENG', 75, 'theory', 75, 0),
                ('Nepali',       'NEP', 75, 'theory', 75, 0),
                ('Economics',    'ECO', 75, 'theory', 75, 0),
            ],
            'General': [
                ('Mathematics',    'MAT', 100,'theory', 100,0),
                ('English',        'ENG', 75, 'theory', 75, 0),
                ('Science',        'SCI', 75, 'both',   50, 25),
                ('Nepali',         'NEP', 75, 'theory', 75, 0),
                ('Social Studies', 'SS',  75, 'theory', 75, 0),
                ('Optional Math',  'OPT', 75, 'theory', 75, 0),
            ],
        }
        teacher_cycle = 0
        for cls in classes:
            stream_name = cls.stream.name if cls.stream else 'General'
            configs = subject_configs.get(stream_name, subject_configs['General'])
            for sname, code_pfx, max_m, stype, theory_m, prac_m in configs:
                subj = Subject(
                    name=sname,
                    code=f'{code_pfx}{cls.name}{cls.section}',
                    class_id=cls.id,
                    stream_id=cls.stream_id,
                    teacher_id=teachers[teacher_cycle % len(teachers)].id,
                    subject_type=stype,
                    max_marks=max_m,
                    pass_marks=int(max_m * 0.4),
                    credit_hours=4,
                    practical_marks=prac_m
                )
                db.session.add(subj)
                teacher_cycle += 1
        db.session.flush()

        # ── Students ────────────────────────────────────────────
        student_names = [
            'Aarav Sharma',    'Bina Thapa',      'Chandan KC',      'Divya Rai',
            'Eshaan Limbu',    'Freya Karki',     'Gaurav Magar',    'Hira Tamang',
            'Isha Shrestha',   'Jai Poudel',      'Kavya Bhattarai', 'Laxman Gurung',
            'Maya Basnet',     'Nishan Dahal',    'Priya Adhikari',  'Rakesh Pandey',
            'Sita Ghimire',    'Tarun Upreti',    'Uma Joshi',       'Vikram Budhathoki',
            'Anjali Subedi',   'Biraj Ghimire',   'Chetana Paudel',  'Dipak Rana',
        ]
        students = []
        for i, sname in enumerate(student_names):
            cls = classes[i % len(classes)]
            username = sname.lower().replace(' ', '.') + str(i)
            email = f'{username}@student.martyrs.edu.np'
            u = User(username=username, email=email, full_name=sname, role='student', phone=f'9840{i:06d}')
            u.set_password('student123')
            db.session.add(u)
            db.session.flush()
            s = Student(
                user_id=u.id,
                roll_no=f'{cls.name}{cls.section}{str(i+1).zfill(3)}',
                class_id=cls.id,
                gender=random.choice(['male', 'female']),
                address='Biratnagar, Morang, Nepal',
                guardian_name=f'Mr./Mrs. {sname.split()[1]}',
                guardian_phone=f'9850{i:06d}',
                blood_group=random.choice(['A+', 'A-', 'B+', 'B-', 'O+', 'O-']),
                admission_date=date(2081, random.randint(1,4), random.randint(1,28))
            )
            db.session.add(s)
            students.append(s)
        db.session.flush()

        # ── Attendance ──────────────────────────────────────────
        today = date.today()
        for s in students:
            for days_ago in range(45):
                att_date = today - timedelta(days=days_ago)
                if att_date.weekday() < 6:  # Mon-Sat (Nepal)
                    status = random.choices(['present', 'absent', 'late'], weights=[82, 12, 6])[0]
                    att = Attendance(student_id=s.id, class_id=s.class_id,
                                     date=att_date, status=status)
                    db.session.add(att)

        # ── Exams ───────────────────────────────────────────────
        exam_types_seq = [
            ('Unit Test 1', 'unit_test', 25, 10),
            ('First Terminal', 'first_terminal', 75, 30),
            ('Mid-Term', 'mid_term', 50, 20),
        ]
        exams = []
        for cls in classes[:6]:
            for subj in cls.subjects[:3]:
                for etype_name, etype, max_m, pass_m in exam_types_seq:
                    exam = Exam(
                        name=f'{etype_name} — {subj.name}',
                        class_id=cls.id,
                        subject_id=subj.id,
                        exam_date=today + timedelta(days=random.randint(-15, 30)),
                        max_marks=max_m,
                        pass_marks=pass_m,
                        exam_type=etype,
                        academic_year='2081-2082'
                    )
                    db.session.add(exam)
                    exams.append(exam)
        db.session.flush()

        # ── Results ─────────────────────────────────────────────
        for student in students:
            for exam in exams:
                if exam.class_id == student.class_id:
                    pct = random.uniform(38, 98)
                    marks = round(pct * exam.max_marks / 100, 1)
                    grade, gpa = Result.calculate_neb_grade(pct)
                    r = Result(student_id=student.id, exam_id=exam.id,
                               marks_obtained=marks, grade=grade, gpa=gpa)
                    db.session.add(r)

        # ── Fees ────────────────────────────────────────────────
        fee_types = [
            ('Tuition Fee', 3500), ('Exam Fee', 500),
            ('Library Fee', 200),  ('Sports Fee', 300), ('Lab Fee', 800),
        ]
        for student in students:
            for fee_type, amount in fee_types:
                paid = random.random() > 0.3
                fee = Fee(
                    student_id=student.id,
                    fee_type=fee_type,
                    amount=amount,
                    due_date=date(2081, random.randint(1,6), 15),
                    paid_date=date(2081, random.randint(1,6), random.randint(1,28)) if paid else None,
                    payment_method='cash' if paid else None,
                    status='paid' if paid else 'pending',
                    academic_year='2081-2082',
                    receipt_no=f'RCP{random.randint(10000,99999)}' if paid else None
                )
                db.session.add(fee)

        # ── Notices ─────────────────────────────────────────────
        notices_data = [
            ('Annual Sports Day 2081',    'The Annual Sports Day will be held on Poush 15, 2081. All students are encouraged to participate. Registration opens Poush 10.', 'all', 'high'),
            ('Board Exam Schedule Released', 'NEB Grade 12 Board Exam schedule has been released. Students must collect admit cards from the exam section after clearing all dues.', 'student', 'urgent'),
            ('Parent-Teacher Meeting',    'A Parent-Teacher Meeting is scheduled for Mangsir 30, 2081 from 10 AM to 3 PM at the college auditorium.', 'parent', 'high'),
            ('Staff Development Workshop','A professional development workshop will be conducted for all teaching staff on Poush 5, 2081. Attendance is mandatory.', 'teacher', 'normal'),
            ('Fee Collection Notice',     'The second installment of annual fees is due by Mangsir 30, 2081. Late fee of NPR 100/day will be charged after deadline.', 'all', 'urgent'),
            ('New Library Books',         'The college library has added 200 new reference books for NEB +2 Science and Management streams. Visit the library to explore.', 'all', 'normal'),
        ]
        for title, content, target, priority in notices_data:
            n = Notice(title=title, content=content, created_by=admin.id,
                       target_role=target, priority=priority, is_active=True,
                       expiry_date=today + timedelta(days=30))
            db.session.add(n)

        # ── Timetable ───────────────────────────────────────────
        periods = [
            (time(10, 0),  time(10, 45), 1),
            (time(10, 45), time(11, 30), 2),
            (time(11, 30), time(12, 15), 3),
            (time(13, 0),  time(13, 45), 4),
            (time(13, 45), time(14, 30), 5),
            (time(14, 30), time(15, 15), 6),
        ]
        for cls in classes[:6]:
            for day in range(6):  # Mon-Sat
                for pi, (start, end, pno) in enumerate(periods):
                    if pi < len(cls.subjects):
                        subj = cls.subjects[pi % len(cls.subjects)]
                        tt = TimeTable(
                            class_id=cls.id,
                            subject_id=subj.id,
                            teacher_id=subj.teacher_id,
                            day_of_week=day,
                            start_time=start,
                            end_time=end,
                            period_no=pno,
                            room_no=cls.room_no
                        )
                        db.session.add(tt)

        # ── Assignments ─────────────────────────────────────────
        from models import Assignment
        assignment_data = [
            ('Physics Lab Report — Ohm\'s Law', 'Prepare a detailed lab report on your Ohm\'s Law practical experiment. Include circuit diagram, observations table, and conclusions.', 10),
            ('Essay — Climate Change Impact in Nepal', 'Write a 500-word essay discussing the impact of climate change on Nepal\'s agriculture and water resources.', 10),
            ('Mathematics Problem Set 3', 'Complete exercises 3.1 to 3.5 from the NEB Mathematics textbook. Show all working steps clearly.', 15),
            ('Business Plan Draft', 'Prepare a one-page business plan for a small business of your choice. Include target market, products/services, and revenue model.', 10),
        ]
        for i, (title, desc, marks) in enumerate(assignment_data):
            cls = classes[i % 4]
            if cls.subjects:
                asgn = Assignment(
                    teacher_id=teachers[i % len(teachers)].id,
                    class_id=cls.id,
                    subject_id=cls.subjects[0].id if cls.subjects else None,
                    title=title,
                    description=desc,
                    due_date=today + timedelta(days=random.randint(3, 14)),
                    max_marks=marks
                )
                db.session.add(asgn)

        # ── Parent ──────────────────────────────────────────────
        pu = User(username='parent1', email='parent1@gmail.com', full_name='Ram Sharma',
                  role='parent', phone='9820000001')
        pu.set_password('parent123')
        db.session.add(pu)
        db.session.flush()
        p = Parent(user_id=pu.id, student_id=students[0].id, relationship='father', occupation='Business')
        db.session.add(p)

        db.session.commit()

        print("\n✅ Database seeded successfully!")
        print("\n📋 Login Credentials:")
        print("  Admin:   admin / admin123")
        print("  Teacher: teacher1 / teacher123  (Ramesh Sharma — Mathematics)")
        print("  Student: aarav.sharma0 / student123  (Aarav Sharma)")
        print("  Parent:  parent1 / parent123")
        print(f"\n📊 Summary:")
        print(f"  Streams: {len(streams)} NEB streams")
        print(f"  Classes: {len(classes)} classes")
        print(f"  Teachers: {len(teachers)}")
        print(f"  Students: {len(students)}")
        print(f"  Exams: {len(exams)}")

if __name__ == '__main__':
    seed_all()
