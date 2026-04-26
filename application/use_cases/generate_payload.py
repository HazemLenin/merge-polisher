"""Generate and normalize Gemini payload for publishers."""

from typing import Any

from core.models import ConfidenceContext, ExecutionPolicy, ExtractedInputs, GenerationPlan


def generate_and_normalize_payload(
    *,
    model_name: str,
    alt_model_name: str,
    current_description: str,
    output_template: str,
    llm_guide: str,
    extracted: ExtractedInputs,
    diff_context: str,
    confidence_context: ConfidenceContext,
    policy: ExecutionPolicy,
    generation_plan: GenerationPlan,
    generate_enhancement_payload,
    normalize_suggestions,
    normalize_effect_tags,
    normalize_risk_level,
    normalize_string_list,
    log,
) -> tuple[str, list[dict[str, Any]], list[str], str, str, list[str], list[str]]:
    """Generate payload with Gemini and normalize all consumed fields."""
    log(f"Generating MR enhancement payload using model: {model_name}")
    generated_payload = generate_enhancement_payload(
        model_name=model_name,
        fallback_model_name=alt_model_name,
        current_description=current_description,
        output_template=output_template,
        llm_guide=llm_guide,
        extracted=extracted,
        diff_context=diff_context,
        confidence_context=confidence_context,
        plan=generation_plan,
        allow_missing_extracted=policy.confidence_history_only_mode,
    )
    description_section = generated_payload.get("description") or {}
    review_section = generated_payload.get("review") or {}
    confidence_section = generated_payload.get("confidence") or {}
    generated_description = str(description_section.get("description_markdown") or "").strip()
    generated_suggestions = normalize_suggestions(review_section.get("suggestions"))
    generated_effect_tags = normalize_effect_tags(confidence_section.get("effect_tags"))
    generated_risk_level = normalize_risk_level(confidence_section.get("risk_level"))
    generated_confidence_explanation = str(
        confidence_section.get("confidence_explanation") or ""
    ).strip()
    generated_optimization_areas = normalize_string_list(
        confidence_section.get("optimization_areas")
    )
    generated_missing_tests = normalize_string_list(
        confidence_section.get("missing_or_outdated_tests")
    )
    log(
        "Gemini payload normalized: "
        f"description_chars={len(generated_description)}, "
        f"suggestions_count={len(generated_suggestions)}, "
        f"effect_tags={generated_effect_tags}, risk_level='{generated_risk_level}'"
    )
    return (
        generated_description,
        generated_suggestions,
        generated_effect_tags,
        generated_risk_level,
        generated_confidence_explanation,
        generated_optimization_areas,
        generated_missing_tests,
    )
