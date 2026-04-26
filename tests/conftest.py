"""Shared fixtures for merge_polisher tests."""

import pytest


@pytest.fixture
def minimal_mr_description() -> str:
    """MR body with required AutoDescriptor markers and extract_required_inputs fields."""
    return """<!-- auto-descriptor:on -->
<!-- auto-review:on -->
<!-- auto-confidence-comment:on -->

### Summary

Short summary.

### Issue Key

GAP-1000

### Problem Brief

Something was broken.

### Solution Brief

We fixed it.

### How to Test

- [ ] Run the app

### Checklist

- [ ] MR title includes `GAP-XXXX`
- [ ] I have tested these changes
"""


@pytest.fixture
def mr_description_no_auto_markers() -> str:
    """Non-empty description without leading opt-in markers."""
    return """### Summary

Manual MR.

### Issue Key

GAP-2000

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
