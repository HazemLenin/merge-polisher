"""Tests for runtime config parsing."""

import pytest

import core.config as config


def test_load_runtime_config_uses_defaults_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("MERGE_POLISHER_SERVICE_PATH_HINTS", raising=False)
    monkeypatch.delenv("MERGE_POLISHER_CRITICAL_PATH_HINTS", raising=False)
    monkeypatch.delenv("MERGE_POLISHER_TEST_PATH_HINTS", raising=False)
    runtime_config = config.load_runtime_config()
    assert len(runtime_config.service_path_hints) > 0
    assert len(runtime_config.critical_path_hints) > 0
    assert len(runtime_config.test_path_hints) > 0


def test_load_runtime_config_parses_json_and_dedupes(monkeypatch) -> None:
    monkeypatch.setenv(
        "MERGE_POLISHER_SERVICE_PATH_HINTS",
        '["Foo/Bar", "foo/bar", "  ", "Handlers"]',
    )
    runtime_config = config.load_runtime_config()
    assert runtime_config.service_path_hints == ("foo/bar", "handlers")


def test_load_runtime_config_fails_on_invalid_json(monkeypatch) -> None:
    monkeypatch.setenv("MERGE_POLISHER_TEST_PATH_HINTS", "not-json")
    with pytest.raises(SystemExit):
        config.load_runtime_config()
