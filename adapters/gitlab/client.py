"""GitLab API client helpers with retry behavior."""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Set

from adapters.vcs.client import VcsClient
from core.constants import MAX_DIFF_CONTEXT_CHARS, MAX_DIFF_FILES, MAX_PATCH_CHARS_PER_FILE

from core.runtime import fail, log


def build_mr_endpoint(ci_api_v4_url: str, ci_project_id: str, ci_mr_iid: str) -> str:
    """Build the GitLab API endpoint for the current merge request."""
    return (
        f"{ci_api_v4_url}/projects/{urllib.parse.quote(ci_project_id, safe='')}"
        f"/merge_requests/{urllib.parse.quote(ci_mr_iid, safe='')}"
    )


def request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: Optional[bytes] = None,
    retries: int = 3,
    timeout_seconds: int = 30,
) -> Dict:
    """Send a GitLab request and decode JSON response with retries."""
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
                    f"GitLab API call failed (attempt {attempt}/{retries}): {exc}. "
                    f"Retrying in {sleep_seconds}s..."
                )
                time.sleep(sleep_seconds)
            else:
                break

    fail(f"GitLab API call failed after {retries} attempts: {last_error}")
    return {}


def fetch_mr_description(endpoint: str, headers: Dict[str, str]) -> str:
    """Fetch and return current MR description content."""
    mr_data = request_json("GET", endpoint, headers=headers)
    description = (mr_data.get("description") or "").strip()
    if not description:
        fail("Merge request description is empty; cannot auto-enhance.")
    return description


def fetch_mr_changes(endpoint: str, headers: Dict[str, str]) -> Dict:
    """Fetch merge request changes metadata and patch list."""
    changes_endpoint = f"{endpoint}/changes"
    mr_data = request_json("GET", changes_endpoint, headers=headers)
    changes = mr_data.get("changes")
    if not isinstance(changes, list):
        fail("GitLab merge request changes payload is missing or invalid.")
    return mr_data


def build_diff_context(mr_changes: Dict) -> str:
    """Build bounded prompt context from source-vs-target branch changes."""
    source_branch = (mr_changes.get("source_branch") or "").strip() or "unknown-source"
    target_branch = (mr_changes.get("target_branch") or "").strip() or "unknown-target"
    changes = mr_changes.get("changes") or []
    if not changes:
        return ""

    lines = [
        "Merge Request Diff Context (source branch compared to target branch):",
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
            lines.append("_No textual patch available from GitLab for this file._")
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
    """Update MR description in GitLab."""
    payload = urllib.parse.urlencode({"description": description}).encode("utf-8")
    request_json("PUT", endpoint, headers=headers, body=payload)


def fetch_mr_versions(endpoint: str, headers: Dict[str, str]) -> Dict[str, str]:
    """Fetch latest MR versions and return SHAs for discussion positions."""
    versions_endpoint = f"{endpoint}/versions"
    versions_payload = request_json("GET", versions_endpoint, headers=headers)
    if not isinstance(versions_payload, list) or not versions_payload:
        fail("Unable to fetch merge request versions for inline suggestions.")

    latest = versions_payload[0]
    base_sha = (latest.get("base_commit_sha") or "").strip()
    start_sha = (latest.get("start_commit_sha") or "").strip()
    head_sha = (latest.get("head_commit_sha") or "").strip()
    if not base_sha or not start_sha or not head_sha:
        fail("Merge request versions payload missing required SHAs.")

    return {"base_sha": base_sha, "start_sha": start_sha, "head_sha": head_sha}


def build_changed_new_lines(mr_changes: Dict) -> Dict[str, Set[int]]:
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
    mr_changes: Dict, file_path: str, target_new_line: int
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
    mr_changes: Dict, file_path: str, new_line: int, suggested_code: str
) -> str:
    """Pass through model suggestion content with lightweight newline cleanup."""
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
    """Create an inline MR discussion with a GitLab suggestion block."""
    discussions_endpoint = f"{endpoint}/discussions"
    body_text = (
        f"{summary.strip()}\n\n"
        "```suggestion\n"
        f"{suggested_code.rstrip()}\n"
        "```"
    )

    payload_data = {
        "body": body_text,
        "position[position_type]": "text",
        "position[base_sha]": versions["base_sha"],
        "position[start_sha]": versions["start_sha"],
        "position[head_sha]": versions["head_sha"],
        "position[new_path]": file_path,
        "position[new_line]": str(new_line),
    }
    payload = urllib.parse.urlencode(payload_data).encode("utf-8")
    request_json("POST", discussions_endpoint, headers=headers, body=payload)


def fetch_mr_notes(endpoint: str, headers: Dict[str, str]) -> List[Dict]:
    """Fetch top-level merge request notes."""
    notes_endpoint = f"{endpoint}/notes"
    notes_payload = request_json("GET", notes_endpoint, headers=headers)
    if not isinstance(notes_payload, list):
        fail("Unable to fetch merge request notes.")
    return [note for note in notes_payload if isinstance(note, dict)]


def filter_notes_by_signature(notes: List[Dict], signature: str) -> List[Dict]:
    """Return only notes that contain the given signature token."""
    matches: List[Dict] = []
    for note in notes:
        note_body = str(note.get("body") or "")
        if signature in note_body:
            matches.append(note)
    return matches


def fetch_mr_notes_by_signature(endpoint: str, headers: Dict[str, str], signature: str) -> List[Dict]:
    """Fetch MR notes and keep only signature-matching notes."""
    return filter_notes_by_signature(fetch_mr_notes(endpoint, headers), signature)


def get_latest_note_by_id(notes: List[Dict]) -> Optional[Dict]:
    """Return latest note by numeric id, when available."""
    with_id = [note for note in notes if isinstance(note.get("id"), int)]
    if with_id:
        return max(with_id, key=lambda note: int(note["id"]))
    return notes[-1] if notes else None


def extract_sha_from_note_body(note_body: str, sha_marker_prefix: str) -> Optional[str]:
    """Extract embedded SHA from hidden comment marker."""
    start_index = note_body.find(sha_marker_prefix)
    if start_index < 0:
        return None
    value_start = start_index + len(sha_marker_prefix)
    value_end = note_body.find("-->", value_start)
    if value_end < 0:
        return None
    sha_value = note_body[value_start:value_end].strip()
    return sha_value or None


def create_mr_note(endpoint: str, headers: Dict[str, str], body: str) -> Dict:
    """Create a top-level merge request note."""
    notes_endpoint = f"{endpoint}/notes"
    payload = urllib.parse.urlencode({"body": body}).encode("utf-8")
    response = request_json("POST", notes_endpoint, headers=headers, body=payload)
    if not isinstance(response, dict):
        fail("GitLab returned invalid payload while creating MR note.")
    return response


def update_mr_note(endpoint: str, headers: Dict[str, str], note_id: int, body: str) -> Dict:
    """Update an existing top-level merge request note."""
    note_endpoint = f"{endpoint}/notes/{note_id}"
    payload = urllib.parse.urlencode({"body": body}).encode("utf-8")
    response = request_json("PUT", note_endpoint, headers=headers, body=payload)
    if not isinstance(response, dict):
        fail("GitLab returned invalid payload while updating MR note.")
    return response


def upsert_mr_note_by_signature(
    endpoint: str, headers: Dict[str, str], body: str, signature: str
) -> str:
    """Update existing signature-matching note or create one."""
    notes = fetch_mr_notes_by_signature(endpoint, headers, signature)
    for note in notes:
        note_body = str(note.get("body") or "")
        note_id = note.get("id")
        if signature in note_body and isinstance(note_id, int):
            update_mr_note(endpoint, headers, note_id=note_id, body=body)
            return "updated"
    create_mr_note(endpoint, headers, body=body)
    return "created"


def build_client(*, build_endpoint, build_auth_headers) -> VcsClient:
    """Build a provider-agnostic client backed by GitLab API helpers."""
    return VcsClient(
        provider_name="gitlab",
        build_endpoint=build_endpoint,
        build_auth_headers=build_auth_headers,
        fetch_description=fetch_mr_description,
        fetch_changes=fetch_mr_changes,
        build_diff_context=build_diff_context,
        update_description=update_mr_description,
        fetch_versions=fetch_mr_versions,
        build_changed_new_lines=build_changed_new_lines,
        normalize_inline_suggestion_code=normalize_inline_suggestion_code,
        create_inline_discussion=create_mr_inline_discussion,
        fetch_notes_by_signature=fetch_mr_notes_by_signature,
        get_latest_note_by_id=get_latest_note_by_id,
        extract_sha_from_note_body=extract_sha_from_note_body,
        create_note=create_mr_note,
    )
