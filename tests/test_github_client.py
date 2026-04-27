"""Tests for github client adapter."""

import json
from pathlib import Path

import pytest

import adapters.github.client as github_client


def test_build_pr_endpoint_from_event_payload(tmp_path: Path, monkeypatch) -> None:
    event_payload = {"pull_request": {"number": 42}}
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps(event_payload), encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
    monkeypatch.setenv("GITHUB_API_URL", "https://api.github.com")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
    monkeypatch.delenv("GITHUB_PR_NUMBER", raising=False)
    endpoint = github_client.build_pr_endpoint()
    assert endpoint.endswith("/repos/acme/repo/pulls/42")


def test_build_auth_headers_prefers_explicit_token(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_API_TOKEN", "pat-token")
    monkeypatch.setenv("GITHUB_TOKEN", "gha-token")
    headers = github_client.build_auth_headers()
    assert headers["Authorization"] == "Bearer pat-token"


def test_fetch_mr_changes_maps_github_shape(monkeypatch) -> None:
    def fake_request(method, url, headers, body=None, retries=3, timeout_seconds=30):
        if url.endswith("/files?per_page=100"):
            return [
                {
                    "filename": "src/app.py",
                    "status": "renamed",
                    "previous_filename": "src/old.py",
                    "patch": "@@ -1 +1 @@\n-print(1)\n+print(2)\n",
                }
            ]
        return {
            "base": {"ref": "main", "sha": "base"},
            "head": {"ref": "feature", "sha": "head"},
        }

    monkeypatch.setattr(github_client, "request_json", fake_request)
    payload = github_client.fetch_mr_changes("https://api.github.com/repos/acme/repo/pulls/1", {})
    assert payload["source_branch"] == "feature"
    assert payload["target_branch"] == "main"
    assert payload["changes"][0]["new_path"] == "src/app.py"
    assert payload["changes"][0]["old_path"] == "src/old.py"
    assert payload["changes"][0]["renamed_file"] is True


def test_create_mr_inline_discussion_posts_review_comment(monkeypatch) -> None:
    captured = {}

    def fake_request(method, url, headers, body=None, retries=3, timeout_seconds=30):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = json.loads((body or b"{}").decode("utf-8"))
        return {"id": 1}

    monkeypatch.setattr(github_client, "request_json", fake_request)
    github_client.create_mr_inline_discussion(
        endpoint="https://api.github.com/repos/acme/repo/pulls/1",
        headers={},
        file_path="src/app.py",
        new_line=10,
        versions={"head_sha": "abc123", "base_sha": "base", "start_sha": "base"},
        summary="Nit",
        suggested_code="print('x')",
    )
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/comments")
    assert captured["payload"]["path"] == "src/app.py"
    assert captured["payload"]["line"] == 10
    assert captured["payload"]["commit_id"] == "abc123"


def test_build_auth_headers_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_API_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        github_client.build_auth_headers()


def test_normalize_inline_suggestion_code_trims_trailing_newline() -> None:
    out = github_client.normalize_inline_suggestion_code(
        mr_changes={"changes": []},
        file_path="src/app.py",
        new_line=10,
        suggested_code="if ok:\n    return 1\n",
    )
    assert out == "if ok:\n    return 1"
