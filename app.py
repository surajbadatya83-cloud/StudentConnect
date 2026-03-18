from datetime import datetime
import os

from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campusvoice.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"

db = SQLAlchemy(app)

CATEGORY_TAGS = [
    "Bullying",
    "Infrastructure",
    "Washroom",
    "Electricity",
    "WiFi",
    "Lab Equipment",
    "Classroom Issue",
    "Other",
]

PRIORITY_LEVELS = ["Low", "Medium", "High"]
COMPLAINT_STATUSES = ["Submitted", "Under Review", "In Progress", "Resolved"]
STATUS_PROGRESS_MAP = {
    "Submitted": 10,
    "Under Review": 30,
    "In Progress": 70,
    "Resolved": 100,
}

DEPARTMENTS = [
    "Administration",
    "Computer Science",
    "Electrical",
    "Hostel",
    "Maintenance",
    "Security",
    "Student Affairs",
    "Other",
]

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    complaints = db.relationship(
        "Complaint", back_populates="student", cascade="all, delete-orphan"
    )


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(80), nullable=False)
    department = db.Column(db.String(120), nullable=False)
    image = db.Column(db.String(255))
    status = db.Column(db.String(30), nullable=False, default="Submitted")
    progress = db.Column(db.Integer, nullable=False, default=0)
    priority = db.Column(db.String(30), nullable=False, default="Medium")
    deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="complaints")
    updates = db.relationship(
        "ComplaintUpdate", back_populates="complaint", cascade="all, delete-orphan"
    )


class ComplaintUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(
        db.Integer, db.ForeignKey("complaint.id"), nullable=False
    )
    message = db.Column(db.Text, nullable=False)
    progress = db.Column(db.String(120), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    complaint = db.relationship("Complaint", back_populates="updates")


def initialize_database() -> None:
    with app.app_context():
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        db.create_all()
        ensure_student_schema()
        ensure_complaint_schema()


def ensure_student_schema() -> None:
    columns = db.session.execute(text("PRAGMA table_info(student)")).fetchall()
    column_names = {column[1] for column in columns}

    if "role" not in column_names:
        db.session.execute(
            text("ALTER TABLE student ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'student'")
        )
        db.session.commit()


def ensure_complaint_schema() -> None:
    columns = db.session.execute(text("PRAGMA table_info(complaint)")).fetchall()
    column_names = {column[1] for column in columns}

    if "progress" not in column_names:
        db.session.execute(
            text("ALTER TABLE complaint ADD COLUMN progress INTEGER NOT NULL DEFAULT 0")
        )
        db.session.commit()

    if "deadline" not in column_names:
        db.session.execute(text("ALTER TABLE complaint ADD COLUMN deadline DATETIME"))
        db.session.commit()


@app.before_request
def load_logged_in_student() -> None:
    student_id = session.get("student_id")
    g.student = db.session.get(Student, student_id) if student_id else None


@app.context_processor
def inject_current_student() -> dict:
    return {"current_student": getattr(g, "student", None)}


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.student is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.student is None or session.get("role") != "admin":
            flash("Please log in as an administrator to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename: str):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    complaints = (
        Complaint.query.filter_by(student_id=g.student.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return render_template("dashboard.html", complaints=complaints)


@app.route("/my-complaints")
@login_required
def my_complaints():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    complaints = (
        Complaint.query.filter_by(student_id=g.student.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return render_template(
        "my_complaints.html",
        complaints=complaints,
        complaint_statuses=COMPLAINT_STATUSES,
        status_progress_map=STATUS_PROGRESS_MAP,
    )


@app.route("/submit-complaint", methods=["GET", "POST"])
@login_required
def submit_complaint():
    if session.get("role") == "admin":
        flash("Administrators cannot submit student complaints.", "warning")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        tag = request.form.get("tag", "").strip()
        department = request.form.get("department", "").strip()
        priority = request.form.get("priority", "").strip()
        image_file = request.files.get("image")

        if not all([title, description, tag, department, priority]):
            flash("Please complete all required fields.", "danger")
            return render_template(
                "submit_complaint.html",
                category_tags=CATEGORY_TAGS,
                departments=DEPARTMENTS,
                priority_levels=PRIORITY_LEVELS,
            )

        if tag not in CATEGORY_TAGS:
            flash("Please choose a valid category tag.", "danger")
            return render_template(
                "submit_complaint.html",
                category_tags=CATEGORY_TAGS,
                departments=DEPARTMENTS,
                priority_levels=PRIORITY_LEVELS,
            )

        if department not in DEPARTMENTS:
            flash("Please choose a valid department.", "danger")
            return render_template(
                "submit_complaint.html",
                category_tags=CATEGORY_TAGS,
                departments=DEPARTMENTS,
                priority_levels=PRIORITY_LEVELS,
            )

        if priority not in PRIORITY_LEVELS:
            flash("Please choose a valid priority level.", "danger")
            return render_template(
                "submit_complaint.html",
                category_tags=CATEGORY_TAGS,
                departments=DEPARTMENTS,
                priority_levels=PRIORITY_LEVELS,
            )

        image_filename = None
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename):
                flash("Image must be a JPG, JPEG, or PNG file.", "danger")
                return render_template(
                    "submit_complaint.html",
                    category_tags=CATEGORY_TAGS,
                    departments=DEPARTMENTS,
                    priority_levels=PRIORITY_LEVELS,
                )

            filename = secure_filename(image_file.filename)
            image_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

        complaint = Complaint(
            student_id=g.student.id,
            title=title,
            description=description,
            tag=tag,
            department=department,
            image=image_filename,
            status="Submitted",
            progress=0,
            priority=priority,
            created_at=datetime.utcnow(),
        )
        db.session.add(complaint)
        db.session.commit()

        flash("Complaint submitted successfully.", "success")
        return redirect(url_for("my_complaints"))

    return render_template(
        "submit_complaint.html",
        category_tags=CATEGORY_TAGS,
        departments=DEPARTMENTS,
        priority_levels=PRIORITY_LEVELS,
    )


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    stats = {
        "total": len(complaints),
        "pending": sum(1 for complaint in complaints if complaint.status == "Submitted"),
        "in_progress": sum(
            1 for complaint in complaints if complaint.status == "In Progress"
        ),
        "resolved": sum(1 for complaint in complaints if complaint.status == "Resolved"),
    }
    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        complaint_statuses=COMPLAINT_STATUSES,
        stats=stats,
    )


@app.route("/admin/complaints")
@admin_required
def admin_complaints():
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    return render_template("admin_complaints.html", complaints=complaints)


@app.route("/admin/complaint/<int:complaint_id>")
@admin_required
def admin_complaint_detail(complaint_id: int):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        return redirect(url_for("admin_complaints"))

    updates = (
        ComplaintUpdate.query.filter_by(complaint_id=complaint.id)
        .order_by(ComplaintUpdate.date.desc())
        .all()
    )
    return render_template(
        "admin_complaint_detail.html",
        complaint=complaint,
        updates=updates,
        complaint_statuses=COMPLAINT_STATUSES,
        status_progress_map=STATUS_PROGRESS_MAP,
    )


@app.route("/admin/complaint/<int:complaint_id>/update", methods=["POST"])
@admin_required
def update_complaint(complaint_id: int):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        return redirect(url_for("admin_complaints"))

    status = request.form.get("status", "").strip()
    progress_raw = request.form.get("progress", "").strip()
    deadline_raw = request.form.get("deadline", "").strip()
    message = request.form.get("message", "").strip()

    if status not in COMPLAINT_STATUSES:
        flash("Please choose a valid complaint status.", "danger")
        return redirect(url_for("admin_complaint_detail", complaint_id=complaint.id))

    if progress_raw:
        try:
            progress = int(progress_raw)
        except ValueError:
            flash("Progress must be a number between 0 and 100.", "danger")
            return redirect(url_for("admin_complaint_detail", complaint_id=complaint.id))
    else:
        progress = STATUS_PROGRESS_MAP[status]

    if progress < 0 or progress > 100:
        flash("Progress must be between 0 and 100.", "danger")
        return redirect(url_for("admin_complaint_detail", complaint_id=complaint.id))

    deadline = None
    if deadline_raw:
        try:
            deadline = datetime.strptime(deadline_raw, "%Y-%m-%d")
        except ValueError:
            flash("Deadline must use a valid date.", "danger")
            return redirect(url_for("admin_complaint_detail", complaint_id=complaint.id))

    complaint.status = status
    complaint.progress = progress
    complaint.deadline = deadline

    if message:
        db.session.add(
            ComplaintUpdate(
                complaint_id=complaint.id,
                message=message,
                progress=status,
                date=datetime.utcnow(),
            )
        )

    db.session.commit()
    flash("Complaint updated successfully.", "success")
    return redirect(url_for("admin_complaint_detail", complaint_id=complaint.id))


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.student is not None:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        department = request.form.get("department", "").strip()

        if not all([name, email, password, department]):
            flash("All fields are required.", "danger")
            return render_template("register.html")

        existing_student = Student.query.filter_by(email=email).first()
        if existing_student is not None:
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        student = Student(
            name=name,
            email=email,
            password=generate_password_hash(password),
            department=department,
        )
        db.session.add(student)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.student is not None:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        student = Student.query.filter_by(email=email).first()
        if student is None or not check_password_hash(student.password, password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        session.clear()
        session["student_id"] = student.id
        session["student_name"] = student.name
        session["role"] = student.role
        flash("You are now logged in.", "success")
        if student.role == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


initialize_database()


if __name__ == "__main__":
    print("Flask starting...")
    app.run(debug=True)
