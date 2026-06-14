from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    profile_image = db.Column(db.String(255), default='default.png')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    student_profile = db.relationship('Student', backref='user', uselist=False)
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False)
    parent_profile = db.relationship('Parent', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def __repr__(self):
        return f'<User {self.username}>'


class Stream(db.Model):
    __tablename__ = 'streams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(10), unique=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    classes = db.relationship('Class', backref='stream', lazy=True)
    subjects = db.relationship('Subject', backref='stream', lazy=True)

    def __repr__(self):
        return f'<Stream {self.name}>'


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    stream_id = db.Column(db.Integer, db.ForeignKey('streams.id'))
    class_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    academic_year = db.Column(db.String(20), default='2081-2082')
    capacity = db.Column(db.Integer, default=40)
    room_no = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship('Student', backref='class_ref', lazy=True)
    subjects = db.relationship('Subject', backref='class_ref', lazy=True)
    timetables = db.relationship('TimeTable', backref='class_ref', lazy=True)

    @property
    def full_name(self):
        stream = f' ({self.stream.name})' if self.stream else ''
        return f"Class {self.name} - {self.section}{stream}"


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    admission_date = db.Column(db.Date, default=datetime.utcnow)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    address = db.Column(db.Text)
    guardian_name = db.Column(db.String(150))
    guardian_phone = db.Column(db.String(20))
    blood_group = db.Column(db.String(5))
    academic_year = db.Column(db.String(20), default='2081-2082')
    status = db.Column(db.String(20), default='active')
    profile_image = db.Column(db.String(255), default='default.png')

    attendances = db.relationship('Attendance', backref='student', lazy=True)
    results = db.relationship('Result', backref='student', lazy=True)
    fees = db.relationship('Fee', backref='student', lazy=True)
    parents = db.relationship('Parent', backref='child', lazy=True)

    @property
    def attendance_percentage(self):
        total = len(self.attendances)
        if total == 0:
            return 0
        present = sum(1 for a in self.attendances if a.status == 'present')
        return round((present / total) * 100, 1)


class Teacher(db.Model):
    __tablename__ = 'teachers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    subject = db.Column(db.String(100))
    qualification = db.Column(db.String(200))
    joining_date = db.Column(db.Date, default=datetime.utcnow)
    salary = db.Column(db.Float)
    department = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')

    emergency_contact = db.Column(db.String(20))
    address = db.Column(db.Text)
    employment_type = db.Column(db.String(50), default='Full-time')
    salary_grade = db.Column(db.String(20))
    bank_account = db.Column(db.String(50))
    pan_number = db.Column(db.String(20))
    specialization = db.Column(db.String(200))
    experience_years = db.Column(db.Integer, default=0)
    previous_institution = db.Column(db.String(200))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    blood_group = db.Column(db.String(5))

    profile_image = db.Column(db.String(255), default='default_teacher.png')
    cv_file = db.Column(db.String(255))
    certificate_file = db.Column(db.String(255))
    contract_file = db.Column(db.String(255))
    id_proof = db.Column(db.String(255))
    teaching_license = db.Column(db.String(255))

    classes_taught = db.relationship('Class', backref='class_teacher', lazy=True,
                                     foreign_keys='Class.class_teacher_id')
    subjects = db.relationship('Subject', backref='teacher', lazy=True)
    assignments = db.relationship('Assignment', backref='teacher', lazy=True)
    timetables = db.relationship('TimeTable', backref='teacher', lazy=True)


class Parent(db.Model):
    __tablename__ = 'parents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    relationship = db.Column(db.String(30))
    occupation = db.Column(db.String(100))
    annual_income = db.Column(db.Float)


class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    stream_id = db.Column(db.Integer, db.ForeignKey('streams.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    subject_type = db.Column(db.String(20), default='theory')
    max_marks = db.Column(db.Integer, default=100)
    pass_marks = db.Column(db.Integer, default=40)
    credit_hours = db.Column(db.Integer, default=4)
    practical_marks = db.Column(db.Integer, default=0)
    is_optional = db.Column(db.Boolean, default=False)

    timetables = db.relationship('TimeTable', backref='subject', lazy=True)
    exams = db.relationship('Exam', backref='subject', lazy=True)


class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='present')
    marked_by = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    remarks = db.Column(db.String(200))

    __table_args__ = (db.UniqueConstraint('student_id', 'date'),)


class Exam(db.Model):
    __tablename__ = 'exams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    exam_date = db.Column(db.Date)
    max_marks = db.Column(db.Integer, default=100)
    pass_marks = db.Column(db.Integer, default=40)
    exam_type = db.Column(db.String(30), default='unit')
    academic_year = db.Column(db.String(20), default='2081-2082')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    results = db.relationship('Result', backref='exam', lazy=True)
    class_ref = db.relationship('Class', foreign_keys=[class_id])


class Result(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    marks_obtained = db.Column(db.Float, default=0)
    practical_marks = db.Column(db.Float, default=0)
    grade = db.Column(db.String(5))
    gpa = db.Column(db.Float, default=0.0)
    remarks = db.Column(db.String(200))
    is_absent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def total_marks(self):
        return (self.marks_obtained or 0) + (self.practical_marks or 0)

    @property
    def percentage(self):
        if self.exam and self.exam.max_marks:
            return round((self.total_marks / self.exam.max_marks) * 100, 1)
        return 0

    @staticmethod
    def calculate_neb_grade(percentage):
        if percentage >= 90:
            return 'A+', 4.0
        elif percentage >= 80:
            return 'A', 3.6
        elif percentage >= 70:
            return 'B+', 3.2
        elif percentage >= 60:
            return 'B', 2.8
        elif percentage >= 50:
            return 'C+', 2.4
        elif percentage >= 40:
            return 'C', 2.0
        elif percentage >= 35:
            return 'D', 1.6
        else:
            return 'F', 0.0

    @staticmethod
    def calculate_grade(percentage):
        grade, _ = Result.calculate_neb_grade(percentage)
        return grade


class Fee(db.Model):
    __tablename__ = 'fees'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    fee_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)
    payment_method = db.Column(db.String(30))
    status = db.Column(db.String(20), default='pending')
    academic_year = db.Column(db.String(20), default='2081-2082')
    receipt_no = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notice(db.Model):
    __tablename__ = 'notices'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.Date)
    target_role = db.Column(db.String(20), default='all')
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.String(20), default='normal')

    author = db.relationship('User', foreign_keys=[created_by])


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    max_marks = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')

    class_ref = db.relationship('Class', foreign_keys=[class_id])
    subject_ref = db.relationship('Subject', foreign_keys=[subject_id])


class TimeTable(db.Model):
    __tablename__ = 'timetables'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    day_of_week = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    room_no = db.Column(db.String(20))
    period_no = db.Column(db.Integer, default=1)


class Message(db.Model):
    """Direct messages between admin/teacher and parents/students."""
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    recipient_type = db.Column(db.String(30), default='specific')
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    email_sent = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')



class LeaveRequest(db.Model):
    """Leave requests from students or teachers."""
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type = db.Column(db.String(50), default='sick')
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_comment = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requester = db.relationship('User', foreign_keys=[user_id], backref='leave_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    @property
    def days(self):
        if self.from_date and self.to_date:
            return (self.to_date - self.from_date).days + 1
        return 0


class Event(db.Model):
    """School calendar events."""
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    event_type = db.Column(db.String(50), default='general')
    target_role = db.Column(db.String(20), default='all')
    location = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    author = db.relationship('User', foreign_keys=[created_by])



class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notif_type = db.Column(db.String(50), default='info')
    link = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id], backref='notifications')
