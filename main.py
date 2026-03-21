from flask import Flask, render_template, request, redirect, session, url_for, make_response, flash
from functools import wraps
import os
import csv
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import base64
from datetime import datetime
from flask import jsonify
from zoneinfo import ZoneInfo
import json
import random
import string
import smtplib
from email.mime.text import MIMEText
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from flask import send_file
import io
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = "kuccps-admin-secret"
app.config["SESSION_COOKIE_SECURE"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# =========================
# MPESA CONFIG
# =========================
consumer_key = "uDRO6DrbBALnrmGGirOFe4GNfAAoXALeGvr5Kds66AcDAD5i"
consumer_secret = "mpApxueWEpYhE9xedaGkta7k83fLpoEuPiNES6bhMaPi3rHiQaSWXdlsJRErcAcR"

shortcode = "9514880"

passkey = "12775367f40cd545f34d5ca77101622bf7c572fb3c6c287fef506ccea269e251"

# =========================
# DATABASE SETUP
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "kuccps.db")

def generate_access_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def send_cluster_email(to_email, access_code, cluster_points):
    """
    Sends cluster email safely.
    Will not crash if email fails, logs error instead.
    """
    sender = "earlybirdonlinecyber@gmail.com"
    password = "kbejotxdnppjzbeb"

    # Use .get() to avoid KeyError
    c1 = cluster_points.get("Cluster 1", 0)
    c2 = cluster_points.get("Cluster 2", 0)
    c3 = cluster_points.get("Cluster 3", 0)

    subject = "Your KUCCPS Cluster Calculation is Ready"
    body = f"""Hello,

Your KUCCPS cluster calculation is ready.

Access code: {access_code}

Top cluster points:
1. Cluster 1: {c1}
2. Cluster 2: {c2}
3. Cluster 3: {c3}

Use this code on the home page to open your saved cluster points and continue course selection.

- Early Bird Cluster Calculator
"""

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to_email

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {e}")   

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    c = conn.cursor()

    # ADMINS
    c.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT
    )
    """)

    # COURSES
    c.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        cluster INTEGER NOT NULL,
        course_code TEXT
    )
    """)

    # SUBJECT REQUIREMENTS
    c.execute("""
    CREATE TABLE IF NOT EXISTS requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        subject TEXT,
        grade TEXT
    )
    """)

    # UNIVERSITIES OFFERING COURSE
    c.execute("""
    CREATE TABLE IF NOT EXISTS universities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        name TEXT,
        course_code TEXT,
        cutoff REAL
    )
    """)

    # CALCULATED USERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS calculated_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        access_code TEXT,
        email TEXT,
        best_cluster TEXT,
        top3_points TEXT,
        full_results TEXT
    )
    """)

    # PAYMENTS TABLE
    c.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        email TEXT,
        checkout_id TEXT,
        status TEXT
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

    # Load courses from DB
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name, cluster FROM courses")
    rows = cur.fetchall()
    conn.close()

    # Create a dict of clusters to courses
    cluster_courses = {str(c): [] for c in range(1, 21)}
    for name, cluster in rows:
        try:
            cluster = int(cluster)
        except:
            continue
        cluster_courses[str(cluster)].append({
            "name": name
        })

    # session["results"] now has all clusters (full_results)
    full_results = session.get("results", {})  # all cluster points

    # keep top 3 cluster points
    top3_points = sorted(full_results.items(), key=lambda x: x[1], reverse=True)[:3]

    # sort results by cluster number
    sorted_results = dict(sorted(full_results.items(), key=lambda x: int(x[0])))

    return render_template(
        "student/results.html",
        results=sorted_results,
        top3=top3_points,
        cluster_courses=cluster_courses,
        points=max(full_results.values())  # pass default points for template links
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
    # ---- prevent duplicate email ----
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM calculated_users WHERE email=?", (email,))
    existing_user = cur.fetchone()

    if existing_user:
        conn.close()
        flash("Email already exists. Please use another email or use your access code to reopen results.")
        return redirect("/")
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO calculated_users (
        date,
        access_code,
        email,
        best_cluster,
        top3_points,
        full_results
    )
    VALUES (?, ?, ?, ?, ?, ?)
""", (
    datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y-%m-%d %H:%M:%S"),
    access_code,
    email,
    str(best_cluster),
    json.dumps(top3_points),   # only top 3 used for email
    json.dumps(results)        # store ALL clusters
))
    conn.commit()
    conn.close()

    # ---- prepare cluster data for email ----
    cluster_email = {
        "Cluster 1": top3_points[0] if len(top3_points) > 0 else 0,
        "Cluster 2": top3_points[1] if len(top3_points) > 1 else 0,
        "Cluster 3": top3_points[2] if len(top3_points) > 2 else 0
    }

    # ---- send email safely ----
    try:
        send_cluster_email(email, access_code, cluster_email)
    except Exception as e:
        print(f"❌ Error sending cluster email (will not crash app): {e}")

    # ---- fetch courses added by admin ----
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name, cluster FROM courses")
    rows = cur.fetchall()
    conn.close()

    cluster_courses = {str(c): [] for c in range(1, 21)}

    for name, cluster in rows:
        try:
            cluster = int(cluster)
        except:
            continue

        if str(cluster) not in cluster_courses:
            continue

        cluster_courses[str(cluster)].append({
            "name": name
        })


    # ---- store results in session ----
    session["results"] = results
    session["cluster_email"] = cluster_email
    session["access_code"] = access_code

    return redirect("/results")

@app.route("/access", methods=["POST"])
def access_by_code():
    code = request.form.get("access_code", "").strip().upper()
    if not code:
        return "Please enter an access code", 400

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT full_results FROM calculated_users WHERE access_code=?", (code,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return "❌ Invalid access code.", 400

    results = json.loads(row[0])
    # Sort clusters numerically
    sorted_results = dict(sorted(results.items(), key=lambda x: int(x[0])))

    session["results"] = sorted_results
    session["access_code"] = code
    return redirect("/results")


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
                if grade_order.get(student_grade, 0) >= grade_order.get(required_grade, 0):
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

    # =========================
    # GET COURSE
    # =========================
    cur.execute(
        "SELECT id, course_code FROM courses WHERE name=? AND cluster=?",
        (course_name, cluster)
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        return "Course not found"

    course_id = row[0]
    course_code = row[1]

    # =========================
    # GET REQUIREMENTS
    # =========================
    cur.execute(
        "SELECT subject, grade FROM requirements WHERE course_id=?",
        (course_id,)
    )

    requirements = dict(cur.fetchall())

    # =========================
    # GET UNIVERSITIES
    # =========================
    cur.execute(
        "SELECT name, cutoff, course_code FROM universities WHERE course_id=?",
        (course_id,)
    )

    universities = cur.fetchall()

    conn.close()

    # =========================
    # SUBJECT CHECK
    # =========================
    subject_check = check_subject_requirements(
        session.get("grades", {}),
        requirements
    )

    qualified = []
    not_qualified = []

    # =========================
    # CHECK QUALIFICATION
    # =========================
    if subject_check["passed"]:

        for uni, cutoff, code in universities:

            uni = uni if uni and uni.strip() else "Unknown University"

            margin = round(points - cutoff, 3)

            if points >= cutoff:
                qualified.append({
                    "university": uni,
                    "course_code": code,
                    "cutoff": cutoff,
                    "margin": f"+{margin}"
                })
            else:
                not_qualified.append({
                    "university": uni,
                    "course_code": code,
                    "cutoff": cutoff,
                    "margin": f"{margin}"
                })

    else:

        for uni, cutoff, code in universities:
            not_qualified.append({
                "university": uni,
                "course_code": code,
                "cutoff": cutoff,
                "margin": "Subjects not met"
            })

    # =========================
    # FALLBACK IF EMPTY
    # =========================
    if not qualified and not not_qualified:

        for uni, cutoff, code in universities:
            not_qualified.append({
                "university": uni,
                "course_code": code,
                "cutoff": cutoff,
                "margin": "Check requirements"
            })

    return render_template(
        "student/course_result.html",
        course=course_name,
        course_code=course_code,
        cluster=cluster,
        points=points,
        subject_check=subject_check,
        qualified=qualified,
        not_qualified=not_qualified
    )


@app.route("/download-course-pdf")
def download_course_pdf():

    course = request.args.get("course")
    cluster = request.args.get("cluster")
    points = float(request.args.get("points"))

    conn = db()
    cur = conn.cursor()

    # Get course id
    cur.execute("SELECT id FROM courses WHERE email=?", (course,))
    row = cur.fetchone()

    if not row:
        return "Course not found"

    course_id = row[0]

    # Get universities
    cur.execute("SELECT name, course_code, cutoff FROM universities WHERE course_id=?", (course_id,))
    universities = cur.fetchall()

    conn.close()

    qualified = []
    not_qualified = []

    for uni, code, cutoff in universities:
        if points >= cutoff:
            qualified.append((uni, code, cutoff, points - cutoff))
        else:
            not_qualified.append((uni, code, cutoff, cutoff - points))

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Early Bird Course Finder", styles['Title']))
    elements.append(Spacer(1,10))

    elements.append(Paragraph(f"Course: {course}", styles['Normal']))
    elements.append(Paragraph(f"Cluster: {cluster}", styles['Normal']))
    elements.append(Paragraph(f"Cluster Points: {points}", styles['Normal']))
    elements.append(Spacer(1,20))

    # Qualified table
    if qualified:

        data = [["#", "University", "Course Code", "Cutoff", "Margin"]]

        for i,(u,code,c,m) in enumerate(qualified,1):
            data.append([i,u,code,c,f"+{m:.3f}"])

        table = Table(data)

        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.darkblue),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('GRID',(0,0),(-1,-1),1,colors.grey)
        ]))

        elements.append(Paragraph("Qualified Universities", styles['Heading2']))
        elements.append(table)
        elements.append(Spacer(1,20))

    # Not qualified table
    if not_qualified:

        data = [["#", "University", "Course Code", "Cutoff", "Margin"]]

        for i,(u,code,c,m) in enumerate(not_qualified,1):
            data.append([i,u,code,c,f"-{m:.3f}"])

        table = Table(data)

        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.darkblue),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('GRID',(0,0),(-1,-1),1,colors.grey)
        ]))

        elements.append(Paragraph("Not Qualified Universities", styles['Heading2']))
        elements.append(table)

    elements.append(Spacer(1,40))
    elements.append(Paragraph("Thanks for using Early Bird Course Finder", styles['Normal']))
    elements.append(Paragraph("For inquiries: 0759080437", styles['Normal']))

    doc.build(elements)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="course_result.pdf",
        mimetype="application/pdf"
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

        resp = make_response(
            render_template(
                "admin/dashboard.html",
                login=True,
                error="Invalid login",
                current_admin={"name": "", "email": ""}
            )
        )
        # Prevent caching
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    resp = make_response(
        render_template(
            "admin/dashboard.html",
            login=True,
            current_admin={"name": "", "email": ""}
        )
    )
    # Prevent caching
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# =========================
# ADMIN DASHBOARD (MODIFIED)
# =========================
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    # Determine which section to show (default: overview)
    show_section = request.args.get("show", "overview")

    conn = db()
    cur = conn.cursor()

    # -------------------------
    # Load Courses
    # -------------------------
    cur.execute("SELECT id, name, cluster FROM courses")
    rows = cur.fetchall()
    courses = {c: [] for c in range(1, 21)}

    for cid, name, cluster in rows:

        try:
            cluster = int(cluster)
        except:
            continue

        if cluster not in courses:
            continue

        cur.execute("SELECT subject, grade FROM requirements WHERE course_id=?", (cid,))
        req_rows = cur.fetchall()

        reqs = ""
        for subject, grade in req_rows:
            reqs += f"{subject} : {grade}\n"



        cur.execute("SELECT name, course_code, cutoff FROM universities WHERE course_id=?", (cid,))
        uni_rows = cur.fetchall()

        unis = []
        for u, code, cutoff in uni_rows:
            unis.append({
                "name": u,
                "course_code": code,
                "cutoff": cutoff
            })

        courses[cluster].append({
            "id": cid,
            "name": name,
            "requirements": reqs,
            "universities": unis
        })


    # -------------------------
    # Dashboard Counts
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
    # Calculated Users
    # -------------------------
    cur.execute("""
            SELECT id, date, access_code, email, full_results
            FROM calculated_users
            ORDER BY id DESC
        """)
    calculated_users = [
            dict(
                id=r[0],
                date=r[1],
                access_code=r[2],
                name=r[3],
                full_results=r[4]
            )
            for r in cur.fetchall()
        ]

    # -------------------------
    # Admins
    # -------------------------
    cur.execute("SELECT id, username, name FROM admins")
    admins = [
        dict(id=r[0], username=r[1], name=r[2])
        for r in cur.fetchall()
    ]

    # -------------------------
    # Current Admin
    # -------------------------
    current_admin = {
        "name": session.get("admin_name", "Admin"),
        "email": session.get("admin_email", "admin@example.com")
    }

    conn.close()

    # -------------------------
    # Render dashboard
    # -------------------------
    resp = make_response(
        render_template(
            "admin/dashboard.html",
            courses=courses,
            admins=admins,
            subjects=SUBJECTS,
            clusters_count=clusters_count,
            courses_count=courses_count,
            universities_count=universities_count,
            admin_count=admin_count,
            calculated_users=calculated_users,
            current_admin=current_admin,
            show_section=show_section  # tells template which tab to show
        )
    )

    # Prevent caching
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"

    return resp


# =========================
# CRUD ROUTES THAT STAY ON CURRENT SECTION
# =========================

# Delete Calculated User
@app.route("/admin/delete-user/<int:user_id>")
@admin_required
def delete_user(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM calculated_users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard", show="calculated_users"))

@app.route("/admin/edit-course/<int:course_id>", methods=["POST"])
@admin_required
def edit_course(course_id):

    name = request.form["name"]
    requirements_text = request.form.get("requirements", "")

    universities = request.form["universities"].split("\n")
    codes = request.form["course_codes"].split("\n")
    cutoffs = request.form["cutoffs"].split("\n")

    conn = db()
    cur = conn.cursor()

    # -----------------------------
    # UPDATE COURSE NAME
    # -----------------------------
    cur.execute("UPDATE courses SET name=? WHERE id=?", (name, course_id))

    # -----------------------------
    # UPDATE REQUIREMENTS
    # -----------------------------
    cur.execute("DELETE FROM requirements WHERE course_id=?", (course_id,))

    if requirements_text:
        lines = requirements_text.splitlines()

        for r in lines:
            parts = r.split(":", 1)

            if len(parts) == 2:
                subject = parts[0].strip()
                grade = parts[1].strip()

                cur.execute(
                    "INSERT INTO requirements (course_id, subject, grade) VALUES (?, ?, ?)",
                    (course_id, subject, grade)
                )

    # -----------------------------
    # UPDATE UNIVERSITIES
    # -----------------------------
    cur.execute("DELETE FROM universities WHERE course_id=?", (course_id,))

    for u, c, cut in zip(universities, codes, cutoffs):

        if not u.strip():
            continue

        cur.execute(
            "INSERT INTO universities(course_id,name,course_code,cutoff) VALUES (?,?,?,?)",
            (course_id, u.strip(), c.strip(), cut.strip())
        )

    conn.commit()
    conn.close()

    flash("✅ Course updated successfully!")
    return redirect(url_for("admin_dashboard", show="courses") + "#courses")

# =========================
# ADD COURSE
# =========================
@app.route("/admin/add-course", methods=["POST"])
@admin_required
def add_course():

    name = request.form["name"]
    cluster = request.form["cluster"]
    requirements_text = request.form.get("requirements", "")

    universities = request.form.get("universities", "").split("\n")
    codes = request.form.get("course_codes", "").split("\n")
    cutoffs = request.form.get("cutoffs", "").split("\n")

    conn = db()
    cur = conn.cursor()

    # -----------------------------
    # INSERT COURSE
    # -----------------------------
    cur.execute(
        "INSERT INTO courses (name, cluster) VALUES (?, ?)",
        (name, cluster)
    )

    course_id = cur.lastrowid

    # -----------------------------
    # INSERT REQUIREMENTS
    # -----------------------------
    if requirements_text:

        for r in requirements_text.splitlines():

            r = r.strip()
            if not r:
                continue

            parts = r.split(":", 1)

            if len(parts) == 2:
                subject = parts[0].strip()
                grade = parts[1].strip()

                cur.execute(
                    "INSERT INTO requirements (course_id, subject, grade) VALUES (?, ?, ?)",
                    (course_id, subject, grade)
                )

    # -----------------------------
    # INSERT UNIVERSITIES
    # -----------------------------
    for u, c, cut in zip(universities, codes, cutoffs):

        if not u.strip():
            continue

        cur.execute(
            "INSERT INTO universities (course_id, name, course_code, cutoff) VALUES (?, ?, ?, ?)",
            (course_id, u.strip(), c.strip(), cut.strip())
        )

    conn.commit()
    conn.close()

    flash("✅ Course added successfully!")
    return redirect(url_for("admin_dashboard", show="courses") + "#courses")

# Create Admin
@app.route("/admin/create", methods=["POST"])
@admin_required
def create_admin():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")

    if not name or not email or not password:
        flash("All fields are required!")
        return redirect(url_for("admin_dashboard", show="admins"))

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

    return redirect(url_for("admin_dashboard", show="admins"))


# Delete Admin
@app.route("/admin/delete-admin/<int:admin_id>")
@admin_required
def delete_admin(admin_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE id=?", (admin_id,))
    conn.commit()
    conn.close()
    flash("✅ Admin deleted successfully!")
    return redirect(url_for("admin_dashboard", show="admins"))


# Route to upload courses CSV
@app.route("/admin/upload-csv", methods=["POST"])
@admin_required
def upload_courses_csv():

    import csv, io, re

    file = request.files.get("courses_csv")

    if not file:
        flash("No CSV selected")
        return redirect(url_for("admin_dashboard"))

    conn = db()
    cur = conn.cursor()

    reader = csv.DictReader(io.TextIOWrapper(file.stream, encoding="utf-8-sig"))

    current_course = None
    current_cluster = None
    course_id = None

    for row in reader:

        course_value = (row.get("course_name") or "").strip()
        cluster_value = (row.get("cluster") or "").strip()
        requirements_value = (row.get("requirements") or "").strip()

        # -------- NEW COURSE --------
        if course_value:

            current_course = course_value
            current_cluster = int(cluster_value)

            cur.execute(
                "INSERT INTO courses (name, cluster) VALUES (?, ?)",
                (current_course, current_cluster)
            )

            course_id = cur.lastrowid

        # -------- REQUIREMENTS (can appear later) --------
        if requirements_value and course_id:

            reqs = re.split(r'\||\n', requirements_value)

            for r in reqs:

                r = r.strip()

                if not r or ":" not in r:
                    continue

                subject, grade = r.split(":", 1)

                # CLEAN SUBJECT FORMAT (removes space before :)
                subject = subject.replace(" :", "").strip()
                grade = grade.strip()

                cur.execute(
                    "INSERT INTO requirements (course_id, subject, grade) VALUES (?, ?, ?)",
                    (course_id, subject, grade)
                )

        # -------- UNIVERSITY DATA --------
        university = (row.get("university") or "").strip()
        course_code = (row.get("course_code") or "").strip()
        cutoff_value = (row.get("cutoff") or "").strip()

        if cutoff_value in ["", "-", "NA", "N/A"]:
            cutoff = 0
        else:
            try:
                cutoff = float(cutoff_value)
            except:
                cutoff = 0

        if university and course_id:

            cur.execute(
                "INSERT INTO universities (course_id, name, course_code, cutoff) VALUES (?, ?, ?, ?)",
                (course_id, university, course_code, cutoff)
            )

    conn.commit()
    conn.close()

    flash("CSV imported successfully")
    return redirect(url_for("admin_dashboard"))

# Route to logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin_login"))

# =========================
# ADMIN ACTION ROUTES
# =========================

@app.template_filter("from_json")
def from_json_filter(value):
    try:
        return json.loads(value)
    except:
        return {}

# =========================
# DELETE COURSE
# =========================
@app.route("/admin/delete-course/<int:course_id>")
@admin_required
def delete_course(course_id):

    conn = db()
    cur = conn.cursor()

    # delete requirements first
    cur.execute("DELETE FROM requirements WHERE course_id=?", (course_id,))

    # delete universities
    cur.execute("DELETE FROM universities WHERE course_id=?", (course_id,))

    # delete course
    cur.execute("DELETE FROM courses WHERE id=?", (course_id,))

    conn.commit()
    conn.close()

    flash("✅ Course deleted successfully!")
    return redirect(url_for("admin_dashboard", show="courses") + "#courses")

@app.route("/stkpush", methods=["POST"])
def stkpush():

    data = request.get_json()
    print("STK REQUEST:", data)

    phone = data.get("phone")

    # Normalize phone
    if phone.startswith("07"):
        phone = "254" + phone[1:]
    elif phone.startswith("+254"):
        phone = phone[1:]

    email = data.get("email")

    if not phone or not email:
        return jsonify({"status": "error", "message": "Phone and email required"})


    conn = sqlite3.connect("kuccps.db")
    cursor = conn.cursor()

    # Prevent duplicate emails
    cursor.execute("SELECT id FROM calculated_users WHERE email=?", (email,))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return jsonify({
            "status": "error",
            "message": "This email already exists. Fetch your access code instead."
        })

    conn.close()


    try:


        # GET ACCESS TOKEN (LIVE)
        url = "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

        r = requests.get(url, auth=(consumer_key, consumer_secret))
        token_response = r.json()

        if "access_token" not in token_response:
            return jsonify({"status":"error","message":"Failed to get access token"})

        access_token = token_response["access_token"]

        # GENERATE PASSWORD
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        password = base64.b64encode(
            (shortcode + passkey + timestamp).encode()
        ).decode()


        # STK PUSH URL (LIVE)
        stk_url = "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"


        payload = {

            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerBuyGoodsOnline",

            "Amount": 150,

            "PartyA": phone,
            "PartyB": "8583554",

            "PhoneNumber": phone,

            "CallBackURL": "https://kuccps-cluster-system-1.onrender.com/mpesa_callback",

            "AccountReference": "EARLYBIRDTECHSOLUTIONS",

            "TransactionDesc": "KUCCPS Cluster Calculator"
        }


        headers = {
            "Authorization": "Bearer " + access_token
        }


        response = requests.post(stk_url, json=payload, headers=headers)

        print("MPESA RESPONSE:", response.text)
        print("PAYLOAD:", payload)

        res = response.json()

        checkout_id = res.get("CheckoutRequestID")

        if checkout_id:

            conn = sqlite3.connect("kuccps.db")
            cur = conn.cursor()

            cur.execute("""
            INSERT INTO payments (phone,email,checkout_id,status)
            VALUES (?,?,?,?)
            """,(phone,email,checkout_id,"pending"))

            conn.commit()
            conn.close()

            return jsonify({
                "status":"success",
                "checkout_id": checkout_id
            })

        if res.get("ResponseCode") == "0":
            return jsonify({
                "status": "success",
                "message": "STK Push sent. Check your phone"
            })
        else:
            return jsonify({
                "status": "error",
                "message": res
            })

    except Exception as e:

        print("MPESA ERROR:", e)

        return jsonify({
            "status": "error",
            "message": "Payment request failed"
        })

@app.route("/mpesa_callback", methods=["POST"])
def mpesa_callback():

    data = request.json
    print("MPESA CALLBACK RECEIVED:", data)

    body = data["Body"]["stkCallback"]

    checkout_id = body["CheckoutRequestID"]
    result_code = body["ResultCode"]

    conn = sqlite3.connect("kuccps.db")
    cur = conn.cursor()

    if result_code == 0:

        cur.execute("""
        UPDATE payments
        SET status='success'
        WHERE checkout_id=?
        """,(checkout_id,))

    else:

        cur.execute("""
        UPDATE payments
        SET status='failed'
        WHERE checkout_id=?
        """,(checkout_id,))

    conn.commit()
    conn.close()

    return jsonify({"ResultCode":0,"ResultDesc":"Accepted"})

@app.route("/check_payment/<checkout_id>")
def check_payment(checkout_id):

    conn = sqlite3.connect("kuccps.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT status,email FROM payments
        WHERE checkout_id=?
    """,(checkout_id,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"status":"pending"})

    status,email = row

    # PAYMENT SUCCESS
    if status == "success":

        # load the user's saved results
        conn = sqlite3.connect("kuccps.db")
        cur = conn.cursor()

        cur.execute("""
            SELECT full_results,access_code
            FROM calculated_users
            WHERE email=?
        """,(email,))

        user = cur.fetchone()
        conn.close()

        if user:

            results = json.loads(user[0])

            session["results"] = results
            session["access_code"] = user[1]

            return jsonify({
                "status":"success",
                "redirect":"/results"
            })

    return jsonify({"status":status})

@app.route("/fetch_access", methods=["POST"])
def fetch_access():

    data = request.get_json()

    if not data:
        return jsonify({"access_code": None})

    email = data.get("email")

    conn = sqlite3.connect("kuccps.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT access_code FROM calculated_users WHERE email=?",
        (email,)
    )

    result = cursor.fetchone()
    conn.close()

    if result:
        return jsonify({"access_code": result[0]})
    else:
        return jsonify({"access_code": None})

# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))  # Use Render's assigned port if available
    app.run(host="0.0.0.0", port=port, debug=True)