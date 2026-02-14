#!/usr/bin/env python3
"""Coverage Matrix: Verify every mistake maps to ≥1 principle.

Parses behavioral-principles.md cross-reference table and principle headers.
Verifies no orphaned mistakes after compression.

Usage:
    python3 ~/Development/tools/coverage_matrix.py verify
    python3 ~/Development/tools/coverage_matrix.py report
"""

import re
import sys
from pathlib import Path

PRINCIPLES_FILE = (
    Path.home() / '.claude' / 'projects' / '-Users-nissimagent' / 'memory' / 'behavioral-principles.md'
)

# HIGH-severity mistakes that MUST have ≥2 covering principles
HIGH_SEVERITY = {22, 31, 36}


def parse_cross_reference(content: str) -> dict:
    """Parse the Mistake → Principle cross-reference table.

    Returns: {mistake_number: [principle_ids]}
    """
    mappings = {}
    # Match table rows: | number | description | principles |
    for match in re.finditer(
        r'\|\s*(\d+b?)\s*\|[^|]+\|\s*([^|]+)\|', content
    ):
        mistake_id = match.group(1)
        principles_str = match.group(2).strip()
        # Extract principle IDs (P1, P2, MD-1, etc.)
        principle_ids = re.findall(r'(?:P\d+|MD-\d+)', principles_str)
        if principle_ids:
            mappings[mistake_id] = principle_ids
    return mappings


def parse_principle_headers(content: str) -> set:
    """Extract all principle IDs that exist as headers or sections in the file.

    Looks for patterns like "## 1." or "## P1" or "### MD-1" or "[P1]" in text.
    """
    found = set()

    # Match "## N." headers (numbered sections)
    for match in re.finditer(r'^##\s+(\d+)\.', content, re.MULTILINE):
        found.add(f'P{match.group(1)}')

    # Match "## PN" or "P## N" patterns
    for match in re.finditer(r'\bP(\d+)\b', content):
        found.add(f'P{match.group(1)}')

    # Match "### MD-N" meta-directives
    for match in re.finditer(r'\bMD-(\d+)\b', content):
        found.add(f'MD-{match.group(1)}')

    return found


def verify(content: str) -> dict:
    """Run full coverage verification.

    Returns: {
        'total_mistakes': int,
        'covered': int,
        'orphaned': [(mistake_id, [principle_ids])],
        'weakened': [(mistake_id, original_count, current_count)],
        'high_severity_ok': bool,
        'coverage_pct': float,
    }
    """
    mappings = parse_cross_reference(content)
    available = parse_principle_headers(content)

    orphaned = []
    weakened = []
    covered = 0

    for mistake_id, principle_ids in mappings.items():
        # Check which mapped principles exist in the file
        existing = [p for p in principle_ids if p in available]

        if not existing:
            orphaned.append((mistake_id, principle_ids))
        else:
            covered += 1
            if len(existing) < len(principle_ids):
                weakened.append((mistake_id, len(principle_ids), len(existing)))

    # Check HIGH-severity mistakes have ≥2
    high_ok = True
    for m in HIGH_SEVERITY:
        m_str = str(m)
        if m_str in mappings:
            existing = [p for p in mappings[m_str] if p in available]
            if len(existing) < 2:
                high_ok = False

    total = len(mappings)
    coverage_pct = (covered / total * 100) if total > 0 else 0

    return {
        'total_mistakes': total,
        'covered': covered,
        'orphaned': orphaned,
        'weakened': weakened,
        'high_severity_ok': high_ok,
        'coverage_pct': coverage_pct,
        'available_principles': len(available),
    }


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('verify', 'report'):
        print('Usage: coverage_matrix.py verify|report')
        sys.exit(1)

    if not PRINCIPLES_FILE.exists():
        print(f'ERROR: {PRINCIPLES_FILE} not found')
        sys.exit(1)

    content = PRINCIPLES_FILE.read_text()
    result = verify(content)

    if sys.argv[1] == 'report':
        print(f"\n## Coverage Matrix Report")
        print(f"Principles file: {PRINCIPLES_FILE.name}")
        print(f"Available principles: {result['available_principles']}")
        print(f"Total mistakes mapped: {result['total_mistakes']}")
        print(f"Covered: {result['covered']}/{result['total_mistakes']} ({result['coverage_pct']:.1f}%)")
        print(f"Orphaned: {len(result['orphaned'])}")
        print(f"Weakened: {len(result['weakened'])}")
        print(f"HIGH-severity ≥2 check: {'PASS' if result['high_severity_ok'] else 'FAIL'}")

        if result['orphaned']:
            print(f"\n### CRITICAL — Orphaned Mistakes (0 covering principles):")
            for m_id, p_ids in result['orphaned']:
                print(f"  Mistake #{m_id}: needs {', '.join(p_ids)}")

        if result['weakened']:
            print(f"\n### WARNING — Weakened Coverage:")
            for m_id, orig, curr in result['weakened']:
                print(f"  Mistake #{m_id}: {orig} → {curr} principles")

        if not result['orphaned'] and result['high_severity_ok']:
            print(f"\nPASSING: All criteria met.")
        print()

    elif sys.argv[1] == 'verify':
        # Machine-friendly output
        if result['orphaned']:
            print(f"FAIL: {len(result['orphaned'])} orphaned mistakes")
            for m_id, p_ids in result['orphaned']:
                print(f"  #{m_id}: {', '.join(p_ids)}")
            sys.exit(1)
        elif not result['high_severity_ok']:
            print(f"FAIL: HIGH-severity mistakes need ≥2 principles")
            sys.exit(1)
        else:
            print(f"PASS: {result['covered']}/{result['total_mistakes']} covered ({result['coverage_pct']:.0f}%), {result['available_principles']} principles")
            sys.exit(0)


if __name__ == '__main__':
    main()
