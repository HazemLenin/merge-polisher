"""Confidence-domain helpers for deterministic MR score computation."""

from typing import Any, Dict

from core.constants import (
    CONFIDENCE_BASELINE,
    CONFIDENCE_LARGE_DIFF_THRESHOLD,
    CONFIDENCE_LARGE_SERVICE_DIFF_THRESHOLD,
    CONFIDENCE_MAX,
    CONFIDENCE_MEDIUM_DIFF_THRESHOLD,
    CONFIDENCE_MIN,
    CONFIDENCE_SMALL_DIFF_THRESHOLD,
    CONFIDENCE_WEIGHT_CRITICAL_FILE,
    CONFIDENCE_WEIGHT_HAS_TEST_CHANGES,
    CONFIDENCE_WEIGHT_HUGE_DIFF,
    CONFIDENCE_WEIGHT_LARGE_DIFF,
    CONFIDENCE_WEIGHT_LARGE_SERVICE_FILE,
    CONFIDENCE_WEIGHT_MEDIUM_DIFF,
    CONFIDENCE_WEIGHT_NO_TESTS_WITH_LARGE_LOGIC,
    CONFIDENCE_WEIGHT_SERVICE_FILE,
    CONFIDENCE_WEIGHT_SMALL_DIFF,
    CONFIDENCE_WEIGHT_WIDE_CHANGESET,
    CONFIDENCE_WIDE_FILESET_THRESHOLD,
    CRITICAL_PATH_HINTS,
    SERVICE_PATH_HINTS,
    TEST_PATH_HINTS,
)


def _is_path_match(path: str, hints: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(hint in normalized for hint in hints)


def summarize_change_signals(mr_changes: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize deterministic diff signals used in confidence scoring."""
    return summarize_change_signals_with_hints(
        mr_changes=mr_changes,
        service_path_hints=SERVICE_PATH_HINTS,
        critical_path_hints=CRITICAL_PATH_HINTS,
        test_path_hints=TEST_PATH_HINTS,
    )


def summarize_change_signals_with_hints(
    *,
    mr_changes: Dict[str, Any],
    service_path_hints: tuple[str, ...],
    critical_path_hints: tuple[str, ...],
    test_path_hints: tuple[str, ...],
) -> Dict[str, Any]:
    """Summarize deterministic diff signals using runtime path hint sets."""
    changes = mr_changes.get("changes")
    if not isinstance(changes, list):
        return {
            "files_touched": 0,
            "total_added_lines": 0,
            "total_removed_lines": 0,
            "total_changed_lines": 0,
            "service_files_touched": 0,
            "large_service_files": 0,
            "critical_files_touched": 0,
            "test_files_touched": 0,
            "has_test_changes": False,
        }

    summary = {
        "files_touched": 0,
        "total_added_lines": 0,
        "total_removed_lines": 0,
        "total_changed_lines": 0,
        "service_files_touched": 0,
        "large_service_files": 0,
        "critical_files_touched": 0,
        "test_files_touched": 0,
        "has_test_changes": False,
    }

    for change in changes:
        if not isinstance(change, dict):
            continue
        new_path = str(change.get("new_path") or change.get("old_path") or "").strip()
        if not new_path:
            continue
        summary["files_touched"] += 1
        diff_lines = str(change.get("diff") or "").splitlines()

        added = 0
        removed = 0
        for line in diff_lines:
            if line.startswith("+++ ") or line.startswith("--- "):
                continue
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
        changed_lines = added + removed

        summary["total_added_lines"] += added
        summary["total_removed_lines"] += removed
        summary["total_changed_lines"] += changed_lines

        if _is_path_match(new_path, service_path_hints):
            summary["service_files_touched"] += 1
            if changed_lines >= CONFIDENCE_LARGE_SERVICE_DIFF_THRESHOLD:
                summary["large_service_files"] += 1
        if _is_path_match(new_path, critical_path_hints):
            summary["critical_files_touched"] += 1
        if _is_path_match(new_path, test_path_hints):
            summary["test_files_touched"] += 1

    summary["has_test_changes"] = summary["test_files_touched"] > 0
    return summary


def compute_confidence_score(signals: Dict[str, Any]) -> Dict[str, Any]:
    """Compute deterministic confidence score and reasons on 0.0-10.0 scale."""
    score = CONFIDENCE_BASELINE
    reasons: list[dict[str, Any]] = []
    changed_lines = int(signals.get("total_changed_lines", 0))
    files_touched = int(signals.get("files_touched", 0))
    service_files = int(signals.get("service_files_touched", 0))
    large_service_files = int(signals.get("large_service_files", 0))
    critical_files = int(signals.get("critical_files_touched", 0))
    has_test_changes = bool(signals.get("has_test_changes", False))

    def apply_rule(rule: str, weight: float, why: str) -> None:
        nonlocal score
        score += weight
        reasons.append({"rule": rule, "weight": round(weight, 2), "reason": why})

    if changed_lines <= CONFIDENCE_SMALL_DIFF_THRESHOLD:
        apply_rule("small_diff_scope", CONFIDENCE_WEIGHT_SMALL_DIFF, "Limited diff scope.")
    elif changed_lines <= CONFIDENCE_MEDIUM_DIFF_THRESHOLD:
        apply_rule("medium_diff_scope", CONFIDENCE_WEIGHT_MEDIUM_DIFF, "Moderate diff size.")
    elif changed_lines <= CONFIDENCE_LARGE_DIFF_THRESHOLD:
        apply_rule(
            "large_diff_scope", CONFIDENCE_WEIGHT_LARGE_DIFF, "Large diff increases review risk."
        )
    else:
        apply_rule(
            "huge_diff_scope",
            CONFIDENCE_WEIGHT_HUGE_DIFF,
            "Very large diff increases uncertainty.",
        )

    if files_touched >= CONFIDENCE_WIDE_FILESET_THRESHOLD:
        apply_rule(
            "wide_changeset",
            CONFIDENCE_WEIGHT_WIDE_CHANGESET,
            "Many files changed across the merge request.",
        )
    if service_files > 0:
        apply_rule(
            "service_logic_touched",
            CONFIDENCE_WEIGHT_SERVICE_FILE * service_files,
            "Service/business logic files were modified.",
        )
    if large_service_files > 0:
        apply_rule(
            "large_service_logic_delta",
            CONFIDENCE_WEIGHT_LARGE_SERVICE_FILE * large_service_files,
            "Large service deltas increase confidence risk.",
        )
    if critical_files > 0:
        apply_rule(
            "critical_paths_touched",
            CONFIDENCE_WEIGHT_CRITICAL_FILE * critical_files,
            "Sensitive or critical paths were updated.",
        )
    if has_test_changes:
        apply_rule(
            "test_updates_present",
            CONFIDENCE_WEIGHT_HAS_TEST_CHANGES,
            "Changed scope includes test updates.",
        )
    elif changed_lines >= CONFIDENCE_LARGE_DIFF_THRESHOLD or large_service_files > 0:
        apply_rule(
            "no_tests_for_substantial_logic",
            CONFIDENCE_WEIGHT_NO_TESTS_WITH_LARGE_LOGIC,
            "Substantial logic changed without visible test updates.",
        )

    bounded = max(CONFIDENCE_MIN, min(CONFIDENCE_MAX, score))
    return {
        "score": round(bounded, 1),
        "reasons": reasons,
        "signals": signals,
    }
