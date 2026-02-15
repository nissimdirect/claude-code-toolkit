#!/usr/bin/env python3
"""Adaptive Rule Engine v3 — Production Implementation

Loads scored rules from rules.yaml, classifies prompts by domain/tool,
returns the top relevant behavioral principle reminders.

State (spikes, activation counts, dormancy) persists in rule-engine-state.json.
Lifecycle events (decay, dormancy, merge detection) run via session-close.

Must complete scoring in <100ms (called from learning_hook.py on every prompt).
"""

import datetime
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# ============================================================
# PATHS
# ============================================================

RULES_PATH = Path(__file__).parent / "rules.yaml"
STATE_PATH = Path.home() / ".claude/.locks/rule-engine-state.json"

# ============================================================
# CONSTANTS (must match rule_engine_sim.py exactly)
# ============================================================

THRESHOLD = 0.5
BUDGET = 5
INJECTION_LIMIT = 3          # Max principles to inject per prompt
DOMAIN_SCORE_EXPLICIT = 0.4
DOMAIN_SCORE_UNIVERSAL = 0.3
SPIKE_CAP = 0.15
IMMUNE_SPIKE = 0.20
SPIKE_DECAY_PER_DAY = 0.010
INACTIVE_THRESHOLD_DAYS = 60
UNMERGE_COOLDOWN_DAYS = 30
CO_ACTIVATION_MERGE_THRESHOLD = 0.90
SPREAD_BONUS_FACTOR = 0.2
CO_ACTIVATION_MAX_PAIRS = 500
CO_ACTIVATION_MIN_EITHER = 5   # Prune pairs below this in advance_day
CALENDAR_DECAY_MAX_DAYS = 365  # Cap calendar-based decay to prevent mass dormancy from stale dates

VALID_TIERS = {"value", "principle", "practice"}
VALID_DOMAINS = {"code", "audio", "writing", "git", "advisory", "budget", "scraping", "all"}
CONSEQUENCE_MIN = 0.1
CONSEQUENCE_MAX = 0.3

SPIKE_AMOUNT = {
    "hook": 0.15,
    "self_check": 0.08,
    "user": 0.15,
    "audit": 0.06,
}

# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class Rule:
    id: str
    principle_id: str
    name: str
    tier: str
    pinned: bool
    domains: list
    consequence: float
    tool_triggers: list
    antigens: list
    connections: dict
    reminder: str
    # State (loaded from state file)
    adaptive_spike: float = 0.0
    dormant: bool = False
    days_since_activation: int = 0
    activation_count: int = 0


# ============================================================
# LOADING
# ============================================================

_rules_cache = None
_rules_mtime = 0


def clear_cache():
    """Clear rules cache. Public method for testability."""
    global _rules_cache, _rules_mtime
    _rules_cache = None
    _rules_mtime = 0


def validate_rules(rules: dict[str, Rule]) -> list[str]:
    """Validate rules against schema constraints. Returns list of warnings."""
    warnings = []
    for rid, r in rules.items():
        if r.tier not in VALID_TIERS:
            warnings.append(f"{rid}: invalid tier '{r.tier}' (expected {VALID_TIERS})")
        if r.consequence < CONSEQUENCE_MIN or r.consequence > CONSEQUENCE_MAX:
            warnings.append(f"{rid}: consequence {r.consequence} outside [{CONSEQUENCE_MIN}, {CONSEQUENCE_MAX}]")
        for d in r.domains:
            if d not in VALID_DOMAINS:
                warnings.append(f"{rid}: invalid domain '{d}' (expected {VALID_DOMAINS})")
        for conn_id in r.connections:
            if conn_id not in rules:
                warnings.append(f"{rid}: connection target '{conn_id}' not found in rules")
        for conn_id, weight in r.connections.items():
            if weight < 0 or weight > 1:
                warnings.append(f"{rid}: connection weight {weight} to {conn_id} outside [0, 1]")
    return warnings


def load_rules() -> dict[str, Rule]:
    """Load rules from YAML. Cached by mtime."""
    global _rules_cache, _rules_mtime

    if not RULES_PATH.exists():
        return {}

    mtime = RULES_PATH.stat().st_mtime
    if _rules_cache and mtime == _rules_mtime:
        return _rules_cache

    try:
        data = yaml.safe_load(RULES_PATH.read_text())
    except (yaml.YAMLError, OSError):
        return {}

    rules = {}
    for r in data.get("rules", []):
        rules[r["id"]] = Rule(
            id=r["id"],
            principle_id=r.get("principle_id", ""),
            name=r["name"],
            tier=r["tier"],
            pinned=r.get("pinned", False),
            domains=r.get("domains", ["all"]),
            consequence=r.get("consequence", 0.2),
            tool_triggers=r.get("tool_triggers", []),
            antigens=r.get("antigens", []),
            connections=r.get("connections", {}),
            reminder=r.get("reminder", ""),
        )

    _rules_cache = rules
    _rules_mtime = mtime
    return rules


def load_state() -> dict:
    """Load persistent state from JSON."""
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict):
    """Save state to JSON atomically (write tmp + rename)."""
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(STATE_PATH.parent),
            prefix=".rule-engine-state-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2)
            os.rename(tmp_path, str(STATE_PATH))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError:
        pass


def apply_state(rules: dict[str, Rule], state: dict):
    """Apply persistent state to loaded rules. Validates and clamps values."""
    rule_states = state.get("rules", {})
    for rid, rstate in rule_states.items():
        if rid in rules:
            # Clamp spike to [0, IMMUNE_SPIKE] — IMMUNE_SPIKE is the true max
            # (SPIKE_CAP limits normal violations; immune reactivation goes higher)
            raw_spike = rstate.get("adaptive_spike", 0.0)
            try:
                spike = float(raw_spike)
            except (TypeError, ValueError):
                spike = 0.0
            rules[rid].adaptive_spike = max(0.0, min(spike, IMMUNE_SPIKE))

            rules[rid].dormant = bool(rstate.get("dormant", False))

            raw_days = rstate.get("days_since_activation", 0)
            try:
                rules[rid].days_since_activation = max(0, int(raw_days))
            except (TypeError, ValueError):
                rules[rid].days_since_activation = 0

            raw_count = rstate.get("activation_count", 0)
            try:
                rules[rid].activation_count = max(0, int(raw_count))
            except (TypeError, ValueError):
                rules[rid].activation_count = 0


def extract_state(rules: dict[str, Rule], existing_state: dict) -> dict:
    """Extract current rule state for persistence."""
    rule_states = {}
    for rid, rule in rules.items():
        rule_states[rid] = {
            "adaptive_spike": rule.adaptive_spike,
            "dormant": rule.dormant,
            "days_since_activation": rule.days_since_activation,
            "activation_count": rule.activation_count,
        }

    return {
        "rules": rule_states,
        "co_activation": existing_state.get("co_activation", {}),
        "recently_unmerged": existing_state.get("recently_unmerged", {}),
        "last_decay": existing_state.get("last_decay", ""),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ============================================================
# DOMAIN + TOOL CLASSIFICATION
# ============================================================

_domain_keywords = None
_tool_keywords = None


def _load_classification_keywords():
    """Load domain and tool keywords from rules.yaml."""
    global _domain_keywords, _tool_keywords
    if _domain_keywords is not None:
        return

    try:
        data = yaml.safe_load(RULES_PATH.read_text())
        _domain_keywords = data.get("domain_keywords", {})
        _tool_keywords = data.get("tool_keywords", {})
    except (yaml.YAMLError, OSError):
        _domain_keywords = {}
        _tool_keywords = {}


def classify_prompt(text: str) -> tuple[str, str]:
    """Classify a prompt into (domain, tool) based on keywords.

    Uses stem matching: "editing" matches "edit", "compiling" matches "compile".
    Returns the best-matching domain and tool, or ("all", "read") as default.
    """
    _load_classification_keywords()

    words = set(re.findall(r'[a-z][a-z_/-]+', text.lower()))
    text_lower = text.lower()

    # Score each domain — check both exact word match and substring in text
    domain_scores = {}
    for domain, keywords in _domain_keywords.items():
        score = 0
        for kw in keywords:
            if kw in words or kw in text_lower:
                score += 1
        if score > 0:
            domain_scores[domain] = score

    # Score each tool — stem matching (keyword is prefix of any word)
    tool_scores = {}
    for tool, keywords in _tool_keywords.items():
        score = 0
        for kw in keywords:
            if kw in words:
                score += 1
            else:
                # Stem match: "edit" matches "editing", "compile" matches "compiling"
                for word in words:
                    if word.startswith(kw) or kw.startswith(word):
                        score += 1
                        break
        if score > 0:
            tool_scores[tool] = score

    best_domain = max(domain_scores, key=domain_scores.get) if domain_scores else "all"
    best_tool = max(tool_scores, key=tool_scores.get) if tool_scores else "read"

    return best_domain, best_tool


# ============================================================
# SCORING ENGINE
# ============================================================

def score_rule(rule: Rule, domain: str, tool: str) -> float:
    """Score a rule against a classified prompt. Must match sim exactly."""
    if rule.dormant:
        return 0.0

    if domain in rule.domains:
        domain_score = DOMAIN_SCORE_EXPLICIT
    elif "all" in rule.domains:
        domain_score = DOMAIN_SCORE_UNIVERSAL
    else:
        domain_score = 0.0

    consequence_score = rule.consequence
    tool_score = 0.2 if tool in rule.tool_triggers else 0.0
    spike_score = min(rule.adaptive_spike, SPIKE_CAP)

    return domain_score + consequence_score + tool_score + spike_score


def _build_reason(rule: Rule, domain: str, tool: str) -> str:
    """Build a short reason string explaining why this rule was selected."""
    parts = []
    if domain in rule.domains:
        parts.append(domain)
    elif "all" in rule.domains:
        parts.append("universal")
    if tool in rule.tool_triggers:
        parts.append(tool)
    if rule.adaptive_spike > 0:
        parts.append("spiked")
    return "+".join(parts) if parts else "base"


def domain_specificity(rule: Rule, domain: str) -> int:
    """Tiebreaker: explicit domain (1) > universal (0) > no match (-1)."""
    if domain in rule.domains:
        return 1
    elif "all" in rule.domains:
        return 0
    return -1


def get_relevant_rules(prompt_text: str) -> list[dict]:
    """Main entry point. Returns top relevant rules with reminders.

    Returns list of dicts with: id, name, reminder, score, principle_id, domain, tool, reason
    """
    rules = load_rules()
    if not rules:
        return []

    state = load_state()
    apply_state(rules, state)

    domain, tool = classify_prompt(prompt_text)

    # Score all rules
    scored = []
    for rule in rules.values():
        s = score_rule(rule, domain, tool)
        if s >= THRESHOLD:
            scored.append((rule, s))

    # Sort by score, then domain specificity as tiebreaker
    scored.sort(key=lambda x: (x[1], domain_specificity(x[0], domain)), reverse=True)
    activated = scored[:BUDGET]

    # Spreading activation
    activated_ids = {r.id for r, _ in activated}
    spread_candidates = []
    for rule, sc in activated:
        for conn_id, weight in rule.connections.items():
            if conn_id not in activated_ids and conn_id in rules:
                conn_rule = rules[conn_id]
                if not conn_rule.dormant:
                    base_score = score_rule(conn_rule, domain, tool)
                    spread_bonus = weight * SPREAD_BONUS_FACTOR
                    total = base_score + spread_bonus
                    if total >= THRESHOLD:
                        spread_candidates.append((conn_rule, total))

    spread_candidates.sort(key=lambda x: x[1], reverse=True)
    remaining = BUDGET - len(activated)
    if remaining > 0:
        activated.extend(spread_candidates[:remaining])

    # Update activation state
    for rule, _ in activated:
        rule.activation_count += 1
        rule.days_since_activation = 0

    # Track co-activations (exclude "all"-domain rules)
    co_act = state.get("co_activation", {})
    non_universal = sorted(r.id for r, _ in activated if "all" not in rules[r.id].domains)
    activated_id_set = {r.id for r, _ in activated}
    for i, r1 in enumerate(non_universal):
        for r2 in non_universal[i+1:]:
            key = f"{r1}:{r2}"
            if key not in co_act:
                co_act[key] = {"both": 0, "either": 0}
            co_act[key]["both"] += 1
            co_act[key]["either"] += 1
    for r_id in non_universal:
        for other_id in rules:
            if other_id != r_id and other_id not in activated_id_set and "all" not in rules[other_id].domains:
                key = ":".join(sorted([r_id, other_id]))
                if key in co_act:
                    co_act[key]["either"] += 1

    # Save updated state
    updated_state = extract_state(rules, state)
    updated_state["co_activation"] = co_act
    save_state(updated_state)

    # Return top INJECTION_LIMIT rules with reminders + reason
    result = []
    for rule, s in activated[:INJECTION_LIMIT]:
        if rule.reminder:
            result.append({
                "id": rule.id,
                "principle_id": rule.principle_id,
                "name": rule.name,
                "reminder": rule.reminder,
                "score": round(s, 3),
                "domain": domain,
                "tool": tool,
                "reason": _build_reason(rule, domain, tool),
            })

    return result


# ============================================================
# LIFECYCLE (called from session-close, not from hook)
# ============================================================

def record_violation(rule_id: str, source: str = "hook") -> str | None:
    """Record a violation/omission. Returns message if immune reactivation."""
    rules = load_rules()
    state = load_state()
    apply_state(rules, state)

    if rule_id not in rules:
        return None

    rule = rules[rule_id]

    # Immune reactivation
    if rule.dormant:
        rule.dormant = False
        rule.adaptive_spike = IMMUNE_SPIKE
        msg = f"IMMUNE REACTIVATION: {rule.id} ({rule.name}) spike={IMMUNE_SPIKE}"
        save_state(extract_state(rules, state))
        return msg

    # Normal spike
    spike = SPIKE_AMOUNT.get(source, 0.08)
    rule.adaptive_spike = min(rule.adaptive_spike + spike, SPIKE_CAP)
    save_state(extract_state(rules, state))
    return None


def advance_day(days: int = None):
    """Decay spikes, tick cooldowns. Calendar-aware: applies multiple days if needed.

    If days is None, calculates from last_decay date. If no last_decay, applies 1 day.
    """
    rules = load_rules()
    state = load_state()
    apply_state(rules, state)

    # Calendar-based decay: calculate actual days elapsed
    if days is None:
        last_decay = state.get("last_decay", "")
        if last_decay:
            try:
                last_date = datetime.date.fromisoformat(last_decay)
                today = datetime.date.today()
                elapsed = (today - last_date).days
                # Cap to prevent mass dormancy from ancient/corrupt last_decay dates
                days = max(1, min(elapsed, CALENDAR_DECAY_MAX_DAYS))
            except (ValueError, TypeError):
                days = 1
        else:
            days = 1

    # Decay spikes (apply N days of decay)
    for rule in rules.values():
        if rule.adaptive_spike > 0:
            rule.adaptive_spike = max(0, rule.adaptive_spike - SPIKE_DECAY_PER_DAY * days)
            if rule.adaptive_spike <= 0.001:
                rule.adaptive_spike = 0.0
        rule.days_since_activation += days

    # Tick un-merge cooldowns
    unmerged = state.get("recently_unmerged", {})
    expired = [rid for rid, d in unmerged.items() if d <= days]
    for rid in expired:
        del unmerged[rid]
    for rid in unmerged:
        unmerged[rid] -= days

    # Prune co-activation pairs: remove low-signal pairs, cap total
    co_act = state.get("co_activation", {})
    if len(co_act) > CO_ACTIVATION_MAX_PAIRS:
        # Remove pairs with either < threshold
        co_act = {k: v for k, v in co_act.items()
                  if v.get("either", 0) >= CO_ACTIVATION_MIN_EITHER}
        # If still over limit, keep top pairs by 'either' count
        if len(co_act) > CO_ACTIVATION_MAX_PAIRS:
            sorted_pairs = sorted(co_act.items(), key=lambda x: x[1]["either"], reverse=True)
            co_act = dict(sorted_pairs[:CO_ACTIVATION_MAX_PAIRS])

    updated = extract_state(rules, state)
    updated["recently_unmerged"] = unmerged
    updated["co_activation"] = co_act
    updated["last_decay"] = time.strftime("%Y-%m-%d")
    save_state(updated)


def detect_inactive() -> list[str]:
    """Find rules that should go dormant (60+ days inactive, not pinned)."""
    rules = load_rules()
    state = load_state()
    apply_state(rules, state)

    return [r.id for r in rules.values()
            if r.days_since_activation >= INACTIVE_THRESHOLD_DAYS
            and not r.dormant and not r.pinned]


def detect_merge_candidates() -> list[tuple[str, str, float]]:
    """Find rule pairs with >90% co-activation rate."""
    state = load_state()
    unmerged = state.get("recently_unmerged", {})
    candidates = []

    for key, counts in state.get("co_activation", {}).items():
        if counts["either"] >= 10:
            ratio = counts["both"] / counts["either"]
            if ratio >= CO_ACTIVATION_MERGE_THRESHOLD:
                r1, r2 = key.split(":")
                if r1 not in unmerged and r2 not in unmerged:
                    candidates.append((r1, r2, ratio))

    return candidates


def get_lifecycle_report() -> dict:
    """Generate lifecycle report for session-close."""
    rules = load_rules()
    state = load_state()
    apply_state(rules, state)

    active = [r for r in rules.values() if not r.dormant]
    dormant = [r for r in rules.values() if r.dormant]
    spiked = [r for r in active if r.adaptive_spike > 0]
    inactive = detect_inactive()
    merges = detect_merge_candidates()

    # Schema validation warnings
    schema_warnings = validate_rules(rules)

    return {
        "total_rules": len(rules),
        "active": len(active),
        "dormant": len(dormant),
        "dormant_ids": [r.id for r in dormant],
        "spiked": len(spiked),
        "spiked_rules": {r.id: round(r.adaptive_spike, 3) for r in spiked},
        "inactive_candidates": inactive,
        "merge_candidates": [(r1, r2, round(ratio, 2)) for r1, r2, ratio in merges],
        "last_decay": state.get("last_decay", "never"),
        "co_activation_pairs": len(state.get("co_activation", {})),
        "schema_warnings": schema_warnings,
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "test":
            prompt = " ".join(sys.argv[2:]) or "edit some python code"
            domain, tool = classify_prompt(prompt)
            print(f"Domain: {domain}, Tool: {tool}")
            results = get_relevant_rules(prompt)
            for r in results:
                print(f"  [{r['id']}] {r['name']} (score={r['score']}, reason={r['reason']}) — {r['reminder']}")
            if not results:
                print("  (no rules above threshold)")

        elif cmd == "lifecycle":
            report = get_lifecycle_report()
            print(json.dumps(report, indent=2))

        elif cmd == "advance":
            advance_day()
            print("Advanced (calendar-based decay applied)")

        elif cmd == "validate":
            rules = load_rules()
            warnings = validate_rules(rules)
            if warnings:
                for w in warnings:
                    print(f"  WARNING: {w}")
            else:
                print("  All rules valid.")

        elif cmd == "violation":
            rule_id = sys.argv[2] if len(sys.argv) > 2 else "R4"
            source = sys.argv[3] if len(sys.argv) > 3 else "hook"
            msg = record_violation(rule_id, source)
            print(msg or f"Spike recorded for {rule_id}")

        else:
            print(f"Usage: {sys.argv[0]} [test <prompt>|lifecycle|advance|validate|violation <rule_id> <source>]")
    else:
        # Default: show lifecycle report
        report = get_lifecycle_report()
        print(json.dumps(report, indent=2))
