from datetime import datetime, timezone
import os
import re

from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campusvoice.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["DEFAULT_ADMIN_EMAIL"] = os.environ.get(
    "DEFAULT_ADMIN_EMAIL", "surajbadatya83@gmail.com"
).strip().lower()

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
    "Computer Science and Engineering (CSE)",
    "Information Technology (IT)",
    "Electronics and Communication Engineering (ECE)",
    "Electrical Engineering (EE)",
    "Mechanical Engineering (ME)",
    "Civil Engineering (CE)",
    "Chemical Engineering",
    "Aerospace Engineering",
    "Biotechnology Engineering",
    "Metallurgical Engineering",
    "Industrial Engineering",
    "Production Engineering",
    "Automobile Engineering",
    "Mechatronics Engineering",
    "Artificial Intelligence & Data Science",
    "Artificial Intelligence & Machine Learning",
    "Robotics Engineering",
    "Environmental Engineering",
    "Other",
]

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
TITLE_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "in",
    "is",
    "not",
    "of",
    "on",
    "the",
    "to",
    "with",
}

DEFAULT_FEED_SORT = "most_voted"
FEED_SORT_OPTIONS = {
    "most_voted": "Most voted",
    "recent": "Most recent",
}
FEED_PAGE_SIZE = 9
FEED_STATUS_OPTIONS = {
    "all": "All statuses",
    "pending": "Pending",
    "in_progress": "In Progress",
    "resolved": "Resolved",
}
ADMIN_VISIBILITY_OPTIONS = {
    "active": "Active complaints",
    "deleted": "Deleted complaints",
    "all": "All complaints",
}
DELETION_REASON_OPTIONS = [
    "Spam",
    "Offensive content",
    "Duplicate complaint",
    "Irrelevant",
    "Other",
]
TRENDING_COMPLAINT_MIN_VOTES = 3
TRENDING_COMPLAINT_LIMIT = 3
HARD_DELETE_MAX_VOTES = 4
EDIT_HISTORY_NOTICE_THRESHOLD = 20
COMMENTS_PAGE_SIZE = 10
MAX_COMMENT_LENGTH = 2000


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
    votes = db.relationship("Vote", back_populates="student", cascade="all, delete-orphan")


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
    votes = db.Column(db.Integer, nullable=False, default=1)
    is_merged = db.Column(db.Boolean, nullable=False, default=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_by = db.Column(db.Integer)
    deleted_reason = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime)
    parent_id = db.Column(db.Integer, db.ForeignKey("complaint.id"))
    deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="complaints")
    updates = db.relationship(
        "ComplaintUpdate", back_populates="complaint", cascade="all, delete-orphan"
    )
    parent = db.relationship("Complaint", remote_side=[id], backref="merged_children")
    vote_records = db.relationship(
        "Vote", back_populates="complaint", cascade="all, delete-orphan"
    )
    edit_history = db.relationship(
        "ComplaintEditHistory", back_populates="complaint", cascade="all, delete-orphan"
    )
    comments = db.relationship(
        "Comment", back_populates="complaint", cascade="all, delete-orphan"
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


class ComplaintEditHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    old_title = db.Column(db.String(200), nullable=False)
    old_description = db.Column(db.Text, nullable=False)
    old_tag = db.Column(db.String(80), nullable=False)
    edited_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    complaint = db.relationship("Complaint", back_populates="edit_history")


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("student_id", "complaint_id", name="uq_vote_student_complaint"),
    )

    student = db.relationship("Student", back_populates="votes")
    complaint = db.relationship("Complaint", back_populates="vote_records")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaint.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    user_role = db.Column(db.String(20), nullable=False, default="student")
    parent_comment_id = db.Column(db.Integer, db.ForeignKey("comment.id"))
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    complaint = db.relationship("Complaint", back_populates="comments")
    author = db.relationship("Student")
    parent = db.relationship("Comment", remote_side=[id], back_populates="replies")
    replies = db.relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Comment.created_at.asc()",
    )


def initialize_database() -> None:
    with app.app_context():
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        db.create_all()
        ensure_student_schema()
        ensure_complaint_schema()
        ensure_vote_schema()
        ensure_edit_history_schema()
        ensure_notification_schema()
        ensure_comment_schema()
        ensure_default_admin()


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

    if "votes" not in column_names:
        db.session.execute(
            text("ALTER TABLE complaint ADD COLUMN votes INTEGER NOT NULL DEFAULT 1")
        )
        db.session.commit()

    if "is_merged" not in column_names:
        db.session.execute(
            text("ALTER TABLE complaint ADD COLUMN is_merged BOOLEAN NOT NULL DEFAULT 0")
        )
        db.session.commit()

    if "is_deleted" not in column_names:
        db.session.execute(
            text("ALTER TABLE complaint ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0")
        )
        db.session.commit()

    if "deleted_by" not in column_names:
        db.session.execute(text("ALTER TABLE complaint ADD COLUMN deleted_by INTEGER"))
        db.session.commit()

    if "deleted_reason" not in column_names:
        db.session.execute(text("ALTER TABLE complaint ADD COLUMN deleted_reason TEXT"))
        db.session.commit()

    if "deleted_at" not in column_names:
        db.session.execute(text("ALTER TABLE complaint ADD COLUMN deleted_at DATETIME"))
        db.session.commit()

    if "parent_id" not in column_names:
        db.session.execute(text("ALTER TABLE complaint ADD COLUMN parent_id INTEGER"))
        db.session.commit()

    if "updated_at" not in column_names:
        db.session.execute(text("ALTER TABLE complaint ADD COLUMN updated_at DATETIME"))
        db.session.commit()

    db.session.execute(
        text(
            """
            UPDATE complaint
            SET updated_at = created_at
            WHERE updated_at IS NULL
            """
        )
    )
    db.session.commit()

    db.session.execute(
        text(
            """
            UPDATE complaint
            SET votes = 1
            WHERE votes IS NULL OR votes < 1
            """
        )
    )
    db.session.commit()


def ensure_vote_schema() -> None:
    inspector = inspect(db.engine)
    if not inspector.has_table("vote"):
        Vote.__table__.create(db.engine)

    complaints = Complaint.query.all()
    for complaint in complaints:
        vote_count = Vote.query.filter_by(complaint_id=complaint.id).count()

        if vote_count == 0:
            db.session.add(Vote(student_id=complaint.student_id, complaint_id=complaint.id))
            complaint.votes = max(complaint.votes, 1)
        else:
            complaint.votes = vote_count

    db.session.commit()


def ensure_edit_history_schema() -> None:
    inspector = inspect(db.engine)
    if not inspector.has_table("complaint_edit_history"):
        ComplaintEditHistory.__table__.create(db.engine)


def ensure_notification_schema() -> None:
    inspector = inspect(db.engine)
    if not inspector.has_table("notification"):
        Notification.__table__.create(db.engine)


def ensure_comment_schema() -> None:
    inspector = inspect(db.engine)
    if not inspector.has_table("comment"):
        Comment.__table__.create(db.engine)


def ensure_default_admin() -> None:
    admin_email = app.config["DEFAULT_ADMIN_EMAIL"]
    admin_student = Student.query.filter_by(email=admin_email).first()

    if admin_student is not None and admin_student.role != "admin":
        admin_student.role = "admin"
        db.session.commit()


@app.before_request
def load_logged_in_student() -> None:
    student_id = session.get("student_id")
    g.student = db.session.get(Student, student_id) if student_id else None


@app.context_processor
def inject_current_student() -> dict:
    unread_count = 0
    if getattr(g, "student", None) is not None and session.get("role") != "admin":
        unread_count = Notification.query.filter_by(
            student_id=g.student.id,
            is_read=False,
        ).count()

    return {
        "current_student": getattr(g, "student", None),
        "unread_notifications_count": unread_count,
        "feed_status_label": feed_status_label,
    }


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


def title_keywords(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {word for word in words if len(word) > 2 and word not in TITLE_STOP_WORDS}


def text_keywords(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.lower())
    return {word for word in words if len(word) > 2 and word not in TITLE_STOP_WORDS}


def keyword_overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def is_similar_title(submitted_title: str, existing_title: str) -> bool:
    submitted_normalized = submitted_title.strip().lower()
    existing_normalized = existing_title.strip().lower()

    if not submitted_normalized or not existing_normalized:
        return False

    if (
        submitted_normalized in existing_normalized
        or existing_normalized in submitted_normalized
    ):
        return True

    submitted_keywords = title_keywords(submitted_title)
    existing_keywords = title_keywords(existing_title)

    if not submitted_keywords or not existing_keywords:
        return False

    common_keywords = submitted_keywords & existing_keywords
    return len(common_keywords) >= 2


def complaint_similarity_score(
    title: str,
    description: str,
    existing_complaint: "Complaint",
    department: str,
    tag: str,
) -> float:
    if existing_complaint.is_merged:
        return 0.0

    score = 0.0
    if department and department == existing_complaint.department:
        score += 0.2
    if tag and tag == existing_complaint.tag:
        score += 0.25

    if is_similar_title(title, existing_complaint.title):
        score += 0.35

    combined_submitted_keywords = text_keywords(f"{title} {description}")
    combined_existing_keywords = text_keywords(
        f"{existing_complaint.title} {existing_complaint.description}"
    )
    overlap_score = keyword_overlap_score(
        combined_submitted_keywords,
        combined_existing_keywords,
    )

    if overlap_score >= 0.5:
        score += 0.35
    elif overlap_score >= 0.3:
        score += 0.2
    elif overlap_score >= 0.18:
        score += 0.1

    return score


def find_similar_complaints(
    title: str,
    description: str,
    department: str,
    tag: str,
    limit: int = 5,
) -> list[Complaint]:
    if not department:
        return []

    candidates = (
        active_complaints_query()
        .filter(Complaint.department == department)
        .order_by(Complaint.votes.desc(), Complaint.created_at.desc())
        .all()
    )

    scored_matches = []
    for complaint in candidates:
        score = complaint_similarity_score(title, description, complaint, department, tag)
        if score >= 0.45:
            scored_matches.append((score, complaint))

    scored_matches.sort(
        key=lambda item: (item[0], item[1].votes, item[1].created_at),
        reverse=True,
    )
    return [complaint for _, complaint in scored_matches[:limit]]


def active_complaints_query():
    return Complaint.query.filter_by(is_merged=False, is_deleted=False)


def deleted_complaints_query():
    return Complaint.query.filter_by(is_deleted=True)


def non_merged_complaints_query():
    return Complaint.query.filter_by(is_merged=False)


def normalize_admin_visibility(raw_value: str) -> str:
    value = (raw_value or "").strip().lower()
    if value not in ADMIN_VISIBILITY_OPTIONS:
        return "active"
    return value


def complaint_scope_query_for_admin(visibility: str):
    if visibility == "deleted":
        return Complaint.query.filter(
            Complaint.is_merged.is_(False),
            Complaint.is_deleted.is_(True),
        )
    if visibility == "all":
        return Complaint.query.filter(Complaint.is_merged.is_(False))
    return active_complaints_query()


def build_deleted_reason(selected_reason: str, custom_reason: str) -> str:
    normalized_reason = selected_reason.strip()
    normalized_custom_reason = custom_reason.strip()

    if normalized_reason not in DELETION_REASON_OPTIONS:
        raise ValueError("Please choose a valid deletion reason.")

    if normalized_reason == "Other":
        if not normalized_custom_reason:
            raise ValueError("Please provide a reason when selecting Other.")
        return f"Other: {normalized_custom_reason}"

    return normalized_reason


def safe_redirect_target(default_endpoint: str, **default_values) -> str:
    target = request.form.get("next", "").strip()
    if target.startswith("/"):
        return target
    return url_for(default_endpoint, **default_values)


def comment_redirect_target(complaint_id: int) -> str:
    if session.get("role") == "admin":
        return safe_redirect_target("admin_complaint_detail", complaint_id=complaint_id)
    return safe_redirect_target("complaint_detail", complaint_id=complaint_id)


def sanitize_comment_content(raw_content: str) -> str:
    cleaned = (raw_content or "").replace("\x00", "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"<[^>]*>", "", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.split("\n"))
    return cleaned.strip()


def can_view_complaint(complaint: "Complaint") -> bool:
    if getattr(g, "student", None) is None:
        return False
    if session.get("role") == "admin":
        return True
    if complaint.student_id == g.student.id:
        return True
    return not complaint.is_deleted


def can_edit_comment(comment: "Comment") -> bool:
    return getattr(g, "student", None) is not None and comment.user_id == g.student.id


def can_delete_comment(comment: "Comment") -> bool:
    if getattr(g, "student", None) is None:
        return False
    if session.get("role") == "admin":
        return True
    return comment.user_id == g.student.id


def serialize_comment(comment: "Comment") -> dict:
    author = comment.author
    display_name = author.name if author is not None else f"User #{comment.user_id}"
    is_placeholder = comment.content == "This comment was deleted."
    return {
        "id": comment.id,
        "content": comment.content,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        "author_name": display_name,
        "user_role": comment.user_role,
        "is_admin": comment.user_role == "admin",
        "is_placeholder": is_placeholder,
        "can_edit": can_edit_comment(comment) and not is_placeholder,
        "can_delete": can_delete_comment(comment),
        "can_reply": not is_placeholder,
    }


def get_comment_threads(complaint_id: int, page: int) -> tuple[list[dict], int, bool]:
    visible_limit = max(page, 1) * COMMENTS_PAGE_SIZE
    top_level_query = Comment.query.filter_by(
        complaint_id=complaint_id,
        parent_comment_id=None,
    ).order_by(Comment.created_at.asc(), Comment.id.asc())
    total_top_level = top_level_query.count()
    top_level_comments = top_level_query.limit(visible_limit).all()
    parent_ids = [comment.id for comment in top_level_comments]

    replies_by_parent: dict[int, list[dict]] = {}
    if parent_ids:
        replies = (
            Comment.query.filter(Comment.parent_comment_id.in_(parent_ids))
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .all()
        )
        for reply in replies:
            replies_by_parent.setdefault(reply.parent_comment_id, []).append(
                serialize_comment(reply)
            )

    threads = []
    for comment in top_level_comments:
        threads.append(
            {
                "comment": serialize_comment(comment),
                "replies": replies_by_parent.get(comment.id, []),
            }
        )

    return threads, total_top_level, total_top_level > len(top_level_comments)


def delete_comment_or_placeholder(comment: "Comment") -> None:
    if comment.replies:
        comment.content = "This comment was deleted."
        comment.updated_at = datetime.utcnow()
        return
    db.session.delete(comment)


def can_student_edit_complaint(complaint: "Complaint") -> tuple[bool, str | None]:
    if complaint.student_id != getattr(g, "student", None).id:
        return False, "You can only edit your own complaints."
    if complaint.is_deleted:
        return False, "Deleted complaints cannot be edited."
    if complaint.is_merged:
        return False, "Merged complaints cannot be edited."
    if complaint.status == "Resolved":
        return False, "Resolved complaints cannot be edited."
    return True, None


def can_student_delete_complaint(complaint: "Complaint") -> tuple[bool, str | None]:
    if complaint.student_id != getattr(g, "student", None).id:
        return False, "You can only delete your own complaints."
    if complaint.is_deleted:
        return False, "This complaint has already been archived."
    if complaint.is_merged:
        return False, "Merged complaints cannot be deleted."
    if complaint.status == "Resolved":
        return False, "Resolved complaints cannot be deleted."
    return True, None


def feed_status_label(status: str) -> str:
    if status in {"Submitted", "Under Review"}:
        return "Pending"
    return status


def format_time_ago(value: datetime | None) -> str:
    if value is None:
        return "Unknown"

    current_time = datetime.now(timezone.utc)
    source_time = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    delta = current_time - source_time.astimezone(timezone.utc)
    seconds = max(int(delta.total_seconds()), 0)

    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if seconds < 604800:
        days = seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"
    weeks = seconds // 604800
    return f"{weeks} week{'s' if weeks != 1 else ''} ago"


def complaint_matches_search(complaint: "Complaint", search_term: str) -> bool:
    if not search_term:
        return True

    search_keywords = text_keywords(search_term)
    searchable_text = " ".join(
        [complaint.title, complaint.description, complaint.tag, complaint.department]
    ).lower()

    if search_term.lower() in searchable_text:
        return True

    complaint_keywords = text_keywords(searchable_text)
    return bool(search_keywords & complaint_keywords)


def complaint_matches_status(complaint: "Complaint", selected_status: str) -> bool:
    if selected_status == "all":
        return True

    mapped_status = feed_status_label(complaint.status).lower().replace(" ", "_")
    return mapped_status == selected_status


def serialize_complaint_card(complaint: "Complaint", voted_ids: set[int] | None = None) -> dict:
    voted_ids = voted_ids or set()
    posted_by = (
        "You"
        if getattr(g, "student", None) is not None and complaint.student_id == g.student.id
        else f"Student #{complaint.student_id}"
    )
    return {
        "id": complaint.id,
        "title": complaint.title,
        "description": complaint.description,
        "category": complaint.tag,
        "tag": complaint.tag,
        "department": complaint.department,
        "status": complaint.status,
        "feed_status": feed_status_label(complaint.status),
        "votes": complaint.votes,
        "posted_by": posted_by,
        "time_ago": format_time_ago(complaint.created_at),
        "created_at": complaint.created_at,
        "image": complaint.image,
        "has_voted": complaint.id in voted_ids,
        "priority": complaint.priority,
        "student_name": complaint.student.name,
        "student_id": complaint.student_id,
        "updated_at": complaint.updated_at,
        "is_deleted": complaint.is_deleted,
        "deleted_reason": complaint.deleted_reason,
        "deleted_at": complaint.deleted_at,
        "deleted_by": complaint.deleted_by,
        "merged_count": len(complaint.merged_children),
        "can_edit": (
            getattr(g, "student", None) is not None
            and complaint.student_id == g.student.id
            and not complaint.is_deleted
            and not complaint.is_merged
            and complaint.status != "Resolved"
        ),
        "can_delete": (
            getattr(g, "student", None) is not None
            and complaint.student_id == g.student.id
            and not complaint.is_deleted
            and not complaint.is_merged
            and complaint.status != "Resolved"
        ),
    }


def build_feed_context(is_admin: bool = False) -> dict:
    search_term = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "").strip()
    selected_department = request.args.get("department", "").strip()
    selected_scope = request.args.get("scope", "all").strip().lower() or "all"
    selected_status = request.args.get("status", "all").strip() or "all"
    sort_by = request.args.get("sort", DEFAULT_FEED_SORT).strip() or DEFAULT_FEED_SORT
    page = max(request.args.get("page", 1, type=int), 1)
    visibility = (
        normalize_admin_visibility(request.args.get("visibility", "active"))
        if is_admin
        else "active"
    )

    complaints = complaint_scope_query_for_admin(visibility).all()

    if selected_category:
        complaints = [item for item in complaints if item.tag == selected_category]

    if selected_department:
        complaints = [item for item in complaints if item.department == selected_department]

    if (
        not is_admin
        and selected_scope == "my_department"
        and getattr(g, "student", None) is not None
    ):
        complaints = [item for item in complaints if item.department == g.student.department]
    else:
        selected_scope = "all"

    complaints = [
        item
        for item in complaints
        if complaint_matches_status(item, selected_status)
        and complaint_matches_search(item, search_term)
    ]

    if sort_by == "recent":
        complaints.sort(key=lambda item: item.created_at, reverse=True)
    else:
        sort_by = DEFAULT_FEED_SORT
        complaints.sort(key=lambda item: (item.votes, item.created_at), reverse=True)

    voted_ids: set[int] = set()
    if not is_admin and getattr(g, "student", None) is not None:
        voted_ids = {
            vote.complaint_id
            for vote in Vote.query.filter_by(student_id=g.student.id).all()
        }

    trending_ids = {
        complaint.id
        for complaint in sorted(
            complaints,
            key=lambda item: (item.votes, item.created_at),
            reverse=True,
        )[:TRENDING_COMPLAINT_LIMIT]
        if complaint.votes >= TRENDING_COMPLAINT_MIN_VOTES
    }

    complaint_cards = []
    for complaint in complaints:
        card = serialize_complaint_card(complaint, voted_ids=voted_ids)
        card["is_trending"] = complaint.id in trending_ids
        complaint_cards.append(card)

    total_results = len(complaint_cards)
    visible_count = page * FEED_PAGE_SIZE
    visible_cards = complaint_cards[:visible_count]
    has_more = total_results > len(visible_cards)

    status_counts = {
        "all": len(complaint_cards),
        "pending": sum(1 for item in complaint_cards if item["feed_status"] == "Pending"),
        "in_progress": sum(
            1 for item in complaint_cards if item["feed_status"] == "In Progress"
        ),
        "resolved": sum(1 for item in complaint_cards if item["feed_status"] == "Resolved"),
    }

    return {
        "complaint_cards": visible_cards,
        "feed_filters": {
            "q": search_term,
            "category": selected_category,
            "department": selected_department,
            "scope": selected_scope,
            "status": selected_status,
            "sort": sort_by,
            "visibility": visibility,
            "page": page,
        },
        "feed_sort_options": FEED_SORT_OPTIONS,
        "feed_status_options": FEED_STATUS_OPTIONS,
        "feed_visibility_options": ADMIN_VISIBILITY_OPTIONS,
        "feed_category_options": CATEGORY_TAGS,
        "feed_department_options": DEPARTMENTS,
        "feed_status_counts": status_counts,
        "trending_count": len(trending_ids),
        "feed_total_results": total_results,
        "feed_has_more": has_more,
        "feed_next_page": page + 1,
    }


def get_submit_complaint_context(**extra_context):
    context = {
        "category_tags": CATEGORY_TAGS,
        "departments": DEPARTMENTS,
        "priority_levels": PRIORITY_LEVELS,
        "duplicate_complaints": [],
    }
    context.update(extra_context)
    return context


def get_edit_complaint_context(complaint: "Complaint", **extra_context):
    context = {
        "complaint": complaint,
        "category_tags": CATEGORY_TAGS,
        "departments": DEPARTMENTS,
        "priority_levels": PRIORITY_LEVELS,
        "edit_history_notice_threshold": EDIT_HISTORY_NOTICE_THRESHOLD,
    }
    context.update(extra_context)
    return context


def create_notification(student_id: int, complaint_id: int, message: str) -> None:
    db.session.add(
        Notification(
            student_id=student_id,
            complaint_id=complaint_id,
            message=message,
            is_read=False,
            created_at=datetime.utcnow(),
        )
    )


def delete_complaint_with_dependencies(complaint: "Complaint") -> None:
    Notification.query.filter_by(complaint_id=complaint.id).delete()
    db.session.delete(complaint)


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
        Complaint.query.filter_by(student_id=g.student.id, is_merged=False)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return render_template(
        "dashboard.html",
        complaints=complaints,
        **build_feed_context(is_admin=False),
    )


@app.route("/my-complaints")
@login_required
def my_complaints():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    complaints = (
        Complaint.query.filter_by(student_id=g.student.id, is_merged=False)
        .order_by(Complaint.is_deleted.asc(), Complaint.updated_at.desc(), Complaint.created_at.desc())
        .all()
    )
    return render_template(
        "my_complaints.html",
        complaints=complaints,
        complaint_statuses=COMPLAINT_STATUSES,
        status_progress_map=STATUS_PROGRESS_MAP,
    )


@app.route("/complaint/<int:complaint_id>")
@login_required
def complaint_detail(complaint_id: int):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        return redirect(url_for("dashboard"))

    if session.get("role") == "admin":
        return redirect(url_for("admin_complaint_detail", complaint_id=complaint.id))

    if not can_view_complaint(complaint):
        flash("You do not have access to that complaint.", "warning")
        return redirect(url_for("dashboard"))

    comments_page = max(request.args.get("comments_page", 1, type=int), 1)
    comment_threads, top_level_comment_count, comments_has_more = get_comment_threads(
        complaint.id, comments_page
    )
    total_comment_count = Comment.query.filter_by(complaint_id=complaint.id).count()

    updates = (
        ComplaintUpdate.query.filter_by(complaint_id=complaint.id)
        .order_by(ComplaintUpdate.date.desc())
        .all()
    )
    return render_template(
        "complaint_detail.html",
        complaint=complaint,
        updates=updates,
        comment_threads=comment_threads,
        comments_page=comments_page,
        comments_has_more=comments_has_more,
        top_level_comment_count=top_level_comment_count,
        total_comment_count=total_comment_count,
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
        submit_anyway = request.form.get("submit_anyway") == "1"
        image_file = request.files.get("image")

        if not all([title, description, tag, department, priority]):
            flash("Please complete all required fields.", "danger")
            return render_template(
                "submit_complaint.html",
                **get_submit_complaint_context(),
            )

        if tag not in CATEGORY_TAGS:
            flash("Please choose a valid category tag.", "danger")
            return render_template(
                "submit_complaint.html",
                **get_submit_complaint_context(),
            )

        if department not in DEPARTMENTS:
            flash("Please choose a valid department.", "danger")
            return render_template(
                "submit_complaint.html",
                **get_submit_complaint_context(),
            )

        if priority not in PRIORITY_LEVELS:
            flash("Please choose a valid priority level.", "danger")
            return render_template(
                "submit_complaint.html",
                **get_submit_complaint_context(),
            )

        similar_complaints = find_similar_complaints(title, description, department, tag)
        existing_vote = None
        if similar_complaints:
            similar_ids = [complaint.id for complaint in similar_complaints]
            existing_vote = (
                Vote.query.filter(
                    Vote.student_id == g.student.id,
                    Vote.complaint_id.in_(similar_ids),
                )
                .first()
            )

        if similar_complaints and not submit_anyway:
            flash(
                "This complaint has already been submitted. You can vote for the existing complaint instead of creating a duplicate.",
                "warning",
            )
            return render_template(
                "submit_complaint.html",
                **get_submit_complaint_context(
                    duplicate_complaints=similar_complaints,
                    already_voted_complaint_id=existing_vote.complaint_id if existing_vote else None,
                ),
            )

        image_filename = None
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename):
                flash("Image must be a JPG, JPEG, or PNG file.", "danger")
                return render_template(
                    "submit_complaint.html",
                    **get_submit_complaint_context(),
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
            votes=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(complaint)
        db.session.flush()
        db.session.add(Vote(student_id=g.student.id, complaint_id=complaint.id))
        db.session.commit()

        flash("Complaint submitted successfully.", "success")
        return redirect(url_for("my_complaints"))

    return render_template(
        "submit_complaint.html",
        **get_submit_complaint_context(),
    )


@app.route("/complaints/<int:complaint_id>/comments", methods=["POST"])
@login_required
def create_comment(complaint_id: int):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        if session.get("role") == "admin":
            return redirect(url_for("admin_complaints"))
        return redirect(url_for("dashboard"))

    if not can_view_complaint(complaint):
        flash("You do not have access to comment on that complaint.", "warning")
        return redirect(comment_redirect_target(complaint_id))

    if complaint.is_deleted:
        flash("Comments are locked for deleted complaints.", "warning")
        return redirect(comment_redirect_target(complaint_id))

    content = sanitize_comment_content(request.form.get("content", ""))
    if not content:
        flash("Comment text cannot be empty.", "danger")
        return redirect(comment_redirect_target(complaint_id))

    if len(content) > MAX_COMMENT_LENGTH:
        flash(f"Comments must be {MAX_COMMENT_LENGTH} characters or fewer.", "danger")
        return redirect(comment_redirect_target(complaint_id))

    parent_comment_id = request.form.get("parent_comment_id", type=int)
    parent_comment = None
    if parent_comment_id:
        parent_comment = db.session.get(Comment, parent_comment_id)
        if (
            parent_comment is None
            or parent_comment.complaint_id != complaint.id
            or parent_comment.parent_comment_id is not None
        ):
            flash("Reply target is invalid.", "danger")
            return redirect(comment_redirect_target(complaint_id))

    comment = Comment(
        complaint_id=complaint.id,
        user_id=g.student.id,
        user_role=session.get("role", "student"),
        parent_comment_id=parent_comment.id if parent_comment else None,
        content=content,
        updated_at=datetime.utcnow(),
    )
    db.session.add(comment)
    db.session.commit()
    flash("Comment posted successfully.", "success")
    return redirect(comment_redirect_target(complaint_id))


@app.route("/vote/<int:complaint_id>", methods=["POST"])
@login_required
def vote_complaint(complaint_id: int):
    if session.get("role") == "admin":
        flash("Administrators cannot vote on student complaints.", "warning")
        return redirect(url_for("admin_dashboard"))

    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        return redirect(url_for("my_complaints"))

    if complaint.is_deleted:
        flash("Archived complaints can no longer receive votes.", "warning")
        return redirect(request.form.get("next") or url_for("dashboard"))

    if complaint.is_merged and complaint.parent_id:
        complaint = db.session.get(Complaint, complaint.parent_id) or complaint

    existing_vote = Vote.query.filter_by(
        student_id=g.student.id,
        complaint_id=complaint.id,
    ).first()
    if existing_vote is not None:
        flash("You have already voted for this complaint.", "info")
        next_page = request.form.get("next") or url_for("my_complaints")
        return redirect(next_page)

    db.session.add(Vote(student_id=g.student.id, complaint_id=complaint.id))
    complaint.votes += 1
    db.session.commit()

    flash("Your vote has been added to this complaint.", "success")
    next_page = request.form.get("next") or url_for("my_complaints")
    return redirect(next_page)


@app.route("/comments/<int:comment_id>/edit", methods=["POST"])
@login_required
def edit_comment(comment_id: int):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        flash("Comment not found.", "danger")
        if session.get("role") == "admin":
            return redirect(url_for("admin_complaints"))
        return redirect(url_for("dashboard"))

    if not can_edit_comment(comment):
        flash("You can only edit your own comments.", "warning")
        return redirect(comment_redirect_target(comment.complaint_id))

    updated_content = sanitize_comment_content(request.form.get("content", ""))
    if not updated_content:
        flash("Comment text cannot be empty.", "danger")
        return redirect(comment_redirect_target(comment.complaint_id))

    if len(updated_content) > MAX_COMMENT_LENGTH:
        flash(f"Comments must be {MAX_COMMENT_LENGTH} characters or fewer.", "danger")
        return redirect(comment_redirect_target(comment.complaint_id))

    comment.content = updated_content
    comment.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Comment updated successfully.", "success")
    return redirect(comment_redirect_target(comment.complaint_id))


@app.route("/comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id: int):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        flash("Comment not found.", "danger")
        if session.get("role") == "admin":
            return redirect(url_for("admin_complaints"))
        return redirect(url_for("dashboard"))

    if not can_delete_comment(comment):
        flash("You do not have permission to delete that comment.", "warning")
        return redirect(comment_redirect_target(comment.complaint_id))

    complaint_id = comment.complaint_id
    delete_comment_or_placeholder(comment)
    db.session.commit()
    flash("Comment removed successfully.", "success")
    return redirect(comment_redirect_target(complaint_id))


@app.route("/complaints/<int:complaint_id>/edit", methods=["GET", "POST"])
@login_required
def edit_student_complaint(complaint_id: int):
    if session.get("role") == "admin":
        flash("Administrators cannot edit student complaints here.", "warning")
        return redirect(url_for("admin_dashboard"))

    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        return redirect(url_for("my_complaints"))

    is_allowed, error_message = can_student_edit_complaint(complaint)
    if not is_allowed:
        flash(error_message, "danger")
        return redirect(url_for("my_complaints"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        tag = request.form.get("tag", "").strip()
        department = request.form.get("department", "").strip()
        priority = request.form.get("priority", "").strip()

        if not all([title, description, tag, department, priority]):
            flash("Please complete all required fields.", "danger")
            return render_template(
                "edit_complaint.html",
                **get_edit_complaint_context(complaint),
            )

        if tag not in CATEGORY_TAGS:
            flash("Please choose a valid category.", "danger")
            return render_template(
                "edit_complaint.html",
                **get_edit_complaint_context(complaint),
            )

        if department not in DEPARTMENTS:
            flash("Please choose a valid department.", "danger")
            return render_template(
                "edit_complaint.html",
                **get_edit_complaint_context(complaint),
            )

        if priority not in PRIORITY_LEVELS:
            flash("Please choose a valid priority level.", "danger")
            return render_template(
                "edit_complaint.html",
                **get_edit_complaint_context(complaint),
            )

        if (
            title != complaint.title
            or description != complaint.description
            or tag != complaint.tag
        ):
            db.session.add(
                ComplaintEditHistory(
                    complaint_id=complaint.id,
                    old_title=complaint.title,
                    old_description=complaint.description,
                    old_tag=complaint.tag,
                    edited_at=datetime.utcnow(),
                )
            )

        complaint.title = title
        complaint.description = description
        complaint.tag = tag
        complaint.department = department
        complaint.priority = priority
        complaint.updated_at = datetime.utcnow()
        db.session.commit()

        if complaint.votes > EDIT_HISTORY_NOTICE_THRESHOLD:
            flash(
                "Complaint updated. Because this complaint has strong community support, the previous version was recorded in edit history.",
                "warning",
            )
        else:
            flash("Complaint updated successfully.", "success")
        return redirect(url_for("my_complaints"))

    return render_template(
        "edit_complaint.html",
        **get_edit_complaint_context(complaint),
    )


@app.route("/complaints/<int:complaint_id>", methods=["PUT"])
@login_required
def update_student_complaint_api(complaint_id: int):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        return jsonify({"error": "Complaint not found."}), 404

    is_allowed, error_message = can_student_edit_complaint(complaint)
    if not is_allowed:
        return jsonify({"error": error_message}), 403

    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    tag = str(payload.get("tag", "")).strip()
    department = str(payload.get("department", complaint.department)).strip()
    priority = str(payload.get("priority", complaint.priority)).strip()

    if not all([title, description, tag, department, priority]):
        return jsonify({"error": "All editable fields are required."}), 400
    if tag not in CATEGORY_TAGS:
        return jsonify({"error": "Invalid category."}), 400
    if department not in DEPARTMENTS:
        return jsonify({"error": "Invalid department."}), 400
    if priority not in PRIORITY_LEVELS:
        return jsonify({"error": "Invalid priority."}), 400

    if (
        title != complaint.title
        or description != complaint.description
        or tag != complaint.tag
    ):
        db.session.add(
            ComplaintEditHistory(
                complaint_id=complaint.id,
                old_title=complaint.title,
                old_description=complaint.description,
                old_tag=complaint.tag,
                edited_at=datetime.utcnow(),
            )
        )

    complaint.title = title
    complaint.description = description
    complaint.tag = tag
    complaint.department = department
    complaint.priority = priority
    complaint.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(
        {
            "message": "Complaint updated successfully.",
            "complaint": {
                "id": complaint.id,
                "title": complaint.title,
                "description": complaint.description,
                "category": complaint.tag,
                "votes": complaint.votes,
                "updated_at": complaint.updated_at.isoformat(),
            },
        }
    )


@app.route("/complaints/<int:complaint_id>/delete", methods=["POST"])
@login_required
def delete_student_complaint(complaint_id: int):
    if session.get("role") == "admin":
        flash("Administrators cannot delete student complaints here.", "warning")
        return redirect(url_for("admin_dashboard"))

    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        return redirect(url_for("my_complaints"))

    is_allowed, error_message = can_student_delete_complaint(complaint)
    if not is_allowed:
        flash(error_message, "danger")
        return redirect(url_for("my_complaints"))

    if complaint.votes <= HARD_DELETE_MAX_VOTES:
        delete_complaint_with_dependencies(complaint)
        db.session.commit()
        flash("Complaint deleted permanently.", "success")
    else:
        complaint.is_deleted = True
        complaint.updated_at = datetime.utcnow()
        db.session.commit()
        flash(
            "Complaint archived instead of deleted because multiple students voted for it. The record and vote count were preserved for fairness.",
            "warning",
        )

    return redirect(url_for("my_complaints"))


@app.route("/complaints/<int:complaint_id>", methods=["DELETE"])
@login_required
def delete_student_complaint_api(complaint_id: int):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        return jsonify({"error": "Complaint not found."}), 404

    is_allowed, error_message = can_student_delete_complaint(complaint)
    if not is_allowed:
        return jsonify({"error": error_message}), 403

    if complaint.votes <= HARD_DELETE_MAX_VOTES:
        delete_complaint_with_dependencies(complaint)
        db.session.commit()
        return jsonify({"message": "Complaint deleted permanently.", "mode": "hard_delete"})

    complaint.is_deleted = True
    complaint.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Complaint archived successfully.", "mode": "soft_delete"})


@app.route("/api/similar-complaints")
@login_required
def similar_complaints_api():
    if session.get("role") == "admin":
        return jsonify({"items": []})

    title = request.args.get("title", "").strip()
    description = request.args.get("description", "").strip()
    department = request.args.get("department", "").strip()
    tag = request.args.get("tag", "").strip()

    if len(title) < 4 or not department or not tag:
        return jsonify({"items": []})

    similar_complaints = find_similar_complaints(title, description, department, tag, limit=3)
    voted_ids = {
        vote.complaint_id for vote in Vote.query.filter_by(student_id=g.student.id).all()
    }
    items = [serialize_complaint_card(item, voted_ids=voted_ids) for item in similar_complaints]
    return jsonify({"items": items})


@app.route("/notifications")
@login_required
def notifications():
    if session.get("role") == "admin":
        flash("Notifications are available only for student accounts.", "warning")
        return redirect(url_for("admin_dashboard"))

    notification_items = (
        Notification.query.filter_by(student_id=g.student.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template("notifications.html", notifications=notification_items)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()

        if not name or not department:
            flash("Name and department are required.", "danger")
            return render_template("profile.html", departments=DEPARTMENTS)

        if department not in DEPARTMENTS:
            flash("Please choose a valid department.", "danger")
            return render_template("profile.html", departments=DEPARTMENTS)

        g.student.name = name
        g.student.department = department
        session["student_name"] = name
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", departments=DEPARTMENTS)


@app.route("/settings")
@login_required
def settings():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    return render_template("settings.html")


@app.route("/mark-read/<int:notification_id>", methods=["POST"])
@login_required
def mark_notification_read(notification_id: int):
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.student_id != g.student.id:
        flash("Notification not found.", "danger")
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("notifications"))

    notification.is_read = True
    db.session.commit()
    flash("Notification marked as read.", "success")
    return redirect(url_for("notifications"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    visibility = normalize_admin_visibility(request.args.get("visibility", "active"))
    complaints = (
        complaint_scope_query_for_admin(visibility)
        .order_by(Complaint.votes.desc(), Complaint.created_at.desc())
        .all()
    )
    merged_count = Complaint.query.filter_by(is_merged=True).count()
    deleted_count = deleted_complaints_query().count()
    stats = {
        "total": len(complaints),
        "pending": sum(
            1 for complaint in complaints if feed_status_label(complaint.status) == "Pending"
        ),
        "in_progress": sum(
            1 for complaint in complaints if complaint.status == "In Progress"
        ),
        "resolved": sum(1 for complaint in complaints if complaint.status == "Resolved"),
        "merged": merged_count,
        "deleted": deleted_count,
    }
    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        complaint_statuses=COMPLAINT_STATUSES,
        stats=stats,
        deletion_reason_options=DELETION_REASON_OPTIONS,
        **build_feed_context(is_admin=True),
    )


@app.route("/admin/complaints")
@admin_required
def admin_complaints():
    selected_department = request.args.get("department", "").strip()
    visibility = normalize_admin_visibility(request.args.get("visibility", "all"))

    if visibility == "deleted":
        complaints_query = deleted_complaints_query()
    elif visibility == "active":
        complaints_query = active_complaints_query()
    else:
        complaints_query = Complaint.query

    if selected_department:
        complaints_query = complaints_query.filter(Complaint.department == selected_department)

    complaints = complaints_query.order_by(
        Complaint.is_merged.asc(),
        Complaint.votes.desc(),
        Complaint.created_at.desc(),
    ).all()
    merge_targets = (
        active_complaints_query()
        .order_by(Complaint.votes.desc(), Complaint.created_at.desc())
        .all()
    )
    return render_template(
        "admin_complaints.html",
        complaints=complaints,
        merge_targets=merge_targets,
        departments=DEPARTMENTS,
        selected_department=selected_department,
        selected_visibility=visibility,
        visibility_options=ADMIN_VISIBILITY_OPTIONS,
        deletion_reason_options=DELETION_REASON_OPTIONS,
    )


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
    merge_targets = (
        active_complaints_query()
        .filter(Complaint.id != complaint.id)
        .order_by(Complaint.votes.desc(), Complaint.created_at.desc())
        .all()
    )
    comments_page = max(request.args.get("comments_page", 1, type=int), 1)
    comment_threads, top_level_comment_count, comments_has_more = get_comment_threads(
        complaint.id, comments_page
    )
    total_comment_count = Comment.query.filter_by(complaint_id=complaint.id).count()
    return render_template(
        "admin_complaint_detail.html",
        complaint=complaint,
        updates=updates,
        complaint_statuses=COMPLAINT_STATUSES,
        status_progress_map=STATUS_PROGRESS_MAP,
        merge_targets=merge_targets,
        deletion_reason_options=DELETION_REASON_OPTIONS,
        comment_threads=comment_threads,
        comments_page=comments_page,
        comments_has_more=comments_has_more,
        top_level_comment_count=top_level_comment_count,
        total_comment_count=total_comment_count,
    )


@app.route("/admin/complaint/<int:complaint_id>/update", methods=["POST"])
@admin_required
def update_complaint(complaint_id: int):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        return redirect(url_for("admin_complaints"))

    if complaint.is_deleted:
        flash("Deleted complaints cannot be updated.", "warning")
        return redirect(url_for("admin_complaint_detail", complaint_id=complaint.id))

    previous_status = complaint.status
    previous_progress = complaint.progress

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

    notification_parts = []
    if status != previous_status:
        notification_parts.append(f"status changed to {status}")
    if progress != previous_progress:
        notification_parts.append(f"progress updated to {progress}%")
    if message:
        notification_parts.append(f"admin message: {message}")

    if notification_parts:
        create_notification(
            student_id=complaint.student_id,
            complaint_id=complaint.id,
            message=(
                f"Your complaint '{complaint.title}' has "
                + ", ".join(notification_parts)
                + "."
            ),
        )

    db.session.commit()
    flash("Complaint updated successfully.", "success")
    return redirect(url_for("admin_complaint_detail", complaint_id=complaint.id))


@app.route("/admin/merge/<int:child_id>", methods=["POST"])
@admin_required
def merge_complaints(child_id: int):
    parent_id_raw = request.form.get("parent_id", "").strip()
    try:
        parent_id = int(parent_id_raw)
    except ValueError:
        flash("Choose a valid main complaint to merge into.", "danger")
        return redirect(url_for("admin_complaints"))

    if child_id == parent_id:
        flash("A complaint cannot be merged into itself.", "danger")
        return redirect(url_for("admin_complaints"))

    child = db.session.get(Complaint, child_id)
    parent = db.session.get(Complaint, parent_id)

    if child is None or parent is None:
        flash("One of the selected complaints could not be found.", "danger")
        return redirect(url_for("admin_complaints"))

    if child.is_merged:
        flash("This complaint has already been merged.", "info")
        return redirect(url_for("admin_complaints"))

    if child.is_deleted or parent.is_deleted:
        flash("Deleted complaints cannot be merged.", "danger")
        return redirect(url_for("admin_complaints"))

    if parent.is_merged:
        flash("Choose a main complaint that is not already merged.", "danger")
        return redirect(url_for("admin_complaints"))

    moved_votes = 0
    child_votes = Vote.query.filter_by(complaint_id=child.id).all()
    for vote in child_votes:
        existing_parent_vote = Vote.query.filter_by(
            student_id=vote.student_id,
            complaint_id=parent.id,
        ).first()
        if existing_parent_vote is None:
            db.session.add(Vote(student_id=vote.student_id, complaint_id=parent.id))
            moved_votes += 1
        db.session.delete(vote)

    child.is_merged = True
    child.parent_id = parent.id
    child.votes = 0
    parent.votes += moved_votes

    db.session.add(
        ComplaintUpdate(
            complaint_id=parent.id,
            message=f"Merged duplicate complaint #{child.id}: {child.title}",
            progress=parent.status,
            date=datetime.utcnow(),
        )
    )
    db.session.commit()

    flash(f"Complaint #{child.id} was merged into complaint #{parent.id}.", "success")
    return redirect(url_for("admin_complaint_detail", complaint_id=parent.id))


@app.route("/admin/complaint/<int:complaint_id>/delete", methods=["POST"])
@admin_required
def admin_delete_complaint(complaint_id: int):
    complaint = db.session.get(Complaint, complaint_id)
    if complaint is None:
        flash("Complaint not found.", "danger")
        return redirect(safe_redirect_target("admin_dashboard"))

    if complaint.is_deleted:
        flash("This complaint has already been deleted.", "info")
        return redirect(
            safe_redirect_target("admin_complaint_detail", complaint_id=complaint.id)
        )

    selected_reason = request.form.get("deleted_reason", "").strip()
    custom_reason = request.form.get("custom_reason", "").strip()

    try:
        deleted_reason = build_deleted_reason(selected_reason, custom_reason)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(
            safe_redirect_target("admin_complaint_detail", complaint_id=complaint.id)
        )

    complaint.is_deleted = True
    complaint.deleted_by = g.student.id
    complaint.deleted_reason = deleted_reason
    complaint.deleted_at = datetime.utcnow()
    complaint.updated_at = datetime.utcnow()

    db.session.add(
        ComplaintUpdate(
            complaint_id=complaint.id,
            message=f"Complaint removed by admin. Reason: {deleted_reason}.",
            progress="Removed",
            date=datetime.utcnow(),
        )
    )
    create_notification(
        student_id=complaint.student_id,
        complaint_id=complaint.id,
        message=(
            f"Your complaint '{complaint.title}' was removed due to policy violation. "
            f"Reason: {deleted_reason}."
        ),
    )
    db.session.commit()

    flash("Complaint deleted successfully.", "success")
    return redirect(safe_redirect_target("admin_dashboard"))


@app.route("/admin/deleted-complaints")
@admin_required
def admin_deleted_complaints():
    deleted_items = (
        deleted_complaints_query()
        .order_by(Complaint.deleted_at.desc(), Complaint.updated_at.desc())
        .all()
    )
    return render_template("admin_deleted_complaints.html", complaints=deleted_items)


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
            return render_template("register.html", departments=DEPARTMENTS)

        if department not in DEPARTMENTS:
            flash("Please choose a valid department.", "danger")
            return render_template("register.html", departments=DEPARTMENTS)

        existing_student = Student.query.filter_by(email=email).first()
        if existing_student is not None:
            flash("An account with that email already exists.", "danger")
            return render_template("register.html", departments=DEPARTMENTS)

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

    return render_template("register.html", departments=DEPARTMENTS)


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
            return render_template("login.html", departments=DEPARTMENTS)

        session.clear()
        session["student_id"] = student.id
        session["student_name"] = student.name
        session["role"] = student.role
        flash("You are now logged in.", "success")
        if student.role == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("login.html", departments=DEPARTMENTS)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


initialize_database()


if __name__ == "__main__":
    print("Flask starting...")
   
    app.run(host="0.0.0.0", port=5000, debug=True)
