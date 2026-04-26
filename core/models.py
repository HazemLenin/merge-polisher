"""Typed domain models shared across merge_polisher modules."""

from dataclasses import dataclass
from typing import Any, Dict, List, TypedDict


@dataclass(frozen=True)
class ExecutionPolicy:
    """Resolved enablement and enforcement rules for one pipeline run."""

    description_enabled: bool
    suggestions_enabled: bool
    confidence_comment_marker_enabled: bool
    confidence_comment_history_enabled: bool
    confidence_comment_enabled: bool
    confidence_history_only_mode: bool
    should_enforce_template: bool
    should_enforce_required_inputs: bool


class ExtractedInputs(TypedDict):
    """Required extracted description fields used by generation."""

    issue_key: str
    problem_brief: str
    solution_brief: str


class SuggestionItem(TypedDict):
    """Single inline review suggestion candidate."""

    file_path: str
    new_line: int
    summary: str
    suggested_code: str


class ConfidenceContext(TypedDict):
    """Deterministic confidence score and explanations derived from diff signals."""

    score: float
    signals: Dict[str, Any]
    reasons: List[str]


class EnhancementPayload(TypedDict, total=False):
    """Normalized generation payload returned from Gemini client."""

    description_markdown: str
    suggestions: List[SuggestionItem]
    effect_tags: List[str]
    risk_level: str
    optimization_areas: List[str]
    missing_or_outdated_tests: List[str]
    confidence_explanation: str


@dataclass(frozen=True)
class GenerationPlan:
    """Plan which Gemini sections should be generated for this run."""

    request_description: bool
    request_review: bool
    request_confidence: bool


class DescriptionPayload(TypedDict, total=False):
    """Nested description section from Gemini response."""

    description_markdown: str


class ReviewPayload(TypedDict, total=False):
    """Nested review section from Gemini response."""

    suggestions: List[SuggestionItem]


class ConfidencePayload(TypedDict, total=False):
    """Nested confidence section from Gemini response."""

    effect_tags: List[str]
    risk_level: str
    optimization_areas: List[str]
    missing_or_outdated_tests: List[str]
    confidence_explanation: str


class NestedEnhancementPayload(TypedDict, total=False):
    """Policy-gated nested response returned from Gemini client."""

    description: DescriptionPayload
    review: ReviewPayload
    confidence: ConfidencePayload
