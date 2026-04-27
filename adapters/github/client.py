"""GitHub pull request API client helpers."""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set

from core.constants import MAX_DIFF_CONTEXT_CHARS, MAX_DIFF_FILES, MAX_PATCH_CHARS_PER_FILE
from core.runtime import fail, log


def build_pr_endpoint() -> str:
    """Build GitHub PR endpoint from GitHub Actions context."""
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if not repository or "/" not in repository:
        fail("Missing or invalid GITHUB_REPOSITORY (expected 'owner/repo').")
    owner, repo = repository.split("/", 1)
    api_url = os.getenv("GITHUB_API_URL", "https://api.github.com").strip().rstrip("/")
    pr_number = _resolve_pr_number()
    return f"{api_url}/repos/{owner}/{repo}/pulls/{pr_number}"


def _resolve_pr_number() -> str:
    explicit = os.getenv("GITHUB_PR_NUMBER", "").strip()
    if explicit:
        return explicit

    event_name = os.getenv("GITHUB_EVENT_NAME", "").strip()
    event_path = os.getenv("GITHUB_EVENT_PATH", "").strip()
    if event_name == "pull_request" and event_path:
        try:
            with open(event_path, "r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
            number = str((payload.get("pull_request") or {}).get("number") or "").strip()
            if number:
                return number
        except (OSError, json.JSONDecodeError):
            pass

    ref = os.getenv("GITHUB_REF", "").strip()
    ref_match = re.match(r"^refs/pull/(\d+)/", ref)
    if ref_match:
        return ref_match.group(1)

    fail("Unable to resolve pull request number from GitHub Actions context.")
    return ""


def build_auth_headers() -> dict[str, str]:
    """Build GitHub auth headers using configured token precedence."""
    token = os.getenv("GITHUB_API_TOKEN", "").strip() or os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        fail("Missing GitHub auth token. Provide GITHUB_API_TOKEN or GITHUB_TOKEN.")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[bytes] = None,
    retries: int = 3,
    timeout_seconds: int = 30,
) -> Any:
    """Send a GitHub request and decode JSON response with retries."""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url=url, data=body, method=method.upper(), headers=headers
            )
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload) if payload else {}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                sleep_seconds = attempt * 2
                log(
                    f"GitHub API call failed (attempt {attempt}/{retries}): {exc}. "
                    f"Retrying in {sleep_seconds}s..."
                )
                time.sleep(sleep_seconds)
            else:
                break

    fail(f"GitHub API call failed after {retries} attempts: {last_error}")
    return {}


def fetch_mr_description(endpoint: str, headers: Dict[str, str]) -> str:
    """Fetch and return current pull request body."""
    pr_data = request_json("GET", endpoint, headers=headers)
    description = str(pr_data.get("body") or "").strip()
    if not description:
        fail("Pull request description is empty; cannot auto-enhance.")
    return description


def fetch_mr_changes(endpoint: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Fetch PR metadata with files list under GitLab-compatible shape."""
    pr_data = request_json("GET", endpoint, headers=headers)
    files_endpoint = f"{endpoint}/files?per_page=100"
    files_payload = request_json("GET", files_endpoint, headers=headers)
    if not isinstance(files_payload, list):
        fail("GitHub pull request files payload is missing or invalid.")

    changes: list[dict[str, Any]] = []
    for item in files_payload:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        new_path = str(item.get("filename") or "").strip()
        old_path = str(item.get("previous_filename") or new_path).strip()
        changes.append(
            {
                "new_path": new_path,
                "old_path": old_path,
                "renamed_file": status == "renamed",
                "new_file": status == "added",
                "deleted_file": status == "removed",
                "diff": str(item.get("patch") or ""),
            }
        )

    return {
        "source_branch": str((pr_data.get("head") or {}).get("ref") or "").strip(),
        "target_branch": str((pr_data.get("base") or {}).get("ref") or "").strip(),
        "head_sha": str((pr_data.get("head") or {}).get("sha") or "").strip(),
        "base_sha": str((pr_data.get("base") or {}).get("sha") or "").strip(),
        "changes": changes,
    }


def build_diff_context(mr_changes: Dict[str, Any]) -> str:
    """Build bounded prompt context from source-vs-target branch changes."""
    source_branch = (mr_changes.get("source_branch") or "").strip() or "unknown-source"
    target_branch = (mr_changes.get("target_branch") or "").strip() or "unknown-target"
    changes = mr_changes.get("changes") or []
    if not changes:
        return ""

    lines = [
        "Pull Request Diff Context (source branch compared to target branch):",
        f"Source branch: {source_branch}",
        f"Target branch: {target_branch}",
        "",
    ]

    for index, change in enumerate(changes[:MAX_DIFF_FILES], start=1):
        if not isinstance(change, dict):
            continue
        new_path = (change.get("new_path") or change.get("old_path") or "").strip() or "unknown"
        old_path = (change.get("old_path") or "").strip()
        renamed = bool(change.get("renamed_file"))
        status_parts = []
        if change.get("new_file"):
            status_parts.append("new")
        if change.get("deleted_file"):
            status_parts.append("deleted")
        if renamed:
            status_parts.append("renamed")
        status = f" [{', '.join(status_parts)}]" if status_parts else ""

        lines.append(f"### File {index}: {new_path}{status}")
        if renamed and old_path and old_path != new_path:
            lines.append(f"previous path: {old_path}")

        diff_patch = (change.get("diff") or "").strip()
        if diff_patch:
            capped_patch = diff_patch[:MAX_PATCH_CHARS_PER_FILE]
            if len(diff_patch) > MAX_PATCH_CHARS_PER_FILE:
                log(
                    "Truncating diff content for file "
                    f"'{new_path}' from {len(diff_patch)} to {MAX_PATCH_CHARS_PER_FILE} chars."
                )
                capped_patch += "\n... [truncated per-file diff]"
            lines.append("```diff")
            lines.append(capped_patch)
            lines.append("```")
        else:
            lines.append("_No textual patch available from GitHub for this file._")
        lines.append("")

    if len(changes) > MAX_DIFF_FILES:
        skipped_files = len(changes) - MAX_DIFF_FILES
        log(
            "Skipping diff context for "
            f"{skipped_files} file(s) due to MAX_DIFF_FILES={MAX_DIFF_FILES}."
        )
        lines.append(
            f"... [truncated files: showing first {MAX_DIFF_FILES} of {len(changes)} changed files]"
        )

    context = "\n".join(lines).strip()
    if len(context) > MAX_DIFF_CONTEXT_CHARS:
        log(
            "Truncating overall diff context from "
            f"{len(context)} to {MAX_DIFF_CONTEXT_CHARS} chars."
        )
        context = context[:MAX_DIFF_CONTEXT_CHARS].rstrip()
        context += "\n\n... [truncated overall diff context]"
    return context


def update_mr_description(endpoint: str, headers: Dict[str, str], description: str) -> None:
    """Update pull request body in GitHub."""
    payload = json.dumps({"body": description}).encode("utf-8")
    request_json("PATCH", endpoint, headers=headers, body=payload)


def fetch_mr_versions(endpoint: str, headers: Dict[str, str]) -> Dict[str, str]:
    """Fetch latest PR base/head SHAs for comments."""
    pr_data = request_json("GET", endpoint, headers=headers)
    base_sha = str((pr_data.get("base") or {}).get("sha") or "").strip()
    head_sha = str((pr_data.get("head") or {}).get("sha") or "").strip()
    if not base_sha or not head_sha:
        fail("Pull request payload missing required SHAs.")
    return {"base_sha": base_sha, "start_sha": base_sha, "head_sha": head_sha}


def build_changed_new_lines(mr_changes: Dict[str, Any]) -> Dict[str, Set[int]]:
    """Collect changed line numbers on the new side for each file."""
    results: Dict[str, Set[int]] = {}
    hunk_header = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for change in mr_changes.get("changes") or []:
        if not isinstance(change, dict):
            continue
        new_path = (change.get("new_path") or "").strip()
        if not new_path:
            continue

        changed_lines: Set[int] = set()
        diff_patch = (change.get("diff") or "").splitlines()
        new_line = 0
        in_hunk = False
        for line in diff_patch:
            header_match = hunk_header.match(line)
            if header_match:
                new_line = int(header_match.group(1))
                in_hunk = True
                continue
            if not in_hunk:
                continue
            if line.startswith("+") and not line.startswith("+++"):
                changed_lines.add(new_line)
                new_line += 1
                continue
            if line.startswith("-") and not line.startswith("---"):
                continue
            new_line += 1

        if changed_lines:
            results[new_path] = changed_lines

    return results


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def get_plus_line_content_at(
    mr_changes: Dict[str, Any], file_path: str, target_new_line: int
) -> Optional[str]:
    """Return new-side line text (without diff '+') for a changed line, if present."""
    target_path = _normalize_repo_path(file_path)
    for change in mr_changes.get("changes") or []:
        if not isinstance(change, dict):
            continue
        new_path = _normalize_repo_path((change.get("new_path") or "").strip())
        if new_path != target_path:
            continue

        diff_patch = (change.get("diff") or "").splitlines()
        hunk_header = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
        new_line = 0
        in_hunk = False
        for line in diff_patch:
            header_match = hunk_header.match(line)
            if header_match:
                new_line = int(header_match.group(1))
                in_hunk = True
                continue
            if not in_hunk:
                continue
            if line.startswith("+") and not line.startswith("+++"):
                if new_line == target_new_line:
                    content = line[1:]
                    if content.endswith("\r"):
                        content = content[:-1]
                    return content
                new_line += 1
                continue
            if line.startswith("-") and not line.startswith("---"):
                continue
            new_line += 1
    return None


def normalize_inline_suggestion_code(
    mr_changes: Dict[str, Any], file_path: str, new_line: int, suggested_code: str
) -> str:
    _ = get_plus_line_content_at(mr_changes, file_path, new_line)
    return suggested_code.rstrip("\n")


def create_mr_inline_discussion(
    endpoint: str,
    headers: Dict[str, str],
    file_path: str,
    new_line: int,
    versions: Dict[str, str],
    summary: str,
    suggested_code: str,
) -> None:
    """Create an inline PR review comment with a GitHub suggestion block."""
    comments_endpoint = f"{endpoint}/comments"
    body_text = (
        f"{summary.strip()}\n\n"
        "```suggestion\n"
        f"{suggested_code.rstrip()}\n"
        "```"
    )
    payload = json.dumps(
        {
            "body": body_text,
            "commit_id": versions["head_sha"],
            "path": file_path,
            "line": int(new_line),
            "side": "RIGHT",
        }
    ).encode("utf-8")
    request_json("POST", comments_endpoint, headers=headers, body=payload)


def _to_issue_comments_endpoint(endpoint: str) -> str:
    if "/pulls/" not in endpoint:
        fail("Invalid pull request endpoint format for comments.")
    return endpoint.replace("/pulls/", "/issues/") + "/comments"


def fetch_mr_notes(endpoint: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Fetch top-level pull request issue comments."""
    notes_endpoint = _to_issue_comments_endpoint(endpoint)
    notes_payload = request_json("GET", notes_endpoint, headers=headers)
    if not isinstance(notes_payload, list):
        fail("Unable to fetch pull request comments.")
    return [note for note in notes_payload if isinstance(note, dict)]


def filter_notes_by_signature(notes: List[Dict[str, Any]], signature: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for note in notes:
        note_body = str(note.get("body") or "")
        if signature in note_body:
            matches.append(note)
    return matches


def fetch_mr_notes_by_signature(
    endpoint: str, headers: Dict[str, str], signature: str
) -> List[Dict[str, Any]]:
    return filter_notes_by_signature(fetch_mr_notes(endpoint, headers), signature)


def get_latest_note_by_id(notes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    with_id = [note for note in notes if isinstance(note.get("id"), int)]
    if with_id:
        return max(with_id, key=lambda note: int(note["id"]))
    return notes[-1] if notes else None


def extract_sha_from_note_body(note_body: str, sha_marker_prefix: str) -> Optional[str]:
    start_index = note_body.find(sha_marker_prefix)
    if start_index < 0:
        return None
    value_start = start_index + len(sha_marker_prefix)
    value_end = note_body.find("-->", value_start)
    if value_end < 0:
        return None
    sha_value = note_body[value_start:value_end].strip()
    return sha_value or None


def create_mr_note(endpoint: str, headers: Dict[str, str], body: str) -> Dict[str, Any]:
    notes_endpoint = _to_issue_comments_endpoint(endpoint)
    payload = json.dumps({"body": body}).encode("utf-8")
    response = request_json("POST", notes_endpoint, headers=headers, body=payload)
    if not isinstance(response, dict):
        fail("GitHub returned invalid payload while creating pull request comment.")
    return response
