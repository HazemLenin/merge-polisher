"""Focused tests for confidence comment publish behavior."""

from typing import Any

import app as app_mod
from core.constants import CONFIDENCE_COMMENT_HEAD_SHA_PREFIX, CONFIDENCE_COMMENT_SIGNATURE
from core.models import ExecutionPolicy


def _confidence_enabled_policy() -> ExecutionPolicy:
    return ExecutionPolicy(
        description_enabled=False,
        suggestions_enabled=False,
        confidence_comment_marker_enabled=True,
        confidence_comment_history_enabled=False,
        confidence_comment_enabled=True,
        confidence_history_only_mode=False,
        should_enforce_template=False,
        should_enforce_required_inputs=False,
    )


def test_publish_confidence_comment_skips_when_sha_already_exists(monkeypatch) -> None:
    created_notes: list[str] = []
    monkeypatch.setenv("CI_COMMIT_SHA", "same-sha")
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: created_notes.append(kwargs["body"]))

    app_mod._publish_confidence_comment_if_enabled(
        policy=_confidence_enabled_policy(),
        mr_endpoint="http://example/mr",
        headers={"Authorization": "token"},
        existing_confidence_notes=[
            {
                "id": 5,
                "body": (
                    f"meta\n{CONFIDENCE_COMMENT_SIGNATURE}\n"
                    f"{CONFIDENCE_COMMENT_HEAD_SHA_PREFIX}same-sha -->"
                ),
            }
        ],
        confidence_context={
            "score": 8.5,
            "signals": {},
            "reasons": [{"rule": "small_diff", "delta": 0.6, "why": "small change"}],
        },
        generated_risk_level="low",
        generated_effect_tags=["bugfix"],
        generated_confidence_explanation="safe",
        generated_optimization_areas=[],
        generated_missing_tests=[],
    )
    assert created_notes == []


def test_publish_confidence_comment_creates_when_latest_sha_missing(monkeypatch) -> None:
    created_notes: list[str] = []
    monkeypatch.setenv("CI_COMMIT_SHA", "new-sha")

    def fake_create(**kwargs: Any) -> dict[str, int]:
        created_notes.append(kwargs["body"])
        return {"id": 1}

    monkeypatch.setattr(app_mod, "create_mr_note", fake_create)

    app_mod._publish_confidence_comment_if_enabled(
        policy=_confidence_enabled_policy(),
        mr_endpoint="http://example/mr",
        headers={"Authorization": "token"},
        existing_confidence_notes=[{"id": 9, "body": f"old\n{CONFIDENCE_COMMENT_SIGNATURE}"}],
        confidence_context={"score": 7.0, "signals": {}, "reasons": []},
        generated_risk_level="medium",
        generated_effect_tags=[],
        generated_confidence_explanation="ok",
        generated_optimization_areas=[],
        generated_missing_tests=[],
    )
    assert len(created_notes) == 1
    assert f"{CONFIDENCE_COMMENT_HEAD_SHA_PREFIX}new-sha -->" in created_notes[0]
