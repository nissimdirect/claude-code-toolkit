"""Gate 5 (Tests after code edit) retrospective analysis.

Trigger: an Edit/Write/MultiEdit to a non-test source file (.py, .ts, .tsx,
.js, .jsx, .rb, .go, .rs, .java, .swift, .cpp, .c, .cs).

Strict: a test file is created/edited later in the same session (within 20
turns of the trigger).
Lenient: any test command (pytest, npm test, vitest, jest, go test, cargo
test, rspec, bun test) is run via Bash anywhere later in the session.

Test file detection:
- filename contains 'test_', '_test', '.test.', '.spec.'
- path includes /tests/, /test/, /__tests__/, /spec/

Excludes plan files, docs, and config — focused on source code.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from retrospective_lib import GateSpec, Turn, run_gate_analysis

OUT_DIR = (
    Path(__file__).parent / "runs" / f"retrospective-gate5-{time.strftime('%Y-%m-%d')}"
)

EDIT_TOOLS = {"Edit", "Write", "MultiEdit"}

SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".rb",
    ".go",
    ".rs",
    ".java",
    ".swift",
    ".cpp",
    ".c",
    ".cs",
    ".kt",
    ".scala",
    ".ex",
    ".exs",
    ".elm",
    ".m",
    ".mm",
}

TEST_PATH_MARKERS = (
    "/tests/",
    "/test/",
    "/__tests__/",
    "/spec/",
    "/specs/",
)
TEST_FILENAME_MARKERS = (
    "test_",
    "_test.",
    ".test.",
    ".spec.",
    "_spec.",
)

TEST_COMMAND_RE = re.compile(
    r"\b(?:pytest|py\.test|"
    r"npm\s+(?:run\s+)?test|"
    r"yarn\s+test|"
    r"pnpm\s+test|"
    r"bun\s+(?:run\s+)?test|"
    r"vitest|jest|"
    r"go\s+test|"
    r"cargo\s+test|"
    r"rspec|"
    r"mocha|tap|ava|"
    r"mvn\s+test|gradle\s+test|"
    r"swift\s+test|xcodebuild\s+test|"
    r"dotnet\s+test|"
    r"mix\s+test)\b",
    re.IGNORECASE,
)

STRICT_FORWARD_WINDOW = 20  # tool calls after trigger to look for test edits


def _is_test_file(file_path: str) -> bool:
    if not file_path:
        return False
    fp = file_path.lower()
    if any(m in fp for m in TEST_PATH_MARKERS):
        return True
    base = Path(fp).name
    return any(m in base for m in TEST_FILENAME_MARKERS)


def _is_source_file(file_path: str) -> bool:
    if not file_path or _is_test_file(file_path):
        return False
    suffix = Path(file_path).suffix.lower()
    return suffix in SOURCE_EXTENSIONS


def _edit_path(t: Turn) -> str:
    if t.tool_name not in EDIT_TOOLS:
        return ""
    inp = t.tool_input or {}
    return str(inp.get("file_path", ""))


def triggers(turns: list[Turn]) -> Iterator[dict[str, Any]]:
    """Each non-test source-file Edit/Write is a trigger."""
    for t in turns:
        fp = _edit_path(t)
        if _is_source_file(fp):
            yield {
                "trigger_idx": t.idx,
                "file_path": fp,
                "tool": t.tool_name,
            }


def is_compliant_strict(trigger: dict[str, Any], turns: list[Turn]) -> bool:
    """Test file edited within STRICT_FORWARD_WINDOW after the trigger."""
    seen_after_trigger = 0
    for t in turns:
        if t.idx <= trigger["trigger_idx"]:
            continue
        if not t.tool_name:
            continue
        seen_after_trigger += 1
        if seen_after_trigger > STRICT_FORWARD_WINDOW:
            return False
        if t.tool_name in EDIT_TOOLS and _is_test_file(_edit_path(t)):
            return True
    return False


def is_compliant_lenient(trigger: dict[str, Any], turns: list[Turn]) -> bool:
    """Any test command Bash call later in the session, OR test file edited."""
    for t in turns:
        if t.idx <= trigger["trigger_idx"]:
            continue
        if t.tool_name in EDIT_TOOLS and _is_test_file(_edit_path(t)):
            return True
        if t.tool_name == "Bash":
            cmd = str((t.tool_input or {}).get("command", ""))
            if TEST_COMMAND_RE.search(cmd):
                return True
    return False


SPEC = GateSpec(
    gate_id="Gate 5",
    title="Tests after code edit",
    strict_definition=(
        f"A test file is edited/written within {STRICT_FORWARD_WINDOW} tool "
        "calls after a non-test source-file edit, in the same session."
    ),
    lenient_definition=(
        "Either a test file edit OR a test command Bash call (pytest, vitest, "
        "go test, cargo test, etc.) appears anywhere later in the session."
    ),
    triggers=triggers,
    is_compliant_strict=is_compliant_strict,
    is_compliant_lenient=is_compliant_lenient,
    caveats=[
        "Trigger fires per source-file edit, so refactor sessions with many edits "
        "but a single test pass at the end will show low strict / high lenient.",
        "'Tests' here means co-located unit/integration tests in the project; "
        "manual UAT or browser testing not detected.",
        "One-off scripts and docs in source-extension files (e.g. ad-hoc analysis "
        ".py files in tools/) over-count triggers — the rule arguably doesn't apply.",
    ],
)


if __name__ == "__main__":
    summary = run_gate_analysis(SPEC, OUT_DIR)
    print(
        f"\n{SPEC.gate_id}: strict={100 * summary['pool_strict']:.2f}%  "
        f"lenient={100 * summary['pool_lenient']:.2f}%  "
        f"(n={summary['n_triggers']})"
    )
    sys.exit(0)
