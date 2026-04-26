"""Description-domain helpers for payload normalization and markdown enrichment."""

from typing import Any

from core.constants import ALLOWED_EFFECT_TAGS, ALLOWED_RISK_LEVELS, MAX_INLINE_SUGGESTIONS


def normalize_suggestions(raw_suggestions: object) -> list[dict]:
    """Normalize and validate model suggestions with conservative filtering."""
    if not isinstance(raw_suggestions, list):
        return []

    normalized: list[dict] = []
    for item in raw_suggestions:
        if not isinstance(item, dict):
            continue
        file_path = str(item.get("file_path") or "").strip()
        summary = str(item.get("summary") or "").strip()
        suggested_code = str(item.get("suggested_code") or "").strip()
        line_value = item.get("new_line")
        try:
            new_line = int(line_value)
        except (TypeError, ValueError):
            continue
        if not file_path or not summary or not suggested_code or new_line <= 0:
            continue
        normalized.append(
            {
                "file_path": file_path,
                "new_line": new_line,
                "summary": summary,
                "suggested_code": suggested_code,
            }
        )
        if len(normalized) >= MAX_INLINE_SUGGESTIONS:
            break
    return normalized


def normalize_effect_tags(raw_tags: object) -> list[str]:
    """Normalize effect tags to the allowed enum values."""
    if not isinstance(raw_tags, list):
        return []
    normalized: list[str] = []
    for tag in raw_tags:
        value = str(tag or "").strip().lower()
        if value in ALLOWED_EFFECT_TAGS and value not in normalized:
            normalized.append(value)
    return normalized


def normalize_risk_level(raw_level: object) -> str:
    """Normalize risk level to allowed enum value or empty string."""
    value = str(raw_level or "").strip().lower()
    return value if value in ALLOWED_RISK_LEVELS else ""


def normalize_string_list(raw_items: object) -> list[str]:
    """Normalize arbitrary array values into non-empty trimmed string list."""
    if not isinstance(raw_items, list):
        return []
    result: list[str] = []
    for item in raw_items:
        value = str(item or "").strip()
        if value:
            result.append(value)
    return result


def build_confidence_comment_body(
    *,
    confidence_score: float,
    risk_level: str,
    effect_tags: list[str],
    confidence_explanation: str,
    confidence_reasons: list[dict[str, Any]],
    optimization_areas: list[str],
    missing_or_outdated_tests: list[str],
    signature: str,
    head_sha: str,
    sha_marker_prefix: str,
) -> str:
    """Build standalone MR comment markdown for confidence report."""
    lines = [
        "### Auto Descriptor Confidence Report",
        "",
        f"- **Confidence score:** {confidence_score:.1f}/10.0",
        f"- **Risk level:** {risk_level or 'n/a'}",
        f"- **Effect tags:** {', '.join(effect_tags) if effect_tags else 'n/a'}",
        f"- **Gemini rationale:** {confidence_explanation or 'n/a'}",
    ]
    if optimization_areas:
        lines.append("- **Optimization areas (high-level):**")
        lines.extend([f"  - {item}" for item in optimization_areas[:5]])
    if missing_or_outdated_tests:
        lines.append("- **Missing or outdated tests (changed scope):**")
        lines.extend([f"  - {item}" for item in missing_or_outdated_tests[:5]])
    if confidence_reasons:
        lines.append("- **Score rules triggered:**")
        for reason in confidence_reasons[:8]:
            rule = str(reason.get("rule") or "unknown_rule")
            weight = reason.get("weight")
            detail = str(reason.get("reason") or "").strip()
            lines.append(f"  - `{rule}` ({weight}): {detail or 'n/a'}")
    lines.extend(["", signature, f"{sha_marker_prefix}{head_sha} -->"])
    return "\n".join(lines).strip()
