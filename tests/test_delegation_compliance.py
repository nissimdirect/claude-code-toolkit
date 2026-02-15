#!/usr/bin/env python3
"""Tests for delegation_hook.py v4.2 — parallel race + circuit breaker."""

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path.home() / ".claude" / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import delegation_hook


# --- Compliance tracking tests ---

def test_load_compliance_defaults_have_new_fields():
    """load_compliance() defaults include new tracking fields."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.COMPLIANCE_FILE
    delegation_hook.COMPLIANCE_FILE = tmp_path
    try:
        state = delegation_hook.load_compliance()
        assert "total_prompts" in state
        assert "total_skipped_complexity" in state
        assert "backend_failures" in state
        assert "delegation_rate" in state
        assert state["total_prompts"] == 0
        assert state["backend_failures"] == 0
    finally:
        delegation_hook.COMPLIANCE_FILE = original


def test_load_compliance_forward_compatible():
    """load_compliance() adds missing fields to old-format files."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump({
            "consecutive_ignored": 0,
            "total_advised": 5,
            "total_delegated": 10,
            "total_prefetched": 10,
            "last_date": "2026-02-15",
        }, f)
        tmp_path = Path(f.name)

    original = delegation_hook.COMPLIANCE_FILE
    delegation_hook.COMPLIANCE_FILE = tmp_path
    try:
        state = delegation_hook.load_compliance()
        assert state["total_advised"] == 5
        assert state["total_delegated"] == 10
        assert state["total_prompts"] == 0
        assert state["total_skipped_complexity"] == 0
        assert state["backend_failures"] == 0
        assert state["delegation_rate"] == "0%"
    finally:
        delegation_hook.COMPLIANCE_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_update_compliance_tracks_prompts():
    """update_compliance() increments total_prompts on every call."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.COMPLIANCE_FILE
    delegation_hook.COMPLIANCE_FILE = tmp_path
    try:
        delegation_hook.update_compliance(False, False, False)
        delegation_hook.update_compliance(False, False, False)
        delegation_hook.update_compliance(False, False, False)
        state = json.loads(tmp_path.read_text())
        assert state["total_prompts"] == 3
    finally:
        delegation_hook.COMPLIANCE_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_update_compliance_tracks_complexity_skip():
    """update_compliance() tracks complexity-skipped prompts."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.COMPLIANCE_FILE
    delegation_hook.COMPLIANCE_FILE = tmp_path
    try:
        delegation_hook.update_compliance(False, False, False, complexity_skipped=True)
        delegation_hook.update_compliance(False, False, False, complexity_skipped=True)
        state = json.loads(tmp_path.read_text())
        assert state["total_skipped_complexity"] == 2
    finally:
        delegation_hook.COMPLIANCE_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_update_compliance_tracks_backend_failures():
    """update_compliance() tracks backend failures."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.COMPLIANCE_FILE
    delegation_hook.COMPLIANCE_FILE = tmp_path
    try:
        delegation_hook.update_compliance(True, False, False, backend_failed=True)
        state = json.loads(tmp_path.read_text())
        assert state["backend_failures"] == 1
        assert state["total_advised"] == 1
    finally:
        delegation_hook.COMPLIANCE_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_delegation_rate_computed():
    """update_compliance() computes delegation_rate as percentage."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.COMPLIANCE_FILE
    delegation_hook.COMPLIANCE_FILE = tmp_path
    try:
        delegation_hook.update_compliance(False, True, False)   # prompt 1, delegated
        delegation_hook.update_compliance(False, False, False)   # prompt 2
        delegation_hook.update_compliance(False, True, False)   # prompt 3, delegated
        delegation_hook.update_compliance(False, False, False)   # prompt 4
        state = json.loads(tmp_path.read_text())
        assert state["delegation_rate"] == "50%"
        assert state["total_delegated"] == 2
        assert state["total_prompts"] == 4
    finally:
        delegation_hook.COMPLIANCE_FILE = original
        tmp_path.unlink(missing_ok=True)


# --- Complexity gate tests (stable, no budget awareness) ---

def test_is_too_complex_short():
    """Short simple prompts are NOT complex."""
    assert not delegation_hook.is_too_complex("What is Python?")


def test_is_too_complex_long():
    """Prompts over 2000 chars ARE complex."""
    assert delegation_hook.is_too_complex("x" * 2001)


def test_is_too_complex_keywords():
    """Two complexity keywords trigger the gate."""
    assert delegation_hook.is_too_complex(
        "Please refactor this and do a deep dive into the architecture"
    )


def test_is_too_complex_single_keyword():
    """Single keyword does NOT trigger the gate."""
    assert not delegation_hook.is_too_complex("Please refactor this function")


def test_complexity_gate_stable():
    """Complexity gate uses same thresholds regardless of conditions."""
    msg = "x" * 2001
    assert delegation_hook.is_too_complex(msg)
    # No budget_pct param anymore — always the same behavior
    short_msg = "What is reverb?"
    assert not delegation_hook.is_too_complex(short_msg)


# --- Extraction tests (always smart, no budget tiers) ---

def test_extract_query_uses_focused_extraction():
    """extract_query uses smart focused extraction for long prompts."""
    msg = "Some context here.\nWhat is the best approach?\nBuild a new module.\n" + "x" * 1500
    result = delegation_hook.extract_query(msg)
    assert "What is the best approach?" in result
    assert "Build a new module" in result
    assert len(result) <= delegation_hook.MAX_QUERY_LEN


def test_extract_query_short_passthrough():
    """Short queries pass through without extraction."""
    msg = "What is sidechain compression?"
    result = delegation_hook.extract_query(msg)
    assert result == msg


def test_extract_focused_prioritizes_questions():
    """_extract_focused puts questions first."""
    text = "Line A\nLine B\nWhat should I do?\nLine D"
    result = delegation_hook._extract_focused(text, max_chars=500)
    lines = result.split("\n")
    assert lines[0] == "What should I do?"


def test_extract_summary_keeps_first_and_last():
    """_extract_summary keeps first and last paragraphs."""
    text = "First paragraph.\n\nMiddle stuff.\n\nLast paragraph."
    result = delegation_hook._extract_summary(text, max_chars=500)
    assert "First paragraph" in result
    assert "Last paragraph" in result


# --- Circuit breaker tests ---

def test_breaker_closed_by_default():
    """Circuit breaker is closed when no state file exists."""
    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = Path("/nonexistent/breaker.json")
    try:
        assert not delegation_hook._gemini_breaker_open()
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original


def test_breaker_trips_after_threshold():
    """Breaker trips after GEMINI_BREAKER_THRESHOLD consecutive failures."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = tmp_path
    try:
        # Record failures up to threshold
        for _ in range(delegation_hook.GEMINI_BREAKER_THRESHOLD):
            delegation_hook._gemini_breaker_record(False)

        # Breaker should now be open
        assert delegation_hook._gemini_breaker_open()
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_breaker_resets_on_success():
    """A single success resets the breaker."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = tmp_path
    try:
        # Trip the breaker
        for _ in range(delegation_hook.GEMINI_BREAKER_THRESHOLD):
            delegation_hook._gemini_breaker_record(False)
        assert delegation_hook._gemini_breaker_open()

        # One success resets it
        delegation_hook._gemini_breaker_record(True)
        assert not delegation_hook._gemini_breaker_open()
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_breaker_half_open_after_cooldown():
    """Breaker allows one attempt after cooldown period."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        # Write tripped state with old monotonic timestamp (past cooldown)
        json.dump({
            "failures": delegation_hook.GEMINI_BREAKER_THRESHOLD,
            "tripped_at": time.monotonic() - delegation_hook.GEMINI_BREAKER_COOLDOWN - 1,
        }, f)
        tmp_path = Path(f.name)

    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = tmp_path
    try:
        # Should be half-open (allows attempt)
        assert not delegation_hook._gemini_breaker_open()
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_breaker_stays_open_within_cooldown():
    """Breaker stays tripped within cooldown period."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump({
            "failures": delegation_hook.GEMINI_BREAKER_THRESHOLD,
            "tripped_at": time.monotonic(),  # Just tripped
        }, f)
        tmp_path = Path(f.name)

    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = tmp_path
    try:
        assert delegation_hook._gemini_breaker_open()
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_breaker_below_threshold_stays_closed():
    """Fewer failures than threshold keeps breaker closed."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = tmp_path
    try:
        delegation_hook._gemini_breaker_record(False)
        delegation_hook._gemini_breaker_record(False)
        # 2 failures < threshold (3)
        assert not delegation_hook._gemini_breaker_open()
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original
        tmp_path.unlink(missing_ok=True)


# --- Concurrency stress tests ---

def test_concurrent_breaker_records():
    """Multiple threads recording failures don't corrupt breaker state."""
    import threading as _threading

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = tmp_path
    try:
        errors = []

        def record_failure():
            try:
                delegation_hook._gemini_breaker_record(False)
            except Exception as e:
                errors.append(e)

        # 10 threads all recording failures simultaneously
        threads = [_threading.Thread(target=record_failure) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"

        # Breaker file should exist and be valid JSON
        data = json.loads(tmp_path.read_text())
        assert data["failures"] >= delegation_hook.GEMINI_BREAKER_THRESHOLD
        assert delegation_hook._gemini_breaker_open()
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_concurrent_breaker_mixed_success_failure():
    """Concurrent success + failure don't corrupt breaker state."""
    import threading as _threading

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = tmp_path
    try:
        errors = []

        def record(success):
            try:
                delegation_hook._gemini_breaker_record(success)
            except Exception as e:
                errors.append(e)

        # Mix of successes and failures
        threads = []
        for i in range(20):
            success = (i % 3 == 0)  # ~33% success rate
            threads.append(_threading.Thread(target=record, args=(success,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"

        # File must be valid JSON regardless of race outcome
        data = json.loads(tmp_path.read_text())
        assert "failures" in data
        assert isinstance(data["failures"], int)
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original
        tmp_path.unlink(missing_ok=True)


def test_race_result_holder_consistency():
    """Parallel race result_holder never has mismatched result/model."""
    import threading as _threading

    # Simulate the race pattern from prefetch_from_model
    for _ in range(50):  # Run 50 times to stress-test
        result_lock = _threading.Lock()
        result_holder = [None]
        event = _threading.Event()

        def writer_a():
            with result_lock:
                if not event.is_set():
                    result_holder[0] = ("result_a", "model_a")
                    event.set()

        def writer_b():
            with result_lock:
                if not event.is_set():
                    result_holder[0] = ("result_b", "model_b")
                    event.set()

        ta = _threading.Thread(target=writer_a)
        tb = _threading.Thread(target=writer_b)
        ta.start()
        tb.start()
        event.wait(timeout=2)
        ta.join(timeout=1)
        tb.join(timeout=1)

        # Result must be consistent — result and model must match
        assert result_holder[0] is not None
        result, model = result_holder[0]
        if model == "model_a":
            assert result == "result_a", f"Mismatch: {result_holder[0]}"
        elif model == "model_b":
            assert result == "result_b", f"Mismatch: {result_holder[0]}"
        else:
            assert False, f"Unknown model: {model}"


def test_breaker_state_label():
    """_breaker_state_label returns correct state strings."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = Path(f.name)
    tmp_path.unlink()

    original = delegation_hook.GEMINI_BREAKER_FILE
    delegation_hook.GEMINI_BREAKER_FILE = tmp_path
    try:
        # No file = closed
        assert delegation_hook._breaker_state_label() == "closed"

        # 1 failure = closed(1)
        delegation_hook._gemini_breaker_record(False)
        label = delegation_hook._breaker_state_label()
        assert label == "closed(1)", f"Expected closed(1), got {label}"

        # Trip it
        delegation_hook._gemini_breaker_record(False)
        delegation_hook._gemini_breaker_record(False)
        label = delegation_hook._breaker_state_label()
        assert label == "open", f"Expected open, got {label}"

        # Reset it
        delegation_hook._gemini_breaker_record(True)
        label = delegation_hook._breaker_state_label()
        assert label == "closed(0)" or label == "closed", f"Expected closed, got {label}"
    finally:
        delegation_hook.GEMINI_BREAKER_FILE = original
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test.__name__}: {e}")
    print(f"\n{passed}/{passed + failed} passed")
    sys.exit(1 if failed else 0)
