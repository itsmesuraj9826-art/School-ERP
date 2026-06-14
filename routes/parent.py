from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from models import db, Parent, Student, User, Attendance, Result, Exam, Fee, Notice, Subject, Assignment, TimeTable, LeaveRequest, Event, Notification
from datetime import datetime, date
from sqlalchemy import func

parent_bp = Blueprint('parent', __name__)

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

def parent_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'parent':
            flash('Access denied.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def get_parent():
    return Parent.query.filter_by(user_id=current_user.id).first()

@parent_bp.route('/dashboard')
@login_required
@parent_required
def dashboard():
    parent = get_parent()
    if not parent or not parent.child:
        flash('Parent profile not linked to a student.', 'warning')
        return redirect(url_for('auth.logout'))

    student = parent.child
    student_user = db.session.get(User, student.user_id)

    attendances = Attendance.query.filter_by(student_id=student.id).all()
    total_att = len(attendances)
    present_att = sum(1 for a in attendances if a.status == 'present')
    attendance_pct = round((present_att / total_att * 100), 1) if total_att else 0

    recent_results = db.session.query(Result, Exam, Subject)\
        .join(Exam, Result.exam_id == Exam.id)\
        .outerjoin(Subject, Exam.subject_id == Subject.id)\
        .filter(Result.student_id == student.id)\
        .order_by(Exam.exam_date.desc()).limit(8).all()

    avg_marks = db.session.query(func.avg(Result.marks_obtained))\
        .filter(Result.student_id == student.id).scalar()
    avg_marks = round(float(avg_marks), 1) if avg_marks else 0

    avg_gpa = db.session.query(func.avg(Result.gpa))\
        .filter(Result.student_id == student.id, Result.gpa > 0).scalar()
    avg_gpa = round(float(avg_gpa), 2) if avg_gpa else 0.0

    fees = Fee.query.filter_by(student_id=student.id).order_by(Fee.due_date.desc()).all()
    pending_fees = sum(f.amount for f in fees if f.status in ('pending', 'overdue'))
    total_paid = sum(f.amount for f in fees if f.status == 'paid')

    today = date.today()
    notices = Notice.query.filter(
        Notice.is_active == True,
        db.or_(Notice.target_role == 'all', Notice.target_role == 'parent')
    ).order_by(Notice.created_at.desc()).limit(6).all()

    recent_attendance = Attendance.query.filter_by(student_id=student.id)\
        .order_by(Attendance.date.desc()).limit(15).all()

    today_name = today.strftime('%A')
    day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4, 'Saturday': 5}
    today_num = day_map.get(today_name, 0)

    timetable_today = []
    if student.class_id:
        timetable_today = db.session.query(TimeTable, Subject)\
            .outerjoin(Subject, TimeTable.subject_id == Subject.id)\
            .filter(TimeTable.class_id == student.class_id, TimeTable.day_of_week == today_num)\
            .order_by(TimeTable.start_time).all()

    upcoming_assignments = []
    if student.class_id:
        upcoming_assignments = Assignment.query.filter_by(class_id=student.class_id, status='active')\
            .filter(Assignment.due_date >= today).order_by(Assignment.due_date).limit(5).all()

    all_events = Event.query.filter(
        db.or_(Event.target_role == 'all', Event.target_role == 'parent', Event.target_role == 'student')
    ).order_by(Event.event_date).all()

    full_timetable = []
    if student.class_id:
        full_timetable = db.session.query(TimeTable, Subject)\
            .outerjoin(Subject, TimeTable.subject_id == Subject.id)\
            .filter(TimeTable.class_id == student.class_id)\
            .order_by(TimeTable.day_of_week, TimeTable.start_time).all()

    hour = datetime.now().hour
    if hour < 12:
        greeting = 'Good Morning'
    elif hour < 17:
        greeting = 'Good Afternoon'
    else:
        greeting = 'Good Evening'

    return render_template('parent/dashboard.html',
        parent=parent,
        student=student,
        student_user=student_user,
        attendance_pct=attendance_pct,
        present_att=present_att,
        total_att=total_att,
        recent_results=recent_results,
        avg_marks=avg_marks,
        avg_gpa=avg_gpa,
        fees=fees,
        pending_fees=pending_fees,
        total_paid=total_paid,
        notices=notices,
        recent_attendance=recent_attendance,
        all_attendance=attendances,
        timetable_today=timetable_today,
        full_timetable=full_timetable,
        upcoming_assignments=upcoming_assignments,
        all_events=all_events,
        today=today,
        greeting=greeting
    )


from models import Message
from app import mail

@parent_bp.route('/messages')
@login_required
@parent_required
def messages():
    received = (Message.query
                .filter_by(recipient_id=current_user.id)
                .order_by(Message.sent_at.desc()).all())
    sent = (Message.query
            .filter_by(sender_id=current_user.id)
            .order_by(Message.sent_at.desc()).all())
    unread = sum(1 for m in received if not m.is_read)
    return render_template('parent/messages.html',
                           received=received, sent=sent, unread=unread)


@parent_bp.route('/messages/<int:mid>/read', methods=['POST'])
@login_required
@parent_required
def mark_message_read(mid):
    msg = Message.query.get_or_404(mid)
    if msg.recipient_id == current_user.id:
        msg.is_read = True
        db.session.commit()
    return redirect(url_for('parent.messages'))


@parent_bp.route('/leave-requests')
@login_required
@parent_required
def leave_requests():
    parent = Parent.query.filter_by(user_id=current_user.id).first()
    child_requests = []
    if parent and parent.student_id:
        child = db.session.get(Student, parent.student_id)
        if child:
            child_requests = (LeaveRequest.query
                              .filter_by(user_id=child.user_id)
                              .order_by(LeaveRequest.created_at.desc()).all())
    return render_template('parent/leave_requests.html', child_requests=child_requests)


@parent_bp.route('/events')
@login_required
@parent_required
def events():
    upcoming = Event.query.filter(
        Event.event_date >= date.today(),
        Event.is_active == True,
        Event.target_role.in_(['all', 'parent'])
    ).order_by(Event.event_date.asc()).all()
    past = Event.query.filter(
        Event.event_date < date.today(),
        Event.is_active == True,
        Event.target_role.in_(['all', 'parent'])
    ).order_by(Event.event_date.desc()).limit(20).all()
    return render_template('parent/events.html', upcoming=upcoming, past=past)


@parent_bp.route('/notifications')
@login_required
@parent_required
def notifications():
    notifs = (Notification.query
              .filter_by(user_id=current_user.id)
              .order_by(Notification.created_at.desc()).limit(50).all())
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('parent/notifications.html', notifs=notifs)
