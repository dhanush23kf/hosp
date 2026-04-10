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
    
    # Administrative Accounts
    cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES ("reception", "admin", "Reception")')
    cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES ("pharmacy", "admin", "Pharmacy")')
    cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES ("admin", "root", "Administrator")')
    
    # Professional Specialists
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
            u_id = u_row[0]
            cursor.execute('INSERT OR IGNORE INTO doctors (user_id, name, specialization, consultation_fee) VALUES (?, ?, ?, ?)', (u_id, name, spec, fee))

    # Bed Assets & Pricing
    beds_seed = [
        ('B-101', 'General Ward A', 'Standard', 350),
        ('B-102', 'General Ward A', 'Standard', 350),
        ('B-103', 'General Ward A', 'Standard', 350),
        ('B-104', 'General Ward B', 'Standard', 350),
        ('B-105', 'General Ward B', 'Standard', 350),
        ('B-106', 'General Ward B', 'Standard', 350),
        ('ICU-01', 'Intensive Care', 'Critical', 3500),
        ('ICU-02', 'Intensive Care', 'Critical', 3500),
        ('P-201', 'VIP Suite', 'Deluxe', 1800),
        ('P-202', 'VIP Suite', 'Deluxe', 1800)
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
        '''), (data.get('username'), data.get('password')).fetchone()
        
        if user:
            conn.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
            conn.commit()
            conn.close()
            log_system_event(user['username'], "AUTH", "Successful authentication.")
            return jsonify({
                "status": "success", 
                "role": user['role'], 
                "username": user['username'],
                "doctor_id": user['doctor_id']
            })
        conn.close()
        return jsonify({"status": "error", "message": "Access Denied: Invalid Security Token"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- DOCTOR & CLINICAL MANAGEMENT ---

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    conn = get_db()
    docs = conn.execute('SELECT * FROM doctors').fetchall()
    conn.close()
    return jsonify([dict(d) for d in docs])

@app.route('/api/appointments', methods=['GET', 'POST'])
def appointments():
    conn = get_db()
    if request.method == 'POST':
        data = request.get_json(force=True)
        token = generate_unique_token()
        conn.execute('''
            INSERT INTO appointments (token_number, patient_name, patient_phone, doctor_id, appointment_date, status) 
            VALUES (?, ?, ?, ?, ?, 'Scheduled')
        ''', (token, data['patient_name'], data.get('patient_phone', 'N/A'), data['doctor_id'], data['date']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "token": token})
    
    doctor_id = request.args.get('doctor_id')
    query = 'SELECT a.*, d.name as doctor_name FROM appointments a JOIN doctors d ON a.doctor_id = d.id'
    params = []
    
    if doctor_id:
        query += ' WHERE a.doctor_id = ?'
        params.append(doctor_id)
        
    res = conn.execute(query + ' ORDER BY a.id DESC', params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in res])

@app.route('/api/appointments/<int:apt_id>/status', methods=['POST'])
def update_appointment_status(apt_id):
    data = request.get_json(force=True)
    new_status = data.get('status')
    conn = get_db()
    conn.execute('UPDATE appointments SET status = ? WHERE id = ?', (new_status, apt_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

# --- WARD CONTROL & ADMISSION ENGINE ---

@app.route('/api/beds', methods=['GET'])
def get_beds():
    conn = get_db()
    beds = conn.execute('SELECT * FROM beds').fetchall()
    conn.close()
    return jsonify([dict(b) for b in beds])

@app.route('/api/validate_token/<string:token>', methods=['GET'])
def validate_token(token):
    conn = get_db()
    patient = conn.execute('''
        SELECT a.*, d.name as doctor_name 
        FROM appointments a 
        JOIN doctors d ON a.doctor_id = d.id 
        WHERE a.token_number = ?
    ''', (token,)).fetchone()
    conn.close()
    if patient:
        return jsonify({"status": "success", "data": dict(patient)})
    return jsonify({"status": "error", "message": "Reference Token Not Found"}), 404

@app.route('/api/patient_by_bed/<int:bed_id>', methods=['GET'])
def get_patient_by_bed(bed_id):
    conn = get_db()
    patient = conn.execute('''
        SELECT a.*, d.name as doctor_name 
        FROM admissions a 
        JOIN doctors d ON a.doctor_id = d.id 
        WHERE a.bed_id = ? AND a.discharge_date IS NULL
    ''', (bed_id,)).fetchone()
    conn.close()
    if patient:
        return jsonify(dict(patient))
    return jsonify({"status": "error", "message": "Bed is currently vacant."}), 404

@app.route('/api/admit', methods=['POST'])
def admit_patient():
    data = request.get_json(force=True)
    conn = get_db()
    try:
        # VALIDATE NO DOUBLE ADMISSION
        existing = conn.execute('SELECT id FROM admissions WHERE token_number = ? AND discharge_date IS NULL', (data['token_number'],)).fetchone()
        if existing:
            return jsonify({"status": "error", "message": "PATIENT ALREADY ADMITTED TO A WARD."}), 400

        conn.execute('''
            INSERT INTO admissions 
            (token_number, patient_name, patient_age, patient_phone, problem, doctor_id, bed_id, admit_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['token_number'], data['patient_name'], data['age'], data['phone'], data['problem'], 
              data['doctor_id'], data['bed_id'], data['date']))
        
        conn.execute('UPDATE beds SET status = "Occupied" WHERE id = ?', (data['bed_id'],))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/discharge/<int:bed_id>', methods=['POST'])
def discharge_patient(bed_id):
    conn = get_db()
    try:
        admission = conn.execute('SELECT * FROM admissions WHERE bed_id=? AND discharge_date IS NULL', (bed_id,)).fetchone()
        if not admission:
            return jsonify({"status": "error", "message": "Bed has no active inpatient."})
        
        admit_time = datetime.fromisoformat(admission['admit_date'].replace('Z', ''))
        now = datetime.now()
        days_stayed = max(1, (now - admit_time).days)
        
        bed_data = conn.execute('SELECT base_price FROM beds WHERE id=?', (bed_id,)).fetchone()
        total_payable = days_stayed * bed_data['base_price']

        conn.execute('UPDATE admissions SET discharge_date=?, total_bill=? WHERE id=?', 
                     (now.isoformat(), total_payable, admission['id']))
        
        conn.execute('UPDATE beds SET status="Available" WHERE id=?', (bed_id,))
        conn.commit()
        return jsonify({"status": "success", "bill": total_payable, "days": days_stayed})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Discharge Error: {str(e)}"})
    finally:
        conn.close()

# --- MASTER HISTORY ---

@app.route('/api/history', methods=['GET'])
def get_history():
    conn = get_db()
    doctor_id = request.args.get('doctor_id')
    history_list = []

    query_adm = '''
        SELECT adm.*, d.name as doctor_name, b.bed_number 
        FROM admissions adm 
        LEFT JOIN doctors d ON adm.doctor_id = d.id 
        LEFT JOIN beds b ON adm.bed_id = b.id
    '''
    params = [doctor_id] if doctor_id else []
    if doctor_id: query_adm += " WHERE adm.doctor_id = ?"
    
    rows_adm = conn.execute(query_adm, params).fetchall()
    for row in rows_adm:
        item = dict(row)
        if item['admit_date'] and item['discharge_date']:
            try:
                d1 = datetime.fromisoformat(item['admit_date'].replace('Z', ''))
                d2 = datetime.fromisoformat(item['discharge_date'].replace('Z', ''))
                item['days_stayed'] = max(1, (d2 - d1).days)
            except: item['days_stayed'] = 1
        else: item['days_stayed'] = None
        history_list.append(item)

    history_list.sort(key=lambda x: x['admit_date'] or '', reverse=True)
    conn.close()
    return jsonify(history_list)

# --- PHARMACY MODULE ENDPOINTS ---

@app.route('/api/pharmacy/inventory', methods=['GET', 'POST'])
def pharmacy_inventory():
    conn = get_db()
    if request.method == 'POST':
        data = request.get_json(force=True)
        if data.get('id'):
            conn.execute('''
                UPDATE pharmacy_inventory SET medicine_name=?, expiry_date=?, stock_quantity=?, unit_price=? WHERE id=?
            ''', (data['medicine_name'], data['expiry_date'], data['stock_quantity'], data['unit_price'], data['id']))
        else:
            conn.execute('''
                INSERT INTO pharmacy_inventory (medicine_name, expiry_date, stock_quantity, unit_price) 
                VALUES (?, ?, ?, ?)
            ''', (data['medicine_name'], data['expiry_date'], data['stock_quantity'], data['unit_price']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    
    inventory = conn.execute('SELECT * FROM pharmacy_inventory WHERE stock_quantity > 0').fetchall()
    conn.close()
    return jsonify([dict(i) for i in inventory])

@app.route('/api/pharmacy/inventory/<int:med_id>', methods=['DELETE'])
def delete_medicine(med_id):
    conn = get_db()
    conn.execute('DELETE FROM pharmacy_inventory WHERE id=?', (med_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/pharmacy/sell', methods=['POST'])
def sell_medicine():
    data = request.get_json(force=True)
    conn = get_db()
    now = datetime.now().isoformat()
    try:
        total_bill = 0
        med_summary = ""
        
        for item in data['items']:
            res = conn.execute('SELECT stock_quantity, unit_price, medicine_name FROM pharmacy_inventory WHERE id = ?', (item['id'],)).fetchone()
            
            if not res or res['stock_quantity'] < int(item['qty']):
                return jsonify({"status": "error", "message": f"Insufficient stock for {item['name'] or 'Medicine ID '+str(item['id'])}"}), 400
            
            new_qty = res['stock_quantity'] - int(item['qty'])
            conn.execute('UPDATE pharmacy_inventory SET stock_quantity = ? WHERE id = ?', (new_qty, item['id']))
            total_bill += (res['unit_price'] * int(item['qty']))
            med_summary += f"{res['medicine_name']} (x{item['qty']}), "

        conn.execute('''
            INSERT INTO pharmacy_sales (patient_name, patient_age, patient_phone, problem, medicines_list, total_bill, sale_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data['patient_name'], data['age'], data['phone'], data['problem'], med_summary.strip(", "), total_bill, now))
        
        conn.commit()
        return jsonify({"status": "success", "bill": total_bill})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/pharmacy/history', methods=['GET'])
def get_pharmacy_history():
    conn = get_db()
    sales = conn.execute('SELECT * FROM pharmacy_sales ORDER BY id DESC').fetchall()
    today = datetime.now().strftime('%Y-%m-%d')
    daily = conn.execute('SELECT SUM(total_bill) FROM pharmacy_sales WHERE sale_date LIKE ?', (f'{today}%',)).fetchone()[0] or 0
    conn.close()
    return jsonify({
        "sales": [dict(s) for s in sales],
        "daily": daily
    })

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
    # 1. Force the creation of the database and tables using context manager
    with app.app_context():
        print("Database Initialization Started...")
        init_db() 
        print("Database Initialization Complete.")

    # 2. Get the port from Render
    port = int(os.environ.get("PORT", 5000))
    
    # 3. Run the app (debug=False is mandatory for production)
    app.run(debug=False, port=port, host='0.0.0.0')