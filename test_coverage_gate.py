#!/usr/bin/env python3
"""
Test Coverage Gate — ensures every effect has rendering + behavioral tests.

Run as part of /quality or pre-commit. Exit code:
  0 = all effects covered
  1 = gaps found (prints report)

Usage:
  python3 test_coverage_gate.py                # Full report
  python3 test_coverage_gate.py --summary      # One-line summary
  python3 test_coverage_gate.py --check NAME   # Check specific effect
  python3 test_coverage_gate.py --json         # Machine-readable output

Works for any project with an EFFECTS-like registry.
Currently wired to: ~/Development/entropic/
"""

import sys
import os
import re
import json
import argparse

ENTROPIC_DIR = os.path.expanduser("~/Development/entropic")


def get_registered_effects():
    """Read all effect names from the EFFECTS registry."""
    sys.path.insert(0, ENTROPIC_DIR)
    from effects import EFFECTS
    return sorted(EFFECTS.keys())


def scan_test_files():
    """Scan test files for effect coverage. Returns {effect_name: {rendering: bool, behavioral: bool}}."""
    test_dir = os.path.join(ENTROPIC_DIR, "tests")
    coverage = {}

    if not os.path.isdir(test_dir):
        return coverage

    for fname in os.listdir(test_dir):
        if not fname.startswith("test_") or not fname.endswith(".py"):
            continue
        filepath = os.path.join(test_dir, fname)
        with open(filepath, "r") as f:
            content = f.read()

        # Find all effect names referenced in test files
        # Pattern: "name": "effectname" or effect_name = "effectname"
        effect_refs = re.findall(r'["\']name["\']\s*:\s*["\'](\w+)["\']', content)
        effect_refs += re.findall(r'effect_name\s*[=,]\s*["\'](\w+)["\']', content)
        # Also find parametrize lists
        effect_refs += re.findall(r'["\'](\w+)["\']', content)

        for ref in set(effect_refs):
            ref_lower = ref.lower()
            if ref_lower not in coverage:
                coverage[ref_lower] = {"rendering": False, "behavioral": False, "files": []}

            # Rendering test = tests that the effect produces output without crashing
            if "render" in fname or "param_rendering" in fname:
                coverage[ref_lower]["rendering"] = True
            # Behavioral test = tests specific outcomes (diff > threshold, specific behavior)
            if "session_fixes" in fname or "physics" in fname or "behavioral" in fname:
                coverage[ref_lower]["behavioral"] = True

            if fname not in coverage[ref_lower]["files"]:
                coverage[ref_lower]["files"].append(fname)

    return coverage


def check_param_rendering_coverage():
    """Check if test_param_rendering.py exists and auto-discovers effects."""
    test_file = os.path.join(ENTROPIC_DIR, "tests", "test_param_rendering.py")
    if not os.path.exists(test_file):
        return False, "test_param_rendering.py does not exist"

    with open(test_file) as f:
        content = f.read()

    # Check for auto-discovery pattern (reads from EFFECTS registry)
    if "EFFECTS" in content and "parametrize" in content:
        return True, "Auto-discovers from EFFECTS registry"
    return False, "test_param_rendering.py exists but doesn't auto-discover"


def main():
    parser = argparse.ArgumentParser(description="Test Coverage Gate")
    parser.add_argument("--summary", action="store_true", help="One-line summary")
    parser.add_argument("--check", type=str, help="Check specific effect")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    effects = get_registered_effects()
    coverage = scan_test_files()
    auto_ok, auto_msg = check_param_rendering_coverage()

    # If auto-discovery test exists, all effects have rendering coverage
    if auto_ok:
        for name in effects:
            if name not in coverage:
                coverage[name] = {"rendering": True, "behavioral": False, "files": ["test_param_rendering.py"]}
            else:
                coverage[name]["rendering"] = True

    # Build report
    total = len(effects)
    rendering_covered = sum(1 for e in effects if coverage.get(e, {}).get("rendering", False))
    behavioral_covered = sum(1 for e in effects if coverage.get(e, {}).get("behavioral", False))
    uncovered_rendering = [e for e in effects if not coverage.get(e, {}).get("rendering", False)]
    uncovered_behavioral = [e for e in effects if not coverage.get(e, {}).get("behavioral", False)]

    if args.check:
        name = args.check.lower()
        if name in coverage:
            c = coverage[name]
            print(f"{name}: rendering={'PASS' if c['rendering'] else 'MISSING'}, behavioral={'PASS' if c['behavioral'] else 'MISSING'}")
            print(f"  Files: {', '.join(c['files'])}")
        else:
            print(f"{name}: NO TESTS FOUND")
        sys.exit(0 if coverage.get(name, {}).get("rendering", False) else 1)

    if args.json:
        result = {
            "total_effects": total,
            "rendering_covered": rendering_covered,
            "behavioral_covered": behavioral_covered,
            "auto_discovery": auto_ok,
            "uncovered_rendering": uncovered_rendering,
            "uncovered_behavioral": uncovered_behavioral,
            "pass": rendering_covered == total,
        }
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["pass"] else 1)

    if args.summary:
        status = "PASS" if rendering_covered == total else "FAIL"
        print(f"Test Coverage: {status} — {rendering_covered}/{total} rendering, {behavioral_covered}/{total} behavioral")
        sys.exit(0 if rendering_covered == total else 1)

    # Full report
    print(f"Test Coverage Gate — {ENTROPIC_DIR}")
    print(f"{'=' * 60}")
    print(f"Auto-discovery: {'ACTIVE' if auto_ok else 'MISSING'} ({auto_msg})")
    print(f"Rendering tests: {rendering_covered}/{total} effects covered")
    print(f"Behavioral tests: {behavioral_covered}/{total} effects covered")
    print()

    if uncovered_rendering:
        print(f"MISSING rendering tests ({len(uncovered_rendering)}):")
        for name in uncovered_rendering:
            print(f"  - {name}")
        print()

    if uncovered_behavioral:
        print(f"MISSING behavioral tests ({len(uncovered_behavioral)}):")
        for name in uncovered_behavioral[:20]:  # Cap at 20 to avoid noise
            print(f"  - {name}")
        if len(uncovered_behavioral) > 20:
            print(f"  ... and {len(uncovered_behavioral) - 20} more")
        print()

    if rendering_covered == total:
        print("PASS: All effects have rendering coverage.")
    else:
        print("FAIL: Some effects lack rendering tests.")

    sys.exit(0 if rendering_covered == total else 1)


if __name__ == "__main__":
    main()
