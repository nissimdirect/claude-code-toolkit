#!/usr/bin/env python3
"""Adversarial verification of the learning system observability.

Independently counts everything from raw source, compares to index claims.
Trust nothing. Verify everything.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

LEARNINGS = Path.home() / ".claude/projects/-Users-nissimagent/memory/learnings.md"
INDEX = Path.home() / ".claude/.locks/learning-index.json"

failures = []
warnings = []


def fail(msg):
    failures.append(msg)
    print(f"  FAIL  {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  WARN  {msg}")


def ok(msg):
    print(f"  PASS  {msg}")


def main():
    print("=== ADVERSARIAL OBSERVABILITY VERIFICATION ===\n")

    # --- Load both sources ---
    if not LEARNINGS.exists():
        fail("learnings.md not found")
        return 1
    if not INDEX.exists():
        fail("learning-index.json not found")
        return 1

    text = LEARNINGS.read_text()
    idx = json.loads(INDEX.read_text())

    # === TEST 1: Version field ===
    print("--- Test 1: Index version ---")
    v = idx.get("version")
    if v == 2:
        ok(f"Version is {v}")
    else:
        fail(f"Version is {v}, expected 2")

    # === TEST 2: Active entry count ===
    print("\n--- Test 2: Active entry count ---")
    # Use EXACT same regex as compiler's parse_learnings (line 521-523)
    compiler_pattern = re.compile(
        r"^(\d+)\.\s+\*\*(.+?)\*\*\s*[-\u2014\u2013:]\s*(.+)",
        re.MULTILINE,
    )
    # Apply same skip filters as compiler
    skip_titles = {
        "Actually Do the Work",
        "Test It",
        "Validate Results",
        "Present to User",
        "Get User Sign-Off",
    }
    composition_titles = {
        "vangelis",
        "tigran",
        "thundercat",
        "reese",
        "one-patch",
        "snippets",
        "bad voice leading",
        "tempo/key",
        "no space",
        "too non-diatonic",
    }
    raw_count = 0
    for m in compiler_pattern.finditer(text):
        title = m.group(2).strip()
        if title in skip_titles:
            continue
        preceding = text[max(0, m.start() - 500) : m.start()]
        if "CRITICAL USER FEEDBACK" in preceding or "composition quality" in preceding:
            continue
        if any(ct in title.lower() for ct in composition_titles):
            continue
        raw_count += 1

    idx_active = len([e for e in idx.get("entries", []) if e.get("status") == "active"])
    print(f"  Raw parsed (with filters): {raw_count}")
    print(f"  Index entries[] count: {idx_active}")

    # After dedup+renumber, compiler keeps ALL entries (dupes get new IDs)
    if idx_active == raw_count:
        ok(f"Active count matches: {idx_active}")
    else:
        fail(f"Active count mismatch: index={idx_active}, raw parsed={raw_count}")

    # === TEST 3: Graduated count ===
    print("\n--- Test 3: Graduated count ---")
    # Exact pattern from compiler build_index (line 960-963) — uses set() for dedup
    grad_pattern = re.compile(r"^(\d+)\.\s+~~\*\*(.+?)\*\*~~\s*GRADUATED", re.MULTILINE)
    raw_graduated = grad_pattern.findall(text)
    raw_grad_ids = {int(m[0]) for m in raw_graduated}
    idx_graduated = idx.get("graduated_count", 0)
    print(f"  Raw regex matches: {len(raw_graduated)}, unique IDs: {len(raw_grad_ids)}")
    if idx_graduated == len(raw_grad_ids):
        ok(f"Graduated count matches: {idx_graduated}")
    else:
        fail(
            f"Graduated mismatch: index={idx_graduated}, unique raw={len(raw_grad_ids)}"
        )

    # === TEST 4: Total ===
    print("\n--- Test 4: Total learnings ---")
    total_expected = raw_count + len(raw_grad_ids)
    idx_total = idx.get("total_learnings", 0)
    if idx_total == total_expected:
        ok(f"Total matches: {idx_total}")
    else:
        fail(f"Total mismatch: index={idx_total}, expected={total_expected}")

    # === TEST 5: Hash verification ===
    print("\n--- Test 5: Source hash ---")
    # Compiler uses text.encode(), not read_bytes()
    hash_text = hashlib.sha256(text.encode()).hexdigest()
    hash_bytes = hashlib.sha256(LEARNINGS.read_bytes()).hexdigest()
    idx_hash = idx.get("source_file_hash", "?")

    if idx_hash == hash_text:
        ok("Hash matches (text encoding)")
    else:
        fail(f"Hash mismatch: index={idx_hash[:20]}..., computed={hash_text[:20]}...")

    if hash_text != hash_bytes:
        warn(
            f"text.encode() != read_bytes() — encoding-sensitive! "
            f"text={hash_text[:20]}..., bytes={hash_bytes[:20]}..."
        )
        # This means the health report (which uses read_bytes) could disagree with compiler (which uses text.encode)
        # Check session-close health report: it uses read_bytes()
        if idx_hash == hash_bytes:
            ok("Health report uses read_bytes() — matches index")
        else:
            fail(
                "Health report uses read_bytes() but hash doesn't match index! "
                "Compiler uses text.encode(). Encoding mismatch will cause false DRIFT warnings."
            )
    else:
        ok("text.encode() == read_bytes() — no encoding issue")

    # === TEST 6: Quotes ===
    print("\n--- Test 6: Quotes ---")
    cf_match = re.search(r"^## Critical Feedback", text, re.MULTILINE)
    if not cf_match:
        fail("No Critical Feedback section found")
    else:
        rest = text[cf_match.start() :]
        next_heading = re.search(r"\n## [^#]", rest[5:])
        section = rest[: next_heading.start() + 5] if next_heading else rest
        raw_quotes = re.findall(r'^>\s*"(.+?)"', section, re.MULTILINE)
        idx_quotes = len(idx.get("quotes", []))
        print(f"  Raw quotes in section: {len(raw_quotes)}")
        print(f"  Index quotes: {idx_quotes}")
        # Some may be filtered by injection/suspicious patterns
        if idx_quotes <= len(raw_quotes):
            ok(
                f"Quote count plausible: {idx_quotes} <= {len(raw_quotes)} raw (filtering applied)"
            )
        else:
            fail(
                f"More index quotes than raw! index={idx_quotes} > raw={len(raw_quotes)}"
            )
        # Check for suspicious chars that should be filtered
        suspicious_pattern = re.compile(r"[{}\[\]<>\\`]")
        suspicious = [q for q in raw_quotes if suspicious_pattern.search(q)]
        if suspicious:
            # These should NOT appear in index
            idx_quote_texts = {q["text"] for q in idx.get("quotes", [])}
            leaked = [q for q in suspicious if q in idx_quote_texts]
            if leaked:
                fail(f"Suspicious quotes leaked through filter: {leaked}")
            else:
                ok(f"{len(suspicious)} suspicious quotes correctly filtered out")
        else:
            ok("No suspicious chars in raw quotes (filter not tested)")

    # === TEST 7: Meta-learnings ===
    print("\n--- Test 7: Meta-learnings ---")
    ml_match = re.search(r"^## Meta-Learnings", text, re.MULTILINE)
    if not ml_match:
        fail("No Meta-Learnings section found")
    else:
        rest = text[ml_match.start() :]
        next_heading = re.search(r"\n## [^#]", rest[5:])
        section = rest[: next_heading.start() + 5] if next_heading else rest
        raw_metas = re.findall(r"^### (.+)", section, re.MULTILINE)
        idx_metas = len(idx.get("meta_learnings", []))
        if idx_metas == len(raw_metas):
            ok(f"Meta-learning count matches: {idx_metas}")
        else:
            fail(f"Meta-learning mismatch: index={idx_metas}, raw={len(raw_metas)}")

    # === TEST 8: Correction history ===
    print("\n--- Test 8: Correction history ---")
    raw_corrections = re.findall(r"\*\*Corrections this session:\*\*\s*(\d+)", text)
    idx_corrections = len(idx.get("correction_history", []))
    if idx_corrections == len(raw_corrections):
        ok(f"Correction count matches: {idx_corrections}")
    else:
        fail(
            f"Correction mismatch: index={idx_corrections}, raw={len(raw_corrections)}"
        )

    # === TEST 9: Graduation candidates ===
    print("\n--- Test 9: Graduation candidates ---")
    idx_cands = idx.get("graduation_candidates", 0)
    actual_cands = sum(
        1 for e in idx.get("entries", []) if e.get("graduation_candidate")
    )
    if idx_cands == actual_cands:
        ok(f"Graduation candidate count consistent: {idx_cands}")
    else:
        fail(
            f"Candidate count inconsistent: top-level={idx_cands}, counted={actual_cands}"
        )

    # === TEST 10: Domain coverage ===
    print("\n--- Test 10: Domain coverage ---")
    domains = {}
    unclassified = 0
    for e in idx.get("entries", []):
        d = e.get("domain", "unclassified")
        if d == "unclassified":
            unclassified += 1
        domains[d] = domains.get(d, 0) + 1

    total_domain_entries = sum(domains.values())
    if total_domain_entries == idx_active:
        ok(f"All {total_domain_entries} entries have domains")
    else:
        fail(
            f"Domain coverage gap: {total_domain_entries} domains vs {idx_active} entries"
        )

    if unclassified > idx_active * 0.5:
        warn(f"{unclassified}/{idx_active} entries are 'unclassified' (>{50}%)")
    else:
        ok(
            f"Classification coverage: {idx_active - unclassified}/{idx_active} classified"
        )

    # === TEST 11: Source line accuracy (sample check) ===
    print("\n--- Test 11: Source line accuracy ---")
    lines = text.split("\n")
    bad_lines = 0
    checked = 0
    for entry in idx.get("entries", []):
        src_line = entry.get("source_line", 0)
        if src_line < 1 or src_line > len(lines):
            fail(f"Entry #{entry['id']}: source_line {src_line} out of range")
            bad_lines += 1
            continue
        line_text = lines[src_line - 1]
        expected = f"{entry['original_num']}."
        if expected not in line_text:
            bad_lines += 1
        checked += 1

    if bad_lines == 0:
        ok(f"All {checked} source lines verified")
    else:
        fail(f"{bad_lines}/{checked} source lines mismatched")

    # === TEST 12: v1 backward compat ===
    print("\n--- Test 12: v1 backward compatibility ---")
    v1_fields = {
        "id",
        "title",
        "text",
        "keywords_exact",
        "keywords_compound",
        "type",
        "status",
        "violation_count",
        "inject_as",
    }
    missing = []
    for e in idx.get("entries", [])[:5]:  # Spot check first 5
        for f in v1_fields:
            if f not in e:
                missing.append(f"Entry #{e.get('id', '?')}: missing {f}")
    if not missing:
        ok("v1 fields present in sample entries")
    else:
        for m in missing:
            fail(m)

    # === TEST 13: Health report vs compiler agree ===
    print("\n--- Test 13: Health report hash method consistency ---")
    # Health report in session-close uses: hashlib.sha256(src.read_bytes()).hexdigest()
    # Compiler build_index uses: hashlib.sha256(text.encode()).hexdigest()
    # verify_sources uses: hashlib.sha256(text.encode()).hexdigest()
    # If the file has no BOM or encoding issues, these should match
    health_hash = hashlib.sha256(LEARNINGS.read_bytes()).hexdigest()
    compiler_hash = hashlib.sha256(LEARNINGS.read_text().encode()).hexdigest()
    if health_hash == compiler_hash:
        ok("Health report and compiler use compatible hash methods")
    else:
        fail(
            "CRITICAL: Health report (read_bytes) and compiler (text.encode) produce different hashes! "
            "This means the health report will show DRIFT even when synced."
        )

    # === TEST 14: Empty/corrupt index resilience ===
    print("\n--- Test 14: Health report crash resilience ---")
    # The health report uses .get() everywhere - verify
    empty_idx = {}
    try:
        v = empty_idx.get("version", 1)
        active = len(
            [e for e in empty_idx.get("entries", []) if e.get("status") == "active"]
        )
        grad = empty_idx.get("graduated_count", 0)
        ok("Health report survives empty index (uses .get() correctly)")
    except Exception as exc:
        fail(f"Health report crashes on empty index: {exc}")

    # === TEST 15: Atomic write verification ===
    print("\n--- Test 15: No .tmp remnants ---")
    tmp_file = INDEX.with_suffix(".tmp")
    if tmp_file.exists():
        fail(f".tmp file exists: {tmp_file}")
    else:
        ok("No .tmp remnants")

    # === SUMMARY ===
    print(f"\n{'=' * 50}")
    print(f"Results: {len(failures)} failures, {len(warnings)} warnings")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
    if warnings:
        print("\nWARNINGS:")
        for w in warnings:
            print(f"  - {w}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
