"""Tests for io_utils."""

from pathlib import Path

import pytest

import adapters.io.env_reader as env_reader
import adapters.io.file_reader as file_reader


def test_read_required_env_ok(monkeypatch):
    monkeypatch.setenv("MY_REQUIRED_VAR", " value ")
    assert env_reader.read_required_env("MY_REQUIRED_VAR") == "value"


def test_read_required_env_missing(monkeypatch):
    monkeypatch.delenv("MY_REQUIRED_VAR", raising=False)

    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(env_reader, "fail", boom)
    with pytest.raises(RuntimeError, match="MY_REQUIRED_VAR"):
        env_reader.read_required_env("MY_REQUIRED_VAR")


def test_read_text_file_ok(tmp_path: Path):
    p = tmp_path / "f.txt"
    p.write_text("hello\n", encoding="utf-8")
    assert file_reader.read_text_file(p) == "hello\n"


def test_read_text_file_missing(tmp_path: Path, monkeypatch):
    p = tmp_path / "missing.txt"

    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(file_reader, "fail", boom)
    with pytest.raises(RuntimeError, match="not found"):
        file_reader.read_text_file(p)


def test_read_text_file_empty(tmp_path: Path, monkeypatch):
    p = tmp_path / "empty.txt"
    p.write_text("   \n", encoding="utf-8")

    def boom(msg: str, code: int = 1) -> None:
        raise RuntimeError(msg)

    monkeypatch.setattr(file_reader, "fail", boom)
    with pytest.raises(RuntimeError, match="empty"):
        file_reader.read_text_file(p)
