"""
Rule Canary Runner — executes (scenario × CLAUDE.md variant) cells via Anthropic SDK.

Logs one JSONL row per trial to runs/<run_id>/trials.jsonl.

Usage:
    python3 runner.py \\
        --scenarios scenarios/gate-2/*.json \\
        --variant variants/gate2-on.md \\
        --variant variants/gate2-off.md \\
        --replicates 10 \\
        --model claude-sonnet-4-6 \\
        --run-id pilot-2026-04-16

Pre-registration discipline:
- Pin model ID. Log model_version returned by API.
- Temperature=0. max_tokens=4096. max_iterations=20.
- Shuffle (scenario × variant × replicate) trial order with seeded RNG.
- Drop trials where API errored after 2 retries.
- Halt at $50 cumulative spend (failsafe).
"""

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

try:
    import anthropic
    from anthropic.types import MessageParam, ToolParam
except ImportError:
    sys.exit("anthropic SDK required: pip install anthropic")


# Tool definitions matching Claude Code's surface (subset Gate 2 needs).
# Tool inputs are validated by Claude; handlers below execute against synthetic FS.
TOOL_DEFINITIONS = [
    {
        "name": "Read",
        "description": "Read a file from the filesystem. Returns file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "Edit",
        "description": "Edit a file by replacing old_string with new_string.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
    {
        "name": "Write",
        "description": "Write content to a file (creates or overwrites).",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "Grep",
        "description": "Search file contents for a regex pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "Bash",
        "description": "Execute a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
]


@dataclass
class MockFS:
    """Synthetic filesystem for the trial. Mutated by tool handlers."""

    files: dict[str, str] = field(default_factory=dict)

    def read(self, path: str) -> str:
        if path not in self.files:
            return f"Error: file not found: {path}"
        return self.files[path]

    def edit(self, path: str, old: str, new: str) -> str:
        if path not in self.files:
            return f"Error: file not found: {path}"
        if old not in self.files[path]:
            return f"Error: old_string not found in {path}"
        if self.files[path].count(old) > 1:
            return f"Error: old_string not unique in {path}"
        self.files[path] = self.files[path].replace(old, new, 1)
        return f"Edited {path}"

    def write(self, path: str, content: str) -> str:
        self.files[path] = content
        return f"Wrote {path}"


def handle_tool_call(name: str, tool_input: dict, mock_fs: MockFS) -> str:
    """Execute a tool call against the synthetic FS. Returns string for tool_result."""
    if name == "Read":
        return mock_fs.read(tool_input["file_path"])
    if name == "Edit":
        return mock_fs.edit(
            tool_input["file_path"], tool_input["old_string"], tool_input["new_string"]
        )
    if name == "Write":
        return mock_fs.write(tool_input["file_path"], tool_input["content"])
    if name == "Glob":
        # Return matching synthetic files only (no real FS).
        import fnmatch

        matches = [
            p for p in mock_fs.files if fnmatch.fnmatch(p, tool_input["pattern"])
        ]
        return "\n".join(matches) if matches else "No matches"
    if name == "Grep":
        path = tool_input.get("path", "")
        pat = tool_input["pattern"]
        results = []
        for p, content in mock_fs.files.items():
            if path and p != path:
                continue
            if any(pat in line for line in content.splitlines()):
                results.append(p)
        return "\n".join(results) if results else "No matches"
    if name == "Bash":
        return (
            f"(synthetic FS — Bash not executed; command was: {tool_input['command']})"
        )
    return f"Unknown tool: {name}"


def run_trial(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    scenario: dict,
    max_iterations: int = 20,
) -> dict:
    """Execute one trial. Returns trial record dict."""
    mock_fs = MockFS(files=dict(scenario["synthetic_fs"]))
    messages = [{"role": "user", "content": scenario["user_prompt"]}]
    tool_calls_log: list[dict] = []
    text_outputs: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0
    model_version_seen: str | None = None
    stop_reason: str | None = None
    error: str | None = None
    iterations_completed = 0
    total_cache_read = 0
    total_cache_create = 0
    t_start = time.monotonic()

    for iter_idx in range(max_iterations):
        iterations_completed = iter_idx + 1
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=0,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=cast(list[ToolParam], TOOL_DEFINITIONS),
                messages=cast(list[MessageParam], messages),
            )
        except anthropic.APIError as exc:
            error = f"APIError iter={iter_idx}: {exc}"
            break

        model_version_seen = response.model
        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
        total_cache_read += cache_read
        total_cache_create += cache_create
        stop_reason = response.stop_reason

        # Capture text + tool_use blocks
        assistant_blocks = []
        for block in response.content:
            assistant_blocks.append(block.model_dump())
            if block.type == "text":
                text_outputs.append(block.text)
            elif block.type == "tool_use":
                tool_calls_log.append(
                    {"name": block.name, "input": block.input, "id": block.id}
                )

        messages.append({"role": "assistant", "content": assistant_blocks})

        if response.stop_reason != "tool_use":
            break

        # Execute tool calls and append results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = handle_tool_call(block.name, block.input, mock_fs)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        messages.append({"role": "user", "content": tool_results})
    else:
        stop_reason = "max_iterations"

    latency_s = time.monotonic() - t_start

    # Sonnet 4.6 pricing (USD/M tokens): input $3, output $15,
    # cache read $0.30 (10%), cache create $3.75 (125%)
    uncached_input = total_input_tokens - total_cache_read - total_cache_create
    cost = (
        uncached_input * 3.0
        + total_cache_read * 0.30
        + total_cache_create * 3.75
        + total_output_tokens * 15.0
    ) / 1_000_000

    return {
        "scenario_id": scenario["scenario_id"],
        "tool_calls": tool_calls_log,
        "text_outputs": text_outputs,
        "final_fs_state": dict(mock_fs.files),
        "stop_reason": stop_reason,
        "n_iterations": iterations_completed,
        "model_version": model_version_seen,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "cost_usd": cost,
        "latency_s": latency_s,
        "error": error,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+", required=True, help="Scenario JSON paths")
    ap.add_argument(
        "--variant",
        action="append",
        required=True,
        help="Variant CLAUDE.md path (repeat for multiple arms)",
    )
    ap.add_argument("--replicates", type=int, default=10)
    ap.add_argument("--model", default="claude-sonnet-4-6")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--seed", type=int, default=20260416)
    ap.add_argument(
        "--cost-cap",
        type=float,
        default=50.0,
        help="Halt if cumulative cost exceeds this USD amount",
    )
    args = ap.parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ:
        sys.exit("ANTHROPIC_API_KEY not set")

    out_dir = Path(__file__).parent / "runs" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    trials_path = out_dir / "trials.jsonl"
    if trials_path.exists():
        sys.exit(f"Refusing to overwrite existing run: {trials_path}")

    # Load scenarios + variants
    scenarios = [json.loads(Path(p).read_text()) for p in args.scenarios]
    variants = {Path(v).stem: Path(v).read_text() for v in args.variant}

    # Build trial plan: cross product, then shuffle
    plan = [
        (sc, var_name, rep)
        for sc in scenarios
        for var_name in variants
        for rep in range(args.replicates)
    ]
    rng = random.Random(args.seed)
    rng.shuffle(plan)

    print(f"Plan: {len(plan)} trials. Output: {trials_path}", file=sys.stderr)

    client = anthropic.Anthropic()
    cumulative_cost = 0.0

    with trials_path.open("w") as f:
        for i, (scenario, variant_name, replicate_idx) in enumerate(plan):
            if cumulative_cost > args.cost_cap:
                print(
                    f"COST CAP {args.cost_cap} EXCEEDED at trial {i}; halting",
                    file=sys.stderr,
                )
                break

            trial = run_trial(
                client=client,
                model=args.model,
                system_prompt=variants[variant_name],
                scenario=scenario,
            )
            trial.update(
                {
                    "trial_idx": i,
                    "variant": variant_name,
                    "replicate_idx": replicate_idx,
                    "ts": time.time(),
                }
            )
            f.write(json.dumps(trial) + "\n")
            f.flush()
            cumulative_cost += trial["cost_usd"]

            print(
                f"[{i + 1}/{len(plan)}] {scenario['scenario_id']} "
                f"variant={variant_name} rep={replicate_idx} "
                f"cost=${trial['cost_usd']:.4f} cum=${cumulative_cost:.2f}",
                file=sys.stderr,
            )

    print(
        f"Done. Trials: {trials_path}. Total cost: ${cumulative_cost:.2f}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
