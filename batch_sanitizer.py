#!/usr/bin/env python3
"""Batch sanitizer for multiple KB directories.

Usage:
    python3 batch_sanitizer.py /path/to/dir1 /path/to/dir2 ...

    # Or with all Wave 4-8 dirs:
    python3 batch_sanitizer.py \\
        ~/Development/fonts-in-use \\
        ~/Development/creative-boom \\
        ~/Development/the-brand-identity \\
        ~/Development/its-nice-that
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Import sanitizer from same directory
sys.path.insert(0, str(Path(__file__).parent))
from content_sanitizer import sanitize_directory


def batch_sanitize(directories: list[Path], output_file: Path) -> dict:
    """Run sanitizer on multiple directories and aggregate results."""

    results = {
        'timestamp': datetime.now().isoformat(),
        'directories': [],
        'aggregate': {
            'total_files_scanned': 0,
            'total_files_with_changes': 0,
            'total_injections_found': 0,
            'total_filler_removed': 0,
        }
    }

    for dirpath in directories:
        if not dirpath.exists():
            print(f"SKIP: {dirpath} (does not exist)")
            continue

        print(f"\nProcessing: {dirpath}")
        print("=" * 80)

        # Run sanitizer (not dry-run, max 50K files)
        reports = sanitize_directory(dirpath, dry_run=False, max_files=50000)

        # Aggregate stats for this directory
        files_with_changes = len(reports)
        injections = sum(r['report']['items_removed'] for r in reports)

        # Count filler specifically (items_removed includes all pattern matches)
        filler_count = sum(
            r['report']['items_removed']
            for r in reports
            if any('filler_text' in p for p in r['report']['patterns_matched'])
        )

        dir_summary = {
            'path': str(dirpath),
            'files_scanned': files_with_changes,  # sanitize_directory only returns files with changes
            'files_with_changes': files_with_changes,
            'injections_found': injections,
            'filler_removed': filler_count,
            'reports': reports
        }

        results['directories'].append(dir_summary)

        # Update aggregate
        results['aggregate']['total_files_scanned'] += files_with_changes
        results['aggregate']['total_files_with_changes'] += files_with_changes
        results['aggregate']['total_injections_found'] += injections
        results['aggregate']['total_filler_removed'] += filler_count

        print(f"  Files scanned: {files_with_changes}")
        print(f"  Injections found: {injections}")
        print(f"  Filler removed: {filler_count}")

    # Save full report
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n\nFull report saved to: {output_file}")

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: batch_sanitizer.py <dir1> <dir2> ...")
        sys.exit(1)

    directories = [Path(p).expanduser() for p in sys.argv[1:]]
    output_file = Path(__file__).parent / 'sanitizer_report.json'

    results = batch_sanitize(directories, output_file)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Directories processed: {len(results['directories'])}")
    print(f"Total files scanned: {results['aggregate']['total_files_scanned']}")
    print(f"Total files with changes: {results['aggregate']['total_files_with_changes']}")
    print(f"Total injections found: {results['aggregate']['total_injections_found']}")
    print(f"Total filler removed: {results['aggregate']['total_filler_removed']}")
    print(f"\nReport: {output_file}")


if __name__ == '__main__':
    main()
