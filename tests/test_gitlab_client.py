"""Tests for gitlab_client."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import adapters.gitlab.client as gitlab_client
from adapters.gitlab.client import (
    align_suggested_code_indent,
    build_changed_new_lines,
    build_diff_context,
    build_mr_endpoint,
    extract_sha_from_note_body,
    fetch_mr_notes_by_signature,
    filter_notes_by_signature,
    get_latest_note_by_id,
    normalize_inline_suggestion_code,
    request_json,
    upsert_mr_note_by_signature,
)


def test_build_mr_endpoint_encodes_ids():
    url = build_mr_endpoint("https://gitlab/api/v4", "group/sub", "12")
    assert "/projects/group%2Fsub/" in url
    assert url.endswith("/merge_requests/12")


def test_build_diff_context_empty_changes():
    assert build_diff_context({"changes": []}) == ""


def test_build_diff_context_includes_file_header(minimal_mr_changes):
    ctx = build_diff_context(minimal_mr_changes)
    assert "foo.py" in ctx
    assert "```diff" in ctx


def test_build_changed_new_lines_from_unified_diff(minimal_mr_changes):
    lines = build_changed_new_lines(minimal_mr_changes)
    assert lines["src/service/foo.py"] == {1, 2}


def test_align_suggested_code_indent_adds_reference_prefix():
    ref = "    return 1"
    suggested = "return 2"
    out = align_suggested_code_indent(ref, suggested)
    assert out.startswith("    return 2")


def test_normalize_inline_suggestion_code_without_match(minimal_mr_changes):
    out = normalize_inline_suggestion_code(
        minimal_mr_changes, "src/service/foo.py", 99, "x = 1"
    )
    assert out == "x = 1"


def test_request_json_success(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({"ok": True}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = fake_resp
    cm.__exit__.return_value = None

    with patch.object(gitlab_client.urllib.request, "urlopen", return_value=cm) as op:
        data = request_json("GET", "https://example.invalid/api", headers={})
    op.assert_called_once()
    assert data == {"ok": True}


def test_upsert_mr_note_by_signature_updates(monkeypatch):
    calls = []

    def fake_fetch(endpoint, headers):
        return [{"id": 5, "body": "hello <!-- auto-descriptor:confidence-comment -->"}]

    def fake_update(endpoint, headers, note_id, body):
        calls.append(("update", note_id, body))

    monkeypatch.setattr(gitlab_client, "fetch_mr_notes", fake_fetch)
    monkeypatch.setattr(gitlab_client, "update_mr_note", fake_update)
    monkeypatch.setattr(gitlab_client, "create_mr_note", lambda *a, **k: (_ for _ in ()).throw(AssertionError))

    sig = "<!-- auto-descriptor:confidence-comment -->"
    status = upsert_mr_note_by_signature("https://x/api", {}, "new body\n" + sig, sig)
    assert status == "updated"
    assert calls[0][1] == 5


def test_upsert_mr_note_by_signature_creates(monkeypatch):
    calls = []

    def fake_fetch(endpoint, headers):
        return [{"id": 1, "body": "other"}]

    def fake_create(endpoint, headers, body):
        calls.append(("create", body))
        return {"id": 2}

    monkeypatch.setattr(gitlab_client, "fetch_mr_notes", fake_fetch)
    monkeypatch.setattr(gitlab_client, "create_mr_note", fake_create)

    sig = "<!-- auto-descriptor:confidence-comment -->"
    status = upsert_mr_note_by_signature("https://x/api", {}, "first\n" + sig, sig)
    assert status == "created"
    assert calls[0][0] == "create"


def test_filter_notes_by_signature():
    notes = [
        {"id": 1, "body": "hello"},
        {"id": 2, "body": "with <!-- auto-descriptor:confidence-comment --> signature"},
    ]
    sig = "<!-- auto-descriptor:confidence-comment -->"
    filtered = filter_notes_by_signature(notes, sig)
    assert len(filtered) == 1
    assert filtered[0]["id"] == 2


def test_fetch_mr_notes_by_signature(monkeypatch):
    sig = "<!-- auto-descriptor:confidence-comment -->"
    monkeypatch.setattr(
        gitlab_client,
        "fetch_mr_notes",
        lambda _endpoint, _headers: [{"id": 1, "body": sig}, {"id": 2, "body": "nope"}],
    )
    notes = fetch_mr_notes_by_signature("https://x/api", {}, sig)
    assert [n["id"] for n in notes] == [1]


def test_get_latest_note_by_id_prefers_highest_id():
    notes = [{"id": 1, "body": "a"}, {"id": 7, "body": "b"}, {"id": 4, "body": "c"}]
    latest = get_latest_note_by_id(notes)
    assert latest is not None
    assert latest["id"] == 7


def test_get_latest_note_by_id_falls_back_to_last_item():
    notes = [{"body": "a"}, {"body": "b"}]
    latest = get_latest_note_by_id(notes)
    assert latest is not None
    assert latest["body"] == "b"


def test_extract_sha_from_note_body_success():
    prefix = "<!-- auto-descriptor:confidence-head-sha:"
    body = "x\n<!-- auto-descriptor:confidence-comment -->\n<!-- auto-descriptor:confidence-head-sha:abc123 -->"
    assert extract_sha_from_note_body(body, prefix) == "abc123"


def test_extract_sha_from_note_body_missing_or_malformed():
    prefix = "<!-- auto-descriptor:confidence-head-sha:"
    assert extract_sha_from_note_body("no sha marker", prefix) is None
    assert extract_sha_from_note_body("<!-- auto-descriptor:confidence-head-sha:abc123", prefix) is None
