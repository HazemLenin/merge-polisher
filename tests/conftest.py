"""Shared fixtures for merge_polisher tests."""

import pytest


@pytest.fixture
def provider() -> str:
    """VCS provider under test for app-level integration tests."""
    return "gitlab"


@pytest.fixture
def clean_provider_env(monkeypatch) -> None:
    """Clear provider-selection and auth env to avoid host leakage."""
    for key in (
        "CI_PROVIDER",
        "GITHUB_REPOSITORY",
        "GITHUB_TOKEN",
        "GITHUB_API_TOKEN",
        "CI_API_V4_URL",
        "CI_PROJECT_ID",
        "CI_MERGE_REQUEST_IID",
        "CI_JOB_TOKEN",
        "GITLAB_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def provider_required_env(provider: str) -> dict[str, str]:
    """Required env values consumed through read_required_env."""
    if provider == "github":
        return {
            "GITHUB_REPOSITORY": "acme/repo",
            "GEMINI_API_KEY": "k",
        }
    return {
        "CI_API_V4_URL": "https://gitlab/api/v4",
        "CI_PROJECT_ID": "1",
        "CI_MERGE_REQUEST_IID": "2",
        "GEMINI_API_KEY": "k",
    }


@pytest.fixture
def minimal_mr_description() -> str:
    """MR body with required AutoDescriptor markers and extract_required_inputs fields."""
    return """<!-- auto-descriptor:on -->
<!-- auto-review:on -->
<!-- auto-confidence-comment:on -->

### Summary

Short summary.

### Issue Key

XX-1000

### Problem Brief

Something was broken.

### Solution Brief

We fixed it.

### How to Test

- [ ] Run the app

### Checklist

- [ ] MR title includes `XX-XXXX`
- [ ] I have tested these changes
"""


@pytest.fixture
def mr_description_no_auto_markers() -> str:
    """Non-empty description without leading opt-in markers."""
    return """### Summary

Manual MR.

### Issue Key

XX-2000

### Problem Brief

Problem text.

### Solution Brief

Solution text.

### How to Test

- [ ] Test

### Checklist

- [ ] I have tested these changes
"""


@pytest.fixture
def minimal_mr_changes() -> dict:
    """Single-file MR changes payload with a small unified diff."""
    diff = """@@ -0,0 +1,2 @@
+line one
+line two
"""
    return {
        "source_branch": "feature/x",
        "target_branch": "dev",
        "changes": [
            {
                "new_path": "src/service/foo.py",
                "old_path": "src/service/foo.py",
                "diff": diff,
            }
        ],
    }
