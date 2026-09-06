from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
import secrets

app = Flask(__name__)

# Session ke liye secret key
app.secret_key = "smart-attendance-secret-key"


# Database connection
def get_db():
    conn = sqlite3.connect("attendance.db")
    conn.row_factory = sqlite3.Row
    return conn


# Database/table create karna
def create_table():

    conn = get_db()
    cursor = conn.cursor()

    # Students table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            father_name TEXT NOT NULL,
            class_name TEXT NOT NULL,
            roll_number TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            contact TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(student_id, date),
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    conn.commit()
    conn.close()


# Home page
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        father_name = request.form["father_name"]
        class_name = request.form["class_name"]
        roll_number = request.form["roll_number"]
        email = request.form["email"]
        contact = request.form["contact"]
        password = request.form["password"]

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO students
                (name, father_name, class_name, roll_number, email, contact, password)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                father_name,
                class_name,
                roll_number,
                email,
                contact,
                password
            ))

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "Ye email already registered hai!"

        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        student = conn.execute("""
            SELECT * FROM students
            WHERE email = ? AND password = ?
        """, (email, password)).fetchone()

        conn.close()

        # Agar student mil gaya
        if student:

            # Student ki information session mein save
            session["student_id"] = student["id"]
            session["student_name"] = student["name"]

            # Dashboard par bhejo
            return redirect(url_for("dashboard"))

        # Agar email/password galat hai
        return "Email ya password galat hai!"

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    # Login nahi hai to login page par bhejo
    if "student_id" not in session:
        return redirect(url_for("login"))

    # Database se student ki complete information nikalna
    conn = get_db()

    student = conn.execute("""
        SELECT * FROM students
        WHERE id = ?
    """, (session["student_id"],)).fetchone()

    conn.close()

    return render_template(
        "dashboard.html",
        student=student
    )

# ---------------- MARK ATTENDANCE ----------------


@app.route("/mark-attendance", methods=["POST"])
def mark_attendance():
    if "student_id" not in session:
        return redirect(url_for("login"))

    from datetime import datetime

    student_id = session["student_id"]
    now = datetime.now()

    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    conn = get_db()

    try:
        conn.execute("""
            INSERT INTO attendance
            (student_id, date, time, status)
            VALUES (?, ?, ?, ?)
        """, (student_id, date, time, "Present"))

        conn.commit()
        message = "Attendance successfully marked!"

    except sqlite3.IntegrityError:
        message = "Aaj ki attendance already marked hai!"

    conn.close()

    return message

# ---------------- MONTHLY ATTENDANCE ----------------

@app.route("/monthly-record")
def monthly_record():

    if "student_id" not in session:
        return redirect(url_for("login"))

    from datetime import datetime

    month = request.args.get("month")

    if not month:
        month = datetime.now().strftime("%Y-%m")

    conn = get_db()

    students = conn.execute("""
        SELECT id, name, father_name, class_name, roll_number
        FROM students
        ORDER BY roll_number
    """).fetchall()

    records = []

    for student in students:

        present = conn.execute("""
            SELECT COUNT(*)
            FROM attendance
            WHERE student_id = ?
            AND status = 'Present'
            AND substr(date, 1, 7) = ?
        """, (student["id"], month)).fetchone()[0]

        absent = conn.execute("""
            SELECT COUNT(*)
            FROM attendance
            WHERE student_id = ?
            AND status = 'Absent'
            AND substr(date, 1, 7) = ?
        """, (student["id"], month)).fetchone()[0]

        total = present + absent

        percentage = 0

        if total > 0:
            percentage = round((present / total) * 100, 2)

        records.append({
            "id": student["id"],
            "name": student["name"],
            "father_name": student["father_name"],
            "class_name": student["class_name"],
            "roll_number": student["roll_number"],
            "present": present,
            "absent": absent,
            "total": total,
            "percentage": percentage
        })

    conn.close()

    return render_template(
        "monthly_record.html",
        records=records,
        month=month
    )
# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    # Session delete
    session.clear()

    # Login page par wapas
    return redirect(url_for("login"))


# ---------------- START APP ----------------

if __name__ == "__main__":
    create_table()
    app.run(debug=True)
