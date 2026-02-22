#!/usr/bin/env python3
"""Quick delegation stats dashboard.

Usage: python3 ~/Development/tools/delegation_stats.py
"""

import json
from pathlib import Path
from collections import Counter

AUDIT_LOG = Path.home() / ".claude" / ".locks" / "delegation-hook-audit.log"
EVAL_LOG = Path.home() / ".claude" / ".locks" / "gemini-route-eval.jsonl"
COMPLIANCE = Path.home() / ".claude" / ".locks" / "delegation-compliance.json"
COUNTER = Path.home() / ".claude" / ".locks" / "gemini-daily-counter.json"
ACC_FILE = Path.home() / ".claude" / ".locks" / "delegation-acceptance.json"


def parse_audit_line(line):
    """Extract key=value pairs from audit log line."""
    parts = {}
    for token in line.split():
        if "=" in token and not token.startswith("["):
            k, v = token.split("=", 1)
            parts[k] = v
    return parts


def main():
    print("=" * 55)
    print("  DELEGATION VISIBILITY DASHBOARD")
    print("=" * 55)

    # --- Hook Audit ---
    if AUDIT_LOG.exists():
        lines = [
            l.strip() for l in AUDIT_LOG.read_text().strip().split("\n") if l.strip()
        ]
        entries = [parse_audit_line(l) for l in lines]

        actions = Counter(e.get("action", "unknown") for e in entries)
        models = Counter(e.get("exec", "unknown") for e in entries)
        prefetched = sum(1 for e in entries if e.get("prefetch") == "OK")
        latencies = [int(e["latency"].rstrip("ms")) for e in entries if "latency" in e]
        avg_lat = sum(latencies) // max(len(latencies), 1) if latencies else 0

        print(f"\n  Hook fires:       {len(entries)}")
        print(
            f"  Pre-fetched OK:   {prefetched} ({prefetched * 100 // max(len(entries), 1)}%)"
        )
        print(f"  Avg latency:      {avg_lat}ms")
        print("\n  Actions:")
        for action, count in actions.most_common():
            print(f"    {action:25s} {count:3d}")
        print("\n  Models executed:")
        for model, count in models.most_common():
            print(f"    {model:25s} {count:3d}")
    else:
        print("\n  No audit log yet.")

    # --- Template Routing (derived from audit log) ---
    if AUDIT_LOG.exists():
        lines = [
            l.strip() for l in AUDIT_LOG.read_text().strip().split("\n") if l.strip()
        ]
        # Extract template routing entries from audit log (action=prefetch_template:*)
        template_entries = []
        for l in lines:
            parsed = parse_audit_line(l)
            action = parsed.get("action", "")
            if action.startswith("prefetch_template:"):
                cat = action.split(":", 1)[1]
                ok = parsed.get("prefetch") == "OK"
                template_entries.append({"category": cat, "success": ok})

        # Count all successful prefetches (template + plain)
        total_prefetch_ok = sum(
            1 for l in lines if parse_audit_line(l).get("prefetch") == "OK"
        )

        if template_entries:
            cats = Counter(e["category"] for e in template_entries)
            ok = sum(1 for e in template_entries if e["success"])
            # Estimate tokens saved: ~2,850 per successful template routing
            est_saved = ok * 2850

            print("\n  --- Template Routing (live from audit log) ---")
            print(f"  Template calls:   {len(template_entries)}")
            print(f"  Success:          {ok}/{len(template_entries)}")
            print(f"  Plain prefetch:   {total_prefetch_ok - ok} additional")
            print(f"  Est tokens saved: ~{est_saved:,}")
            print("\n  By category:")
            for cat, count in cats.most_common():
                print(f"    {cat:25s} {count:3d}")
        else:
            print("\n  No template routing data yet.")

    # --- Gemini Daily Counter ---
    if COUNTER.exists():
        try:
            counter = json.loads(COUNTER.read_text())
            print("\n  --- Gemini API Today ---")
            print(f"  Date:             {counter.get('date', '?')}")
            print(
                f"  Requests:         {counter.get('count', 0)}/200 cap (250 free tier)"
            )
        except (json.JSONDecodeError, OSError):
            pass

    # --- Compliance ---
    if COMPLIANCE.exists():
        try:
            comp = json.loads(COMPLIANCE.read_text())
            print("\n  --- Compliance ---")
            print(f"  Total prompts:    {comp.get('total_prompts', 0)}")
            print(f"  Delegation rate:  {comp.get('delegation_rate', '0%')}")
            print(f"  Backend failures: {comp.get('backend_failures', 0)}")
        except (json.JSONDecodeError, OSError):
            pass

    # --- Skill Delegation (v4.4) ---
    if AUDIT_LOG.exists():
        lines = [
            l.strip() for l in AUDIT_LOG.read_text().strip().split("\n") if l.strip()
        ]
        entries = [parse_audit_line(l) for l in lines]
        skill_entries = [e for e in entries if e.get("source", "").startswith("skill:")]
        natural_entries = [
            e for e in entries if e.get("source", "natural") == "natural"
        ]
        skill_prefetched = sum(1 for e in skill_entries if e.get("prefetch") == "OK")
        natural_prefetched = sum(
            1 for e in natural_entries if e.get("prefetch") == "OK"
        )

        # Count by skill name
        skill_names = Counter(
            e.get("source", "").split(":", 1)[1]
            for e in skill_entries
            if ":" in e.get("source", "")
        )

        print("\n  --- Skill Delegation (v4.4) ---")
        if skill_entries:
            print(
                f"  Skill-sourced:    {len(skill_entries)} ({skill_prefetched} prefetched)"
            )
            print(
                f"  Natural-sourced:  {len(natural_entries)} ({natural_prefetched} prefetched)"
            )
            if skill_names:
                print("  By skill:")
                for name, count in skill_names.most_common(10):
                    print(f"    {name:25s} {count:3d}")
        else:
            print("  No skill delegation data yet (v4.4 entries have source= field)")

    # --- Today's skill breakdown ---
    if COMPLIANCE.exists():
        try:
            comp = json.loads(COMPLIANCE.read_text())
            today_skill = comp.get("today_skill_delegated", 0)
            today_total = comp.get("today_delegated", 0)
            today_natural = today_total - today_skill
            if today_total > 0:
                print(
                    f"\n  Today: {today_skill} skill + {today_natural} natural = {today_total} delegated"
                )
        except (json.JSONDecodeError, OSError):
            pass

    # --- Acceptance ---
    if ACC_FILE.exists():
        try:
            acc = json.loads(ACC_FILE.read_text())
            overall = acc.get("overall", {})
            total = overall.get("total_delegated", 0)
            rejected = overall.get("total_rejected", 0)
            unknown = overall.get("total_unknown", 0)
            sessions = overall.get("sessions_with_delegation", 0)

            print("\n  --- Acceptance ---")
            print(f"  Sessions:         {sessions}")
            print(f"  Total delegated:  {total}")
            if total > 0:
                print(
                    f"  Rejected:         {rejected} ({rejected * 100 // max(total, 1)}%)"
                )
                print(
                    f"  Unknown:          {unknown} ({unknown * 100 // max(total, 1)}%)"
                )
                print("  Signal:           redundant subagent spawn detection")

            # Phase status
            current_phase = acc.get("current_phase", 1)
            phase_names = {
                1: "Core Signal + Honest Reporting",
                2: "Per-Template Attribution + Dual Quality Gate",
                3: "Adaptive Threshold Self-Tuning",
            }
            print("\n  --- Phase Status ---")
            print(
                f"  Current phase:    {current_phase} ({phase_names.get(current_phase, '?')})"
            )
            if current_phase == 1:
                print(f"  Sessions:         {sessions} / 50 required for Phase 2")
                if total > 0:
                    rej_pct = rejected * 100 // max(total, 1)
                    health = "GOOD" if rej_pct > 5 else "LOW (signal may be weak)"
                    print(f"  Rejection rate:   {rej_pct}% (signal health: {health})")
                if sessions >= 50:
                    rej_rate_f = rejected / total if total else 0
                    if rej_rate_f > 0.05:
                        print(
                            "  >>> PHASE 2 IS READY — implement per-template attribution + dual quality gate"
                        )
                    else:
                        print(
                            f"  Signal low ({rej_rate_f:.0%} rej) — revisit at 100 sessions"
                        )
                else:
                    print(
                        f"  Next milestone:   Phase 2 — {50 - sessions} sessions to go"
                    )
        except (json.JSONDecodeError, OSError):
            pass
    else:
        print("\n  No acceptance data yet.")

    print(f"\n{'=' * 55}")


def json_summary():
    """Machine-readable summary for startup_checks.py integration."""
    data = {}

    if AUDIT_LOG.exists():
        lines = [
            l.strip() for l in AUDIT_LOG.read_text().strip().split("\n") if l.strip()
        ]
        entries = [parse_audit_line(l) for l in lines]
        prefetched = sum(1 for e in entries if e.get("prefetch") == "OK")
        data["hook_fires"] = len(entries)
        data["prefetched"] = prefetched

    # Derive routing stats from audit log (eval log is stale since v4.4)
    if AUDIT_LOG.exists():
        lines = [
            l.strip() for l in AUDIT_LOG.read_text().strip().split("\n") if l.strip()
        ]
        template_entries = []
        for l in lines:
            parsed = parse_audit_line(l)
            action = parsed.get("action", "")
            if action.startswith("prefetch_template:"):
                template_entries.append(parsed.get("prefetch") == "OK")
        if template_entries:
            ok = sum(1 for s in template_entries if s)
            data["route_calls"] = len(template_entries)
            data["route_success"] = ok
            data["est_tokens_saved"] = ok * 2850

    if COUNTER.exists():
        try:
            counter = json.loads(COUNTER.read_text())
            data["gemini_today"] = counter.get("count", 0)
            data["gemini_date"] = counter.get("date", "?")
        except (json.JSONDecodeError, OSError):
            pass

    print(json.dumps(data))


if __name__ == "__main__":
    import sys

    if "--json" in sys.argv:
        json_summary()
    else:
        main()
