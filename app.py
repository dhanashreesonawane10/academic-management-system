# DATABASE
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
app.secret_key = "abc123"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # users table
    cur.execute(
        """
    create table if not exists users (
        id integer primary key autoincrement,
        name text not null,
        email text unique not null,
        password text not null,
        role text not null
    )
    """
    )

    # courses table
    cur.execute(
        """
    create table if not exists courses(
    course_id integer primary key autoincrement,
    course_name text
    )"""
    )
    # assignments table
    cur.execute( """
    create table if not exists assignments (
        id integer primary key autoincrement,
        title text not null,
        description text,
        due_date text, 
        file text,
        course_id integer,
        foreign key (course_id) references courses(course_id)
    )
    """
    )
    # submissions table
    cur.execute(
        """
    create table if not exists submissions (
        id integer primary key autoincrement,
        assignment_id integer,
        student_id integer,
        file text, 
        submitted_on text,
        foreign key (assignment_id) references assignments(id),
        foreign key (student_id) references users(id)
    )
    """
    )
    # notices table
    cur.execute(
        """
    create table if not exists notices (
        id integer primary key autoincrement,
        title text not null,
        message text,
        faculty_id integer,
        created_on text,
        foreign key (faculty_id) references users(id)
    )
    """
    )

    #planner table
    cur.execute( """
    create table if not exists planner (
        id integer primary key autoincrement,
        task text,
        task_date text
    )
    """)
     
    conn.commit()
    conn.close()

# all the commom routes
# Home / Login page
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!")
    return redirect(url_for("index"))


# register logic
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        conn = get_db_connection()

        try:
            conn.execute(
                "insert into users (name, email, password, role) values (?,?,?,?)",
                (name, email, password, role),
            )
            conn.commit()
        except Exception as e:
            return f"Error: {e}"
        conn.close()

        flash("Registration successful! Please Login.")
        return redirect(url_for("index"))

    return render_template("register.html")


# Login logic
@app.route("/login", methods=["POST"])
def login():

    conn = get_db_connection()
    user = conn.execute(
        "select * from users where email=? and password=? and role=?",
        (
            request.form["email"],
            request.form["password"],
            request.form["role"],
        ),
    ).fetchone()
    conn.close()

    if user:
        flash("Login successful!")
        #store user info in session
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["name"] = user["name"]

        if user["role"] == "student":
            return redirect(url_for("student_dashboard"))
        else:
            return redirect(url_for("faculty_dashboard"))
        
    return render_template("index.html", error="Invalid Login Credentials")

# Student routes
@app.route("/student/dashboard")
def student_dashboard():
    if "user_id" not in session or session["role"] != "student":
        return redirect(url_for("index"))
    return render_template("student/dashboard.html")


@app.route("/student/notices")
def student_notices():
    if "user_id" not in session or session["role"] != "student":
        return redirect(url_for("index"))

    conn = get_db_connection()
    notices = conn.execute("select * from notices").fetchall()
    conn.close()
    return render_template("student/notices.html", notices=notices)

@app.route("/student/assignments")
def student_assignments():
    if "user_id" not in session or session["role"] != "student":
        return redirect(url_for("index"))

    conn = get_db_connection()

    assignments = conn.execute("SELECT * FROM assignments").fetchall()
    submissions = conn.execute("SELECT assignment_id FROM submissions WHERE student_id = ?", (session["user_id"],)).fetchall()
    
    conn.close()

    submitted_ids = [s["assignment_id"] for s in submissions]

    today = datetime.today().date()
    updated_assignments = []

    for a in assignments:
        due = datetime.strptime(a["due_date"], "%Y-%m-%d").date()
        diff = (due - today).days

        # deadline status
        if diff < 0:
            deadline_status = "Expired"
        elif diff == 0:
            deadline_status = "Due Today"
        else:
            deadline_status = f"Due in {diff} days"

        # submission status
        if a["id"] in submitted_ids:
            submit_status = "Submitted"
        else:
            submit_status = "Not Submitted"

        updated_assignments.append({
            "id": a["id"],
            "title": a["title"],
            "description": a["description"],
            "due_date": a["due_date"],
            "file": a["file"],
            "deadline_status": deadline_status,
            "submit_status": submit_status
        })

    return render_template("student/assignments.html", assignments=updated_assignments)

@app.route("/student/submit", methods=["GET", "POST"])
def student_submit():
    if "user_id" not in session or session["role"] != "student":
        return redirect(url_for("index"))

    conn = get_db_connection()

    assignment_id = request.args.get("assignment_id")

    if request.method == "POST":
        assignment_id = request.form["assignment_id"]
        file = request.files["file"]
        student_id = session["user_id"]

        # check if the assignment is already submitted or not
        existing = conn.execute( "SELECT * FROM submissions WHERE assignment_id=? AND student_id=?", (assignment_id, student_id)).fetchone()

        if existing:
            flash("You have already submitted this assignment!")
            return redirect(url_for("student_assignments"))

        if not file or file.filename == "":
            flash("File is required!")
            return redirect(url_for("student_assignments, assignment_id= assignment_id"))

        filename = file.filename
        file.save("static/uploads/" + file.filename)

        conn.execute(
            "insert into submissions (assignment_id, student_id, file, submitted_on) values (?, ?,?,date('now'))",
            (assignment_id, student_id, filename)
        )
        conn.commit()
        conn.close()

        flash("Assignment submitted succesfully!")
        return redirect(url_for("student_assignments"))
    
    assignments = conn.execute("select * from assignments").fetchall()
    conn.close()

    return render_template("student/submit.html", assignments=assignments, selected_id=assignment_id)


@app.route("/student/planner", methods=["get","post"])
def student_planner():
    if "user_id" not in session or session["role"] != "student":
        return redirect(url_for("index"))

    conn= get_db_connection()

    if request.method=="POST":
        print("Form Data: ", request.form)
        task= request.form.get("task")
        task_date= request.form.get("task_date")

        if not task or not task_date:
            flash("Please fill all fields!")
            return redirect(url_for("student_planner"))

        print("Task: ", task)
        print("Task Date: ", task_date)
        conn.execute(
            "insert into planner  (task, task_date) values (?,?)", (task, task_date)
        )
        conn.commit()

        flash("Task added successfully!")
        return redirect(url_for("student_planner")) 

    tasks= conn.execute("select * from planner order by task_date asc").fetchall()
    conn.close()
    return render_template("student/planner.html", tasks=tasks)

#planner delete route
@app.route("/delete_task/<int:task_id>")
def delete_task(task_id):
    if "user_id" not in session:
        return redirect(url_for("index"))

    conn = get_db_connection()
    conn.execute("DELETE FROM planner WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    flash("Task Deleted. ")
    return redirect(url_for("student_planner"))

# Faculty routes
@app.route("/faculty/dashboard")
def faculty_dashboard():
    if "user_id" not in session or session["role"] != "faculty":
        return redirect(url_for("index"))

    return render_template("faculty/dashboard.html")


@app.route("/faculty/notice", methods=["GET", "POST"])
def faculty_notice():
    if "user_id" not in session or session["role"] != "faculty":
        return redirect(url_for("index"))

    if request.method == "POST":
        print(request.form)
        conn = get_db_connection()
        conn.execute(
            "insert into notices (title, message,created_on) values (?,?,date('now'))",
            (request.form["title"], request.form["message"]),
        )
        conn.commit()

        # debug
        rows = conn.execute("select * from notices").fetchall()
        print("notices after insert: ", rows)
        conn.close()
        flash("Notice Posted Successfully!")
        return redirect(url_for("faculty_dashboard"))

    return render_template("faculty/notice.html")

@app.route("/faculty/assignment", methods=["GET", "POST"])
def faculty_assignment():
    if "user_id" not in session or session["role"] != "faculty":
        return redirect(url_for("index"))


    today= datetime.today().isoformat()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        due_date = request.form["due_date"]

        if due_date < today:
            flash("Please select a valid future date.")
            return redirect(url_for("faculty_assignment"))

        file = request.files["file"]

        filename = ""
        if file and file.filename != "":
            filename = file.filename
            upload_path = os.path.join("static", "uploads", filename)
            file.save(upload_path)

        conn = get_db_connection()
        conn.execute(
            "insert into assignments (title, description, due_date, file) values (?,?,?,?)",
            (title, description, due_date, filename),
        )
        conn.commit()
        conn.close()

        flash("Assignment created successfully!")
        return redirect(url_for("faculty_assignment"))
    
    return render_template("faculty/assignment.html", today=today)

@app.route("/faculty/submissions")
def faculty_submissions():
    if "user_id" not in session or session["role"] != "faculty":
        return redirect(url_for("index"))

    conn = get_db_connection()

    submissions = conn.execute("""
        SELECT 
            submissions.*, 
            assignments.title, 
            assignments.due_date,
            users.name
        FROM submissions
        JOIN assignments ON submissions.assignment_id = assignments.id
        JOIN users ON submissions.student_id = users.id
    """).fetchall()

    conn.close()

    updated = []

    for s in submissions:
        due = s["due_date"]
        submitted = s["submitted_on"]

        if submitted <= due:
            status = "On Time"
        else:
            status = "Late"

        updated.append({
            "student": s["name"],
            "title": s["title"],
            "submitted_on": s["submitted_on"],
            "due_date": s["due_date"],
            "file": s["file"], 
            "status": status
        })

    return render_template("faculty/submissions.html", submissions=updated)

# Run app
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
