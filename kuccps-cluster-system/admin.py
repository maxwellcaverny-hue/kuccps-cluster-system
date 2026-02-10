from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "admin-secret-key"


# ---------- ADMIN LOGIN ----------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "1234":
            session["admin"] = True
            return redirect("/dashboard")

        return render_template("admin/login.html", error="Invalid login")

    return render_template("admin/login.html")


# ---------- ADMIN DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect("kuccps.db")
    c = conn.cursor()
    c.execute("SELECT * FROM courses")
    courses = c.fetchall()
    conn.close()

    return render_template("admin/dashboard.html", courses=courses)


# ---------- ADD COURSE ----------
@app.route("/add-course", methods=["POST"])
def add_course():
    if not session.get("admin"):
        return redirect("/admin")

    name = request.form["name"]
    cluster = request.form["cluster"]
    cutoff = request.form["cutoff"]
    university = request.form["university"]

    conn = sqlite3.connect("kuccps.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO courses (name, cluster, cutoff, university) VALUES (?, ?, ?, ?)",
        (name, cluster, cutoff, university)
    )
    conn.commit()
    conn.close()

    return redirect("/dashboard")


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/admin")


if __name__ == "__main__":
    app.run(port=5001, debug=True)