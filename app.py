from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from datetime import datetime, timedelta
import sqlite3
import hashlib
import calendar
from face_recog import process_group_photo, add_student_face
import functools

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['KNOWN_FACES'] = 'static/known_faces'

#  Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['KNOWN_FACES'], exist_ok=True)

# Authentication decorator
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'teacher_id' not in session:
            flash('Please login to access this page')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_teacher(teacher_id):
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM teachers WHERE id = ?", (teacher_id,))
    teacher = c.fetchone()
    conn.close()
    return dict(teacher) if teacher else None

def get_section(section_id):
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sections WHERE id = ?", (section_id,))
    section = c.fetchone()
    conn.close()
    return dict(section) if section else None

def get_teacher_sections(teacher_id):
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sections WHERE created_by = ? ORDER BY name", (teacher_id,))
    sections = c.fetchall()
    conn.close()
    return [dict(section) for section in sections]

def get_section_students(section_id):
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT s.* FROM students s
        JOIN student_sections ss ON s.id = ss.student_id
        WHERE ss.section_id = ?
        ORDER BY s.name
    """, (section_id,))
    students = c.fetchall()
    conn.close()
    return [dict(student) for student in students]

# Routes
@app.route('/')
def index():
    if 'teacher_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = hash_password(request.form['password'])
        
        conn = sqlite3.connect('attendance.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM teachers WHERE email = ? AND password = ?", (email, password))
        teacher = c.fetchone()
        
        if teacher:
            session['teacher_id'] = teacher['id']
            session['teacher_name'] = teacher['name']
            flash('Login successful!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password')
        
        conn.close()
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('signup'))
        
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        
        # Check if email already exists
        c.execute("SELECT * FROM teachers WHERE email = ?", (email,))
        if c.fetchone():
            flash('Email already registered')
            conn.close()
            return redirect(url_for('signup'))
        
        # Hash password and insert new teacher
        hashed_password = hash_password(password)
        c.execute(
            "INSERT INTO teachers (name, email, password, created_at) VALUES (?, ?, ?, ?)",
            (name, email, hashed_password, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        
        conn.commit()
        conn.close()
        
        flash('Account created successfully! Please login.')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    teacher = get_teacher(session['teacher_id'])
    sections = get_teacher_sections(session['teacher_id'])
    return render_template('dashboard.html', teacher=teacher, sections=sections)

@app.route('/add_section', methods=['GET', 'POST'])
@login_required
def add_section():
    if request.method == 'POST':
        section_name = request.form['name']
        student_ids = request.form.getlist('students')
        
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        
        # Create section
        c.execute(
            "INSERT INTO sections (name, created_by, created_at) VALUES (?, ?, ?)",
            (section_name, session['teacher_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        
        section_id = c.lastrowid
        
        # Add students to section
        for student_id in student_ids:
            c.execute(
                "INSERT INTO student_sections (student_id, section_id) VALUES (?, ?)",
                (student_id, section_id)
            )
        
        conn.commit()
        conn.close()
        
        flash(f'Section "{section_name}" created successfully!')
        return redirect(url_for('dashboard'))
    
    # Get all students for selection
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM students ORDER BY name")
    students = c.fetchall()
    conn.close()
    
    return render_template('add_section.html', students=students)

@app.route('/section/<int:section_id>/take_attendance')
@login_required
def take_attendance(section_id):
    section = get_section(section_id)
    if not section or section['created_by'] != session['teacher_id']:
        flash('Section not found or access denied')
        return redirect(url_for('dashboard'))
    
    return render_template('take_attendance.html', section=section, datetime=datetime)

@app.route('/section/<int:section_id>/process_attendance', methods=['POST'])
@login_required
def process_attendance(section_id):
    section = get_section(section_id)
    if not section or section['created_by'] != session['teacher_id']:
        flash('Section not found or access denied')
        return redirect(url_for('dashboard'))
    
    if 'files' not in request.files:
        flash('No files selected')
        return redirect(url_for('take_attendance', section_id=section_id))
    
    files = request.files.getlist('files')
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    # Get students in this section
    section_students = get_section_students(section_id)
    if not section_students:
        flash('No students in this section')
        return redirect(url_for('take_attendance', section_id=section_id))
    
    present_rolls = set()
    
    for file in files:
        if file.filename == '':
            continue
            
        if file and allowed_file(file.filename):
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process the image
            rolls = process_group_photo(filepath)
            present_rolls.update(rolls)
    
    # Convert section_students to a dictionary by roll_no
    students_dict = {student['roll_no']: student for student in section_students}
    
    # Connect to database
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    # Check if attendance for this section and date already exists
    c.execute(
        "SELECT id FROM attendance WHERE section_id = ? AND date = ? LIMIT 1", 
        (section_id, date)
    )
    
    if c.fetchone():
        # Delete existing attendance records for this section and date
        c.execute(
            "DELETE FROM attendance WHERE section_id = ? AND date = ?",
            (section_id, date)
        )
    
    # Mark attendance for each student in this section
    for student in section_students:
        roll_no = student['roll_no']
        status = 'present' if roll_no in present_rolls else 'absent'
        c.execute(
            """INSERT INTO attendance 
               (student_id, date, status, section_id, teacher_id) 
               VALUES (?, ?, ?, ?, ?)""",
            (student['id'], date, status, section_id, session['teacher_id'])
        )
    
    conn.commit()
    
    # Prepare results
    present = [(roll, students_dict[roll]['name']) for roll in present_rolls if roll in students_dict]
    absent = [(student['roll_no'], student['name']) for student in section_students 
             if student['roll_no'] not in present_rolls]
    
    conn.close()
    
    return render_template('results.html', 
                          present=present, 
                          absent=absent, 
                          date=date, 
                          section=section)

@app.route('/section/<int:section_id>/attendance_history')
@login_required
def attendance_history(section_id):
    section = get_section(section_id)
    if not section or section['created_by'] != session['teacher_id']:
        flash('Section not found or access denied')
        return redirect(url_for('dashboard'))
    
    # Get month filter (default to current month)
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    year, month = map(int, selected_month.split('-'))
    
    # Calculate start and end date for the selected month
    start_date = f"{selected_month}-01"
    _, last_day = calendar.monthrange(year, month)
    end_date = f"{selected_month}-{last_day}"
    
    # Get attendance data for the selected month
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get unique dates with attendance records for this section
    c.execute("""
        SELECT DISTINCT date, COUNT(CASE WHEN status = 'present' THEN 1 END) as present_count
        FROM attendance
        JOIN students ON attendance.student_id = students.id
        WHERE section_id = ? AND date BETWEEN ? AND ?
        GROUP BY date
        ORDER BY date DESC
    """, (section_id, start_date, end_date))
    
    attendance_dates = [(row['date'], row['present_count']) for row in c.fetchall()]
    
    # Get total students in this section
    total_students = len(get_section_students(section_id))
    
    conn.close()
    
    return render_template('attendance_history.html',
                          section=section,
                          attendance_dates=attendance_dates,
                          total_students=total_students,
                          selected_month=selected_month)

@app.route('/section/<int:section_id>/attendance/<date>/view')
@login_required
def view_attendance_detail(section_id, date):
    section = get_section(section_id)
    if not section or section['created_by'] != session['teacher_id']:
        flash('Section not found or access denied')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get all students for this section with their attendance status
    c.execute("""
        SELECT s.id, s.name, s.roll_no, a.status
        FROM students s
        JOIN student_sections ss ON s.id = ss.student_id
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date = ? AND a.section_id = ?
        WHERE ss.section_id = ?
        ORDER BY s.name
    """, (date, section_id, section_id))
    
    students = [dict(student) for student in c.fetchall()]
    conn.close()
    
    # Separate into present and absent lists
    present_students = [s for s in students if s.get('status') == 'present']
    absent_students = [s for s in students if s.get('status') != 'present']
    
    # Calculate statistics
    total_students = len(students)
    present_count = len(present_students)
    absent_count = len(absent_students)
    attendance_rate = round((present_count / total_students) * 100) if total_students > 0 else 0
    
    return render_template('attendance_detail.html',
                          section=section,
                          date=date,
                          total_students=total_students,
                          present_count=present_count,
                          absent_count=absent_count,
                          attendance_rate=attendance_rate,
                          present_students=present_students,
                          absent_students=absent_students)

@app.route('/section/<int:section_id>/attendance/<date>/edit', methods=['GET', 'POST'])
@login_required
def edit_attendance(section_id, date):
    section = get_section(section_id)
    if not section or section['created_by'] != session['teacher_id']:
        flash('Section not found or access denied')
        return redirect(url_for('dashboard'))
    
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if request.method == 'POST':
        # Get students in this section
        c.execute("""
            SELECT s.id FROM students s
            JOIN student_sections ss ON s.id = ss.student_id
            WHERE ss.section_id = ?
        """, (section_id,))
        
        student_ids = [row['id'] for row in c.fetchall()]
        
        # First check if attendance exists for this date
        c.execute(
            "SELECT id FROM attendance WHERE section_id = ? AND date = ? LIMIT 1",
            (section_id, date)
        )
        
        if not c.fetchone():
            # Create new attendance records for all students
            for student_id in student_ids:
                status_key = f"status-{student_id}"
                status = request.form.get(status_key, 'absent')
                
                c.execute(
                    """INSERT INTO attendance 
                       (student_id, date, status, section_id, teacher_id) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (student_id, date, status, section_id, session['teacher_id'])
                )
        else:
            # Update existing attendance records
            for student_id in student_ids:
                status_key = f"status-{student_id}"
                status = request.form.get(status_key, 'absent')
                
                # Check if record exists for this student
                c.execute(
                    """SELECT id FROM attendance 
                       WHERE student_id = ? AND date = ? AND section_id = ?""",
                    (student_id, date, section_id)
                )
                
                if c.fetchone():
                    # Update existing record
                    c.execute(
                        """UPDATE attendance SET status = ? 
                           WHERE student_id = ? AND date = ? AND section_id = ?""",
                        (status, student_id, date, section_id)
                    )
                else:
                    # Create new record
                    c.execute(
                        """INSERT INTO attendance 
                           (student_id, date, status, section_id, teacher_id) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (student_id, date, status, section_id, session['teacher_id'])
                    )
        
        conn.commit()
        flash('Attendance updated successfully')
        return redirect(url_for('view_attendance_detail', section_id=section_id, date=date))
    
    # For GET request - display form
    # Get all students for this section with their attendance status
    c.execute("""
        SELECT s.id, s.name, s.roll_no, a.status
        FROM students s
        JOIN student_sections ss ON s.id = ss.student_id
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date = ? AND a.section_id = ?
        WHERE ss.section_id = ?
        ORDER BY s.name
    """, (date, section_id, section_id))
    
    students = [dict(student) for student in c.fetchall()]
    conn.close()
    
    return render_template('edit_attendance.html',
                          section=section,
                          date=date,
                          students=students)

@app.route('/section/<int:section_id>/manage_students')
@login_required
def manage_students(section_id):
    section = get_section(section_id)
    if not section or section['created_by'] != session['teacher_id']:
        flash('Section not found or access denied')
        return redirect(url_for('dashboard'))
    
    # Get students currently in this section
    section_students = get_section_students(section_id)
    
    # Get all students
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM students ORDER BY name")
    all_students = [dict(student) for student in c.fetchall()]
    conn.close()
    
    # Mark which students are already in this section
    section_student_ids = [s['id'] for s in section_students]
    for student in all_students:
        student['in_section'] = student['id'] in section_student_ids
    
    return render_template('manage_students.html',
                          section=section,
                          students=all_students)

@app.route('/section/<int:section_id>/update_students', methods=['POST'])
@login_required
def update_section_students(section_id):
    section = get_section(section_id)
    if not section or section['created_by'] != session['teacher_id']:
        flash('Section not found or access denied')
        return redirect(url_for('dashboard'))
    
    selected_students = request.form.getlist('students')
    
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    # Remove all current associations
    c.execute("DELETE FROM student_sections WHERE section_id = ?", (section_id,))
    
    # Add new associations
    for student_id in selected_students:
        c.execute(
            "INSERT INTO student_sections (student_id, section_id) VALUES (?, ?)",
            (student_id, section_id)
        )
    
    conn.commit()
    conn.close()
    
    flash(f'Students updated for section "{section["name"]}"')
    return redirect(url_for('manage_students', section_id=section_id))

# Original routes (modified to maintain compatibility)
@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        roll_no = request.form['roll_no']
        file = request.files['photo']
        
        if file and allowed_file(file.filename):
            filename = os.path.join(app.config['KNOWN_FACES'], f"{roll_no}.jpg")
            file.save(filename)
            
            if add_student_face(name, roll_no, filename):
                flash('Student added successfully')
                
                # If teacher is logged in, redirect to manage students
                if 'teacher_id' in session and request.args.get('section_id'):
                    section_id = request.args.get('section_id')
                    return redirect(url_for('manage_students', section_id=section_id))
            else:
                flash('Error adding student (possibly duplicate roll no or no face detected)')
        
        return redirect(url_for('index'))
    
    return render_template('add_student.html')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

if __name__ == '__main__':
    app.run(debug=True)