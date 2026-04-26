"""Collect policy/input/diff context from MR."""

from typing import Any, Dict

from core.models import ConfidenceContext, ExecutionPolicy, ExtractedInputs


def fetch_policy_context(
    *,
    mr_endpoint: str,
    headers: dict[str, str],
    fetch_mr_description,
    fetch_mr_notes_by_signature,
    resolve_execution_policy,
    extract_leading_comment_markers,
    description_opt_in_marker: str,
    suggestions_opt_in_marker: str,
    confidence_comment_opt_in_marker: str,
    confidence_comment_signature: str,
    log,
) -> tuple[str, list[dict[str, Any]], ExecutionPolicy]:
    """Fetch MR description and resolve execution policy."""
    log("Fetching current merge request details...")
    current_description = fetch_mr_description(mr_endpoint, headers)
    log(f"Fetched MR description chars: {len(current_description)}")

    existing_confidence_notes = fetch_mr_notes_by_signature(
        mr_endpoint,
        headers,
        confidence_comment_signature,
    )
    policy = resolve_execution_policy(current_description, existing_confidence_notes)

    leading_markers = extract_leading_comment_markers(
        current_description,
        (
            description_opt_in_marker,
            suggestions_opt_in_marker,
            confidence_comment_opt_in_marker,
        ),
    )
    description_preview = current_description[:120].replace("\n", "\\n")
    log(
        "Auto marker status: "
        f"description_marker='{description_opt_in_marker}' enabled={policy.description_enabled}; "
        f"suggestions_marker='{suggestions_opt_in_marker}' enabled={policy.suggestions_enabled}; "
        f"confidence_comment_marker='{confidence_comment_opt_in_marker}' "
        f"enabled={policy.confidence_comment_marker_enabled}; "
        f"confidence_comment_history_detected={policy.confidence_comment_history_enabled}; "
        f"confidence_comment_history_only_mode={policy.confidence_history_only_mode}; "
        f"confidence_comment_effective_enabled={policy.confidence_comment_enabled}"
    )
    log(
        "Description marker leading-comment check: "
        f"marker found before first non-comment line = {policy.description_enabled}. "
        f"Description preview='{description_preview}'"
    )
    log(
        "Suggestions marker leading-comment check: "
        f"marker found before first non-comment line = {policy.suggestions_enabled}"
    )
    log(
        "Confidence comment marker leading-comment check: "
        f"marker found before first non-comment line = {policy.confidence_comment_marker_enabled}"
    )
    log(f"Markers detected in leading comment block: {sorted(leading_markers)}")
    return current_description, existing_confidence_notes, policy


def validate_template_and_inputs(
    *,
    current_description: str,
    policy: ExecutionPolicy,
    is_template_compatible,
    validate_template_requirements,
    extract_required_inputs,
    validate_extraction_requirements,
    fail,
    log,
) -> ExtractedInputs:
    """Apply template and extraction validation rules by resolved policy."""
    template_is_compatible = is_template_compatible(current_description)
    validate_template_requirements(policy, template_is_compatible)
    if policy.confidence_history_only_mode and not template_is_compatible:
        log(
            "Confidence history-only mode active: MR template is incompatible, "
            "skipping template enforcement and continuing with confidence-only flow."
        )

    extracted: ExtractedInputs = {
        "issue_key": "",
        "problem_brief": "",
        "solution_brief": "",
    }
    if policy.should_enforce_required_inputs:
        log("Parsing MR description for required inputs...")
        extracted = extract_required_inputs(current_description)
        log(
            "Extracted required inputs: "
            f"issue_key={extracted['issue_key']}, "
            f"problem_brief_chars={len(extracted['problem_brief'])}, "
            f"solution_brief_chars={len(extracted['solution_brief'])}"
        )
    elif policy.confidence_history_only_mode:
        log(
            "Confidence history-only mode active: required input extraction is skipped "
            "because description/suggestions/confidence marker are disabled."
        )

    extracted_missing_fields = validate_extraction_requirements(policy, extracted)
    if extracted_missing_fields and not policy.confidence_history_only_mode:
        fail(
            "Missing extracted inputs while strict marker path is enabled. "
            f"Missing/blank fields: {extracted_missing_fields}. "
            "Expected non-empty issue_key, problem_brief, and solution_brief."
        )
    if extracted_missing_fields and policy.confidence_history_only_mode:
        log(
            "Confidence history-only mode active: extracted inputs are blank and allowed "
            "for confidence-only generation."
        )
    return extracted


def fetch_diff_and_confidence(
    *,
    mr_endpoint: str,
    headers: dict[str, str],
    runtime_config,
    fetch_mr_changes,
    build_diff_context,
    summarize_change_signals_with_hints,
    compute_confidence_score,
    confidence_baseline: float,
    log,
) -> tuple[Dict[str, Any], str, ConfidenceContext]:
    """Fetch diff context and compute deterministic confidence."""
    diff_context = ""
    mr_changes: Dict[str, Any] = {}
    log("Fetching merge request diff context (source branch vs target branch)...")
    try:
        mr_changes = fetch_mr_changes(mr_endpoint, headers)
        diff_context = build_diff_context(mr_changes)
        if diff_context:
            log(f"Merge request diff context fetched successfully (chars={len(diff_context)}).")
        else:
            log("Merge request has no diff content; continuing with description-only context.")
    except SystemExit:
        log(
            "Warning: unable to fetch merge request diff context. "
            "Continuing with description-only prompt."
        )

    confidence_context: ConfidenceContext = {
        "score": confidence_baseline,
        "signals": {},
        "reasons": [],
    }
    if mr_changes:
        signal_summary = summarize_change_signals_with_hints(
            mr_changes=mr_changes,
            service_path_hints=runtime_config.service_path_hints,
            critical_path_hints=runtime_config.critical_path_hints,
            test_path_hints=runtime_config.test_path_hints,
        )
        confidence_context = compute_confidence_score(signal_summary)
    log(
        "Computed deterministic confidence: "
        f"score={confidence_context['score']}/10.0, "
        f"rules_triggered={len(confidence_context['reasons'])}"
    )
    return mr_changes, diff_context, confidence_context
