# Merge Polisher











AI-assisted MR/PR description polisher for CI pipelines.

Merge Polisher reads merge/pull request description, validates template sections, analyzes changed files, asks Gemini for structured improvements, then can publish:

- updated description body,
- optional inline code suggestions,
- optional confidence comment.

Supported providers:

- GitLab merge requests
- GitHub pull requests

## Why use it

- Enforces template compatibility before generation.
- Extracts `Problem Brief` and `Solution Brief` from current MR/PR description.
- Builds bounded diff context from changed files.
- Generates strict JSON payload (`description`, `review`, `confidence`).
- Publishes only by marker-driven policy in description.
- Uses retry + fallback model handling.

## Table of contents

- [Requirements](#requirements)
- [Quick start (local)](#quick-start-local)
- [Required environment variables and token setup](#required-environment-variables-and-token-setup)
- [Marker-based behavior](#marker-based-behavior)
- [Description template](#description-template)
- [Runtime tuning (optional)](#runtime-tuning-optional)
- [Docker](#docker)
- [CI and tests](#ci-and-tests)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Development notes](#development-notes)

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
2. Set required environment variables.
3. Run:

```bash
python script.py
```

## Required environment variables and token setup

Use this section as single source for required variables and auth setup.

### 1) Required variables by mode

Always required:

- `GOOGLE_API_KEY`: Gemini API key used by `google-genai`.
- `CI_PROVIDER` (optional): `gitlab` or `github` (auto-detected if omitted).

GitLab mode:

- `CI_API_V4_URL`
- `CI_PROJECT_ID`
- `CI_MERGE_REQUEST_IID`
- One auth token: `GITLAB_TOKEN` **or** `CI_JOB_TOKEN`

GitHub mode:

- `GITHUB_REPOSITORY` (`owner/repo`)
- One auth token: `GITHUB_API_TOKEN` **or** `GITHUB_TOKEN`
- Optional override: `GITHUB_PR_NUMBER` (if PR number not auto-resolved)

### 2) GitHub token tutorial

For GitHub Actions, prefer built-in workflow token first.

1. In workflow, grant least permissions needed:

```yaml
permissions:
  contents: read
  pull-requests: write
```

2. Use built-in token as `GITHUB_TOKEN`:

```yaml
env:
  GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
  CI_PROVIDER: github
  GITHUB_REPOSITORY: ${{ github.repository }}
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

3. If repo policy blocks built-in token, create fine-grained PAT:
   - Go to `Settings` -> `Developer settings` -> `Personal access tokens` -> `Fine-grained tokens`.
   - Scope token to target repository.
   - Grant minimum repo permissions needed for PR read/write operations.
   - Save as repo secret (for example `MERGE_POLISHER_GH_TOKEN`), then map to `GITHUB_API_TOKEN`.

### 3) GitLab token tutorial

For GitLab CI, prefer `CI_JOB_TOKEN` when project/repo permissions allow it.

1. Start with built-in job token:

```yaml
variables:
  CI_PROVIDER: "gitlab"
```

`CI_JOB_TOKEN`, `CI_API_V4_URL`, `CI_PROJECT_ID`, and MR metadata are usually available in MR pipelines.

2. If job token cannot update MR fields/comments, create project/group access token:
   - Go to project/group `Settings` -> `Access Tokens`.
   - Create token with minimal API scope needed to read/update merge request data.
   - Save token as masked CI variable (for example `GITLAB_TOKEN`).
   - Do not hardcode token in `.gitlab-ci.yml`.

3. Map variables in CI job:

```yaml
merge_polisher:
  image: python:3.13
  script:
    - pip install -r requirements.txt
    - python script.py
  variables:
    GOOGLE_API_KEY: $GOOGLE_API_KEY
    CI_PROVIDER: "gitlab"
    GITLAB_TOKEN: $GITLAB_TOKEN
```

### 4) Local testing examples

GitHub local run:

```bash
export GOOGLE_API_KEY="your_google_api_key"
export CI_PROVIDER="github"
export GITHUB_REPOSITORY="owner/repo"
export GITHUB_API_TOKEN="your_github_token"
python script.py
```

GitLab local run:

```bash
export GOOGLE_API_KEY="your_google_api_key"
export CI_PROVIDER="gitlab"
export CI_API_V4_URL="https://gitlab.com/api/v4"
export CI_PROJECT_ID="123456"
export CI_MERGE_REQUEST_IID="42"
export GITLAB_TOKEN="your_gitlab_token"
python script.py
```

### 5) Security checklist

- Use least-privilege tokens.
- Prefer short-lived CI-issued tokens (`CI_JOB_TOKEN`, workflow `GITHUB_TOKEN`) when possible.
- Store tokens in CI secrets/variables only.
- Rotate tokens regularly.

## Marker-based behavior

Put these HTML comment markers at top of MR/PR description:

- `<!-- auto-descriptor:on -->`: enable description update.
- `<!-- auto-review:on -->`: enable inline review suggestions.
- `<!-- auto-confidence-comment:on -->`: enable confidence summary comment.

If no marker is enabled, pipeline exits without publishing changes.

## Description template

Default template path:

- `markdown/DefaultTemplateOutput.md`

Expected key sections:

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

## CI and tests

Tests run via:

- `.github/workflows/tests.yml`

Run locally:

```bash
pytest
```

## Project structure

- `script.py`: CLI/CI entrypoint.
- `app.py`: orchestration pipeline.
- `adapters/`: VCS, LLM, IO integrations.
- `application/use_cases/`: use-case orchestration helpers.
- `domain/`: parsing, normalization, confidence logic.
- `core/`: constants, runtime config, policy.
- `markdown/`: templates used by generator.
- `tests/`: unit tests.

## Troubleshooting

- **"Missing required environment variable"**  
Ensure provider-specific CI variables are set.
- **"Unable to auto-detect VCS provider"**  
Set `CI_PROVIDER=gitlab` or `CI_PROVIDER=github`.
- **Gemini quota / API failures**  
Verify API key and billing/quota. App retries and can fallback to alternate model pair.
- **Template validation failure**  
Ensure required sections exist and marker block is correctly placed at top.

## Development notes

- Keep `app.py` orchestration thin; keep logic in use cases/domain modules.
- Add tests for parser/policy/confidence changes.
- Prefer provider-agnostic behavior via `adapters/vcs/provider.py`.

