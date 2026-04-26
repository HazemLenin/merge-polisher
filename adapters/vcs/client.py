"""Provider-agnostic VCS client contract."""

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class VcsClient:
    """Callable contract used by orchestration and use-cases."""

    provider_name: str
    build_endpoint: Callable[[], str]
    build_auth_headers: Callable[[], dict[str, str]]
    fetch_description: Callable[[str, dict[str, str]], str]
    fetch_changes: Callable[[str, dict[str, str]], dict[str, Any]]
    build_diff_context: Callable[[dict[str, Any]], str]
    update_description: Callable[[str, dict[str, str], str], None]
    fetch_versions: Callable[[str, dict[str, str]], dict[str, str]]
    build_changed_new_lines: Callable[[dict[str, Any]], dict[str, set[int]]]
    normalize_inline_suggestion_code: Callable[[dict[str, Any], str, int, str], str]
    create_inline_discussion: Callable[
        [str, dict[str, str], str, int, dict[str, str], str, str], None
    ]
    fetch_notes_by_signature: Callable[[str, dict[str, str], str], list[dict[str, Any]]]
    get_latest_note_by_id: Callable[[list[dict[str, Any]]], Optional[dict[str, Any]]]
    extract_sha_from_note_body: Callable[[str, str], Optional[str]]
    create_note: Callable[[str, dict[str, str], str], dict[str, Any]]
