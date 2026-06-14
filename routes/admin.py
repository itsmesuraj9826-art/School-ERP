from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Student, Teacher, Parent, Class, Subject, Stream, Attendance, Exam, Result, Fee, Notice, \
    Assignment, TimeTable, Message, LeaveRequest, Event, Notification
from datetime import datetime, date, timedelta
from sqlalchemy import func
from app import mail
from utils.mail_helpers import (generate_password, generate_username, send_credentials_email,
                                send_fee_reminder, send_notice_to_parent, send_direct_message)

admin_bp = Blueprint('admin', __name__)


# ============================================================================
# DECORATORS
# ============================================================================

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated


def handle_db_error(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            db.session.rollback()
            flash(f'Database error: {str(e)}', 'danger')
            return redirect(request.referrer or url_for('admin.dashboard'))

    return decorated


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_unique_username(role, full_name, identifier):
    """Generate a unique username for a user"""
    username = generate_username(role, full_name, identifier)
    base = username
    counter = 1
    while User.query.filter_by(username=username).first():
        username = f"{base[:-len('@tbc.edu.np')]}{counter}@tbc.edu.np"
        counter += 1
    return username


def create_user_and_get_credentials(role, full_name, email, phone, identifier):
    """Create a user and return the user object and password"""
    username = generate_unique_username(role, full_name, identifier)
    password = generate_password()

    user = User(
        username=username,
        email=email if email else None,
        full_name=full_name.strip(),
        phone=phone,
        role=role
    )
    user.set_password(password)

    return user, password


def send_credentials_or_fallback(email, full_name, role, username, password, extra_info=""):
    """Send credentials email or return them for display"""
    sent = send_credentials_email(mail, email, full_name, role, username, password, extra_info)
    if not sent:
        flash(f'Email failed! Save these credentials: {username} / {password}', 'warning')
    return sent


def parse_date(date_string):
    """Safely parse a date string"""
    return datetime.strptime(date_string, '%Y-%m-%d').date() if date_string else None


# ============================================================================
# DASHBOARD
# ============================================================================

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    today = date.today()

    # Get attendance for today
    today_attendance = Attendance.query.filter_by(date=today).all()
    present_today = sum(1 for a in today_attendance if a.status == 'present')
    attendance_pct = round((present_today / len(today_attendance) * 100), 1) if today_attendance else 0

    # Get fee totals
    paid_fees = db.session.query(func.sum(Fee.amount)).filter_by(status='paid').scalar() or 0
    pending_fees = db.session.query(func.sum(Fee.amount)).filter_by(status='pending').scalar() or 0

    # Get recent data
    recent_students = (db.session.query(Student, User)
                       .join(User, Student.user_id == User.id)
                       .order_by(Student.id.desc()).limit(5).all())

    upcoming_exams = Exam.query.filter(Exam.exam_date >= today).order_by(Exam.exam_date.asc()).limit(5).all()
    recent_notices = Notice.query.filter_by(is_active=True).order_by(Notice.created_at.desc()).limit(5).all()

    # Monthly admissions chart - MySQL compatible
    monthly_admissions = []
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=30 * i))
        year_month = month_start.strftime('%Y-%m')
        count = Student.query.filter(
            func.date_format(Student.admission_date, '%Y-%m') == year_month
        ).count()
        monthly_admissions.append({'month': month_start.strftime('%b'), 'count': count})

    # Stream statistics
    stream_stats = []
    for stream in Stream.query.filter_by(is_active=True).all():
        count = (db.session.query(Student)
                 .join(Class, Student.class_id == Class.id)
                 .filter(Class.stream_id == stream.id, Student.status == 'active')
                 .count())
        stream_stats.append({'name': stream.name, 'count': count})

    return render_template('admin/dashboard.html',
                           total_students=Student.query.filter_by(status='active').count(),
                           total_teachers=Teacher.query.filter_by(status='active').count(),
                           total_parents=Parent.query.count(),
                           total_classes=Class.query.count(),
                           attendance_pct=attendance_pct,
                           present_today=present_today,
                           total_today=len(today_attendance),
                           paid_fees=paid_fees,
                           pending_fees=pending_fees,
                           recent_students=recent_students,
                           upcoming_exams=upcoming_exams,
                           recent_notices=recent_notices,
                           monthly_admissions=monthly_admissions,
                           stream_stats=stream_stats)


# ============================================================================
# STUDENT MANAGEMENT
# ============================================================================

@admin_bp.route('/students')
@login_required
@admin_required
def students():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    class_filter = request.args.get('class_id', '')
    stream_filter = request.args.get('stream_id', '')

    query = (db.session.query(Student, User, Class)
             .join(User, Student.user_id == User.id)
             .outerjoin(Class, Student.class_id == Class.id))

    if search:
        query = query.filter(db.or_(
            User.full_name.ilike(f'%{search}%'),
            Student.roll_no.ilike(f'%{search}%')
        ))
    if class_filter:
        query = query.filter(Student.class_id == class_filter)
    if stream_filter:
        query = query.filter(Class.stream_id == stream_filter)

    # IMPORTANT: Use .all() for items, but paginate for pagination
    pagination = query.order_by(User.full_name).paginate(page=page, per_page=15, error_out=False)

    # Create an items list for the template
    students_data = pagination

    classes = Class.query.order_by(Class.name, Class.section).all()
    streams = Stream.query.filter_by(is_active=True).all()

    return render_template('admin/students.html',
                           students_data=students_data,
                           classes=classes,
                           streams=streams,
                           search=search,
                           class_filter=class_filter,
                           stream_filter=stream_filter)


@admin_bp.route('/students/<int:sid>')
@login_required
@admin_required
def view_student(sid):
    student = db.get_or_404(Student, sid)
    user = db.session.get(User, student.user_id)
    cls = db.session.get(Class, student.class_id) if student.class_id else None
    fees = Fee.query.filter_by(student_id=sid).order_by(Fee.due_date.desc()).all()
    results = (db.session.query(Result, Exam)
               .join(Exam, Result.exam_id == Exam.id)
               .filter(Result.student_id == sid)
               .order_by(Exam.exam_date.desc()).all())
    attendances = Attendance.query.filter_by(student_id=sid).order_by(Attendance.date.desc()).limit(30).all()
    parent = Parent.query.filter_by(student_id=sid).first()
    parent_user = db.session.get(User, parent.user_id) if parent else None

    return render_template('admin/view_student.html',
                           student=student, user=user, cls=cls, fees=fees,
                           results=results, attendances=attendances,
                           parent=parent, parent_user=parent_user)


@admin_bp.route('/students/add', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def add_student():
    if request.method == 'POST':
        roll_no = request.form['roll_no'].strip()
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip()

        # Create user
        user, password = create_user_and_get_credentials('student', full_name, email, request.form.get('phone'),
                                                         roll_no)
        db.session.add(user)
        db.session.flush()

        # Create student
        student = Student(
            user_id=user.id,
            roll_no=roll_no,
            class_id=request.form.get('class_id') or None,
            gender=request.form.get('gender'),
            address=request.form.get('address'),
            guardian_name=request.form.get('guardian_name'),
            guardian_phone=request.form.get('guardian_phone'),
            blood_group=request.form.get('blood_group'),
            date_of_birth=parse_date(request.form.get('date_of_birth')),
            admission_date=parse_date(request.form.get('admission_date')) or date.today()
        )
        db.session.add(student)
        db.session.commit()

        # Send credentials
        extra_info = f"Roll No: {roll_no}"
        send_credentials_or_fallback(email, full_name, 'student', user.username, password, extra_info)
        flash(f'Student {full_name} added successfully!', 'success')
        return redirect(url_for('admin.students'))

    classes = Class.query.order_by(Class.name, Class.section).all()
    return render_template('admin/add_student.html', classes=classes)


@admin_bp.route('/students/<int:sid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def edit_student(sid):
    student = db.get_or_404(Student, sid)
    user = db.session.get(User, student.user_id)

    if request.method == 'POST':
        try:
            # Update user info
            user.full_name = request.form['full_name'].strip()
            user.email = request.form['email'].strip()
            user.phone = request.form.get('phone')
            user.is_active = 'is_active' in request.form

            # Update student info
            student.roll_no = request.form['roll_no'].strip()
            student.class_id = request.form.get('class_id') or None
            student.gender = request.form.get('gender')
            student.address = request.form.get('address')
            student.guardian_name = request.form.get('guardian_name')
            student.guardian_phone = request.form.get('guardian_phone')
            student.blood_group = request.form.get('blood_group')
            student.status = request.form.get('status', 'active')

            if request.form.get('date_of_birth'):
                student.date_of_birth = parse_date(request.form['date_of_birth'])

            # Handle profile photo upload
            if 'profile_image' in request.files and request.files['profile_image'].filename:
                from utils.file_helpers import save_student_file, delete_student_file
                if student.profile_image and student.profile_image != 'default.png':
                    delete_student_file(student.profile_image)
                saved = save_student_file(request.files['profile_image'], sid, 'profile')
                if saved:
                    student.profile_image = saved

            # Optional password reset
            new_password = request.form.get('new_password', '').strip()
            if new_password:
                user.set_password(new_password)
                flash('Password has been reset.', 'info')

            db.session.commit()
            flash(f'Student {user.full_name} updated successfully!', 'success')
            return redirect(url_for('admin.view_student', sid=sid))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'danger')
            return redirect(url_for('admin.edit_student', sid=sid))

    classes = Class.query.order_by(Class.name, Class.section).all()
    return render_template('admin/edit_student.html', student=student, user=user, classes=classes)

@admin_bp.route('/students/<int:sid>/delete', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def delete_student(sid):
    student = db.get_or_404(Student, sid)
    user = db.session.get(User, student.user_id)

    db.session.delete(student)
    if user:
        db.session.delete(user)
    db.session.commit()

    flash('Student deleted successfully.', 'success')
    return redirect(url_for('admin.students'))


# ============================================================================
# TEACHER MANAGEMENT
# ============================================================================

@admin_bp.route('/teachers')
@login_required
@admin_required
def teachers():
    teachers_data = (db.session.query(Teacher, User)
                     .join(User, Teacher.user_id == User.id)
                     .order_by(User.full_name).all())
    return render_template('admin/teachers.html', teachers_data=teachers_data)


@admin_bp.route('/teachers/<int:tid>')
@login_required
@admin_required
def view_teacher(tid):
    teacher = db.get_or_404(Teacher, tid)
    user = db.session.get(User, teacher.user_id)
    subjects = Subject.query.filter_by(teacher_id=tid).all()
    classes = Class.query.filter_by(class_teacher_id=tid).all()
    assignments = Assignment.query.filter_by(teacher_id=tid).order_by(Assignment.created_at.desc()).limit(10).all()

    return render_template('admin/view_teacher.html',
                           teacher=teacher,
                           user=user,
                           subjects=subjects,
                           classes=classes,
                           assignments=assignments,
                           today=date.today())


@admin_bp.route('/teachers/add', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def add_teacher():
    if request.method == 'POST':
        employee_id = request.form['employee_id'].strip()
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip()

        # Create user
        user, password = create_user_and_get_credentials('teacher', full_name, email, request.form.get('phone'),
                                                         employee_id)
        db.session.add(user)
        db.session.flush()

        # Create teacher with all fields
        teacher = Teacher(
            user_id=user.id,
            employee_id=employee_id,
            subject=request.form.get('subject'),
            qualification=request.form.get('qualification'),
            department=request.form.get('department'),
            salary=float(request.form['salary']) if request.form.get('salary') else None,
            joining_date=parse_date(request.form.get('joining_date')) or date.today(),

            # Additional fields
            emergency_contact=request.form.get('emergency_contact'),
            address=request.form.get('address'),
            employment_type=request.form.get('employment_type', 'Full-time'),
            salary_grade=request.form.get('salary_grade'),
            bank_account=request.form.get('bank_account'),
            pan_number=request.form.get('pan_number'),
            specialization=request.form.get('specialization'),
            experience_years=int(request.form['experience_years']) if request.form.get('experience_years') else 0,
            previous_institution=request.form.get('previous_institution'),
            date_of_birth=parse_date(request.form.get('date_of_birth')),
            gender=request.form.get('gender'),
            blood_group=request.form.get('blood_group')
        )
        db.session.add(teacher)
        db.session.commit()

        # Send credentials
        extra_info = f"Employee ID: {employee_id} | Department: {request.form.get('department', '')}"
        send_credentials_or_fallback(email, full_name, 'teacher', user.username, password, extra_info)
        flash(f'Teacher {full_name} added successfully!', 'success')
        return redirect(url_for('admin.teachers'))

    return render_template('admin/add_teacher.html')

@admin_bp.route('/teachers/<int:tid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def edit_teacher(tid):
    teacher = db.get_or_404(Teacher, tid)
    user = db.session.get(User, teacher.user_id)

    if request.method == 'POST':
        # Update user info
        user.full_name = request.form['full_name'].strip()
        user.email = request.form['email'].strip()
        user.phone = request.form.get('phone')
        user.is_active = 'is_active' in request.form

        # Update teacher info - Basic
        teacher.employee_id = request.form['employee_id'].strip()
        teacher.subject = request.form.get('subject')
        teacher.qualification = request.form.get('qualification')
        teacher.department = request.form.get('department')
        teacher.salary = float(request.form['salary']) if request.form.get('salary') else None
        teacher.status = request.form.get('status', 'active')

        # Update teacher info - Additional fields
        teacher.emergency_contact = request.form.get('emergency_contact')
        teacher.address = request.form.get('address')
        teacher.employment_type = request.form.get('employment_type', 'Full-time')
        teacher.salary_grade = request.form.get('salary_grade')
        teacher.bank_account = request.form.get('bank_account')
        teacher.pan_number = request.form.get('pan_number')
        teacher.specialization = request.form.get('specialization')
        teacher.experience_years = int(request.form['experience_years']) if request.form.get('experience_years') else 0
        teacher.previous_institution = request.form.get('previous_institution')

        if request.form.get('date_of_birth'):
            teacher.date_of_birth = parse_date(request.form['date_of_birth'])
        if request.form.get('gender'):
            teacher.gender = request.form.get('gender')
        if request.form.get('blood_group'):
            teacher.blood_group = request.form.get('blood_group')
        if request.form.get('joining_date'):
            teacher.joining_date = parse_date(request.form['joining_date'])

        # Handle file uploads
        from utils.file_helpers import save_teacher_file, delete_teacher_file

        # Profile Image
        if 'profile_image' in request.files and request.files['profile_image'].filename:
            if teacher.profile_image and teacher.profile_image != 'default_teacher.png':
                delete_teacher_file(teacher.profile_image)
            teacher.profile_image = save_teacher_file(request.files['profile_image'], tid, 'profile')

        # CV File
        if 'cv_file' in request.files and request.files['cv_file'].filename:
            if teacher.cv_file:
                delete_teacher_file(teacher.cv_file)
            teacher.cv_file = save_teacher_file(request.files['cv_file'], tid, 'cv')

        # Certificate File
        if 'certificate_file' in request.files and request.files['certificate_file'].filename:
            if teacher.certificate_file:
                delete_teacher_file(teacher.certificate_file)
            teacher.certificate_file = save_teacher_file(request.files['certificate_file'], tid, 'cert')

        # Contract File
        if 'contract_file' in request.files and request.files['contract_file'].filename:
            if teacher.contract_file:
                delete_teacher_file(teacher.contract_file)
            teacher.contract_file = save_teacher_file(request.files['contract_file'], tid, 'contract')

        # ID Proof
        if 'id_proof' in request.files and request.files['id_proof'].filename:
            if teacher.id_proof:
                delete_teacher_file(teacher.id_proof)
            teacher.id_proof = save_teacher_file(request.files['id_proof'], tid, 'idproof')

        # Teaching License
        if 'teaching_license' in request.files and request.files['teaching_license'].filename:
            if teacher.teaching_license:
                delete_teacher_file(teacher.teaching_license)
            teacher.teaching_license = save_teacher_file(request.files['teaching_license'], tid, 'license')

        # Optional password reset
        new_password = request.form.get('new_password', '').strip()
        if new_password:
            user.set_password(new_password)
            flash('Password has been reset.', 'info')

        db.session.commit()
        flash(f'Teacher {user.full_name} updated successfully.', 'success')
        return redirect(url_for('admin.view_teacher', tid=tid))

    return render_template('admin/edit_teacher.html', teacher=teacher, user=user)

@admin_bp.route('/teachers/<int:tid>/delete', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def delete_teacher(tid):
    teacher = db.get_or_404(Teacher, tid)
    user = db.session.get(User, teacher.user_id)

    db.session.delete(teacher)
    if user:
        db.session.delete(user)
    db.session.commit()

    flash('Teacher deleted successfully.', 'success')
    return redirect(url_for('admin.teachers'))


# ============================================================================
# PARENT MANAGEMENT
# ============================================================================

@admin_bp.route('/parents')
@login_required
@admin_required
def parents():
    from flask import session as _session
    new_creds = _session.pop('new_parent_creds', None)

    parents_data = (db.session.query(Parent, User, Student)
                    .join(User, Parent.user_id == User.id)
                    .outerjoin(Student, Parent.student_id == Student.id)
                    .order_by(User.full_name).all())

    students = (db.session.query(Student, User)
                .join(User, Student.user_id == User.id)
                .filter(Student.status == 'active')
                .order_by(User.full_name).all())

    return render_template('admin/parents.html', parents_data=parents_data,
                           students=students, new_creds=new_creds)


@admin_bp.route('/parents/<int:pid>')
@login_required
@admin_required
def view_parent(pid):
    parent = db.get_or_404(Parent, pid)
    user = db.session.get(User, parent.user_id)
    student = db.session.get(Student, parent.student_id) if parent.student_id else None
    student_user = db.session.get(User, student.user_id) if student else None

    return render_template('admin/view_parent.html',
                           parent=parent, user=user, student=student, student_user=student_user)


@admin_bp.route('/parents/add', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def add_parent():
    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        email = (request.form.get('email') or '').strip() or None
        student_id = request.form.get('student_id') or None

        # If email already belongs to another user, drop it to avoid unique-key error
        if email and User.query.filter_by(email=email).first():
            flash(f'Email {email} is already in use by another account — parent will be created without email.', 'warning')
            email = None

        # Generate identifier for username
        identifier = 'par'
        if student_id:
            student = db.session.get(Student, int(student_id))
            if student:
                identifier = student.roll_no

        # Create user
        user, password = create_user_and_get_credentials('parent', full_name, email, request.form.get('phone'),
                                                         identifier)
        db.session.add(user)
        db.session.flush()

        # Create parent
        parent = Parent(
            user_id=user.id,
            student_id=student_id,
            relationship=request.form.get('relationship'),
            occupation=request.form.get('occupation'),
            annual_income=float(request.form['annual_income']) if request.form.get('annual_income') else None
        )
        db.session.add(parent)
        db.session.commit()

        # Prepare extra info
        extra_info = ""
        if student_id:
            student = db.session.get(Student, int(student_id))
            if student:
                student_user = db.session.get(User, student.user_id)
                if student_user:
                    extra_info = f"Linked to student: {student_user.full_name} (Roll No: {student.roll_no})"

        # Send credentials via email (optional)
        if email:
            send_credentials_or_fallback(email, full_name, 'parent', user.username, password, extra_info)

        # Build WhatsApp wa.me link so admin can send with one tap
        parent_phone = request.form.get('phone', '').strip()
        wa_link = None
        if parent_phone:
            digits = ''.join(c for c in parent_phone if c.isdigit())
            if not digits.startswith('977'):
                digits = '977' + digits.lstrip('0')
            school = 'Martyrs Memorial +2 College'
            wa_text = (
                f"Hello {full_name}!\n\n"
                f"Welcome to {school} Parent Portal.\n\n"
                f"Your login credentials:\n"
                f"Username: {user.username}\n"
                f"Password: {password}\n\n"
                f"{extra_info}\n\n"
                f"Please keep these safe."
            )
            import urllib.parse
            wa_link = 'https://wa.me/' + digits + '?text=' + urllib.parse.quote(wa_text)

        # Store one-time credentials in session for the redirect page to show
        from flask import session as _session
        _session['new_parent_creds'] = {
            'name': full_name,
            'username': user.username,
            'password': password,
            'phone': parent_phone,
            'wa_link': wa_link,
        }
        flash('Parent ' + full_name + ' created! See credentials below.', 'success')
        return redirect(url_for('admin.parents'))

    students = (db.session.query(Student, User)
                .join(User, Student.user_id == User.id)
                .filter(Student.status == 'active')
                .order_by(User.full_name).all())

    return render_template('admin/add_parent.html', students=students)


@admin_bp.route('/parents/<int:pid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def edit_parent(pid):
    parent = db.get_or_404(Parent, pid)
    user = db.session.get(User, parent.user_id)

    if request.method == 'POST':
        # Update user info
        user.full_name = request.form['full_name'].strip()
        user.email = request.form['email'].strip()
        user.phone = request.form.get('phone')
        user.is_active = 'is_active' in request.form

        # Update parent info
        parent.student_id = request.form.get('student_id') or None
        parent.relationship = request.form.get('relationship')
        parent.occupation = request.form.get('occupation')
        parent.annual_income = float(request.form['annual_income']) if request.form.get('annual_income') else None

        # Optional password reset
        new_password = request.form.get('new_password', '').strip()
        if new_password:
            user.set_password(new_password)
            flash('Password has been reset.', 'info')

        db.session.commit()
        flash(f'Parent {user.full_name} updated successfully.', 'success')
        return redirect(url_for('admin.view_parent', pid=pid))

    students = (db.session.query(Student, User)
                .join(User, Student.user_id == User.id)
                .filter(Student.status == 'active')
                .order_by(User.full_name).all())

    return render_template('admin/edit_parent.html', parent=parent, user=user, students=students)


@admin_bp.route('/parents/<int:pid>/delete', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def delete_parent(pid):
    parent = db.get_or_404(Parent, pid)
    user = db.session.get(User, parent.user_id)

    db.session.delete(parent)
    if user:
        db.session.delete(user)
    db.session.commit()

    flash('Parent deleted successfully.', 'success')
    return redirect(url_for('admin.parents'))


# ============================================================================
# CLASS MANAGEMENT
# ============================================================================

@admin_bp.route('/classes')
@login_required
@admin_required
def classes():
    classes_data = Class.query.order_by(Class.name, Class.section).all()
    teachers = db.session.query(Teacher, User).join(User, Teacher.user_id == User.id).all()
    streams = Stream.query.filter_by(is_active=True).all()

    return render_template('admin/classes.html',
                           classes_data=classes_data, teachers=teachers, streams=streams)


@admin_bp.route('/classes/add', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def add_class():
    new_class = Class(
        name=request.form['name'],
        section=request.form['section'],
        stream_id=request.form.get('stream_id') or None,
        class_teacher_id=request.form.get('class_teacher_id') or None,
        academic_year=request.form.get('academic_year', '2081-2082'),
        capacity=int(request.form.get('capacity', 40)),
        room_no=request.form.get('room_no')
    )
    db.session.add(new_class)
    db.session.commit()

    flash('Class added successfully!', 'success')
    return redirect(url_for('admin.classes'))


# ============================================================================
# CLASS MANAGEMENT (Additional Routes)
# ============================================================================

@admin_bp.route('/class/<int:cid>')
@login_required
@admin_required
def view_class(cid):
    """View detailed information about a specific class"""
    class_obj = db.get_or_404(Class, cid)
    subjects = Subject.query.filter_by(class_id=cid).all()
    teachers = db.session.query(Teacher, User).join(User, Teacher.user_id == User.id).all()
    streams = Stream.query.filter_by(is_active=True).all()

    # Students with user info
    students_raw = db.session.query(Student, User)\
        .join(User, Student.user_id == User.id)\
        .filter(Student.class_id == cid, Student.status == 'active')\
        .order_by(Student.roll_no).all()

    student_ids = [s.id for s, u in students_raw]

    # Attendance stats per student
    from sqlalchemy import func
    att_stats = {}
    if student_ids:
        rows = db.session.query(
            Attendance.student_id,
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == 'present', 1), else_=0)).label('present')
        ).filter(Attendance.student_id.in_(student_ids))\
         .group_by(Attendance.student_id).all()
        for r in rows:
            pct = round(r.present / r.total * 100, 1) if r.total else 0
            att_stats[r.student_id] = {'total': r.total, 'present': r.present, 'pct': pct}

    # Class-level attendance summary
    total_att = sum(v['total'] for v in att_stats.values())
    total_present = sum(v['present'] for v in att_stats.values())
    class_att_pct = round(total_present / total_att * 100, 1) if total_att else 0

    # Exams for this class
    exams = Exam.query.filter_by(class_id=cid).order_by(Exam.exam_date.desc()).all()

    # Timetable grouped by day
    DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    timetable_raw = db.session.query(TimeTable, Subject, Teacher, User)\
        .outerjoin(Subject, TimeTable.subject_id == Subject.id)\
        .outerjoin(Teacher, TimeTable.teacher_id == Teacher.id)\
        .outerjoin(User, Teacher.user_id == User.id)\
        .filter(TimeTable.class_id == cid)\
        .order_by(TimeTable.day_of_week, TimeTable.start_time).all()

    timetable = {}
    for tt, subj, teacher, user in timetable_raw:
        d = tt.day_of_week
        if d not in timetable:
            timetable[d] = []
        timetable[d].append({'tt': tt, 'subject': subj, 'teacher': teacher, 'teacher_user': user})

    # Low attendance students (below 75%)
    low_att_students = [(s, u, att_stats.get(s.id, {'pct': 0}))
                        for s, u in students_raw
                        if att_stats.get(s.id, {}).get('pct', 100) < 75]

    return render_template('admin/view_class.html',
                           class_obj=class_obj,
                           students=students_raw,
                           att_stats=att_stats,
                           class_att_pct=class_att_pct,
                           subjects=subjects,
                           teachers=teachers,
                           streams=streams,
                           exams=exams,
                           timetable=timetable,
                           DAYS=DAYS,
                           low_att_students=low_att_students)


@admin_bp.route('/class/<int:cid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def edit_class(cid):
    """Edit class information"""
    class_obj = db.get_or_404(Class, cid)
    teachers = db.session.query(Teacher, User).join(User, Teacher.user_id == User.id).all()
    streams = Stream.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        try:
            class_obj.name = request.form['name']
            class_obj.section = request.form['section']
            class_obj.stream_id = request.form.get('stream_id') or None
            class_obj.class_teacher_id = request.form.get('class_teacher_id') or None
            class_obj.room_no = request.form.get('room_no')
            class_obj.capacity = int(request.form.get('capacity', 40))
            class_obj.academic_year = request.form.get('academic_year', '2081-2082')

            db.session.commit()
            flash(f'Class {class_obj.name}-{class_obj.section} updated successfully!', 'success')
            return redirect(url_for('admin.view_class', cid=cid))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating class: {str(e)}', 'danger')
            return redirect(url_for('admin.edit_class', cid=cid))

    return render_template('admin/edit_class.html',
                           class_obj=class_obj,
                           teachers=teachers,
                           streams=streams)


@admin_bp.route('/class/<int:cid>/delete', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def delete_class(cid):
    """Delete a class"""
    class_obj = db.get_or_404(Class, cid)

    # Check if class has students
    student_count = Student.query.filter_by(class_id=cid).count()
    if student_count > 0:
        flash(f'Cannot delete class with {student_count} students. Please transfer or remove students first.', 'danger')
        return redirect(url_for('admin.classes'))

    class_name = f"{class_obj.name}-{class_obj.section}"
    db.session.delete(class_obj)
    db.session.commit()

    flash(f'Class {class_name} deleted successfully.', 'success')
    return redirect(url_for('admin.classes'))


# ============================================================================
# STREAM MANAGEMENT
# ============================================================================

@admin_bp.route('/streams')
@login_required
@admin_required
def streams():
    streams_data = Stream.query.order_by(Stream.name).all()
    return render_template('admin/streams.html', streams_data=streams_data)


@admin_bp.route('/streams/add', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def add_stream():
    new_stream = Stream(
        name=request.form['name'],
        code=request.form.get('code', '').upper(),
        description=request.form.get('description')
    )
    db.session.add(new_stream)
    db.session.commit()

    flash('Stream added successfully!', 'success')
    return redirect(url_for('admin.streams'))


@admin_bp.route('/streams/<int:sid>/toggle', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def toggle_stream(sid):
    stream = db.get_or_404(Stream, sid)
    stream.is_active = not stream.is_active
    db.session.commit()

    status = "activated" if stream.is_active else "deactivated"
    flash(f'Stream {status}.', 'success')
    return redirect(url_for('admin.streams'))


# ============================================================================
# SUBJECT MANAGEMENT
# ============================================================================

@admin_bp.route('/subjects')
@login_required
@admin_required
def subjects():
    class_filter = request.args.get('class_id', '')
    stream_filter = request.args.get('stream_id', '')

    query = Subject.query
    if class_filter:
        query = query.filter_by(class_id=class_filter)
    if stream_filter:
        query = query.filter_by(stream_id=stream_filter)

    subjects_data = query.order_by(Subject.name).all()
    classes = Class.query.order_by(Class.name, Class.section).all()
    streams = Stream.query.filter_by(is_active=True).all()
    teachers = (db.session.query(Teacher, User)
                .join(User, Teacher.user_id == User.id)
                .order_by(User.full_name).all())

    return render_template('admin/subjects.html',
                           subjects_data=subjects_data, classes=classes, streams=streams,
                           teachers=teachers, class_filter=class_filter, stream_filter=stream_filter)


@admin_bp.route('/subjects/add', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def add_subject():
    new_subject = Subject(
        name=request.form['name'],
        code=request.form.get('code'),
        class_id=request.form.get('class_id') or None,
        stream_id=request.form.get('stream_id') or None,
        teacher_id=request.form.get('teacher_id') or None,
        subject_type=request.form.get('subject_type', 'theory'),
        max_marks=int(request.form.get('max_marks', 100)),
        pass_marks=int(request.form.get('pass_marks', 40)),
        credit_hours=int(request.form.get('credit_hours', 4)),
        practical_marks=int(request.form.get('practical_marks', 0))
    )
    db.session.add(new_subject)
    db.session.commit()

    flash('Subject added successfully!', 'success')
    return redirect(url_for('admin.subjects'))


@admin_bp.route('/subjects/<int:sid>/delete', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def delete_subject(sid):
    subject = db.get_or_404(Subject, sid)
    db.session.delete(subject)
    db.session.commit()

    flash('Subject deleted successfully.', 'success')
    return redirect(url_for('admin.subjects'))


@admin_bp.route('/subjects/<int:sid>/edit', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def edit_subject(sid):
    """Edit subject details including reassigning teacher"""
    subject = db.get_or_404(Subject, sid)

    subject.name = request.form['name']
    subject.code = request.form.get('code')
    subject.class_id = request.form.get('class_id') or None
    subject.stream_id = request.form.get('stream_id') or None
    subject.teacher_id = request.form.get('teacher_id') or None
    subject.subject_type = request.form.get('subject_type', 'theory')
    subject.max_marks = int(request.form.get('max_marks', 100))
    subject.pass_marks = int(request.form.get('pass_marks', 40))
    subject.credit_hours = int(request.form.get('credit_hours', 4))
    subject.practical_marks = int(request.form.get('practical_marks', 0))

    db.session.commit()
    flash(f'Subject "{subject.name}" updated successfully!', 'success')
    return redirect(url_for('admin.subjects', class_id=request.args.get('class_id', ''),
                            stream_id=request.args.get('stream_id', '')))


# ============================================================================
# EXAM MANAGEMENT
# ============================================================================

EXAM_TYPES = [
    ('unit_test', 'Unit Test'),
    ('first_terminal', 'First Terminal'),
    ('mid_term', 'Mid-Term'),
    ('pre_board', 'Pre-Board'),
    ('final_board', 'Final / Board Prep'),
    ('internal', 'Internal Evaluation'),
    ('practical', 'Practical Examination'),
]


@admin_bp.route('/exams')
@login_required
@admin_required
def exams():
    class_filter = request.args.get('class_id', '')
    type_filter = request.args.get('exam_type', '')
    page = request.args.get('page', 1, type=int)

    query = Exam.query
    if class_filter:
        query = query.filter_by(class_id=class_filter)
    if type_filter:
        query = query.filter_by(exam_type=type_filter)

    exams_data = query.order_by(Exam.exam_date.desc()).paginate(page=page, per_page=20)
    classes = Class.query.order_by(Class.name, Class.section).all()

    return render_template('admin/exams.html',
                           exams_data=exams_data, classes=classes, exam_types=EXAM_TYPES,
                           class_filter=class_filter, type_filter=type_filter, today=date.today())


@admin_bp.route('/exams/add', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def add_exam():
    if request.method == 'POST':
        new_exam = Exam(
            name=request.form['name'],
            class_id=request.form.get('class_id') or None,
            subject_id=request.form.get('subject_id') or None,
            exam_date=parse_date(request.form.get('exam_date')),
            max_marks=int(request.form.get('max_marks', 100)),
            pass_marks=int(request.form.get('pass_marks', 40)),
            exam_type=request.form.get('exam_type', 'unit_test'),
            academic_year=request.form.get('academic_year', '2081-2082')
        )
        db.session.add(new_exam)
        db.session.commit()

        flash('Exam created successfully!', 'success')
        return redirect(url_for('admin.exams'))

    classes = Class.query.order_by(Class.name, Class.section).all()
    subjects = Subject.query.order_by(Subject.name).all()

    return render_template('admin/add_exam.html',
                           classes=classes, subjects=subjects, exam_types=EXAM_TYPES)


@admin_bp.route('/exams/<int:eid>/delete', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def delete_exam(eid):
    exam = db.get_or_404(Exam, eid)
    db.session.delete(exam)
    db.session.commit()

    flash('Exam deleted successfully.', 'success')
    return redirect(url_for('admin.exams'))


# ============================================================================
# RESULT MANAGEMENT
# ============================================================================

@admin_bp.route('/results')
@login_required
@admin_required
def results():
    class_filter = request.args.get('class_id', '')
    type_filter = request.args.get('exam_type', '')

    query = Exam.query
    if class_filter:
        query = query.filter_by(class_id=class_filter)
    if type_filter:
        query = query.filter_by(exam_type=type_filter)

    exams_list = query.order_by(Exam.exam_date.desc()).all()
    exam_summary = []

    for exam in exams_list:
        total = Student.query.filter_by(class_id=exam.class_id, status='active').count() if exam.class_id else 0
        entered = Result.query.filter_by(exam_id=exam.id).count()
        avg = db.session.query(func.avg(Result.marks_obtained)).filter_by(exam_id=exam.id).scalar()

        exam_summary.append({
            'exam': exam,
            'total': total,
            'entered': entered,
            'avg': round(float(avg), 1) if avg else 0
        })

    classes = Class.query.order_by(Class.name, Class.section).all()

    return render_template('admin/results.html',
                           exam_summary=exam_summary, classes=classes, exam_types=EXAM_TYPES,
                           class_filter=class_filter, type_filter=type_filter)


@admin_bp.route('/results/<int:eid>/enter', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def enter_marks(eid):
    exam = db.get_or_404(Exam, eid)

    # Get students for this exam's class
    students_data = []
    if exam.class_id:
        students_data = (db.session.query(Student, User)
                         .join(User, Student.user_id == User.id)
                         .filter(Student.class_id == exam.class_id, Student.status == 'active')
                         .order_by(Student.roll_no).all())

    # Get existing results
    existing = {r.student_id: r for r in Result.query.filter_by(exam_id=eid).all()}

    if request.method == 'POST':
        for student, _ in students_data:
            is_absent = f'absent_{student.id}' in request.form
            marks = float(request.form.get(f'marks_{student.id}', 0) or 0)
            practical = float(request.form.get(f'practical_{student.id}', 0) or 0)

            # Calculate grade
            percentage = (marks / exam.max_marks * 100) if exam.max_marks else 0
            grade, gpa = Result.calculate_neb_grade(percentage)

            if student.id in existing:
                result = existing[student.id]
                result.marks_obtained = marks
                result.practical_marks = practical
                result.is_absent = is_absent
                result.grade = grade
                result.gpa = gpa
            else:
                result = Result(
                    student_id=student.id,
                    exam_id=eid,
                    marks_obtained=marks,
                    practical_marks=practical,
                    is_absent=is_absent,
                    grade=grade,
                    gpa=gpa
                )
                db.session.add(result)

        db.session.commit()
        flash(f'Marks saved for {len(students_data)} students!', 'success')
        return redirect(url_for('admin.results'))

    return render_template('admin/enter_marks.html',
                           exam=exam, students_data=students_data, existing=existing)


# ============================================================================
# TIMETABLE MANAGEMENT
# ============================================================================

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


@admin_bp.route('/timetable')
@login_required
@admin_required
def timetable():
    class_filter = request.args.get('class_id', '', type=str)
    selected_class = None
    timetable_data = {}

    if class_filter:
        selected_class = db.session.get(Class, int(class_filter))
        entries = TimeTable.query.filter_by(class_id=class_filter).order_by(TimeTable.day_of_week,
                                                                            TimeTable.period_no).all()

        for entry in entries:
            timetable_data.setdefault(entry.day_of_week, []).append(entry)

    classes = Class.query.order_by(Class.name, Class.section).all()
    subjects = Subject.query.filter_by(class_id=class_filter).all() if class_filter else []
    teachers = (db.session.query(Teacher, User)
                .join(User, Teacher.user_id == User.id)
                .order_by(User.full_name).all())

    return render_template('admin/timetable.html',
                           classes=classes, selected_class=selected_class,
                           timetable_data=timetable_data, days=DAYS,
                           subjects=subjects, teachers=teachers, class_filter=class_filter)


@admin_bp.route('/timetable/add', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def add_timetable():
    # Parse time strings
    start_hour, start_min = map(int, request.form.get('start_time', '10:00').split(':'))
    end_hour, end_min = map(int, request.form.get('end_time', '10:45').split(':'))

    new_entry = TimeTable(
        class_id=request.form['class_id'],
        subject_id=request.form.get('subject_id') or None,
        teacher_id=request.form.get('teacher_id') or None,
        day_of_week=int(request.form['day_of_week']),
        start_time=datetime.strptime(f"{start_hour}:{start_min}", "%H:%M").time(),
        end_time=datetime.strptime(f"{end_hour}:{end_min}", "%H:%M").time(),
        room_no=request.form.get('room_no'),
        period_no=int(request.form.get('period_no', 1))
    )
    db.session.add(new_entry)
    db.session.commit()

    flash('Timetable entry added!', 'success')
    return redirect(url_for('admin.timetable', class_id=request.form.get('class_id', '')))


@admin_bp.route('/timetable/<int:tid>/delete', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def delete_timetable(tid):
    entry = db.get_or_404(TimeTable, tid)
    class_id = entry.class_id
    db.session.delete(entry)
    db.session.commit()

    flash('Timetable entry removed.', 'success')
    return redirect(url_for('admin.timetable', class_id=class_id))


# ============================================================================
# FEE MANAGEMENT
# ============================================================================

@admin_bp.route('/fees')
@login_required
@admin_required
def fees():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')

    query = (db.session.query(Fee, Student, User)
             .join(Student, Fee.student_id == Student.id)
             .join(User, Student.user_id == User.id))

    if status_filter:
        query = query.filter(Fee.status == status_filter)

    fees_data = query.order_by(Fee.due_date.desc()).paginate(page=page, per_page=20)

    # Get totals
    total_collected = db.session.query(func.sum(Fee.amount)).filter_by(status='paid').scalar() or 0
    total_pending = db.session.query(func.sum(Fee.amount)).filter_by(status='pending').scalar() or 0
    total_overdue = db.session.query(func.sum(Fee.amount)).filter_by(status='overdue').scalar() or 0

    # Get active students for dropdown
    students = (db.session.query(Student, User)
                .join(User, Student.user_id == User.id)
                .filter(Student.status == 'active')
                .order_by(User.full_name).all())

    return render_template('admin/fees.html',
                           fees_data=fees_data,
                           total_collected=total_collected,
                           total_pending=total_pending,
                           total_overdue=total_overdue,
                           status_filter=status_filter,
                           students=students)


@admin_bp.route('/fees/add', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def add_fee():
    new_fee = Fee(
        student_id=request.form['student_id'],
        fee_type=request.form['fee_type'],
        amount=float(request.form['amount']),
        due_date=parse_date(request.form.get('due_date')),
        status='pending',
        academic_year=request.form.get('academic_year', '2081-2082')
    )
    db.session.add(new_fee)
    db.session.commit()

    flash('Fee record added!', 'success')
    return redirect(url_for('admin.fees'))


@admin_bp.route('/fees/<int:fid>/pay', methods=['POST'])
@login_required
@admin_required
@handle_db_error
def mark_paid(fid):
    fee = db.get_or_404(Fee, fid)
    fee.status = 'paid'
    fee.paid_date = date.today()
    fee.payment_method = request.form.get('payment_method', 'cash')
    fee.receipt_no = f'RCP{fee.id:06d}'
    db.session.commit()

    flash('Fee marked as paid!', 'success')
    return redirect(url_for('admin.fees'))


# ============================================================================
# NOTICE MANAGEMENT
# ============================================================================

@admin_bp.route('/notices')
@login_required
@admin_required
def notices():
    notices_data = Notice.query.order_by(Notice.created_at.desc()).all()
    return render_template('admin/notices.html', notices_data=notices_data)


@admin_bp.route('/notices/add', methods=['GET', 'POST'])
@login_required
@admin_required
@handle_db_error
def add_notice():
    if request.method == 'POST':
        new_notice = Notice(
            title=request.form['title'],
            content=request.form['content'],
            created_by=current_user.id,
            target_role=request.form.get('target_role', 'all'),
            priority=request.form.get('priority', 'normal'),
            expiry_date=parse_date(request.form.get('expiry_date'))
        )
        db.session.add(new_notice)
        db.session.commit()

        # Email broadcast to parents if requested
        email_broadcast = request.form.get('email_broadcast') == 'on'
        if email_broadcast:
            target = new_notice.target_role
            sent = 0
            # Get all parents linked to active students
            parents_users = (db.session.query(User, Parent)
                             .join(Parent, Parent.user_id == User.id)
                             .filter(User.is_active == True).all())
            for pu, _ in parents_users:
                if pu.email:
                    try:
                        send_notice_to_parent(mail, pu.email, pu.full_name,
                                              new_notice.title, new_notice.content)
                        sent += 1
                    except Exception:
                        pass
            flash(f'Notice published! Email sent to {sent} parent(s).', 'success')
        else:
            flash('Notice published!', 'success')
        return redirect(url_for('admin.notices'))

    return render_template('admin/add_notice.html')

# ============================================================================
# FEE RECEIPT
# ============================================================================

@admin_bp.route('/fees/<int:fid>/receipt')
@login_required
@admin_required
def fee_receipt(fid):
    fee = db.get_or_404(Fee, fid)
    student = db.session.get(Student, fee.student_id)
    student_user = db.session.get(User, student.user_id) if student else None
    cls = db.session.get(Class, student.class_id) if student and student.class_id else None
    from datetime import datetime as _dt
    return render_template('admin/fee_receipt.html',
                           fee=fee, student=student, student_user=student_user, cls=cls,
                           now=_dt.now())


# ============================================================================
# FEE REMINDERS
# ============================================================================

@admin_bp.route('/fees/send-reminders', methods=['POST'])
@login_required
@admin_required
def send_fee_reminders():
    """Email all parents with pending or overdue fees."""
    pending_fees = (db.session.query(Fee, Student, User, Parent, User)
                   .join(Student, Fee.student_id == Student.id)
                   .join(User, Student.user_id == User.id)
                   .join(Parent, Parent.student_id == Student.id)
                   .join(User, Parent.user_id == User.id, isouter=True)
                   .filter(Fee.status.in_(['pending', 'overdue']))
                   .all())

    # Simpler approach: iterate pending fees, look up parent per student
    fees_q = Fee.query.filter(Fee.status.in_(['pending', 'overdue'])).all()
    sent = 0
    notified_parents = set()
    for fee in fees_q:
        student = db.session.get(Student, fee.student_id)
        if not student:
            continue
        student_user = db.session.get(User, student.user_id)
        student_name = student_user.full_name if student_user else student.roll_no
        for parent in student.parents:
            parent_user = db.session.get(User, parent.user_id)
            if parent_user and parent_user.email:
                key = (parent_user.email, fee.id)
                if key not in notified_parents:
                    try:
                        send_fee_reminder(
                            mail, parent_user.email, parent_user.full_name,
                            student_name, fee.fee_type, fee.amount, fee.due_date
                        )
                        sent += 1
                        notified_parents.add(key)
                    except Exception:
                        pass

    flash(f'Fee reminders sent! {sent} email(s) dispatched.', 'success')
    return redirect(url_for('admin.fees'))


# ============================================================================
# MESSAGING MODULE
# ============================================================================

@admin_bp.route('/messages')
@login_required
@admin_required
def messages():
    sent = Message.query.filter_by(sender_id=current_user.id).order_by(Message.sent_at.desc()).all()
    received = Message.query.filter_by(recipient_id=current_user.id).order_by(Message.sent_at.desc()).all()
    # All parents for compose dropdown
    parents = (db.session.query(User, Parent)
               .join(Parent, Parent.user_id == User.id)
               .filter(User.is_active == True).order_by(User.full_name).all())
    teachers = (db.session.query(User, Teacher)
                .join(Teacher, Teacher.user_id == User.id)
                .filter(User.is_active == True).order_by(User.full_name).all())
    return render_template('admin/messages.html',
                           sent=sent, received=received,
                           parents=parents, teachers=teachers)


@admin_bp.route('/messages/send', methods=['POST'])
@login_required
@admin_required
def send_message():
    recipient_type = request.form.get('recipient_type', 'specific')
    subject = request.form.get('subject', '').strip()
    body_text = request.form.get('body', '').strip()

    if not subject or not body_text:
        flash('Subject and message body are required.', 'danger')
        return redirect(url_for('admin.messages'))

    email_copy = request.form.get('send_email') == 'on'
    sent_count = 0

    if recipient_type == 'specific':
        recipient_id = request.form.get('recipient_id', type=int)
        if not recipient_id:
            flash('Please select a recipient.', 'danger')
            return redirect(url_for('admin.messages'))
        msg = Message(sender_id=current_user.id, recipient_id=recipient_id,
                      recipient_type='specific', subject=subject, body=body_text)
        db.session.add(msg)
        if email_copy:
            recipient_user = db.session.get(User, recipient_id)
            if recipient_user and recipient_user.email:
                try:
                    send_direct_message(mail, recipient_user.email, recipient_user.full_name,
                                        current_user.full_name, subject, body_text)
                    msg.email_sent = True
                    sent_count = 1
                except Exception:
                    pass

    else:
        # Broadcast to all parents or all teachers
        if recipient_type == 'all_parents':
            users_q = (db.session.query(User).join(Parent, Parent.user_id == User.id)
                       .filter(User.is_active == True).all())
        elif recipient_type == 'all_teachers':
            users_q = (db.session.query(User).join(Teacher, Teacher.user_id == User.id)
                       .filter(User.is_active == True).all())
        elif recipient_type == 'all_students':
            users_q = (db.session.query(User).join(Student, Student.user_id == User.id)
                       .filter(User.is_active == True).all())
        else:
            users_q = []

        for u in users_q:
            msg = Message(sender_id=current_user.id, recipient_id=u.id,
                          recipient_type=recipient_type, subject=subject, body=body_text)
            db.session.add(msg)
            if email_copy and u.email:
                try:
                    send_direct_message(mail, u.email, u.full_name,
                                        current_user.full_name, subject, body_text)
                    msg.email_sent = True
                    sent_count += 1
                except Exception:
                    pass

    db.session.commit()
    flash(f'Message sent! {sent_count} email(s) also dispatched.', 'success')
    return redirect(url_for('admin.messages'))


@admin_bp.route('/messages/<int:mid>/read', methods=['POST'])
@login_required
@admin_required
def mark_message_read(mid):
    msg = db.get_or_404(Message, mid)
    if msg.recipient_id == current_user.id:
        msg.is_read = True
        db.session.commit()
    return redirect(url_for('admin.messages'))


# ============================================================================
# STUDENT REPORT CARD
# ============================================================================

@admin_bp.route('/students/<int:sid>/report-card')
@login_required
@admin_required
def student_report_card(sid):
    student = db.get_or_404(Student, sid)
    student_user = db.session.get(User, student.user_id)
    cls = db.session.get(Class, student.class_id) if student.class_id else None

    all_results = (db.session.query(Result, Exam, Subject)
                   .join(Exam, Result.exam_id == Exam.id)
                   .outerjoin(Subject, Exam.subject_id == Subject.id)
                   .filter(Result.student_id == student.id)
                   .order_by(Exam.exam_date).all())

    attendances = Attendance.query.filter_by(student_id=student.id).all()
    total_att = len(attendances)
    present_att = sum(1 for a in attendances if a.status == 'present')
    att_pct = round((present_att / total_att * 100), 1) if total_att else 0

    avg_gpa = db.session.query(func.avg(Result.gpa))\
        .filter(Result.student_id == student.id, Result.gpa > 0).scalar()
    avg_gpa = round(float(avg_gpa), 2) if avg_gpa else 0.0

    from datetime import datetime as _dt
    return render_template('admin/student_report_card.html',
                           student=student, student_user=student_user, cls=cls,
                           all_results=all_results,
                           total_att=total_att, present_att=present_att, att_pct=att_pct,
                           avg_gpa=avg_gpa, now=_dt.now())


# ------------------------------------------------------------

@admin_bp.route('/leave-requests')
@login_required
@admin_required
def leave_requests():
    pending = (LeaveRequest.query
               .join(User, LeaveRequest.user_id == User.id)
               .filter(LeaveRequest.status == 'pending')
               .order_by(LeaveRequest.created_at.desc()).all())
    all_requests = (LeaveRequest.query
                    .join(User, LeaveRequest.user_id == User.id)
                    .order_by(LeaveRequest.created_at.desc())
                    .limit(100).all())
    return render_template('admin/leave_requests.html',
                           pending=pending, all_requests=all_requests)


@admin_bp.route('/leave-requests/<int:lid>/approve', methods=['POST'])
@login_required
@admin_required
def approve_leave(lid):
    lr = db.session.get(LeaveRequest, lid)
    if not lr:
        flash('Leave request not found.', 'danger')
        return redirect(url_for('admin.leave_requests'))
    lr.status = 'approved'
    lr.reviewed_by = current_user.id
    lr.reviewed_at = datetime.utcnow()
    lr.review_comment = request.form.get('comment', '')
    # Notify the requester
    notif = Notification(
        user_id=lr.user_id,
        title='Leave Request Approved',
        message=f'Your leave request from {lr.from_date} to {lr.to_date} has been approved.',
        notif_type='success',
        link=url_for('student.leave_requests') if lr.requester.role == 'student' else url_for('teacher.leave_requests')
    )
    db.session.add(notif)
    db.session.commit()
    flash('Leave request approved.', 'success')
    return redirect(url_for('admin.leave_requests'))


@admin_bp.route('/leave-requests/<int:lid>/reject', methods=['POST'])
@login_required
@admin_required
def reject_leave(lid):
    lr = db.session.get(LeaveRequest, lid)
    if not lr:
        flash('Leave request not found.', 'danger')
        return redirect(url_for('admin.leave_requests'))
    lr.status = 'rejected'
    lr.reviewed_by = current_user.id
    lr.reviewed_at = datetime.utcnow()
    lr.review_comment = request.form.get('comment', '')
    notif = Notification(
        user_id=lr.user_id,
        title='Leave Request Rejected',
        message=f'Your leave request from {lr.from_date} to {lr.to_date} has been rejected. '
                f'Reason: {lr.review_comment or "Not specified"}',
        notif_type='danger',
        link=url_for('student.leave_requests') if lr.requester.role == 'student' else url_for('teacher.leave_requests')
    )
    db.session.add(notif)
    db.session.commit()
    flash('Leave request rejected.', 'warning')
    return redirect(url_for('admin.leave_requests'))


# ------------------------------------------------------------

@admin_bp.route('/events')
@login_required
@admin_required
def events():
    upcoming = (Event.query
                .filter(Event.event_date >= date.today(), Event.is_active == True)
                .order_by(Event.event_date.asc()).all())
    past = (Event.query
            .filter(Event.event_date < date.today(), Event.is_active == True)
            .order_by(Event.event_date.desc()).limit(30).all())
    return render_template('admin/events.html', upcoming=upcoming, past=past)


@admin_bp.route('/events/add', methods=['POST'])
@login_required
@admin_required
def add_event():
    title = request.form.get('title', '').strip()
    if not title:
        flash('Event title is required.', 'danger')
        return redirect(url_for('admin.events'))
    ev = Event(
        title=title,
        description=request.form.get('description', ''),
        event_date=datetime.strptime(request.form['event_date'], '%Y-%m-%d').date(),
        end_date=datetime.strptime(request.form['end_date'], '%Y-%m-%d').date() if request.form.get('end_date') else None,
        event_type=request.form.get('event_type', 'general'),
        target_role=request.form.get('target_role', 'all'),
        location=request.form.get('location', ''),
        created_by=current_user.id
    )
    db.session.add(ev)
    db.session.commit()
    flash('Event added successfully.', 'success')
    return redirect(url_for('admin.events'))


@admin_bp.route('/events/<int:eid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_event(eid):
    ev = db.get_or_404(Event, eid)
    ev.is_active = False
    db.session.commit()
    flash('Event removed.', 'success')
    return redirect(url_for('admin.events'))


# ------------------------------------------------------------

@admin_bp.route('/notifications')
@login_required
@admin_required
def notifications():
    notifs = (Notification.query
              .filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc()).limit(50).all())
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('admin/notifications.html', notifs=notifs)


@admin_bp.route('/notifications/count')
@login_required
@admin_required
def notif_count():
    from flask import jsonify
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})
