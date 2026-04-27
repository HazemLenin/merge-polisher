"""Shared constants for the auto-descriptor pipeline."""
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GITLAB_DIR = SCRIPT_DIR.parents[2]
LLM_GUIDE_PATH = GITLAB_DIR / "mr_description_llm.md"
DEFAULT_TEMPLATE_PATH = SCRIPT_DIR.parents[1] / "markdown" / "DefaultTemplateOutput.md"

DEFAULT_PRIMARY_MODEL = "gemini-3-flash-preview"
DEFAULT_ALT_MODEL = "gemini-2.5-flash"

MAX_DIFF_FILES = 40
MAX_PATCH_CHARS_PER_FILE = 40000
MAX_DIFF_CONTEXT_CHARS = 180000
MAX_INLINE_SUGGESTIONS = 10

DESCRIPTION_OPT_IN_MARKER = "<!-- auto-descriptor:on -->"
SUGGESTIONS_OPT_IN_MARKER = "<!-- auto-review:on -->"
CONFIDENCE_COMMENT_OPT_IN_MARKER = "<!-- auto-confidence-comment:on -->"
CONFIDENCE_COMMENT_SIGNATURE = "<!-- auto-descriptor:confidence-comment -->"
CONFIDENCE_COMMENT_HEAD_SHA_PREFIX = "<!-- auto-descriptor:confidence-head-sha:"
REQUIRED_EXTRACTED_FIELDS = ("problem_brief", "solution_brief")

ALLOWED_EFFECT_TAGS = ("bugfix", "feature", "refactor", "perf", "security", "docs")
ALLOWED_RISK_LEVELS = ("low", "medium", "high", "critical")

CONFIDENCE_BASELINE = 7.5
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 10.0

CONFIDENCE_WEIGHT_SMALL_DIFF = 0.6
CONFIDENCE_WEIGHT_MEDIUM_DIFF = 0.25
CONFIDENCE_WEIGHT_LARGE_DIFF = -0.9
CONFIDENCE_WEIGHT_HUGE_DIFF = -1.5
CONFIDENCE_WEIGHT_SERVICE_FILE = -0.35
CONFIDENCE_WEIGHT_LARGE_SERVICE_FILE = -0.85
CONFIDENCE_WEIGHT_CRITICAL_FILE = -0.65
CONFIDENCE_WEIGHT_HAS_TEST_CHANGES = 1.1
CONFIDENCE_WEIGHT_NO_TESTS_WITH_LARGE_LOGIC = -1.35
CONFIDENCE_WEIGHT_WIDE_CHANGESET = -0.7

CONFIDENCE_SMALL_DIFF_THRESHOLD = 80
CONFIDENCE_MEDIUM_DIFF_THRESHOLD = 220
CONFIDENCE_LARGE_DIFF_THRESHOLD = 500
CONFIDENCE_WIDE_FILESET_THRESHOLD = 12
CONFIDENCE_LARGE_SERVICE_DIFF_THRESHOLD = 140

# Substrings matched on lowercased paths (GitLab new_path). Tuned for GapMap / ParkingBridge / Shared.
SERVICE_PATH_HINTS = (
    "gapmap.application",
    "parkingbridge.application",
    "all.application",
    "gapmap.infrastructure",
    "parkingbridge.infrastructure",
    "all.infrastructure",
    "gapmap.api",
    "parkingbridge.webui",
    "/handlers/",
    "handlers/",
    "corelogic",
)
CRITICAL_PATH_HINTS = (
    "payu",
    "payment",
    "accounting",
    "billing",
    "invoice",
    "checkout",
    "wallet",
    "jwt",
    "authentication",
    "authorization",
    "permission",
    "security",
    "session",
    "gateway",
    "auth",
    "acl",
)
TEST_PATH_HINTS = (
    "/tests/",
    "unittests",
    "integrationtests",
    "__tests__",
)

REQUIRED_TEMPLATE_MARKERS = [
    "### Summary",
    "### Problem Brief",
    "### Solution Brief",
    "### How to Test",
    "### Checklist",
    "- [ ] I have tested these changes",
]

OPTIONAL_TEMPLATE_MARKERS = [
    "### Issue Key",
]

