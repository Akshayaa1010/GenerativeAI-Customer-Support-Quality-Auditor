"""
Call Quality Auditor — admin dashboard.

The admin uploads recorded support calls, the AI scores each call against
the company policy, and the dashboard shows how every employee is doing.

Routes
  /login, /logout, /dashboard           pages
  POST /api/audits                      upload a call recording to audit
  GET  /api/audits/<id>/status          progress of a running audit
  GET  /api/audits/<id>                 full result of one audit
  GET  /api/overview                    team-wide numbers for the home page
  GET  /api/agents/<name>               one employee's numbers and audits
  POST /api/coaching-roadmap            AI training plan from common mistakes
  GET  /api/export.csv                  all completed audits as CSV
  GET  /healthz                         health check for Cloud Run
"""

import csv
import hmac
import io
import logging
import os
import secrets
import sys
import uuid
from functools import wraps

from flask import Flask, jsonify, make_response, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from backend import config, database
from backend.pipeline import start_audit_in_background
from backend.scoring import generate_coaching_roadmap

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

LANGUAGES = {"auto": None, "en": "en", "hi": "hi", "ta": "ta", "es": "es", "fr": "fr"}


def create_app() -> Flask:
    if config.IS_PRODUCTION and not config.DATABASE_URL:
        # The container's disk is wiped on every restart, so SQLite would lose all audits.
        raise RuntimeError("DATABASE_URL must be set in production (e.g. a Neon Postgres URL).")

    app = Flask(__name__, template_folder="frontend/templates", static_folder="frontend/static")
    app.secret_key = _load_secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.IS_PRODUCTION,
        MAX_CONTENT_LENGTH=config.MAX_UPLOAD_BYTES,
    )
    database.init_db()
    database.fail_stale_audits()
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    return app


def _load_secret_key() -> str:
    if config.FLASK_SECRET_KEY:
        return config.FLASK_SECRET_KEY
    if config.IS_PRODUCTION:
        raise RuntimeError("FLASK_SECRET_KEY must be set in production.")
    logger.warning("FLASK_SECRET_KEY is not set; using a temporary key (you will be logged out on restart).")
    return secrets.token_hex(32)


app = create_app()


# ================= Authentication =================

def is_valid_admin(username: str, password: str) -> bool:
    if not (config.ADMIN_USERNAME and config.ADMIN_PASSWORD):
        return False
    # compare_digest takes the same time whether or not the values match.
    return (hmac.compare_digest(username.encode(), config.ADMIN_USERNAME.encode())
            and hmac.compare_digest(password.encode(), config.ADMIN_PASSWORD.encode()))


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not logged in"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("is_admin") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if not (config.ADMIN_USERNAME and config.ADMIN_PASSWORD):
        error = "Admin account is not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD."
    elif request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if is_valid_admin(username, password):
            session.clear()
            session["is_admin"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        error = "Invalid username or password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session["username"])


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


# ================= Auditing calls =================

def _has_allowed_extension(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_AUDIO_EXTENSIONS


@app.route("/api/audits", methods=["POST"])
@login_required
def upload_call():
    audio = request.files.get("audio")
    agent_name = request.form.get("agent_name", "").strip()
    language = LANGUAGES.get(request.form.get("language", "auto"))

    if not agent_name:
        return jsonify({"error": "Enter the employee's name"}), 400
    if audio is None or not audio.filename:
        return jsonify({"error": "Choose an audio file"}), 400
    if not _has_allowed_extension(audio.filename):
        allowed = ", ".join(sorted(config.ALLOWED_AUDIO_EXTENSIONS))
        return jsonify({"error": f"Unsupported file type. Allowed: {allowed}"}), 400
    if not config.GROQ_API_KEY:
        return jsonify({"error": "GROQ_API_KEY is not configured on the server"}), 503

    filename = secure_filename(audio.filename)
    audio_path = os.path.join(config.UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
    audio.save(audio_path)

    audit_id = database.create_audit(agent_name, filename)
    start_audit_in_background(audit_id, audio_path, language)
    return jsonify({"audit_id": audit_id}), 202


@app.route("/api/audits/<int:audit_id>/status")
@login_required
def audit_status(audit_id):
    status = database.get_audit_status(audit_id)
    if status is None:
        return jsonify({"error": "Audit not found"}), 404
    return jsonify(status)


@app.route("/api/audits/<int:audit_id>")
@login_required
def audit_detail(audit_id):
    audit = database.get_audit(audit_id)
    if audit is None:
        return jsonify({"error": "Audit not found"}), 404
    return jsonify(audit)


# ================= Dashboard data =================

@app.route("/api/overview")
@login_required
def overview():
    return jsonify({
        "team": database.team_summary(),
        "agents": database.agent_leaderboard(),
        "top_violations": database.top_violations(),
        "recent_audits": database.list_audits(limit=10),
    })


@app.route("/api/agents/<path:agent_name>")
@login_required
def agent_detail(agent_name):
    return jsonify({
        "summary": database.agent_summary(agent_name),
        "top_violations": database.top_violations(agent_name),
        "audits": database.list_audits(agent_name, limit=50),
    })


@app.route("/api/coaching-roadmap", methods=["POST"])
@login_required
def coaching_roadmap():
    violations = database.top_violations(limit=10)
    suggestions = database.recent_suggestions()
    if not violations and not suggestions:
        return jsonify({"error": "Audit a few calls first — there is nothing to build a plan from yet."}), 400
    try:
        return jsonify({"roadmap": generate_coaching_roadmap(violations, suggestions)})
    except Exception as error:
        logger.exception("Coaching roadmap failed")
        return jsonify({"error": f"Could not generate the roadmap: {error}"}), 502


@app.route("/api/export.csv")
@login_required
def export_csv():
    rows = database.export_rows()
    buffer = io.StringIO()
    columns = ["id", "agent_name", "filename", "outcome", "overall_score", "compliance_score",
               "protocol_score", "soft_skills_score", "empathy", "professionalism",
               "summary", "pii_summary", "created_at"]
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = "attachment; filename=call_audits.csv"
    return response


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"error": f"File is too large (max {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    app.run(host="127.0.0.1", port=port, debug=False)
