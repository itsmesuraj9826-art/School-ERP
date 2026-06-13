from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from models import db, Student, User, Class, Subject, Attendance, Exam, Result, Fee, Notice, Assignment, TimeTable, LeaveRequest, Event, Notification
from datetime import datetime, date
from sqlalchemy import func

student_bp = Blueprint('student', __name__)

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            flash('Access denied. Student privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated


def get_student():
    """Get the student profile for the current user"""
    return Student.query.filter_by(user_id=current_user.id).first()


def parse_date(date_string):
    """Safely parse a date string"""
    return datetime.strptime(date_string, '%Y-%m-%d').date() if date_string else None


# ============================================================================
# DASHBOARD
# ============================================================================

@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    student = get_student()
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.logout'))

    # Attendance statistics
    attendances = Attendance.query.filter_by(student_id=student.id).all()
    total_att = len(attendances)
    present_att = sum(1 for a in attendances if a.status == 'present')
    attendance_pct = round((present_att / total_att * 100), 1) if total_att else 0

    # Results
    results = db.session.query(Result, Exam, Subject) \
        .join(Exam, Result.exam_id == Exam.id) \
        .outerjoin(Subject, Exam.subject_id == Subject.id) \
        .filter(Result.student_id == student.id) \
        .order_by(Exam.exam_date.desc()).limit(6).all()

    avg_marks = db.session.query(func.avg(Result.marks_obtained)) \
        .filter(Result.student_id == student.id).scalar()
    avg_marks = round(float(avg_marks), 1) if avg_marks else 0

    avg_gpa = db.session.query(func.avg(Result.gpa)) \
        .filter(Result.student_id == student.id, Result.gpa > 0).scalar()
    avg_gpa = round(float(avg_gpa), 2) if avg_gpa else 0.0

    # Fees
    fees = Fee.query.filter_by(student_id=student.id).order_by(Fee.due_date.desc()).all()
    pending_fees = sum(f.amount for f in fees if f.status in ('pending', 'overdue'))
    pending_fee_count = sum(1 for f in fees if f.status in ('pending', 'overdue'))

    # Today's timetable
    today = date.today()
    today_name = today.strftime('%A')
    day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6}
    today_num = day_map.get(today_name, 0)

    timetable_today = []
    if student.class_id:
        timetable_today = db.session.query(TimeTable, Subject) \
            .outerjoin(Subject, TimeTable.subject_id == Subject.id) \
            .filter(TimeTable.class_id == student.class_id, TimeTable.day_of_week == today_num) \
            .order_by(TimeTable.start_time).all()

    # Assignments
    assignments = []
    if student.class_id:
        assignments = Assignment.query.filter_by(class_id=student.class_id, status='active') \
            .filter(Assignment.due_date >= today) \
            .order_by(Assignment.due_date).limit(5).all()

    # Notices
    notices = Notice.query.filter(
        Notice.is_active == True,
        db.or_(Notice.target_role == 'all', Notice.target_role == 'student')
    ).order_by(Notice.created_at.desc()).limit(5).all()

    # Upcoming exams
    upcoming_exams = []
    if student.class_id:
        upcoming_exams = Exam.query.filter(
            Exam.class_id == student.class_id,
            Exam.exam_date >= today
        ).order_by(Exam.exam_date).limit(5).all()

    return render_template('student/dashboard.html',
                           student=student,
                           attendance_pct=attendance_pct,
                           present_att=present_att,
                           total_att=total_att,
                           results=results,
                           avg_marks=avg_marks,
                           avg_gpa=avg_gpa,
                           fees=fees,
                           pending_fees=pending_fees,
                           pending_fee_count=pending_fee_count,
                           timetable_today=timetable_today,
                           assignments=assignments,
                           notices=notices,
                           upcoming_exams=upcoming_exams
                           )


# ============================================================================
# RESULTS
# ============================================================================

@student_bp.route('/results')
@login_required
@student_required
def results():
    student = get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    exam_type_filter = request.args.get('exam_type', '')

    query = db.session.query(Result, Exam, Subject) \
        .join(Exam, Result.exam_id == Exam.id) \
        .outerjoin(Subject, Exam.subject_id == Subject.id) \
        .filter(Result.student_id == student.id)

    if exam_type_filter:
        query = query.filter(Exam.exam_type == exam_type_filter)

    all_results = query.order_by(Exam.exam_date.desc()).all()

    avg_gpa = db.session.query(func.avg(Result.gpa)) \
        .filter(Result.student_id == student.id, Result.gpa > 0).scalar()
    avg_gpa = round(float(avg_gpa), 2) if avg_gpa else 0.0

    total_results = len(all_results)
    passed = sum(1 for r, e, s in all_results if r.grade not in ('F', None, ''))

    exam_types = [
        ('unit_test', 'Unit Test'),
        ('first_terminal', 'First Terminal'),
        ('mid_term', 'Mid-Term'),
        ('pre_board', 'Pre-Board'),
        ('final_board', 'Final / Board'),
        ('internal', 'Internal'),
        ('practical', 'Practical'),
    ]

    return render_template('student/results.html',
                           student=student,
                           all_results=all_results,
                           avg_gpa=avg_gpa,
                           total_results=total_results,
                           passed=passed,
                           exam_type_filter=exam_type_filter,
                           exam_types=exam_types
                           )


# ============================================================================
# TIMETABLE
# ============================================================================

@student_bp.route('/timetable')
@login_required
@student_required
def timetable():
    student = get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    timetable_data = {}
    if student.class_id:
        entries = db.session.query(TimeTable, Subject) \
            .outerjoin(Subject, TimeTable.subject_id == Subject.id) \
            .filter(TimeTable.class_id == student.class_id) \
            .order_by(TimeTable.day_of_week, TimeTable.start_time).all()

        for tt, subj in entries:
            day = tt.day_of_week
            if day not in timetable_data:
                timetable_data[day] = []
            timetable_data[day].append((tt, subj))

    return render_template('student/timetable.html',
                           student=student,
                           timetable_data=timetable_data,
                           days=DAYS
                           )


# ============================================================================
# ASSIGNMENTS
# ============================================================================

@student_bp.route('/assignments')
@login_required
@student_required
def assignments():
    student = get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    today = date.today()
    status_filter = request.args.get('status', 'active')

    query = Assignment.query
    if student.class_id:
        query = query.filter_by(class_id=student.class_id)

    if status_filter == 'active':
        query = query.filter(Assignment.due_date >= today, Assignment.status == 'active')
    elif status_filter == 'overdue':
        query = query.filter(Assignment.due_date < today, Assignment.status == 'active')
    elif status_filter == 'submitted':
        query = query.filter(Assignment.status == 'submitted')

    assignments_list = query.order_by(Assignment.due_date).all()

    return render_template('student/assignments.html',
                           student=student,
                           assignments_list=assignments_list,
                           today=today,
                           status_filter=status_filter
                           )


# ============================================================================
# ATTENDANCE
# ============================================================================

@student_bp.route('/attendance')
@login_required
@student_required
def attendance():
    student = get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    all_att = Attendance.query.filter_by(student_id=student.id) \
        .order_by(Attendance.date.desc()).all()

    total = len(all_att)
    present = sum(1 for a in all_att if a.status == 'present')
    absent = sum(1 for a in all_att if a.status == 'absent')
    late = sum(1 for a in all_att if a.status == 'late')
    pct = round((present / total * 100), 1) if total else 0

    # Group by month
    monthly = {}
    for a in all_att:
        key = a.date.strftime('%B %Y')
        if key not in monthly:
            monthly[key] = {'present': 0, 'absent': 0, 'late': 0, 'total': 0}
        monthly[key][a.status] = monthly[key].get(a.status, 0) + 1
        monthly[key]['total'] += 1

    return render_template('student/attendance.html',
                           student=student,
                           all_att=all_att[:60],
                           total=total,
                           present=present,
                           absent=absent,
                           late=late,
                           pct=pct,
                           monthly=monthly
                           )


# ============================================================================
# FEES
# ============================================================================

@student_bp.route('/fees')
@login_required
@student_required
def fees():
    student = get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    fees_list = Fee.query.filter_by(student_id=student.id).order_by(Fee.due_date.desc()).all()
    total_paid = sum(f.amount for f in fees_list if f.status == 'paid')
    total_pending = sum(f.amount for f in fees_list if f.status in ('pending', 'overdue'))

    return render_template('student/fees.html',
                           student=student,
                           fees_list=fees_list,
                           total_paid=total_paid,
                           total_pending=total_pending
                           )


# ============================================================================
# PROFILE
# ============================================================================

@student_bp.route('/profile')
@login_required
@student_required
def profile():
    student = get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    user = current_user
    cls = db.session.get(Class, student.class_id) if student.class_id else None

    return render_template('student/profile.html',
                           student=student,
                           user=user,
                           cls=cls
                           )


# ============================================================================
# SETTINGS
# ============================================================================

@student_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@student_required
def settings():
    """Student settings page"""
    student = get_student()
    user = current_user

    if request.method == 'POST':
        # Update profile settings
        user.phone = request.form.get('phone')
        student.address = request.form.get('address')
        student.guardian_name = request.form.get('guardian_name')
        student.guardian_phone = request.form.get('guardian_phone')
        student.blood_group = request.form.get('blood_group')

        if request.form.get('date_of_birth'):
            student.date_of_birth = parse_date(request.form['date_of_birth'])

        # Handle password change
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if current_password and new_password:
            if user.check_password(current_password):
                if new_password == confirm_password:
                    user.set_password(new_password)
                    db.session.commit()
                    flash('Password changed successfully! Please login again.', 'success')
                    return redirect(url_for('auth.logout'))
                else:
                    flash('New passwords do not match!', 'danger')
                    return redirect(url_for('student.settings'))
            else:
                flash('Current password is incorrect!', 'danger')
                return redirect(url_for('student.settings'))

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.settings'))

    cls = db.session.get(Class, student.class_id) if student.class_id else None

    return render_template('student/settings.html',
                           student=student,
                           user=user,
                                                  cls=cls)


# ============================================================================
# REPORT CARD
# ============================================================================

@student_bp.route('/report-card')
@login_required
@student_required
def report_card():
    student = get_student()
    if not student:
        return redirect(url_for('auth.logout'))

    student_user = current_user
    cls = db.session.get(Class, student.class_id) if student.class_id else None

    all_results = db.session.query(Result, Exam, Subject) \
        .join(Exam, Result.exam_id == Exam.id) \
        .outerjoin(Subject, Exam.subject_id == Subject.id) \
        .filter(Result.student_id == student.id) \
        .order_by(Exam.exam_date).all()

    attendances = Attendance.query.filter_by(student_id=student.id).all()
    total_att = len(attendances)
    present_att = sum(1 for a in attendances if a.status == 'present')
    att_pct = round((present_att / total_att * 100), 1) if total_att else 0

    avg_gpa = db.session.query(func.avg(Result.gpa)) \
        .filter(Result.student_id == student.id, Result.gpa > 0).scalar()
    avg_gpa = round(float(avg_gpa), 2) if avg_gpa else 0.0

    from datetime import datetime as _dt
    return render_template('student/report_card.html',
                           student=student, student_user=student_user, cls=cls,
                           all_results=all_results,
                           total_att=total_att, present_att=present_att, att_pct=att_pct,
                           avg_gpa=avg_gpa, now=_dt.now())


# ── LEAVE REQUESTS ────────────────────────────────────────────────────────────

@student_bp.route('/leave-requests', methods=['GET', 'POST'])
@login_required
@student_required
def leave_requests():
    if request.method == 'POST':
        from_date = datetime.strptime(request.form['from_date'], '%Y-%m-%d').date()
        to_date = datetime.strptime(request.form['to_date'], '%Y-%m-%d').date()
        if to_date < from_date:
            flash('End date cannot be before start date.', 'danger')
            return redirect(url_for('student.leave_requests'))
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
        return redirect(url_for('student.leave_requests'))

    my_requests = (LeaveRequest.query
                   .filter_by(user_id=current_user.id)
                   .order_by(LeaveRequest.created_at.desc()).all())
    return render_template('student/leave_requests.html', my_requests=my_requests)


# ── EVENTS ────────────────────────────────────────────────────────────────────

@student_bp.route('/events')
@login_required
@student_required
def events():
    upcoming = (Event.query
                .filter(Event.event_date >= date.today(), Event.is_active == True,
                        Event.target_role.in_(['all', 'student']))
                .order_by(Event.event_date.asc()).all())
    past = (Event.query
            .filter(Event.event_date < date.today(), Event.is_active == True,
                    Event.target_role.in_(['all', 'student']))
            .order_by(Event.event_date.desc()).limit(20).all())
    return render_template('student/events.html', upcoming=upcoming, past=past)


# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────

@student_bp.route('/notifications')
@login_required
@student_required
def notifications():
    notifs = (Notification.query
              .filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc()).limit(50).all())
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('student/notifications.html', notifs=notifs)