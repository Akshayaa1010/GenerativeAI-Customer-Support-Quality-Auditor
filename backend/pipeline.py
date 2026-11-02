"""
The audit pipeline for one uploaded call:

    audio --> transcribe --> redact PII --> label speakers --> find relevant
    policy rules (RAG) --> AI evaluation --> save scores

Progress is written to the database at each step, so the dashboard can show
it no matter which server instance handles the status request.
"""

import logging
import os
import threading

from backend import database, llm
from backend.policy import policy_version
from backend.rag import get_retriever
from backend.redaction import redact_pii
from backend.scoring import evaluate_call, label_speakers

logger = logging.getLogger(__name__)


def start_audit_in_background(audit_id: int, audio_path: str, language: str | None):
    """Run the audit on a background thread so the upload request returns immediately."""
    thread = threading.Thread(target=run_audit, args=(audit_id, audio_path, language), daemon=True)
    thread.start()


def run_audit(audit_id: int, audio_path: str, language: str | None):
    try:
        database.update_progress(audit_id, "Transcribing audio")
        raw_transcript = llm.transcribe(audio_path, language)
        if not raw_transcript:
            raise ValueError("No speech was detected in the audio file.")

        # Redact before the transcript is sent to any LLM.
        database.update_progress(audit_id, "Redacting personal data")
        redaction = redact_pii(raw_transcript)

        database.update_progress(audit_id, "Identifying agent and customer")
        labelled = label_speakers(redaction.text) or redaction.text
        # The labelling step can reformat text; a second pass catches anything it exposed.
        transcript = redact_pii(labelled).text

        database.update_progress(audit_id, "Finding relevant policy rules")
        rules = get_retriever().relevant_rules(transcript)

        database.update_progress(audit_id, f"AI is scoring the call against {len(rules)} rules")
        scores = evaluate_call(transcript, rules)

        database.save_completed_audit(audit_id, transcript, redaction.summary(), scores, policy_version())
        logger.info("Audit %d completed: %s (%.1f)", audit_id, scores.outcome, scores.overall_score)

    except Exception as error:
        logger.exception("Audit %d failed", audit_id)
        database.mark_failed(audit_id, str(error))

    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass
