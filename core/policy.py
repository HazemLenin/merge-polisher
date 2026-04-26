"""Execution policy resolution and validation helpers."""

from typing import Any, List

from core.constants import (
    CONFIDENCE_COMMENT_OPT_IN_MARKER,
    DESCRIPTION_OPT_IN_MARKER,
    REQUIRED_EXTRACTED_FIELDS,
    SUGGESTIONS_OPT_IN_MARKER,
)
from core.models import ExecutionPolicy
from domain.mr.markers import is_marker_present
from core.runtime import fail


def resolve_execution_policy(
    current_description: str,
    existing_confidence_notes: List[dict[str, Any]],
) -> ExecutionPolicy:
    """Resolve marker/history based execution flags and enforcement rules."""
    description_enabled = is_marker_present(current_description, DESCRIPTION_OPT_IN_MARKER)
    suggestions_enabled = is_marker_present(current_description, SUGGESTIONS_OPT_IN_MARKER)
    confidence_comment_marker_enabled = is_marker_present(
        current_description,
        CONFIDENCE_COMMENT_OPT_IN_MARKER,
    )
    confidence_comment_history_enabled = bool(existing_confidence_notes)
    confidence_comment_enabled = (
        confidence_comment_marker_enabled or confidence_comment_history_enabled
    )
    confidence_history_only_mode = (
        confidence_comment_history_enabled and not confidence_comment_marker_enabled
    )
    should_enforce_template = description_enabled or suggestions_enabled
    should_enforce_required_inputs = (
        description_enabled or suggestions_enabled or confidence_comment_marker_enabled
    )

    return ExecutionPolicy(
        description_enabled=description_enabled,
        suggestions_enabled=suggestions_enabled,
        confidence_comment_marker_enabled=confidence_comment_marker_enabled,
        confidence_comment_history_enabled=confidence_comment_history_enabled,
        confidence_comment_enabled=confidence_comment_enabled,
        confidence_history_only_mode=confidence_history_only_mode,
        should_enforce_template=should_enforce_template,
        should_enforce_required_inputs=should_enforce_required_inputs,
    )


def validate_template_requirements(
    policy: ExecutionPolicy,
    template_is_compatible: bool,
) -> None:
    """Enforce template constraints based on resolved policy."""
    if policy.should_enforce_template and not template_is_compatible:
        fail(
            "MR description does not match required AutoDescriptor template markers. "
            "Auto-description is aborted."
        )


def validate_extraction_requirements(
    policy: ExecutionPolicy,
    extracted: dict[str, str],
) -> list[str]:
    """Return missing extracted fields under resolved policy constraints."""
    extracted_missing_fields = [
        field
        for field in REQUIRED_EXTRACTED_FIELDS
        if not str(extracted.get(field, "") or "").strip()
    ]
    return extracted_missing_fields
