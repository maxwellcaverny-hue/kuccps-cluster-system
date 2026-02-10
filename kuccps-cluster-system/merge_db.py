import sqlite3

OLD_DB = "kuccps.db"
NEW_DB = "database.db"

old = sqlite3.connect(OLD_DB)
new = sqlite3.connect(NEW_DB)

old.row_factory = sqlite3.Row
new.row_factory = sqlite3.Row

oc = old.cursor()
nc = new.cursor()

print("🔄 Merging databases...")

# ---- COURSES ----
oc.execute("SELECT * FROM courses")
for row in oc.fetchall():
    nc.execute("""
        INSERT OR IGNORE INTO courses (id, name, cluster)
        VALUES (?, ?, ?)
    """, (row["id"], row["name"], row["cluster"]))

# ---- REQUIREMENTS ----
oc.execute("SELECT * FROM requirements")
for row in oc.fetchall():
    nc.execute("""
        INSERT OR IGNORE INTO requirements (id, course_id, subject, grade)
        VALUES (?, ?, ?, ?)
    """, (row["id"], row["course_id"], row["subject"], row["grade"]))

# ---- UNIVERSITIES ----
oc.execute("SELECT * FROM universities")
for row in oc.fetchall():
    nc.execute("""
        INSERT OR IGNORE INTO universities (id, course_id, name, cutoff)
        VALUES (?, ?, ?, ?)
    """, (row["id"], row["course_id"], row["name"], row["cutoff"]))

# ---- ADMINS ----
oc.execute("SELECT * FROM admins")
for row in oc.fetchall():
    nc.execute("""
        INSERT OR IGNORE INTO admins (id, username, password)
        VALUES (?, ?, ?)
    """, (row["id"], row["username"], row["password"]))

new.commit()
old.close()
new.close()

print("✅ Merge complete. All data is now in database.db")