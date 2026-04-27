"""Tests for gemini_client."""

import json

import pytest

import adapters.llm.gemini_client as gemini_client
from core.constants import DEFAULT_ALT_MODEL, DEFAULT_PRIMARY_MODEL
from adapters.llm.gemini_client import (
    build_single_call_prompt,
    generate_enhancement_payload,
    validate_extracted_inputs,
    validate_models,
)
from core.models import GenerationPlan


FULL_PLAN = GenerationPlan(
    request_description=True,
    request_review=True,
    request_confidence=True,
)


def test_validate_models_accepts_expected_pair():
    validate_models(DEFAULT_PRIMARY_MODEL, DEFAULT_ALT_MODEL)


def test_validate_models_rejects_other(monkeypatch):
    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(gemini_client, "fail", boom)
    with pytest.raises(RuntimeError, match="Unsupported Gemini model configuration"):
        validate_models("wrong-model", DEFAULT_ALT_MODEL)


def test_build_single_call_prompt_contains_inputs():
    extracted = {
        "issue_key": "GAP-1",
        "problem_brief": "pb",
        "solution_brief": "sb",
    }
    ctx = {"score": 7.5, "reasons": [], "signals": {}}
    prompt = build_single_call_prompt(
        current_description="desc",
        output_template="tpl",
        llm_guide="guide",
        extracted=extracted,
        diff_context="diff here",
        confidence_context=ctx,
        plan=FULL_PLAN,
    )
    assert "GAP-1" in prompt
    assert "diff here" in prompt
    assert json.dumps(ctx, ensure_ascii=True) in prompt
    assert "summary must be a concise full sentence" in prompt
    assert "suggested_code can be multiline" in prompt
    assert "Do not include unchanged surrounding lines" in prompt


def test_build_single_call_prompt_includes_only_requested_sections():
    extracted = {"issue_key": "GAP-1", "problem_brief": "pb", "solution_brief": "sb"}
    ctx = {"score": 7.5, "reasons": [], "signals": {}}
    prompt = build_single_call_prompt(
        current_description="desc",
        output_template="tpl",
        llm_guide="guide",
        extracted=extracted,
        diff_context="diff here",
        confidence_context=ctx,
        plan=GenerationPlan(
            request_description=False,
            request_review=True,
            request_confidence=False,
        ),
    )
    assert '"review"' in prompt
    assert '"description"' not in prompt
    assert '"confidence"' not in prompt


def test_generate_enhancement_payload_primary_success(monkeypatch):
    payload = {"description": {"description_markdown": "ok"}, "review": {"suggestions": []}}
    monkeypatch.setattr(
        gemini_client,
        "_generate_with_model",
        lambda model_name, prompt, retries, plan: payload if model_name == DEFAULT_PRIMARY_MODEL else {},
    )
    out = generate_enhancement_payload(
        model_name=DEFAULT_PRIMARY_MODEL,
        fallback_model_name=DEFAULT_ALT_MODEL,
        current_description="d",
        output_template="t",
        llm_guide="g",
        extracted={"issue_key": "GAP-1", "problem_brief": "p", "solution_brief": "s"},
        diff_context="",
        confidence_context={"score": 1, "signals": {}, "reasons": []},
        plan=GenerationPlan(request_description=True, request_review=True, request_confidence=False),
    )
    assert out == payload


def test_generate_enhancement_payload_fallback_on_api_error(monkeypatch):
    class ApiError(Exception):
        pass

    def fake_generate(model_name, prompt, retries, plan):
        if model_name == DEFAULT_PRIMARY_MODEL:
            raise ApiError("boom")
        return {"description": {"description_markdown": "alt"}, "review": {"suggestions": []}}

    monkeypatch.setattr(gemini_client, "_generate_with_model", fake_generate)
    out = generate_enhancement_payload(
        model_name=DEFAULT_PRIMARY_MODEL,
        fallback_model_name=DEFAULT_ALT_MODEL,
        current_description="d",
        output_template="t",
        llm_guide="g",
        extracted={"issue_key": "GAP-1", "problem_brief": "p", "solution_brief": "s"},
        diff_context="",
        confidence_context={"score": 1, "signals": {}, "reasons": []},
        plan=GenerationPlan(request_description=True, request_review=True, request_confidence=False),
    )
    assert out["description"]["description_markdown"] == "alt"


def test_generate_enhancement_payload_fails_when_both_models_fail(monkeypatch):
    class ApiError(Exception):
        pass

    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(gemini_client, "fail", boom)
    monkeypatch.setattr(gemini_client, "_generate_with_model", lambda *_a, **_k: (_ for _ in ()).throw(ApiError("x")))
    with pytest.raises(RuntimeError, match="failed on primary and fallback models"):
        generate_enhancement_payload(
            model_name=DEFAULT_PRIMARY_MODEL,
            fallback_model_name=DEFAULT_ALT_MODEL,
            current_description="d",
            output_template="t",
            llm_guide="g",
            extracted={"issue_key": "GAP-1", "problem_brief": "p", "solution_brief": "s"},
            diff_context="",
            confidence_context={"score": 1, "signals": {}, "reasons": []},
            plan=GenerationPlan(request_description=True, request_review=True, request_confidence=False),
        )


def test_generate_enhancement_payload_does_not_fallback_on_parse_error(monkeypatch):
    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(gemini_client, "fail", boom)
    monkeypatch.setattr(
        gemini_client,
        "_generate_with_model",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("invalid json")),
    )
    with pytest.raises(RuntimeError, match="Gemini generation failed after"):
        generate_enhancement_payload(
            model_name=DEFAULT_PRIMARY_MODEL,
            fallback_model_name=DEFAULT_ALT_MODEL,
            current_description="d",
            output_template="t",
            llm_guide="g",
            extracted={"issue_key": "GAP-1", "problem_brief": "p", "solution_brief": "s"},
            diff_context="",
            confidence_context={"score": 1, "signals": {}, "reasons": []},
            plan=GenerationPlan(request_description=True, request_review=True, request_confidence=False),
        )


def test_validate_extracted_inputs_fails_in_strict_mode(monkeypatch):
    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(gemini_client, "fail", boom)

    with pytest.raises(RuntimeError, match="Extracted MR inputs are required in strict mode"):
        validate_extracted_inputs({"issue_key": "", "problem_brief": "pb"})


def test_validate_extracted_inputs_allows_blank_values_in_history_only_mode():
    normalized = validate_extracted_inputs(
        {"issue_key": "", "problem_brief": " ", "solution_brief": ""},
        allow_missing_extracted=True,
    )
    assert normalized == {"issue_key": "", "problem_brief": "", "solution_brief": ""}
