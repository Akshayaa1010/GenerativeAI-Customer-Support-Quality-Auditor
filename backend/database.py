"""
Database access. Two tables:

    audits         one row per audited call (status, scores, transcript)
    rule_findings  one row per policy rule checked in an audit

PostgreSQL is used when DATABASE_URL is set (production). Otherwise a local
SQLite file is used, so the app runs with zero setup on a laptop.
SQL is written once with "?" placeholders and converted for PostgreSQL.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from backend import config

USE_POSTGRES = bool(config.DATABASE_URL)

ID_COLUMN = "SERIAL PRIMARY KEY" if USE_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS audits (
    id                 {ID_COLUMN},
    agent_name         TEXT NOT NULL,
    filename           TEXT,
    status             TEXT NOT NULL,          -- processing | completed | failed
    progress_message   TEXT,
    error              TEXT,
    transcript         TEXT,                   -- redacted, speaker-labelled
    pii_summary        TEXT,
    empathy            REAL,
    professionalism    REAL,
    compliance_score   REAL,
    protocol_score     REAL,
    soft_skills_score  REAL,
    overall_score      REAL,
    outcome            TEXT,                   -- PASS | WARN | FAIL
    summary            TEXT,
    suggestions        TEXT,                   -- JSON list of strings
    policy_version     TEXT,
    created_at         TEXT NOT NULL,
    completed_at       TEXT
);

CREATE TABLE IF NOT EXISTS rule_findings (
    id              {ID_COLUMN},
    audit_id        INTEGER NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    rule_id         TEXT NOT NULL,
    rule_title      TEXT NOT NULL,
    zero_tolerance  INTEGER NOT NULL,          -- 1 or 0
    verdict         TEXT NOT NULL,             -- pass | fail | not_applicable
    evidence        TEXT,
    explanation     TEXT
);

CREATE INDEX IF NOT EXISTS idx_audits_agent ON audits(agent_name);
CREATE INDEX IF NOT EXISTS idx_findings_audit ON rule_findings(audit_id);
"""


# ----- Connection helpers -------------------------------------------------

def _connect():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        return psycopg2.connect(config.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

    os.makedirs(os.path.dirname(config.SQLITE_PATH), exist_ok=True)
    connection = sqlite3.connect(config.SQLITE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def _transaction():
    """Open a connection, commit if the block succeeds, roll back if it raises."""
    connection = _connect()
    try:
        yield connection.cursor()
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _sql(query: str) -> str:
    return query.replace("?", "%s") if USE_POSTGRES else query


def _fetch_all(query: str, params=()) -> list[dict]:
    with _transaction() as cursor:
        cursor.execute(_sql(query), params)
        return [dict(row) for row in cursor.fetchall()]


def _fetch_one(query: str, params=()) -> dict | None:
    rows = _fetch_all(query, params)
    return rows[0] if rows else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db():
    with _transaction() as cursor:
        if USE_POSTGRES:
            cursor.execute(SCHEMA)
        else:
            cursor.connection.executescript(SCHEMA)


# ----- Writing audits -----------------------------------------------------

def create_audit(agent_name: str, filename: str) -> int:
    with _transaction() as cursor:
        cursor.execute(
            _sql("INSERT INTO audits (agent_name, filename, status, progress_message, created_at) "
                 "VALUES (?, ?, 'processing', 'Queued', ?) RETURNING id"),
            (agent_name, filename, _now()),
        )
        return cursor.fetchone()["id"]


def update_progress(audit_id: int, message: str):
    with _transaction() as cursor:
        cursor.execute(_sql("UPDATE audits SET progress_message = ? WHERE id = ?"), (message, audit_id))


def mark_failed(audit_id: int, error: str):
    with _transaction() as cursor:
        cursor.execute(
            _sql("UPDATE audits SET status = 'failed', error = ?, completed_at = ? WHERE id = ?"),
            (error, _now(), audit_id),
        )


def save_completed_audit(audit_id: int, transcript: str, pii_summary: str, scores, policy_version: str):
    """Store the scores and every rule finding for an audit in one transaction."""
    with _transaction() as cursor:
        cursor.execute(
            _sql("""UPDATE audits SET
                        status = 'completed', progress_message = 'Completed', error = NULL,
                        transcript = ?, pii_summary = ?,
                        empathy = ?, professionalism = ?,
                        compliance_score = ?, protocol_score = ?, soft_skills_score = ?,
                        overall_score = ?, outcome = ?, summary = ?, suggestions = ?,
                        policy_version = ?, completed_at = ?
                    WHERE id = ?"""),
            (transcript, pii_summary,
             scores.empathy, scores.professionalism,
             scores.compliance_score, scores.protocol_score, scores.soft_skills_score,
             scores.overall_score, scores.outcome, scores.summary, json.dumps(scores.suggestions),
             policy_version, _now(), audit_id),
        )
        for finding in scores.findings:
            cursor.execute(
                _sql("INSERT INTO rule_findings (audit_id, rule_id, rule_title, zero_tolerance, "
                     "verdict, evidence, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)"),
                (audit_id, finding.rule_id, finding.rule_title, int(finding.zero_tolerance),
                 finding.verdict, finding.evidence, finding.explanation),
            )


def fail_stale_audits(older_than_minutes: int = 30):
    """Audits stuck in 'processing' (e.g. the server restarted mid-audit) are marked failed."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)).isoformat(timespec="seconds")
    with _transaction() as cursor:
        cursor.execute(
            _sql("UPDATE audits SET status = 'failed', error = 'Processing was interrupted. Please upload the call again.' "
                 "WHERE status = 'processing' AND created_at < ?"),
            (cutoff,),
        )


# ----- Reading audits -----------------------------------------------------

AUDIT_LIST_COLUMNS = """id, agent_name, filename, status, outcome, overall_score,
                        empathy, professionalism, created_at"""


def get_audit(audit_id: int) -> dict | None:
    audit = _fetch_one("SELECT * FROM audits WHERE id = ?", (audit_id,))
    if audit is None:
        return None
    audit["suggestions"] = json.loads(audit["suggestions"] or "[]")
    audit["findings"] = _fetch_all(
        "SELECT rule_id, rule_title, zero_tolerance, verdict, evidence, explanation "
        "FROM rule_findings WHERE audit_id = ? ORDER BY id",
        (audit_id,),
    )
    return audit


def get_audit_status(audit_id: int) -> dict | None:
    return _fetch_one("SELECT id, status, progress_message, error FROM audits WHERE id = ?", (audit_id,))


def list_audits(agent_name: str | None = None, limit: int = 20) -> list[dict]:
    if agent_name:
        return _fetch_all(f"SELECT {AUDIT_LIST_COLUMNS} FROM audits WHERE agent_name = ? "
                          "ORDER BY id DESC LIMIT ?", (agent_name, limit))
    return _fetch_all(f"SELECT {AUDIT_LIST_COLUMNS} FROM audits ORDER BY id DESC LIMIT ?", (limit,))


# ----- Dashboard statistics (completed audits only) -----------------------

AGENT_STATS_COLUMNS = """
    COUNT(*)                                              AS audit_count,
    AVG(overall_score)                                    AS avg_overall,
    AVG(empathy)                                          AS avg_empathy,
    AVG(professionalism)                                  AS avg_professionalism,
    100.0 * SUM(CASE WHEN outcome = 'PASS' THEN 1 ELSE 0 END) / COUNT(*) AS pass_rate,
    SUM(CASE WHEN outcome = 'FAIL' THEN 1 ELSE 0 END)     AS fail_count
"""


def team_summary() -> dict:
    row = _fetch_one(f"SELECT {AGENT_STATS_COLUMNS}, COUNT(DISTINCT agent_name) AS agent_count "
                     "FROM audits WHERE status = 'completed'")
    return row if row and row["audit_count"] else {
        "audit_count": 0, "agent_count": 0, "avg_overall": None, "avg_empathy": None,
        "avg_professionalism": None, "pass_rate": None, "fail_count": 0,
    }


def agent_leaderboard() -> list[dict]:
    return _fetch_all(f"SELECT agent_name, {AGENT_STATS_COLUMNS} FROM audits WHERE status = 'completed' "
                      "GROUP BY agent_name ORDER BY avg_overall DESC")


def agent_summary(agent_name: str) -> dict | None:
    return _fetch_one(f"SELECT agent_name, {AGENT_STATS_COLUMNS} FROM audits "
                      "WHERE status = 'completed' AND agent_name = ? GROUP BY agent_name", (agent_name,))


def top_violations(agent_name: str | None = None, limit: int = 5) -> list[dict]:
    """Rules broken most often, across the team or for one agent."""
    agent_filter = "AND a.agent_name = ?" if agent_name else ""
    params = (agent_name, limit) if agent_name else (limit,)
    return _fetch_all(
        f"""SELECT f.rule_id, f.rule_title, MAX(f.zero_tolerance) AS zero_tolerance, COUNT(*) AS count
            FROM rule_findings f JOIN audits a ON a.id = f.audit_id
            WHERE f.verdict = 'fail' AND a.status = 'completed' {agent_filter}
            GROUP BY f.rule_id, f.rule_title
            ORDER BY count DESC, f.rule_id
            LIMIT ?""",
        params,
    )


def recent_suggestions(limit_audits: int = 50) -> list[str]:
    rows = _fetch_all("SELECT suggestions FROM audits WHERE status = 'completed' "
                      "ORDER BY id DESC LIMIT ?", (limit_audits,))
    unique = {}
    for row in rows:
        for suggestion in json.loads(row["suggestions"] or "[]"):
            unique.setdefault(suggestion.lower(), suggestion)
    return list(unique.values())


def export_rows() -> list[dict]:
    return _fetch_all(
        """SELECT id, agent_name, filename, outcome, overall_score, compliance_score, protocol_score,
                  soft_skills_score, empathy, professionalism, summary, pii_summary, created_at
           FROM audits WHERE status = 'completed' ORDER BY id"""
    )
