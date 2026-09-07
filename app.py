from flask import Flask, render_template, request, session, redirect, url_for
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

app = Flask(__name__)

# Session security
app.secret_key = "smart-attendance-student-key"


# ================= SUPABASE =================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL ya SUPABASE_KEY .env me missing hai!"
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ================= HOME =================

@app.route("/")
def home():

    return render_template("index.html")


# ================= REGISTER =================

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

        try:

            supabase.table("students").insert({
                "name": name,
                "father_name": father_name,
                "class_name": class_name,
                "roll_number": roll_number,
                "email": email,
                "contact": contact,
                "password": password
            }).execute()

            return redirect(url_for("login"))

        except Exception as e:

            print("REGISTER ERROR:", e)

            return "Registration failed. Email already registered ho sakta hai."

    return render_template("register.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        try:

            result = (
                supabase
                .table("students")
                .select("*")
                .eq("email", email)
                .eq("password", password)
                .execute()
            )

            students = result.data

            if students:

                student = students[0]

                session["student_id"] = student["id"]
                session["student_name"] = student["name"]

                return redirect(url_for("dashboard"))

            return "Email ya password galat hai!"

        except Exception as e:

            print("LOGIN ERROR:", e)

            return "Database connection error."


    return render_template("login.html")


# ================= STUDENT DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    if "student_id" not in session:

        return redirect(url_for("login"))

    try:

        result = (
            supabase
            .table("students")
            .select("*")
            .eq("id", session["student_id"])
            .execute()
        )

        students = result.data

        if not students:

            session.clear()

            return redirect(url_for("login"))

        student = students[0]

        return render_template(
            "dashboard.html",
            student=student
        )

    except Exception as e:

        print("DASHBOARD ERROR:", e)

        return "Database connection error."


# ================= MARK ATTENDANCE =================


@app.route("/attendance/<token>")
def scan_attendance(token):

    if not session.get("student_id"):
        return redirect(url_for("login"))

    try:
        # Check whether this QR session is valid
        result = (
            supabase
            .table("attendance_sessions")
            .select("id,date,active")
            .eq("token", token)
            .eq("active", True)
            .execute()
        )

        if not result.data:
            return "This attendance QR code is invalid or expired."

        qr_session = result.data[0]

        today = datetime.now().strftime("%Y-%m-%d")

        if qr_session["date"] != today:
            return "This attendance QR code has expired."

        student_id = session.get("student_id")

        # Check if attendance is already marked today
        existing = (
            supabase
            .table("attendance")
            .select("id")
            .eq("student_id", student_id)
            .eq("date", today)
            .execute()
        )

        if existing.data:
            return "Attendance has already been marked for today."

        # Mark attendance
        supabase.table("attendance").insert({
            "student_id": student_id,
            "date": today,
            "time": datetime.now().strftime("%H:%M:%S"),
            "status": "Present"
        }).execute()

        return "Attendance marked successfully."

    except Exception as error:
        print("ATTENDANCE ERROR:", repr(error))
        return "Unable to mark attendance. Please try again."

    
@app.route("/mark-attendance", methods=["POST"])
def mark_attendance():

    if "student_id" not in session:

        return redirect(url_for("login"))

    student_id = session["student_id"]

    now = datetime.now()

    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    try:

        existing = (
            supabase
            .table("attendance")
            .select("*")
            .eq("student_id", student_id)
            .eq("date", date)
            .execute()
        )

        if existing.data:

            return "Aaj ki attendance already marked hai!"

        supabase.table("attendance").insert({
            "student_id": student_id,
            "date": date,
            "time": time,
            "status": "Present"
        }).execute()

        return "Attendance successfully marked!"

    except Exception as error:
    print("ATTENDANCE ERROR:", repr(error))
    return f"Attendance error: {error}"


# ================= MONTHLY RECORD =================

@app.route("/monthly-record")
def monthly_record():

    if "student_id" not in session:

        return redirect(url_for("login"))

    month = request.args.get("month")

    if not month:

        month = datetime.now().strftime("%Y-%m")

    student_id = session["student_id"]

    try:

        student_result = (
            supabase
            .table("students")
            .select(
                "id,name,father_name,class_name,roll_number"
            )
            .eq("id", student_id)
            .execute()
        )

        students = student_result.data

        if not students:

            return "Student not found."

        student = students[0]


        attendance_result = (
            supabase
            .table("attendance")
            .select("*")
            .eq("student_id", student_id)
            .execute()
        )

        attendance_records = attendance_result.data


        present = 0
        absent = 0


        for record in attendance_records:

            record_date = str(record["date"])

            if record_date.startswith(month):

                if record["status"] == "Present":

                    present += 1

                elif record["status"] == "Absent":

                    absent += 1


        total = present + absent

        percentage = 0

        if total > 0:

            percentage = round(
                (present / total) * 100,
                2
            )


        records = [{
            "id": student["id"],
            "name": student["name"],
            "father_name": student["father_name"],
            "class_name": student["class_name"],
            "roll_number": student["roll_number"],
            "present": present,
            "absent": absent,
            "total": total,
            "percentage": percentage
        }]


        return render_template(
            "monthly_record.html",
            records=records,
            month=month
        )

    except Exception as e:

        print("MONTHLY RECORD ERROR:", e)

        return "Monthly record load nahi ho saka."


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ================= RUN APP =================

if __name__ == "__main__":

    app.run(debug=True)
