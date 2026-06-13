-- ============================================================
--  Martyrs' Memorial College — School ERP
--  Complete Database Setup
--  Run this once against your MySQL server:
--    mysql -u root -p < school_erp_setup.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS school_erp
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE school_erp;

SET FOREIGN_KEY_CHECKS = 0;

-- ──────────────────────────────────────────────
--  1. USERS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(80)  UNIQUE NOT NULL,
    email         VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL,          -- admin | teacher | student | parent
    full_name     VARCHAR(150) NOT NULL,
    phone         VARCHAR(20),
    profile_image VARCHAR(255) DEFAULT 'default.png',
    is_active     TINYINT(1)   DEFAULT 1,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
    last_login    DATETIME,
    INDEX idx_users_role (role),
    INDEX idx_users_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  2. STREAMS  (Science / Management / Humanities …)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS streams (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50)  NOT NULL,
    code        VARCHAR(10)  UNIQUE,
    description TEXT,
    is_active   TINYINT(1)   DEFAULT 1,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  3. TEACHERS  (must exist before classes)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS teachers (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT  UNIQUE NOT NULL,
    employee_id   VARCHAR(20) UNIQUE NOT NULL,
    subject       VARCHAR(100),
    qualification VARCHAR(200),
    joining_date  DATE,
    salary        FLOAT,
    department    VARCHAR(100),
    status        VARCHAR(20) DEFAULT 'active',
    CONSTRAINT fk_teacher_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_teacher_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  4. CLASSES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS classes (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(50) NOT NULL,
    section          VARCHAR(10) NOT NULL,
    stream_id        INT,
    class_teacher_id INT,
    academic_year    VARCHAR(20) DEFAULT '2081-2082',
    capacity         INT         DEFAULT 40,
    room_no          VARCHAR(20),
    created_at       DATETIME    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_class_stream  FOREIGN KEY (stream_id)        REFERENCES streams(id)  ON DELETE SET NULL,
    CONSTRAINT fk_class_teacher FOREIGN KEY (class_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL,
    INDEX idx_class_ay (academic_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  5. STUDENTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS students (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    user_id        INT  UNIQUE NOT NULL,
    roll_no        VARCHAR(20) UNIQUE NOT NULL,
    class_id       INT,
    admission_date DATE,
    date_of_birth  DATE,
    gender         VARCHAR(10),
    address        TEXT,
    guardian_name  VARCHAR(150),
    guardian_phone VARCHAR(20),
    blood_group    VARCHAR(5),
    academic_year  VARCHAR(20) DEFAULT '2081-2082',
    status         VARCHAR(20) DEFAULT 'active',
    CONSTRAINT fk_student_user  FOREIGN KEY (user_id)  REFERENCES users(id)   ON DELETE CASCADE,
    CONSTRAINT fk_student_class FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL,
    INDEX idx_student_status (status),
    INDEX idx_student_class  (class_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  6. PARENTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS parents (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT  UNIQUE NOT NULL,
    student_id    INT,
    relationship  VARCHAR(30),
    occupation    VARCHAR(100),
    annual_income FLOAT,
    CONSTRAINT fk_parent_user    FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
    CONSTRAINT fk_parent_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  7. SUBJECTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subjects (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(20),
    class_id        INT,
    stream_id       INT,
    teacher_id      INT,
    subject_type    VARCHAR(20) DEFAULT 'theory',   -- theory | practical | both
    max_marks       INT         DEFAULT 100,
    pass_marks      INT         DEFAULT 40,
    credit_hours    INT         DEFAULT 4,
    practical_marks INT         DEFAULT 0,
    is_optional     TINYINT(1)  DEFAULT 0,
    CONSTRAINT fk_subject_class   FOREIGN KEY (class_id)   REFERENCES classes(id)   ON DELETE SET NULL,
    CONSTRAINT fk_subject_stream  FOREIGN KEY (stream_id)  REFERENCES streams(id)   ON DELETE SET NULL,
    CONSTRAINT fk_subject_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id)  ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  8. ATTENDANCE
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attendance (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT  NOT NULL,
    class_id   INT,
    date       DATE NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'present',   -- present | absent | late
    marked_by  INT,
    remarks    VARCHAR(200),
    CONSTRAINT fk_att_student   FOREIGN KEY (student_id) REFERENCES students(id)  ON DELETE CASCADE,
    CONSTRAINT fk_att_class     FOREIGN KEY (class_id)   REFERENCES classes(id)   ON DELETE SET NULL,
    CONSTRAINT fk_att_teacher   FOREIGN KEY (marked_by)  REFERENCES teachers(id)  ON DELETE SET NULL,
    UNIQUE KEY uq_attendance (student_id, date),
    INDEX idx_att_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  9. EXAMS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exams (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    class_id      INT,
    subject_id    INT,
    exam_date     DATE,
    max_marks     INT         DEFAULT 100,
    pass_marks    INT         DEFAULT 40,
    exam_type     VARCHAR(30) DEFAULT 'unit_test',
    -- unit_test | first_terminal | mid_term | pre_board | final_board | internal | practical
    academic_year VARCHAR(20) DEFAULT '2081-2082',
    created_at    DATETIME    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_exam_class   FOREIGN KEY (class_id)   REFERENCES classes(id)   ON DELETE SET NULL,
    CONSTRAINT fk_exam_subject FOREIGN KEY (subject_id) REFERENCES subjects(id)  ON DELETE SET NULL,
    INDEX idx_exam_date (exam_date),
    INDEX idx_exam_type (exam_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  10. RESULTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS results (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    student_id       INT   NOT NULL,
    exam_id          INT   NOT NULL,
    marks_obtained   FLOAT DEFAULT 0,
    practical_marks  FLOAT DEFAULT 0,
    grade            VARCHAR(5),
    gpa              FLOAT DEFAULT 0.0,
    remarks          VARCHAR(200),
    is_absent        TINYINT(1) DEFAULT 0,
    created_at       DATETIME   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_result_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    CONSTRAINT fk_result_exam    FOREIGN KEY (exam_id)    REFERENCES exams(id)    ON DELETE CASCADE,
    UNIQUE KEY uq_result (student_id, exam_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  11. FEES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fees (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    student_id     INT         NOT NULL,
    fee_type       VARCHAR(50) NOT NULL,
    amount         FLOAT       NOT NULL,
    due_date       DATE,
    paid_date      DATE,
    payment_method VARCHAR(30),
    status         VARCHAR(20) DEFAULT 'pending',   -- pending | paid | overdue | waived
    academic_year  VARCHAR(20) DEFAULT '2081-2082',
    receipt_no     VARCHAR(50),
    created_at     DATETIME    DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fee_student FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_fee_status (status),
    INDEX idx_fee_student (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  12. NOTICES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notices (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    content     TEXT         NOT NULL,
    created_by  INT,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    expiry_date DATE,
    target_role VARCHAR(20)  DEFAULT 'all',   -- all | student | teacher | parent
    is_active   TINYINT(1)   DEFAULT 1,
    priority    VARCHAR(20)  DEFAULT 'normal', -- normal | high | urgent
    CONSTRAINT fk_notice_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_notice_active (is_active),
    INDEX idx_notice_role   (target_role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  13. ASSIGNMENTS
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assignments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    teacher_id  INT NOT NULL,
    class_id    INT NOT NULL,
    subject_id  INT,
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    due_date    DATE,
    max_marks   INT         DEFAULT 10,
    created_at  DATETIME    DEFAULT CURRENT_TIMESTAMP,
    status      VARCHAR(20) DEFAULT 'active',
    CONSTRAINT fk_assign_teacher  FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    CONSTRAINT fk_assign_class    FOREIGN KEY (class_id)   REFERENCES classes(id)  ON DELETE CASCADE,
    CONSTRAINT fk_assign_subject  FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    INDEX idx_assign_class (class_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ──────────────────────────────────────────────
--  14. TIMETABLES
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS timetables (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    class_id    INT NOT NULL,
    subject_id  INT,
    teacher_id  INT,
    day_of_week INT NOT NULL,   -- 0=Monday … 5=Saturday
    start_time  TIME,
    end_time    TIME,
    room_no     VARCHAR(20),
    period_no   INT DEFAULT 1,
    CONSTRAINT fk_tt_class   FOREIGN KEY (class_id)   REFERENCES classes(id)   ON DELETE CASCADE,
    CONSTRAINT fk_tt_subject FOREIGN KEY (subject_id) REFERENCES subjects(id)  ON DELETE SET NULL,
    CONSTRAINT fk_tt_teacher FOREIGN KEY (teacher_id) REFERENCES teachers(id)  ON DELETE SET NULL,
    INDEX idx_tt_class_day (class_id, day_of_week)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
--  SEED DATA
-- ============================================================

-- ── Admin user ──────────────────────────────────────────────
--  username : msuraj24@tbc.edu.np
--  password : suraj@123  (bcrypt hash below)
INSERT INTO users (username, email, password_hash, role, full_name, is_active)
VALUES (
    'msuraj24@tbc.edu.np',
    'msuraj24@tbc.edu.np',
    '$2b$12$d2pG6U8qSPYkyLYgzk.HtO0pwkrZJQ2whL8ZyLIHI32IWECVK4wim',
    'admin',
    'Suraj Mehta',
    1
)
ON DUPLICATE KEY UPDATE
    password_hash = VALUES(password_hash),
    role          = 'admin',
    is_active     = 1;

-- ── Streams ─────────────────────────────────────────────────
INSERT IGNORE INTO streams (name, code, description) VALUES
    ('Science',     'SCI', 'Physics, Chemistry, Biology/Mathematics'),
    ('Management',  'MGT', 'Business Studies, Accountancy, Economics'),
    ('Humanities',  'HUM', 'Sociology, History, Political Science, English');

-- ── Sample notice ───────────────────────────────────────────
INSERT INTO notices (title, content, created_by, target_role, priority)
SELECT
    'Welcome to Martyrs'' Memorial College ERP',
    'The new School ERP system is now live. All portals (Admin, Teacher, Student, Parent) are active. Please log in with the credentials sent to your registered email.',
    id,
    'all',
    'high'
FROM users WHERE username = 'msuraj24@tbc.edu.np'
LIMIT 1;

-- ============================================================
--  USEFUL VIEWS  (optional — handy for reporting)
-- ============================================================

CREATE OR REPLACE VIEW v_student_summary AS
SELECT
    s.id            AS student_id,
    s.roll_no,
    u.full_name,
    u.email,
    u.phone,
    s.gender,
    s.blood_group,
    s.status,
    s.academic_year,
    CONCAT('Class ', c.name, ' - ', c.section) AS class_name,
    st.name         AS stream_name
FROM students s
JOIN users   u  ON s.user_id  = u.id
LEFT JOIN classes c  ON s.class_id = c.id
LEFT JOIN streams st ON c.stream_id = st.id;

CREATE OR REPLACE VIEW v_teacher_summary AS
SELECT
    t.id            AS teacher_id,
    t.employee_id,
    u.full_name,
    u.email,
    u.phone,
    t.subject,
    t.department,
    t.qualification,
    t.status
FROM teachers t
JOIN users u ON t.user_id = u.id;

CREATE OR REPLACE VIEW v_fee_summary AS
SELECT
    f.id,
    u.full_name     AS student_name,
    s.roll_no,
    f.fee_type,
    f.amount,
    f.due_date,
    f.paid_date,
    f.status,
    f.receipt_no,
    f.academic_year
FROM fees f
JOIN students s ON f.student_id = s.id
JOIN users    u ON s.user_id    = u.id;

CREATE OR REPLACE VIEW v_attendance_summary AS
SELECT
    s.roll_no,
    u.full_name,
    COUNT(*)                                          AS total_days,
    SUM(a.status = 'present')                        AS present_days,
    SUM(a.status = 'absent')                         AS absent_days,
    ROUND(SUM(a.status = 'present') / COUNT(*) * 100, 1) AS attendance_pct
FROM attendance a
JOIN students s ON a.student_id = s.id
JOIN users    u ON s.user_id    = u.id
GROUP BY s.id, s.roll_no, u.full_name;

-- ============================================================
--  Done.  Admin login:
--    Username : msuraj24@tbc.edu.np
--    Password : suraj@123
-- ============================================================
