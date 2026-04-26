"""Main application orchestration for MR description enhancement."""

import os
from typing import Any

from application.use_cases.build_generation_plan import build_generation_plan
from application.use_cases.collect_mr_context import (
    fetch_diff_and_confidence,
    fetch_policy_context,
    validate_template_and_inputs,
)
from application.use_cases.generate_payload import generate_and_normalize_payload
from application.use_cases.load_runtime_context import load_runtime_context
from application.use_cases.publishers import (
    publish_confidence_comment_if_enabled,
    publish_description_if_enabled,
    publish_inline_suggestions_if_enabled,
)
from adapters.gitlab.client import (
    build_changed_new_lines,
    create_mr_inline_discussion,
    create_mr_note,
    extract_sha_from_note_body,
    fetch_mr_changes,
    fetch_mr_description,
    fetch_mr_notes_by_signature,
    fetch_mr_versions,
    get_latest_note_by_id,
    normalize_inline_suggestion_code,
    update_mr_description,
)
from adapters.io.env_reader import read_required_env
from adapters.io.file_reader import read_text_file
from adapters.llm.gemini_client import generate_enhancement_payload
from adapters.vcs.provider import resolve_vcs_client
from core.config import load_runtime_config
from core.constants import (
    CONFIDENCE_BASELINE,
    CONFIDENCE_COMMENT_HEAD_SHA_PREFIX,
    CONFIDENCE_COMMENT_OPT_IN_MARKER,
    CONFIDENCE_COMMENT_SIGNATURE,
    DEFAULT_ALT_MODEL,
    DEFAULT_PRIMARY_MODEL,
    DEFAULT_TEMPLATE_PATH,
    DESCRIPTION_OPT_IN_MARKER,
    LLM_GUIDE_PATH,
    SUGGESTIONS_OPT_IN_MARKER,
)
from core.policy import (
    resolve_execution_policy,
    validate_extraction_requirements,
    validate_template_requirements,
)
from core.runtime import fail, log
from domain.confidence.scoring import compute_confidence_score, summarize_change_signals_with_hints
from domain.description.confidence_comment import build_confidence_comment_body
from domain.description.normalization import (
    normalize_effect_tags,
    normalize_risk_level,
    normalize_string_list,
    normalize_suggestions,
)
from domain.mr.markers import extract_leading_comment_markers
from domain.mr.parser import extract_required_inputs, is_template_compatible


def _publish_confidence_comment_if_enabled(
    *,
    policy,
    mr_endpoint: str,
    headers: dict[str, str],
    existing_confidence_notes: list[dict[str, Any]],
    confidence_context,
    generated_risk_level: str,
    generated_effect_tags: list[str],
    generated_confidence_explanation: str,
    generated_optimization_areas: list[str],
    generated_missing_tests: list[str],
) -> None:
    """Backward-compatible wrapper for tests and existing call sites."""
    publish_confidence_comment_if_enabled(
        policy=policy,
        mr_endpoint=mr_endpoint,
        headers=headers,
        existing_confidence_notes=existing_confidence_notes,
        confidence_context=confidence_context,
        generated_risk_level=generated_risk_level,
        generated_effect_tags=generated_effect_tags,
        generated_confidence_explanation=generated_confidence_explanation,
        generated_optimization_areas=generated_optimization_areas,
        generated_missing_tests=generated_missing_tests,
        env_getter=os.getenv,
        fetch_mr_versions=fetch_mr_versions,
        build_confidence_comment_body=build_confidence_comment_body,
        confidence_comment_signature=CONFIDENCE_COMMENT_SIGNATURE,
        confidence_comment_head_sha_prefix=CONFIDENCE_COMMENT_HEAD_SHA_PREFIX,
        get_latest_note_by_id=get_latest_note_by_id,
        extract_sha_from_note_body=extract_sha_from_note_body,
        create_mr_note=create_mr_note,
        log=log,
    )


def _publish_inline_suggestions_if_enabled(
    *,
    policy,
    mr_endpoint: str,
    headers: dict[str, str],
    generated_suggestions: list[dict[str, Any]],
    diff_context: str,
    mr_changes: dict[str, Any],
) -> None:
    """Backward-compatible wrapper for tests and existing call sites."""
    publish_inline_suggestions_if_enabled(
        policy=policy,
        mr_endpoint=mr_endpoint,
        headers=headers,
        generated_suggestions=generated_suggestions,
        diff_context=diff_context,
        mr_changes=mr_changes,
        fetch_mr_versions=fetch_mr_versions,
        build_changed_new_lines=build_changed_new_lines,
        normalize_inline_suggestion_code=normalize_inline_suggestion_code,
        create_mr_inline_discussion=create_mr_inline_discussion,
        log=log,
    )


def run() -> None:
    """Execute the full CI flow: validate, generate, and update MR text."""
    log("Starting auto-descriptor pipeline run.")
    (
        vcs_client,
        mr_endpoint,
        headers,
        llm_guide,
        output_template,
        model_name,
        alt_model_name,
    ) = load_runtime_context(
        read_required_env=read_required_env,
        env_getter=os.getenv,
        resolve_vcs_client=resolve_vcs_client,
        read_text_file=read_text_file,
        llm_guide_path=LLM_GUIDE_PATH,
        template_path=DEFAULT_TEMPLATE_PATH,
        default_primary_model=DEFAULT_PRIMARY_MODEL,
        default_alt_model=DEFAULT_ALT_MODEL,
        log=log,
    )
    runtime_config = load_runtime_config()
    fetch_description = vcs_client.fetch_description
    fetch_notes_by_signature = vcs_client.fetch_notes_by_signature
    fetch_changes = vcs_client.fetch_changes
    build_diff_context = vcs_client.build_diff_context
    fetch_versions = vcs_client.fetch_versions
    build_changed_lines = vcs_client.build_changed_new_lines
    normalize_suggestion = vcs_client.normalize_inline_suggestion_code
    create_inline_discussion = vcs_client.create_inline_discussion
    update_description = vcs_client.update_description
    get_latest_note = vcs_client.get_latest_note_by_id
    extract_sha = vcs_client.extract_sha_from_note_body
    create_note = vcs_client.create_note

    # Keep legacy monkeypatch points for existing GitLab-oriented tests.
    if vcs_client.provider_name == "gitlab":
        fetch_description = fetch_mr_description
        fetch_notes_by_signature = fetch_mr_notes_by_signature
        fetch_changes = fetch_mr_changes
        fetch_versions = fetch_mr_versions
        build_changed_lines = build_changed_new_lines
        normalize_suggestion = normalize_inline_suggestion_code
        create_inline_discussion = create_mr_inline_discussion
        update_description = update_mr_description
        get_latest_note = get_latest_note_by_id
        extract_sha = extract_sha_from_note_body
        create_note = create_mr_note

    current_description, existing_confidence_notes, policy = fetch_policy_context(
        mr_endpoint=mr_endpoint,
        headers=headers,
        fetch_mr_description=fetch_description,
        fetch_mr_notes_by_signature=fetch_notes_by_signature,
        resolve_execution_policy=resolve_execution_policy,
        extract_leading_comment_markers=extract_leading_comment_markers,
        description_opt_in_marker=DESCRIPTION_OPT_IN_MARKER,
        suggestions_opt_in_marker=SUGGESTIONS_OPT_IN_MARKER,
        confidence_comment_opt_in_marker=CONFIDENCE_COMMENT_OPT_IN_MARKER,
        confidence_comment_signature=CONFIDENCE_COMMENT_SIGNATURE,
        log=log,
    )
    if not (
        policy.description_enabled
        or policy.suggestions_enabled
        or policy.confidence_comment_enabled
    ):
        log(
            "Skipping auto descriptor: MR has no enabled auto markers "
            f"({DESCRIPTION_OPT_IN_MARKER} or {SUGGESTIONS_OPT_IN_MARKER} "
            f"or {CONFIDENCE_COMMENT_OPT_IN_MARKER})."
        )
        return

    generation_plan = build_generation_plan(policy)
    extracted = validate_template_and_inputs(
        current_description=current_description,
        policy=policy,
        is_template_compatible=is_template_compatible,
        validate_template_requirements=validate_template_requirements,
        extract_required_inputs=extract_required_inputs,
        validate_extraction_requirements=validate_extraction_requirements,
        fail=fail,
        log=log,
    )
    mr_changes, diff_context, confidence_context = fetch_diff_and_confidence(
        mr_endpoint=mr_endpoint,
        headers=headers,
        runtime_config=runtime_config,
        fetch_mr_changes=fetch_changes,
        build_diff_context=build_diff_context,
        summarize_change_signals_with_hints=summarize_change_signals_with_hints,
        compute_confidence_score=compute_confidence_score,
        confidence_baseline=CONFIDENCE_BASELINE,
        log=log,
    )
    (
        generated_description,
        generated_suggestions,
        generated_effect_tags,
        generated_risk_level,
        generated_confidence_explanation,
        generated_optimization_areas,
        generated_missing_tests,
    ) = generate_and_normalize_payload(
        model_name=model_name,
        alt_model_name=alt_model_name,
        current_description=current_description,
        output_template=output_template,
        llm_guide=llm_guide,
        extracted=extracted,
        diff_context=diff_context,
        confidence_context=confidence_context,
        policy=policy,
        generation_plan=generation_plan,
        generate_enhancement_payload=generate_enhancement_payload,
        normalize_suggestions=normalize_suggestions,
        normalize_effect_tags=normalize_effect_tags,
        normalize_risk_level=normalize_risk_level,
        normalize_string_list=normalize_string_list,
        log=log,
    )
    publish_confidence_comment_if_enabled(
        policy=policy,
        mr_endpoint=mr_endpoint,
        headers=headers,
        existing_confidence_notes=existing_confidence_notes,
        confidence_context=confidence_context,
        generated_risk_level=generated_risk_level,
        generated_effect_tags=generated_effect_tags,
        generated_confidence_explanation=generated_confidence_explanation,
        generated_optimization_areas=generated_optimization_areas,
        generated_missing_tests=generated_missing_tests,
        env_getter=os.getenv,
        fetch_mr_versions=fetch_versions,
        build_confidence_comment_body=build_confidence_comment_body,
        confidence_comment_signature=CONFIDENCE_COMMENT_SIGNATURE,
        confidence_comment_head_sha_prefix=CONFIDENCE_COMMENT_HEAD_SHA_PREFIX,
        get_latest_note_by_id=get_latest_note,
        extract_sha_from_note_body=extract_sha,
        create_mr_note=create_note,
        log=log,
    )
    publish_description_if_enabled(
        policy=policy,
        mr_endpoint=mr_endpoint,
        headers=headers,
        generated_description=generated_description,
        update_mr_description=update_description,
        fail=fail,
        log=log,
    )
    publish_inline_suggestions_if_enabled(
        policy=policy,
        mr_endpoint=mr_endpoint,
        headers=headers,
        generated_suggestions=generated_suggestions,
        diff_context=diff_context,
        mr_changes=mr_changes,
        fetch_mr_versions=fetch_versions,
        build_changed_new_lines=build_changed_lines,
        normalize_inline_suggestion_code=normalize_suggestion,
        create_mr_inline_discussion=create_inline_discussion,
        log=log,
    )
