# Merge Polisher

<p align="center">
  <img src="assets/Logo%20Rounded.png" alt="merge_polisher logo" width="220" />
</p>

<!-- Repo Badges -->
<p align="center">
  <a href="https://github.com/HazemLenin/merge-polisher/stargazers">
    <img alt="stars" src="https://badgen.net/github/stars/HazemLenin/merge-polisher?label=stars" />
  </a>
  <a href="https://github.com/HazemLenin/merge-polisher/network/members">
    <img alt="forks" src="https://badgen.net/github/forks/HazemLenin/merge-polisher?label=forks" />
  </a>
  <a href="https://github.com/HazemLenin/merge-polisher/watchers">
    <img alt="watchers" src="https://badgen.net/github/watchers/HazemLenin/merge-polisher?label=watchers" />
  </a>
  <a href="https://github.com/HazemLenin/merge-polisher/issues">
    <img alt="issues" src="https://badgen.net/github/open-issues/HazemLenin/merge-polisher?label=issues" />
  </a>
  <a href="https://github.com/HazemLenin/merge-polisher/pulls">
    <img alt="pull requests" src="https://badgen.net/github/prs/HazemLenin/merge-polisher?label=pull%20requests" />
  </a>
  <a href="https://github.com/HazemLenin/merge-polisher/commits/main">
    <img alt="last commit" src="https://badgen.net/github/last-commit/HazemLenin/merge-polisher?label=last%20commit" />
  </a>
  <a href="https://github.com/HazemLenin/merge-polisher">
    <img alt="repo size" src="https://img.shields.io/github/repo-size/HazemLenin/merge-polisher?label=repo%20size&cacheSeconds=300" />
  </a>
  <a href="https://github.com/HazemLenin/merge-polisher/blob/main/LICENSE">
    <img alt="license" src="https://badgen.net/github/license/HazemLenin/merge-polisher?label=license" />
  </a>
</p>

<!-- Tech Badges -->
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

