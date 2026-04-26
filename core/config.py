"""Runtime config parsing for merge polisher."""

import json
import os
from dataclasses import dataclass

from core.constants import CRITICAL_PATH_HINTS, SERVICE_PATH_HINTS, TEST_PATH_HINTS
from core.runtime import fail


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime-tunable settings loaded from CI env."""

    service_path_hints: tuple[str, ...]
    critical_path_hints: tuple[str, ...]
    test_path_hints: tuple[str, ...]


def _parse_hint_list(env_name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return default
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(
            f"Invalid JSON in {env_name}. Expected JSON array of strings. Error: {exc}"
        )
    if not isinstance(parsed, list):
        fail(f"Invalid {env_name}. Expected JSON array of strings.")
    normalized: list[str] = []
    for item in parsed:
        value = str(item or "").strip().lower()
        if not value:
            continue
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        return default
    return tuple(normalized)


def load_runtime_config() -> RuntimeConfig:
    """Load configurable path hints from environment."""
    return RuntimeConfig(
        service_path_hints=_parse_hint_list(
            "MERGE_POLISHER_SERVICE_PATH_HINTS", SERVICE_PATH_HINTS
        ),
        critical_path_hints=_parse_hint_list(
            "MERGE_POLISHER_CRITICAL_PATH_HINTS", CRITICAL_PATH_HINTS
        ),
        test_path_hints=_parse_hint_list(
            "MERGE_POLISHER_TEST_PATH_HINTS", TEST_PATH_HINTS
        ),
    )
