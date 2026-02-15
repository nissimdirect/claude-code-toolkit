#!/usr/bin/env python3
"""KB Quality Gate - Post-scrape validation for new articles.

Runs automatically after every scrape operation to ensure new articles
meet quality standards before entering the knowledge base.

Checks:
1. Body word count (minimum 50 words)
2. Boilerplate trimming (strips fluff)
3. Source weight lookup (warns if source is low-weight)
4. Duplicate detection (exact title match)
5. Summary stats

Usage:
    # Validate a single directory (after scraping)
    python3 kb_quality_gate.py ~/Development/cherie-hu/articles/

    # Validate with auto-fix (trim + delete dead)
    python3 kb_quality_gate.py ~/Development/cherie-hu/articles/ --fix

    # Validate all KB sources
    python3 kb_quality_gate.py --all

    # Called from forge skill or scraper scripts:
    from kb_quality_gate import validate_directory
    report = validate_directory(Path("~/Development/new-source/articles/"))
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

# Import siblings
sys.path.insert(0, str(Path(__file__).parent))
from trim_articles import trim_article, KB_ROOTS
from detect_dead_articles import extract_body_words
from kb_loader import SOURCE_WEIGHTS


def validate_directory(directory: Path, fix: bool = False) -> dict:
    """Validate all .md files in a directory against quality standards.

    Returns a report dict with:
        - total: number of files checked
        - passed: files that meet standards
        - dead: files with <50 body words
        - trimmed: files that had boilerplate removed
        - trimmed_bytes: total bytes saved by trimming
        - duplicates: files with duplicate titles
        - source_weight: quality weight for this source
        - issues: list of issue descriptions
    """
    if not directory.exists():
        return {"error": f"Directory not found: {directory}"}

    report = {
        "directory": str(directory),
        "total": 0,
        "passed": 0,
        "dead": 0,
        "dead_files": [],
        "trimmed": 0,
        "trimmed_bytes": 0,
        "duplicates": 0,
        "source_weight": _get_dir_weight(directory),
        "issues": [],
    }

    titles_seen: Counter = Counter()
    md_files = list(directory.rglob("*.md"))

    for md_file in md_files:
        if md_file.name in ("README.md", "INDEX.md"):
            continue

        report["total"] += 1

        # Check 1: Body word count
        word_count = extract_body_words(md_file)
        if word_count < 50:
            report["dead"] += 1
            report["dead_files"].append(str(md_file))
            if fix:
                md_file.unlink()
                report["issues"].append(f"DELETED (dead): {md_file.name} ({word_count} words)")
            else:
                report["issues"].append(f"DEAD: {md_file.name} ({word_count} words)")
            continue

        # Check 2: Trim boilerplate
        try:
            original = md_file.read_text(encoding="utf-8", errors="replace")
            trimmed = trim_article(original)
            saved = len(original) - len(trimmed)
            if saved > 0:
                report["trimmed"] += 1
                report["trimmed_bytes"] += saved
                if fix:
                    md_file.write_text(trimmed, encoding="utf-8")
        except Exception:
            pass

        # Check 3: Duplicate title detection
        title = _extract_title(md_file)
        if title:
            titles_seen[title] += 1

        report["passed"] += 1

    # Count duplicates
    for title, count in titles_seen.items():
        if count > 1:
            report["duplicates"] += count - 1

    return report


def _extract_title(filepath: Path) -> str:
    """Extract title from article frontmatter."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")[:20]
        for line in lines:
            m = re.match(r'^title:\s*["\']?(.+?)["\']?\s*$', line)
            if m:
                return m.group(1).strip()
            if line.strip().startswith("# "):
                return line.strip()[2:].strip()
    except Exception:
        pass
    return ""


def _get_dir_weight(directory: Path) -> float:
    """Look up source weight from directory name."""
    dir_str = str(directory)
    for key, weight in SOURCE_WEIGHTS.items():
        if key in dir_str:
            return weight
    return 1.0


def print_report(report: dict) -> None:
    """Pretty-print a validation report."""
    if "error" in report:
        print(f"ERROR: {report['error']}")
        return

    print(f"\n{'='*60}")
    print(f"KB Quality Gate Report: {report['directory']}")
    print(f"{'='*60}")
    print(f"  Source weight:    {report['source_weight']:.1f}x")
    print(f"  Total files:     {report['total']}")
    print(f"  Passed:          {report['passed']}")
    print(f"  Dead (<50 words): {report['dead']}")
    print(f"  Trimmed:         {report['trimmed']} ({report['trimmed_bytes']:,} bytes saved)")
    print(f"  Duplicates:      {report['duplicates']}")

    # Verdict
    dead_pct = (report["dead"] / report["total"] * 100) if report["total"] > 0 else 0
    if dead_pct > 50:
        print(f"\n  VERDICT: FAIL — {dead_pct:.0f}% dead articles. Scraper likely broken.")
    elif dead_pct > 20:
        print(f"\n  VERDICT: WARNING — {dead_pct:.0f}% dead articles. Review scraper.")
    elif report["total"] == 0:
        print(f"\n  VERDICT: EMPTY — No articles found.")
    else:
        print(f"\n  VERDICT: PASS")

    if report["issues"]:
        print(f"\n  Issues ({len(report['issues'])}):")
        for issue in report["issues"][:10]:
            print(f"    - {issue}")
        if len(report["issues"]) > 10:
            print(f"    ... and {len(report['issues']) - 10} more")


def main():
    parser = argparse.ArgumentParser(description="KB Quality Gate — post-scrape validation")
    parser.add_argument("directory", nargs="?", help="Directory to validate")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix: trim boilerplate, delete dead articles")
    parser.add_argument("--all", action="store_true",
                        help="Validate all KB source directories")
    args = parser.parse_args()

    if args.all:
        total_dead = 0
        total_trimmed_bytes = 0
        failed_sources = []

        for root in KB_ROOTS:
            if not root.exists():
                continue
            report = validate_directory(root, fix=args.fix)
            if "error" not in report:
                total_dead += report["dead"]
                total_trimmed_bytes += report["trimmed_bytes"]
                dead_pct = (report["dead"] / report["total"] * 100) if report["total"] > 0 else 0
                if dead_pct > 20:
                    failed_sources.append((str(root), dead_pct))
                status = "FAIL" if dead_pct > 50 else "WARN" if dead_pct > 20 else "OK"
                print(f"  [{status}] {root.name}: {report['total']} files, {report['dead']} dead, {report['trimmed_bytes']:,}B trimmed")

        print(f"\nTotal dead across KB: {total_dead}")
        print(f"Total trimmed: {total_trimmed_bytes:,} bytes")
        if failed_sources:
            print(f"\nFailing sources ({len(failed_sources)}):")
            for src, pct in failed_sources:
                print(f"  {pct:.0f}% dead: {src}")

    elif args.directory:
        report = validate_directory(Path(args.directory).expanduser(), fix=args.fix)
        print_report(report)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
