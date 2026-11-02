"""
Turns data/policy.txt into a list of structured rules.

The policy file is organised into numbered sections, each containing rules
written as:

    [Rule 2.1] Greeting and Verification
    - Standard: ...
    - Verification: ...

Every rule becomes one `PolicyRule`. Rules inside a section whose heading
contains "ZERO TOLERANCE" are marked `zero_tolerance=True`: breaking one of
them fails the whole audit. Scoring-rubric entries ("[Metric 4.1] ...") are
not rules an agent can break, so they are ignored here.
"""

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache

from backend.config import POLICY_PATH

SECTION_HEADING = re.compile(r"^\d+\.\s+(.+)$")
RULE_HEADING = re.compile(r"^\[Rule\s+([\d.]+)\]\s*(.+)$")
DIVIDER = re.compile(r"^=+$")


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str           # e.g. "2.1"
    title: str             # e.g. "Greeting and Verification"
    text: str              # full rule text, used for embeddings and the LLM prompt
    zero_tolerance: bool   # True for rules where one breach means FAIL

    def as_prompt_text(self) -> str:
        label = " (ZERO TOLERANCE)" if self.zero_tolerance else ""
        return f"[Rule {self.rule_id}] {self.title}{label}\n{self.text}"


def parse_policy(policy_text: str) -> list[PolicyRule]:
    rules = []
    in_zero_tolerance_section = False
    current_rule = None  # (rule_id, title, body_lines, zero_tolerance)

    def finish_current_rule():
        if current_rule:
            rule_id, title, body_lines, zero_tolerance = current_rule
            rules.append(PolicyRule(rule_id, title, "\n".join(body_lines).strip(), zero_tolerance))

    for raw_line in policy_text.splitlines():
        line = raw_line.strip()

        if not line or DIVIDER.match(line):
            continue

        section = SECTION_HEADING.match(line)
        if section:
            finish_current_rule()
            current_rule = None
            in_zero_tolerance_section = "ZERO TOLERANCE" in section.group(1).upper()
            continue

        rule = RULE_HEADING.match(line)
        if rule:
            finish_current_rule()
            current_rule = (rule.group(1), rule.group(2).strip(), [], in_zero_tolerance_section)
            continue

        if line.startswith("[Metric"):
            # Rubric entries end the current rule and are not collected.
            finish_current_rule()
            current_rule = None
            continue

        if current_rule:
            current_rule[2].append(line)

    finish_current_rule()
    return rules


@lru_cache(maxsize=1)
def _read_policy_file() -> str:
    with open(POLICY_PATH, encoding="utf-8") as f:
        return f.read()


def load_policy_rules() -> list[PolicyRule]:
    return parse_policy(_read_policy_file())


def policy_version() -> str:
    """Short hash of the policy file. Changes whenever the policy text changes."""
    return hashlib.sha256(_read_policy_file().encode("utf-8")).hexdigest()[:12]
