from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
import csv
import os
import json
import sqlite3
import io
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')  # Use environment variable in production

@app.template_filter('format_hours')
def format_hours(hours):
    """Format hours in a human-readable way (e.g., 0.89 -> 53 minutes, 8.5 -> 8h 30m)"""
    if hours is None:
        hours = 0.0
    hours = float(hours)
    
    if hours == 0:
        return "0 hours"
    
    # Get whole hours and minutes
    whole_hours = int(hours)
    minutes = int((hours - whole_hours) * 60)
    
    if whole_hours == 0:
        if minutes == 0:
            return "0 hours"
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif minutes == 0:
        return f"{whole_hours} hour{'s' if whole_hours != 1 else ''}"
    else:
        return f"{whole_hours}h {minutes}m"

# Configuration
DATA_DIR = 'data'
USERS_CSV = os.path.join(DATA_DIR, 'users.csv')
ORDERS_CSV = os.path.join(DATA_DIR, 'orders.csv')
MENU_CSV = os.path.join(DATA_DIR, 'menu.csv')
CATEGORIES_CSV = os.path.join(DATA_DIR, 'categories.csv')
ADMIN_PROFILE_JSON = os.path.join(DATA_DIR, 'admin_profile.json')
ADMIN_SETTINGS_JSON = os.path.join(DATA_DIR, 'admin_settings.json')
ROLE_RATES_JSON = os.path.join(DATA_DIR, 'role_rates.json')
EMPLOYEES_DB = os.path.join(DATA_DIR, 'employees.db')
COUPONS_CSV = os.path.join(DATA_DIR, 'coupons.csv')

# Default job categories for employees
JOB_CATEGORIES_DEFAULT = [
    'Server', 'Chef', 'Line Cook', 'Sous Chef', 'Head Chef', 'Prep Cook',
    'Bartender', 'Barista', 'Cashier', 'Host/Hostess', 'Dishwasher',
    'Delivery Driver', 'Manager', 'Assistant Manager', 'Shift Lead',
    'HR', 'Admin', 'Cleaner'
]

# Upload configuration
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_image(file_storage):
    if not file_storage or file_storage.filename == '' or not allowed_file(file_storage.filename):
        return None
    filename = secure_filename(file_storage.filename)
    name, ext = os.path.splitext(filename)
    counter = 1
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    while os.path.exists(save_path):
        filename = f"{name}_{counter}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        counter += 1
    file_storage.save(save_path)
    return filename

def get_categories():
    categories = []
    if os.path.exists(CATEGORIES_CSV):
        with open(CATEGORIES_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if row:
                    categories.append(row[0])
    return categories

def save_categories(categories):
    unique_sorted = sorted(set([c.strip() for c in categories if c.strip()]))
    with open(CATEGORIES_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['category'])
        for category in unique_sorted:
            writer.writerow([category])
    return unique_sorted

def get_user_map():
    users = {}
    if os.path.exists(USERS_CSV):
        with open(USERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                users[row['user_id']] = row['name']
    return users

def get_employee_connection():
    conn = sqlite3.connect(EMPLOYEES_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_employee_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with get_employee_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                gender TEXT,
                dob TEXT,
                mobile TEXT,
                address TEXT,
                job_title TEXT,
                notes TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        ''')
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
        if 'status' not in existing_columns:
            conn.execute("ALTER TABLE employees ADD COLUMN status TEXT DEFAULT 'active'")
        if 'schedule' not in existing_columns:
            # Default schedule: Mon-Fri, 9AM-5PM
            default_schedule = json.dumps({
                'monday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'tuesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'wednesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'thursday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'friday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
                'saturday': {'enabled': False, 'start': '09:00', 'end': '17:00'},
                'sunday': {'enabled': False, 'start': '09:00', 'end': '17:00'}
            })
            # SQLite doesn't support parameterized DEFAULT values in ALTER TABLE
            # Escape single quotes in the JSON string
            escaped_schedule = default_schedule.replace("'", "''")
            conn.execute(f"ALTER TABLE employees ADD COLUMN schedule TEXT DEFAULT '{escaped_schedule}'")
        if 'hours_this_period' not in existing_columns:
            conn.execute("ALTER TABLE employees ADD COLUMN hours_this_period REAL DEFAULT 0")
        if 'last_paid_date' not in existing_columns:
            conn.execute("ALTER TABLE employees ADD COLUMN last_paid_date TEXT")
        if 'profile_picture' not in existing_columns:
            conn.execute("ALTER TABLE employees ADD COLUMN profile_picture TEXT")
        if 'hourly_rate' not in existing_columns:
            conn.execute("ALTER TABLE employees ADD COLUMN hourly_rate REAL")
        
        # Create attendance table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT NOT NULL,
                date TEXT NOT NULL,
                check_in_time TEXT,
                check_out_time TEXT,
                hours_worked REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
                UNIQUE(employee_id, date)
            )
        ''')
        conn.commit()

def employee_id_exists(candidate):
    with get_employee_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM employees WHERE employee_id = ? LIMIT 1",
            (candidate,)
        ).fetchone()
    return row is not None

def generate_employee_id():
    attempts = 0
    while attempts < 1000:
        candidate = f"{random.randint(0, 999_999):06d}"
        if not employee_id_exists(candidate):
            return candidate
        attempts += 1
    raise ValueError("Unable to generate unique employee ID")

def get_employees(search_query=None, limit=None, status_filter=None):
    query = "SELECT employee_id, first_name, last_name, email, gender, dob, mobile, address, job_title, notes, status, created_at, schedule FROM employees"
    params = []
    if search_query:
        query += " WHERE (employee_id LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR mobile LIKE ?)"
        search_term = f"%{search_query}%"
        params.extend([search_term] * 5)
    if status_filter:
        clause = "status = ?"
        if "WHERE" in query:
            query += f" AND {clause}"
        else:
            query += f" WHERE {clause}"
        params.append(status_filter)
    query += " ORDER BY datetime(created_at) DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_employee_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        employees = []
        for row in rows:
            emp = dict(row)
            # Parse schedule JSON
            if emp.get('schedule'):
                try:
                    emp['schedule'] = json.loads(emp['schedule'])
                except:
                    emp['schedule'] = get_default_schedule()
            else:
                emp['schedule'] = get_default_schedule()
            employees.append(emp)
        return employees

def create_employee_record(first_name, last_name, email, gender='', dob='', mobile='', address='', job_title='', notes='', status='active'):
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    employee_id = generate_employee_id()
    default_schedule = json.dumps(get_default_schedule())
    with get_employee_connection() as conn:
        # Check if schedule column exists
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
        if 'schedule' in existing_columns:
            conn.execute('''
                INSERT INTO employees (employee_id, first_name, last_name, email, gender, dob, mobile, address, job_title, notes, status, created_at, schedule)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (employee_id, first_name, last_name, email, gender, dob, mobile, address, job_title, notes, status, created_at, default_schedule))
        else:
            conn.execute('''
                INSERT INTO employees (employee_id, first_name, last_name, email, gender, dob, mobile, address, job_title, notes, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (employee_id, first_name, last_name, email, gender, dob, mobile, address, job_title, notes, status, created_at))
        conn.commit()
    return employee_id

def update_employee_record(employee_id, **fields):
    allowed_fields = {'first_name', 'last_name', 'email', 'gender', 'dob', 'mobile', 'address', 'job_title', 'notes', 'schedule'}
    updates = []
    params = []
    for key, value in fields.items():
        if key in allowed_fields and value is not None:
            if key == 'schedule' and isinstance(value, dict):
                # Convert schedule dict to JSON string
                value = json.dumps(value)
            updates.append(f"{key} = ?")
            params.append(value)
    if not updates:
        return False
    params.append(employee_id)
    with get_employee_connection() as conn:
        conn.execute(f"UPDATE employees SET {', '.join(updates)} WHERE employee_id = ?", params)
        conn.commit()
    return True

def update_employee_status(employee_id, status):
    if status not in {'active', 'suspended'}:
        return False
    with get_employee_connection() as conn:
        conn.execute("UPDATE employees SET status = ? WHERE employee_id = ?", (status, employee_id))
        conn.commit()
    return True

def delete_employee_record(employee_id):
    with get_employee_connection() as conn:
        conn.execute("DELETE FROM employees WHERE employee_id = ?", (employee_id,))
        conn.commit()

def get_default_schedule():
    """Get default schedule (Mon-Fri, 9AM-5PM)"""
    return {
        'monday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'tuesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'wednesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'thursday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'friday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'saturday': {'enabled': False, 'start': '09:00', 'end': '17:00'},
        'sunday': {'enabled': False, 'start': '09:00', 'end': '17:00'}
    }

# Cache for table structure to avoid repeated PRAGMA calls
_employee_table_columns = None

def get_employee_by_id(employee_id):
    """Get employee by employee_id"""
    global _employee_table_columns
    with get_employee_connection() as conn:
        # Cache table structure check
        if _employee_table_columns is None:
            table_info = conn.execute("PRAGMA table_info(employees)").fetchall()
            _employee_table_columns = [col['name'] for col in table_info]
        
        # Build SELECT query dynamically based on available columns
        columns = ['employee_id', 'first_name', 'last_name', 'email', 'gender', 'dob', 'mobile', 'address', 'job_title', 'notes', 'status', 'created_at']
        if 'schedule' in _employee_table_columns:
            columns.append('schedule')
        if 'hourly_rate' in _employee_table_columns:
            columns.append('hourly_rate')
        if 'profile_picture' in _employee_table_columns:
            columns.append('profile_picture')
        
        query = f"SELECT {', '.join(columns)} FROM employees WHERE employee_id = ?"
        row = conn.execute(query, (employee_id,)).fetchone()
        
        if row:
            emp = dict(row)
            # Parse schedule JSON
            schedule_str = emp.get('schedule')
            if schedule_str and schedule_str.strip():
                try:
                    parsed_schedule = json.loads(schedule_str)
                    # Ensure it's a dict and has the expected structure
                    if isinstance(parsed_schedule, dict):
                        emp['schedule'] = parsed_schedule
                    else:
                        emp['schedule'] = get_default_schedule()
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    # If parsing fails, use default schedule
                    emp['schedule'] = get_default_schedule()
            else:
                emp['schedule'] = get_default_schedule()
            return emp
    return None

# Attendance functions
def get_today_attendance(employee_id, date):
    """Get today's attendance record for an employee"""
    with get_employee_connection() as conn:
        row = conn.execute(
            "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
            (employee_id, date)
        ).fetchone()
        if row:
            return dict(row)
    return None

def check_in_employee(employee_id):
    """Record employee check-in"""
    now = datetime.now()
    date = now.strftime('%Y-%m-%d')
    check_in_time = now.strftime('%Y-%m-%d %H:%M:%S')
    
    with get_employee_connection() as conn:
        # Check if attendance record exists for today
        existing = conn.execute(
            "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
            (employee_id, date)
        ).fetchone()
        
        if existing:
            # Update check-in time if not already set
            if not existing['check_in_time']:
                conn.execute(
                    "UPDATE attendance SET check_in_time = ? WHERE employee_id = ? AND date = ?",
                    (check_in_time, employee_id, date)
                )
                conn.commit()
                return True
            return False  # Already checked in
        else:
            # Create new attendance record
            conn.execute(
                "INSERT INTO attendance (employee_id, date, check_in_time, created_at) VALUES (?, ?, ?, ?)",
                (employee_id, date, check_in_time, check_in_time)
            )
            conn.commit()
            return True

def check_out_employee(employee_id):
    """Record employee check-out and calculate hours"""
    now = datetime.now()
    date = now.strftime('%Y-%m-%d')
    check_out_time = now.strftime('%Y-%m-%d %H:%M:%S')
    
    with get_employee_connection() as conn:
        # Get today's attendance record
        attendance = conn.execute(
            "SELECT * FROM attendance WHERE employee_id = ? AND date = ?",
            (employee_id, date)
        ).fetchone()
        
        if not attendance:
            return False  # No check-in found
        
        if attendance['check_out_time']:
            return False  # Already checked out
        
        # Calculate hours worked
        check_in = datetime.strptime(attendance['check_in_time'], '%Y-%m-%d %H:%M:%S')
        check_out = datetime.strptime(check_out_time, '%Y-%m-%d %H:%M:%S')
        hours_worked = (check_out - check_in).total_seconds() / 3600
        
        # Update attendance record
        conn.execute(
            "UPDATE attendance SET check_out_time = ?, hours_worked = ? WHERE employee_id = ? AND date = ?",
            (check_out_time, hours_worked, employee_id, date)
        )
        
        # Update hours_this_period in employees table
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
        if 'hours_this_period' in existing_columns:
            conn.execute(
                "UPDATE employees SET hours_this_period = COALESCE(hours_this_period, 0) + ? WHERE employee_id = ?",
                (hours_worked, employee_id)
            )
        
        conn.commit()
        return True

def get_attendance_records(employee_id=None, date=None, start_date=None, end_date=None):
    """Get attendance records with optional filters"""
    query = """
        SELECT a.*, e.first_name, e.last_name, e.job_title
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        WHERE 1=1
    """
    params = []
    
    if employee_id:
        query += " AND a.employee_id = ?"
        params.append(employee_id)
    
    if date:
        query += " AND a.date = ?"
        params.append(date)
    
    if start_date:
        query += " AND a.date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND a.date <= ?"
        params.append(end_date)
    
    query += " ORDER BY a.date DESC, a.check_in_time DESC"
    
    with get_employee_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

# Payroll functions
def get_hours_worked_today(employee_id):
    """Get hours worked today for an employee"""
    today = datetime.now().strftime('%Y-%m-%d')
    attendance = get_today_attendance(employee_id, today)
    if attendance and attendance.get('hours_worked'):
        return attendance['hours_worked']
    # If checked in but not checked out, calculate current hours
    if attendance and attendance.get('check_in_time') and not attendance.get('check_out_time'):
        check_in = datetime.strptime(attendance['check_in_time'], '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        hours = (now - check_in).total_seconds() / 3600
        return hours
    return 0.0

def get_hours_worked_this_week(employee_id):
    """Get total hours worked this week (Monday to Sunday)"""
    now = datetime.now()
    # Get Monday of current week (weekday() returns 0 for Monday, 6 for Sunday)
    days_since_monday = now.weekday()
    monday = now - timedelta(days=days_since_monday)
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = monday.strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
    records = get_attendance_records(employee_id=employee_id, start_date=start_date, end_date=end_date)
    total_hours = sum(record.get('hours_worked', 0) or 0 for record in records)
    
    # Add current session if checked in but not checked out
    today = now.strftime('%Y-%m-%d')
    today_attendance = get_today_attendance(employee_id, today)
    if today_attendance and today_attendance.get('check_in_time') and not today_attendance.get('check_out_time'):
        check_in = datetime.strptime(today_attendance['check_in_time'], '%Y-%m-%d %H:%M:%S')
        current_hours = (now - check_in).total_seconds() / 3600
        total_hours += current_hours
    
    return total_hours

def get_overtime_status(employee_id):
    """Get overtime status (hours today and this week)"""
    hours_today = get_hours_worked_today(employee_id)
    hours_week = get_hours_worked_this_week(employee_id)
    
    # Overtime: > 8 hours/day or > 40 hours/week
    is_overtime_today = hours_today > 8.0
    is_overtime_week = hours_week > 40.0
    
    return {
        'hours_today': hours_today,
        'hours_week': hours_week,
        'is_overtime_today': is_overtime_today,
        'is_overtime_week': is_overtime_week,
        'overtime_today': max(0, hours_today - 8.0) if is_overtime_today else 0.0,
        'overtime_week': max(0, hours_week - 40.0) if is_overtime_week else 0.0
    }

def get_employee_payroll_info(employee_id):
    """Get payroll information for an employee"""
    with get_employee_connection() as conn:
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
        if 'hours_this_period' not in existing_columns or 'last_paid_date' not in existing_columns:
            return {'hours_this_period': 0, 'last_paid_date': None}
        
        row = conn.execute(
            "SELECT hours_this_period, last_paid_date FROM employees WHERE employee_id = ?",
            (employee_id,)
        ).fetchone()
        
        if row:
            return {
                'hours_this_period': row['hours_this_period'] or 0,
                'last_paid_date': row['last_paid_date']
            }
    return {'hours_this_period': 0, 'last_paid_date': None}

def get_all_employees_with_payroll():
    """Get all employees with their payroll information"""
    with get_employee_connection() as conn:
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
        
        # Build SELECT query based on available columns
        columns = ['employee_id', 'first_name', 'last_name', 'job_title', 'status', 'created_at']
        if 'hours_this_period' in existing_columns:
            columns.append('hours_this_period')
        if 'last_paid_date' in existing_columns:
            columns.append('last_paid_date')
        if 'hourly_rate' in existing_columns:
            columns.append('hourly_rate')
        
        query = f"SELECT {', '.join(columns)} FROM employees WHERE status = 'active' ORDER BY first_name, last_name"
        employees = conn.execute(query).fetchall()
        
        # Add default values for missing columns and calculate effective hourly rate
        role_rates = load_role_rates()
        admin_settings = load_admin_settings()
        default_rate = admin_settings.get('hourly_rate', 15.00)
        
        result = []
        for row in employees:
            emp = dict(row)
            if 'hours_this_period' not in emp:
                emp['hours_this_period'] = 0
            if 'last_paid_date' not in emp:
                emp['last_paid_date'] = None
            if 'hourly_rate' not in emp:
                emp['hourly_rate'] = None
            
            # Calculate effective hourly rate
            emp['effective_hourly_rate'] = get_employee_hourly_rate(emp)
            result.append(emp)
        
        return result

def mark_employee_as_paid(employee_id):
    """Mark an employee as paid and reset their hours"""
    now = datetime.now()
    paid_date = now.strftime('%Y-%m-%d')
    
    with get_employee_connection() as conn:
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
        if 'hours_this_period' not in existing_columns or 'last_paid_date' not in existing_columns:
            return False
        
        conn.execute(
            "UPDATE employees SET hours_this_period = 0, last_paid_date = ? WHERE employee_id = ?",
            (paid_date, employee_id)
        )
        conn.commit()
        return True

def mark_multiple_employees_as_paid(employee_ids):
    """Mark multiple employees as paid and reset their hours"""
    now = datetime.now()
    paid_date = now.strftime('%Y-%m-%d')
    
    with get_employee_connection() as conn:
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
        if 'hours_this_period' not in existing_columns or 'last_paid_date' not in existing_columns:
            return 0
        
        if not employee_ids:
            return 0
        
        placeholders = ','.join(['?'] * len(employee_ids))
        conn.execute(
            f"UPDATE employees SET hours_this_period = 0, last_paid_date = ? WHERE employee_id IN ({placeholders})",
            [paid_date] + employee_ids
        )
        conn.commit()
        return len(employee_ids)

# Louisiana tax rate (state + local average ~9.45%)
TAX_RATE = 0.0945
DELIVERY_FEE = 5.99

# Admin configuration (use environment variables in production)
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@tastycorner.com')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize CSV files with headers if they don't exist
def init_csv_files():
    # Users CSV
    if not os.path.exists(USERS_CSV):
        with open(USERS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'email', 'password_hash', 'name', 'phone', 'address', 'created_at'])
    
    # Orders CSV
    if not os.path.exists(ORDERS_CSV):
        with open(ORDERS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['order_id', 'user_id', 'items', 'allergies', 'subtotal', 'tax', 'delivery_fee', 'tip', 'total', 'status', 'created_at', 'coupon_code', 'discount'])
    
    # Coupons CSV
    if not os.path.exists(COUPONS_CSV):
        with open(COUPONS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['code', 'discount_type', 'discount_value', 'min_order', 'max_discount', 'usage_limit', 'used_count', 'expiry_date', 'is_active'])
    
    # Menu CSV
    if not os.path.exists(MENU_CSV):
        with open(MENU_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['item_id', 'name', 'description', 'price', 'category', 'image'])
        # Add sample menu items
        sample_items = [
            # Appetizers
            ['1', 'Chicken Wings', 'Crispy chicken wings with your choice of sauce', '11.99', 'Appetizers', 'wings.jpg'],
            ['2', 'Mozzarella Sticks', 'Golden fried mozzarella with marinara sauce', '8.99', 'Appetizers', 'mozzarella.jpg'],
            ['3', 'Buffalo Cauliflower', 'Crispy cauliflower tossed in buffalo sauce with blue cheese dip', '9.99', 'Appetizers', 'cauliflower.jpg'],
            ['4', 'Loaded Nachos', 'Tortilla chips topped with cheese, jalapeños, sour cream, and guacamole', '10.99', 'Appetizers', 'nachos.jpg'],
            ['5', 'Shrimp Cocktail', 'Fresh jumbo shrimp with cocktail sauce', '12.99', 'Appetizers', 'shrimp.jpg'],
            ['6', 'Onion Rings', 'Beer-battered onion rings with chipotle aioli', '7.99', 'Appetizers', 'rings.jpg'],
            
            # Salads
            ['7', 'Caesar Salad', 'Fresh romaine lettuce with parmesan, croutons, and Caesar dressing', '10.99', 'Salads', 'caesar.jpg'],
            ['8', 'Garden Salad', 'Mixed greens with tomatoes, cucumbers, carrots, and house vinaigrette', '9.99', 'Salads', 'garden.jpg'],
            ['9', 'Cobb Salad', 'Romaine, grilled chicken, bacon, eggs, avocado, and blue cheese', '13.99', 'Salads', 'cobb.jpg'],
            ['10', 'Greek Salad', 'Fresh vegetables, feta cheese, olives, and Greek dressing', '11.99', 'Salads', 'greek_salad.jpg'],
            
            # Main Course
            ['11', 'Classic Burger', 'Juicy beef patty with lettuce, tomato, onion, and special sauce', '12.99', 'Main Course', 'burger.jpg'],
            ['12', 'BBQ Bacon Burger', 'Beef patty with crispy bacon, cheddar, BBQ sauce, and onion rings', '14.99', 'Main Course', 'bbq-burger.jpg'],
            ['13', 'Margherita Pizza', 'Classic pizza with tomato sauce, mozzarella, and basil', '14.99', 'Main Course', 'pizza.jpg'],
            ['14', 'Pepperoni Pizza', 'Classic pepperoni pizza with mozzarella cheese', '15.99', 'Main Course', 'pepperoni.jpg'],
            ['15', 'Grilled Chicken', 'Tender grilled chicken breast with vegetables and mashed potatoes', '16.99', 'Main Course', 'chicken.jpg'],
            ['16', 'Fish & Chips', 'Beer-battered fish with crispy fries', '13.99', 'Main Course', 'fish.jpg'],
            ['17', 'Ribeye Steak', '12oz ribeye steak cooked to perfection with sides', '24.99', 'Main Course', 'steak.jpg'],
            ['18', 'Pasta Carbonara', 'Creamy pasta with bacon, parmesan, and black pepper', '15.99', 'Main Course', 'carbonara.jpg'],
            ['19', 'Shrimp Scampi', 'Garlic butter shrimp over linguine pasta', '17.99', 'Main Course', 'scampi.jpg'],
            ['20', 'BBQ Ribs', 'Fall-off-the-bone ribs with BBQ sauce and coleslaw', '18.99', 'Main Course', 'ribs.jpg'],
            ['21', 'Chicken Parmesan', 'Breaded chicken with marinara and mozzarella over pasta', '16.99', 'Main Course', 'chicken-parm.jpg'],
            ['22', 'Seafood Platter', 'Grilled fish, shrimp, and scallops with vegetables', '22.99', 'Main Course', 'seafood.jpg'],
            
            # Desserts
            ['23', 'Chocolate Cake', 'Rich chocolate cake with vanilla ice cream', '7.99', 'Desserts', 'cake.jpg'],
            ['24', 'Cheesecake', 'New York style cheesecake with berry compote', '8.99', 'Desserts', 'cheesecake.jpg'],
            ['25', 'Apple Pie', 'Warm apple pie with vanilla ice cream', '7.99', 'Desserts', 'apple-pie.jpg'],
            ['26', 'Ice Cream Sundae', 'Vanilla ice cream with hot fudge, nuts, and whipped cream', '6.99', 'Desserts', 'sundae.jpg'],
            ['27', 'Tiramisu', 'Classic Italian dessert with coffee and mascarpone', '8.99', 'Desserts', 'tiramisu.jpg'],
            ['28', 'Brownie Delight', 'Warm brownie with ice cream and chocolate sauce', '7.99', 'Desserts', 'brownie.jpg'],
            
            # Beverages
            ['29', 'Fresh Lemonade', 'House-made lemonade, sweet and refreshing', '3.99', 'Beverages', 'lemonade.jpg'],
            ['30', 'Iced Tea', 'Freshly brewed iced tea, sweet or unsweetened', '2.99', 'Beverages', 'iced-tea.jpg'],
            ['31', 'Soft Drinks', 'Coca-Cola, Pepsi, Sprite, or Dr. Pepper', '2.49', 'Beverages', 'soda.jpg'],
            ['32', 'Fresh Orange Juice', 'Freshly squeezed orange juice', '4.99', 'Beverages', 'orange-juice.jpg'],
        ]
        with open(MENU_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerows(sample_items)
    
    if not os.path.exists(CATEGORIES_CSV):
        default_categories = ['Appetizers', 'Salads', 'Main Course', 'Desserts', 'Beverages']
        with open(CATEGORIES_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['category'])
            for category in default_categories:
                writer.writerow([category])
    
init_csv_files()
init_employee_db()

def get_user_by_email(email):
    """Get user by email from CSV"""
    if not os.path.exists(USERS_CSV):
        return None
    with open(USERS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['email'] == email:
                return row
    return None

def create_user(email, password, name, phone, address):
    """Create a new user in CSV"""
    # Get next user_id
    user_id = 1
    if os.path.exists(USERS_CSV):
        with open(USERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                user_id = int(rows[-1]['user_id']) + 1
    
    password_hash = generate_password_hash(password)
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with open(USERS_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, email, password_hash, name, phone, address, created_at])
    
    return user_id

# Cache for menu items to avoid repeated file reads
_menu_items_cache = None
_menu_items_cache_time = None
MENU_CACHE_DURATION = 60  # Cache for 60 seconds

def get_menu_items():
    """Get all menu items from CSV with caching"""
    global _menu_items_cache, _menu_items_cache_time
    
    # Check if cache is valid
    if _menu_items_cache is not None and _menu_items_cache_time is not None:
        cache_age = (datetime.now() - _menu_items_cache_time).total_seconds()
        if cache_age < MENU_CACHE_DURATION:
            return _menu_items_cache
    
    # Load from file
    if not os.path.exists(MENU_CSV):
        return []
    items = []
    with open(MENU_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['price'] = float(row['price'])
            items.append(row)
    
    # Update cache
    _menu_items_cache = items
    _menu_items_cache_time = datetime.now()
    return items

def save_menu_items(items):
    """Persist menu items to CSV"""
    global _menu_items_cache, _menu_items_cache_time
    with open(MENU_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['item_id', 'name', 'description', 'price', 'category', 'image'])
        for item in items:
            writer.writerow([
                item['item_id'],
                item['name'],
                item['description'],
                f"{float(item['price']):.2f}",
                item['category'],
                item.get('image', '')
            ])
    # Invalidate cache when menu is updated
    _menu_items_cache = None
    _menu_items_cache_time = None

def get_all_orders():
    """Return all orders (admin view)"""
    orders = []
    if os.path.exists(ORDERS_CSV):
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['items'] = json.loads(row['items'])
                row['allergies'] = json.loads(row['allergies'])
                # Handle legacy orders without coupon fields
                if 'coupon_code' not in row:
                    row['coupon_code'] = ''
                    row['discount'] = '0.00'
                orders.append(row)
    orders.sort(key=lambda x: x['created_at'], reverse=True)
    return orders

def save_orders(orders):
    """Persist orders to CSV"""
    with open(ORDERS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['order_id', 'user_id', 'items', 'allergies', 'subtotal', 'tax', 'delivery_fee', 'tip', 'total', 'status', 'created_at', 'coupon_code', 'discount'])
        for order in orders:
            writer.writerow([
                order['order_id'],
                order['user_id'],
                json.dumps(order['items']),
                json.dumps(order.get('allergies', [])),
                order['subtotal'],
                order['tax'],
                order['delivery_fee'],
                order['tip'],
                order['total'],
                order['status'],
                order['created_at'],
                order.get('coupon_code', ''),
                order.get('discount', '0.00')
            ])

def save_order(user_id, items, allergies, subtotal, tax, delivery_fee, tip, total, coupon_code='', discount=0.0):
    """Save order to CSV"""
    order_id = 1
    if os.path.exists(ORDERS_CSV):
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                order_id = int(rows[-1]['order_id']) + 1
    
    items_json = json.dumps(items)
    allergies_json = json.dumps(allergies) if allergies else '[]'
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Check if CSV has new columns, if not we need to handle migration
    file_exists = os.path.exists(ORDERS_CSV)
    has_coupon_fields = True  # Default to new format with coupon fields
    if file_exists:
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            has_coupon_fields = header and 'coupon_code' in header
    
    # Check if file exists, if not create it with header
    with open(ORDERS_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write header if file doesn't exist (always use new format for new files)
        if not file_exists:
            writer.writerow(['order_id', 'user_id', 'items', 'allergies', 'subtotal', 'tax', 'delivery_fee', 'tip', 'total', 'status', 'created_at', 'coupon_code', 'discount'])
        
        if has_coupon_fields:
            writer.writerow([
                order_id,
                user_id,
                items_json,
                allergies_json,
                f"{float(subtotal):.2f}",
                f"{float(tax):.2f}",
                f"{float(delivery_fee):.2f}",
                f"{float(tip):.2f}",
                f"{float(total):.2f}",
                'pending',
                created_at,
                coupon_code,
                f"{float(discount):.2f}"
            ])
        else:
            # Legacy format
            writer.writerow([
                order_id,
                user_id,
                items_json,
                allergies_json,
                f"{float(subtotal):.2f}",
                f"{float(tax):.2f}",
                f"{float(delivery_fee):.2f}",
                f"{float(tip):.2f}",
                f"{float(total):.2f}",
                'pending',
                created_at
            ])
    
    return order_id

# Coupon management functions
def get_coupons():
    """Get all coupons"""
    coupons = []
    if os.path.exists(COUPONS_CSV):
        with open(COUPONS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['discount_value'] = float(row['discount_value'])
                row['min_order'] = float(row.get('min_order', 0))
                row['max_discount'] = float(row.get('max_discount', 0)) if row.get('max_discount') else None
                row['usage_limit'] = int(row.get('usage_limit', 0)) if row.get('usage_limit') else None
                row['used_count'] = int(row.get('used_count', 0))
                row['is_active'] = row.get('is_active', 'true').lower() == 'true'
                coupons.append(row)
    return coupons

def get_coupon_by_code(code):
    """Get coupon by code"""
    coupons = get_coupons()
    for coupon in coupons:
        if coupon['code'].upper() == code.upper():
            return coupon
    return None

def validate_coupon(code, subtotal):
    """Validate and calculate discount for a coupon"""
    coupon = get_coupon_by_code(code)
    if not coupon:
        return None, "Coupon code not found"
    
    if not coupon['is_active']:
        return None, "Coupon is not active"
    
    # Check expiry date
    if coupon.get('expiry_date'):
        try:
            expiry = datetime.strptime(coupon['expiry_date'], '%Y-%m-%d')
            if datetime.now() > expiry:
                return None, "Coupon has expired"
        except ValueError:
            pass
    
    # Check minimum order
    if subtotal < coupon['min_order']:
        return None, f"Minimum order of ${coupon['min_order']:.2f} required"
    
    # Check usage limit
    if coupon['usage_limit'] and coupon['used_count'] >= coupon['usage_limit']:
        return None, "Coupon usage limit reached"
    
    # Calculate discount
    if coupon['discount_type'] == 'percentage':
        discount = subtotal * (coupon['discount_value'] / 100)
        if coupon['max_discount']:
            discount = min(discount, coupon['max_discount'])
    else:  # fixed
        discount = coupon['discount_value']
    
    return discount, None

def apply_coupon(code):
    """Increment coupon usage count"""
    coupons = get_coupons()
    for coupon in coupons:
        if coupon['code'].upper() == code.upper():
            coupon['used_count'] += 1
            save_coupons(coupons)
            return True
    return False

def save_coupons(coupons):
    """Save coupons to CSV"""
    with open(COUPONS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['code', 'discount_type', 'discount_value', 'min_order', 'max_discount', 'usage_limit', 'used_count', 'expiry_date', 'is_active'])
        for coupon in coupons:
            writer.writerow([
                coupon['code'],
                coupon['discount_type'],
                f"{float(coupon['discount_value']):.2f}",
                f"{float(coupon.get('min_order', 0)):.2f}",
                f"{float(coupon['max_discount']):.2f}" if coupon.get('max_discount') else '',
                str(coupon['usage_limit']) if coupon.get('usage_limit') else '',
                str(coupon.get('used_count', 0)),
                coupon.get('expiry_date', ''),
                'true' if coupon.get('is_active', True) else 'false'
            ])

def is_admin():
    return session.get('is_admin') is True

def render_admin_dashboard():
    menu_items = get_menu_items()
    categories = get_categories()
    profile = load_admin_profile()

    menu_category_set = set(item['category'] for item in menu_items)
    combined_categories = sorted(menu_category_set.union(categories))
    if combined_categories != categories:
        categories = save_categories(combined_categories)

    menu_search = request.args.get('menu_search', '').strip().lower()
    menu_category = request.args.get('menu_category', '').strip()

    filtered_items = menu_items
    if menu_search:
        filtered_items = [item for item in filtered_items if menu_search in item['name'].lower() or menu_search in item['description'].lower()]
    if menu_category:
        filtered_items = [item for item in filtered_items if item['category'] == menu_category]

    orders = get_all_orders()
    user_map = get_user_map()
    for order in orders:
        order['customer_name'] = user_map.get(order['user_id'], 'Guest Customer')

    order_search = request.args.get('order_search', '').strip().lower()
    order_status = request.args.get('order_status', '').strip()

    filtered_orders = orders
    if order_search:
        def matches(order):
            return (order_search in str(order['order_id']).lower() or
                    order_search in order['customer_name'].lower() or
                    order_search in order['created_at'].lower())
        filtered_orders = [order for order in filtered_orders if matches(order)]
    if order_status:
        filtered_orders = [order for order in filtered_orders if order['status'] == order_status]

    total_orders = len(orders)
    total_revenue = sum(float(order['total']) for order in orders) if orders else 0
    pending_orders = sum(1 for order in orders if order['status'] == 'pending')
    completed_orders = sum(1 for order in orders if order['status'] == 'completed')
    average_order_value = total_revenue / total_orders if total_orders else 0
    average_tip = sum(float(order['tip']) for order in orders) / total_orders if total_orders else 0

    new_order_alert = session.pop('has_new_order', False)

    initial_section = request.args.get('section')
    if not initial_section:
        if order_search or order_status or new_order_alert:
            initial_section = 'orders'
        else:
            initial_section = 'overview'

    sales_per_day = {}
    sales_by_week = {}
    sales_by_month = {}
    most_ordered = {}
    orders_by_status = {}
    category_sales = {}
    hour_count = {}
    item_category_map = {item['item_id']: item['category'] for item in menu_items}

    orders_sorted = sorted(orders, key=lambda x: x['created_at'])
    seen_users = set()
    new_customers = 0
    returning_customers = 0

    for order in orders_sorted:
        date_string = order['created_at']
        try:
            dt = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            dt = datetime.strptime(date_string.split('.')[0], '%Y-%m-%d %H:%M:%S')
        date_key = dt.date().isoformat()
        week_key = f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"
        month_key = dt.strftime('%Y-%m')

        sales_per_day[date_key] = sales_per_day.get(date_key, 0) + float(order['total'])
        sales_by_week[week_key] = sales_by_week.get(week_key, 0) + float(order['total'])
        sales_by_month[month_key] = sales_by_month.get(month_key, 0) + float(order['total'])
        hour = dt.hour
        hour_count[hour] = hour_count.get(hour, 0) + 1

        status = order['status']
        orders_by_status[status] = orders_by_status.get(status, 0) + 1

        user_id = order['user_id']
        if user_id not in seen_users:
            new_customers += 1
            seen_users.add(user_id)
        else:
            returning_customers += 1

        for item in order['items']:
            most_ordered[item['name']] = most_ordered.get(item['name'], 0) + item['quantity']
            category = item_category_map.get(str(item.get('item_id', '')), item.get('category', 'Other'))
            category_sales[category] = category_sales.get(category, 0) + float(item['price']) * item['quantity']

    busiest_hour = max(hour_count, key=lambda h: hour_count[h]) if hour_count else None

    sales_labels = sorted(sales_per_day.keys())
    sales_values = [round(sales_per_day[label], 2) for label in sales_labels]

    weekly_labels = sorted(sales_by_week.keys())[-8:]
    weekly_values = [round(sales_by_week[label], 2) for label in weekly_labels]

    monthly_labels = sorted(sales_by_month.keys())[-12:]
    monthly_values = [round(sales_by_month[label], 2) for label in monthly_labels]

    most_ordered_sorted = sorted(most_ordered.items(), key=lambda x: x[1], reverse=True)[:7]
    most_labels = [item[0] for item in most_ordered_sorted]
    most_values = [item[1] for item in most_ordered_sorted]

    status_labels = list(orders_by_status.keys())
    status_values = [orders_by_status[label] for label in status_labels]

    category_sorted = sorted(category_sales.items(), key=lambda x: x[1], reverse=True)
    category_labels = [item[0] for item in category_sorted]
    category_values = [round(item[1], 2) for item in category_sorted]
    top_category = category_sorted[0][0] if category_sorted else 'N/A'

    customer_chart = {
        'labels': ['New Customers', 'Returning Customers'],
        'values': [new_customers, returning_customers]
    }

    sales_chart = {
        'labels': sales_labels,
        'values': sales_values
    }

    weekly_chart = {
        'labels': weekly_labels,
        'values': weekly_values
    }

    monthly_chart = {
        'labels': monthly_labels,
        'values': monthly_values
    }

    top_items_chart = {
        'labels': most_labels,
        'values': most_values
    }

    status_chart = {
        'labels': status_labels,
        'values': status_values
    }

    category_chart = {
        'labels': category_labels,
        'values': category_values
    }

    employee_search = request.args.get('employee_search', '').strip()
    employee_status_filter = request.args.get('employee_status', '').strip()
    all_employees = get_employees()
    employee_count = len(all_employees)
    employees_display = get_employees(
        search_query=employee_search or None,
        status_filter=employee_status_filter or None
    ) if (employee_search or employee_status_filter) else all_employees
    recent_employees = all_employees[:5]
    gender_counts = {}
    role_counts = {}
    complete_profiles = 0
    status_counts = {}
    for employee in all_employees:
        gender_label = employee.get('gender') or 'Not set'
        gender_counts[gender_label] = gender_counts.get(gender_label, 0) + 1

        job_title = employee.get('job_title') or 'Unassigned'
        role_counts[job_title] = role_counts.get(job_title, 0) + 1

        if employee.get('email') and employee.get('mobile') and employee.get('address'):
            complete_profiles += 1
        
        status_label = employee.get('status') or 'active'
        status_counts[status_label] = status_counts.get(status_label, 0) + 1

    latest_employee = all_employees[0] if all_employees else None
    top_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:4]
    completion_rate = round((complete_profiles / employee_count) * 100, 1) if employee_count else 0
    active_count = status_counts.get('active', 0)
    suspended_count = status_counts.get('suspended', 0)

    recent_activity = []
    for order in sorted(orders, key=lambda x: x['created_at'], reverse=True)[:12]:
        recent_activity.append({
            'order_id': order['order_id'],
            'created_at': order['created_at'],
            'customer': order['customer_name'],
            'total': f"${float(order['total']):.2f}",
            'status': order['status']
        })

    busiest_hour_label = f"{busiest_hour:02d}:00" if busiest_hour is not None else 'N/A'

    # Build job categories for dropdown: defaults + existing job titles (excluding placeholders)
    existing_titles = sorted(t for t in role_counts.keys() if t and t.lower() not in {'unassigned', 'none', 'n/a'})
    job_categories = sorted(set(JOB_CATEGORIES_DEFAULT).union(existing_titles))

    # Get attendance records for today
    today = datetime.now().strftime('%Y-%m-%d')
    today_attendance = get_attendance_records(date=today)
    
    # Get date filter for attendance
    attendance_date = request.args.get('attendance_date', today)
    attendance_employee = request.args.get('attendance_employee', '')
    
    # Get attendance records with filters
    attendance_records = get_attendance_records(
        employee_id=attendance_employee if attendance_employee else None,
        date=attendance_date if attendance_date != today else None,
        start_date=attendance_date if attendance_date != today else None,
        end_date=attendance_date if attendance_date != today else None
    )

    # Get role rates and admin settings
    role_rates = load_role_rates()
    admin_settings = load_admin_settings()
    
    return render_template(
        'admin/dashboard.html',
        menu_items=filtered_items,
        all_categories=categories,
        menu_search=request.args.get('menu_search', ''),
        menu_category=menu_category,
        admin_email=session.get('admin_email', ADMIN_EMAIL),
        profile=profile,
        orders=orders,
        orders_display=filtered_orders,
        order_search=order_search,
        order_status=order_status,
        status_options=['pending', 'preparing', 'out_for_delivery', 'completed', 'cancelled'],
        total_orders=total_orders,
        pending_orders=pending_orders,
        completed_orders=completed_orders,
        total_revenue=total_revenue,
        average_order_value=average_order_value,
        average_tip=average_tip,
        top_category=top_category,
        busiest_hour=busiest_hour_label,
        new_order_alert=new_order_alert,
        initial_section=initial_section,
        sales_chart=json.dumps(sales_chart),
        weekly_chart=json.dumps(weekly_chart),
        monthly_chart=json.dumps(monthly_chart),
        top_items_chart=json.dumps(top_items_chart),
        customer_chart=json.dumps(customer_chart),
        status_chart=json.dumps(status_chart),
        category_chart=json.dumps(category_chart),
        recent_activity=recent_activity,
        employees=employees_display,
        employee_search=employee_search,
        employee_count=employee_count,
        role_rates=role_rates,
        admin_settings=admin_settings,
        recent_employees=recent_employees,
        latest_employee=latest_employee,
        gender_counts=gender_counts,
        top_roles=top_roles,
        completion_rate=completion_rate,
        status_counts=status_counts,
        active_count=active_count,
        suspended_count=suspended_count,
        employee_status_filter=employee_status_filter,
        job_categories=job_categories,
        today_attendance=today_attendance,
        attendance_records=attendance_records,
        attendance_date=attendance_date,
        attendance_employee=attendance_employee,
        today=today,
        payroll_employees=get_all_employees_with_payroll()
    )

def load_admin_profile():
    if os.path.exists(ADMIN_PROFILE_JSON):
        with open(ADMIN_PROFILE_JSON, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {
        'name': 'Administrator',
        'title': 'Site Manager',
        'bio': 'Managing the TastyCorner experience—where every bite tells a story!',
        'avatar': 'admin-avatar.png'
    }

def save_admin_profile(profile):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ADMIN_PROFILE_JSON, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2)
    return profile

def load_admin_settings():
    """Load admin settings (hourly rate, etc.)"""
    if os.path.exists(ADMIN_SETTINGS_JSON):
        with open(ADMIN_SETTINGS_JSON, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {
        'hourly_rate': 15.00
    }

def save_admin_settings(settings):
    """Save admin settings"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ADMIN_SETTINGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    return settings

def load_role_rates():
    """Load role-based hourly rates"""
    if os.path.exists(ROLE_RATES_JSON):
        with open(ROLE_RATES_JSON, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {}

def save_role_rates(role_rates):
    """Save role-based hourly rates"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ROLE_RATES_JSON, 'w', encoding='utf-8') as f:
        json.dump(role_rates, f, indent=2)
    return role_rates

def get_employee_hourly_rate(employee):
    """Get hourly rate for an employee (individual rate or role-based rate or default)"""
    # First check if employee has individual rate
    if employee.get('hourly_rate'):
        return float(employee['hourly_rate'])
    
    # Then check role-based rate
    job_title = employee.get('job_title', '').strip()
    if job_title:
        role_rates = load_role_rates()
        if job_title in role_rates:
            return float(role_rates[job_title])
    
    # Fallback to default from admin settings
    admin_settings = load_admin_settings()
    return admin_settings.get('hourly_rate', 15.00)

@app.route('/')
def index():
    """Home page"""
    # Get featured menu items for Chef's Specials section
    menu_items = get_menu_items()
    featured_items = []
    featured_names = ['Classic Burger', 'Margherita Pizza', 'Chicken Wings', 'Chocolate Cake']
    for item in menu_items:
        if item['name'] in featured_names:
            featured_items.append(item)
    # Sort to maintain order: Classic Burger, Margherita Pizza, Chicken Wings, Chocolate Cake
    featured_items.sort(key=lambda x: featured_names.index(x['name']) if x['name'] in featured_names else 999)
    
    return render_template('index.html', featured_items=featured_items)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """User signup"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        
        if not all([email, password, name, phone, address]):
            flash('Please fill in all fields', 'error')
            return render_template('signup.html')
        
        # Check if user already exists
        if get_user_by_email(email):
            flash('Email already registered. Please sign in.', 'error')
            return render_template('signup.html')
        
        # Create user
        user_id = create_user(email, password, name, phone, address)
        flash('Account created successfully! Please sign in.', 'success')
        return redirect(url_for('signin'))
    
    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    """User signin"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter email and password', 'error')
            return render_template('signin.html')
        
        user = get_user_by_email(email)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('menu'))
        else:
            flash('Invalid email or password', 'error')
            return render_template('signin.html')
    
    return render_template('signin.html')

@app.route('/signout')
def signout():
    """User signout"""
    session.clear()
    flash('You have been signed out', 'info')
    return redirect(url_for('index'))

@app.route('/menu')
def menu():
    """Menu page"""
    items = get_menu_items()
    
    # Get search query
    search_query = request.args.get('search', '').lower()
    category_filter = request.args.get('category', '')
    
    # Filter items by search query
    if search_query:
        items = [item for item in items if search_query in item['name'].lower() or search_query in item['description'].lower()]
    
    # Filter by category
    if category_filter:
        items = [item for item in items if item['category'] == category_filter]
    
    # Group items by category
    categories = {}
    all_categories = set()
    for item in items:
        category = item['category']
        all_categories.add(category)
        if category not in categories:
            categories[category] = []
        categories[category].append(item)
    
    # Get all unique categories for filter buttons
    all_items = get_menu_items()
    all_categories_list = sorted(set(item['category'] for item in all_items))
    
    # Get wishlist item IDs for easy checking in template
    wishlist_ids = []
    if 'wishlist' in session:
        wishlist_ids = [w['item_id'] for w in session['wishlist']]
    
    return render_template('menu.html', 
                         categories=categories, 
                         all_categories=all_categories_list,
                         search_query=request.args.get('search', ''),
                         category_filter=category_filter,
                         wishlist_ids=wishlist_ids, 
                         user_name=session.get('user_name'))

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    """Shopping cart"""
    if 'user_id' not in session:
        flash('Please sign in to view your cart', 'error')
        return redirect(url_for('signin'))
    
    if request.method == 'POST':
        # Add item to cart
        item_id = request.form.get('item_id')
        quantity = int(request.form.get('quantity', 1))
        allergies = request.form.get('allergies', '')
        
        if 'cart' not in session:
            session['cart'] = []
        
        items = get_menu_items()
        item = next((i for i in items if i['item_id'] == item_id), None)
        
        if item:
            cart_item = {
                'item_id': item_id,
                'name': item['name'],
                'price': float(item['price']),
                'quantity': quantity,
                'allergies': allergies
            }
            session['cart'].append(cart_item)
            session.modified = True
            flash(f'{item["name"]} added to cart!', 'success')
        
        return redirect(url_for('menu'))
    
    cart = session.get('cart', [])
    subtotal = sum(item['price'] * item['quantity'] for item in cart)
    
    return render_template('cart.html', cart=cart, subtotal=subtotal, user_name=session.get('user_name'))

@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    """Update item quantity in cart"""
    if 'user_id' not in session:
        flash('Please sign in', 'error')
        return redirect(url_for('signin'))
    
    index = int(request.form.get('index', -1))
    quantity = int(request.form.get('quantity', 1))
    
    if 'cart' in session and 0 <= index < len(session['cart']):
        if quantity <= 0:
            # Remove item if quantity is 0 or less
            item_name = session['cart'][index]['name']
            session['cart'].pop(index)
            session.modified = True
            flash(f'{item_name} removed from cart', 'info')
        else:
            session['cart'][index]['quantity'] = quantity
            session.modified = True
            flash('Cart updated', 'success')
    
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:index>')
def remove_from_cart(index):
    """Remove item from cart"""
    if 'cart' in session and 0 <= index < len(session['cart']):
        item_name = session['cart'][index]['name']
        session['cart'].pop(index)
        session.modified = True
        flash(f'{item_name} removed from cart', 'info')
    return redirect(url_for('cart'))

@app.route('/wishlist', methods=['GET', 'POST'])
def wishlist():
    """Favorites page"""
    if 'user_id' not in session:
        flash('Please sign in to view your favorites', 'error')
        return redirect(url_for('signin'))
    
    if request.method == 'POST':
        # Add item to wishlist
        item_id = request.form.get('item_id')
        
        if 'wishlist' not in session:
            session['wishlist'] = []
        
        items = get_menu_items()
        item = next((i for i in items if i['item_id'] == item_id), None)
        
        if item:
            # Check if item already in wishlist
            wishlist_item_ids = [w['item_id'] for w in session['wishlist']]
            if item_id not in wishlist_item_ids:
                wishlist_item = {
                    'item_id': item_id,
                    'name': item['name'],
                    'price': float(item['price']),
                    'description': item['description'],
                    'image': item['image']
                }
                session['wishlist'].append(wishlist_item)
                session.modified = True
                flash(f'{item["name"]} added to wishlist!', 'success')
            else:
                flash(f'{item["name"]} is already in your wishlist', 'info')
        
        return redirect(url_for('menu'))
    
    wishlist = session.get('wishlist', [])
    return render_template('wishlist.html', wishlist=wishlist, user_name=session.get('user_name'))

@app.route('/remove_from_wishlist/<int:index>')
def remove_from_wishlist(index):
    """Remove item from favorites"""
    if 'wishlist' in session and 0 <= index < len(session['wishlist']):
        item_name = session['wishlist'][index]['name']
        session['wishlist'].pop(index)
        session.modified = True
        flash(f'{item_name} removed from favorites', 'info')
    return redirect(url_for('wishlist'))

@app.route('/add_wishlist_to_cart/<int:index>')
def add_wishlist_to_cart(index):
    """Add favorites item to cart"""
    if 'wishlist' in session and 0 <= index < len(session['wishlist']):
        wishlist_item = session['wishlist'][index]
        
        if 'cart' not in session:
            session['cart'] = []
        
        cart_item = {
            'item_id': wishlist_item['item_id'],
            'name': wishlist_item['name'],
            'price': wishlist_item['price'],
            'quantity': 1,
            'allergies': ''
        }
        session['cart'].append(cart_item)
        session.modified = True
        flash(f'{wishlist_item["name"]} added to cart!', 'success')
    
    return redirect(url_for('wishlist'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """Checkout page"""
    if 'user_id' not in session:
        flash('Please sign in to checkout', 'error')
        return redirect(url_for('signin'))
    
    cart = session.get('cart', [])
    if not cart:
        flash('Your cart is empty', 'error')
        return redirect(url_for('menu'))
    
    if request.method == 'POST':
        # Process order
        tip_percentage = request.form.get('tip_percentage')
        custom_tip = request.form.get('custom_tip')
        coupon_code = request.form.get('coupon_code', '').strip().upper()
        
        subtotal = sum(item['price'] * item['quantity'] for item in cart)
        
        # Apply coupon if provided
        discount = 0.0
        applied_coupon = ''
        if coupon_code:
            discount, error_msg = validate_coupon(coupon_code, subtotal)
            if error_msg:
                flash(f'Coupon error: {error_msg}', 'error')
                return redirect(url_for('checkout'))
            applied_coupon = coupon_code
            apply_coupon(coupon_code)
        
        # Apply discount to subtotal
        subtotal_after_discount = max(0, subtotal - discount)
        
        tax = subtotal_after_discount * TAX_RATE
        delivery_fee = DELIVERY_FEE
        
        # Calculate tip (on original subtotal before discount)
        tip = 0
        if tip_percentage == 'custom' and custom_tip:
            tip = float(custom_tip)
        elif tip_percentage and tip_percentage != 'no_tip':
            tip_percent = float(tip_percentage.replace('%', '')) / 100
            tip = subtotal * tip_percent
        
        total = subtotal_after_discount + tax + delivery_fee + tip
        
        # Collect allergies from all items
        allergies = []
        for item in cart:
            if item.get('allergies'):
                allergies.append(f"{item['name']}: {item['allergies']}")
        
        # Save order
        order_id = save_order(
            session['user_id'],
            cart,
            allergies,
            round(subtotal, 2),
            round(tax, 2),
            delivery_fee,
            round(tip, 2),
            round(total, 2),
            applied_coupon,
            round(discount, 2)
        )
        
        session['cart'] = []
        session.modified = True
        session['has_new_order'] = True
        
        flash(f'Order #{order_id} placed successfully! Total: ${total:.2f}', 'success')
        return redirect(url_for('order_confirmation', order_id=order_id))
    
    subtotal = sum(item['price'] * item['quantity'] for item in cart)
    
    # Get applied coupon from session if any
    applied_coupon = session.get('applied_coupon', '')
    discount = 0.0
    if applied_coupon:
        discount, _ = validate_coupon(applied_coupon, subtotal)
        if discount is None:
            discount = 0.0
    
    # Calculate tax on discounted subtotal
    subtotal_after_discount = max(0, subtotal - discount)
    tax = subtotal_after_discount * TAX_RATE
    delivery_fee = DELIVERY_FEE
    
    return render_template('checkout.html', 
                         cart=cart, 
                         subtotal=round(subtotal, 2),
                         tax=round(tax, 2),
                         tax_rate=TAX_RATE * 100,
                         delivery_fee=delivery_fee,
                         discount=round(discount, 2),
                         applied_coupon=applied_coupon,
                         user_name=session.get('user_name'))

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Admin dashboard / login"""
    if is_admin():
        return render_admin_dashboard()
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            session['admin_email'] = email
            flash('Welcome back, Admin!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid admin credentials', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_email', None)
    flash('Admin signed out', 'info')
    return redirect(url_for('admin'))

@app.route('/admin/profile', methods=['POST'])
def admin_update_profile():
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    profile = load_admin_profile()
    profile['name'] = request.form.get('name', profile.get('name', '')).strip() or profile.get('name', '')
    profile['title'] = request.form.get('title', profile.get('title', '')).strip() or profile.get('title', '')
    profile['bio'] = request.form.get('bio', profile.get('bio', '')).strip() or profile.get('bio', '')

    avatar_file = request.files.get('avatar')
    if avatar_file and avatar_file.filename:
        avatar_filename = save_uploaded_image(avatar_file)
        if avatar_filename:
            profile['avatar'] = avatar_filename

    save_admin_profile(profile)
    flash('Profile updated successfully', 'success')
    return redirect(request.referrer or url_for('admin'))

@app.route('/admin/settings', methods=['POST'])
def admin_update_settings():
    """Update admin settings"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    settings = load_admin_settings()
    hourly_rate = request.form.get('hourly_rate', '').strip()
    
    if hourly_rate:
        try:
            settings['hourly_rate'] = float(hourly_rate)
            if settings['hourly_rate'] < 0:
                flash('Hourly rate cannot be negative', 'error')
                return redirect(request.referrer or url_for('admin', section='settings'))
            save_admin_settings(settings)
            flash('Settings updated successfully', 'success')
        except ValueError:
            flash('Invalid hourly rate value', 'error')
    else:
        flash('Hourly rate is required', 'error')
    
    return redirect(request.referrer or url_for('admin', section='settings'))

@app.route('/admin/role-rates', methods=['POST'])
def admin_update_role_rates():
    """Update role-based hourly rates"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    role_rates = load_role_rates()
    
    # Get all role rates from form
    for key, value in request.form.items():
        if key.startswith('role_rate_'):
            role = key.replace('role_rate_', '')
            try:
                rate = float(value.strip())
                if rate >= 0:
                    role_rates[role] = rate
                else:
                    flash(f'Invalid rate for {role}: rate cannot be negative', 'error')
            except ValueError:
                if value.strip():  # Only error if value is not empty
                    flash(f'Invalid rate for {role}: must be a number', 'error')
    
    save_role_rates(role_rates)
    flash('Role rates updated successfully', 'success')
    return redirect(request.referrer or url_for('admin', section='payroll'))

@app.route('/admin/employee-rate', methods=['POST'])
def admin_update_employee_rate():
    """Update individual employee hourly rate"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    employee_id = request.form.get('employee_id', '').strip()
    hourly_rate = request.form.get('hourly_rate', '').strip()
    
    if not employee_id:
        flash('Employee ID is required', 'error')
        return redirect(request.referrer or url_for('admin', section='payroll'))
    
    if not hourly_rate:
        # Clear individual rate (will use role-based or default)
        with get_employee_connection() as conn:
            existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
            if 'hourly_rate' in existing_columns:
                conn.execute(
                    "UPDATE employees SET hourly_rate = NULL WHERE employee_id = ?",
                    (employee_id,)
                )
                conn.commit()
        flash('Employee hourly rate cleared. Will use role-based or default rate.', 'success')
        return redirect(request.referrer or url_for('admin', section='payroll'))
    
    try:
        rate = float(hourly_rate)
        if rate < 0:
            flash('Hourly rate cannot be negative', 'error')
            return redirect(request.referrer or url_for('admin', section='payroll'))
        
        with get_employee_connection() as conn:
            existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
            if 'hourly_rate' not in existing_columns:
                conn.execute("ALTER TABLE employees ADD COLUMN hourly_rate REAL")
            
            conn.execute(
                "UPDATE employees SET hourly_rate = ? WHERE employee_id = ?",
                (rate, employee_id)
            )
            conn.commit()
        
        flash('Employee hourly rate updated successfully', 'success')
    except ValueError:
        flash('Invalid hourly rate value', 'error')
    
    return redirect(request.referrer or url_for('admin', section='payroll'))

@app.route('/admin/bulk-role-rate', methods=['POST'])
def admin_bulk_update_role_rate():
    """Bulk update hourly rate for all employees with a specific role"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    role = request.form.get('role', '').strip()
    hourly_rate = request.form.get('hourly_rate', '').strip()
    
    if not role:
        flash('Role is required', 'error')
        return redirect(request.referrer or url_for('admin', section='payroll'))
    
    if not hourly_rate:
        flash('Hourly rate is required', 'error')
        return redirect(request.referrer or url_for('admin', section='payroll'))
    
    try:
        rate = float(hourly_rate)
        if rate < 0:
            flash('Hourly rate cannot be negative', 'error')
            return redirect(request.referrer or url_for('admin', section='payroll'))
        
        # Update role-based rate
        role_rates = load_role_rates()
        role_rates[role] = rate
        save_role_rates(role_rates)
        
        # Optionally clear individual rates for employees with this role
        # (so they use the role-based rate)
        clear_individual = request.form.get('clear_individual', '') == 'on'
        
        if clear_individual:
            with get_employee_connection() as conn:
                existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
                if 'hourly_rate' in existing_columns:
                    conn.execute(
                        "UPDATE employees SET hourly_rate = NULL WHERE job_title = ?",
                        (role,)
                    )
                    conn.commit()
        
        count = 0
        with get_employee_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM employees WHERE job_title = ? AND status = 'active'",
                (role,)
            ).fetchone()[0]
        
        flash(f'Hourly rate for {role} set to ${rate:.2f}/hour. Affects {count} active employee(s).', 'success')
    except ValueError:
        flash('Invalid hourly rate value', 'error')
    
    return redirect(request.referrer or url_for('admin', section='payroll'))

@app.route('/admin/menu/add', methods=['POST'])
def admin_menu_add():
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    price = request.form.get('price', '').strip()
    category_selected = request.form.get('category_select', '').strip()
    new_category = request.form.get('new_category', '').strip()
    category = new_category if new_category else category_selected
    image_file = request.files.get('image_file')
    
    if not all([name, description, price, category]):
        flash('Name, description, price, and category are required', 'error')
        return redirect(request.referrer or url_for('admin'))
    
    try:
        price_value = float(price)
    except ValueError:
        flash('Price must be a valid number', 'error')
        return redirect(request.referrer or url_for('admin'))
    
    image_filename = save_uploaded_image(image_file) if image_file else ''
    
    categories = get_categories()
    if category not in categories:
        categories.append(category)
        categories = save_categories(categories)
    
    items = get_menu_items()
    next_id = max([int(item['item_id']) for item in items] + [0]) + 1
    items.append({
        'item_id': str(next_id),
        'name': name,
        'description': description,
        'price': price_value,
        'category': category,
        'image': image_filename
    })
    save_menu_items(items)
    flash(f'Menu item "{name}" added successfully', 'success')
    return redirect(request.referrer or url_for('admin'))

@app.route('/admin/menu/update/<item_id>', methods=['POST'])
def admin_menu_update(item_id):
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    items = get_menu_items()
    for item in items:
        if item['item_id'] == item_id:
            item['name'] = request.form.get('name', item['name']).strip()
            item['description'] = request.form.get('description', item['description']).strip()
            category_selected = request.form.get('category_select', item['category']).strip()
            new_category = request.form.get('new_category', '').strip()
            category = new_category if new_category else category_selected
            if not category:
                flash('Category is required', 'error')
                return redirect(request.referrer or url_for('admin'))
            item['category'] = category
            categories = get_categories()
            if category not in categories:
                save_categories(categories + [category])
            price = request.form.get('price', item['price'])
            try:
                item['price'] = float(price)
            except ValueError:
                flash('Price must be a valid number', 'error')
                return redirect(request.referrer or url_for('admin'))
            image_file = request.files.get('image_file')
            if image_file and image_file.filename:
                image_filename = save_uploaded_image(image_file)
                if image_filename:
                    item['image'] = image_filename
            save_menu_items(items)
            flash(f'Menu item "{item["name"]}" updated', 'success')
            break
    else:
        flash('Menu item not found', 'error')
    return redirect(request.referrer or url_for('admin'))

@app.route('/admin/menu/delete/<item_id>', methods=['POST'])
def admin_menu_delete(item_id):
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    items = get_menu_items()
    filtered = [item for item in items if item['item_id'] != item_id]
    if len(filtered) == len(items):
        flash('Menu item not found', 'error')
    else:
        save_menu_items(filtered)
        flash('Menu item removed', 'info')
    return redirect(request.referrer or url_for('admin'))

@app.route('/admin/employees/add', methods=['POST'])
def admin_add_employee():
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))

    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    gender = request.form.get('gender', '').strip()
    dob = request.form.get('dob', '').strip()
    mobile = request.form.get('mobile', '').strip()
    address = request.form.get('address', '').strip()
    selected_title = request.form.get('job_title', '').strip()
    job_title_custom = request.form.get('job_title_custom', '').strip()
    job_title = job_title_custom if selected_title == '__custom__' and job_title_custom else selected_title
    notes = request.form.get('notes', '').strip()

    if not all([first_name, last_name, email]):
        flash('First name, last name, and email are required', 'error')
        return redirect(url_for('admin', section='employees'))

    try:
        employee_id = create_employee_record(
            first_name=first_name,
            last_name=last_name,
            email=email,
            gender=gender,
            dob=dob,
            mobile=mobile,
            address=address,
            job_title=job_title,
            notes=notes
        )
        flash(f'Employee {first_name} {last_name} added with ID {employee_id}', 'success')
    except sqlite3.IntegrityError:
        flash('An employee with that email already exists', 'error')

    return redirect(url_for('admin', section='employees'))

@app.route('/admin/employees/update/<employee_id>', methods=['POST'])
def admin_update_employee(employee_id):
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))

    selected_title_upd = request.form.get('job_title', '').strip()
    job_title_custom_upd = request.form.get('job_title_custom', '').strip()
    job_title_final = job_title_custom_upd if selected_title_upd == '__custom__' and job_title_custom_upd else selected_title_upd

    updated = update_employee_record(
        employee_id,
        first_name=request.form.get('first_name', '').strip(),
        last_name=request.form.get('last_name', '').strip(),
        email=request.form.get('email', '').strip(),
        gender=request.form.get('gender', '').strip(),
        dob=request.form.get('dob', '').strip(),
        mobile=request.form.get('mobile', '').strip(),
        address=request.form.get('address', '').strip(),
        job_title=job_title_final,
        notes=request.form.get('notes', '').strip()
    )
    if updated:
        flash('Employee details updated', 'success')
    else:
        flash('No changes detected or invalid fields', 'info')
    return redirect(url_for('admin', section='employees'))

@app.route('/admin/employees/schedule/<employee_id>', methods=['POST'])
def admin_update_employee_schedule(employee_id):
    """Update employee schedule"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    schedule = {}
    
    for day in days:
        enabled = request.form.get(f'{day}_enabled', 'off') == 'on'
        start_time = request.form.get(f'{day}_start', '09:00').strip()
        end_time = request.form.get(f'{day}_end', '17:00').strip()
        schedule[day] = {
            'enabled': enabled,
            'start': start_time,
            'end': end_time
        }
    
    updated = update_employee_record(employee_id, schedule=schedule)
    if updated:
        flash('Employee schedule updated successfully', 'success')
    else:
        flash('Failed to update schedule', 'error')
    
    return redirect(url_for('admin', section='employees'))

@app.route('/admin/employees/status/<employee_id>', methods=['POST'])
def admin_update_employee_status(employee_id):
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))

    new_status = request.form.get('status', '').strip()
    if update_employee_status(employee_id, new_status):
        status_label = 'Active' if new_status == 'active' else 'Suspended'
        flash(f'Employee status set to {status_label}', 'success')
    else:
        flash('Invalid status value', 'error')
    return redirect(url_for('admin', section='employees'))

@app.route('/admin/employees/delete/<employee_id>', methods=['POST'])
def admin_delete_employee(employee_id):
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))

    delete_employee_record(employee_id)
    flash(f'Employee ID {employee_id} removed from directory', 'info')
    return redirect(url_for('admin', section='employees'))

@app.route('/admin/employees/export')
def admin_export_employees():
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))

    employees = get_employees()
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Title
    title = Paragraph("Employee Directory - TastyCorner", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    
    # Report date
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    report_date = Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", date_style)
    elements.append(report_date)
    elements.append(Spacer(1, 0.3*inch))
    
    # Prepare table data
    table_data = [['ID', 'Name', 'Email', 'Phone', 'Job Title', 'Status']]
    
    for employee in employees:
        full_name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip()
        email = employee.get('email', 'N/A')
        mobile = employee.get('mobile', 'N/A')
        job_title = employee.get('job_title', 'N/A')
        status = employee.get('status', 'active').title()
        emp_id = employee.get('employee_id', 'N/A')
        
        # Truncate long text for table
        if len(full_name) > 20:
            full_name = full_name[:17] + '...'
        if len(email) > 25:
            email = email[:22] + '...'
        if len(job_title) > 20:
            job_title = job_title[:17] + '...'
        
        table_data.append([emp_id, full_name, email, mobile, job_title, status])
    
    # Create table
    table = Table(table_data, colWidths=[0.8*inch, 1.5*inch, 2*inch, 1.2*inch, 1.5*inch, 0.8*inch])
    
    # Style the table
    table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary
    summary_style = ParagraphStyle(
        'SummaryStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_LEFT
    )
    total_count = len(employees)
    active_count = sum(1 for e in employees if e.get('status', '').lower() == 'active')
    suspended_count = total_count - active_count
    
    summary_text = f"<b>Summary:</b> Total Employees: {total_count} | Active: {active_count} | Suspended: {suspended_count}"
    summary = Paragraph(summary_text, summary_style)
    elements.append(summary)
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF data
    buffer.seek(0)
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Return PDF response
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'employees_{timestamp}.pdf'
    return Response(
        pdf_data,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.route('/admin/orders/update/<int:order_id>', methods=['POST'])
def admin_update_order(order_id):
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    status = request.form.get('status', 'pending')
    orders = get_all_orders()
    updated = False
    for order in orders:
        if int(order['order_id']) == order_id:
            order['status'] = status
            updated = True
            break
    
    if updated:
        save_orders(orders)
        flash(f'Order #{order_id} status updated to {status}', 'success')
    else:
        flash('Order not found', 'error')
    return redirect(url_for('admin'))

@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    """Order confirmation page"""
    if 'user_id' not in session:
        flash('Please sign in', 'error')
        return redirect(url_for('signin'))
    
    # Get order details from CSV
    if os.path.exists(ORDERS_CSV):
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['order_id']) == order_id and row['user_id'] == session['user_id']:
                    row['items'] = json.loads(row['items'])
                    row['allergies'] = json.loads(row['allergies'])
                    # Handle legacy orders without coupon fields
                    if 'coupon_code' not in row:
                        row['coupon_code'] = ''
                        row['discount'] = '0.00'
                    return render_template('order_confirmation.html', order=row, user_name=session.get('user_name'))
    
    flash('Order not found', 'error')
    return redirect(url_for('menu'))

def get_user_orders(user_id):
    """Get all orders for a user"""
    orders = []
    if os.path.exists(ORDERS_CSV):
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['user_id'] == user_id:
                    row['items'] = json.loads(row['items'])
                    row['allergies'] = json.loads(row['allergies'])
                    # Handle legacy orders without coupon fields
                    if 'coupon_code' not in row:
                        row['coupon_code'] = ''
                        row['discount'] = '0.00'
                    orders.append(row)
    # Sort by date, newest first
    orders.sort(key=lambda x: x['created_at'], reverse=True)
    return orders

@app.route('/orders')
def orders():
    """Order history page"""
    if 'user_id' not in session:
        flash('Please sign in to view your orders', 'error')
        return redirect(url_for('signin'))
    
    user_orders = get_user_orders(session['user_id'])
    return render_template('orders.html', orders=user_orders, user_name=session.get('user_name'))

@app.route('/apply_coupon', methods=['POST'])
def apply_coupon_checkout():
    """Apply coupon at checkout"""
    if 'user_id' not in session:
        flash('Please sign in', 'error')
        return redirect(url_for('signin'))
    
    coupon_code = request.form.get('coupon_code', '').strip().upper()
    remove_coupon = request.form.get('remove', '').strip()
    cart = session.get('cart', [])
    subtotal = sum(item['price'] * item['quantity'] for item in cart)
    
    if remove_coupon or not coupon_code:
        session.pop('applied_coupon', None)
        session.modified = True
        flash('Coupon removed', 'info')
    elif coupon_code:
        discount, error_msg = validate_coupon(coupon_code, subtotal)
        if error_msg:
            flash(f'Coupon error: {error_msg}', 'error')
        else:
            session['applied_coupon'] = coupon_code
            session.modified = True
            flash(f'Coupon "{coupon_code}" applied! Discount: ${discount:.2f}', 'success')
    
    return redirect(url_for('checkout'))

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    """Cancel order within 30 minutes"""
    if 'user_id' not in session:
        flash('Please sign in', 'error')
        return redirect(url_for('signin'))
    
    # Get order
    orders = get_all_orders()
    order = None
    for o in orders:
        if int(o['order_id']) == order_id and o['user_id'] == session['user_id']:
            order = o
            break
    
    if not order:
        flash('Order not found', 'error')
        return redirect(url_for('orders'))
    
    # Check if order can be cancelled (within 30 minutes and not already cancelled/completed)
    if order['status'] in ['cancelled', 'completed']:
        flash('This order cannot be cancelled', 'error')
        return redirect(url_for('orders'))
    
    # Check time difference
    try:
        order_time = datetime.strptime(order['created_at'], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        # Try alternative format
        try:
            order_time = datetime.strptime(order['created_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
        except:
            flash('Unable to parse order time', 'error')
            return redirect(url_for('orders'))
    
    time_diff = datetime.now() - order_time
    minutes_passed = time_diff.total_seconds() / 60
    
    if minutes_passed > 30:
        flash('Orders can only be cancelled within 30 minutes of placement', 'error')
        return redirect(url_for('orders'))
    
    # Update order status to cancelled
    for o in orders:
        if int(o['order_id']) == order_id:
            o['status'] = 'cancelled'
            break
    
    save_orders(orders)
    flash(f'Order #{order_id} has been cancelled. Refund will be processed within 3-5 business days.', 'success')
    return redirect(url_for('orders'))

@app.route('/reorder/<int:order_id>')
def reorder(order_id):
    """Quick reorder from order history"""
    if 'user_id' not in session:
        flash('Please sign in', 'error')
        return redirect(url_for('signin'))
    
    if os.path.exists(ORDERS_CSV):
        with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row['order_id']) == order_id and row['user_id'] == session['user_id']:
                    items = json.loads(row['items'])
                    
                    # Add items to cart
                    if 'cart' not in session:
                        session['cart'] = []
                    
                    for item in items:
                        cart_item = {
                            'item_id': item['item_id'],
                            'name': item['name'],
                            'price': float(item['price']),
                            'quantity': item['quantity'],
                            'allergies': item.get('allergies', '')
                        }
                        session['cart'].append(cart_item)
                    
                    session.modified = True
                    flash(f'Order #{order_id} added to cart!', 'success')
                    return redirect(url_for('cart'))
    
    flash('Order not found', 'error')
    return redirect(url_for('orders'))

@app.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html', user_name=session.get('user_name'))

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html', user_name=session.get('user_name'))

@app.route('/worker/login', methods=['GET', 'POST'])
def worker_login():
    """Worker login page"""
    if request.method == 'POST':
        employee_id = request.form.get('employee_id', '').strip()
        
        if not employee_id:
            flash('Please enter your Employee ID', 'error')
            return render_template('worker/login.html')
        
        employee = get_employee_by_id(employee_id)
        
        if not employee:
            flash('Invalid Employee ID', 'error')
            return render_template('worker/login.html')
        
        if employee['status'] != 'active':
            flash('Your account is not active. Please contact your administrator.', 'error')
            return render_template('worker/login.html')
        
        # Set worker session
        session['worker_id'] = employee['employee_id']
        session['worker_name'] = f"{employee['first_name']} {employee['last_name']}"
        session['worker_job_title'] = employee.get('job_title', 'Employee')
        flash(f'Welcome, {employee["first_name"]}!', 'success')
        return redirect(url_for('worker_dashboard'))
    
    return render_template('worker/login.html')

@app.route('/worker/dashboard')
def worker_dashboard():
    """Worker dashboard"""
    if 'worker_id' not in session:
        flash('Please log in with your Employee ID', 'error')
        return redirect(url_for('worker_login'))
    
    employee_id = session['worker_id']
    employee = get_employee_by_id(employee_id)
    
    if not employee:
        session.clear()
        flash('Employee not found', 'error')
        return redirect(url_for('worker_login'))
    
    if employee['status'] != 'active':
        session.clear()
        flash('Your account is not active', 'error')
        return redirect(url_for('worker_login'))
    
    # Get today's attendance status
    today = datetime.now().strftime('%Y-%m-%d')
    attendance = get_today_attendance(employee_id, today)
    
    # Check if employee has schedule for today
    today_weekday = datetime.now().strftime('%A').lower()
    schedule = employee.get('schedule', {})
    today_schedule = schedule.get(today_weekday, {})
    has_schedule_today = today_schedule.get('enabled', False)
    
    # Get payroll information
    payroll_info = get_employee_payroll_info(employee_id)
    
    # Get employee's hourly rate (individual, role-based, or default)
    hourly_rate = get_employee_hourly_rate(employee)
    
    # Get hours tracking information
    hours_today = get_hours_worked_today(employee_id)
    hours_week = get_hours_worked_this_week(employee_id)
    overtime_status = get_overtime_status(employee_id)
    
    return render_template('worker/dashboard.html', 
                         employee=employee, 
                         attendance=attendance,
                         has_schedule_today=has_schedule_today,
                         payroll_info=payroll_info,
                         hourly_rate=hourly_rate,
                         hours_today=hours_today,
                         hours_week=hours_week,
                         overtime_status=overtime_status)

@app.route('/worker/checkin', methods=['POST'])
def worker_checkin():
    """Employee check-in"""
    if 'worker_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('worker_login'))
    
    employee_id = session['worker_id']
    employee = get_employee_by_id(employee_id)
    
    if not employee:
        flash('Employee not found', 'error')
        return redirect(url_for('worker_login'))
    
    # Check if employee has a schedule for today
    today_weekday = datetime.now().strftime('%A').lower()
    schedule = employee.get('schedule', {})
    today_schedule = schedule.get(today_weekday, {})
    has_schedule_today = today_schedule.get('enabled', False) == True or today_schedule.get('enabled') == 'true' or today_schedule.get('enabled') == 1
    
    if not has_schedule_today:
        flash('You do not have a schedule for today. Please contact your administrator.', 'error')
        return redirect(url_for('worker_dashboard'))
    
    success = check_in_employee(employee_id)
    
    if success:
        flash('Checked in successfully!', 'success')
    else:
        flash('You have already checked in today', 'info')
    
    return redirect(url_for('worker_dashboard'))

@app.route('/worker/checkout', methods=['POST'])
def worker_checkout():
    """Employee check-out"""
    if 'worker_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('worker_login'))
    
    employee_id = session['worker_id']
    employee = get_employee_by_id(employee_id)
    
    if not employee:
        flash('Employee not found', 'error')
        return redirect(url_for('worker_login'))
    
    # Check if they have checked in (must have checked in to check out)
    today = datetime.now().strftime('%Y-%m-%d')
    attendance = get_today_attendance(employee_id, today)
    
    if not attendance or not attendance.get('check_in_time'):
        flash('You must check in first before checking out.', 'error')
        return redirect(url_for('worker_dashboard'))
    
    # Verify they have a schedule for today (for consistency)
    today_weekday = datetime.now().strftime('%A').lower()
    schedule = employee.get('schedule', {})
    today_schedule = schedule.get(today_weekday, {})
    has_schedule_today = today_schedule.get('enabled', False) == True or today_schedule.get('enabled') == 'true' or today_schedule.get('enabled') == 1
    
    if not has_schedule_today:
        flash('You do not have a schedule for today. Please contact your administrator.', 'error')
        return redirect(url_for('worker_dashboard'))
    
    success = check_out_employee(employee_id)
    
    if success:
        attendance = get_today_attendance(employee_id, today)
        hours = attendance['hours_worked'] if attendance else 0
        flash(f'Checked out successfully! Hours worked today: {hours:.2f}', 'success')
    else:
        flash('Unable to check out. Make sure you have checked in first.', 'error')
    
    return redirect(url_for('worker_dashboard'))

@app.route('/worker/profile-picture', methods=['POST'])
def worker_upload_profile_picture():
    """Upload employee profile picture"""
    if 'worker_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('worker_login'))
    
    employee_id = session['worker_id']
    profile_file = request.files.get('profile_picture')
    
    if not profile_file or not profile_file.filename:
        flash('No file selected', 'error')
        return redirect(url_for('worker_dashboard'))
    
    if not allowed_file(profile_file.filename):
        flash('Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF, WEBP)', 'error')
        return redirect(url_for('worker_dashboard'))
    
    # Save the file
    filename = save_uploaded_image(profile_file)
    if not filename:
        flash('Failed to upload image', 'error')
        return redirect(url_for('worker_dashboard'))
    
    # Update employee record
    with get_employee_connection() as conn:
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(employees)")}
        if 'profile_picture' in existing_columns:
            # Delete old profile picture if exists
            old_picture = conn.execute(
                "SELECT profile_picture FROM employees WHERE employee_id = ?",
                (employee_id,)
            ).fetchone()
            if old_picture and old_picture['profile_picture']:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], old_picture['profile_picture'])
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except:
                        pass
            
            conn.execute(
                "UPDATE employees SET profile_picture = ? WHERE employee_id = ?",
                (filename, employee_id)
            )
            conn.commit()
            flash('Profile picture updated successfully', 'success')
        else:
            flash('Profile picture feature not available', 'error')
    
    return redirect(url_for('worker_dashboard'))

@app.route('/admin/payroll/mark-paid', methods=['POST'])
def admin_mark_paid():
    """Mark employee(s) as paid"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin_login'))
    
    employee_ids = request.form.getlist('employee_ids')
    
    if not employee_ids:
        flash('Please select at least one employee', 'error')
        return redirect(url_for('admin', section='payroll'))
    
    count = mark_multiple_employees_as_paid(employee_ids)
    
    if count > 0:
        flash(f'Successfully marked {count} employee(s) as paid. Hours reset to 0.', 'success')
    else:
        flash('Failed to mark employees as paid', 'error')
    
    return redirect(url_for('admin', section='payroll'))

@app.route('/admin/payroll/mark-paid-single/<employee_id>', methods=['POST'])
def admin_mark_paid_single(employee_id):
    """Mark a single employee as paid"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin_login'))
    
    success = mark_employee_as_paid(employee_id)
    
    if success:
        flash('Employee marked as paid. Hours reset to 0.', 'success')
    else:
        flash('Failed to mark employee as paid', 'error')
    
    return redirect(url_for('admin', section='payroll'))

@app.route('/worker/logout')
def worker_logout():
    """Worker logout"""
    session.pop('worker_id', None)
    session.pop('worker_name', None)
    session.pop('worker_job_title', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('worker_login'))

@app.route('/admin/coupons/add', methods=['POST'])
def admin_add_coupon():
    """Add a new coupon"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    code = request.form.get('code', '').strip().upper()
    discount_type = request.form.get('discount_type', 'percentage')
    discount_value = request.form.get('discount_value', '').strip()
    min_order = request.form.get('min_order', '0').strip()
    max_discount = request.form.get('max_discount', '').strip()
    usage_limit = request.form.get('usage_limit', '').strip()
    expiry_date = request.form.get('expiry_date', '').strip()
    is_active = request.form.get('is_active', 'true') == 'true'
    
    if not all([code, discount_value]):
        flash('Code and discount value are required', 'error')
        return redirect(request.referrer or url_for('admin'))
    
    # Check if coupon code already exists
    if get_coupon_by_code(code):
        flash('Coupon code already exists', 'error')
        return redirect(request.referrer or url_for('admin'))
    
    try:
        discount_value = float(discount_value)
        min_order = float(min_order) if min_order else 0.0
        max_discount = float(max_discount) if max_discount else None
        usage_limit = int(usage_limit) if usage_limit else None
    except ValueError:
        flash('Invalid numeric values', 'error')
        return redirect(request.referrer or url_for('admin'))
    
    coupons = get_coupons()
    coupons.append({
        'code': code,
        'discount_type': discount_type,
        'discount_value': discount_value,
        'min_order': min_order,
        'max_discount': max_discount,
        'usage_limit': usage_limit,
        'used_count': 0,
        'expiry_date': expiry_date,
        'is_active': is_active
    })
    save_coupons(coupons)
    flash(f'Coupon "{code}" added successfully', 'success')
    return redirect(request.referrer or url_for('admin'))

@app.route('/admin/coupons/update/<code>', methods=['POST'])
def admin_update_coupon(code):
    """Update a coupon"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    coupons = get_coupons()
    updated = False
    for coupon in coupons:
        if coupon['code'].upper() == code.upper():
            discount_type = request.form.get('discount_type', coupon['discount_type'])
            discount_value = request.form.get('discount_value', '').strip()
            min_order = request.form.get('min_order', '0').strip()
            max_discount = request.form.get('max_discount', '').strip()
            usage_limit = request.form.get('usage_limit', '').strip()
            expiry_date = request.form.get('expiry_date', '').strip()
            is_active = request.form.get('is_active', 'false') == 'true'
            
            if discount_value:
                try:
                    coupon['discount_type'] = discount_type
                    coupon['discount_value'] = float(discount_value)
                    coupon['min_order'] = float(min_order) if min_order else 0.0
                    coupon['max_discount'] = float(max_discount) if max_discount else None
                    coupon['usage_limit'] = int(usage_limit) if usage_limit else None
                    coupon['expiry_date'] = expiry_date
                    coupon['is_active'] = is_active
                    updated = True
                except ValueError:
                    flash('Invalid numeric values', 'error')
                    return redirect(request.referrer or url_for('admin'))
            break
    
    if updated:
        save_coupons(coupons)
        flash(f'Coupon "{code}" updated', 'success')
    else:
        flash('Coupon not found', 'error')
    return redirect(request.referrer or url_for('admin'))

@app.route('/admin/coupons/delete/<code>', methods=['POST'])
def admin_delete_coupon(code):
    """Delete a coupon"""
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    coupons = get_coupons()
    filtered = [c for c in coupons if c['code'].upper() != code.upper()]
    if len(filtered) == len(coupons):
        flash('Coupon not found', 'error')
    else:
        save_coupons(filtered)
        flash('Coupon removed', 'info')
    return redirect(request.referrer or url_for('admin'))

@app.route('/admin/categories/add', methods=['POST'])
def admin_add_category():
    if not is_admin():
        flash('Please sign in as admin', 'error')
        return redirect(url_for('admin'))
    
    category = request.form.get('category_name', '').strip()
    if not category:
        flash('Category name is required', 'error')
        return redirect(request.referrer or url_for('admin'))
    
    categories = get_categories()
    if category in categories:
        flash('Category already exists', 'info')
    else:
        save_categories(categories + [category])
        flash(f'Category "{category}" added', 'success')
    return redirect(request.referrer or url_for('admin'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)

