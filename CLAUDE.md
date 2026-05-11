# CLAUDE.md

Purpose: guidance for Claude when working in `merge_polisher`.

## Project identity

- Name: Merge Polisher
- Goal: AI-assisted MR/PR description polishing for CI pipelines.
- Providers: GitLab MRs and GitHub PRs.
- Entry point: `script.py` (calls `app.run()` pipeline).

## Tech stack

- Python: 3.13+
- Dependencies:
  - `pytest>=8,<9`
  - `google-genai>=1.73.1`

## Architecture rules

- Keep `app.py` orchestration-focused.
- Put business logic in:
  - `application/use_cases/` for workflow staging
  - `domain/` for parsing, normalization, confidence/scoring
  - `adapters/` for provider/LLM/IO boundaries
- Keep provider behavior behind `adapters/vcs/provider.py` and provider clients.
- Preserve typed contracts in `core/models.py` when adding payload fields.

## Runtime behavior (must preserve)

- Marker-driven publish gates:
  - `<!-- auto-descriptor:on -->` => update description
  - `<!-- auto-review:on -->` => publish inline suggestions
  - `<!-- auto-confidence-comment:on -->` => publish confidence comment
- If no marker enabled, exit without publishing.
- Confidence comment history logic:
  - Signature marker: `<!-- auto-descriptor:confidence-comment -->`
  - Head SHA marker prefix: `<!-- auto-descriptor:confidence-head-sha:`
  - Do not duplicate confidence note for same head SHA.
- Provider resolution:
  - explicit: `CI_PROVIDER=gitlab|github`
  - else auto-detect from CI env
  - fail on ambiguous/no provider context
- Model defaults:
  - primary: `gemini-3-flash-preview`
  - fallback: `gemini-2.5-flash`

## Required template contract

When strict description/template path is active, keep required markers compatible:

- `### Summary`
- `### Problem Brief`
- `### Solution Brief`
- `### How to Test`
- `### Checklist`
- `- [ ] I have tested these changes`

## Environment variables

Always:

- `GOOGLE_API_KEY`
- `CI_PROVIDER` (optional if auto-detect works)

GitLab mode:

- `CI_API_V4_URL`
- `CI_PROJECT_ID`
- `CI_MERGE_REQUEST_IID`
- `GITLAB_TOKEN` or `CI_JOB_TOKEN`

GitHub mode:

- `GITHUB_REPOSITORY`
- `GITHUB_API_TOKEN` or `GITHUB_TOKEN`
- optional: `GITHUB_PR_NUMBER`

Optional runtime tuning (JSON array string):

- `MERGE_POLISHER_SERVICE_PATH_HINTS`
- `MERGE_POLISHER_CRITICAL_PATH_HINTS`
- `MERGE_POLISHER_TEST_PATH_HINTS`

Optional guide override:

- `MERGE_POLISHER_LLM_GUIDE_PATH`

## Dev workflow

Install:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
pytest
```

Run app locally:

```bash
python script.py
```

## Testing expectations

- Add/update focused unit tests for any behavior change.
- Keep `tests/test_app.py` passing for orchestration behavior.
- For marker/policy changes, add coverage in:
  - `tests/test_policy.py`
  - `tests/test_trigger_matrix.py`
  - `tests/test_confidence_comment.py` or related suites
- Do not ship logic change without tests unless explicitly requested.

## Editing guardrails for Claude

- Do not hardcode secrets or tokens.
- Do not silently change marker strings or template contract.
- Do not move core business logic into `app.py`.
- Prefer minimal, surgical diffs.
- Preserve backward compatibility unless task explicitly allows breaking changes.
- If changing external behavior, update docs (`README.md`) and tests together.

## File map

- `app.py`: top-level orchestration
- `script.py`: process entry point
- `application/use_cases/`: staged workflow helpers
- `adapters/gitlab/client.py`: GitLab API integration
- `adapters/github/client.py`: GitHub API integration
- `adapters/llm/gemini_client.py`: Gemini call + payload handling
- `core/constants.py`: markers/models/defaults and limits
- `core/config.py`: runtime hint parsing
- `domain/`: parser, markers, normalization, confidence scoring
- `tests/`: behavior and regression coverage

