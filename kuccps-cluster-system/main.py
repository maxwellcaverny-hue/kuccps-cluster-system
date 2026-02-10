from flask import Flask, render_template, request, redirect, session, url_for
from functools import wraps
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "kuccps.db")

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# DO NOT TOUCH THIS – your real formula
from clusters import compute_cluster, medicine_eligibility

app = Flask(__name__)
@app.route("/test-delete")
def test_delete():
    return "TEST ROUTE WORKS"

app.secret_key = "kuccps-admin-secret"

# =========================
# KCSE SUBJECTS
# =========================
SUBJECTS = {
    "ENG": "English",
    "KIS": "Kiswahili",
    "MAT": "Mathematics",
    "BIO": "Biology",
    "CHE": "Chemistry",
    "PHY": "Physics",
    "GSC": "General Science",
    "HAG": "History & Government",
    "GEO": "Geography",
    "CRE": "CRE",
    "IRE": "IRE",
    "HRE": "HRE",
    "CMP": "Computer Studies",
    "AGR": "Agriculture",
    "ARD": "Art & Design",
    "HSC": "Home Science",
    "BST": "Business Studies",
    "FRE": "French",
    "GER": "German",
    "MUS": "Music",
    "ARB": "Arabic"
}

# =========================
# SUBJECT NORMALIZATION
# =========================
SUBJECT_NORMALIZATION = {
    "ENGLISH": "ENG",
    "KISWAHILI": "KIS",
    "MATHEMATICS": "MAT",
    "MATH": "MAT",

    "BIOLOGY": "BIO",
    "CHEMISTRY": "CHE",
    "PHYSICS": "PHY",
    "GENERAL SCIENCE": "GSC",

    "HISTORY": "HAG",
    "HISTORY & GOVERNMENT": "HAG",
    "GEOGRAPHY": "GEO",

    "CRE": "CRE",
    "IRE": "IRE",
    "HRE": "HRE",

    "COMPUTER STUDIES": "CMP",
    "AGRICULTURE": "AGR",
    "ART & DESIGN": "ARD",
    "HOME SCIENCE": "HSC",

    "BUSINESS STUDIES": "BST",
    "FRENCH": "FRE",
    "GERMAN": "GER",
    "MUSIC": "MUS",
    "ARABIC": "ARB"
}

# =========================
# DB HELPERS
# =========================
def db():
    return sqlite3.connect(DB)

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

from werkzeug.security import generate_password_hash

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
# ADMIN AUTH
# =========================
def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/admin")
        return f(*args, **kwargs)
    return wrapped

# =========================
# STUDENT HOME
# =========================
@app.route("/")
def home():
    return render_template("student/calculator.html")

# =========================
# CALCULATE (STRICT & CLEAN)
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

    # store grades
    session["grades"] = grades

    # compute cluster points
    results = {}
    for c in range(1, 21):
        results[c] = compute_cluster(c, grades)

    # fetch courses
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name, cluster FROM courses")
    rows = cur.fetchall()
    conn.close()

    cluster_courses = {c: [] for c in range(1, 21)}
    for name, cluster in rows:
        cluster_courses[cluster].append({"name": name})

    # store for results page
    session["results"] = results
    session["cluster_courses"] = cluster_courses

    # GO TO RESULTS PAGE
    return redirect("/results")

    # ✅ SAVE GRADES FOR LATER CHECK
    session["grades"] = grades

    # ---- compute cluster points (DO NOT TOUCH) ----
    results = {}
    for c in range(1, 21):
        results[c] = compute_cluster(c, grades)

    # ---- fetch courses added by admin ----
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name, cluster FROM courses")
    rows = cur.fetchall()
    conn.close()

    cluster_courses = {c: [] for c in range(1, 21)}
    for name, cluster in rows:
        cluster_courses[cluster].append({"name": name})

        session["results"] = results
    session["cluster_courses"] = cluster_courses

    return redirect("/results")
    
def check_subject_requirements(student_grades, requirements):
    grade_order = {
        "A": 12, "A-": 11,
        "B+": 10, "B": 9, "B-": 8,
        "C+": 7, "C": 6, "C-": 5,
        "D+": 4, "D": 3, "D-": 2,
        "E": 1
    }

    # normalize student grades
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
                else:
                    matched_subject = subject
                    matched_grade = student_grade

        if not met:
            failed.append({
                "subject": requirement,
                "required": required_grade,
                "student_subject": matched_subject,
                "student_grade": matched_grade
            })

    return {
        "passed": len(failed) == 0,
        "failed": failed
    }

@app.route("/admin/edit/<int:course_id>", methods=["GET", "POST"])
@admin_required
def edit_course(course_id):
    conn = db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        cluster = request.form["cluster"]

        c.execute(
            "UPDATE courses SET name = ?, cluster = ? WHERE id = ?",
            (name, cluster, course_id)
        )

        conn.commit()
        conn.close()
        return redirect("/admin/dashboard")

    c.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
    course = c.fetchone()
    conn.close()

    return render_template("admin/edit_course.html", course=course)

@app.route("/check-course")
def check_course():
    cluster = int(request.args.get("cluster"))
    points = float(request.args.get("points"))
    course_name = request.args.get("course_name")

    conn = db()
    cur = conn.cursor()

    # get course
    cur.execute(
        "SELECT id FROM courses WHERE name=? AND cluster=?",
        (course_name, cluster)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return "Course not found for this cluster"

    course_id = row[0]

    # get subject requirements
    cur.execute(
        "SELECT subject, grade FROM requirements WHERE course_id=?",
        (course_id,)
    )
    requirements = dict(cur.fetchall())

    # get universities
    cur.execute(
        "SELECT name, cutoff FROM universities WHERE course_id=?",
        (course_id,)
    )
    universities = cur.fetchall()

    conn.close()

    # subject requirement check
    subject_check = check_subject_requirements(
        session.get("grades", {}),
        requirements
    )

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
# ADMIN LOGIN
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM admins WHERE username = ?", (username,))
        admin = c.fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = True
            return redirect("/admin/dashboard")

        return render_template("admin/login.html", error="Invalid login")

    return render_template("admin/login.html")

# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT id, name, cluster FROM courses")
    rows = cur.fetchall()

    courses = {c: [] for c in range(1, 21)}

    for cid, name, cluster in rows:
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

    conn.close()

    return render_template(
        "admin/dashboard.html",
        courses=courses,
        subjects=SUBJECTS
    )
from werkzeug.security import generate_password_hash

@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    if request.method == "POST":
        new_username = request.form["username"]
        new_password = request.form["password"]

        hashed_password = generate_password_hash(new_password)

        conn = db()
        c = conn.cursor()

        # Since you have only ONE admin, update the first one
        c.execute("""
            UPDATE admins
            SET username = ?, password = ?
            WHERE id = 1
        """, (new_username, hashed_password))

        conn.commit()
        conn.close()

        return redirect("/admin/dashboard")

    return render_template("admin/settings.html")

# =========================
# ADD COURSE
# =========================

# ---- POST: handle adding course ----
@app.route("/admin/add-course", methods=["POST"])
@admin_required
def add_course():
    conn = db()
    cur = conn.cursor()

    # ---- CLUSTER SAFETY ----
    cluster = int(request.form["cluster"])
    if cluster < 1 or cluster > 20:
        conn.close()
        return "❌ Cluster must be between 1 and 20"

    name = request.form["name"].strip()

    # ---- INSERT COURSE ----
    cur.execute(
        "INSERT INTO courses (name, cluster) VALUES (?, ?)",
        (name, cluster)
    )
    course_id = cur.lastrowid

    # ---- SUBJECT REQUIREMENTS ----
    ALLOWED_GRADES = ["A","A-","B+","B","B-","C+","C","C-","D+","D","D-","E"]
    requirements_input = request.form.get("requirements", "")

    for line in requirements_input.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue

        subject_part, grade_part = line.split(":", 1)
        subject = subject_part.strip()
        grade = grade_part.strip().upper()

        if not subject or not grade:
            continue
        if grade not in ALLOWED_GRADES:
            continue

        cur.execute(
            "INSERT INTO requirements (course_id, subject, grade) VALUES (?, ?, ?)",
            (course_id, subject, grade)
        )

    # ---- UNIVERSITIES & CUTOFFS ----
    universities = request.form.get("universities", "").splitlines()
    cutoffs = request.form.get("cutoffs", "").splitlines()

    for uni, cutoff in zip(universities, cutoffs):
        uni_name = uni.strip()
        try:
            cutoff_value = float(cutoff.strip())
        except ValueError:
            continue
        if uni_name:
            cur.execute(
                "INSERT INTO universities (course_id, name, cutoff) VALUES (?, ?, ?)",
                (course_id, uni_name, cutoff_value)
            )

    # Commit and close
    conn.commit()
    conn.close()

    return redirect("/admin/dashboard")


# ---- GET: show add course page ----
@app.route("/admin/add-course", methods=["GET"])
@admin_required
def add_course_page():
    return render_template("admin/add_course.html")


# ---- GET: show all courses ----
@app.route("/admin/courses")
@admin_required
def view_courses():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.id, c.name, c.cluster, u.name, u.cutoff
        FROM courses c
        LEFT JOIN universities u ON c.id = u.course_id
        ORDER BY c.cluster
    """)

    rows = cur.fetchall()
    conn.close()

    courses = {}
    for cid, cname, cluster, uni, cutoff in rows:
        courses.setdefault(cluster, []).append({
            "id": cid,
            "name": cname,
            "university": uni,
            "cutoff": cutoff
        })

    return render_template("admin/courses.html", courses=courses)

@app.route("/admin/course/delete/<int:course_id>", methods=["POST"])
@admin_required
def delete_course(course_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM universities WHERE course_id=?", (course_id,))
    cur.execute("DELETE FROM requirements WHERE course_id=?", (course_id,))
    cur.execute("DELETE FROM courses WHERE id=?", (course_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/admin")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
