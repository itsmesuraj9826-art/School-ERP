import random
import string
import requests as _requests
from datetime import date as _date
from flask import current_app
from flask_mail import Message


def _nepal_phone(phone):
    """Normalise a Nepal phone number to E.164 (+977XXXXXXXXXX)."""
    phone = ''.join(c for c in (phone or '') if c.isdigit() or c == '+')
    if phone.startswith('+977'):
        return phone
    if phone.startswith('977'):
        return '+' + phone
    if phone.startswith('0'):
        phone = phone[1:]
    return '+977' + phone


def send_whatsapp_credentials(phone, full_name, username, password, student_name=''):
    """
    Send login credentials to a parent via WhatsApp using Twilio.
    Requires in .env:
        TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxx
        TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxx
        TWILIO_WHATSAPP_FROM=+14155238886   (Twilio sandbox number or your approved number)
    """
    try:
        sid   = current_app.config.get('TWILIO_ACCOUNT_SID', '')
        token = current_app.config.get('TWILIO_AUTH_TOKEN', '')
        from_ = current_app.config.get('TWILIO_WHATSAPP_FROM', '')
        if not (sid and token and from_ and phone):
            return False

        to_number = _nepal_phone(phone)
        school = current_app.config.get('SCHOOL_NAME', "Martyrs' Memorial +2 College")
        portal_url = current_app.config.get('SCHOOL_URL', '')

        body = (
            f"Hello {full_name}! 👋\n\n"
            f"Welcome to *{school}* Parent Portal.\n\n"
            f"Your login credentials:\n"
            f"🔑 *Username:* {username}\n"
            f"🔒 *Password:* {password}\n"
        )
        if student_name:
            body += f"👤 *Student:* {student_name}\n"
        if portal_url:
            body += f"\n🌐 Login at: {portal_url}\n"
        body += "\nPlease keep these safe. Contact school admin if you need help."

        resp = _requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={
                'From': f'whatsapp:{from_}',
                'To':   f'whatsapp:{to_number}',
                'Body': body,
            },
            timeout=10
        )
        if resp.status_code in (200, 201):
            current_app.logger.info(f"WhatsApp sent to {to_number}")
            return True
        current_app.logger.warning(f"WhatsApp failed ({resp.status_code}): {resp.text}")
        return False
    except Exception as e:
        current_app.logger.error(f"WhatsApp error: {e}")
        return False


def generate_password(length=10):
    chars = string.ascii_letters + string.digits + "!@#$"
    return ''.join(random.choices(chars, k=length))


def generate_username(role, name, identifier):
    first = name.strip().split()[0].lower()
    if role == 'student':
        return f"s.{identifier.lower()}@tbc.edu.np"
    elif role == 'teacher':
        return f"t.{identifier.lower()}@tbc.edu.np"
    elif role == 'parent':
        return f"p.{identifier.lower()}.{first}@tbc.edu.np"
    return f"{first}.{identifier.lower()}@tbc.edu.np"


def send_credentials_email(mail, recipient_email, full_name, role, username, password, extra_info=""):
    school = current_app.config.get('SCHOOL_NAME', "Martyrs' Memorial College")
    portal_map = {'student': 'Student Portal', 'teacher': 'Teacher Portal', 'parent': 'Parent Portal'}
    portal = portal_map.get(role, 'Portal')

    body = (
        f"Dear {full_name},\n\n"
        f"Welcome to {school}!\n\n"
        f"Your {portal} account has been created. Your login credentials are:\n\n"
        f"    Username : {username}\n"
        f"    Password : {password}\n\n"
        f"{extra_info}\n"
        f"Please log in and change your password after first login.\n\n"
        f"Regards,\n{school} Administration\n"
    )
    msg = Message(
        subject=f"[{school}] Your {portal} Login Credentials",
        recipients=[recipient_email],
        body=body
    )
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Mail send failed to {recipient_email}: {e}")
        return False


def send_attendance_notification(mail, parent_email, parent_name, student_name,
                                  att_date, status, class_name="", leave_reason=""):
    """Email a parent when their child is marked absent, late, or on leave."""
    school = current_app.config.get('SCHOOL_NAME', "Martyrs' Memorial College")
    status_map = {"absent": "ABSENT", "late": "LATE", "leave": "ON LEAVE"}
    status_text = status_map.get(status, status.upper())
    emoji_map = {"absent": "❌", "late": "⏰", "leave": "📋"}
    emoji = emoji_map.get(status, "⚠️")

    reason_line = f"\n    Reason    : {leave_reason}" if leave_reason else ""
    class_line = f" · {class_name}" if class_name else ""
    followup = {
        "absent": "If this absence was unexpected, please contact the class teacher.",
        "late": "Your child arrived late today. Please ensure punctuality.",
        "leave": "Leave has been recorded as requested.",
    }.get(status, "")

    body = (
        f"Dear {parent_name},\n\n"
        f"{emoji} Attendance Alert — {student_name}\n"
        f"{'='*50}\n\n"
        f"    Student   : {student_name}\n"
        f"    Date      : {att_date.strftime('%A, %d %B %Y')}{class_line}\n"
        f"    Status    : {status_text}"
        f"{reason_line}\n\n"
        f"{followup}\n\n"
        f"Log in to the Parent Portal to view full attendance details.\n\n"
        f"Regards,\n{school} Administration\n"
        f"\n─ Automated notification · Do not reply ─\n"
    )
    msg = Message(
        subject=f"[{school}] Attendance Alert — {student_name} · {status_text}",
        recipients=[parent_email],
        body=body
    )
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Attendance notification failed to {parent_email}: {e}")
        return False


def send_fee_reminder(mail, parent_email, parent_name, student_name, fee_type, amount, due_date):
    """Email a parent about a pending or overdue fee."""
    school = current_app.config.get('SCHOOL_NAME', "Martyrs' Memorial College")
    today = _date.today()
    overdue = due_date and due_date < today
    status_word = "OVERDUE" if overdue else "DUE SOON"
    body = (
        f"Dear {parent_name},\n\n"
        f"This is a reminder that the following fee for {student_name} is {status_word}:\n\n"
        f"    Fee Type  : {fee_type}\n"
        f"    Amount    : NPR {amount:,.0f}\n"
        f"    Due Date  : {due_date.strftime('%d %B %Y') if due_date else 'N/A'}\n\n"
        f"{'This fee is overdue. Please pay immediately to avoid penalties.' if overdue else 'Please ensure timely payment.'}\n\n"
        f"Visit the school office or the parent portal to make payment.\n\n"
        f"Regards,\n{school} Administration\n"
    )
    msg = Message(
        subject=f"[{school}] Fee Reminder - {student_name} ({fee_type})",
        recipients=[parent_email],
        body=body
    )
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Fee reminder failed to {parent_email}: {e}")
        return False


def send_notice_to_parent(mail, parent_email, parent_name, notice_title, notice_content):
    """Email a parent about a new school notice."""
    school = current_app.config.get('SCHOOL_NAME', "Martyrs' Memorial College")
    body = (
        f"Dear {parent_name},\n\n"
        f"New Notice from {school}\n\n"
        f"Title: {notice_title}\n\n"
        f"{notice_content}\n\n"
        f"Please log in to the Parent Portal for more details.\n\n"
        f"Regards,\n{school} Administration\n"
    )
    msg = Message(
        subject=f"[{school}] Notice: {notice_title}",
        recipients=[parent_email],
        body=body
    )
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Notice broadcast failed to {parent_email}: {e}")
        return False


def send_assignment_notification(mail, parent_email, parent_name, student_name,
                                  assignment_title, subject_name, due_date, class_name=""):
    """Email a parent when a new assignment is posted."""
    school = current_app.config.get('SCHOOL_NAME', "Martyrs' Memorial College")
    body = (
        f"Dear {parent_name},\n\n"
        f"New Assignment for {student_name}\n\n"
        f"A new assignment has been posted"
        f"{(' for ' + class_name) if class_name else ''}:\n\n"
        f"    Assignment : {assignment_title}\n"
        f"    Subject    : {subject_name or 'N/A'}\n"
        f"    Due Date   : {due_date.strftime('%d %B %Y') if due_date else 'N/A'}\n\n"
        f"Please encourage {student_name} to complete it on time.\n\n"
        f"Regards,\n{school} Administration\n"
    )
    msg = Message(
        subject=f"[{school}] New Assignment: {assignment_title}",
        recipients=[parent_email],
        body=body
    )
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Assignment notification failed to {parent_email}: {e}")
        return False


def send_direct_message(mail, recipient_email, recipient_name, sender_name, subject, body_text):
    """Send a direct message from admin/teacher to a parent."""
    school = current_app.config.get('SCHOOL_NAME', "Martyrs' Memorial College")
    body = (
        f"Dear {recipient_name},\n\n"
        f"You have a new message from {sender_name} ({school}):\n\n"
        f"Subject: {subject}\n\n"
        f"{body_text}\n\n"
        f"Please log in to your portal to reply or view more messages.\n\n"
        f"Regards,\n{school} Administration\n"
    )
    msg = Message(
        subject=f"[{school}] Message from {sender_name}: {subject}",
        recipients=[recipient_email],
        body=body
    )
    try:
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Direct message failed to {recipient_email}: {e}")
        return False
