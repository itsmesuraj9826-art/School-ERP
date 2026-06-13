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