"""Tests for generation plan creation."""

from application.use_cases.build_generation_plan import build_generation_plan
from core.models import ExecutionPolicy


def test_generation_plan_follows_policy_flags() -> None:
    policy = ExecutionPolicy(
        description_enabled=True,
        suggestions_enabled=False,
        confidence_comment_marker_enabled=False,
        confidence_comment_history_enabled=True,
        confidence_comment_enabled=True,
        confidence_history_only_mode=True,
        should_enforce_template=False,
        should_enforce_required_inputs=False,
    )
    plan = build_generation_plan(policy)
    assert plan.request_description is True
    assert plan.request_review is False
    assert plan.request_confidence is True
