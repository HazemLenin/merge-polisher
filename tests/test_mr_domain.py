"""Tests for mr_domain."""

import pytest

import domain.mr.markers as mr_domain
from core.constants import (
    CONFIDENCE_COMMENT_OPT_IN_MARKER,
    DESCRIPTION_OPT_IN_MARKER,
    SUGGESTIONS_OPT_IN_MARKER,
)
from domain.mr.markers import (
    build_auth_headers,
    extract_leading_comment_markers,
    is_marker_present,
)


def test_extract_leading_comment_markers_stops_at_first_markdown():
    desc = f"""{DESCRIPTION_OPT_IN_MARKER}
<!-- ignored later -->
### Summary
{SUGGESTIONS_OPT_IN_MARKER}
"""
    found = extract_leading_comment_markers(
        desc,
        (DESCRIPTION_OPT_IN_MARKER, SUGGESTIONS_OPT_IN_MARKER, CONFIDENCE_COMMENT_OPT_IN_MARKER),
    )
    assert DESCRIPTION_OPT_IN_MARKER in found
    assert SUGGESTIONS_OPT_IN_MARKER not in found


def test_is_marker_present_in_leading_comments_only():
    desc = f"""<!-- x -->
{DESCRIPTION_OPT_IN_MARKER}

### Summary
{DESCRIPTION_OPT_IN_MARKER}
"""
    assert is_marker_present(desc, DESCRIPTION_OPT_IN_MARKER) is True


def test_build_auth_headers_prefers_gitlab_token(monkeypatch):
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-secret")
    monkeypatch.setenv("CI_JOB_TOKEN", "job-token")
    h = build_auth_headers()
    assert h["PRIVATE-TOKEN"] == "glpat-secret"
    assert "JOB-TOKEN" not in h


def test_build_auth_headers_falls_back_to_ci_job_token(monkeypatch):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.setenv("CI_JOB_TOKEN", "job-token")
    h = build_auth_headers()
    assert h["JOB-TOKEN"] == "job-token"


def test_build_auth_headers_missing_token(monkeypatch):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)

    def boom(_msg: str, _code: int = 1) -> None:
        raise RuntimeError("fail-called")

    monkeypatch.setattr(mr_domain, "fail", boom)
    with pytest.raises(RuntimeError, match="fail-called"):
        build_auth_headers()
