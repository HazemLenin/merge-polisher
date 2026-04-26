"""MR-domain helpers for marker extraction and auth configuration."""

import os

from core.runtime import fail, log


def extract_leading_comment_markers(description: str, markers: tuple[str, ...]) -> set[str]:
    """Return markers found before first non-comment/non-whitespace content."""
    found: set[str] = set()
    index = 0
    length = len(description)

    while index < length:
        while index < length and description[index].isspace():
            index += 1
        if index >= length:
            break

        if description.startswith("<!--", index):
            end = description.find("-->", index + 4)
            if end == -1:
                break
            comment_block = description[index : end + 3]
            for marker in markers:
                if marker in comment_block:
                    found.add(marker)
            index = end + 3
            continue

        break

    return found


def is_marker_present(description: str, marker: str) -> bool:
    """Return True when marker appears in leading comment/whitespace block."""
    return marker in extract_leading_comment_markers(description, (marker,))


def build_auth_headers() -> dict:
    """Build GitLab auth headers from available CI token sources."""
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if os.getenv("GITLAB_TOKEN", "").strip():
        headers["PRIVATE-TOKEN"] = os.environ["GITLAB_TOKEN"].strip()
        log("Using GitLab token source: GITLAB_TOKEN")
        return headers
    if os.getenv("CI_JOB_TOKEN", "").strip():
        headers["JOB-TOKEN"] = os.environ["CI_JOB_TOKEN"].strip()
        log("Using GitLab token source: CI_JOB_TOKEN")
        return headers
    fail("Missing GitLab auth token. Provide either GITLAB_TOKEN or CI_JOB_TOKEN.")
    return headers
