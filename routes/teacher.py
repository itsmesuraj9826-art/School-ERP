# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, Teacher, Student, User, Class, Subject, Attendance, Assignment, Exam, Result, Notice, TimeTable, Parent, LeaveRequest, Event, Notification
from datetime import datetime, date
from sqlalchemy import func
from app import mail
from utils.mail_helpers import send_attendance_notification, send_assignment_notification

teacher_bp = Blueprint('teacher', __name__)

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            flash('Access denied.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def get_teacher():
    return Teacher.query.filter_by(user_id=current_user.id).first()

# ------------------------------------------------------------

@teacher_bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    teacher = get_teacher()
    if not teacher:
        flash('Teacher profile not found.', 'danger')
        return redirect(url_for('auth.logout'))

    my_classes = Class.query.filter_by(class_teacher_id=teacher.id).all()
    my_subjects = Subject.query.filter_by(teacher_id=teacher.id).all()

    today = date.today()
    today_name = today.strftime('%A')
    day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
    today_num = day_map.get(today_name, 0)

    todays_classes = db.session.query(TimeTable, Class, Subject)\
        .join(Class, TimeTable.class_id == Class.id)\
        .outerjoin(Subject, TimeTable.subject_id == Subject.id)\
        .filter(TimeTable.teacher_id == teacher.id, TimeTable.day_of_week == today_num)\
        .order_by(TimeTable.start_time).all()

    pending_assignments = Assignment.query.filter_by(
        teacher_id=teacher.id, status='active'
    ).filter(Assignment.due_date >= today).count()

    upcoming_exams = Exam.query.join(Class).filter(
        Class.class_teacher_id == teacher.id,
        Exam.exam_date >= today
    ).order_by(Exam.exam_date).limit(5).all()

    recent_notices = Notice.query.filter(
        Notice.is_active == True,
        db.or_(Notice.target_role == 'all', Notice.target_role == 'teacher')
    ).order_by(Notice.created_at.desc()).limit(5).all()

    class_ids = [c.id for c in my_classes]
    total_students = Student.query.filter(Student.class_id.in_(class_ids)).count() if class_ids else 0

    return render_template('teacher/dashboard.html',
        teacher=teacher,
        my_classes=my_classes,
        my_subjects=my_subjects,
        todays_classes=todays_classes,
        pending_assignments=pending_assignments,
        upcoming_exams=upcoming_exams,
        recent_notices=recent_notices,
        total_students=total_students,
        today=today
    )


# ============================================================================
# PROFILE & SETTINGS
# ============================================================================

@teacher_bp.route('/my-profile')
@login_required
@teacher_required
def my_profile():
    """Teacher's own profile view"""
    teacher = get_teacher()
    user = current_user
    subjects = Subject.query.filter_by(teacher_id=teacher.id).all()
    classes = Class.query.filter_by(class_teacher_id=teacher.id).all()

    return render_template('teacher/my_profile.html',
                           teacher=teacher,
                           user=user,
                           subjects=subjects,
                           classes=classes)


@teacher_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@teacher_required
def settings():
    """Teacher settings page"""
    teacher = get_teacher()
    user = current_user

    if request.method == 'POST':
        # Update profile settings
        user.phone = request.form.get('phone')
        teacher.address = request.form.get('address')
        teacher.emergency_contact = request.form.get('emergency_contact')
        teacher.date_of_birth = parse_date(request.form.get('date_of_birth')) if request.form.get(
            'date_of_birth') else teacher.date_of_birth
        teacher.blood_group = request.form.get('blood_group')

        # Handle password change
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if current_password and new_password:
            if user.check_password(current_password):
                if new_password == confirm_password:
                    user.set_password(new_password)
                    flash('Password changed successfully!', 'success')
                else:
                    flash('New passwords do not match!', 'danger')
                    return redirect(url_for('teacher.settings'))
            else:
                flash('Current password is incorrect!', 'danger')
                return redirect(url_for('teacher.settings'))

        # Handle profile picture upload
        if 'profile_image' in request.files and request.files['profile_image'].filename:
            from utils.file_helpers import save_teacher_file, delete_teacher_file
            if teacher.profile_image and teacher.profile_image != 'default_teacher.png':
                delete_teacher_file(teacher.profile_image)
            teacher.profile_image = save_teacher_file(request.files['profile_image'], teacher.id, 'profile')
            flash('Profile picture updated!', 'success')

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('teacher.settings'))

    return render_template('teacher/settings.html', teacher=teacher, user=user)


# ------------------------------------------------------------

@teacher_bp.route('/attendance', methods=['GET', 'POST'])
@login_required
@teacher_required
def attendance():
    teacher = get_teacher()

    all_class_ids = db.session.query(TimeTable.class_id)\
        .filter(TimeTable.teacher_id == teacher.id).distinct().all()
    all_class_ids = [c[0] for c in all_class_ids]

    my_classes = Class.query.filter(
        db.or_(
            Class.class_teacher_id == teacher.id,
            Class.id.in_(all_class_ids)
        )
    ).all()

    selected_class_id = request.args.get('class_id', type=int)
    selected_date = request.args.get('date', date.today().isoformat())

    students = []
    existing_attendance = {}

    if selected_class_id:
        students_data = db.session.query(Student, User)\
            .join(User, Student.user_id == User.id)\
            .filter(Student.class_id == selected_class_id, Student.status == 'active')\
            .order_by(Student.roll_no).all()

        att_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        existing = Attendance.query.filter_by(class_id=selected_class_id, date=att_date).all()
        existing_attendance = {a.student_id: a.status for a in existing}
        students = students_data

    if request.method == 'POST':
        att_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        class_id = int(request.form['class_id'])
        cls = db.session.get(Class, class_id)
        class_name = cls.full_name if cls else ""

        student_ids = request.form.getlist('student_ids')
        saved = 0
        notify_count = 0
        for sid in student_ids:
            sid = int(sid)
            status = request.form.get(f'status_{sid}', 'absent')
            old_status = None
            existing = Attendance.query.filter_by(student_id=sid, date=att_date).first()
            if existing:
                old_status = existing.status
                existing.status = status
            else:
                att = Attendance(student_id=sid, class_id=class_id, date=att_date,
                                 status=status, marked_by=teacher.id)
                db.session.add(att)
            saved += 1

            # Send parent notification if student is absent or late (and status changed)
            if status in ('absent', 'late') and old_status != status:
                student = db.session.get(Student, sid)
                if student and student.parents:
                    student_user = db.session.get(User, student.user_id)
                    student_name = student_user.full_name if student_user else f"Roll {student.roll_no}"
                    for parent in student.parents:
                        parent_user = db.session.get(User, parent.user_id)
                        if parent_user and parent_user.email:
                            try:
                                send_attendance_notification(
                                    mail, parent_user.email, parent_user.full_name,
                                    student_name, att_date, status, class_name
                                )
                                notify_count += 1
                            except Exception:
                                pass

        db.session.commit()
        msg = f'Attendance saved for {saved} students!'
        if notify_count:
            msg += f' {notify_count} parent notification(s) sent.'
        flash(msg, 'success')
        return redirect(url_for('teacher.attendance', class_id=class_id, date=att_date.isoformat()))

    return render_template('teacher/attendance.html',
        my_classes=my_classes,
        students=students,
        existing_attendance=existing_attendance,
        selected_class_id=selected_class_id,
        selected_date=selected_date
    )

# ------------------------------------------------------------

@teacher_bp.route('/students')
@login_required
@teacher_required
def students():
    teacher = get_teacher()
    class_filter = request.args.get('class_id', '', type=str)
    search = request.args.get('search', '')

    all_class_ids_q = db.session.query(TimeTable.class_id)\
        .filter(TimeTable.teacher_id == teacher.id).distinct().all()
    all_class_ids = [c[0] for c in all_class_ids_q]

    my_class_ids = list(set(
        [c.id for c in Class.query.filter_by(class_teacher_id=teacher.id).all()] + all_class_ids
    ))

    my_classes = Class.query.filter(Class.id.in_(my_class_ids)).order_by(Class.name, Class.section).all()

    query = db.session.query(Student, User, Class)\
        .join(User, Student.user_id == User.id)\
        .outerjoin(Class, Student.class_id == Class.id)\
        .filter(Student.class_id.in_(my_class_ids), Student.status == 'active')

    if class_filter:
        query = query.filter(Student.class_id == class_filter)
    if search:
        query = query.filter(
            db.or_(User.full_name.ilike(f'%{search}%'), Student.roll_no.ilike(f'%{search}%'))
        )

    students_data = query.order_by(Class.name, Student.roll_no).all()

    return render_template('teacher/students.html',
        students_data=students_data,
        my_classes=my_classes,
        class_filter=class_filter,
        search=search
    )

# ------------------------------------------------------------

@teacher_bp.route('/timetable')
@login_required
@teacher_required
def timetable():
    teacher = get_teacher()
    timetable_data = {}

    entries = db.session.query(TimeTable, Class, Subject)\
        .join(Class, TimeTable.class_id == Class.id)\
        .outerjoin(Subject, TimeTable.subject_id == Subject.id)\
        .filter(TimeTable.teacher_id == teacher.id)\
        .order_by(TimeTable.day_of_week, TimeTable.start_time).all()

    for tt, cls, subj in entries:
        day = tt.day_of_week
        if day not in timetable_data:
            timetable_data[day] = []
        timetable_data[day].append((tt, cls, subj))

    return render_template('teacher/timetable.html',
        timetable_data=timetable_data,
        days=DAYS,
        teacher=teacher
    )

# ------------------------------------------------------------

@teacher_bp.route('/marks')
@login_required
@teacher_required
def marks():
    teacher = get_teacher()

    all_class_ids_q = db.session.query(TimeTable.class_id)\
        .filter(TimeTable.teacher_id == teacher.id).distinct().all()
    all_class_ids = [c[0] for c in all_class_ids_q]
    my_class_ids = list(set(
        [c.id for c in Class.query.filter_by(class_teacher_id=teacher.id).all()] + all_class_ids
    ))

    exams_list = Exam.query.filter(Exam.class_id.in_(my_class_ids))\
        .order_by(Exam.exam_date.desc()).all()

    exam_summary = []
    for exam in exams_list:
        total = Student.query.filter_by(class_id=exam.class_id, status='active').count() if exam.class_id else 0
        entered = Result.query.filter_by(exam_id=exam.id).count()
        exam_summary.append({'exam': exam, 'total': total, 'entered': entered})

    return render_template('teacher/marks.html', exam_summary=exam_summary)

@teacher_bp.route('/marks/<int:eid>', methods=['GET', 'POST'])
@login_required
@teacher_required
def enter_marks(eid):
    teacher = get_teacher()
    exam = Exam.query.get_or_404(eid)

    if exam.class_id:
        students_data = db.session.query(Student, User)\
            .join(User, Student.user_id == User.id)\
            .filter(Student.class_id == exam.class_id, Student.status == 'active')\
            .order_by(Student.roll_no).all()
    else:
        students_data = []

    existing = {r.student_id: r for r in Result.query.filter_by(exam_id=eid).all()}

    if request.method == 'POST':
        try:
            for student, _ in students_data:
                marks_val = float(request.form.get(f'marks_{student.id}', 0) or 0)
                practical = float(request.form.get(f'practical_{student.id}', 0) or 0)
                is_absent = f'absent_{student.id}' in request.form

                pct = (marks_val / exam.max_marks * 100) if exam.max_marks else 0
                grade, gpa = Result.calculate_neb_grade(pct)

                if student.id in existing:
                    r = existing[student.id]
                    r.marks_obtained = marks_val
                    r.practical_marks = practical
                    r.is_absent = is_absent
                    r.grade = grade
                    r.gpa = gpa
                else:
                    r = Result(
                        student_id=student.id, exam_id=eid,
                        marks_obtained=marks_val, practical_marks=practical,
                        is_absent=is_absent, grade=grade, gpa=gpa
                    )
                    db.session.add(r)

            db.session.commit()
            flash('Marks saved successfully!', 'success')
            return redirect(url_for('teacher.marks'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')

    return render_template('teacher/enter_marks.html',
        exam=exam, students_data=students_data, existing=existing)

# ------------------------------------------------------------

@teacher_bp.route('/assignments')
@login_required
@teacher_required
def assignments():
    teacher = get_teacher()
    assignments_data = Assignment.query.filter_by(teacher_id=teacher.id)\
        .order_by(Assignment.created_at.desc()).all()

    all_class_ids_q = db.session.query(TimeTable.class_id)\
        .filter(TimeTable.teacher_id == teacher.id).distinct().all()
    all_class_ids = [c[0] for c in all_class_ids_q]
    my_class_ids = list(set(
        [c.id for c in Class.query.filter_by(class_teacher_id=teacher.id).all()] + all_class_ids
    ))

    my_classes = Class.query.filter(Class.id.in_(my_class_ids)).order_by(Class.name).all()
    my_subjects = Subject.query.filter_by(teacher_id=teacher.id).all()

    return render_template('teacher/assignments.html',
        assignments_data=assignments_data,
        my_classes=my_classes,
        my_subjects=my_subjects,
        today=date.today()
    )


@teacher_bp.route('/assignments/add', methods=['POST'])
@login_required
@teacher_required
def add_assignment():
    teacher = get_teacher()
    class_id = int(request.form['class_id'])
    subject_id = request.form.get('subject_id') or None
    due_date_str = request.form.get('due_date')
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else None

    asgn = Assignment(
        teacher_id=teacher.id,
        class_id=class_id,
        subject_id=int(subject_id) if subject_id else None,
        title=request.form['title'],
        description=request.form.get('description', ''),
        due_date=due_date,
        max_marks=int(request.form.get('max_marks', 10))
    )
    db.session.add(asgn)
    db.session.commit()

    # Notify parents of students in this class
    subject = db.session.get(Subject, int(subject_id)) if subject_id else None
    cls = db.session.get(Class, class_id)
    students = Student.query.filter_by(class_id=class_id, status='active').all()
    notify_count = 0
    for student in students:
        student_user = db.session.get(User, student.user_id)
        for parent in student.parents:
            parent_user = db.session.get(User, parent.user_id)
            if parent_user and parent_user.email:
                try:
                    send_assignment_notification(
                        mail, parent_user.email, parent_user.full_name,
                        student_user.full_name if student_user else student.roll_no,
                        asgn.title,
                        subject.name if subject else 'N/A',
                        due_date,
                        cls.full_name if cls else ''
                    )
                    notify_count += 1
                except Exception:
                    pass

    flash(f'Assignment posted! {notify_count} parent(s) notified.', 'success')
    return redirect(url_for('teacher.assignments'))


@teacher_bp.route('/assignments/<int:aid>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_assignment(aid):
    a = Assignment.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    flash('Assignment deleted.', 'success')
    return redire

# ------------------------------------------------------------

@teacher_bp.route('/leave-requests', methods=['GET', 'POST'])
@login_required
@teacher_required
def leave_requests():
    if request.method == 'POST':
        from_date = datetime.strptime(request.form['from_date'], '%Y-%m-%d').date()
        to_date = datetime.strptime(request.form['to_date'], '%Y-%m-%d').date()
        if to_date < from_date:
            flash('End date cannot be before start date.', 'danger')
            return redirect(url_for('teacher.leave_requests'))
        lr = LeaveRequest(
            user_id=current_user.id,
            leave_type=request.form.get('leave_type', 'sick'),
            from_date=from_date,
            to_date=to_date,
            reason=request.form.get('reason', '').strip()
        )
        db.session.add(lr)
        db.session.commit()
        flash('Leave request submitted.', 'success')
        return redirect(url_for('teacher.leave_requests'))

    my_requests = (LeaveRequest.query
                   .filter_by(user_id=current_user.id)
                   .order_by(LeaveRequest.created_at.desc()).all())
    return render_template('teacher/leave_requests.html', my_requests=my_requests)


# ------------------------------------------------------------

@teacher_bp.route('/events')
@login_required
@teacher_required
def events():
    upcoming = (Event.query
                .filter(Event.event_date >= date.today(), Event.is_active == True,
                        Event.target_role.in_(['all', 'teacher']))
                .order_by(Event.event_date.asc()).all())
    past = (Event.query
            .filter(Event.event_date < date.today(), Event.is_active == True,
                    Event.target_role.in_(['all', 'teacher']))
            .order_by(Event.event_date.desc()).limit(20).all())
    return render_template('teacher/events.html', upcoming=upcoming, past=past)


# ------------------------------------------------------------

@teacher_bp.route('/notifications')
@login_required
@teacher_required
def notifications():
    notifs = (Notification.query
              .filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc()).limit(50).all())
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('teacher/notifications.html', notifs=notifs)
