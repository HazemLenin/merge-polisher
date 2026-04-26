"""Tests for mr_parser."""

import pytest

import domain.mr.parser as mr_parser
from core.constants import REQUIRED_TEMPLATE_MARKERS
from domain.mr.parser import (
    extract_labeled_text,
    extract_required_inputs,
    is_template_compatible,
)


def test_is_template_compatible_requires_all_markers():
    base = "\n".join(REQUIRED_TEMPLATE_MARKERS)
    assert is_template_compatible(base) is True
    assert is_template_compatible(base.replace("### Summary", "")) is False


def test_extract_labeled_text_header_style():
    desc = "### Problem Brief\n\nMulti\nline\n\n### Solution Brief\n\nDone\n"
    assert "Multi line" in (extract_labeled_text(desc, "problem brief") or "")
    assert extract_labeled_text(desc, "solution brief") == "Done"


def test_extract_required_inputs_success(minimal_mr_description):
    data = extract_required_inputs(minimal_mr_description)
    assert data["issue_key"] == "GAP-1000"
    assert "broken" in data["problem_brief"].lower()
    assert "fixed" in data["solution_brief"].lower()


def test_extract_required_inputs_missing_issue(monkeypatch):
    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(mr_parser, "fail", boom)
    body = """
### Problem Brief
p
### Solution Brief
s
"""
    with pytest.raises(RuntimeError, match="issue key"):
        extract_required_inputs(body)
