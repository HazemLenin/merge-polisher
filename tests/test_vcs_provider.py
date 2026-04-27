"""Tests for VCS provider resolution."""

import pytest

from adapters.vcs.provider import resolve_vcs_client


def _clear_provider_env(monkeypatch) -> None:
    monkeypatch.delenv("CI_PROVIDER", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("CI_API_V4_URL", raising=False)
    monkeypatch.delenv("CI_PROJECT_ID", raising=False)
    monkeypatch.delenv("CI_MERGE_REQUEST_IID", raising=False)


def test_resolve_vcs_client_prefers_explicit_provider(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("CI_PROVIDER", "github")
    client = resolve_vcs_client()
    assert client.provider_name == "github"


def test_resolve_vcs_client_prefers_explicit_provider_when_opposite_keys_exist(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("CI_PROVIDER", "gitlab")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
    monkeypatch.setenv("CI_API_V4_URL", "https://gitlab/api/v4")
    monkeypatch.setenv("CI_PROJECT_ID", "1")
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "2")
    client = resolve_vcs_client()
    assert client.provider_name == "gitlab"


def test_resolve_vcs_client_auto_detects_github(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
    client = resolve_vcs_client()
    assert client.provider_name == "github"


def test_resolve_vcs_client_auto_detects_gitlab(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("CI_API_V4_URL", "https://gitlab/api/v4")
    monkeypatch.setenv("CI_PROJECT_ID", "1")
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "2")
    client = resolve_vcs_client()
    assert client.provider_name == "gitlab"


def test_resolve_vcs_client_fails_when_ambiguous(monkeypatch) -> None:
    _clear_provider_env(monkeypatch)
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
    monkeypatch.setenv("CI_API_V4_URL", "https://gitlab/api/v4")
    monkeypatch.setenv("CI_PROJECT_ID", "1")
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "2")
    with pytest.raises(SystemExit):
        resolve_vcs_client()
