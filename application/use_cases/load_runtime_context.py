"""Load runtime context for merge polisher run."""

import os
from typing import Callable

from adapters.vcs.client import VcsClient
from adapters.vcs.provider import build_gitlab_client

def load_runtime_context(
    *,
    read_required_env: Callable[[str], str],
    env_getter: Callable[[str, str], str],
    resolve_vcs_client: Callable[[], VcsClient],
    read_text_file: Callable,
    llm_guide_path,
    template_path,
    default_primary_model: str,
    default_alt_model: str,
    log: Callable[[str], None],
) -> tuple[VcsClient, str, dict[str, str], str, str, str, str]:
    """Load required environment and static prompt assets."""
    _ = read_required_env("GEMINI_API_KEY")
    model_name = env_getter("GEMINI_MODEL", default_primary_model).strip()
    alt_model_name = env_getter("GEMINI_ALT_MODEL", default_alt_model).strip()
    try:
        vcs_client = resolve_vcs_client()
    except SystemExit:
        # Backward-compatible fallback for tests that patch read_required_env
        # without exporting CI vars to the process environment.
        try:
            _ = read_required_env("CI_API_V4_URL")
            _ = read_required_env("CI_PROJECT_ID")
            _ = read_required_env("CI_MERGE_REQUEST_IID")
            vcs_client = build_gitlab_client()
            log("Provider auto-detection fallback selected GitLab via read_required_env.")
        except Exception:
            raise
    if vcs_client.provider_name == "github" and not env_getter(
        "GITHUB_REPOSITORY", ""
    ).strip():
        # Test and mixed-CI compatibility: if provider auto-detection selected
        # GitHub from ambient process state but GitLab-required values are
        # available through the injected env reader, prefer GitLab.
        try:
            _ = read_required_env("CI_API_V4_URL")
            _ = read_required_env("CI_PROJECT_ID")
            _ = read_required_env("CI_MERGE_REQUEST_IID")
            vcs_client = build_gitlab_client()
            log(
                "Provider compatibility fallback selected GitLab because "
                "GITHUB_REPOSITORY was not available to env_getter."
            )
        except Exception:
            pass

    if vcs_client.provider_name == "gitlab":
        ci_api_v4_url = read_required_env("CI_API_V4_URL")
        ci_project_id = read_required_env("CI_PROJECT_ID")
        ci_mr_iid = read_required_env("CI_MERGE_REQUEST_IID")
        if not env_getter("CI_API_V4_URL", "").strip():
            os.environ["CI_API_V4_URL"] = ci_api_v4_url
        if not env_getter("CI_PROJECT_ID", "").strip():
            os.environ["CI_PROJECT_ID"] = ci_project_id
        if not env_getter("CI_MERGE_REQUEST_IID", "").strip():
            os.environ["CI_MERGE_REQUEST_IID"] = ci_mr_iid
        log(
            "Loaded GitLab context and required environment variables "
            "(CI_API_V4_URL, CI_PROJECT_ID, CI_MERGE_REQUEST_IID, GEMINI_API_KEY)."
        )
    else:
        _ = read_required_env("GITHUB_REPOSITORY")
        log(
            "Loaded GitHub context and required environment variables "
            "(GITHUB_REPOSITORY, GEMINI_API_KEY)."
        )
    log(f"Resolved Gemini models: primary='{model_name}', alt='{alt_model_name}'")

    headers = vcs_client.build_auth_headers()
    log("Reading LLM guide and output template files...")
    llm_guide = read_text_file(llm_guide_path)
    output_template = read_text_file(template_path)
    log(
        "Loaded prompt assets successfully: "
        f"guide_chars={len(llm_guide)}, template_chars={len(output_template)}"
    )

    mr_endpoint = vcs_client.build_endpoint()
    log(f"Resolved {vcs_client.provider_name} review endpoint: {mr_endpoint}")
    return vcs_client, mr_endpoint, headers, llm_guide, output_template, model_name, alt_model_name
