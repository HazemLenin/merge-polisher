"""Integration-style tests for app.run with heavy mocking."""

from typing import Any

import pytest

import app as app_mod
from adapters.vcs.client import VcsClient
from core.constants import (
    CONFIDENCE_COMMENT_HEAD_SHA_PREFIX,
    CONFIDENCE_COMMENT_SIGNATURE,
    DESCRIPTION_OPT_IN_MARKER,
)


@pytest.fixture(params=["gitlab", "github"])
def provider(request) -> str:
    return request.param


@pytest.fixture(autouse=True)
def configure_provider_runtime(
    monkeypatch,
    provider: str,
    clean_provider_env,
    provider_required_env,
) -> None:
    monkeypatch.setenv("CI_PROVIDER", provider)
    if provider == "github":
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
        monkeypatch.setenv("GITHUB_TOKEN", "token")
    else:
        monkeypatch.setenv("CI_API_V4_URL", "https://gitlab/api/v4")
        monkeypatch.setenv("CI_PROJECT_ID", "1")
        monkeypatch.setenv("CI_MERGE_REQUEST_IID", "2")
        monkeypatch.setenv("CI_JOB_TOKEN", "token")
        monkeypatch.delenv("GITLAB_TOKEN", raising=False)

    monkeypatch.setattr(app_mod, "read_required_env", lambda name: provider_required_env[name])
    monkeypatch.setattr(
        app_mod,
        "resolve_vcs_client",
        lambda: VcsClient(
            provider_name=provider,
            build_endpoint=lambda: "https://example.test/mr/1",
            build_auth_headers=lambda: {},
            fetch_description=lambda endpoint, headers: app_mod.fetch_mr_description(endpoint, headers),
            fetch_changes=lambda endpoint, headers: app_mod.fetch_mr_changes(endpoint, headers),
            build_diff_context=lambda changes: "diff-context",
            update_description=lambda endpoint, headers, body: app_mod.update_mr_description(endpoint, headers, body),
            fetch_versions=lambda endpoint, headers: app_mod.fetch_mr_versions(endpoint, headers),
            build_changed_new_lines=lambda changes: app_mod.build_changed_new_lines(changes),
            normalize_inline_suggestion_code=lambda changes, file_path, new_line, suggested_code: app_mod.normalize_inline_suggestion_code(
                changes, file_path, new_line, suggested_code
            ),
            create_inline_discussion=lambda endpoint, headers, file_path, new_line, versions, summary, suggested_code: app_mod.create_mr_inline_discussion(
                endpoint=endpoint,
                headers=headers,
                file_path=file_path,
                new_line=new_line,
                versions=versions,
                summary=summary,
                suggested_code=suggested_code,
            ),
            fetch_notes_by_signature=lambda endpoint, headers, signature: app_mod.fetch_mr_notes_by_signature(
                endpoint, headers, signature
            ),
            get_latest_note_by_id=lambda notes: app_mod.get_latest_note_by_id(notes),
            extract_sha_from_note_body=lambda body, prefix: app_mod.extract_sha_from_note_body(body, prefix),
            create_note=lambda endpoint, headers, body: app_mod.create_mr_note(
                endpoint=endpoint, headers=headers, body=body
            ),
        ),
    )


def test_run_returns_early_when_no_markers(
    monkeypatch, mr_description_no_auto_markers: str
) -> None:
    updates: list[str] = []
    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: mr_description_no_auto_markers)
    monkeypatch.setattr(app_mod, "fetch_mr_notes_by_signature", lambda *_a, **_k: [])

    def capture_update(_endpoint, _headers, body: str) -> None:
        updates.append(body)

    monkeypatch.setattr(app_mod, "update_mr_description", capture_update)

    app_mod.run()

    assert updates == []


def test_run_updates_description_and_creates_confidence_note(
    monkeypatch, minimal_mr_description: str, minimal_mr_changes: dict[str, Any]
) -> None:
    updates: list[str] = []
    notes: list[str] = []

    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: minimal_mr_description)
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: minimal_mr_changes)

    def fake_generate(**_kwargs):
        return {
            "description": {"description_markdown": "### Summary\n\nAuto-filled body.\n"},
            "review": {"suggestions": []},
            "confidence": {
                "effect_tags": ["bugfix"],
                "risk_level": "low",
                "optimization_areas": ["cache"],
                "missing_or_outdated_tests": [],
                "confidence_explanation": "Looks safe.",
            },
        }

    monkeypatch.setattr(app_mod, "generate_enhancement_payload", fake_generate)

    def capture_update(_endpoint, _headers, body: str) -> None:
        updates.append(body)

    monkeypatch.setattr(app_mod, "fetch_mr_notes_by_signature", lambda *_a, **_k: [])

    def capture_note(*, endpoint, headers, body) -> dict[str, int]:
        notes.append(body)
        return {"id": 1}

    monkeypatch.setattr(app_mod, "update_mr_description", capture_update)
    monkeypatch.setattr(app_mod, "create_mr_note", capture_note)
    monkeypatch.setenv("CI_COMMIT_SHA", "abc123")

    app_mod.run()

    assert len(updates) == 1
    assert updates[0] == "### Summary\n\nAuto-filled body."
    assert DESCRIPTION_OPT_IN_MARKER not in updates[0]
    assert len(notes) == 1
    assert CONFIDENCE_COMMENT_SIGNATURE in notes[0]
    assert f"{CONFIDENCE_COMMENT_HEAD_SHA_PREFIX}abc123 -->" in notes[0]
    assert "Confidence score" in notes[0]


def test_run_skips_confidence_when_latest_sha_matches(
    monkeypatch, mr_description_no_auto_markers: str, minimal_mr_changes: dict[str, Any]
) -> None:
    created_notes: list[str] = []
    description_updates: list[str] = []

    monkeypatch.setenv("CI_COMMIT_SHA", "same123")
    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: mr_description_no_auto_markers)
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: minimal_mr_changes)
    monkeypatch.setattr(
        app_mod,
        "fetch_mr_notes_by_signature",
        lambda *_a, **_k: [
            {
                "id": 7,
                "body": (
                    f"old note\n{CONFIDENCE_COMMENT_SIGNATURE}\n"
                    f"{CONFIDENCE_COMMENT_HEAD_SHA_PREFIX}same123 -->"
                ),
            }
        ],
    )
    monkeypatch.setattr(
        app_mod,
        "generate_enhancement_payload",
        lambda **_kwargs: {
            "description": {"description_markdown": "### Summary\n\nIgnored.\n"},
            "review": {"suggestions": []},
            "confidence": {
                "effect_tags": [],
                "risk_level": "low",
                "optimization_areas": [],
                "missing_or_outdated_tests": [],
                "confidence_explanation": "ok",
            },
        },
    )
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: created_notes.append(kwargs["body"]))
    monkeypatch.setattr(
        app_mod, "update_mr_description", lambda *_args, **_kwargs: description_updates.append("updated")
    )

    app_mod.run()

    assert created_notes == []
    assert description_updates == []


def test_run_creates_confidence_when_latest_sha_missing(
    monkeypatch, mr_description_no_auto_markers: str, minimal_mr_changes: dict[str, Any]
) -> None:
    created_notes: list[str] = []
    description_updates: list[str] = []

    monkeypatch.setenv("CI_COMMIT_SHA", "new123")
    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: mr_description_no_auto_markers)
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: minimal_mr_changes)
    monkeypatch.setattr(
        app_mod,
        "fetch_mr_notes_by_signature",
        lambda *_a, **_k: [{"id": 9, "body": f"legacy\n{CONFIDENCE_COMMENT_SIGNATURE}"}],
    )
    monkeypatch.setattr(
        app_mod,
        "generate_enhancement_payload",
        lambda **_kwargs: {
            "description": {"description_markdown": "### Summary\n\nIgnored.\n"},
            "review": {"suggestions": []},
            "confidence": {
                "effect_tags": [],
                "risk_level": "medium",
                "optimization_areas": [],
                "missing_or_outdated_tests": [],
                "confidence_explanation": "ok",
            },
        },
    )
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: created_notes.append(kwargs["body"]))
    monkeypatch.setattr(
        app_mod, "update_mr_description", lambda *_args, **_kwargs: description_updates.append("updated")
    )

    app_mod.run()

    assert len(created_notes) == 1
    assert f"{CONFIDENCE_COMMENT_HEAD_SHA_PREFIX}new123 -->" in created_notes[0]
    assert description_updates == []


def test_run_requires_required_input_extraction_when_only_confidence_marker_enabled(
    monkeypatch, minimal_mr_changes: dict[str, Any]
) -> None:
    mr_description = """<!-- auto-confidence-comment:on -->

### Summary
This MR intentionally omits issue/problem/solution sections.
"""

    monkeypatch.setenv("CI_COMMIT_SHA", "sha999")
    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: mr_description)
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: minimal_mr_changes)
    monkeypatch.setattr(app_mod, "fetch_mr_notes_by_signature", lambda *_a, **_k: [])

    def extraction_called(_description: str) -> dict[str, str]:
        raise RuntimeError("extract_required_inputs called")

    monkeypatch.setattr(app_mod, "extract_required_inputs", extraction_called)

    import pytest

    with pytest.raises(RuntimeError, match="extract_required_inputs called"):
        app_mod.run()


def test_run_skips_required_input_extraction_for_confidence_history_enablement(
    monkeypatch, mr_description_no_auto_markers: str
) -> None:
    created_notes: list[str] = []

    monkeypatch.setenv("CI_COMMIT_SHA", "sha777")
    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: mr_description_no_auto_markers)
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: {})
    monkeypatch.setattr(
        app_mod,
        "fetch_mr_notes_by_signature",
        lambda *_a, **_k: [{"id": 42, "body": f"note\n{CONFIDENCE_COMMENT_SIGNATURE}"}],
    )

    def extraction_called(_description: str) -> dict[str, str]:
        raise RuntimeError("extract_required_inputs called")

    monkeypatch.setattr(app_mod, "extract_required_inputs", extraction_called)
    monkeypatch.setattr(
        app_mod,
        "generate_enhancement_payload",
        lambda **_kwargs: {
            "description": {"description_markdown": "### Summary\n\nIgnored.\n"},
            "review": {"suggestions": []},
            "confidence": {
                "effect_tags": [],
                "risk_level": "low",
                "optimization_areas": [],
                "missing_or_outdated_tests": [],
                "confidence_explanation": "ok",
            },
        },
    )
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: created_notes.append(kwargs["body"]))
    monkeypatch.setattr(app_mod, "update_mr_description", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_mod, "fetch_mr_versions", lambda *_args, **_kwargs: {"head_sha": "sha777"})

    app_mod.run()
    assert len(created_notes) == 1
    assert f"{CONFIDENCE_COMMENT_HEAD_SHA_PREFIX}sha777 -->" in created_notes[0]


def test_run_skips_template_and_required_inputs_for_confidence_history_only_incompatible_template(
    monkeypatch,
) -> None:
    created_notes: list[str] = []
    incompatible_description = "Manual content without required markers or required sections."

    monkeypatch.setenv("CI_COMMIT_SHA", "sha888")
    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: incompatible_description)
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: {})
    monkeypatch.setattr(
        app_mod,
        "fetch_mr_notes_by_signature",
        lambda *_a, **_k: [{"id": 43, "body": f"note\n{CONFIDENCE_COMMENT_SIGNATURE}"}],
    )

    def extraction_called(_description: str) -> dict[str, str]:
        raise RuntimeError("extract_required_inputs called")

    monkeypatch.setattr(app_mod, "extract_required_inputs", extraction_called)
    monkeypatch.setattr(
        app_mod,
        "generate_enhancement_payload",
        lambda **kwargs: {
            "description": {"description_markdown": ""},
            "review": {"suggestions": []},
            "confidence": {
                "effect_tags": ["ops"],
                "risk_level": "medium",
                "optimization_areas": [],
                "missing_or_outdated_tests": [],
                "confidence_explanation": f"issue={kwargs['extracted']['issue_key']!r}",
            },
        },
    )
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **kwargs: created_notes.append(kwargs["body"]))
    monkeypatch.setattr(app_mod, "update_mr_description", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_mod, "fetch_mr_versions", lambda *_args, **_kwargs: {"head_sha": "sha888"})

    app_mod.run()

    assert len(created_notes) == 1
    assert "issue=''" in created_notes[0]
    assert f"{CONFIDENCE_COMMENT_HEAD_SHA_PREFIX}sha888 -->" in created_notes[0]


def test_run_forwards_primary_and_alt_models_to_gemini(
    monkeypatch, minimal_mr_description: str, minimal_mr_changes: dict[str, Any]
) -> None:
    captured_models: list[tuple[str, str]] = []

    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    monkeypatch.setenv("GEMINI_ALT_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: minimal_mr_description)
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: minimal_mr_changes)
    monkeypatch.setattr(app_mod, "fetch_mr_notes_by_signature", lambda *_a, **_k: [])

    def fake_generate(**kwargs):
        captured_models.append((kwargs["model_name"], kwargs["fallback_model_name"]))
        return {
            "description": {"description_markdown": "### Summary\n\nAuto-filled body.\n"},
            "review": {"suggestions": []},
            "confidence": {
                "effect_tags": [],
                "risk_level": "low",
                "optimization_areas": [],
                "missing_or_outdated_tests": [],
                "confidence_explanation": "ok",
            },
        }

    monkeypatch.setattr(app_mod, "generate_enhancement_payload", fake_generate)
    monkeypatch.setattr(app_mod, "update_mr_description", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **_kwargs: {"id": 1})

    app_mod.run()

    assert captured_models == [("gemini-3-flash-preview", "gemini-2.5-flash")]


def test_run_fails_when_extracted_data_is_blank_in_strict_marker_path(
    monkeypatch, minimal_mr_description: str
) -> None:
    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: minimal_mr_description)
    monkeypatch.setattr(app_mod, "fetch_mr_notes_by_signature", lambda *_a, **_k: [])
    monkeypatch.setattr(
        app_mod,
        "extract_required_inputs",
        lambda _description: {"issue_key": "", "problem_brief": " ", "solution_brief": ""},
    )
    monkeypatch.setattr(app_mod, "fail", boom)

    with pytest.raises(RuntimeError, match="Missing extracted inputs while strict marker path is enabled"):
        app_mod.run()


def test_run_builds_plan_and_requests_only_enabled_sections(
    monkeypatch, minimal_mr_changes: dict[str, Any]
) -> None:
    captured_plan: list[tuple[bool, bool, bool]] = []
    mr_description = """<!-- auto-review:on -->

### Summary
Short summary.

### Issue Key
XX-1234

### Problem Brief
Problem.

### Solution Brief
Solution.

### How to Test
- [ ] Test

### Checklist
- [ ] I have tested these changes
"""

    monkeypatch.setattr(app_mod, "read_text_file", lambda _path: "file-content\n")
    monkeypatch.setattr(app_mod, "fetch_mr_description", lambda _e, _h: mr_description)
    monkeypatch.setattr(app_mod, "fetch_mr_notes_by_signature", lambda *_a, **_k: [])
    monkeypatch.setattr(app_mod, "fetch_mr_changes", lambda _e, _h: minimal_mr_changes)
    monkeypatch.setattr(app_mod, "fetch_mr_versions", lambda *_a, **_k: {"base_sha": "b", "start_sha": "s", "head_sha": "h"})
    monkeypatch.setattr(app_mod, "create_mr_inline_discussion", lambda **_kwargs: None)
    monkeypatch.setattr(app_mod, "update_mr_description", lambda *_a, **_k: None)
    monkeypatch.setattr(app_mod, "create_mr_note", lambda **_kwargs: {"id": 1})

    def fake_generate(**kwargs):
        plan = kwargs["plan"]
        captured_plan.append(
            (plan.request_description, plan.request_review, plan.request_confidence)
        )
        return {"review": {"suggestions": []}}

    monkeypatch.setattr(app_mod, "generate_enhancement_payload", fake_generate)
    app_mod.run()
    assert captured_plan == [(False, True, False)]
