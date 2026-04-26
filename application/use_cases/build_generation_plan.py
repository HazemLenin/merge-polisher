"""Build model generation plan from execution policy."""

from core.models import ExecutionPolicy, GenerationPlan


def build_generation_plan(policy: ExecutionPolicy) -> GenerationPlan:
    """Return section flags used for prompt/response contract."""
    return GenerationPlan(
        request_description=policy.description_enabled,
        request_review=policy.suggestions_enabled,
        request_confidence=policy.confidence_comment_enabled,
    )
