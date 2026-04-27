# merge_polisher

<p align="center">
  <img src="assets/Logo%20Rounded.png" alt="merge_polisher logo" width="220" />
</p>

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white" />
  <img alt="ci" src="https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white" />
  <img alt="docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white" />
  <img alt="llm" src="https://img.shields.io/badge/LLM-Gemini-8E75B2" />
  <img alt="provider-gitlab" src="https://img.shields.io/badge/VCS-GitLab-FC6D26?logo=gitlab&logoColor=white" />
  <img alt="provider-github" src="https://img.shields.io/badge/VCS-GitHub-181717?logo=github&logoColor=white" />
  <img alt="mr-pr" src="https://img.shields.io/badge/MR%2FPR-Auto_Polish-0EA5E9" />
  <img alt="description" src="https://img.shields.io/badge/Description-Auto_Update-10B981" />
  <img alt="review" src="https://img.shields.io/badge/Inline_Review-Suggestions-14B8A6" />
  <img alt="confidence" src="https://img.shields.io/badge/Confidence-Comment-7C3AED" />
  <img alt="template" src="https://img.shields.io/badge/Template-Validated-6366F1" />
  <img alt="policy" src="https://img.shields.io/badge/Policy-Marker_Driven-F59E0B" />
</p>

AI-assisted merge/pull request description polisher for CI pipelines.

It reads an MR/PR description, validates template sections, analyzes changed files, asks Gemini for structured improvements, then updates:
- the description body,
- optional inline code suggestions,
- optional confidence comment.

Supported providers:
- GitLab merge requests
- GitHub pull requests

## What it does

- Enforces template compatibility before generation.
- Extracts `Problem Brief` and `Solution Brief` from the current MR/PR description.
- Builds bounded diff context from changed files.
- Generates structured JSON with a strict schema (description/review/confidence).
- Publishes results based on marker-driven policy in the description.
- Uses retry + fallback model handling.

## Project structure

- `script.py`: CLI/CI entrypoint.
- `app.py`: orchestration pipeline.
- `adapters/`: VCS, LLM, IO integrations.
- `application/use_cases/`: use-case level orchestration helpers.
- `domain/`: parsing, normalization, confidence logic.
- `core/`: constants, runtime config, policy.
- `markdown/`: template files used by the generator.
- `tests/`: unit tests.

## Requirements

- Python 3.13+
- Gemini API access (`google-genai`)
- CI context for one VCS provider (GitLab or GitHub)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Quick start (local)

1. Install dependencies.
2. Set required environment variables (see below).
3. Run:

```bash
python script.py
```

## Environment variables

### Common

- `GOOGLE_API_KEY` (required): Gemini API key used by `google-genai`.
- `CI_PROVIDER` (optional): force provider (`gitlab` or `github`). If omitted, provider is auto-detected.

### GitLab mode

Required:
- `CI_API_V4_URL`
- `CI_PROJECT_ID`
- `CI_MERGE_REQUEST_IID`

Auth (one required):
- `GITLAB_TOKEN` or
- `CI_JOB_TOKEN`

### GitHub mode

Required:
- `GITHUB_REPOSITORY` (`owner/repo`)

Auth (one required):
- `GITHUB_API_TOKEN` or
- `GITHUB_TOKEN`

PR number resolution:
- Auto-resolved from GitHub Actions event context.
- Optional override: `GITHUB_PR_NUMBER`.

## Marker-based behavior

Put these HTML comment markers at the top of your MR/PR description.

- `<!-- auto-descriptor:on -->`: enable description update.
- `<!-- auto-review:on -->`: enable inline review suggestions.
- `<!-- auto-confidence-comment:on -->`: enable confidence summary comment.

If no marker is enabled, the pipeline exits without publishing changes.

## Description template

Default template path:
- `markdown/DefaultTemplateOutput.md`

Expected key sections include:
- `### Summary`
- `### Problem Brief`
- `### Solution Brief`
- `### How to Test`
- `### Checklist`

## Runtime tuning (optional)

Path hint lists can be overridden with JSON arrays:
- `MERGE_POLISHER_SERVICE_PATH_HINTS`
- `MERGE_POLISHER_CRITICAL_PATH_HINTS`
- `MERGE_POLISHER_TEST_PATH_HINTS`

Example:

```bash
export MERGE_POLISHER_TEST_PATH_HINTS='["/tests/", "__tests__", "integrationtests"]'
```

## Docker

Build image:

```bash
docker build -t merge-polisher:local .
```

Run container:

```bash
docker run --rm \
  -e GOOGLE_API_KEY=... \
  -e CI_PROVIDER=github \
  -e GITHUB_REPOSITORY=owner/repo \
  -e GITHUB_TOKEN=... \
  merge-polisher:local
```

Automated Docker publish workflow:
- `.github/workflows/docker-publish.yml`
- Docs: `docs/docker-publish.md`

## CI

Tests run via:
- `.github/workflows/tests.yml`

Run locally:

```bash
pytest
```

## Troubleshooting

- **"Missing required environment variable"**  
  Ensure provider-specific CI variables are set.

- **"Unable to auto-detect VCS provider"**  
  Set `CI_PROVIDER=gitlab` or `CI_PROVIDER=github`.

- **Gemini quota / API failures**  
  Verify API key and billing/quota. The app retries and can fallback to an alternate model pair.

- **Template validation failure**  
  Ensure required sections exist and marker block is correctly placed at the top.

## Development notes

- Keep `app.py` orchestration thin and logic in use cases/domain modules.
- Add tests for parser/policy/confidence changes.
- Prefer provider-agnostic behavior through `adapters/vcs/provider.py`.
