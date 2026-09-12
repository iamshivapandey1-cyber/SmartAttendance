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

# ================= STUDENT PROFILE =================

@app.route("/profile")
def profile():

    if "student_id" not in session:
        return redirect(url_for("login"))

    student_id = session["student_id"]

    try:

        result = (
            supabase
            .table("students")
            .select(
                "id,name,father_name,class_name,"
                "roll_number,email,contact,profile_picture"
            )
            .eq("id", student_id)
            .execute()
        )

        students = result.data

        if not students:
            session.clear()
            return redirect(url_for("login"))

        student = students[0]

        return render_template(
            "profile.html",
            student=student
        )

    except Exception as error:

        print("PROFILE ERROR:", repr(error))

        return "Unable to load your profile."


# ================= CHANGE PASSWORD =================

@app.route("/change-password", methods=["GET", "POST"])
def change_password():

    if "student_id" not in session:
        return redirect(url_for("login"))

    student_id = session["student_id"]

    if request.method == "POST":

        current_password = request.form.get(
            "current_password", ""
        )

        new_password = request.form.get(
            "new_password", ""
        )

        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not current_password or not new_password or not confirm_password:
            return render_template(
                "change_password.html",
                error="All fields are required."
            )

        if new_password != confirm_password:
            return render_template(
                "change_password.html",
                error="New passwords do not match."
            )

        if len(new_password) < 6:
            return render_template(
                "change_password.html",
                error="Password must be at least 6 characters long."
            )

        try:

            # Get current student
            result = (
                supabase
                .table("students")
                .select("id,password")
                .eq("id", student_id)
                .execute()
            )

            students = result.data

            if not students:
                session.clear()
                return redirect(url_for("login"))

            student = students[0]

            # Verify current password
            if student["password"] != current_password:
                return render_template(
                    "change_password.html",
                    error="Current password is incorrect."
                )

            # Update password
            supabase.table("students").update({
                "password": new_password
            }).eq(
                "id", student_id
            ).execute()

            return render_template(
                "change_password.html",
                success="Password changed successfully."
            )

        except Exception as error:

            print("CHANGE PASSWORD ERROR:", repr(error))

            return render_template(
                "change_password.html",
                error="Unable to change password. Please try again."
            )

    return render_template("change_password.html")


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

# ================= QR ATTENDANCE =================

@app.route("/attendance/<token>")
def scan_attendance(token):

    if not session.get("student_id"):
        return redirect(url_for("login"))

    try:

        # Find the QR session
        result = (
            supabase
            .table("attendance_sessions")
            .select("id,date,active,created_at")
            .eq("token", token)
            .eq("active", True)
            .execute()
        )

        if not result.data:
            return "This attendance QR code is invalid or expired."

        qr_session = result.data[0]

        # Today's date
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # QR must be generated today
        if qr_session["date"] != today:
            return "This attendance QR code has expired."

        # Check QR age (5 minutes)
        created_at = qr_session["created_at"]

        # Convert Supabase timestamp to datetime
        created_at = datetime.fromisoformat(
            created_at.replace("Z", "+00:00")
        )

        # Make current time timezone-aware
        current_time = datetime.now(created_at.tzinfo)

        # QR age in seconds
        qr_age = (current_time - created_at).total_seconds()

        if qr_age > 300:
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


# ================= MANUAL ATTENDANCE DISABLED =================

@app.route("/mark-attendance", methods=["POST"])
def mark_attendance():

    return "Attendance can only be marked by scanning a valid QR code."

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
