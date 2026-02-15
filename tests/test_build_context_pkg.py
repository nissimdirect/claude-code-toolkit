#!/usr/bin/env python3
"""Tests for build_context_pkg.py — context package builder for LLM delegation."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import build_context_pkg


def test_build_package_returns_dict():
    """build_package() returns a dict with required keys."""
    pkg = build_context_pkg.build_package()
    assert isinstance(pkg, dict)
    assert "generated" in pkg
    assert "version" in pkg
    assert "user" in pkg
    assert "conventions" in pkg


def test_package_has_conventions():
    """Conventions section includes key fields."""
    pkg = build_context_pkg.build_package()
    conv = pkg.get("conventions", {})
    assert "audio_terms" in conv
    assert "security" in conv
    assert "tools" in conv


def test_save_package_under_limit():
    """Saved package stays under MAX_CHARS."""
    pkg = build_context_pkg.build_package()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        tmp_path = Path(f.name)

    # Temporarily override output path
    original = build_context_pkg.OUTPUT_PATH
    build_context_pkg.OUTPUT_PATH = tmp_path
    try:
        char_count = build_context_pkg.save_package(pkg)
        assert char_count <= build_context_pkg.MAX_CHARS, (
            f"Package too large: {char_count} > {build_context_pkg.MAX_CHARS}"
        )
        # Verify it's valid JSON
        content = tmp_path.read_text()
        parsed = json.loads(content)
        assert isinstance(parsed, dict)
    finally:
        build_context_pkg.OUTPUT_PATH = original
        tmp_path.unlink(missing_ok=True)


def test_compress_active_tasks_extracts_focus():
    """_compress_active_tasks() extracts Current Focus section."""
    content = """# Active Tasks

## Current Focus
- Task A (P0)
- Task B (P1)

---

## Backlog
- Task C
"""
    result = build_context_pkg._compress_active_tasks(content)
    assert "Current Focus" in result
    assert "Task A" in result
    assert "Task B" in result


def test_compress_active_tasks_empty():
    """_compress_active_tasks() handles no focus section."""
    result = build_context_pkg._compress_active_tasks("Nothing here")
    assert result == ""


def test_read_file_head_missing_file():
    """_read_file_head() returns empty string for missing file."""
    result = build_context_pkg._read_file_head(Path("/nonexistent/file.md"))
    assert result == ""


def test_read_file_head_respects_limit():
    """_read_file_head() respects max_lines."""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
        for i in range(100):
            f.write(f"Line {i}\n")
        tmp_path = Path(f.name)

    try:
        result = build_context_pkg._read_file_head(tmp_path, max_lines=5)
        lines = result.split("\n")
        assert len(lines) == 5
        assert lines[0] == "Line 0"
        assert lines[4] == "Line 4"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_get_dir_structure_nonexistent():
    """_get_dir_structure() returns empty list for nonexistent dir."""
    result = build_context_pkg._get_dir_structure(Path("/nonexistent/dir"))
    assert result == []


def test_save_trims_when_over_limit():
    """save_package() trims sections when over MAX_CHARS."""
    pkg = {
        "version": "1.0",
        "project_structure": {"big": "x" * 30000},
        "kb_stats": {"also_big": "y" * 30000},
        "conventions": {"small": "ok"},
    }
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        tmp_path = Path(f.name)

    original = build_context_pkg.OUTPUT_PATH
    build_context_pkg.OUTPUT_PATH = tmp_path
    try:
        char_count = build_context_pkg.save_package(pkg)
        content = json.loads(tmp_path.read_text())
        # project_structure should be trimmed first
        assert "project_structure" not in content
        assert char_count <= build_context_pkg.MAX_CHARS
    finally:
        build_context_pkg.OUTPUT_PATH = original
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
