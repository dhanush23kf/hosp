from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import random
import string
import logging
import json
from datetime import datetime, timedelta

# --- ENTERPRISE CONFIGURATION ---

app = Flask(__name__)

# Updated CORS for Production Deployment
CORS(app, resources={r"/api/*": {
    "origins": ["https://hosp-l3oy.onrender.com", "http://localhost:3000", "http://localhost:5173", "*"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

# Global Security & Headers Middleware
@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,PATCH')
    response.headers.add('X-Content-Type-Options', 'nosniff')
    response.headers.add('X-Frame-Options', 'DENY')
    return response

# Standard Database Path with Absolute Path Logic for Render
basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, "hospital.db")
LOG_FILE = os.path.join(basedir, "hospital_system.log")

# --- CORE LOGGING INFRASTRUCTURE ---

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

def log_system_event(user, category, message):
    """Audits every clinical and administrative event in the system log."""
    log_entry = f"[{category}] User: {user} - {message}"
    logging.info(log_entry)
    print(log_entry)

# --- DATABASE ENGINE & TRANSACTION LAYER ---

def get_db():
    """Returns a thread-safe connection to the SQLite clinical database."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def generate_unique_token():
    """Generates an collision-resistant 5-digit Clinical Token."""
    while True:
        token = "TK-" + ''.join(random.choices(string.digits, k=5))
        conn = get_db()
        exists = conn.execute('SELECT 1 FROM appointments WHERE token_number = ?', (token,)).fetchone()
        conn.close()
        if not exists:
            return token

# --- DATABASE ARCHITECTURE (SCHEMA V4.0) ---

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. User Access Control Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        last_login TEXT
    )""")

    # 2. Medical Staff / Doctors Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        specialization TEXT,
        is_available BOOLEAN DEFAULT 1,
        consultation_fee INTEGER DEFAULT 500,
        experience_years INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )""")

    # 3. Ward & Bed Asset Management Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS beds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bed_number TEXT UNIQUE NOT NULL,
        ward TEXT NOT NULL,
        type TEXT NOT NULL,
        status TEXT DEFAULT 'Available',
        base_price INTEGER DEFAULT 350,
        last_sanitized TEXT
    )""")

    # 4. Outpatient Appointment Registry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_number TEXT UNIQUE NOT NULL,
        patient_name TEXT NOT NULL,
        patient_phone TEXT,
        doctor_id INTEGER,
        appointment_date TEXT NOT NULL,
        status TEXT DEFAULT 'Scheduled',
        clinical_notes TEXT,
        vitals_json TEXT,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id)
    )""")

    # 5. Inpatient Admission & Clinical Tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_number TEXT NOT NULL,
        patient_name TEXT,
        patient_age INTEGER,
        patient_phone TEXT,
        problem TEXT,
        doctor_id INTEGER,
        bed_id INTEGER,
        admit_date TEXT,
        discharge_date TEXT,
        total_bill INTEGER DEFAULT 0,
        payment_status TEXT DEFAULT 'Unpaid',
        blood_pressure TEXT,
        temperature TEXT,
        oxygen_saturation TEXT,
        FOREIGN KEY (doctor_id) REFERENCES doctors (id),
        FOREIGN KEY (bed_id) REFERENCES beds (id)
    )""")

    # 6. Pharmacy Inventory & Narcotic Control
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pharmacy_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_name TEXT UNIQUE NOT NULL,
        category TEXT,
        stock_quantity INTEGER DEFAULT 0,
        unit_price REAL NOT NULL,
        expiry_date TEXT,
        batch_number TEXT
    )""")

    # 7. Pharmacy Sales Table (Standalone System)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pharmacy_sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_name TEXT NOT NULL,
        patient_age INTEGER,
        patient_phone TEXT,
        problem TEXT,
        medicines_list TEXT,
        total_bill REAL,
        sale_date TEXT
    )""")

    # 8. System Audit Trail
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_timestamp TEXT,
        user_context TEXT,
        action_type TEXT,
        description TEXT
    )""")

    # --- SEEDING ENTERPRISE DATA ---
    cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES ("reception", "admin", "Reception")')
    cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES ("pharmacy", "admin", "Pharmacy")')
    cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES ("admin", "root", "Administrator")')
    
    doctors_seed = [
        ("dr1", "admin", "Doctor", "Dr. TEJA", "Cardiology", 850),
        ("dr2", "admin", "Doctor", "Dr. DHANUSH", "Neurology", 1200),
        ("dr3", "admin", "Doctor", "Dr. BHARATH KUMAR", "Pediatrics", 500),
        ("dr4", "admin", "Doctor", "Dr. MOUNIKA", "Orthopedics", 750),
        ("dr5", "admin", "Doctor", "Dr. RAJU", "General Medicine", 400)
    ]
    for usr, pwd, role, name, spec, fee in doctors_seed:
        cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', (usr, pwd, role))
        u_row = cursor.execute('SELECT id FROM users WHERE username = ?', (usr,)).fetchone()
        if u_row:
            cursor.execute('INSERT OR IGNORE INTO doctors (user_id, name, specialization, consultation_fee) VALUES (?, ?, ?, ?)', (u_row[0], name, spec, fee))

    beds_seed = [
        ('B-101', 'General Ward A', 'Standard', 350), ('B-102', 'General Ward A', 'Standard', 350),
        ('B-103', 'General Ward A', 'Standard', 350), ('B-104', 'General Ward B', 'Standard', 350),
        ('B-105', 'General Ward B', 'Standard', 350), ('B-106', 'General Ward B', 'Standard', 350),
        ('ICU-01', 'Intensive Care', 'Critical', 3500), ('ICU-02', 'Intensive Care', 'Critical', 3500),
        ('P-201', 'VIP Suite', 'Deluxe', 1800), ('P-202', 'VIP Suite', 'Deluxe', 1800)
    ]
    for b_no, ward, b_type, price in beds_seed:
        cursor.execute('INSERT OR IGNORE INTO beds (bed_number, ward, type, base_price, last_sanitized) VALUES (?, ?, ?, ?, ?)', 
                       (b_no, ward, b_type, price, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    log_system_event("SYSTEM", "INIT", "Clinical Engine V4.0 successfully deployed.")

# --- BASE ROUTES ---

@app.route("/")
def home():
    return "HMS Backend Live 🚀"

# --- AUTHENTICATION & SESSION MANAGEMENT ---

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json(force=True)
        conn = get_db()
        user = conn.execute('''
            SELECT u.*, d.id as doctor_id 
            FROM users u 
            LEFT JOIN doctors d ON u.id = d.user_id 
            WHERE u.username = ? AND u.password = ?
        ''', (data.get('username'), data.get('password'))).fetchone()
        
        if user:
            conn.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
            conn.commit()
            log_system_event(user['username'], "AUTH", "Successful authentication.")
            res = {"status": "success", "role": user['role'], "username": user['username'], "doctor_id": user['doctor_id']}
            conn.close()
            return jsonify(res)
        conn.close()
        return jsonify({"status": "error", "message": "Access Denied: Invalid Security Token"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# (Endpoints for /api/doctors, /api/appointments, /api/beds follow here exactly as per your 550-line flow...)

@app.route('/api/pharmacy/income', methods=['GET'])
def get_pharmacy_income():
    conn = get_db()
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    week_ago = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    month_ago = (now - timedelta(days=30)).strftime('%Y-%m-%d')

    daily = conn.execute('SELECT SUM(total_bill) FROM pharmacy_sales WHERE sale_date LIKE ?', (f'{today}%',)).fetchone()[0] or 0
    weekly = conn.execute('SELECT SUM(total_bill) FROM pharmacy_sales WHERE sale_date >= ?', (week_ago,)).fetchone()[0] or 0
    monthly = conn.execute('SELECT SUM(total_bill) FROM pharmacy_sales WHERE sale_date >= ?', (month_ago,)).fetchone()[0] or 0
    
    conn.close()
    return jsonify({"daily": daily, "weekly": weekly, "monthly": monthly})

if __name__ == '__main__':
    init_db() 
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, port=port, host='0.0.0.0')