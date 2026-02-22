#!/usr/bin/env python3
"""Post-scrape cleanup — runs content sanitizer + quality gate on scraped directories.

Import this from any scraper and call `cleanup()` after scraping completes.
This ensures every scraper automatically sanitizes and validates its output.

Usage (from a scraper):
    from post_scrape_cleanup import cleanup
    cleanup(output_dirs)  # list of Path objects or strings

Usage (CLI):
    python3 post_scrape_cleanup.py ~/Development/knowledge-bases/first-1000/copyblogger
    python3 post_scrape_cleanup.py dir1 dir2 dir3
"""

import sys
from pathlib import Path

# Add tools dir to path so we can import siblings
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))

from content_sanitizer import sanitize_directory
from kb_quality_gate import validate_directory


def cleanup(directories: list, fix: bool = True, max_files_per_dir: int = 5000) -> dict:
    """Run content sanitizer + quality gate on a list of directories.

    Args:
        directories: List of Path objects or strings pointing to article dirs.
        fix: If True, auto-fix issues (delete dead articles, trim boilerplate).
        max_files_per_dir: Safety limit for sanitizer per directory.

    Returns:
        Summary dict with totals across all directories.
    """
    summary = {
        "dirs_processed": 0,
        "sanitizer_files_cleaned": 0,
        "quality_gate_dead": 0,
        "quality_gate_trimmed": 0,
        "quality_gate_trimmed_bytes": 0,
        "quality_gate_passed": 0,
        "quality_gate_total": 0,
        "verdicts": {},
    }

    for d in directories:
        d = Path(d).expanduser()
        if not d.exists():
            print(f"  SKIP (not found): {d}")
            continue

        md_count = len(list(d.rglob("*.md")))
        if md_count == 0:
            print(f"  SKIP (empty): {d}")
            continue

        print(f"\n{'=' * 50}")
        print(f"Cleaning: {d.name} ({md_count} files)")
        print("=" * 50)

        # Step 1: Content sanitizer (prompt injection, filler)
        print("  [1/2] Content sanitizer...")
        reports = sanitize_directory(d, dry_run=False, max_files=max_files_per_dir)
        cleaned = sum(
            1
            for r in reports
            if r.get("report", {}).get("items_removed", 0) > 0
            and r.get("file", "") != "__LIMIT_REACHED__"
        )
        summary["sanitizer_files_cleaned"] += cleaned
        if cleaned > 0:
            print(f"         {cleaned} files sanitized")
        else:
            print("         Clean (no issues)")

        # Step 2: Quality gate (dead articles, boilerplate, dupes)
        print("  [2/2] Quality gate...")
        report = validate_directory(d, fix=fix)
        if "error" in report:
            print(f"         ERROR: {report['error']}")
            continue

        dead = report.get("dead", 0)
        trimmed = report.get("trimmed", 0)
        trimmed_bytes = report.get("trimmed_bytes", 0)
        passed = report.get("passed", 0)
        total = report.get("total", 0)

        summary["quality_gate_dead"] += dead
        summary["quality_gate_trimmed"] += trimmed
        summary["quality_gate_trimmed_bytes"] += trimmed_bytes
        summary["quality_gate_passed"] += passed
        summary["quality_gate_total"] += total
        summary["dirs_processed"] += 1

        # Determine verdict
        if total == 0:
            verdict = "EMPTY"
        elif dead / max(total, 1) > 0.5:
            verdict = "FAIL"
        elif dead / max(total, 1) > 0.2:
            verdict = "WARNING"
        else:
            verdict = "PASS"

        summary["verdicts"][d.name] = verdict
        print(
            f"         {verdict}: {passed}/{total} passed, {dead} dead removed, {trimmed} trimmed ({trimmed_bytes:,}B saved)"
        )

    # Final summary
    print(f"\n{'=' * 50}")
    print("POST-SCRAPE CLEANUP COMPLETE")
    print("=" * 50)
    print(f"  Dirs processed:    {summary['dirs_processed']}")
    print(f"  Sanitizer cleaned: {summary['sanitizer_files_cleaned']} files")
    print(f"  Dead removed:      {summary['quality_gate_dead']}")
    print(
        f"  Trimmed:           {summary['quality_gate_trimmed']} ({summary['quality_gate_trimmed_bytes']:,}B saved)"
    )
    print(
        f"  Quality passed:    {summary['quality_gate_passed']}/{summary['quality_gate_total']}"
    )

    fails = [k for k, v in summary["verdicts"].items() if v == "FAIL"]
    if fails:
        print(
            f"\n  FAILURES: {', '.join(fails)} — scraper may be broken for these sources"
        )

    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 post_scrape_cleanup.py <dir1> [dir2] ...")
        sys.exit(1)

    dirs = [Path(d) for d in sys.argv[1:]]
    cleanup(dirs)
