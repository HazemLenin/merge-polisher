# Docker Publish (GitHub Actions)

This repository publishes Docker images to Docker Hub using `.github/workflows/docker-publish.yml`.

## Required GitHub repository secrets

- `DOCKERHUB_USERNAME`: your Docker Hub account username.
- `DOCKERHUB_TOKEN`: a Docker Hub personal access token with write permissions.

To add these secrets in GitHub:

1. Open repository `Settings`.
2. Go to `Secrets and variables` -> `Actions`.
3. Click `New repository secret` and add both values.

## Publish behavior

- Push to `main` publishes:
  - `latest`
  - `sha-<short-commit>`
- Push a version tag like `v1.2.3` publishes:
  - `1.2.3`
  - `1.2`
  - `sha-<short-commit>`

## Validation checklist

1. Push a commit to `main`.
2. Confirm the `Docker Publish` workflow succeeds in GitHub Actions.
3. Verify `latest` and `sha-*` tags exist in Docker Hub.
4. Create and push a test tag (for example `v0.1.0`).
5. Verify version tags appear in Docker Hub.
