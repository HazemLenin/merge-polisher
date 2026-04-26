"""Focused tests for inline suggestion gating."""

import app as app_mod
from core.models import ExecutionPolicy


def _suggestions_enabled_policy() -> ExecutionPolicy:
    return ExecutionPolicy(
        description_enabled=False,
        suggestions_enabled=True,
        confidence_comment_marker_enabled=False,
        confidence_comment_history_enabled=False,
        confidence_comment_enabled=False,
        confidence_history_only_mode=False,
        should_enforce_template=False,
        should_enforce_required_inputs=False,
    )


def test_publish_inline_suggestions_posts_only_changed_lines(
    monkeypatch,
    minimal_mr_changes: dict,
) -> None:
    posted: list[tuple[str, int]] = []
    monkeypatch.setattr(app_mod, "fetch_mr_versions", lambda *_a, **_k: {"head_sha": "sha"})
    monkeypatch.setattr(app_mod, "normalize_inline_suggestion_code", lambda *_a, **_k: "aligned")

    def fake_create(**kwargs):
        posted.append((kwargs["file_path"], kwargs["new_line"]))
        return {"id": 3}

    monkeypatch.setattr(app_mod, "create_mr_inline_discussion", fake_create)

    app_mod._publish_inline_suggestions_if_enabled(
        policy=_suggestions_enabled_policy(),
        mr_endpoint="http://example/mr",
        headers={"Authorization": "token"},
        generated_suggestions=[
            {
                "file_path": "src/service/foo.py",
                "new_line": 1,
                "summary": "good",
                "suggested_code": "x = 1",
            },
            {
                "file_path": "src/service/foo.py",
                "new_line": 99,
                "summary": "skip",
                "suggested_code": "y = 2",
            },
        ],
        diff_context="non-empty",
        mr_changes=minimal_mr_changes,
    )
    assert posted == [("src/service/foo.py", 1)]


def test_publish_inline_suggestions_skips_when_diff_context_missing(
    monkeypatch,
    minimal_mr_changes: dict,
) -> None:
    posted: list[tuple[str, int]] = []
    monkeypatch.setattr(
        app_mod,
        "create_mr_inline_discussion",
        lambda **kwargs: posted.append((kwargs["file_path"], kwargs["new_line"])),
    )

    app_mod._publish_inline_suggestions_if_enabled(
        policy=_suggestions_enabled_policy(),
        mr_endpoint="http://example/mr",
        headers={"Authorization": "token"},
        generated_suggestions=[
            {
                "file_path": "src/service/foo.py",
                "new_line": 1,
                "summary": "good",
                "suggested_code": "x = 1",
            }
        ],
        diff_context="",
        mr_changes=minimal_mr_changes,
    )
    assert posted == []
