"""
Schema validator for scenario JSON files.

Usage:
    python3 validate_scenarios.py scenarios/gate-2/*.json

Exit status: 0 if all pass, 1 otherwise.
"""

import json
import sys
from pathlib import Path

REQUIRED_FIELDS = {
    "scenario_id": str,
    "user_prompt": str,
    "synthetic_fs": dict,
    "pre_existing_files": list,
    "expected_final_state": dict,
    "max_iterations": int,
}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"JSON parse error: {exc}"]

    if not isinstance(data, dict):
        return ["Top-level must be a JSON object"]

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"Missing required field: {field}")
            continue
        if not isinstance(data[field], expected_type):
            errors.append(
                f"Field '{field}' must be {expected_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )

    if errors:
        return errors

    if data["scenario_id"] != path.stem:
        errors.append(
            f"scenario_id '{data['scenario_id']}' does not match filename stem '{path.stem}'"
        )

    if data["max_iterations"] < 1 or data["max_iterations"] > 50:
        errors.append(f"max_iterations should be 1-50, got {data['max_iterations']}")

    for p in data["pre_existing_files"]:
        if not isinstance(p, str):
            errors.append(
                f"pre_existing_files entries must be strings, got {type(p).__name__}"
            )
        elif p not in data["synthetic_fs"]:
            errors.append(
                f"pre_existing_files entry '{p}' is not in synthetic_fs — "
                f"file should exist before the task"
            )

    for path_key, content in data["synthetic_fs"].items():
        if not isinstance(path_key, str) or not isinstance(content, str):
            errors.append(
                f"synthetic_fs entries must be string→string, got {path_key}: {type(content).__name__}"
            )

    for path_key, content in data["expected_final_state"].items():
        if not isinstance(path_key, str) or not isinstance(content, str):
            errors.append(
                f"expected_final_state entries must be string→string, got {path_key}: {type(content).__name__}"
            )

    if not data["user_prompt"].strip():
        errors.append("user_prompt is empty or whitespace-only")

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("Usage: validate_scenarios.py <scenario.json> [scenario.json ...]")

    paths = [Path(p) for p in sys.argv[1:]]
    total = len(paths)
    failed: list[tuple[Path, list[str]]] = []

    for p in paths:
        if not p.exists():
            failed.append((p, ["File does not exist"]))
            continue
        errs = validate(p)
        if errs:
            failed.append((p, errs))

    if failed:
        for p, errs in failed:
            print(f"\nFAIL {p}:")
            for e in errs:
                print(f"  - {e}")
        print(f"\n{len(failed)}/{total} files failed validation.")
        return 1

    print(f"OK — all {total} files valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
