"""Tests for the parts of the app that do not need network access."""

from backend.policy import load_policy_rules, parse_policy
from backend.rag import split_into_windows
from backend.redaction import redact_pii
from backend.scoring import LLMEvaluation, RuleFinding, calculate_scores


# ----- Policy parsing ------------------------------------------------------

def test_policy_file_parses_into_rules():
    rules = load_policy_rules()
    ids = [rule.rule_id for rule in rules]
    assert ids == ["2.1", "2.2", "2.3", "3.1", "3.2"]


def test_only_section_three_rules_are_zero_tolerance():
    zero_tolerance = {rule.rule_id for rule in load_policy_rules() if rule.zero_tolerance}
    assert zero_tolerance == {"3.1", "3.2"}


def test_metric_entries_are_not_rules():
    text = "1. RULES\n[Rule 1.1] Be kind\n- Say hello\n2. RUBRIC\n[Metric 2.1] Score\n- Points"
    rules = parse_policy(text)
    assert len(rules) == 1
    assert rules[0].text == "- Say hello"


# ----- Redaction -----------------------------------------------------------

def test_redacts_structured_pii():
    text = ("Card 4111 1111 1111 1111, Aadhaar 1234 5678 9012, phone +91 9876543210, "
            "IFSC SBIN0001234, mail a.b@example.com")
    result = redact_pii(text)
    for placeholder in ["[CARD REDACTED]", "[AADHAAR REDACTED]", "[PHONE REDACTED]",
                        "[IFSC REDACTED]", "[EMAIL REDACTED]"]:
        assert placeholder in result.text
    assert "9876543210" not in result.text
    assert result.counts["Card Number"] == 1


def test_redacts_numbers_formatted_by_speech_to_text():
    # Real Whisper output from a test call
    result = redact_pii("Customer: My number is 98,76543,210. Card 4111-1111-1111-1111.")
    assert "[PHONE REDACTED]" in result.text
    assert "[CARD REDACTED]" in result.text
    assert "98" not in result.text


def test_amounts_and_short_numbers_are_kept():
    text = "Agent: Your balance is 42,000 rupees and there are two charges of 3,000 each on 02-11-2026."
    assert redact_pii(text).text == text


def test_redacting_twice_does_not_nest_placeholders():
    once = redact_pii("Agent: Thank you for contacting Support. My name is Anita Rao.").text
    twice = redact_pii(once).text
    assert "[[" not in twice
    assert twice == once


def test_redacts_names_the_model_misses():
    # Real transcript lines from the sample calls
    text = ("Agent: Thank you for contacting support. My name is Priya. How may I help you today?\n"
            "Customer: Nehagupta, order number 33187.\n"
            "Customer: Sanjay Kumar, account number 44907.\n"
            "Agent: Have a wonderful day, Mr. Mehta.")
    result = redact_pii(text).text
    for name in ["Priya", "Nehagupta", "Sanjay", "Kumar", "Mehta"]:
        assert name not in result


def test_ordinary_sentences_are_not_treated_as_names():
    text = "Agent: It is the only way. I am sorry about that."
    assert redact_pii(text).text == text


def test_text_without_pii_is_unchanged():
    result = redact_pii("Customer: My order has not arrived yet.")
    assert result.text == "Customer: My order has not arrived yet."
    assert result.summary() == "No PII detected"


# ----- Retrieval windows ---------------------------------------------------

def test_transcript_is_split_into_windows():
    transcript = "\n".join(f"Agent: line {i}" for i in range(13))
    windows = split_into_windows(transcript, 6)
    assert len(windows) == 3
    assert windows[2] == "Agent: line 12"


# ----- Score calculation ---------------------------------------------------

def _finding(rule_id, verdict, zero_tolerance=False):
    return RuleFinding(rule_id, f"Rule {rule_id}", zero_tolerance, verdict, "", "")


def _evaluation(empathy=80, professionalism=90):
    return LLMEvaluation(empathy=empathy, professionalism=professionalism,
                         summary="ok", rule_judgements=[], suggestions=[])


def test_all_rules_passed_is_pass():
    scores = calculate_scores(_evaluation(), [_finding("2.1", "pass"), _finding("3.1", "pass", True)])
    assert scores.outcome == "PASS"
    # 0.4 * 100 + 0.3 * 100 + 0.3 * 85
    assert scores.overall_score == 95.5


def test_zero_tolerance_failure_is_fail_even_with_great_soft_skills():
    scores = calculate_scores(_evaluation(100, 100), [_finding("2.1", "pass"), _finding("3.1", "fail", True)])
    assert scores.outcome == "FAIL"
    assert scores.compliance_score == 0


def test_protocol_failure_is_warn():
    findings = [_finding("2.1", "pass"), _finding("2.2", "fail"), _finding("2.3", "not_applicable")]
    scores = calculate_scores(_evaluation(), findings)
    assert scores.outcome == "WARN"
    assert scores.protocol_score == 50.0   # 1 of 2 applicable rules passed
