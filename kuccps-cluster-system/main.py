from flask import Flask, render_template, request, redirect, session, url_for
from functools import wraps
import os
import csv
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from requests.auth import HTTPBasicAuth
import base64
from datetime import datetime
from flask import Flask
import json
import random
import string
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "kuccps-admin-secret"

# ======= MPESA CONFIG =======
MPESA_CONSUMER_KEY = "uDRO6DrbBALnrmGGirOFe4GNfAAoXALeGvr5Kds66AcDAD5i"
MPESA_CONSUMER_SECRET = "mpApxueWEpYhE9xedaGkta7k83fLpoEuPiNES6bhMaPi3rHiQaSWXdlsJRErcAc"
MPESA_SHORTCODE = "9514880"
MPESA_PASSKEY = "12775367f40cd545f34d5ca77101622bf7c572fb3c6c287fef506ccea269e251"
MPESA_CALLBACK_URL = "https://postinfective-unpraying-noelle.ngrok-free.dev/callback"
MPESA_AMOUNT = 150
MPESA_ACCOUNT_REF = "EARLY BIRD TECH SOLUTIONS KUCCPS CLUSTERS AND COURSES"
MPESA_TRANSACTION_DESC = "KUCCPS Cluster Fee"

# =========================
# DATABASE SETUP
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "kuccps.db")

def generate_access_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def send_cluster_email(to_email, access_code, cluster_points):
    sender = "earlybirdonlinecyber@gmail.com"
    password = "YOUR_GMAIL_APP_PASSWORD"  # Use Gmail App Password

    subject = "Your KUCCPS Cluster Calculation is Ready"
    body = f"""Hello,

Your KUCCPS cluster calculation is ready.

Access code: {access_code}

Top cluster points:
1. Cluster 1: {cluster_points['Cluster 1']}
2. Cluster 2: {cluster_points['Cluster 2']}
3. Cluster 3: {cluster_points['Cluster 3']}

Use this code on the home page to open your saved cluster points and continue course selection.

- Early Bird Cluster Calculator
"""

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_email

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        print("✅ Email sent to", to_email)
    except Exception as e:
        print("❌ Error sending email:", e)    

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            cluster INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            subject TEXT,
            grade TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            name TEXT,
            cutoff REAL
        )
    """)
    conn.commit()
    conn.close()


init_db()


def create_default_admin():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM admins")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )
        print("✅ Default admin created: admin / admin123")
    conn.commit()
    conn.close()


create_default_admin()

# =========================
# IMPORT CLUSTER FORMULAS
# =========================
from clusters import compute_cluster, medicine_eligibility

# =========================
# KCSE SUBJECTS
# =========================
SUBJECTS = {
    "ENG": "English", "KIS": "Kiswahili", "MAT": "Mathematics", "BIO": "Biology",
    "CHE": "Chemistry", "PHY": "Physics", "GSC": "General Science", "HAG": "History & Government",
    "GEO": "Geography", "CRE": "CRE", "IRE": "IRE", "HRE": "HRE",
    "CMP": "Computer Studies", "AGR": "Agriculture", "ARD": "Art & Design",
    "HSC": "Home Science", "BST": "Business Studies", "FRE": "French",
    "GER": "German", "MUS": "Music", "ARB": "Arabic"
}

SUBJECT_NORMALIZATION = {
    "ENGLISH": "ENG", "KISWAHILI": "KIS", "MATHEMATICS": "MAT", "MATH": "MAT",
    "BIOLOGY": "BIO", "CHEMISTRY": "CHE", "PHYSICS": "PHY", "GENERAL SCIENCE": "GSC",
    "HISTORY": "HAG", "HISTORY & GOVERNMENT": "HAG", "GEOGRAPHY": "GEO",
    "CRE": "CRE", "IRE": "IRE", "HRE": "HRE", "COMPUTER STUDIES": "CMP",
    "AGRICULTURE": "AGR", "ART & DESIGN": "ARD", "HOME SCIENCE": "HSC",
    "BUSINESS STUDIES": "BST", "FRENCH": "FRE", "GERMAN": "GER",
    "MUSIC": "MUS", "ARABIC": "ARB"
}

# =========================
# ADMIN AUTH DECORATOR
# =========================
def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/admin")
        return f(*args, **kwargs)
    return wrapped

# Mask email filter here
@app.template_filter('mask_email')
def mask_email(email):
    try:
        local, domain = email.split("@")
        if len(local) > 1:
            local = local[0] + "*" * (len(local)-1)
        return f"{local}@{domain}"
    except:
        return email

# =========================
# ROUTES
# =========================
@app.route("/test-delete")
def test_delete():
    return "TEST ROUTE WORKS"


@app.route("/")
def home():
    return render_template("student/calculator.html")


@app.route("/calculator")
def calculator():
    return render_template("student/calculator.html")


@app.route("/results")
def results():
    if "results" not in session:
        return redirect("/")
    return render_template(
        "student/results.html",
        results=session["results"],
        cluster_courses=session["cluster_courses"]
    )

# =========================
# CALCULATE CLUSTER POINTS
# =========================
@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.form.to_dict()
    print("🔥 DATA RECEIVED:", data)

    # ---- collect grades ----
    grades = {
        "ENG": request.form.get("English", ""),
        "KIS": request.form.get("Kiswahili", ""),
        "MAT": request.form.get("Mathematics", ""),
        "BIO": request.form.get("Biology", ""),
        "CHE": request.form.get("Chemistry", ""),
        "PHY": request.form.get("Physics", ""),
        "GSC": request.form.get("General Science", ""),
        "HAG": request.form.get("History", ""),
        "GEO": request.form.get("Geography", ""),
        "CRE": request.form.get("CRE", ""),
        "IRE": request.form.get("IRE", ""),
        "HRE": request.form.get("HRE", ""),
        "CMP": request.form.get("Computer Studies", ""),
        "AGR": request.form.get("Agriculture", ""),
        "ARD": request.form.get("Art & Design", ""),
        "HSC": request.form.get("Home Science", ""),
        "BST": request.form.get("Business Studies", ""),
        "FRE": request.form.get("French", ""),
        "GER": request.form.get("German", ""),
        "MUS": request.form.get("Music", ""),
        "ARB": request.form.get("Arabic", "")
    }

    # Save grades in session
    session["grades"] = grades

    # ---- PAYMENT CHECK ----
    if "payment_done" not in session:
        return render_template("student/payment.html", grades=grades)

    # ---- compute cluster points ----
    results = {}
    for c in range(1, 21):
        results[c] = compute_cluster(c, grades)

    # ---- get top 3 cluster points ----
    sorted_points = sorted(results.values(), reverse=True)
    top3_points = sorted_points[:3]

    best_cluster = top3_points[0] if len(top3_points) > 0 else 0

    # ---- generate access code ----
    access_code = generate_access_code()

    # ---- save user calculation to DB ----
    email = request.form.get("email", "").strip()

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO calculated_users (date, access_code, name, best_cluster, top3_points)
        VALUES (?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        access_code,
        email,
        str(best_cluster),
        json.dumps(top3_points)
    ))

    conn.commit()
    conn.close()

    # ---- prepare cluster data for email ----
    cluster_email = {
        "Cluster 1": top3_points[0] if len(top3_points) > 0 else 0,
        "Cluster 2": top3_points[1] if len(top3_points) > 1 else 0,
        "Cluster 3": top3_points[2] if len(top3_points) > 2 else 0
    }

    # ---- send email ----
    send_cluster_email(email, access_code, cluster_email)

    # ---- fetch courses added by admin ----
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name, cluster FROM courses")
    rows = cur.fetchall()
    conn.close()

    cluster_courses = {c: [] for c in range(1, 21)}

    for name, cluster in rows:
        cluster_courses[cluster].append({
            "name": name
        })

    # ---- store results in session ----
    session["results"] = results
    session["cluster_email"] = cluster_email
    session["cluster_courses"] = cluster_courses
    session["access_code"] = access_code

    return redirect("/results")

from flask import Flask, request, session, redirect, flash, render_template
import json

@app.route("/access_code", methods=["POST"])
def access_code():
    code = request.form.get("access_code", "").strip().upper()

    # Example: check DB or session for saved results
    # Here we assume session stores past results for simplicity
    if "saved_results" in session and session["saved_results"].get(code):
        session["results"] = session["saved_results"][code]["results"]
        session["cluster_courses"] = session["saved_results"][code]["cluster_courses"]
        return redirect("/results")
    else:
        flash("Invalid access code or no saved results.")
        return redirect("/calculate")


# =========================
# SUBJECT REQUIREMENT CHECK
# =========================
def check_subject_requirements(student_grades, requirements):
    grade_order = {
        "A": 12, "A-": 11, "B+": 10, "B": 9, "B-": 8,
        "C+": 7, "C": 6, "C-": 5, "D+": 4, "D": 3, "D-": 2, "E": 1
    }

    clean_grades = {}
    for k, v in student_grades.items():
        if v and v.strip():
            clean_grades[k.strip().upper()] = v.strip().upper()

    failed = []
    for requirement, required_grade in requirements.items():
        options = []
        for s in requirement.split("/"):
            key = s.strip().upper()
            options.append(SUBJECT_NORMALIZATION.get(key, key))

        met = False
        matched_subject = None
        matched_grade = None
        for subject in options:
            if subject in clean_grades:
                student_grade = clean_grades[subject]
                if grade_order.get(student_grade, 0) >= grade_order[required_grade]:
                    met = True
                    break
                matched_subject = subject
                matched_grade = student_grade
        if not met:
            failed.append({
                "subject": requirement,
                "required": required_grade,
                "student_subject": matched_subject,
                "student_grade": matched_grade
            })

    return {"passed": len(failed) == 0, "failed": failed}


# =========================
# CHECK COURSE DETAILS
# =========================
@app.route("/check-course")
def check_course():
    cluster = int(request.args.get("cluster"))
    points = float(request.args.get("points"))
    course_name = request.args.get("course_name")

    conn = db()
    cur = conn.cursor()

    # Get course id
    cur.execute("SELECT id FROM courses WHERE name=? AND cluster=?", (course_name, cluster))
    row = cur.fetchone()
    if not row:
        conn.close()
        return "Course not found for this cluster"
    course_id = row[0]

    # Get requirements
    cur.execute("SELECT subject, grade FROM requirements WHERE course_id=?", (course_id,))
    requirements = dict(cur.fetchall())

    # Get universities
    cur.execute("SELECT name, cutoff FROM universities WHERE course_id=?", (course_id,))
    universities = cur.fetchall()
    conn.close()

    # Subject requirement check
    subject_check = check_subject_requirements(session.get("grades", {}), requirements)

    qualified = []
    not_qualified = []
    if subject_check["passed"]:
        for uni, cutoff in universities:
            if points >= cutoff:
                qualified.append((uni, cutoff))
            else:
                not_qualified.append((uni, cutoff))

    return render_template(
        "student/course_result.html",
        course=course_name,
        cluster=cluster,
        points=points,
        subject_check=subject_check,
        qualified=qualified,
        not_qualified=not_qualified
    )


# =========================
# ADMIN LOGIN / DASHBOARD / SETTINGS / CRUD
# =========================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM admins WHERE username=?", (username,))
        admin = cur.fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = True
            session["admin_name"] = admin["name"] or username
            session["admin_email"] = admin["username"]

            return redirect(url_for("admin_dashboard"))

        return render_template(
            "admin/dashboard.html",
            login=True,
            error="Invalid login",
            current_admin={"name": "", "email": ""}
        )

    return render_template(
        "admin/dashboard.html",
        login=True,
        current_admin={"name": "", "email": ""}
    )


@app.route("/admin/create", methods=["POST"])
@admin_required
def create_admin():

    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")

    if not name or not email or not password:
        flash("All fields are required!")
        return redirect(url_for("admin_dashboard"))

    conn = db()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO admins (username, password, name) VALUES (?, ?, ?)",
            (email, generate_password_hash(password), name)
        )
        conn.commit()
        flash(f"✅ Admin '{name}' created successfully!")

    except sqlite3.IntegrityError:
        flash(f"❌ Admin with email '{email}' already exists!")

    finally:
        conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    conn = db()
    cur = conn.cursor()

    # -------------------------
    # LOAD COURSES
    # -------------------------
    cur.execute("SELECT id, name, cluster FROM courses")
    rows = cur.fetchall()

    courses = {c: [] for c in range(1, 21)}

    for cid, name, cluster in rows:

        if cluster not in courses:
            continue

        cur.execute(
            "SELECT subject, grade FROM requirements WHERE course_id=?",
            (cid,)
        )
        reqs = dict(cur.fetchall())

        cur.execute(
            "SELECT name, cutoff FROM universities WHERE course_id=?",
            (cid,)
        )
        unis = [{"name": u, "cutoff": c} for u, c in cur.fetchall()]

        courses[cluster].append({
            "id": cid,
            "name": name,
            "requirements": reqs,
            "universities": unis
        })

    # -------------------------
    # DASHBOARD COUNTS
    # -------------------------
    cur.execute("SELECT COUNT(DISTINCT cluster) FROM courses")
    clusters_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM courses")
    courses_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM universities")
    universities_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM admins")
    admin_count = cur.fetchone()[0]

    # -------------------------
    # CALCULATED USERS
    # -------------------------
    cur.execute("""
        SELECT id, date, access_code, name, best_cluster, top3_points
        FROM calculated_users
    """)

    calculated_users = [
        dict(
            id=r[0],
            date=r[1],
            access_code=r[2],
            name=r[3],
            best_cluster=r[4],
            top3_points=r[5]
        )
        for r in cur.fetchall()
    ]

    # -------------------------
    # LOAD ADMINS
    # -------------------------
    cur.execute("SELECT id, username, name FROM admins")

    admins = [
        dict(id=r[0], username=r[1], name=r[2])
        for r in cur.fetchall()
    ]

    # -------------------------
    # CURRENT LOGGED IN ADMIN
    # -------------------------
    current_admin = {
        "name": session.get("admin_name", "Admin"),
        "email": session.get("admin_email", "admin@example.com")
    }

    conn.close()

    return render_template(
        "admin/dashboard.html",
        courses=courses,
        admins=admins,
        subjects=SUBJECTS,
        clusters_count=clusters_count,
        courses_count=courses_count,
        universities_count=universities_count,
        admin_count=admin_count,
        calculated_users=calculated_users,
        current_admin=current_admin
    )


@app.route("/access", methods=["POST"])
def access_by_code():

    code = request.form.get("access_code", "").strip().upper()

    if not code:
        return "Please enter an access code", 400

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT best_cluster, top3_points
        FROM calculated_users
        WHERE access_code=?
    """, (code,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return "❌ Invalid access code. Please check your email.", 400

    best_cluster = row[0]
    top3_points = json.loads(row[1])

    # Prepare results
    cluster_email = {
        "Cluster 1": top3_points[0] if len(top3_points) > 0 else 0,
        "Cluster 2": top3_points[1] if len(top3_points) > 1 else 0,
        "Cluster 3": top3_points[2] if len(top3_points) > 2 else 0
    }

    # Save to session
    session["results"] = cluster_email
    session["access_code"] = code

    return redirect("/results")

# Route to add a new course manually
@app.route("/admin/add-course", methods=["POST"])
@admin_required
def add_course():
    data = request.form
    conn = db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO courses (name, cluster, course_code, cutoff) VALUES (?, ?, ?, ?)",
        (data["name"], data["cluster"], data["course_code"], data["cutoff"])
    )
    course_id = cur.lastrowid

    # Insert requirements
    requirements = data["requirements"].split("|")  # e.g. "Math:C+ | English:B"
    for r in requirements:
        if ":" in r:
            subject, grade = r.strip().split(":")
            cur.execute("INSERT INTO requirements (course_id, subject, grade) VALUES (?, ?, ?)", (course_id, subject.strip(), grade.strip()))

    # Insert university
    cur.execute("INSERT INTO universities (course_id, name, cutoff) VALUES (?, ?, ?)", (course_id, data["university"], data["cutoff"]))

    conn.commit()
    conn.close()
    flash("Course added successfully!")
    return redirect(url_for("admin_dashboard"))


# Route to upload courses CSV
@app.route("/admin/upload-csv", methods=["POST"])
@admin_required
def upload_courses_csv():
    import csv, io

    file = request.files.get("courses_csv")
    if not file:
        flash("No file selected")
        return redirect(url_for("admin_dashboard"))

    conn = db()
    cur = conn.cursor()

    # For tracking current course/cluster while reading rows
    current_course_name = None
    current_cluster = None
    current_requirements = ""

    reader = csv.reader(io.TextIOWrapper(file.stream, encoding="utf-8"))
    for row in reader:
        # Skip empty rows
        if not any(row):
            continue

        # Detect new course row (first column non-empty string, second column = cluster)
        if row[0] and row[1]:
            current_course_name = row[0].strip()
            try:
                current_cluster = int(row[1].strip())
            except ValueError:
                current_cluster = None
            current_requirements = row[3] if len(row) > 3 else ""
            continue  # Skip to next row

        # University rows (usually first column empty)
        if current_course_name and current_cluster is not None:
            course_code = row[2].strip() if len(row) > 2 else ""
            university_name = row[3].strip() if len(row) > 3 else ""
            cutoff_str = row[4].strip() if len(row) > 4 else "0"
            try:
                cutoff = float(cutoff_str) if cutoff_str and cutoff_str != "-" else 0
            except ValueError:
                cutoff = 0

            # Insert course only once per course name
            cur.execute(
                "INSERT INTO courses (name, cluster, course_code, cutoff) VALUES (?, ?, ?, ?)",
                (current_course_name, current_cluster, course_code, cutoff)
            )
            course_id = cur.lastrowid

            # Handle requirements
            reqs = current_requirements.split("|")
            for r in reqs:
                if ":" in r:
                    subject, grade = r.strip().split(":")
                    cur.execute(
                        "INSERT INTO requirements (course_id, subject, grade) VALUES (?, ?, ?)",
                        (course_id, subject.strip(), grade.strip())
                    )

            # Insert university info
            if university_name:
                cur.execute(
                    "INSERT INTO universities (course_id, name, cutoff) VALUES (?, ?, ?)",
                    (course_id, university_name, cutoff)
                )

    conn.commit()
    conn.close()
    flash("✅ CSV uploaded successfully!")
    return redirect(url_for("admin_dashboard"))


# Route to logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin_login"))

import sqlite3
from werkzeug.security import generate_password_hash
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kuccps.db")

conn = sqlite3.connect(DB)
c = conn.cursor()

# 1. Admins
c.execute("""
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT
)
""")

# 2. Courses
c.execute("""
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cluster INTEGER NOT NULL,
    course_code TEXT,
    cutoff REAL
)
""")

# 3. Requirements
c.execute("""
CREATE TABLE IF NOT EXISTS requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    grade TEXT NOT NULL,
    FOREIGN KEY(course_id) REFERENCES courses(id)
)
""")

# 4. Universities
c.execute("""
CREATE TABLE IF NOT EXISTS universities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    cutoff REAL,
    FOREIGN KEY(course_id) REFERENCES courses(id)
)
""")

# 5. Calculated Users
c.execute("""
CREATE TABLE IF NOT EXISTS calculated_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    access_code TEXT NOT NULL,
    name TEXT NOT NULL,
    best_cluster TEXT,
    top3_points TEXT
)
""")

# Optional: create default admin
c.execute("SELECT COUNT(*) FROM admins")
if c.fetchone()[0] == 0:
    c.execute(
        "INSERT INTO admins (username, password, name) VALUES (?, ?, ?)",
        ("admin", generate_password_hash("admin123"), "Super Admin")
    )
    print("✅ Default admin created: admin / admin123")

conn.commit()
conn.close()
print("✅ All tables created successfully")

import requests
from flask import request, redirect, url_for, session
@app.route("/mpesa_callback", methods=["POST"])
def mpesa_callback():
    data = request.json
    print("MPESA CALLBACK:", data)
    
    try:
        result_code = data["Body"]["stkCallback"]["ResultCode"]
        callback_items = data["Body"]["stkCallback"].get("CallbackMetadata", {}).get("Item", [])
        
        phone = ""
        amount = 0
        for item in callback_items:
            if item["Name"] == "PhoneNumber":
                phone = str(item["Value"])
            if item["Name"] == "Amount":
                amount = float(item["Value"])

        conn = db()
        cur = conn.cursor()

        if result_code == 0:
            cur.execute(
                "INSERT INTO payments (phone, amount, status, timestamp) VALUES (?, ?, ?, ?)",
                (phone, amount, "SUCCESS", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        else:
            cur.execute(
                "INSERT INTO payments (phone, amount, status, timestamp) VALUES (?, ?, ?, ?)",
                (phone, amount, "FAILED", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )

        conn.commit()
        conn.close()

    except Exception as e:
        print("Callback error:", e)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}

@app.route("/check-payment", methods=["GET"])
def check_payment():
    phone = request.args.get("phone")
    if not phone:
        return {"status": "error", "message": "Phone number required"}

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT status FROM payments WHERE phone=? ORDER BY id DESC LIMIT 1", (phone,))
    row = cur.fetchone()
    conn.close()

    if row:
        return {"status": row[0].lower()}
    else:
        return {"status": "pending"}

@app.route("/stk_push", methods=["POST"])
def stk_push():
    phone = request.form.get("phone")
    if not phone:
        return "Phone number required"

    if phone.startswith("07"):
        phone = "254" + phone[1:]

    response = stk_push_request(phone)

    if response.get("ResponseCode") == "0":
        return render_template("student/waiting_payment.html", phone=phone)
    else:
        print("STK push failed:", response)
        return "Payment initiation failed, try again."

# =========================
# MPESA ACCESS TOKEN
# =========================
def get_access_token():
    url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(
        url,
        auth=HTTPBasicAuth(MPESA_CONSUMER_KEY.strip(), MPESA_CONSUMER_SECRET.strip()),
        allow_redirects=False
    )
    print("STATUS:", response.status_code)
    print("BODY:", response.text)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Failed to get access token: {response.status_code} {response.text}")

# =========================
# STK PUSH REQUEST
# =========================
def stk_push_request(phone_number):

    access_token = get_access_token()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    password = base64.b64encode(
        (MPESA_SHORTCODE + MPESA_PASSKEY + timestamp).encode()
    ).decode("utf-8")

    url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerBuyGoodsOnline",
        "Amount": MPESA_AMOUNT,
        "PartyA": phone_number,
        "PartyB": "8583554",
        "PhoneNumber": phone_number,
        "CallBackURL": MPESA_CALLBACK_URL,
        "AccountReference": MPESA_ACCOUNT_REF,
        "TransactionDesc": MPESA_TRANSACTION_DESC
    }

    response = requests.post(url, json=payload, headers=headers)

    print("MPESA RESPONSE:", response.json())

    return response.json()


# =========================
# ADMIN ACTION ROUTES
# =========================

# Delete Admin
@app.route("/admin/delete-admin/<int:admin_id>")
@admin_required
def delete_admin(admin_id):

    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM admins WHERE id=?", (admin_id,))
    conn.commit()

    conn.close()

    return redirect(url_for("admin_dashboard"))


# Edit Course (placeholder page)
@app.route("/admin/edit-course/<int:course_id>")
@admin_required
def edit_course(course_id):

    conn = db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM courses WHERE id=?", (course_id,))
    course = cur.fetchone()

    cur.execute("SELECT subject, grade FROM requirements WHERE course_id=?", (course_id,))
    requirements = cur.fetchall()

    cur.execute("SELECT name, cutoff, course_code FROM universities WHERE course_id=?", (course_id,))
    universities = cur.fetchall()

    conn.close()

    return render_template(
        "admin/edit_course.html",
        course=course,
        requirements=requirements,
        universities=universities
    )


# Delete Course
@app.route("/admin/delete-course/<int:course_id>")
@admin_required
def delete_course(course_id):

    conn = db()
    cur = conn.cursor()

    # delete related data first
    cur.execute("DELETE FROM requirements WHERE course_id=?", (course_id,))
    cur.execute("DELETE FROM universities WHERE course_id=?", (course_id,))
    cur.execute("DELETE FROM courses WHERE id=?", (course_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


# View Calculated User
@app.route("/admin/view-user/<int:user_id>")
@admin_required
def view_user(user_id):

    conn = db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM calculated_users WHERE id=?", (user_id,))
    user = cur.fetchone()

    conn.close()

    return render_template(
        "admin/view_user.html",
        user=user
    )


# Delete Calculated User
@app.route("/admin/delete-user/<int:user_id>")
@admin_required
def delete_user(user_id):

    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM calculated_users WHERE id=?", (user_id,))
    conn.commit()

    conn.close()

    return redirect(url_for("admin_dashboard"))


# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
