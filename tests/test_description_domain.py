"""Tests for description_domain."""

from core.constants import (
    CONFIDENCE_COMMENT_HEAD_SHA_PREFIX,
    CONFIDENCE_COMMENT_SIGNATURE,
    MAX_INLINE_SUGGESTIONS,
)
from domain.description.confidence_comment import build_confidence_comment_body
from domain.description.normalization import (
    normalize_effect_tags,
    normalize_risk_level,
    normalize_suggestions,
    normalize_string_list,
)


def test_normalize_suggestions_filters_invalid():
    raw = [
        {
            "file_path": "a.py",
            "summary": "This improves readability and keeps behavior unchanged.",
            "suggested_code": "x",
            "new_line": 1,
        },
        {"file_path": "", "summary": "bad", "suggested_code": "x", "new_line": 1},
        "not-a-dict",
        {"file_path": "b.py", "summary": "bad", "suggested_code": "x", "new_line": 0},
    ]
    out = normalize_suggestions(raw)
    assert len(out) == 1
    assert out[0]["file_path"] == "a.py"


def test_normalize_suggestions_caps_at_max():
    raw = [
        {
            "file_path": f"f{i}.py",
            "summary": "This keeps the logic explicit and easier to test.",
            "suggested_code": "line1\nline2",
            "new_line": 1,
        }
        for i in range(MAX_INLINE_SUGGESTIONS + 5)
    ]
    out = normalize_suggestions(raw)
    assert len(out) == MAX_INLINE_SUGGESTIONS


def test_normalize_suggestions_rejects_non_sentence_summary():
    out = normalize_suggestions(
        [
            {
                "file_path": "x.py",
                "summary": "too short",
                "suggested_code": "x = 1",
                "new_line": 1,
            }
        ]
    )
    assert out == []


def test_normalize_suggestions_accepts_multiline_code():
    out = normalize_suggestions(
        [
            {
                "file_path": "x.py",
                "summary": "This handles both branches and keeps return values consistent.",
                "suggested_code": "if ok:\n    return 1\nreturn 0",
                "new_line": 10,
            }
        ]
    )
    assert len(out) == 1
    assert "\n" in out[0]["suggested_code"]


def test_normalize_effect_tags_dedupes_and_filters():
    assert normalize_effect_tags(["bugfix", "INVALID", "Bugfix", "feature"]) == [
        "bugfix",
        "feature",
    ]
    assert normalize_effect_tags(None) == []


def test_normalize_risk_level():
    assert normalize_risk_level("HIGH") == "high"
    assert normalize_risk_level("nope") == ""


def test_normalize_string_list():
    assert normalize_string_list([" a ", "", "b"]) == ["a", "b"]
    assert normalize_string_list({}) == []


def test_build_confidence_comment_body_includes_sections():
    reasons = [{"rule": "small_diff_scope", "weight": 0.6, "reason": "Limited diff scope."}]
    opts = [f"opt{i}" for i in range(7)]
    missing = [f"m{i}" for i in range(7)]
    body = build_confidence_comment_body(
        confidence_score=8.2,
        risk_level="low",
        effect_tags=["bugfix"],
        confidence_explanation="Because tests.",
        confidence_reasons=reasons,
        optimization_areas=opts,
        missing_or_outdated_tests=missing,
        signature=CONFIDENCE_COMMENT_SIGNATURE,
        head_sha="abc123",
        sha_marker_prefix=CONFIDENCE_COMMENT_HEAD_SHA_PREFIX,
    )
    assert CONFIDENCE_COMMENT_SIGNATURE in body
    assert f"{CONFIDENCE_COMMENT_HEAD_SHA_PREFIX}abc123 -->" in body
    assert "8.2/10.0" in body
    assert "opt0" in body and "opt4" in body
    assert "opt5" not in body
    assert "m0" in body and "m4" in body
    assert "m5" not in body
    assert "small_diff_scope" in body
