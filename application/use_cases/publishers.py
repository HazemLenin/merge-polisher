"""Publish generated outputs to GitLab."""

from typing import Any

from core.models import ConfidenceContext, ExecutionPolicy


def publish_confidence_comment_if_enabled(
    *,
    policy: ExecutionPolicy,
    mr_endpoint: str,
    headers: dict[str, str],
    existing_confidence_notes: list[dict[str, Any]],
    confidence_context: ConfidenceContext,
    generated_risk_level: str,
    generated_effect_tags: list[str],
    generated_confidence_explanation: str,
    generated_optimization_areas: list[str],
    generated_missing_tests: list[str],
    env_getter,
    fetch_mr_versions,
    build_confidence_comment_body,
    confidence_comment_signature: str,
    confidence_comment_head_sha_prefix: str,
    get_latest_note_by_id,
    extract_sha_from_note_body,
    create_mr_note,
    log,
) -> None:
    """Create confidence note when enabled and dedupe by head SHA."""
    if not policy.confidence_comment_enabled:
        return

    current_head_sha = env_getter("CI_COMMIT_SHA", "").strip()
    if not current_head_sha:
        try:
            current_head_sha = fetch_mr_versions(mr_endpoint, headers)["head_sha"]
        except SystemExit:
            current_head_sha = "unknown-head-sha"

    confidence_comment = build_confidence_comment_body(
        confidence_score=float(confidence_context["score"]),
        risk_level=generated_risk_level,
        effect_tags=generated_effect_tags,
        confidence_explanation=generated_confidence_explanation,
        confidence_reasons=list(confidence_context.get("reasons", [])),
        optimization_areas=generated_optimization_areas,
        missing_or_outdated_tests=generated_missing_tests,
        signature=confidence_comment_signature,
        head_sha=current_head_sha,
        sha_marker_prefix=confidence_comment_head_sha_prefix,
    )
    try:
        latest_confidence_note = get_latest_note_by_id(existing_confidence_notes)
        latest_sha = None
        if latest_confidence_note:
            latest_sha = extract_sha_from_note_body(
                str(latest_confidence_note.get("body") or ""),
                confidence_comment_head_sha_prefix,
            )
        if latest_sha and latest_sha == current_head_sha:
            log(
                "Confidence comment already exists for this commit SHA; "
                "skipping new confidence note creation."
            )
            return

        create_mr_note(
            endpoint=mr_endpoint,
            headers=headers,
            body=confidence_comment,
        )
        log("Confidence comment created successfully.")
    except SystemExit:
        log(
            "Warning: unable to create confidence comment note. "
            "Continuing with existing pipeline behavior."
        )


def publish_description_if_enabled(
    *,
    policy: ExecutionPolicy,
    mr_endpoint: str,
    headers: dict[str, str],
    generated_description: str,
    update_mr_description,
    fail,
    log,
) -> None:
    """Publish MR description when enabled."""
    if policy.description_enabled:
        if not generated_description:
            fail("Gemini response is missing 'description_markdown' while description is enabled.")
        log("Updating merge request description...")
        update_mr_description(mr_endpoint, headers, generated_description)
        log("MR description was successfully enhanced and updated.")
        return
    log("Description marker disabled. Skipping MR description update.")


def publish_inline_suggestions_if_enabled(
    *,
    policy: ExecutionPolicy,
    mr_endpoint: str,
    headers: dict[str, str],
    generated_suggestions: list[dict[str, Any]],
    diff_context: str,
    mr_changes: dict[str, Any],
    fetch_mr_versions,
    build_changed_new_lines,
    normalize_inline_suggestion_code,
    create_mr_inline_discussion,
    log,
) -> None:
    """Publish inline suggestions only when enabled and on changed lines."""
    if not policy.suggestions_enabled:
        log("Suggestions marker disabled. Skipping inline suggestions.")
        return
    if not generated_suggestions:
        log("No valid suggestions returned by Gemini. Skipping inline suggestions.")
        return
    if not diff_context:
        log("Diff context unavailable. Skipping inline suggestions.")
        return

    versions = fetch_mr_versions(mr_endpoint, headers)
    changed_new_lines = build_changed_new_lines(mr_changes)
    log(
        "Prepared inline suggestion context: "
        f"files_with_changed_lines={len(changed_new_lines)}"
    )
    posted = 0

    for suggestion in generated_suggestions:
        file_path = suggestion["file_path"]
        new_line = suggestion["new_line"]
        summary = str(suggestion.get("summary") or "").strip()
        suggested_code = str(suggestion.get("suggested_code") or "")
        normalized_path = file_path.replace("\\", "/")
        allowed_lines = (
            changed_new_lines.get(normalized_path)
            or changed_new_lines.get(file_path)
            or set()
        )
        if new_line not in allowed_lines:
            log(f"Skipping suggestion (not a changed line): {file_path}:{new_line}")
            continue
        if not summary:
            log(f"Skipping suggestion (missing summary): {file_path}:{new_line}")
            continue
        aligned_code = normalize_inline_suggestion_code(
            mr_changes, normalized_path, new_line, suggested_code
        )
        if not aligned_code.strip():
            log(f"Skipping suggestion (empty suggested_code after normalization): {file_path}:{new_line}")
            continue
        try:
            create_mr_inline_discussion(
                endpoint=mr_endpoint,
                headers=headers,
                file_path=normalized_path,
                new_line=new_line,
                versions=versions,
                summary=summary,
                suggested_code=aligned_code,
            )
            posted += 1
        except SystemExit:
            log(f"Skipping suggestion due to GitLab API failure: {file_path}:{new_line}")
            continue

    log(f"Inline suggestions published: {posted}/{len(generated_suggestions)}")
