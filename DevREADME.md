# Auto Descriptor Module

This module enhances GitLab merge requests and GitHub pull requests by generating description updates, optional inline suggestions, and an optional standalone note/comment with confidence, risk, effect tags, optimization hints, missing-test notes, and deterministic score rules derived from the diff.

## Domain-Oriented Layout

- `app.py`: pipeline orchestration only (load env, fetch MR, call domains, publish outputs)
- `models.py`: typed contracts for execution policy, extracted inputs, confidence context, and generation payload
- `policy.py`: marker/history policy resolution and strict/relaxed validation rules
- `mr_domain.py`: marker detection and auth-header setup
- `mr_parser.py`: template compatibility and required-field extraction
- `gitlab_client.py`: GitLab API boundary (fetch/update/discussion operations)
- `gemini_client.py`: Gemini prompt construction and response parsing
- `confidence_domain.py`: deterministic signal extraction and confidence scoring
- `description_domain.py`: model-output normalization and standalone confidence / review-note comment formatting
- `constants.py`: shared model, marker, threshold, and heuristic constants
- `runtime.py`: logging and fail-fast behavior
- `io_utils.py`: environment and file read utilities
- `script.py`: process entrypoint

## Runtime Flow

1. Read CI env vars and prompt/template files.
2. Resolve VCS provider client (GitLab or GitHub), then fetch MR/PR description and detect enablement markers.
3. Validate template (when description update is enabled).
4. Fetch diff context and derive deterministic confidence context.
5. Build policy-gated generation plan and ask Gemini only for enabled sections (single nested JSON response; primary model first, fallback model on primary API failure after retries).
6. Normalize payload fields (suggestions, tags, lists, etc.).
7. Update MR/PR description when enabled (Gemini markdown only; no injected risk/confidence metadata in the description).
8. Create standalone confidence / review metadata note/comment (history-preserving; one note per new commit SHA) when enabled.
9. Publish inline suggestions only on changed lines when enabled.

## Provider Selection

- Runtime selection is hybrid:
  - explicit override via `CI_PROVIDER=gitlab|github`
  - otherwise auto-detect from CI context
- Auto-detect rules:
  - GitHub when `GITHUB_REPOSITORY` is present
  - GitLab when `CI_API_V4_URL`, `CI_PROJECT_ID`, and `CI_MERGE_REQUEST_IID` are present
  - fails fast if both contexts are present (ambiguous) or neither can be detected
- Existing GitLab behavior remains the default when running in GitLab CI.

## Provider Runtime Environment

### GitLab

- Context:
  - `CI_API_V4_URL`
  - `CI_PROJECT_ID`
  - `CI_MERGE_REQUEST_IID`
- Auth:
  - `GITLAB_TOKEN` (preferred) or `CI_JOB_TOKEN`

### GitHub (GitHub Actions Native)

- Context:
  - `GITHUB_REPOSITORY` (`owner/repo`)
  - PR number resolved from one of:
    - `GITHUB_PR_NUMBER` (optional explicit override)
    - `GITHUB_EVENT_PATH` payload when `GITHUB_EVENT_NAME=pull_request`
    - `GITHUB_REF` in `refs/pull/<n>/...` format
  - optional `GITHUB_API_URL` (defaults to `https://api.github.com`)
- Auth precedence:
  - `GITHUB_API_TOKEN` first
  - fallback to `GITHUB_TOKEN` (standard GitHub Actions token)

## Orchestration Stages

`app.py` keeps `run()` small and pushes details into stage helpers:

1. `_load_runtime_context`
2. `_fetch_policy_context`
3. `_validate_template_and_inputs`
4. `_fetch_diff_and_confidence`
5. `_generate_and_normalize_payload`
6. `_publish_confidence_comment_if_enabled`
7. `_publish_description_if_enabled`
8. `_publish_inline_suggestions_if_enabled`

This keeps sequencing and side effects explicit while moving branching rules into `policy.py`.

## Enablement Markers

Place markers in the leading comment block at the top of MR description/template:

- `<!-- auto-descriptor:on -->`: enable MR description generation/update.
- `<!-- auto-review:on -->`: enable inline suggestion comments on changed lines.
- `<!-- auto-confidence-comment:on -->`: enable separate MR note with confidence score, risk level, effect tags, Gemini rationale, optimization areas, missing-test notes, and deterministic score rules.

These markers are independent; any combination can be enabled.

## Confidence Comment Upsert

- The MR note uses a hidden signature token to identify bot-owned note content.
- Confidence execution is enabled when either:
  - `<!-- auto-confidence-comment:on -->` marker is present in the leading MR description comment block, or
  - a previous signature-matching confidence note already exists.
- Each confidence note embeds hidden head SHA metadata:
  - `<!-- auto-descriptor:confidence-head-sha:<sha> -->`
- On each run:
  - if latest confidence note SHA matches current head SHA, no new confidence note is created;
  - if SHA is missing/malformed on latest confidence note, a new confidence note is created;
  - if current head SHA is newer/different, a new confidence note is created.
- This preserves confidence history while preventing duplicate notes for the same commit.

## Gemini Model Configuration

- `GEMINI_MODEL`: primary Gemini model (default: `gemini-3-flash-preview`).
- `GEMINI_ALT_MODEL`: fallback Gemini model (default: `gemini-2.5-flash`).
- Fallback behavior:
  - primary model is retried first;
  - fallback model is attempted only when primary fails with API/transport errors after retries;
  - invalid/empty JSON payload errors do not trigger fallback.
- Validation policy is strict: only the configured primary/alt pair is accepted.

## Runtime Path Hint Configuration

Only these confidence hint groups are customizable at runtime (via CI env vars):

- `MERGE_POLISHER_SERVICE_PATH_HINTS`
- `MERGE_POLISHER_CRITICAL_PATH_HINTS`
- `MERGE_POLISHER_TEST_PATH_HINTS`

Format for each variable: JSON array string.

Example:

`["gapmap.application","/handlers/","corelogic"]`

Invalid JSON fails fast with clear error message.

## Safe Extension Points

- Adjust confidence behavior in `confidence_domain.py` and related constants in `constants.py`.
- Adjust Gemini output contract/rules in `gemini_client.py`.
- Adjust markdown placement/formatting in `description_domain.py`.
- Adjust provider-specific lifecycle details in `adapters/gitlab/client.py` or `adapters/github/client.py`.
- Keep `app.py` focused on sequencing and side effects; avoid embedding domain logic there.

## How to Extend Safely

- Add or change marker behavior in `policy.py` first, then update orchestration helpers in `app.py`.
- Keep externally visible behavior backward-compatible unless CI contract changes are intentional.
- Prefer adding typed fields in `models.py` before introducing new payload keys in generation or publishing.
- Add focused unit tests for new policy branches and publish gates, then keep integration coverage in `test_app.py`.

## Testing Strategy

- `test_app.py`: integration-style orchestration coverage with mocked boundaries.
- `test_policy.py`: policy matrix and strict/relaxed validation semantics.
- `test_confidence_comment.py`: SHA dedupe behavior for confidence notes.
- `test_suggestions_gate.py`: changed-line eligibility and skip gating for inline suggestions.
- Existing domain/client tests (`test_gemini_client.py`, `test_gitlab_client.py`, `test_github_client.py`, etc.) continue to validate module-local behavior.
- `test_vcs_provider.py`: provider resolution matrix (explicit, auto-detect, ambiguity).
