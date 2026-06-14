import os
from werkzeug.utils import secure_filename
from flask import current_app
from datetime import datetime


def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def save_teacher_file(file, teacher_id, file_type):
    """Save a file for a teacher"""
    if not file or file.filename == '':
        return None

    if not allowed_file(file.filename):
        return None

    # Create teacher-specific folder
    teacher_folder = os.path.join(current_app.config['TEACHER_UPLOAD_FOLDER'], str(teacher_id))
    os.makedirs(teacher_folder, exist_ok=True)

    # Generate unique filename
    original_filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{file_type}_{timestamp}_{original_filename}"
    filepath = os.path.join(teacher_folder, filename)

    # Save file
    file.save(filepath)

    # Return relative path for database
    return f"uploads/teachers/{teacher_id}/{filename}"


def delete_teacher_file(filepath):
    """Delete a file from the server"""
    if filepath:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filepath)
        if os.path.exists(full_path):
            os.remove(full_path)

def save_student_file(file, student_id, file_type='profile'):
    """Save a file for a student"""
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    # Always resolve from root_path so there is no double-uploads confusion
    student_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'students', str(student_id))
    os.makedirs(student_folder, exist_ok=True)
    ext = file.filename.rsplit('.', 1)[1].lower()
    import uuid
    filename = f"{file_type}_{uuid.uuid4().hex[:12]}.{ext}"
    filepath = os.path.join(student_folder, filename)
    file.save(filepath)
    return f"uploads/students/{student_id}/{filename}"


def delete_student_file(filepath):
    """Delete a student file"""
    if filepath and filepath != 'default.png':
        full_path = os.path.join(current_app.root_path, 'static', filepath)
        if os.path.exists(full_path):
            os.remove(full_path)
