"""Unit tests for execution policy resolution and policy validations."""

import core.policy as policy
from core.models import ExecutionPolicy


def _strict_policy() -> ExecutionPolicy:
    return ExecutionPolicy(
        description_enabled=True,
        suggestions_enabled=False,
        confidence_comment_marker_enabled=False,
        confidence_comment_history_enabled=False,
        confidence_comment_enabled=False,
        confidence_history_only_mode=False,
        should_enforce_template=True,
        should_enforce_required_inputs=True,
    )


def test_resolve_execution_policy_all_markers_enabled(minimal_mr_description: str) -> None:
    resolved = policy.resolve_execution_policy(minimal_mr_description, [])
    assert resolved.description_enabled is True
    assert resolved.suggestions_enabled is True
    assert resolved.confidence_comment_marker_enabled is True
    assert resolved.confidence_comment_history_enabled is False
    assert resolved.confidence_comment_enabled is True
    assert resolved.confidence_history_only_mode is False
    assert resolved.should_enforce_template is True
    assert resolved.should_enforce_required_inputs is True


def test_resolve_execution_policy_history_only_mode(
    mr_description_no_auto_markers: str,
) -> None:
    resolved = policy.resolve_execution_policy(
        mr_description_no_auto_markers,
        [{"id": 1, "body": "note"}],
    )
    assert resolved.description_enabled is False
    assert resolved.suggestions_enabled is False
    assert resolved.confidence_comment_marker_enabled is False
    assert resolved.confidence_comment_history_enabled is True
    assert resolved.confidence_comment_enabled is True
    assert resolved.confidence_history_only_mode is True
    assert resolved.should_enforce_template is False
    assert resolved.should_enforce_required_inputs is False


def test_validate_template_requirements_fails_when_required_and_incompatible() -> None:
    strict = _strict_policy()

    import pytest

    with pytest.raises(SystemExit):
        policy.validate_template_requirements(strict, template_is_compatible=False)


def test_validate_extraction_requirements_allows_missing_in_history_only() -> None:
    history_only = ExecutionPolicy(
        description_enabled=False,
        suggestions_enabled=False,
        confidence_comment_marker_enabled=False,
        confidence_comment_history_enabled=True,
        confidence_comment_enabled=True,
        confidence_history_only_mode=True,
        should_enforce_template=False,
        should_enforce_required_inputs=False,
    )
    missing = policy.validate_extraction_requirements(
        history_only,
        {"issue_key": "", "problem_brief": "", "solution_brief": ""},
    )
    assert missing == ["issue_key", "problem_brief", "solution_brief"]
