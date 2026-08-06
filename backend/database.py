"""
backend/database.py
===================
Dual-mode database layer:
  - Cloud Run (production): PostgreSQL via DATABASE_URL env var
  - Local dev (no DATABASE_URL set): SQLite fallback for zero-config testing

Production DATABASE_URL formats:
  Cloud SQL (Unix socket): postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance
  Cloud SQL (public IP):   postgresql://user:pass@PUBLIC_IP:5432/dbname
  Supabase / Neon / Railway: postgresql://user:pass@host:5432/dbname?sslmode=require
"""

import os
import sqlite3
import logging
import pandas as pd
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SQLITE_PATH  = os.path.join(PROJECT_ROOT, "data", "audit_system.db")
_USE_POSTGRES = bool(os.environ.get("DATABASE_URL"))

# SQL placeholder style: %s for psycopg2, ? for sqlite3
PH = "%s" if _USE_POSTGRES else "?"


# ─────────────────────────────────────────────
# Connection Management
# ─────────────────────────────────────────────

def get_connection():
    """
    Returns a live DB connection.
    - DATABASE_URL set  → psycopg2 (PostgreSQL) — used on Cloud Run
    - DATABASE_URL unset → sqlite3 (WAL mode) — used locally
    """
    if _USE_POSTGRES:
        import psycopg2, psycopg2.extras
        url = os.environ["DATABASE_URL"]
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        logger.debug("No DATABASE_URL — falling back to SQLite for local development.")
        os.makedirs(os.path.dirname(_SQLITE_PATH), exist_ok=True)
        conn = sqlite3.connect(_SQLITE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn


@contextmanager
def get_db():
    """Context manager: auto-commits on success, rolls back on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _exec(conn, sql: str, params=()):
    """
    Execute a SQL statement on either a psycopg2 or sqlite3 connection.
    Returns the cursor so callers can call .fetchone() / .fetchall().
    """
    if _USE_POSTGRES:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    else:
        return conn.execute(sql, params)


def _fetchone(conn, sql: str, params=()):
    cur = _exec(conn, sql, params)
    row = cur.fetchone()
    return dict(row) if row else None


def _fetchall(conn, sql: str, params=()):
    cur = _exec(conn, sql, params)
    return [dict(r) for r in cur.fetchall()]


# ─────────────────────────────────────────────
# Schema Initialisation
# ─────────────────────────────────────────────

def init_db():
    """
    Create all tables if they don't exist.
    Uses SERIAL (PostgreSQL) or INTEGER PRIMARY KEY AUTOINCREMENT (SQLite).
    Safe to call on every startup.
    """
    if _USE_POSTGRES:
        schema = """
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                organization  TEXT NOT NULL DEFAULT 'Default',
                created_at    TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS audit_sessions (
                id           SERIAL PRIMARY KEY,
                session_uuid TEXT UNIQUE NOT NULL,
                agent_name   TEXT NOT NULL,
                source       TEXT NOT NULL CHECK(source IN ('Audio', 'Email')),
                filename     TEXT,
                organization TEXT NOT NULL DEFAULT 'Default',
                created_at   TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS audit_results (
                id               SERIAL PRIMARY KEY,
                session_id       INTEGER REFERENCES audit_sessions(id) ON DELETE CASCADE,
                chunk            TEXT NOT NULL,
                empathy          REAL,
                professionalism  REAL,
                compliance       TEXT,
                reason           TEXT,
                violations       TEXT,
                suggestions      TEXT,
                evaluation       TEXT,
                agent            TEXT,
                masking_score    INTEGER DEFAULT 100,
                masking_analysis TEXT,
                source           TEXT,
                transcript       TEXT,
                filename         TEXT,
                organization     TEXT DEFAULT 'Default',
                created_at       TIMESTAMPTZ DEFAULT NOW()
            );
        """
    else:
        schema = """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                organization  TEXT NOT NULL DEFAULT 'Default',
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS audit_sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_uuid TEXT UNIQUE NOT NULL,
                agent_name   TEXT NOT NULL,
                source       TEXT NOT NULL CHECK(source IN ('Audio', 'Email')),
                filename     TEXT,
                organization TEXT NOT NULL DEFAULT 'Default',
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS audit_results (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       INTEGER REFERENCES audit_sessions(id) ON DELETE CASCADE,
                chunk            TEXT NOT NULL,
                empathy          REAL,
                professionalism  REAL,
                compliance       TEXT,
                reason           TEXT,
                violations       TEXT,
                suggestions      TEXT,
                evaluation       TEXT,
                agent            TEXT,
                masking_score    INTEGER DEFAULT 100,
                masking_analysis TEXT,
                source           TEXT,
                transcript       TEXT,
                filename         TEXT,
                organization     TEXT DEFAULT 'Default',
                created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """

    with get_db() as conn:
        if _USE_POSTGRES:
            with conn.cursor() as cur:
                cur.execute(schema)
        else:
            conn.executescript(schema)

    engine = "PostgreSQL" if _USE_POSTGRES else "SQLite"
    logger.info("Database initialised (%s).", engine)


# ─────────────────────────────────────────────
# User CRUD
# ─────────────────────────────────────────────

def _sha256(password: str) -> str:
    """Legacy SHA-256 hash — for migration compatibility only."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(username: str, password: str, organization: str):
    """Returns (True, msg) on success, (False, msg) on failure."""
    try:
        with get_db() as conn:
            _exec(
                conn,
                f"INSERT INTO users (username, password_hash, organization) VALUES ({PH}, {PH}, {PH})",
                (username, generate_password_hash(password), organization)
            )
        logger.info("User '%s' created.", username)
        return True, "Account created successfully"
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return False, "Username already exists"
        logger.error("create_user error: %s", e)
        return False, str(e)


def authenticate_user(username: str, password: str, env_user: str, env_pass: str):
    """
    Verify credentials. Returns (True, organization) or (False, None).
    Always checks env-var admin credentials first as a fallback override.
    """
    if username == env_user and password == env_pass:
        return True, "Default"

    with get_db() as conn:
        row = _fetchone(
            conn,
            f"SELECT password_hash, organization FROM users WHERE username = {PH}",
            (username,)
        )

    if row is None:
        return False, None

    stored_hash = row["password_hash"]
    org = row["organization"]

    if stored_hash.startswith(("pbkdf2:", "scrypt:")):
        if check_password_hash(stored_hash, password):
            return True, org
    else:
        # Legacy SHA-256 — auto-upgrade on successful login
        if stored_hash == _sha256(password):
            logger.info("Upgrading password hash for '%s'.", username)
            with get_db() as conn:
                _exec(
                    conn,
                    f"UPDATE users SET password_hash = {PH} WHERE username = {PH}",
                    (generate_password_hash(password), username)
                )
            return True, org

    return False, None


def get_all_usernames():
    """Return list of all registered usernames."""
    with get_db() as conn:
        rows = _fetchall(conn, "SELECT username FROM users")
    return [r["username"] for r in rows]


# ─────────────────────────────────────────────
# Audit Session CRUD
# ─────────────────────────────────────────────

def create_audit_session(session_uuid: str, agent_name: str, source: str,
                         filename: str, organization: str) -> int:
    """Insert a new audit session and return its integer ID."""
    with get_db() as conn:
        if _USE_POSTGRES:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO audit_sessions (session_uuid, agent_name, source, filename, organization)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (session_uuid, agent_name, source, filename, organization)
            )
            return cur.fetchone()["id"]
        else:
            cur = conn.execute(
                """INSERT INTO audit_sessions (session_uuid, agent_name, source, filename, organization)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_uuid, agent_name, source, filename, organization)
            )
            return cur.lastrowid


# ─────────────────────────────────────────────
# Audit Results CRUD
# ─────────────────────────────────────────────

def save_audit_rows(rows: list, session_id: int = None):
    """Bulk-insert audit result dicts into the DB."""
    if _USE_POSTGRES:
        sql = """
            INSERT INTO audit_results
                (session_id, chunk, empathy, professionalism, compliance, reason,
                 violations, suggestions, evaluation, agent, masking_score,
                 masking_analysis, source, transcript, filename, organization)
            VALUES
                (%(session_id)s, %(chunk)s, %(empathy)s, %(professionalism)s,
                 %(compliance)s, %(reason)s, %(violations)s, %(suggestions)s,
                 %(evaluation)s, %(agent)s, %(masking_score)s,
                 %(masking_analysis)s, %(source)s, %(transcript)s,
                 %(filename)s, %(organization)s)
        """
        with get_db() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    row.setdefault("session_id", session_id)
                    cur.execute(sql, row)
    else:
        sql = """
            INSERT INTO audit_results
                (session_id, chunk, empathy, professionalism, compliance, reason,
                 violations, suggestions, evaluation, agent, masking_score,
                 masking_analysis, source, transcript, filename, organization)
            VALUES
                (:session_id, :chunk, :empathy, :professionalism, :compliance, :reason,
                 :violations, :suggestions, :evaluation, :agent, :masking_score,
                 :masking_analysis, :source, :transcript, :filename, :organization)
        """
        with get_db() as conn:
            for row in rows:
                row.setdefault("session_id", session_id)
                conn.execute(sql, row)

    logger.info("Saved %d audit rows to DB (session_id=%s).", len(rows), session_id)


def get_audit_dataframe(organization: str = None) -> pd.DataFrame:
    """
    Return audit_results as a DataFrame with legacy CSV column name aliases.
    Works identically on both PostgreSQL and SQLite.
    """
    ph = PH
    sql = """
        SELECT
            chunk            AS "Chunk",
            empathy,
            professionalism,
            compliance,
            reason,
            violations,
            suggestions,
            evaluation,
            agent            AS "Agent",
            masking_score,
            masking_analysis,
            source           AS "Source",
            transcript       AS "Transcript",
            filename         AS "Filename",
            organization     AS "Organization",
            created_at
        FROM audit_results
    """
    params = []
    if organization:
        sql += f" WHERE organization = {ph}"
        params.append(organization)
    sql += " ORDER BY id ASC"

    with get_db() as conn:
        df = pd.read_sql_query(sql, conn, params=params)

    df["empathy"]         = pd.to_numeric(df["empathy"], errors="coerce")
    df["professionalism"] = pd.to_numeric(df["professionalism"], errors="coerce")
    df["masking_score"]   = pd.to_numeric(df["masking_score"], errors="coerce").fillna(100)
    df["Organization"]    = df["Organization"].fillna("Default")
    df = df.dropna(subset=["empathy", "professionalism"])
    return df


# ─────────────────────────────────────────────
# Health / Meta
# ─────────────────────────────────────────────

def get_db_stats() -> dict:
    """Return live stats for the /api/db-status endpoint."""
    with get_db() as conn:
        total_audits   = _fetchone(conn, "SELECT COUNT(*) AS c FROM audit_results")["c"]
        total_users    = _fetchone(conn, "SELECT COUNT(*) AS c FROM users")["c"]
        total_sessions = _fetchone(conn, "SELECT COUNT(*) AS c FROM audit_sessions")["c"]
        latest_row     = _fetchone(conn, "SELECT MAX(created_at) AS t FROM audit_results")
        latest         = latest_row["t"] if latest_row else None

    engine = "PostgreSQL (Cloud Run)" if _USE_POSTGRES else "SQLite (local dev)"
    return {
        "database": engine,
        "tables": ["users", "audit_sessions", "audit_results"],
        "total_audit_rows": total_audits,
        "total_users": total_users,
        "total_sessions": total_sessions,
        "latest_audit": str(latest) if latest else "No audits yet",
        "status": "healthy",
    }
