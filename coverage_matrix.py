#!/usr/bin/env python3
"""Coverage Matrix + Rule Inflation Gate.

Parses behavioral-principles.md cross-reference table and principle headers.
Verifies no orphaned mistakes after compression.
Enforces hard caps on rule counts to prevent re-inflation.

Usage:
    python3 ~/Development/tools/coverage_matrix.py verify    # Coverage check
    python3 ~/Development/tools/coverage_matrix.py report    # Full report
    python3 ~/Development/tools/coverage_matrix.py gate      # Rule inflation gate
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


CLAUDE_MD = Path.home() / '.claude' / 'CLAUDE.md'

# Hard caps — these are the inflation guardrails.
# Set to current post-compression counts. Adding = merging/replacing.
# To increase a cap: run `gate --set-cap core_principles=50` (requires justification).
CAPS = {
    'core_principles': 45,      # Core Principles section (was 90, compressed to 45)
    'domain_principles': 20,    # Domain Principles section (Music + UX + Security)
    'meta_directives': 10,      # MD-1 through MD-N
    'claude_md_rules': 12,      # Execution Gates + Core Rules in CLAUDE.md
}


def count_sections(content: str) -> dict:
    """Count principles by section in behavioral-principles.md."""
    counts = {
        'core_principles': 0,
        'domain_principles': 0,
        'meta_directives': 0,
    }

    in_core = False
    in_domain = False
    in_meta = False

    for line in content.split('\n'):
        # Section detection
        if '## Core Principles' in line:
            in_core, in_domain, in_meta = True, False, False
            continue
        elif '## Meta-Directives' in line:
            in_core, in_domain, in_meta = False, False, True
            continue
        elif '## Domain Principles' in line:
            in_core, in_domain, in_meta = False, True, False
            continue
        elif line.startswith('## ') and '##' in line[:4]:
            in_core, in_domain, in_meta = False, False, False
            continue

        # Count ### headers as individual principles
        if line.startswith('### P') and in_core:
            counts['core_principles'] += 1
        elif line.startswith('### MD-') and in_meta:
            counts['meta_directives'] += 1
        elif line.startswith('- **P') and in_domain:
            counts['domain_principles'] += 1

    return counts


def count_claude_md_rules(claude_md_path: Path) -> int:
    """Count numbered rules in CLAUDE.md Core Rules section."""
    if not claude_md_path.exists():
        return 0
    content = claude_md_path.read_text()
    # Count lines matching "N. " pattern in Core Rules section
    in_rules = False
    count = 0
    for line in content.split('\n'):
        if 'Core Rules' in line:
            in_rules = True
            continue
        if in_rules and line.startswith('---'):
            break
        if in_rules and re.match(r'^\d+\.\s', line.strip()):
            count += 1
    return count


def gate_check() -> dict:
    """Run the rule inflation gate. Returns pass/fail with details."""
    content = PRINCIPLES_FILE.read_text()
    counts = count_sections(content)
    counts['claude_md_rules'] = count_claude_md_rules(CLAUDE_MD)

    violations = []
    for key, cap in CAPS.items():
        actual = counts.get(key, 0)
        if actual > cap:
            violations.append({
                'category': key,
                'actual': actual,
                'cap': cap,
                'over_by': actual - cap,
            })

    return {
        'counts': counts,
        'caps': CAPS,
        'violations': violations,
        'passed': len(violations) == 0,
    }


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('verify', 'report', 'gate'):
        print('Usage: coverage_matrix.py verify|report|gate')
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

    elif sys.argv[1] == 'gate':
        gate = gate_check()
        print("\n## Rule Inflation Gate")
        print(f"{'Category':<25} {'Count':>5} {'Cap':>5} {'Status':>8}")
        print("-" * 48)
        for key, cap in CAPS.items():
            actual = gate['counts'].get(key, 0)
            status = 'PASS' if actual <= cap else f'OVER +{actual - cap}'
            print(f"{key:<25} {actual:>5} {cap:>5} {status:>8}")

        if gate['passed']:
            print(f"\nGATE PASSED: All categories within caps.")
            sys.exit(0)
        else:
            print(f"\nGATE FAILED: {len(gate['violations'])} cap(s) exceeded.")
            for v in gate['violations']:
                print(f"  {v['category']}: {v['actual']}/{v['cap']} (over by {v['over_by']})")
            print("\nTo add a new rule, you must MERGE or REPLACE an existing one.")
            print("Run: coverage_matrix.py report — to see full coverage.")
            sys.exit(1)


if __name__ == '__main__':
    main()
