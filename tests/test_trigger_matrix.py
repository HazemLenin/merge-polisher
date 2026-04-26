"""Trigger-matrix tests for marker combinations and confidence history."""

from typing import Any

import app as app_mod
from core.constants import CONFIDENCE_COMMENT_SIGNATURE


def _fake_env(name: str) -> str:
    return {
        "CI_API_V4_URL": "https://gitlab/api/v4",
        "CI_PROJECT_ID": "1",
        "CI_MERGE_REQUEST_IID": "2",
        "GEMINI_API_KEY": "k",
    }[name]


def _build_description(*markers: str) -> str:
    marker_block = "\n".join(markers)
    return f"""{marker_block}

### Summary
Short summary.

### Issue Key
GAP-1000

### Problem Brief
Problem text.

### Solution Brief
Solution text.

### How to Test
- [ ] run

### Checklist
- [ ] I have tested these changes
"""


def _default_payload() -> dict[str, Any]:
    return {
        "description": {"description_markdown": "### Summary\n\nGenerated body.\n"},
        "review": {"suggestions": []},
        "confidence": {
            "effect_tags": ["bugfix"],
            "risk_level": "low",
            "optimization_areas": [],
            "missing_or_outdated_tests": [],
            "confidence_explanation": "ok",
        },
    }


def _setup_common(monkeypatch, description: str, mr_changes: dict[str, Any], notes: list[dict[str, Any]]) -> None:
    monkeypatch.setenv("CI_JOB_TOKEN", "token")
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.setattr(app_mod, "read_required_env", _fake_env)
    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: description)
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: mr_changes)
    monkeypatch.setattr(app_mod, "fetch_mr_notes_by_signature", lambda *_a, **_k: notes)


def test_trigger_descriptor_marker_only_updates_description(
    monkeypatch, minimal_mr_changes: dict[str, Any]
) -> None:
    description = _build_description("<!-- auto-descriptor:on -->")
    updates: list[str] = []
    notes: list[str] = []
    inlines: list[tuple[str, int]] = []
    gemini_calls: list[dict[str, Any]] = []

    _setup_common(monkeypatch, description, minimal_mr_changes, [])
    monkeypatch.setattr(app_mod, "extract_required_inputs", lambda _d: {
        "issue_key": "GAP-1000",
        "problem_brief": "Problem text.",
        "solution_brief": "Solution text.",
    })
    monkeypatch.setattr(
        app_mod,
        "generate_enhancement_payload",
        lambda **kwargs: (gemini_calls.append(kwargs) or _default_payload()),
    )
    monkeypatch.setattr(app_mod, "update_mr_description", lambda _e, _h, body: updates.append(body))
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: notes.append(kwargs["body"]))
    monkeypatch.setattr(
        app_mod,
        "create_mr_inline_discussion",
        lambda **kwargs: inlines.append((kwargs["file_path"], kwargs["new_line"])),
    )

    app_mod.run()

    assert len(gemini_calls) == 1
    assert len(updates) == 1
    assert notes == []
    assert inlines == []


def test_trigger_auto_review_marker_only_posts_inline_only(
    monkeypatch, minimal_mr_changes: dict[str, Any]
) -> None:
    description = _build_description("<!-- auto-review:on -->")
    updates: list[str] = []
    notes: list[str] = []
    inlines: list[tuple[str, int]] = []
    gemini_calls: list[dict[str, Any]] = []

    _setup_common(monkeypatch, description, minimal_mr_changes, [])
    monkeypatch.setattr(app_mod, "extract_required_inputs", lambda _d: {
        "issue_key": "GAP-1000",
        "problem_brief": "Problem text.",
        "solution_brief": "Solution text.",
    })
    payload = _default_payload()
    payload["review"]["suggestions"] = [
        {
            "file_path": "src/service/foo.py",
            "new_line": 1,
            "summary": "nit",
            "suggested_code": "line one",
        }
    ]
    monkeypatch.setattr(
        app_mod,
        "generate_enhancement_payload",
        lambda **kwargs: (gemini_calls.append(kwargs) or payload),
    )
    monkeypatch.setattr(app_mod, "update_mr_description", lambda _e, _h, body: updates.append(body))
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: notes.append(kwargs["body"]))
    monkeypatch.setattr(app_mod, "fetch_mr_versions", lambda *_a, **_k: {"head_sha": "sha"})
    monkeypatch.setattr(app_mod, "normalize_inline_suggestion_code", lambda *_a, **_k: "aligned")
    monkeypatch.setattr(
        app_mod,
        "create_mr_inline_discussion",
        lambda **kwargs: inlines.append((kwargs["file_path"], kwargs["new_line"])),
    )

    app_mod.run()

    assert len(gemini_calls) == 1
    assert updates == []
    assert notes == []
    assert len(inlines) == 1


def test_trigger_confidence_marker_only_posts_confidence_only(
    monkeypatch, minimal_mr_changes: dict[str, Any]
) -> None:
    description = _build_description("<!-- auto-confidence-comment:on -->")
    updates: list[str] = []
    notes: list[str] = []
    inlines: list[tuple[str, int]] = []
    gemini_calls: list[dict[str, Any]] = []

    _setup_common(monkeypatch, description, minimal_mr_changes, [])
    monkeypatch.setenv("CI_COMMIT_SHA", "sha-1")
    monkeypatch.setattr(app_mod, "extract_required_inputs", lambda _d: {
        "issue_key": "GAP-1000",
        "problem_brief": "Problem text.",
        "solution_brief": "Solution text.",
    })
    monkeypatch.setattr(
        app_mod,
        "generate_enhancement_payload",
        lambda **kwargs: (gemini_calls.append(kwargs) or _default_payload()),
    )
    monkeypatch.setattr(app_mod, "update_mr_description", lambda _e, _h, body: updates.append(body))
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: notes.append(kwargs["body"]))
    monkeypatch.setattr(
        app_mod,
        "create_mr_inline_discussion",
        lambda **kwargs: inlines.append((kwargs["file_path"], kwargs["new_line"])),
    )

    app_mod.run()

    assert len(gemini_calls) == 1
    assert updates == []
    assert inlines == []
    assert len(notes) == 1
    assert CONFIDENCE_COMMENT_SIGNATURE in notes[0]


def test_trigger_no_markers_does_nothing_and_skips_validation(
    monkeypatch, mr_description_no_auto_markers: str, minimal_mr_changes: dict[str, Any]
) -> None:
    gemini_calls = 0
    extraction_calls = 0
    updates: list[str] = []
    notes: list[str] = []

    _setup_common(monkeypatch, mr_description_no_auto_markers, minimal_mr_changes, [])

    def count_extract(_desc: str) -> dict[str, str]:
        nonlocal extraction_calls
        extraction_calls += 1
        return {"issue_key": "x", "problem_brief": "y", "solution_brief": "z"}

    def count_generate(**_kwargs: Any) -> dict[str, Any]:
        nonlocal gemini_calls
        gemini_calls += 1
        return _default_payload()

    monkeypatch.setattr(app_mod, "extract_required_inputs", count_extract)
    monkeypatch.setattr(app_mod, "generate_enhancement_payload", count_generate)
    monkeypatch.setattr(app_mod, "update_mr_description", lambda _e, _h, body: updates.append(body))
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: notes.append(kwargs["body"]))

    app_mod.run()

    assert gemini_calls == 0
    assert extraction_calls == 0
    assert updates == []
    assert notes == []


def test_trigger_history_with_confidence_marker_adds_confidence_only(
    monkeypatch, minimal_mr_changes: dict[str, Any]
) -> None:
    description = _build_description("<!-- auto-confidence-comment:on -->")
    gemini_calls = 0
    updates: list[str] = []
    notes: list[str] = []
    existing = [{"id": 100, "body": f"old\n{CONFIDENCE_COMMENT_SIGNATURE}"}]

    _setup_common(monkeypatch, description, minimal_mr_changes, existing)
    monkeypatch.setenv("CI_COMMIT_SHA", "new-sha")
    monkeypatch.setattr(app_mod, "extract_required_inputs", lambda _d: {
        "issue_key": "GAP-1000",
        "problem_brief": "Problem text.",
        "solution_brief": "Solution text.",
    })

    def count_generate(**_kwargs: Any) -> dict[str, Any]:
        nonlocal gemini_calls
        gemini_calls += 1
        return _default_payload()

    monkeypatch.setattr(app_mod, "generate_enhancement_payload", count_generate)
    monkeypatch.setattr(app_mod, "update_mr_description", lambda _e, _h, body: updates.append(body))
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: notes.append(kwargs["body"]))

    app_mod.run()

    assert gemini_calls == 1
    assert updates == []
    assert len(notes) == 1


def test_trigger_history_without_marker_adds_confidence_only_and_skips_extraction(
    monkeypatch, mr_description_no_auto_markers: str, minimal_mr_changes: dict[str, Any]
) -> None:
    gemini_calls = 0
    extraction_calls = 0
    updates: list[str] = []
    notes: list[str] = []
    existing = [{"id": 101, "body": f"old\n{CONFIDENCE_COMMENT_SIGNATURE}"}]

    _setup_common(monkeypatch, mr_description_no_auto_markers, minimal_mr_changes, existing)
    monkeypatch.setenv("CI_COMMIT_SHA", "new-sha-2")

    def count_extract(_desc: str) -> dict[str, str]:
        nonlocal extraction_calls
        extraction_calls += 1
        return {"issue_key": "x", "problem_brief": "y", "solution_brief": "z"}

    def count_generate(**_kwargs: Any) -> dict[str, Any]:
        nonlocal gemini_calls
        gemini_calls += 1
        return _default_payload()

    monkeypatch.setattr(app_mod, "extract_required_inputs", count_extract)
    monkeypatch.setattr(app_mod, "generate_enhancement_payload", count_generate)
    monkeypatch.setattr(app_mod, "update_mr_description", lambda _e, _h, body: updates.append(body))
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: notes.append(kwargs["body"]))

    app_mod.run()

    assert extraction_calls == 0
    assert gemini_calls == 1
    assert updates == []
    assert len(notes) == 1
