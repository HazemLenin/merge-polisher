"""Parsing and validation helpers for MR description input."""

import re
from typing import Dict, Optional

from core.constants import REQUIRED_TEMPLATE_MARKERS
from core.runtime import fail


def is_template_compatible(description: str) -> bool:
    """Check whether the MR follows the expected AutoDescriptor template."""
    return all(marker in description for marker in REQUIRED_TEMPLATE_MARKERS)


def extract_labeled_text(description: str, field_name: str) -> Optional[str]:
    """Extract a labeled field from multiple markdown writing styles."""
    patterns = [
        rf"(?is)^#{{1,6}}\s*{field_name}\s*:?\s*(.+?)(?=^#{{1,6}}\s|\Z)",
        rf"(?is)^\s*[-*]?\s*\*\*{field_name}\*\*\s*:?\s*(.+?)$",
        rf"(?is)^\s*[-*]?\s*{field_name}\s*:\s*(.+?)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, flags=re.MULTILINE | re.IGNORECASE)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip()
            if value:
                return value
    return None


def extract_required_inputs(description: str) -> Dict[str, str]:
    """Extract issue key (optional), problem brief, and solution brief."""
    issue_key = extract_labeled_text(description, "issue key") or ""
    if not issue_key:
        issue_match = re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", description)
        if issue_match:
            issue_key = issue_match.group(0)
    problem_brief = extract_labeled_text(description, "problem brief")
    solution_brief = extract_labeled_text(description, "solution brief")

    if not problem_brief:
        fail(
            "Could not find 'problem brief' in MR description. "
            "Please include a clear 'Problem brief:' section."
        )
    if not solution_brief:
        fail(
            "Could not find 'solution brief' in MR description. "
            "Please include a clear 'Solution brief:' section."
        )

    return {
        "issue_key": issue_key,
        "problem_brief": problem_brief,
        "solution_brief": solution_brief,
    }
