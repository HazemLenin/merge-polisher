"""Load runtime context for merge polisher run."""

from typing import Callable


def load_runtime_context(
    *,
    read_required_env: Callable[[str], str],
    env_getter: Callable[[str, str], str],
    build_auth_headers: Callable[[], dict[str, str]],
    read_text_file: Callable,
    build_mr_endpoint: Callable[[str, str, str], str],
    llm_guide_path,
    template_path,
    default_primary_model: str,
    default_alt_model: str,
    log: Callable[[str], None],
) -> tuple[str, dict[str, str], str, str, str, str]:
    """Load required environment and static prompt assets."""
    ci_api_v4_url = read_required_env("CI_API_V4_URL")
    ci_project_id = read_required_env("CI_PROJECT_ID")
    ci_mr_iid = read_required_env("CI_MERGE_REQUEST_IID")
    _ = read_required_env("GEMINI_API_KEY")
    model_name = env_getter("GEMINI_MODEL", default_primary_model).strip()
    alt_model_name = env_getter("GEMINI_ALT_MODEL", default_alt_model).strip()
    log(
        "Loaded required CI environment variables "
        "(CI_API_V4_URL, CI_PROJECT_ID, CI_MERGE_REQUEST_IID, GEMINI_API_KEY)."
    )
    log(f"Resolved Gemini models: primary='{model_name}', alt='{alt_model_name}'")

    headers = build_auth_headers()
    log("Reading LLM guide and output template files...")
    llm_guide = read_text_file(llm_guide_path)
    output_template = read_text_file(template_path)
    log(
        "Loaded prompt assets successfully: "
        f"guide_chars={len(llm_guide)}, template_chars={len(output_template)}"
    )

    mr_endpoint = build_mr_endpoint(ci_api_v4_url, ci_project_id, ci_mr_iid)
    log(f"Resolved MR endpoint: {mr_endpoint}")
    return mr_endpoint, headers, llm_guide, output_template, model_name, alt_model_name
