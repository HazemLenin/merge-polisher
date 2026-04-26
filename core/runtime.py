"""Runtime helpers for logging and fail-fast exits."""

import sys


def log(message: str) -> None:
    """Emit CI-friendly, prefixed log lines."""
    print(f"[enhance-mr-description] {message}", flush=True)


def fail(message: str, code: int = 1) -> None:
    """Log an error and terminate the process."""
    log(f"ERROR: {message}")
    sys.exit(code)
