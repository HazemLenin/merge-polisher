"""Input and file-loading utilities."""

import os
from pathlib import Path

from core.runtime import fail


def read_required_env(name: str) -> str:
    """Return a required environment variable or fail clearly."""
    value = os.getenv(name, "").strip()
    if not value:
        fail(f"Missing required environment variable: {name}")
    return value


def read_text_file(path: Path) -> str:
    """Read a UTF-8 file and fail with actionable messages."""
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"Required file not found: {path}")
    except OSError as exc:
        fail(f"Failed to read file {path}: {exc}")
    if not content.strip():
        fail(f"File is empty: {path}")
    return content
