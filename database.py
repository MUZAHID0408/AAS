import sqlite3

def initialize_database():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    # Enable foreign key constraints
    c.execute("PRAGMA foreign_keys = ON")
    
    # Teachers table
    c.execute('''CREATE TABLE IF NOT EXISTS teachers
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    
    # Students table
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  roll_no TEXT UNIQUE NOT NULL,
                  face_encoding BLOB,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    
    # Sections table
    c.execute('''CREATE TABLE IF NOT EXISTS sections
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  created_by INTEGER NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY(created_by) REFERENCES teachers(id) ON DELETE CASCADE)''')
    
    # Student-Section mapping
    c.execute('''CREATE TABLE IF NOT EXISTS student_sections
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  student_id INTEGER NOT NULL,
                  section_id INTEGER NOT NULL,
                  UNIQUE(student_id, section_id),
                  FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                  FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE)''')
    
    # Attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  student_id INTEGER NOT NULL,
                  date TEXT NOT NULL,
                  status TEXT NOT NULL CHECK(status IN ('present', 'absent')),
                  section_id INTEGER NOT NULL,
                  teacher_id INTEGER NOT NULL,
                  recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(student_id, date, section_id),
                  FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                  FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE,
                  FOREIGN KEY(teacher_id) REFERENCES teachers(id) ON DELETE CASCADE)''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    initialize_database()