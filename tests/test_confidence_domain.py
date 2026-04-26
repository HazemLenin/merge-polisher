"""Tests for confidence_domain."""

from domain.confidence.scoring import (
    compute_confidence_score,
    summarize_change_signals,
    summarize_change_signals_with_hints,
)
from core.constants import (
    CONFIDENCE_LARGE_SERVICE_DIFF_THRESHOLD,
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
)


def test_summarize_change_signals_empty_changes():
    assert summarize_change_signals({}) == summarize_change_signals({"changes": None})


def test_summarize_change_signals_counts_diff_and_hints():
    diff = "\n".join(["+" + "x" * 200 for _ in range(200)])
    mr_changes = {
        "changes": [
            {
                "new_path": "Main/src/GapMap.Application/Handlers/Accounting/Payment/PostPayment.cs",
                "diff": diff,
            },
            {
                "new_path": "Main/tests/Application.UnitTests/Payment/PaymentTests.cs",
                "diff": "@@ -0,0 +1,1 @@\n+ok\n",
            },
        ]
    }
    s = summarize_change_signals(mr_changes)
    assert s["files_touched"] == 2
    assert s["total_changed_lines"] > 0
    assert s["service_files_touched"] >= 1
    assert s["critical_files_touched"] >= 1
    assert s["has_test_changes"] is True


def test_summarize_large_service_file_flag():
    lines = ["+x"] * (CONFIDENCE_LARGE_SERVICE_DIFF_THRESHOLD + 1)
    diff = "\n".join(lines)
    mr_changes = {
        "changes": [
            {
                "new_path": "Main/src/GapMap.Application/Handlers/Parking/Orders/LargeHandler.cs",
                "diff": diff,
            }
        ]
    }
    s = summarize_change_signals(mr_changes)
    assert s["large_service_files"] == 1


def test_compute_confidence_score_bounded():
    tiny = {
        "total_changed_lines": 10,
        "files_touched": 1,
        "service_files_touched": 0,
        "large_service_files": 0,
        "critical_files_touched": 0,
        "has_test_changes": True,
    }
    low = compute_confidence_score(tiny)
    assert CONFIDENCE_MIN <= low["score"] <= CONFIDENCE_MAX

    huge = {
        "total_changed_lines": 100_000,
        "files_touched": 50,
        "service_files_touched": 5,
        "large_service_files": 2,
        "critical_files_touched": 3,
        "has_test_changes": False,
    }
    high = compute_confidence_score(huge)
    assert high["score"] == CONFIDENCE_MIN
    assert len(high["reasons"]) >= 1


def test_summarize_change_signals_with_runtime_hints():
    mr_changes = {
        "changes": [
            {"new_path": "src/custom-service/foo.py", "diff": "@@ -1 +1 @@\n+ok"},
            {"new_path": "src/custom-tests/foo_test.py", "diff": "@@ -1 +1 @@\n+ok"},
        ]
    }
    summary = summarize_change_signals_with_hints(
        mr_changes=mr_changes,
        service_path_hints=("custom-service",),
        critical_path_hints=("nothing",),
        test_path_hints=("custom-tests",),
    )
    assert summary["service_files_touched"] == 1
    assert summary["test_files_touched"] == 1
