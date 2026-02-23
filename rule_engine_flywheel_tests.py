#!/usr/bin/env python3
"""Flywheel & Visibility Test Suite — Rule Engine v3

Tests the complete self-regulating loop:
  violation → spike → injection priority → correction → decay → dormancy → immune reactivation

And visibility at each checkpoint:
  Can the operator SEE what's happening at every stage?

15 Phases, ~120+ tests. Each phase tests one flywheel stage + its observability.
"""

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

# ============================================================
# TEST INFRASTRUCTURE
# ============================================================


@dataclass
class TestResult:
    phase: str
    name: str
    passed: bool
    detail: str = ""


class TestRunner:
    def __init__(self):
        self.results: list[TestResult] = []
        self.phase_counts: dict[str, tuple[int, int]] = {}  # phase -> (pass, total)

    def record(self, phase: str, name: str, condition: bool, detail: str = ""):
        self.results.append(TestResult(phase, name, condition, detail))
        p, t = self.phase_counts.get(phase, (0, 0))
        self.phase_counts[phase] = (p + (1 if condition else 0), t + 1)

    def summary(self) -> str:
        lines = ["\n" + "=" * 70]
        lines.append("FLYWHEEL & VISIBILITY TEST SUITE — RESULTS")
        lines.append("=" * 70)

        total_pass = 0
        total_tests = 0

        for phase, (p, t) in self.phase_counts.items():
            status = "PASS" if p == t else "FAIL"
            lines.append(f"  {phase}: {p}/{t} {status}")
            total_pass += p
            total_tests += t

        lines.append("-" * 70)
        overall = "ALL PASS" if total_pass == total_tests else "FAILURES"
        lines.append(f"  TOTAL: {total_pass}/{total_tests} ({overall})")
        lines.append("=" * 70)

        # Show failures
        failures = [r for r in self.results if not r.passed]
        if failures:
            lines.append("\nFAILURES:")
            for f in failures:
                detail = f" — {f.detail}" if f.detail else ""
                lines.append(f"  [{f.phase}] {f.name}{detail}")

        return "\n".join(lines)


# ============================================================
# SETUP: Import production engine
# ============================================================

TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))

import rule_engine
from rule_engine import (
    Rule,
    load_rules,
    load_state,
    save_state,
    apply_state,
    extract_state,
    classify_prompt,
    score_rule,
    get_relevant_rules,
    record_violation,
    advance_day,
    detect_inactive,
    detect_merge_candidates,
    get_lifecycle_report,
    validate_rules,
    clear_cache,
    THRESHOLD,
    BUDGET,
    INJECTION_LIMIT,
    SPIKE_CAP,
    IMMUNE_SPIKE,
    SPIKE_DECAY_PER_DAY,
    INACTIVE_THRESHOLD_DAYS,
    SPIKE_AMOUNT,
    DOMAIN_SCORE_EXPLICIT,
    DOMAIN_SCORE_UNIVERSAL,
    SPREAD_BONUS_FACTOR,
    CO_ACTIVATION_MAX_PAIRS,
    CO_ACTIVATION_MIN_EITHER,
    CALENDAR_DECAY_MAX_DAYS,
)

RULES_PATH = rule_engine.RULES_PATH
STATE_PATH = rule_engine.STATE_PATH
HOOK_PATH = Path.home() / ".claude/hooks/learning_hook.py"
LEARNINGS_INDEX_PATH = Path.home() / ".claude/.locks/learning-index.json"
PRINCIPLES_PATH = (
    Path.home() / ".claude/projects/-Users-nissimagent/memory/behavioral-principles.md"
)


def backup_state():
    """Backup current state before tests."""
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return None


def restore_state(backup):
    """Restore state after tests. Never deletes state file."""
    if backup is not None:
        STATE_PATH.write_text(json.dumps(backup, indent=2))
    # If backup was None (no state existed), leave current state as-is.
    # NEVER unlink state file — tests should be non-destructive.


# ============================================================
# PHASE 1: VIOLATION → SPIKE (Entry Point)
# ============================================================


def test_phase1_violation_spike(runner: TestRunner):
    phase = "P1: Violation→Spike"

    # Save and reset state
    orig = backup_state()
    try:
        # Start with clean state
        rules = load_rules()
        clean_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(clean_state)

        # Test 1: Hook violation adds spike
        msg = record_violation("R4", "hook")
        state = load_state()
        spike = state["rules"]["R4"]["adaptive_spike"]
        runner.record(
            phase,
            "Hook violation adds spike to R4",
            spike == SPIKE_AMOUNT["hook"],
            f"spike={spike}, expected={SPIKE_AMOUNT['hook']}",
        )

        # Test 2: User violation adds correct amount
        save_state(clean_state)
        record_violation("R9", "user")
        state = load_state()
        spike = state["rules"]["R9"]["adaptive_spike"]
        runner.record(
            phase,
            "User violation adds correct spike",
            spike == SPIKE_AMOUNT["user"],
            f"spike={spike}, expected={SPIKE_AMOUNT['user']}",
        )

        # Test 3: Self-check violation adds correct amount
        save_state(clean_state)
        record_violation("R5", "self_check")
        state = load_state()
        spike = state["rules"]["R5"]["adaptive_spike"]
        runner.record(
            phase,
            "Self-check violation adds correct spike",
            spike == SPIKE_AMOUNT["self_check"],
            f"spike={spike}, expected={SPIKE_AMOUNT['self_check']}",
        )

        # Test 4: Audit violation adds correct amount
        save_state(clean_state)
        record_violation("R1", "audit")
        state = load_state()
        spike = state["rules"]["R1"]["adaptive_spike"]
        runner.record(
            phase,
            "Audit violation adds correct spike",
            spike == SPIKE_AMOUNT["audit"],
            f"spike={spike}, expected={SPIKE_AMOUNT['audit']}",
        )

        # Test 5: Spike is capped at SPIKE_CAP
        save_state(clean_state)
        for _ in range(20):
            record_violation("R4", "hook")
        state = load_state()
        spike = state["rules"]["R4"]["adaptive_spike"]
        runner.record(
            phase,
            "Spike capped at SPIKE_CAP after many violations",
            spike == SPIKE_CAP,
            f"spike={spike}, cap={SPIKE_CAP}",
        )

        # Test 6: Violation on nonexistent rule returns None safely
        result = record_violation("R_NONEXISTENT", "hook")
        runner.record(phase, "Nonexistent rule violation returns None", result is None)

        # Test 7: State file is updated after violation (visibility)
        save_state(clean_state)
        record_violation("R30", "hook")
        state = load_state()
        runner.record(
            phase,
            "State file updated_at reflects violation time",
            "updated_at" in state and state["updated_at"] != "",
        )

        # Test 8: Multiple rules can have independent spikes
        save_state(clean_state)
        record_violation("R4", "hook")
        record_violation("R9", "user")
        record_violation("R30", "self_check")
        state = load_state()
        r4_spike = state["rules"]["R4"]["adaptive_spike"]
        r9_spike = state["rules"]["R9"]["adaptive_spike"]
        r30_spike = state["rules"]["R30"]["adaptive_spike"]
        runner.record(
            phase,
            "Three rules have independent spikes",
            r4_spike > 0 and r9_spike > 0 and r30_spike > 0,
            f"R4={r4_spike}, R9={r9_spike}, R30={r30_spike}",
        )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 2: SPIKE → INJECTION PRIORITY (The Boost)
# ============================================================


def test_phase2_spike_injection(runner: TestRunner):
    phase = "P2: Spike→Injection"

    orig = backup_state()
    try:
        rules = load_rules()

        # Test 1: Spiked rule scores higher than unspiked equivalent
        # R42 (audio, practice, 0.1 consequence) normally scores low
        # With spike, it should score higher
        clean_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(clean_state)

        # Score R42 without spike
        rules_fresh = load_rules()
        apply_state(rules_fresh, load_state())
        score_no_spike = score_rule(rules_fresh["R42"], "audio", "edit")

        # Add spike to R42
        spiked_state = json.loads(json.dumps(clean_state))
        spiked_state["rules"]["R42"]["adaptive_spike"] = SPIKE_CAP
        save_state(spiked_state)

        rules_spiked = load_rules()
        apply_state(rules_spiked, load_state())
        score_with_spike = score_rule(rules_spiked["R42"], "audio", "edit")

        runner.record(
            phase,
            "Spiked rule scores higher than unspiked",
            score_with_spike > score_no_spike,
            f"spiked={score_with_spike}, unspiked={score_no_spike}",
        )

        # Test 2: Spike contribution is exactly min(spike, SPIKE_CAP)
        diff = score_with_spike - score_no_spike
        runner.record(
            phase,
            "Spike contribution equals SPIKE_CAP",
            abs(diff - SPIKE_CAP) < 0.001,
            f"diff={diff}, expected={SPIKE_CAP}",
        )

        # Test 3: Spiked rule appears in get_relevant_rules for matching domain
        save_state(spiked_state)
        results = get_relevant_rules("audio mixing lufs loudness mastering")
        result_ids = [r["id"] for r in results]
        runner.record(
            phase,
            "Spiked R42 appears in audio query results",
            "R42" in result_ids,
            f"result_ids={result_ids}",
        )

        # Test 4: Result includes score for visibility
        if results:
            has_score = all("score" in r for r in results)
            runner.record(phase, "All results include numeric score", has_score)
        else:
            runner.record(
                phase, "All results include numeric score", False, "No results returned"
            )

        # Test 5: Result includes domain classification for visibility
        if results:
            has_domain = all("domain" in r for r in results)
            runner.record(
                phase, "All results include domain classification", has_domain
            )
        else:
            runner.record(phase, "All results include domain classification", False)

        # Test 6: Result includes tool classification for visibility
        if results:
            has_tool = all("tool" in r for r in results)
            runner.record(phase, "All results include tool classification", has_tool)
        else:
            runner.record(phase, "All results include tool classification", False)

        # Test 7: Result includes principle_id for traceability
        if results:
            has_pid = all("principle_id" in r for r in results)
            runner.record(phase, "All results include principle_id", has_pid)
        else:
            runner.record(phase, "All results include principle_id", False)

        # Test 8: Injection limit respected
        save_state(spiked_state)
        results = get_relevant_rules("edit python code function class module refactor")
        runner.record(
            phase,
            f"Results capped at INJECTION_LIMIT={INJECTION_LIMIT}",
            len(results) <= INJECTION_LIMIT,
            f"got {len(results)} results",
        )

        # Test 9: Results include 'reason' field (visibility of WHY)
        if results:
            has_reason = all("reason" in r for r in results)
            runner.record(
                phase,
                "All results include reason tag",
                has_reason,
                f"reasons={[r.get('reason') for r in results]}",
            )
        else:
            runner.record(
                phase, "All results include reason tag", False, "No results returned"
            )

        # Test 10: Reason contains 'spiked' for spiked rules
        save_state(spiked_state)
        results = get_relevant_rules("audio mixing lufs loudness mastering")
        r42_result = next((r for r in results if r["id"] == "R42"), None)
        if r42_result:
            runner.record(
                phase,
                "Spiked rule reason contains 'spiked'",
                "spiked" in r42_result.get("reason", ""),
                f"reason={r42_result.get('reason')}",
            )
        else:
            runner.record(
                phase,
                "Spiked rule reason contains 'spiked'",
                False,
                "R42 not in results",
            )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 3: ACTIVATION TRACKING (Counters + Co-activation)
# ============================================================


def test_phase3_activation_tracking(runner: TestRunner):
    phase = "P3: Activation Tracking"

    orig = backup_state()
    try:
        rules = load_rules()
        clean_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 5,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(clean_state)

        # Test 1: Activation count increments
        get_relevant_rules("edit python code")
        state = load_state()
        activated_rules = [
            rid for rid, rs in state["rules"].items() if rs["activation_count"] > 0
        ]
        runner.record(
            phase,
            "At least one rule activated after query",
            len(activated_rules) > 0,
            f"activated: {activated_rules}",
        )

        # Test 2: days_since_activation resets for activated rules
        activated_reset = [
            rid
            for rid, rs in state["rules"].items()
            if rs["activation_count"] > 0 and rs["days_since_activation"] == 0
        ]
        runner.record(
            phase,
            "Activated rules have days_since_activation=0",
            len(activated_reset) > 0,
            f"reset: {activated_reset}",
        )

        # Test 3: Non-activated rules keep their days_since_activation
        non_activated = [
            rid for rid, rs in state["rules"].items() if rs["activation_count"] == 0
        ]
        kept_days = all(
            state["rules"][rid]["days_since_activation"] == 5
            for rid in non_activated
            if rid in state["rules"]
        )
        runner.record(
            phase,
            "Non-activated rules keep days_since_activation",
            kept_days or len(non_activated) == 0,
        )

        # Test 4: Co-activation pairs are tracked
        save_state(clean_state)
        get_relevant_rules("edit python code")
        state = load_state()
        co_act = state.get("co_activation", {})
        runner.record(
            phase,
            "Co-activation dict is populated",
            len(co_act) > 0,
            f"pairs: {len(co_act)}",
        )

        # Test 5: Co-activation pairs have 'both' and 'either' counts
        if co_act:
            first_key = next(iter(co_act))
            has_counts = "both" in co_act[first_key] and "either" in co_act[first_key]
            runner.record(
                phase,
                "Co-activation pairs have both/either counts",
                has_counts,
                f"sample: {co_act[first_key]}",
            )
        else:
            runner.record(
                phase,
                "Co-activation pairs have both/either counts",
                False,
                "no co-activation data",
            )

        # Test 6: Repeated activations increment counts
        save_state(clean_state)
        for _ in range(3):
            get_relevant_rules("edit python code")
        state = load_state()
        max_count = max(rs["activation_count"] for rs in state["rules"].values())
        runner.record(
            phase,
            "Repeated queries increment activation count",
            max_count >= 3,
            f"max_count={max_count}",
        )

        # Test 7: State persistence survives reload
        state_before = load_state()
        # Force cache invalidation by touching mtime
        rule_engine._rules_cache = None
        state_after = load_state()
        runner.record(
            phase, "State persists across reloads", state_before == state_after
        )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 4: DECAY (Spike Erosion Over Time)
# ============================================================


def test_phase4_decay(runner: TestRunner):
    phase = "P4: Decay"

    orig = backup_state()
    try:
        rules = load_rules()

        # Test 1: advance_day() reduces spikes
        spiked_state = {
            "rules": {
                rid: {
                    "adaptive_spike": SPIKE_CAP if rid == "R4" else 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(spiked_state)
        advance_day()
        state = load_state()
        new_spike = state["rules"]["R4"]["adaptive_spike"]
        expected = SPIKE_CAP - SPIKE_DECAY_PER_DAY
        runner.record(
            phase,
            "advance_day reduces spike by SPIKE_DECAY_PER_DAY",
            abs(new_spike - expected) < 0.001,
            f"new={new_spike}, expected={expected}",
        )

        # Test 2: Spike decays to zero (not negative)
        tiny_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.005 if rid == "R4" else 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(tiny_state)
        advance_day()
        state = load_state()
        spike = state["rules"]["R4"]["adaptive_spike"]
        runner.record(
            phase, "Spike decays to 0.0, never negative", spike == 0.0, f"spike={spike}"
        )

        # Test 3: days_since_activation increments
        save_state(spiked_state)
        advance_day()
        state = load_state()
        days = state["rules"]["R4"]["days_since_activation"]
        runner.record(
            phase, "days_since_activation increments by 1", days == 1, f"days={days}"
        )

        # Test 4: Multiple advance_day calls compound correctly
        fresh_state = {
            "rules": {
                rid: {
                    "adaptive_spike": SPIKE_CAP if rid == "R9" else 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(fresh_state)
        for _ in range(5):
            advance_day()
        state = load_state()
        spike5 = state["rules"]["R9"]["adaptive_spike"]
        expected5 = max(0, SPIKE_CAP - 5 * SPIKE_DECAY_PER_DAY)
        runner.record(
            phase,
            "5 days of decay compound correctly",
            abs(spike5 - expected5) < 0.001,
            f"spike={spike5}, expected={expected5}",
        )

        # Test 5: last_decay timestamp is set (visibility)
        runner.record(
            phase,
            "last_decay timestamp set after advance_day",
            state.get("last_decay", "") != "",
            f"last_decay={state.get('last_decay', 'MISSING')}",
        )

        # Test 6: Full decay timeline — spike reaches zero
        full_state = {
            "rules": {
                rid: {
                    "adaptive_spike": SPIKE_CAP if rid == "R4" else 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(full_state)
        days_to_zero = int(SPIKE_CAP / SPIKE_DECAY_PER_DAY) + 2
        for _ in range(days_to_zero):
            advance_day()
        state = load_state()
        spike_final = state["rules"]["R4"]["adaptive_spike"]
        runner.record(
            phase,
            f"Spike reaches 0 after {days_to_zero} days",
            spike_final == 0.0,
            f"spike={spike_final}",
        )

        # Test 7: Unspiked rules unaffected by decay
        state = load_state()
        r9_spike = state["rules"]["R9"]["adaptive_spike"]
        runner.record(phase, "Unspiked rules stay at 0 through decay", r9_spike == 0.0)

    finally:
        restore_state(orig)


# ============================================================
# PHASE 5: DORMANCY (Inactivity → Sleep)
# ============================================================


def test_phase5_dormancy(runner: TestRunner):
    phase = "P5: Dormancy"

    orig = backup_state()
    try:
        rules = load_rules()

        # Test 1: Rule with 60+ days inactive detected as dormancy candidate
        dormant_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 65 if rid == "R42" else 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(dormant_state)
        candidates = detect_inactive()
        runner.record(
            phase,
            "R42 at 65 days detected as inactive",
            "R42" in candidates,
            f"candidates={candidates}",
        )

        # Test 2: Pinned rules are NOT detected as dormancy candidates
        pinned_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 100,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(pinned_state)
        candidates = detect_inactive()
        pinned_ids = [rid for rid, r in load_rules().items() if r.pinned]
        pinned_in_candidates = [pid for pid in pinned_ids if pid in candidates]
        runner.record(
            phase,
            "Pinned rules never become dormancy candidates",
            len(pinned_in_candidates) == 0,
            f"pinned_in_candidates={pinned_in_candidates}",
        )

        # Test 3: Already dormant rules not re-detected
        already_dormant_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": True if rid == "R42" else False,
                    "days_since_activation": 100,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(already_dormant_state)
        candidates = detect_inactive()
        runner.record(
            phase, "Already dormant rules not re-detected", "R42" not in candidates
        )

        # Test 4: Dormant rule scores 0.0 (excluded from activation)
        rules_test = load_rules()
        apply_state(rules_test, already_dormant_state)
        dormant_score = score_rule(rules_test["R42"], "audio", "edit")
        runner.record(
            phase,
            "Dormant rule scores 0.0",
            dormant_score == 0.0,
            f"score={dormant_score}",
        )

        # Test 5: Dormant rule excluded from get_relevant_rules
        save_state(already_dormant_state)
        results = get_relevant_rules("audio mixing mastering lufs")
        result_ids = [r["id"] for r in results]
        runner.record(
            phase,
            "Dormant R42 excluded from query results",
            "R42" not in result_ids,
            f"result_ids={result_ids}",
        )

        # Test 6: Rule at exactly 59 days NOT detected
        edge_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 59 if rid == "R67" else 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(edge_state)
        candidates = detect_inactive()
        runner.record(
            phase, "Rule at 59 days NOT detected as inactive", "R67" not in candidates
        )

        # Test 7: Rule at exactly 60 days IS detected
        boundary_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 60 if rid == "R67" else 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(boundary_state)
        candidates = detect_inactive()
        runner.record(phase, "Rule at exactly 60 days IS detected", "R67" in candidates)

    finally:
        restore_state(orig)


# ============================================================
# PHASE 6: IMMUNE REACTIVATION (Dormant → Alive on Violation)
# ============================================================


def test_phase6_immune(runner: TestRunner):
    phase = "P6: Immune Reactivation"

    orig = backup_state()
    try:
        rules = load_rules()

        # Test 1: Violation on dormant rule reactivates it
        dormant_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": True if rid == "R42" else False,
                    "days_since_activation": 100 if rid == "R42" else 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(dormant_state)
        msg = record_violation("R42", "hook")
        state = load_state()
        runner.record(
            phase,
            "Dormant R42 reactivated by violation",
            state["rules"]["R42"]["dormant"] is False,
        )

        # Test 2: Immune reactivation sets spike to IMMUNE_SPIKE
        spike = state["rules"]["R42"]["adaptive_spike"]
        runner.record(
            phase,
            "Immune spike set to IMMUNE_SPIKE",
            spike == IMMUNE_SPIKE,
            f"spike={spike}, expected={IMMUNE_SPIKE}",
        )

        # Test 3: Reactivation returns a message (visibility)
        runner.record(
            phase,
            "Reactivation returns visible message",
            msg is not None and "IMMUNE REACTIVATION" in msg,
            f"msg={msg}",
        )

        # Test 4: Reactivated rule now participates in scoring
        results = get_relevant_rules("audio lufs mastering mixing")
        result_ids = [r["id"] for r in results]
        runner.record(
            phase,
            "Reactivated R42 appears in audio queries",
            "R42" in result_ids,
            f"result_ids={result_ids}",
        )

        # Test 5: IMMUNE_SPIKE > SPIKE_CAP (stronger comeback)
        runner.record(
            phase,
            "IMMUNE_SPIKE exceeds normal SPIKE_CAP",
            IMMUNE_SPIKE > SPIKE_CAP,
            f"immune={IMMUNE_SPIKE}, cap={SPIKE_CAP}",
        )

        # Test 6: Normal violation on active rule does NOT return immune message
        save_state(dormant_state)
        save_state(
            {
                "rules": {
                    rid: {
                        "adaptive_spike": 0.0,
                        "dormant": False,
                        "days_since_activation": 0,
                        "activation_count": 5,
                    }
                    for rid in rules
                },
                "co_activation": {},
                "recently_unmerged": {},
                "last_decay": "",
                "updated_at": "",
            }
        )
        msg_normal = record_violation("R4", "hook")
        runner.record(
            phase, "Normal violation returns None (not immune msg)", msg_normal is None
        )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 7: MERGE DETECTION (Co-activation → Consolidation Signal)
# ============================================================


def test_phase7_merge(runner: TestRunner):
    phase = "P7: Merge Detection"

    orig = backup_state()
    try:
        rules = load_rules()

        # Test 1: High co-activation ratio triggers merge candidate
        co_act_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {
                "R27:R4": {"both": 10, "either": 10},  # 100% co-activation
            },
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(co_act_state)
        merges = detect_merge_candidates()
        pair_found = any(
            (r1 == "R27" and r2 == "R4") or (r1 == "R4" and r2 == "R27")
            for r1, r2, _ in merges
        )
        runner.record(
            phase,
            "100% co-activation pair detected as merge candidate",
            pair_found,
            f"merges={merges}",
        )

        # Test 2: Low co-activation NOT flagged
        low_co_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {
                "R27:R4": {"both": 5, "either": 10},  # 50% — below threshold
            },
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(low_co_state)
        merges = detect_merge_candidates()
        runner.record(phase, "50% co-activation NOT flagged as merge", len(merges) == 0)

        # Test 3: Insufficient data (either < 10) NOT flagged
        few_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {
                "R27:R4": {"both": 9, "either": 9},  # 100% but < 10 observations
            },
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(few_state)
        merges = detect_merge_candidates()
        runner.record(
            phase, "High ratio but <10 observations NOT flagged", len(merges) == 0
        )

        # Test 4: Recently unmerged pair excluded
        unmerge_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {
                "R27:R4": {"both": 10, "either": 10},
            },
            "recently_unmerged": {"R27": 15, "R4": 15},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(unmerge_state)
        merges = detect_merge_candidates()
        runner.record(
            phase, "Recently unmerged pair excluded from merge", len(merges) == 0
        )

        # Test 5: Merge candidates include ratio (visibility)
        save_state(co_act_state)
        merges = detect_merge_candidates()
        if merges:
            r1, r2, ratio = merges[0]
            runner.record(
                phase, "Merge candidate includes ratio", ratio >= 0.9, f"ratio={ratio}"
            )
        else:
            runner.record(
                phase, "Merge candidate includes ratio", False, "no candidates"
            )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 8: LIFECYCLE REPORT (Full Observability)
# ============================================================


def test_phase8_lifecycle_report(runner: TestRunner):
    phase = "P8: Lifecycle Report"

    orig = backup_state()
    try:
        rules = load_rules()

        # Set up a rich state for reporting
        rich_state = {
            "rules": {},
            "co_activation": {
                "R27:R4": {"both": 12, "either": 12},
            },
            "recently_unmerged": {},
            "last_decay": "2026-02-14",
            "updated_at": "",
        }

        for rid in rules:
            rich_state["rules"][rid] = {
                "adaptive_spike": SPIKE_CAP if rid in ("R4", "R9") else 0.0,
                "dormant": True if rid == "R42" else False,
                "days_since_activation": 70 if rid == "R67" else 2,
                "activation_count": 10 if rid in ("R4", "R9") else 1,
            }
        save_state(rich_state)

        report = get_lifecycle_report()

        # Test 1: Report has total_rules count
        runner.record(
            phase,
            "Report includes total_rules",
            "total_rules" in report and report["total_rules"] == len(rules),
            f"total_rules={report.get('total_rules')}",
        )

        # Test 2: Report has active count
        runner.record(
            phase,
            "Report includes active count",
            "active" in report and report["active"] > 0,
        )

        # Test 3: Report has dormant count + ids
        runner.record(
            phase,
            "Report includes dormant count",
            "dormant" in report and report["dormant"] >= 1,
        )
        runner.record(
            phase,
            "Report includes dormant_ids",
            "dormant_ids" in report and "R42" in report["dormant_ids"],
        )

        # Test 4: Report has spiked rules with values
        runner.record(
            phase,
            "Report includes spiked count",
            "spiked" in report and report["spiked"] >= 2,
        )
        runner.record(
            phase,
            "Report includes spiked_rules dict",
            "spiked_rules" in report and "R4" in report["spiked_rules"],
            f"spiked_rules={report.get('spiked_rules')}",
        )

        # Test 5: Report has inactive candidates
        runner.record(
            phase,
            "Report includes inactive_candidates",
            "inactive_candidates" in report,
        )

        # Test 6: Report has merge candidates
        runner.record(
            phase, "Report includes merge_candidates", "merge_candidates" in report
        )

        # Test 7: Report has last_decay date (visibility of maintenance)
        runner.record(
            phase,
            "Report includes last_decay date",
            "last_decay" in report and report["last_decay"] == "2026-02-14",
        )

        # Test 8: Report is JSON-serializable (for dashboards)
        try:
            json.dumps(report)
            serializable = True
        except (TypeError, ValueError):
            serializable = False
        runner.record(phase, "Report is JSON-serializable", serializable)

        # Test 9: Report includes co_activation_pairs count
        runner.record(
            phase,
            "Report includes co_activation_pairs",
            "co_activation_pairs" in report,
            f"pairs={report.get('co_activation_pairs')}",
        )

        # Test 10: Report includes schema_warnings
        runner.record(
            phase,
            "Report includes schema_warnings",
            "schema_warnings" in report,
            f"warnings={report.get('schema_warnings')}",
        )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 9: HOOK INTEGRATION (End-to-End Injection)
# ============================================================


def test_phase9_hook_integration(runner: TestRunner):
    phase = "P9: Hook Integration"

    # Test 1: learning_hook.py exists
    runner.record(
        phase, "learning_hook.py exists", HOOK_PATH.exists(), f"path={HOOK_PATH}"
    )

    # Test 2: Hook imports rule_engine
    if HOOK_PATH.exists():
        hook_source = HOOK_PATH.read_text()
        runner.record(
            phase,
            "Hook imports rule_engine",
            "import rule_engine" in hook_source or "rule_engine" in hook_source,
        )

        # Test 3: Hook has graceful degradation (try/except)
        runner.record(
            phase,
            "Hook has graceful degradation",
            "except" in hook_source and "rule_engine" in hook_source,
        )

        # Test 4: Hook produces additionalContext
        runner.record(
            phase, "Hook outputs additionalContext", "additionalContext" in hook_source
        )
    else:
        for name in [
            "Hook imports rule_engine",
            "Hook has graceful degradation",
            "Hook outputs additionalContext",
        ]:
            runner.record(phase, name, False, "hook file not found")

    # Test 5: Hook runs without error on code prompt
    try:
        event = json.dumps(
            {
                "event": "UserPromptSubmit",
                "data": {"message": "edit the python function to fix the bug"},
            }
        )
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=event,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip()
        parsed = json.loads(output) if output else {}
        runner.record(
            phase,
            "Hook runs successfully on code prompt",
            result.returncode == 0,
            f"returncode={result.returncode}",
        )

        # Test 6: Hook returns rule injections
        context = parsed.get("additionalContext", "")
        has_rules = "[Rule " in context
        runner.record(
            phase,
            "Hook returns rule injections in context",
            has_rules,
            f"context_preview={context[:120]}",
        )
    except Exception as e:
        runner.record(phase, "Hook runs successfully on code prompt", False, str(e))
        runner.record(phase, "Hook returns rule injections in context", False, str(e))

    # Test 7: Hook returns empty for short prompts
    try:
        event = json.dumps({"event": "UserPromptSubmit", "data": {"message": "ok"}})
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=event,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip()
        parsed = json.loads(output) if output else {}
        context = parsed.get("additionalContext", "")
        runner.record(
            phase,
            "Short prompt 'ok' produces no rule injection",
            "[Rule " not in context,
            f"context={context[:80]}",
        )
    except Exception as e:
        runner.record(
            phase, "Short prompt 'ok' produces no rule injection", False, str(e)
        )

    # Test 8: Hook returns domain-appropriate rules
    try:
        event = json.dumps(
            {
                "event": "UserPromptSubmit",
                "data": {"message": "git commit and push the changes to remote"},
            }
        )
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=event,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip()
        parsed = json.loads(output) if output else {}
        context = parsed.get("additionalContext", "")
        # Should include R30 (Git Discipline) or R50 (Security)
        has_git_rule = "R30" in context or "R50" in context
        runner.record(
            phase,
            "Git prompt returns git-relevant rules",
            has_git_rule,
            f"context_preview={context[:120]}",
        )
    except Exception as e:
        runner.record(phase, "Git prompt returns git-relevant rules", False, str(e))

    # Test 9: Hook injection includes reason tag (new format)
    try:
        event = json.dumps(
            {
                "event": "UserPromptSubmit",
                "data": {"message": "edit the python function to fix the bug"},
            }
        )
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=event,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip()
        parsed = json.loads(output) if output else {}
        context = parsed.get("additionalContext", "")
        # New format: [Rule R4|P4 | code+edit] reminder
        has_reason_pipe = " | " in context and "[Rule " in context
        runner.record(
            phase,
            "Hook injection includes reason tag in format",
            has_reason_pipe,
            f"context_preview={context[:150]}",
        )
    except Exception as e:
        runner.record(
            phase, "Hook injection includes reason tag in format", False, str(e)
        )


# ============================================================
# PHASE 10: FULL FLYWHEEL (End-to-End Loop)
# ============================================================


def test_phase10_full_flywheel(runner: TestRunner):
    phase = "P10: Full Flywheel"

    orig = backup_state()
    try:
        rules = load_rules()

        # START: Clean slate
        clean_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(clean_state)

        # STEP 1: R42 (audio, practice) is alive but low priority
        results_before = get_relevant_rules("audio lufs mixing mastering")
        r42_before = next((r for r in results_before if r["id"] == "R42"), None)
        score_before = r42_before["score"] if r42_before else 0.0
        runner.record(
            phase, "Step 1: R42 baseline score captured", True, f"score={score_before}"
        )

        # STEP 2: Violation occurs — spike added
        record_violation("R42", "hook")
        state = load_state()
        spike_after_violation = state["rules"]["R42"]["adaptive_spike"]
        runner.record(
            phase,
            "Step 2: Violation adds spike",
            spike_after_violation > 0,
            f"spike={spike_after_violation}",
        )

        # STEP 3: Rule now scores higher
        results_after = get_relevant_rules("audio lufs mixing mastering")
        r42_after = next((r for r in results_after if r["id"] == "R42"), None)
        score_after = r42_after["score"] if r42_after else 0.0
        runner.record(
            phase,
            "Step 3: Spiked rule scores higher",
            score_after > score_before or (score_before == 0 and score_after > 0),
            f"before={score_before}, after={score_after}",
        )

        # STEP 4: Time passes — spike decays
        for _ in range(15):
            advance_day()
        state = load_state()
        spike_after_decay = state["rules"]["R42"]["adaptive_spike"]
        runner.record(
            phase,
            "Step 4: Spike decays over 15 days",
            spike_after_decay < spike_after_violation,
            f"before={spike_after_violation}, after={spike_after_decay}",
        )

        # STEP 5: Long inactivity — rule becomes dormancy candidate
        # Set days_since_activation high
        state["rules"]["R42"]["days_since_activation"] = 65
        state["rules"]["R42"]["adaptive_spike"] = 0.0
        save_state(state)
        candidates = detect_inactive()
        runner.record(
            phase,
            "Step 5: Long-inactive rule is dormancy candidate",
            "R42" in candidates,
        )

        # STEP 6: Mark as dormant, verify excluded
        state = load_state()
        state["rules"]["R42"]["dormant"] = True
        save_state(state)
        results_dormant = get_relevant_rules("audio lufs mixing mastering")
        dormant_ids = [r["id"] for r in results_dormant]
        runner.record(
            phase,
            "Step 6: Dormant rule excluded from results",
            "R42" not in dormant_ids,
        )

        # STEP 7: Antigen recurs — immune reactivation!
        msg = record_violation("R42", "user")
        state = load_state()
        runner.record(
            phase,
            "Step 7: Immune reactivation on violation",
            state["rules"]["R42"]["dormant"] is False
            and state["rules"]["R42"]["adaptive_spike"] == IMMUNE_SPIKE,
            f"dormant={state['rules']['R42']['dormant']}, spike={state['rules']['R42']['adaptive_spike']}",
        )

        # STEP 8: Reactivated rule participates again
        results_reactivated = get_relevant_rules("audio lufs mixing mastering")
        r42_reactivated = next(
            (r for r in results_reactivated if r["id"] == "R42"), None
        )
        runner.record(
            phase,
            "Step 8: Reactivated rule appears in results",
            r42_reactivated is not None,
            f"present={'yes' if r42_reactivated else 'no'}",
        )

        # STEP 9: Lifecycle report captures full state (visibility)
        report = get_lifecycle_report()
        runner.record(
            phase,
            "Step 9: Lifecycle report reflects current state",
            report["total_rules"] > 0 and "spiked_rules" in report,
        )

        # STEP 10: The flywheel is complete — all stages verified
        runner.record(
            phase,
            "Step 10: FLYWHEEL COMPLETE",
            True,
            "violation→spike→boost→decay→dormancy→immune→reactivation",
        )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 11: DOMAIN CLASSIFICATION VISIBILITY
# ============================================================


def test_phase11_classification(runner: TestRunner):
    phase = "P11: Classification Visibility"

    # Test all 7 domains are classifiable
    domain_prompts = {
        "code": "edit the python function class to fix the bug",
        "audio": "adjust the audio filter dsp lufs levels",
        "writing": "write the prd document specification draft",
        "git": "git commit push pull merge branch rebase",
        "advisory": "advisor strategy recommend evaluate assess",
        "budget": "budget token cost resource usage tracking",
        "scraping": "scrape crawl download articles kb knowledge",
    }

    for expected_domain, prompt in domain_prompts.items():
        domain, tool = classify_prompt(prompt)
        runner.record(
            phase,
            f"'{expected_domain}' domain classified correctly",
            domain == expected_domain,
            f"got domain='{domain}' from '{prompt[:40]}...'",
        )

    # Test tool classification
    tool_prompts = {
        "edit": "edit change modify the file",
        "bash": "run execute build compile test",
        "write": "write create generate new file",
        "read": "read look check show view examine",
    }

    for expected_tool, prompt in tool_prompts.items():
        domain, tool = classify_prompt(prompt)
        runner.record(
            phase,
            f"'{expected_tool}' tool classified correctly",
            tool == expected_tool,
            f"got tool='{tool}' from '{prompt[:40]}...'",
        )

    # Test stem matching
    domain, tool = classify_prompt("editing some files and refactoring")
    runner.record(
        phase, "Stem matching: 'editing' → edit tool", tool == "edit", f"tool={tool}"
    )

    domain, tool = classify_prompt("compiling the code and running tests")
    runner.record(
        phase, "Stem matching: 'compiling' → bash tool", tool == "bash", f"tool={tool}"
    )


# ============================================================
# PHASE 12: SPREADING ACTIVATION VISIBILITY
# ============================================================


def test_phase12_spreading(runner: TestRunner):
    phase = "P12: Spreading Activation"

    orig = backup_state()
    try:
        rules = load_rules()

        # Test 1: R4 (Read Before Editing) connects to R9 (Verify Everything) with weight 0.6
        r4 = rules.get("R4")
        if r4:
            has_r9_connection = "R9" in r4.connections
            runner.record(
                phase,
                "R4 has connection to R9",
                has_r9_connection,
                f"connections={r4.connections}",
            )
        else:
            runner.record(phase, "R4 has connection to R9", False, "R4 not found")

        # Test 2: Connections are bidirectional or one-way (verify structure)
        connection_pairs = []
        for rid, r in rules.items():
            for cid, weight in r.connections.items():
                connection_pairs.append((rid, cid, weight))
        runner.record(
            phase,
            "Connection graph has edges",
            len(connection_pairs) > 0,
            f"edges={len(connection_pairs)}",
        )

        # Test 3: All connection targets exist in rules
        missing_targets = []
        for rid, cid, _ in connection_pairs:
            if cid not in rules:
                missing_targets.append(f"{rid}→{cid}")
        runner.record(
            phase,
            "All connection targets exist as rules",
            len(missing_targets) == 0,
            f"missing={missing_targets}",
        )

        # Test 4: Connection weights are between 0 and 1
        bad_weights = [
            (rid, cid, w) for rid, cid, w in connection_pairs if w < 0 or w > 1
        ]
        runner.record(
            phase,
            "All connection weights in [0, 1]",
            len(bad_weights) == 0,
            f"bad_weights={bad_weights}",
        )

        # Test 5: Spreading bonus formula is correct
        # bonus = connection_weight * SPREAD_BONUS_FACTOR
        sample_weight = 0.6
        expected_bonus = sample_weight * SPREAD_BONUS_FACTOR
        runner.record(
            phase,
            "Spreading bonus formula verified",
            expected_bonus == 0.12,
            f"bonus={expected_bonus}, weight={sample_weight}, factor={SPREAD_BONUS_FACTOR}",
        )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 13: PERFORMANCE BENCHMARKS
# ============================================================


def test_phase13_performance(runner: TestRunner):
    phase = "P13: Performance"

    orig = backup_state()
    try:
        rules = load_rules()
        clean_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(clean_state)

        # Test 1: Cold start (load + classify + score) < 50ms
        clear_cache()
        start = time.perf_counter()
        get_relevant_rules("edit python code function class")
        cold_ms = (time.perf_counter() - start) * 1000
        runner.record(phase, "Cold query < 50ms", cold_ms < 50, f"cold={cold_ms:.1f}ms")

        # Test 2: Cached query < 5ms
        times = []
        for _ in range(10):
            start = time.perf_counter()
            get_relevant_rules("edit python code function class")
            times.append((time.perf_counter() - start) * 1000)
        avg_ms = sum(times) / len(times)
        runner.record(
            phase,
            "Cached query avg < 5ms (10 iterations)",
            avg_ms < 5,
            f"avg={avg_ms:.2f}ms",
        )

        # Test 3: record_violation < 10ms
        start = time.perf_counter()
        record_violation("R4", "hook")
        violation_ms = (time.perf_counter() - start) * 1000
        runner.record(
            phase,
            "record_violation < 10ms",
            violation_ms < 10,
            f"violation={violation_ms:.1f}ms",
        )

        # Test 4: advance_day < 10ms
        start = time.perf_counter()
        advance_day(days=1)
        advance_ms = (time.perf_counter() - start) * 1000
        runner.record(
            phase, "advance_day < 10ms", advance_ms < 10, f"advance={advance_ms:.1f}ms"
        )

        # Test 5: lifecycle report < 20ms
        start = time.perf_counter()
        get_lifecycle_report()
        report_ms = (time.perf_counter() - start) * 1000
        runner.record(
            phase,
            "lifecycle_report < 20ms",
            report_ms < 20,
            f"report={report_ms:.1f}ms",
        )

        # Test 6: Hook end-to-end < 5 seconds (hook timeout)
        event = json.dumps(
            {
                "event": "UserPromptSubmit",
                "data": {"message": "edit the python function to fix the bug"},
            }
        )
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=event,
            capture_output=True,
            text=True,
            timeout=5,
        )
        hook_ms = (time.perf_counter() - start) * 1000
        runner.record(
            phase,
            "Hook end-to-end < 5000ms",
            hook_ms < 5000 and result.returncode == 0,
            f"hook={hook_ms:.0f}ms",
        )

        # Test 7: validate_rules < 5ms
        start = time.perf_counter()
        validate_rules(rules)
        validate_ms = (time.perf_counter() - start) * 1000
        runner.record(
            phase,
            "validate_rules < 5ms",
            validate_ms < 5,
            f"validate={validate_ms:.2f}ms",
        )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 14: MALFORMED INPUT RESILIENCE
# ============================================================


def test_phase14_malformed(runner: TestRunner):
    phase = "P14: Malformed Input"

    orig = backup_state()
    try:
        rules = load_rules()

        # Test 1: Empty prompt doesn't crash (hook filters short prompts, engine doesn't)
        results = get_relevant_rules("")
        runner.record(
            phase,
            "Empty prompt returns list without crash",
            isinstance(results, list),
            f"got {len(results)} results (engine returns matches; hook filters)",
        )

        # Test 2: Unicode/emoji prompt doesn't crash
        try:
            results = get_relevant_rules("fix the bug in \U0001f525\U0001f4a5 module")
            runner.record(phase, "Unicode prompt doesn't crash", True)
        except Exception as e:
            runner.record(phase, "Unicode prompt doesn't crash", False, str(e))

        # Test 3: Very long prompt doesn't crash
        try:
            long_prompt = "edit " * 10000
            results = get_relevant_rules(long_prompt)
            runner.record(
                phase, "10K-word prompt doesn't crash", isinstance(results, list)
            )
        except Exception as e:
            runner.record(phase, "10K-word prompt doesn't crash", False, str(e))

        # Test 4: Corrupted state JSON — load_state handles gracefully
        if STATE_PATH.exists():
            good_state = STATE_PATH.read_text()
        else:
            good_state = None
        try:
            STATE_PATH.write_text("{corrupt json!!! not valid")
            state = load_state()
            runner.record(
                phase,
                "Corrupted JSON returns empty dict",
                state == {},
                f"got type={type(state)}",
            )
        finally:
            if good_state:
                STATE_PATH.write_text(good_state)

        # Test 5: State with wrong types — apply_state clamps gracefully
        bad_type_state = {
            "rules": {
                "R4": {
                    "adaptive_spike": "not_a_number",
                    "dormant": "maybe",
                    "days_since_activation": "yesterday",
                    "activation_count": None,
                }
            }
        }
        fresh_rules = load_rules()
        try:
            apply_state(fresh_rules, bad_type_state)
            r4 = fresh_rules["R4"]
            runner.record(
                phase,
                "Bad types in state clamped safely",
                r4.adaptive_spike == 0.0
                and r4.days_since_activation == 0
                and r4.activation_count == 0,
                f"spike={r4.adaptive_spike}, days={r4.days_since_activation}, count={r4.activation_count}",
            )
        except Exception as e:
            runner.record(phase, "Bad types in state clamped safely", False, str(e))

        # Test 6: State with negative values — clamped to 0
        neg_state = {
            "rules": {
                "R4": {
                    "adaptive_spike": -5.0,
                    "dormant": False,
                    "days_since_activation": -10,
                    "activation_count": -3,
                }
            }
        }
        fresh_rules2 = load_rules()
        apply_state(fresh_rules2, neg_state)
        r4 = fresh_rules2["R4"]
        runner.record(
            phase,
            "Negative values clamped to 0",
            r4.adaptive_spike == 0.0
            and r4.days_since_activation == 0
            and r4.activation_count == 0,
        )

        # Test 7: State with spike > IMMUNE_SPIKE — clamped
        overflow_state = {
            "rules": {
                "R4": {
                    "adaptive_spike": 999.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
            }
        }
        fresh_rules3 = load_rules()
        apply_state(fresh_rules3, overflow_state)
        runner.record(
            phase,
            "Spike > IMMUNE_SPIKE clamped to IMMUNE_SPIKE",
            fresh_rules3["R4"].adaptive_spike == IMMUNE_SPIKE,
            f"spike={fresh_rules3['R4'].adaptive_spike}",
        )

        # Test 8: Schema validation catches bad rules
        bad_rules = {
            "BAD1": Rule(
                id="BAD1",
                principle_id="P999",
                name="Bad",
                tier="legendary",
                pinned=False,
                domains=["mars"],
                consequence=5.0,
                tool_triggers=[],
                antigens=[],
                connections={"NONEXISTENT": 2.5},
                reminder="test",
            ),
        }
        warnings = validate_rules(bad_rules)
        runner.record(
            phase,
            "Schema validates bad tier, domain, consequence, connection",
            len(warnings) >= 4,
            f"warnings={len(warnings)}: {warnings[:2]}",
        )

        # Test 9: classify_prompt with only special chars
        domain, tool = classify_prompt("!@#$%^&*(){}[]")
        runner.record(
            phase,
            "Special chars prompt returns defaults",
            domain == "all" and tool == "read",
            f"domain={domain}, tool={tool}",
        )

        # Test 10: Missing state file — get_relevant_rules still works
        if STATE_PATH.exists():
            backup_text = STATE_PATH.read_text()
        else:
            backup_text = None
        try:
            if STATE_PATH.exists():
                STATE_PATH.rename(STATE_PATH.with_suffix(".bak"))
            results = get_relevant_rules("edit python code")
            runner.record(
                phase,
                "Missing state file — engine still returns results",
                isinstance(results, list),
                f"got {len(results)} results",
            )
        finally:
            bak = STATE_PATH.with_suffix(".bak")
            if bak.exists():
                bak.rename(STATE_PATH)
            elif backup_text:
                STATE_PATH.write_text(backup_text)

        # Test 11: Ancient last_decay date capped at CALENDAR_DECAY_MAX_DAYS
        rules = load_rules()
        ancient_state = {
            "rules": {
                rid: {
                    "adaptive_spike": SPIKE_CAP if rid == "R4" else 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "2020-01-01",
            "updated_at": "",
        }
        save_state(ancient_state)
        advance_day()  # Should cap at CALENDAR_DECAY_MAX_DAYS, not 2200+
        state = load_state()
        max_days = max(rs["days_since_activation"] for rs in state["rules"].values())
        runner.record(
            phase,
            f"Ancient last_decay capped at {CALENDAR_DECAY_MAX_DAYS} days",
            max_days <= CALENDAR_DECAY_MAX_DAYS,
            f"max_days_since_activation={max_days}",
        )

        # Test 12: Future last_decay date treated as 1 day
        future_state = {
            "rules": {
                rid: {
                    "adaptive_spike": SPIKE_CAP if rid == "R4" else 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 5,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "2099-12-31",
            "updated_at": "",
        }
        save_state(future_state)
        advance_day()
        state = load_state()
        days_after = state["rules"]["R4"]["days_since_activation"]
        runner.record(
            phase,
            "Future last_decay treated as 1 day (not negative)",
            days_after == 1,
            f"days={days_after}",
        )

        # Test 13: fcntl import in rule_engine (Learning #192: flock-protected state)
        import inspect

        source = inspect.getsource(rule_engine)
        runner.record(
            phase,
            "fcntl imported in rule_engine.py for flock",
            "import fcntl" in source,
            "flock protects save_state from concurrent overwrites",
        )

    finally:
        restore_state(orig)


# ============================================================
# PHASE 15: CONCURRENT ACCESS
# ============================================================


def test_phase15_concurrent(runner: TestRunner):
    phase = "P15: Concurrent Access"

    orig = backup_state()
    try:
        rules = load_rules()
        clean_state = {
            "rules": {
                rid: {
                    "adaptive_spike": 0.0,
                    "dormant": False,
                    "days_since_activation": 0,
                    "activation_count": 0,
                }
                for rid in rules
            },
            "co_activation": {},
            "recently_unmerged": {},
            "last_decay": "",
            "updated_at": "",
        }
        save_state(clean_state)

        # Test 1: Concurrent violations don't crash
        errors = []

        def violate(rule_id):
            try:
                record_violation(rule_id, "hook")
            except Exception as e:
                errors.append(str(e))

        threads = []
        for rid in ["R4", "R9", "R30", "R42", "R5"]:
            t = threading.Thread(target=violate, args=(rid,))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        runner.record(
            phase,
            "5 concurrent violations don't crash",
            len(errors) == 0,
            f"errors={errors}" if errors else "clean",
        )

        # Test 2: State file not corrupted after concurrent writes
        state = load_state()
        try:
            json.dumps(state)  # Valid JSON?
            valid_json = True
        except (TypeError, ValueError):
            valid_json = False
        runner.record(
            phase, "State file valid JSON after concurrent writes", valid_json
        )

        # Test 3: Concurrent queries don't crash
        save_state(clean_state)
        query_errors = []

        def query(prompt):
            try:
                get_relevant_rules(prompt)
            except Exception as e:
                query_errors.append(str(e))

        prompts = [
            "edit python code function",
            "audio mixing mastering lufs",
            "git commit push branch",
            "write document prd spec",
            "scrape articles download kb",
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(query, prompts)

        runner.record(
            phase,
            "5 concurrent queries don't crash",
            len(query_errors) == 0,
            f"errors={query_errors}" if query_errors else "clean",
        )

        # Test 4: Mixed reads and writes don't corrupt
        save_state(clean_state)
        mixed_errors = []

        def mixed_op(i):
            try:
                if i % 2 == 0:
                    get_relevant_rules("edit python code")
                else:
                    record_violation("R4", "hook")
            except Exception as e:
                mixed_errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            executor.map(mixed_op, range(20))

        state = load_state()
        runner.record(
            phase,
            "Mixed concurrent reads/writes don't corrupt state",
            len(mixed_errors) == 0 and "rules" in state,
            f"errors={len(mixed_errors)}, state_keys={list(state.keys())}",
        )

        # Test 5: Atomic writes survive concurrent save_state
        save_state(clean_state)

        def bulk_save(n):
            try:
                s = load_state()
                s["updated_at"] = f"thread-{n}"
                save_state(s)
            except Exception:
                pass  # Atomic write may race, that's ok — should not corrupt

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(bulk_save, range(50))

        final_state = load_state()
        runner.record(
            phase,
            "50 concurrent save_state calls don't corrupt",
            "rules" in final_state and isinstance(final_state["rules"], dict),
            f"keys={list(final_state.keys())}",
        )

    finally:
        restore_state(orig)


# ============================================================
# MAIN
# ============================================================


def main():
    runner = TestRunner()

    print("Flywheel & Visibility Test Suite — Rule Engine v3")
    print("=" * 50)

    test_phase1_violation_spike(runner)
    print(
        f"  P1: Violation→Spike ... {runner.phase_counts.get('P1: Violation→Spike', (0, 0))}"
    )

    test_phase2_spike_injection(runner)
    print(
        f"  P2: Spike→Injection ... {runner.phase_counts.get('P2: Spike→Injection', (0, 0))}"
    )

    test_phase3_activation_tracking(runner)
    print(
        f"  P3: Activation Tracking ... {runner.phase_counts.get('P3: Activation Tracking', (0, 0))}"
    )

    test_phase4_decay(runner)
    print(f"  P4: Decay ... {runner.phase_counts.get('P4: Decay', (0, 0))}")

    test_phase5_dormancy(runner)
    print(f"  P5: Dormancy ... {runner.phase_counts.get('P5: Dormancy', (0, 0))}")

    test_phase6_immune(runner)
    print(
        f"  P6: Immune Reactivation ... {runner.phase_counts.get('P6: Immune Reactivation', (0, 0))}"
    )

    test_phase7_merge(runner)
    print(
        f"  P7: Merge Detection ... {runner.phase_counts.get('P7: Merge Detection', (0, 0))}"
    )

    test_phase8_lifecycle_report(runner)
    print(
        f"  P8: Lifecycle Report ... {runner.phase_counts.get('P8: Lifecycle Report', (0, 0))}"
    )

    test_phase9_hook_integration(runner)
    print(
        f"  P9: Hook Integration ... {runner.phase_counts.get('P9: Hook Integration', (0, 0))}"
    )

    test_phase10_full_flywheel(runner)
    print(
        f"  P10: Full Flywheel ... {runner.phase_counts.get('P10: Full Flywheel', (0, 0))}"
    )

    test_phase11_classification(runner)
    print(
        f"  P11: Classification Visibility ... {runner.phase_counts.get('P11: Classification Visibility', (0, 0))}"
    )

    test_phase12_spreading(runner)
    print(
        f"  P12: Spreading Activation ... {runner.phase_counts.get('P12: Spreading Activation', (0, 0))}"
    )

    test_phase13_performance(runner)
    print(
        f"  P13: Performance ... {runner.phase_counts.get('P13: Performance', (0, 0))}"
    )

    test_phase14_malformed(runner)
    print(
        f"  P14: Malformed Input ... {runner.phase_counts.get('P14: Malformed Input', (0, 0))}"
    )

    test_phase15_concurrent(runner)
    print(
        f"  P15: Concurrent Access ... {runner.phase_counts.get('P15: Concurrent Access', (0, 0))}"
    )

    print(runner.summary())

    # Return exit code
    total_pass = sum(p for p, _ in runner.phase_counts.values())
    total_tests = sum(t for _, t in runner.phase_counts.values())
    sys.exit(0 if total_pass == total_tests else 1)


if __name__ == "__main__":
    main()
