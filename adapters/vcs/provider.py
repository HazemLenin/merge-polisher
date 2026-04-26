"""VCS provider factory and runtime detection."""

import os

from adapters.github import client as github_client
from adapters.gitlab import client as gitlab_client
from adapters.vcs.client import VcsClient
from core.runtime import fail
from domain.mr.markers import build_auth_headers as build_gitlab_auth_headers


def resolve_vcs_client() -> VcsClient:
    """Resolve VCS provider using explicit setting then CI env auto-detect."""
    explicit_provider = os.getenv("CI_PROVIDER", "").strip().lower()
    if explicit_provider:
        if explicit_provider == "gitlab":
            return build_gitlab_client()
        if explicit_provider == "github":
            return build_github_client()
        fail("Invalid CI_PROVIDER. Supported values: gitlab, github.")

    has_github_context = bool(os.getenv("GITHUB_REPOSITORY", "").strip())
    has_gitlab_context = all(
        [
            bool(os.getenv("CI_API_V4_URL", "").strip()),
            bool(os.getenv("CI_PROJECT_ID", "").strip()),
            bool(os.getenv("CI_MERGE_REQUEST_IID", "").strip()),
        ]
    )
    if has_github_context and has_gitlab_context:
        fail("Ambiguous provider auto-detection. Set CI_PROVIDER explicitly.")
    if has_github_context:
        return build_github_client()
    if has_gitlab_context:
        return build_gitlab_client()
    fail("Unable to auto-detect VCS provider. Set CI_PROVIDER=gitlab|github.")
    return build_gitlab_client()


def build_gitlab_client() -> VcsClient:
    return gitlab_client.build_client(
        build_endpoint=lambda: gitlab_client.build_mr_endpoint(
            os.environ["CI_API_V4_URL"].strip(),
            os.environ["CI_PROJECT_ID"].strip(),
            os.environ["CI_MERGE_REQUEST_IID"].strip(),
        ),
        build_auth_headers=build_gitlab_auth_headers,
    )


def build_github_client() -> VcsClient:
    return VcsClient(
        provider_name="github",
        build_endpoint=github_client.build_pr_endpoint,
        build_auth_headers=github_client.build_auth_headers,
        fetch_description=github_client.fetch_mr_description,
        fetch_changes=github_client.fetch_mr_changes,
        build_diff_context=github_client.build_diff_context,
        update_description=github_client.update_mr_description,
        fetch_versions=github_client.fetch_mr_versions,
        build_changed_new_lines=github_client.build_changed_new_lines,
        normalize_inline_suggestion_code=github_client.normalize_inline_suggestion_code,
        create_inline_discussion=github_client.create_mr_inline_discussion,
        fetch_notes_by_signature=github_client.fetch_mr_notes_by_signature,
        get_latest_note_by_id=github_client.get_latest_note_by_id,
        extract_sha_from_note_body=github_client.extract_sha_from_note_body,
        create_note=github_client.create_mr_note,
    )
