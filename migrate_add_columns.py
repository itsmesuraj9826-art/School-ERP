"""
One-time migration script — run once from project root:
    python migrate_add_columns.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

import pymysql

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'school_erp')

conn = pymysql.connect(
    host=DB_HOST, port=DB_PORT,
    user=DB_USER, password=DB_PASSWORD,
    database=DB_NAME, charset='utf8mb4'
)

migrations = [
    # students table
    ("students", "profile_image",
     "ALTER TABLE students ADD COLUMN profile_image VARCHAR(255) DEFAULT 'default.png'"),

    # users table — email nullable (parents may not have one)
    ("users", "email_nullable",
     "ALTER TABLE users MODIFY COLUMN email VARCHAR(120) NULL"),

    # leave_requests table
    ("leave_requests", "id",
     """CREATE TABLE IF NOT EXISTS leave_requests (
         id INT AUTO_INCREMENT PRIMARY KEY,
         user_id INT NOT NULL,
         leave_type VARCHAR(50) DEFAULT 'sick',
         from_date DATE NOT NULL,
         to_date DATE NOT NULL,
         reason TEXT NOT NULL,
         status VARCHAR(20) DEFAULT 'pending',
         reviewed_by INT,
         review_comment TEXT,
         reviewed_at DATETIME,
         created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
         FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
     ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""),

    # events table
    ("events", "id",
     """CREATE TABLE IF NOT EXISTS events (
         id INT AUTO_INCREMENT PRIMARY KEY,
         title VARCHAR(200) NOT NULL,
         description TEXT,
         event_date DATE NOT NULL,
         end_date DATE,
         event_type VARCHAR(50) DEFAULT 'general',
         target_role VARCHAR(20) DEFAULT 'all',
         location VARCHAR(200),
         created_by INT,
         created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
         is_active TINYINT(1) DEFAULT 1,
         FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
     ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""),

    # notifications table
    ("notifications", "id",
     """CREATE TABLE IF NOT EXISTS notifications (
         id INT AUTO_INCREMENT PRIMARY KEY,
         user_id INT NOT NULL,
         title VARCHAR(200) NOT NULL,
         message TEXT NOT NULL,
         notif_type VARCHAR(50) DEFAULT 'info',
         link VARCHAR(300),
         is_read TINYINT(1) DEFAULT 0,
         created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
         FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
     ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""),
]

with conn.cursor() as cur:
    for table, col, sql in migrations:
        try:
            # Check if already done
            if col not in ("id", "email_nullable"):
                cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE '{col}'")
                if cur.fetchone():
                    print(f"  SKIP  {table}.{col} already exists")
                    continue
            elif col == "email_nullable":
                # Just run it — modifying nullable is safe to repeat
                pass
            cur.execute(sql)
            conn.commit()
            print(f"  OK    {table}: {col}")
        except pymysql.err.OperationalError as e:
            if "already exists" in str(e) or "Duplicate column" in str(e):
                print(f"  SKIP  {table}: already migrated")
            else:
                print(f"  ERR   {table}.{col}: {e}")

conn.close()
print("\nMigration complete. Restart python app.py")
