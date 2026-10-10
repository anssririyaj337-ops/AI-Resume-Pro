import os
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort, jsonify)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
import ai_service

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-me")
db_url = os.getenv("DATABASE_URL", "sqlite:///resume.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

TEMPLATES = ["classic", "modern", "compact"]
FIELDS = ["title", "template", "name", "email", "phone", "links",
          "education", "skills", "experience", "projects", "summary"]


# ---------- MODELS ----------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resumes = db.relationship("Resume", backref="owner", cascade="all, delete-orphan")


class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(120), default="Untitled Resume")
    template = db.Column(db.String(20), default="classic")
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    links = db.Column(db.String(300))
    education = db.Column(db.Text)
    skills = db.Column(db.Text)
    experience = db.Column(db.Text)
    projects = db.Column(db.Text)
    summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reports = db.relationship("AIReport", backref="resume", cascade="all, delete-orphan")


class AIReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resume.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False)   # ats / cover / interview
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def get_my_resume(rid):
    # sirf apna resume mil sakta hai (security)
    return Resume.query.filter_by(id=rid, user_id=current_user.id).first_or_404()


# ---------- AUTH ----------
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Please fill all fields. Password must be at least 6 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("This email is already registered.", "error")
        else:
            u = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(u)
            db.session.commit()
            login_user(u)
            return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password_hash, request.form.get("password", "")):
            login_user(u)
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------- RESUME CRUD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    resumes = (Resume.query.filter_by(user_id=current_user.id)
               .order_by(Resume.updated_at.desc()).all())
    return render_template("dashboard.html", resumes=resumes)


@app.route("/resume/new", methods=["GET", "POST"])
@app.route("/resume/<int:rid>/edit", methods=["GET", "POST"])
@login_required
def editor(rid=None):
    r = get_my_resume(rid) if rid else None
    if request.method == "POST":
        data = {f: request.form.get(f, "").strip() for f in FIELDS}
        if data["template"] not in TEMPLATES:
            data["template"] = "classic"
        if not data["title"]:
            data["title"] = "Untitled Resume"
        if r is None:
            r = Resume(user_id=current_user.id, **data)
            db.session.add(r)
        else:
            for k, v in data.items():
                setattr(r, k, v)
        db.session.commit()
        return redirect(url_for("view_resume", rid=r.id))
    return render_template("editor.html", r=r)


@app.route("/resume/<int:rid>")
@login_required
def view_resume(rid):
    return render_template("resume.html", r=get_my_resume(rid))


@app.route("/resume/<int:rid>/delete", methods=["POST"])
@login_required
def delete_resume(rid):
    db.session.delete(get_my_resume(rid))
    db.session.commit()
    flash("Resume deleted.", "ok")
    return redirect(url_for("dashboard"))


# ---------- AI FEATURES ----------
KINDS = {
    "ats": ai_service.ats_check,
    "cover": ai_service.cover_letter,
    "interview": ai_service.interview_questions,
}


@app.route("/resume/<int:rid>/ai/<kind>", methods=["POST"])
@login_required
def ai_action(rid, kind):
    r = get_my_resume(rid)
    if kind != "improve" and kind not in KINDS:
        abort(404)
    try:
        if kind == "improve":
            r.summary = ai_service.improve_summary(r)
            db.session.commit()
            flash("AI summary added!", "ok")
            return redirect(url_for("view_resume", rid=rid))
        jd = request.form.get("jd", "").strip()
        if not jd:
            flash("Please paste the job description first.", "error")
            return redirect(url_for("insights", rid=rid))
        content = KINDS[kind](r, jd)
        db.session.add(AIReport(resume_id=r.id, kind=kind, content=content))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"AI error: {e}", "error")
    return redirect(url_for("insights", rid=rid))


@app.route("/resume/<int:rid>/insights")
@login_required
def insights(rid):
    r = get_my_resume(rid)

    def latest(kind):
        return (AIReport.query.filter_by(resume_id=r.id, kind=kind)
                .order_by(AIReport.id.desc()).first())

    ats = latest("ats")
    try:
        ats_data = json.loads(ats.content) if ats else None
    except ValueError:
        ats_data = None
    return render_template("insights.html", r=r, ats=ats_data,
                           cover=latest("cover"), interview=latest("interview"))


# ---------- REST API ----------
@app.route("/api/resumes")
@login_required
def api_resumes():
    return jsonify([{"id": r.id, "title": r.title, "template": r.template,
                     "updated": r.updated_at.isoformat()} for r in current_user.resumes])


with app.app_context():
    db.create_all()   # tables auto ban jayengi

if __name__ == "__main__":
    app.run(debug=True)