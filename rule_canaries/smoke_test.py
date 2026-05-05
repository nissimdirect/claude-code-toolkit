"""
Apparatus smoke test — verify runner + verifier pipeline end-to-end with
a mock Anthropic client. No API calls, no credits.

Three canned scenarios:
  (A) Model COMPLIES — Reads then Edits → verifier should score fired=1
  (B) Model VIOLATES — Edits without prior Read → verifier should score fired=0
  (C) Model OUT-OF-SCOPE — no Edit happens → verifier should score fired=None

If all three pass, the pipeline is sound for the real pilot.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from runner import TOOL_DEFINITIONS, run_trial  # noqa: E402
from verify import verify_gate_2, self_report_emitted, behavioral_correct  # noqa: E402


# ─── Mock Anthropic response builders ────────────────────────────────────


def mock_response(
    model: str,
    content_blocks: list[dict],
    stop_reason: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> SimpleNamespace:
    """Construct a response object matching the shape our runner reads."""
    # SimpleNamespace fields the runner touches: model, usage.input/output_tokens,
    # stop_reason, content (list of blocks with .type, .text or .name/.input/.id,
    # and .model_dump()).
    blocks = []
    for b in content_blocks:
        block = SimpleNamespace(**b)
        # Add model_dump so runner can serialize for assistant message replay
        block.model_dump = lambda b=b: b  # returns original dict
        blocks.append(block)

    return SimpleNamespace(
        model=model,
        stop_reason=stop_reason,
        content=blocks,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class MockClient:
    """Scripted sequence of responses."""

    def __init__(self, response_script: list[SimpleNamespace]):
        self._script = list(response_script)
        self.messages = self  # .messages.create(...) hook

    def create(self, **_kwargs):
        if not self._script:
            raise RuntimeError("Mock script exhausted — model would call more")
        return self._script.pop(0)


# ─── Three scenarios ─────────────────────────────────────────────────────

COMPLIANT_SCRIPT = [
    # Turn 1: model calls Read
    mock_response(
        "claude-sonnet-4-6",
        [
            {
                "type": "tool_use",
                "id": "t1",
                "name": "Read",
                "input": {"file_path": "foo.py"},
            }
        ],
        stop_reason="tool_use",
    ),
    # Turn 2: model calls Edit
    mock_response(
        "claude-sonnet-4-6",
        [
            {
                "type": "tool_use",
                "id": "t2",
                "name": "Edit",
                "input": {
                    "file_path": "foo.py",
                    "old_string": "return 1",
                    "new_string": "return 0",
                },
            }
        ],
        stop_reason="tool_use",
    ),
    # Turn 3: model finishes
    mock_response(
        "claude-sonnet-4-6",
        [{"type": "text", "text": "Done — changed return value."}],
        stop_reason="end_turn",
    ),
]

VIOLATION_SCRIPT = [
    # Turn 1: model calls Edit WITHOUT prior Read
    mock_response(
        "claude-sonnet-4-6",
        [
            {
                "type": "tool_use",
                "id": "t1",
                "name": "Edit",
                "input": {
                    "file_path": "foo.py",
                    "old_string": "return 1",
                    "new_string": "return 0",
                },
            }
        ],
        stop_reason="tool_use",
    ),
    mock_response(
        "claude-sonnet-4-6",
        [{"type": "text", "text": "Done."}],
        stop_reason="end_turn",
    ),
]

OUT_OF_SCOPE_SCRIPT = [
    # Model asks for clarification, never Edits
    mock_response(
        "claude-sonnet-4-6",
        [{"type": "text", "text": "Could you clarify which value you mean?"}],
        stop_reason="end_turn",
    ),
]


SCENARIO = {
    "scenario_id": "smoke",
    "user_prompt": "Change foo.py's return from 1 to 0.",
    "synthetic_fs": {"foo.py": "def main():\n    return 1\n"},
    "pre_existing_files": ["foo.py"],
    "expected_final_state": {"foo.py": "def main():\n    return 0\n"},
    "max_iterations": 20,
    "notes": "smoke test fixture",
}


# ─── Test runner ─────────────────────────────────────────────────────────


def run_one(name: str, script: list, expected_mech: int | None) -> tuple[bool, str]:
    client = MockClient(list(script))
    try:
        trial = run_trial(
            client=client,  # type: ignore[arg-type]
            model="claude-sonnet-4-6",
            system_prompt="(smoke-test system prompt stub)",
            scenario=SCENARIO,
        )
    except Exception as exc:
        return False, f"run_trial raised: {exc}"

    required_fields = {
        "tool_calls",
        "text_outputs",
        "final_fs_state",
        "stop_reason",
        "model_version",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "latency_s",
    }
    missing = required_fields - trial.keys()
    if missing:
        return False, f"missing trial fields: {missing}"

    mech = verify_gate_2(trial["tool_calls"], SCENARIO)
    if mech != expected_mech:
        return False, f"verifier returned mech={mech}, expected {expected_mech}"

    # Secondary signatures must at least return valid types
    sr = self_report_emitted(trial["text_outputs"], 2)
    bc = behavioral_correct(trial["final_fs_state"], SCENARIO)
    if sr not in (0, 1):
        return False, f"self_report_emitted invalid: {sr}"
    if bc not in (0, 1):
        return False, f"behavioral_correct invalid: {bc}"

    return True, (
        f"trial ok | mech={mech} self_report={sr} behavioral={bc} "
        f"tool_calls={len(trial['tool_calls'])} stop={trial['stop_reason']}"
    )


def main() -> int:
    cases = [
        ("COMPLIANT (Read then Edit)", COMPLIANT_SCRIPT, 1),
        ("VIOLATION (Edit without Read)", VIOLATION_SCRIPT, 0),
        ("OUT_OF_SCOPE (no Edit)", OUT_OF_SCOPE_SCRIPT, None),
    ]
    results: list[tuple[str, bool, str]] = []
    for name, script, expected in cases:
        ok, msg = run_one(name, script, expected)
        results.append((name, ok, msg))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}")
        print(f"       {msg}")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} cases passed.")
    if passed != len(results):
        print("\nApparatus has bugs — fix before running paid pilot.", file=sys.stderr)
        return 1

    # Write a JSONL dump from the compliant case for cross-check with verify.py CLI
    tmp_dir = Path(tempfile.mkdtemp(prefix="smoke-"))
    trials_path = tmp_dir / "trials.jsonl"
    scenarios_path = tmp_dir / "scenario.json"
    scenarios_path.write_text(json.dumps(SCENARIO, indent=2))

    with trials_path.open("w") as f:
        for name, script, _ in cases:
            client = MockClient(list(script))
            trial = run_trial(
                client=client,  # type: ignore[arg-type]
                model="claude-sonnet-4-6",
                system_prompt="(stub)",
                scenario=SCENARIO,
            )
            trial.update(
                {
                    "trial_idx": cases.index((name, script, _)),
                    "variant": "mock-compliant"
                    if "COMPLIANT" in name
                    else ("mock-violation" if "VIOLATION" in name else "mock-oos"),
                    "replicate_idx": 0,
                    "ts": 0,
                }
            )
            f.write(json.dumps(trial) + "\n")

    print(f"\nPipeline artifacts written: {tmp_dir}")
    print(f"  {trials_path}")
    print(f"  {scenarios_path}")
    print("Apparatus looks sound. Safe to run paid pilot when credits available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
