"""Gemini generation client for single-call MR enhancement output."""

import json
import time
from typing import Any, Dict, Optional

from google import genai

from core.constants import (
    DEFAULT_ALT_MODEL,
    DEFAULT_PRIMARY_MODEL,
    MAX_INLINE_SUGGESTIONS,
    REQUIRED_EXTRACTED_FIELDS,
)
from core.models import (
    ConfidenceContext,
    ExtractedInputs,
    GenerationPlan,
    NestedEnhancementPayload,
)
from core.runtime import fail, graceful_exit, log


def validate_models(model_name: str, fallback_model_name: str) -> None:
    """Enforce strict primary/alt model policy."""
    allowed = {model_name, fallback_model_name}
    expected = {DEFAULT_PRIMARY_MODEL, DEFAULT_ALT_MODEL}
    if allowed != expected:
        fail(
            "Unsupported Gemini model configuration. "
            f"Expected primary/alt pair {sorted(expected)}, "
            f"got {sorted(allowed)}."
        )


def build_single_call_prompt(
    current_description: str,
    output_template: str,
    llm_guide: str,
    extracted: ExtractedInputs,
    diff_context: str,
    confidence_context: ConfidenceContext,
    plan: GenerationPlan,
) -> str:
    """Build compact prompt that returns both description and suggestions as JSON."""
    schema_lines: list[str] = ["{"]
    if plan.request_description:
        schema_lines.append('  "description": {')
        schema_lines.append('    "description_markdown": "string"')
        schema_lines.append("  },")
    if plan.request_review:
        schema_lines.append('  "review": {')
        schema_lines.append('    "suggestions": [')
        schema_lines.append("      {")
        schema_lines.append('        "file_path": "string",')
        schema_lines.append('        "new_line": 123,')
        schema_lines.append('        "summary": "short review note",')
        schema_lines.append('        "suggested_code": "replacement snippet"')
        schema_lines.append("      }")
        schema_lines.append("    ]")
        schema_lines.append("  },")
    if plan.request_confidence:
        schema_lines.append('  "confidence": {')
        schema_lines.append('    "effect_tags": ["bugfix|feature|refactor|perf|security|docs"],')
        schema_lines.append('    "risk_level": "low|medium|high|critical",')
        schema_lines.append('    "optimization_areas": ["high-level optimization opportunity"],')
        schema_lines.append(
            '    "missing_or_outdated_tests": ["missing or stale test note from changed scope only"],'
        )
        schema_lines.append(
            '    "confidence_explanation": "brief score rationale tied to triggered confidence rules"'
        )
        schema_lines.append("  },")
    if schema_lines[-1].endswith(","):
        schema_lines[-1] = schema_lines[-1][:-1]
    schema_lines.append("}")
    schema = "\n".join(schema_lines)

    rules = []
    if plan.request_review:
        rules.extend(
            [
                f"- Max {MAX_INLINE_SUGGESTIONS} suggestions.",
                "- Suggestions must target changed lines only.",
                "- Each suggestion summary must be a concise full sentence (minimum one sentence, maximum two).",
                "- suggested_code can be multiline and must contain only the exact replacement snippet.",
                "- Do not include unchanged surrounding lines in suggested_code.",
                "- Preserve valid indentation and internal block structure in suggested_code.",
            ]
        )
    if plan.request_description:
        rules.append("- Keep description grounded in provided context and output template.")
    if plan.request_confidence:
        rules.extend(
            [
                "- Keep missing test notes constrained to changed scope only.",
                "- Keep optimization areas high-level (architecture/perf/maintainability).",
                "- Explain confidence using provided score/rules; do not compute another score.",
            ]
        )
    rules.append("- Use concise text.")
    rules.append("- Do not include markdown fences around JSON.")

    return f"""
Return only strict JSON with this schema:
{schema}

Rules:
{chr(10).join(rules)}

Issue key: {extracted["issue_key"]}
Problem brief: {extracted["problem_brief"]}
Solution brief: {extracted["solution_brief"]}

Template:
{output_template}

Guide:
{llm_guide}

Current MR description:
{current_description}

Diff context:
{diff_context or "Unavailable"}

Deterministic confidence context (computed by Python):
{json.dumps(confidence_context, ensure_ascii=True)}
""".strip()


def validate_extracted_inputs(
    extracted: Dict[str, str], allow_missing_extracted: bool = False
) -> ExtractedInputs:
    """Validate extracted fields for prompt generation."""
    normalized = {field: str(extracted.get(field, "") or "").strip() for field in REQUIRED_EXTRACTED_FIELDS}
    issue_key = str(extracted.get("issue_key", "") or "").strip()
    missing_fields = [field for field, value in normalized.items() if not value]
    if missing_fields and not allow_missing_extracted:
        fail(
            "Extracted MR inputs are required in strict mode, but missing/blank fields were found: "
            f"{missing_fields}. "
            "Expected non-empty problem_brief and solution_brief."
        )
    return {
        "issue_key": issue_key,
        "problem_brief": normalized["problem_brief"],
        "solution_brief": normalized["solution_brief"],
    }


def generate_enhancement_payload(
    model_name: str,
    fallback_model_name: str,
    current_description: str,
    output_template: str,
    llm_guide: str,
    extracted: Dict[str, str],
    diff_context: str,
    confidence_context: ConfidenceContext,
    plan: GenerationPlan,
    allow_missing_extracted: bool = False,
    retries: int = 3,
) -> NestedEnhancementPayload:
    """Generate and parse payload, with model fallback on API failures."""
    validate_models(model_name, fallback_model_name)
    validated_extracted = validate_extracted_inputs(
        extracted, allow_missing_extracted=allow_missing_extracted
    )
    prompt = build_single_call_prompt(
        current_description,
        output_template,
        llm_guide,
        validated_extracted,
        diff_context,
        confidence_context,
        plan,
    )

    try:
        return _generate_with_model(model_name, prompt, retries, plan)
    except Exception as primary_error:  # noqa: BLE001
        if not _is_api_error(primary_error):
            fail(f"Gemini generation failed after {retries} attempts: {primary_error}")
        log(
            "Primary Gemini model failed after retries with API error; "
            f"falling back from '{model_name}' to '{fallback_model_name}'."
        )
        try:
            return _generate_with_model(fallback_model_name, prompt, retries, plan)
        except Exception as fallback_error:  # noqa: BLE001
            if _is_high_demand_error(fallback_error):
                graceful_exit(
                    "Gemini models are temporarily unavailable due to high demand "
                    f"(primary='{model_name}', fallback='{fallback_model_name}'). "
                    "Skipping MR enhancement for this run."
                )
            fail(
                "Gemini generation failed on primary and fallback models: "
                f"primary='{model_name}', fallback='{fallback_model_name}', "
                f"last_error={fallback_error}"
            )
    return {}


def _parse_nested_payload(payload: dict[str, Any], plan: GenerationPlan) -> NestedEnhancementPayload:
    """Validate and prune Gemini response according to requested sections."""
    result: NestedEnhancementPayload = {}
    if plan.request_description:
        section = payload.get("description")
        if not isinstance(section, dict):
            raise ValueError("Gemini payload missing required object: description")
        result["description"] = {
            "description_markdown": str(section.get("description_markdown") or "").strip()
        }
    if plan.request_review:
        section = payload.get("review")
        if not isinstance(section, dict):
            raise ValueError("Gemini payload missing required object: review")
        suggestions = section.get("suggestions")
        if suggestions is None:
            suggestions = []
        if not isinstance(suggestions, list):
            raise ValueError("Gemini payload review.suggestions must be an array")
        result["review"] = {"suggestions": suggestions}
    if plan.request_confidence:
        section = payload.get("confidence")
        if not isinstance(section, dict):
            raise ValueError("Gemini payload missing required object: confidence")
        result["confidence"] = {
            "effect_tags": section.get("effect_tags") if isinstance(section.get("effect_tags"), list) else [],
            "risk_level": str(section.get("risk_level") or "").strip(),
            "optimization_areas": section.get("optimization_areas")
            if isinstance(section.get("optimization_areas"), list)
            else [],
            "missing_or_outdated_tests": section.get("missing_or_outdated_tests")
            if isinstance(section.get("missing_or_outdated_tests"), list)
            else [],
            "confidence_explanation": str(section.get("confidence_explanation") or "").strip(),
        }
    return result


def _is_api_error(exc: Exception) -> bool:
    """Return True when failure is likely from API/transport layer."""
    return not isinstance(exc, ValueError)


def _is_high_demand_error(exc: Exception) -> bool:
    """Return True when the API reports transient model capacity pressure (503)."""
    error_code = getattr(exc, "code", None)
    if error_code is not None and str(error_code) in {"503", "UNAVAILABLE"}:
        return True
    status = getattr(exc, "status", None)
    if status is not None and str(status).upper() == "UNAVAILABLE":
        return True
    text = str(exc).lower()
    if "high demand" in text:
        return True
    return "503" in text and "unavailable" in text


def _generate_with_model(
    model_name: str, prompt: str, retries: int, plan: GenerationPlan
) -> NestedEnhancementPayload:
    """Run generation for a single model with retry behavior."""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            client = genai.Client()
            response = client.models.generate_content(model=model_name, contents=prompt)
            text = (response.text or "").strip()
            if not text:
                raise ValueError("Gemini returned empty response text.")
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError("Gemini payload is not a JSON object.")
            return _parse_nested_payload(payload, plan)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            error_code = str(getattr(exc, "code", ""))
            error_message = str(getattr(exc, "message", "")) or str(exc)
            if error_code == "429" and "limit: 0" in error_message.lower():
                fail("Gemini quota is exhausted for this project. No point retrying.")
            if attempt < retries:
                sleep_seconds = attempt * 5
                log(
                    f"Gemini generation failed for model '{model_name}' "
                    f"(attempt {attempt}/{retries}): {exc}. "
                    f"Retrying in {sleep_seconds}s..."
                )
                time.sleep(sleep_seconds)
            else:
                break
    if last_error is None:
        raise RuntimeError("Gemini generation failed without a captured error.")
    raise last_error
