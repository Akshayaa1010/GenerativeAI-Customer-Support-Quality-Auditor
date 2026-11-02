"""
PII redaction. Runs on every transcript before any text is sent to an LLM
or saved to the database.

Emails and IFSC codes are found with regular expressions. Card, Aadhaar and
phone numbers are found by their digit count, because speech-to-text writes
the same number in many ways ("9876543210", "98765 43210", "98,76543,210").
Person names are found with spaCy's named-entity recogniser.
"""

import logging
import re
from dataclasses import dataclass

import spacy

logger = logging.getLogger(__name__)

TEXT_PATTERNS = [
    ("Email Address", "[EMAIL REDACTED]", re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
    ("IFSC Code", "[IFSC REDACTED]", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
]

# A run of digits that may be split by spaces, commas, dots or hyphens.
NUMBER_RUN = re.compile(r"(?<!\w)\+?\d(?:[ ,.\-]{0,2}\d)+")

NUMBER_PLACEHOLDERS = {
    "Card Number": "[CARD REDACTED]",
    "Aadhaar Number": "[AADHAAR REDACTED]",
    "Phone Number": "[PHONE REDACTED]",
}


def is_mobile(digits: str) -> bool:
    """Indian mobile numbers have 10 digits and start with 6, 7, 8 or 9."""
    return len(digits) == 10 and digits[0] in "6789"


def classify_number(digits: str) -> str | None:
    """Decide what kind of identifier a string of digits is, or None if it is not PII."""
    if 13 <= len(digits) <= 19:
        return "Card Number"
    if is_mobile(digits) or (digits.startswith("0") and is_mobile(digits[1:])):
        return "Phone Number"
    if digits.startswith("91") and is_mobile(digits[2:]):
        return "Phone Number"
    if len(digits) == 12:
        return "Aadhaar Number"
    return None  # amounts, dates, order numbers, etc.

NAME_PLACEHOLDER = "[NAME REDACTED]"

# spaCy's small English model misses many Indian names, so names are also
# found from the words around them. Each pattern captures the name as "name".
NAME = r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
CONTEXT_NAME_PATTERNS = [
    # "My name is Anita", "I am Rohan Das", "It is Arjun Mehta"
    re.compile(rf"\b(?:[Mm]y name is|I am|I'm|[Ii]t is|[Ii]t's)\s+{NAME}"),
    # "Mr. Mehta", "Ms Gupta"
    re.compile(rf"\b(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+{NAME}"),
    # A verification answer: "Customer: Neha Gupta, order number 33187"
    re.compile(rf"^Customer:\s*{NAME},\s*(?:account|order|customer|policy)\b", re.MULTILINE),
]
PLACEHOLDER = re.compile(r"\[[A-Z ]+ REDACTED\]")


def _load_spacy_model():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        logger.warning("spaCy model 'en_core_web_sm' is missing; names will not be redacted. "
                       "Install it with: python -m spacy download en_core_web_sm")
        return None


_nlp = _load_spacy_model()


@dataclass
class RedactionResult:
    text: str
    counts: dict[str, int]  # e.g. {"Phone Number": 2, "Person Name": 1}

    def summary(self) -> str:
        if not self.counts:
            return "No PII detected"
        return ", ".join(f"{count} {label}{'s' if count > 1 else ''}" for label, count in self.counts.items())


def redact_pii(text: str) -> RedactionResult:
    counts: dict[str, int] = {}

    for label, placeholder, pattern in TEXT_PATTERNS:
        text, found = pattern.subn(placeholder, text)
        if found:
            counts[label] = found

    def replace_number(match):
        label = classify_number(re.sub(r"\D", "", match.group()))
        if label is None:
            return match.group()
        counts[label] = counts.get(label, 0) + 1
        return NUMBER_PLACEHOLDERS[label]

    text = NUMBER_RUN.sub(replace_number, text)

    text, names_by_model = _redact_names(text)
    text, names_by_context = _redact_names_from_context(text)
    if names_by_model + names_by_context:
        counts["Person Name"] = names_by_model + names_by_context

    return RedactionResult(text=text, counts=counts)


def _redact_names_from_context(text: str) -> tuple[str, int]:
    found = 0

    def replace_name(match):
        nonlocal found
        found += 1
        start, end = match.span("name")
        return match.group()[:start - match.start()] + NAME_PLACEHOLDER + match.group()[end - match.start():]

    for pattern in CONTEXT_NAME_PATTERNS:
        text = pattern.sub(replace_name, text)
    return text, found


def _redact_names(text: str) -> tuple[str, int]:
    if _nlp is None or not text:
        return text, 0

    # Spans already redacted (e.g. "[NAME REDACTED]") must not be redacted again.
    placeholders = [match.span() for match in PLACEHOLDER.finditer(text)]

    def overlaps_placeholder(ent):
        return any(start < ent.end_char and ent.start_char < end for start, end in placeholders)

    people = [ent for ent in _nlp(text).ents if ent.label_ == "PERSON" and not overlaps_placeholder(ent)]
    # Replace from the end of the text backwards so earlier offsets stay valid.
    for ent in sorted(people, key=lambda e: e.start_char, reverse=True):
        text = text[:ent.start_char] + NAME_PLACEHOLDER + text[ent.end_char:]
    return text, len(people)
