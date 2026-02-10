import sqlite3

DB_NAME = "kuccps.db"

def connect():
    return sqlite3.connect(DB_NAME)

def get_courses():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM courses")
    data = cursor.fetchall()
    conn.close()
    return data
