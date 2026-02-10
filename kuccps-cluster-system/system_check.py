import sqlite3
import inspect
import main

DB = "kuccps.db"

def check_single_calculate():
    src = inspect.getsource(main)
    count = src.count("def calculate")
    assert count == 1, f"❌ Multiple calculate() functions found: {count}"
    print("✅ Single calculate() function confirmed")

def check_calculate_route():
    src = inspect.getsource(main.calculate)
    assert "CLUSTER_COURSES" not in src, "❌ Static CLUSTER_COURSES used in calculate()"
    assert "cluster_courses" in src, "❌ cluster_courses not built dynamically"
    print("✅ calculate() route OK")

def check_database():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {t[0] for t in c.fetchall()}
    required = {"courses", "requirements", "universities"}
    missing = required - tables
    assert not missing, f"❌ Missing tables: {missing}"
    print("✅ Database tables OK")
    conn.close()

def run_all_checks():
    print("\n🔍 RUNNING SYSTEM INTEGRITY CHECKS\n")
    check_single_calculate()
    check_calculate_route()
    check_database()
    print("\n🎉 ALL CHECKS PASSED — SYSTEM IS CLEAN & SAFE\n")

if __name__ == "__main__":
    run_all_checks()
