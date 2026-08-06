"""
backend/scoring_engine.py
=========================
LLM-based compliance scoring engine.
Uses the ComplianceRAG system (Pinecone) to retrieve relevant policy rules
before scoring each chunk / email, then persists results to SQLite via database.py.
"""

import os
import sys
import uuid
import logging
import json
import pandas as pd
from groq import Groq
from rag_compliance import ComplianceRAG
from database import (
    save_audit_rows,
    create_audit_session,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Lazy-loaded RAG system — initialised on first use to reduce startup memory
_rag_system = None


def get_rag_system():
    """Return the shared ComplianceRAG instance, initialising it on first call."""
    global _rag_system
    if _rag_system is None:
        logger.info("Initialising ComplianceRAG system (first use)...")
        _rag_system = ComplianceRAG()
    return _rag_system


# ─────────────────────────────────────────────
# Chunk Scoring (Audio calls)
# ─────────────────────────────────────────────

def score_chunk(chunk_text: str) -> dict:
    """Score a single conversation chunk using the LLM + RAG rules."""
    relevant_rules = get_rag_system().get_rules_for_context(chunk_text)

    prompt = f"""
    Evaluate this chunk based on these specific rules:
    {relevant_rules}

    Conversation:
    {chunk_text}

    Return JSON ONLY:
    {{
      "empathy": 1-100,
      "professionalism": 1-100,
      "compliance": "Pass/Fail/Warn",
      "reason": "Explain violation if any",
      "violations": ["List specific policy violations"],
      "suggestions": ["List specific improvement suggestions"]
    }}
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


# ─────────────────────────────────────────────
# Email Scoring
# ─────────────────────────────────────────────

def score_email(
    email_text: str,
    agent_name: str = "Unknown Agent",
    filename: str = None,
    organization: str = "Default",
    **kwargs,
) -> dict:
    """
    Score an email, redact PII, persist results to the database,
    and return the LLM result dict.
    """
    from datetime import datetime

    if filename is None:
        filename = f"Email_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.debug("score_email called — agent=%s filename=%s", agent_name, filename)

    # 1. RAG-grounded LLM scoring
    relevant_rules = get_rag_system().get_rules_for_context(email_text)

    prompt = f"""
    Evaluate this customer service email based on these specific rules:
    {relevant_rules}

    Email Content:
    {email_text}

    Return JSON ONLY:
    {{
      "empathy": 1-100,
      "professionalism": 1-100,
      "compliance": "Pass/Fail/Warn",
      "reason": "Explain violation if any",
      "violations": ["List specific policy violations"],
      "suggestions": ["List specific improvement suggestions"]
    }}
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)

    # 2. Redact PII from email text
    from redaction import redact_pii
    masking_result = redact_pii(email_text)

    # 3. Create an audit session record
    session_uuid = str(uuid.uuid4())
    session_id = create_audit_session(
        session_uuid=session_uuid,
        agent_name=agent_name,
        source="Email",
        filename=filename,
        organization=organization,
    )

    # 4. Build DB rows — one EMAIL row + one FINAL row for dashboard consistency
    base_row = {
        "session_id": session_id,
        "agent": agent_name,
        "empathy": result.get("empathy"),
        "professionalism": result.get("professionalism"),
        "compliance": result.get("compliance"),
        "reason": result.get("reason"),
        "violations": "|".join(result.get("violations", [])),
        "suggestions": "|".join(result.get("suggestions", [])),
        "evaluation": json.dumps(result),
        "masking_score": masking_result.get("masking_score", 100),
        "masking_analysis": masking_result.get("analysis", ""),
        "source": "Email",
        "transcript": masking_result.get("redacted_text", ""),
        "filename": filename,
        "organization": organization,
    }

    email_row = {**base_row, "chunk": "EMAIL"}
    final_row = {**base_row, "chunk": "FINAL"}

    save_audit_rows([email_row, final_row], session_id=session_id)
    logger.info("Email audit saved to DB — session_uuid=%s", session_uuid)

    return result


# ─────────────────────────────────────────────
# Full Audio Call Audit Pipeline
# ─────────────────────────────────────────────

def run_average_audit(
    file_path: str,
    agent_name: str = "Unknown Agent",
    masking_score: int = 100,
    masking_analysis: str = "",
    filename: str = None,
    redacted_transcript: str = None,
    organization: str = "Default",
):
    """
    Read a labeled dialogue file, score it in 5-turn chunks,
    compute averages, and persist everything to the database.
    """
    if filename is None:
        filename = os.path.basename(file_path)

    if not os.path.isabs(file_path):
        file_path = os.path.join(PROJECT_ROOT, file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [
            line.strip()
            for line in f.readlines()
            if line.strip().startswith(("Agent:", "Customer:"))
        ]

    if redacted_transcript is None:
        redacted_transcript = "\n".join(lines)

    # 1. Score each 5-turn chunk
    chunk_results = []
    for i in range(0, len(lines), 5):
        chunk = "".join(lines[i : i + 5])
        chunk_results.append(score_chunk(chunk))

    df = pd.DataFrame(chunk_results)

    # 2. Compute averages
    final_empathy = df["empathy"].mean()
    final_professionalism = df["professionalism"].mean()
    avg_score = (final_empathy + final_professionalism) / 2
    overall_compliance = (
        "PASS" if avg_score >= 80 else "WARN" if avg_score >= 60 else "FAIL"
    )

    # 3. Aggregate violations / suggestions
    def _join_col(series):
        items = []
        for val in series:
            if isinstance(val, list):
                items.extend(val)
            elif pd.notna(val):
                items.extend([v.strip() for v in str(val).split("|")])
        return list(set(v for v in items if v))

    all_violations = _join_col(df.get("violations", pd.Series(dtype=str)))
    all_suggestions = _join_col(df.get("suggestions", pd.Series(dtype=str)))

    # 4. Create audit session record
    session_uuid = str(uuid.uuid4())
    session_id = create_audit_session(
        session_uuid=session_uuid,
        agent_name=agent_name,
        source="Audio",
        filename=filename,
        organization=organization,
    )

    # 5. Build rows to save
    common = dict(
        session_id=session_id,
        agent=agent_name,
        masking_score=masking_score,
        masking_analysis=masking_analysis,
        source="Audio",
        transcript=redacted_transcript,
        filename=filename,
        organization=organization,
    )

    rows_to_save = []
    for idx, row in df.iterrows():
        violations_str = (
            " | ".join(row["violations"])
            if isinstance(row.get("violations"), list)
            else str(row.get("violations", ""))
        )
        suggestions_str = (
            " | ".join(row["suggestions"])
            if isinstance(row.get("suggestions"), list)
            else str(row.get("suggestions", ""))
        )
        rows_to_save.append({
            **common,
            "chunk": str(idx + 1),
            "empathy": row.get("empathy"),
            "professionalism": row.get("professionalism"),
            "compliance": row.get("compliance"),
            "reason": row.get("reason"),
            "violations": violations_str,
            "suggestions": suggestions_str,
            "evaluation": None,
        })

    # FINAL summary row
    rows_to_save.append({
        **common,
        "chunk": "FINAL",
        "empathy": final_empathy,
        "professionalism": final_professionalism,
        "compliance": overall_compliance,
        "reason": "Final average scores",
        "violations": " | ".join(all_violations) if all_violations else "None",
        "suggestions": " | ".join(all_suggestions) if all_suggestions else "None",
        "evaluation": None,
    })

    save_audit_rows(rows_to_save, session_id=session_id)

    logger.info("--- FINAL AUDIT RESULTS FOR %s ---", agent_name)
    logger.info("Final Empathy:         %.2f", final_empathy)
    logger.info("Final Professionalism: %.2f", final_professionalism)
    logger.info("Overall Compliance:    %s", overall_compliance)
    logger.info("Saved to DB — session_uuid=%s", session_uuid)

    # Return a DataFrame in the same shape as before for backward compatibility
    return df


# ─────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys

    agent = _sys.argv[2] if len(_sys.argv) > 2 else "Sample Agent"
    target_file = os.path.join(PROJECT_ROOT, "data", "3_labeled_dialogue.txt")

    if os.path.exists(target_file):
        run_average_audit(target_file, agent)
    else:
        print(
            f"Error: {target_file} not found. "
            "Please run the full pipeline or process an email/audio first."
        )
