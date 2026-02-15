"""
Rule Engine Simulator v2 — Tuned parameters + expanded scenarios.
Tests the Adaptive Rule Engine design before building.
"""

import json
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timedelta
import random

# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class Rule:
    id: str
    name: str
    tier: str  # value, principle, practice
    pinned: bool
    domains: list
    consequence: float  # 0.1, 0.2, 0.3
    tool_triggers: list
    antigens: list
    adaptive_spike: float = 0.0
    spike_expires: Optional[str] = None
    connections: dict = field(default_factory=dict)
    dormant: bool = False
    graduated: bool = False
    last_activated: Optional[str] = None
    activation_count: int = 0
    days_since_activation: int = 0

@dataclass
class Prompt:
    domain: str
    tool: str
    description: str

@dataclass
class SessionEvent:
    event_type: str  # "violation", "omission", "correction"
    rule_id: Optional[str] = None
    source: str = "hook"  # "hook", "self_check", "user", "audit"

# ============================================================
# RULE ENGINE — TUNED v2
# ============================================================

class RuleEngine:
    THRESHOLD = 0.5
    BUDGET = 5
    # v2 TUNING: Higher spikes, slower decay
    SPIKE_AMOUNT = {
        "hook": 0.15,       # was 0.10
        "self_check": 0.08, # was 0.06
        "user": 0.15,       # was 0.10
        "audit": 0.06,      # was 0.04
    }
    IMMUNE_SPIKE = 0.20              # was 0.10 — forceful reactivation
    SPIKE_DECAY_PER_DAY = 0.010      # was 0.014 — 10-day window (was 7)
    SPIKE_CAP = 0.15                 # was 0.10
    SPREAD_BONUS_FACTOR = 0.2
    CO_ACTIVATION_MERGE_THRESHOLD = 0.90
    INACTIVE_THRESHOLD_DAYS = 60     # was 30
    # v3 FIX: Domain affinity — explicit domain match scores higher than "all"
    DOMAIN_SCORE_EXPLICIT = 0.4      # rule explicitly lists this domain
    DOMAIN_SCORE_UNIVERSAL = 0.3     # rule has "all" (reduced from 0.4)
    # v3 FIX: Un-merge cooldown — recently split rules can't be re-flagged
    UNMERGE_COOLDOWN_DAYS = 30

    def __init__(self, rules: list[Rule]):
        self.rules = {r.id: r for r in rules}
        self.co_activation_tracker = {}
        self.prompt_count = 0
        self.activation_log = []  # per-prompt log for analysis
        self.recently_unmerged = {}  # rule_id → days remaining in cooldown

    def score(self, rule: Rule, prompt: Prompt) -> float:
        if rule.dormant:
            return 0.0
        # v3: Explicit domain match > universal "all" match
        if prompt.domain in rule.domains:
            domain_score = self.DOMAIN_SCORE_EXPLICIT
        elif "all" in rule.domains:
            domain_score = self.DOMAIN_SCORE_UNIVERSAL
        else:
            domain_score = 0.0
        consequence_score = rule.consequence
        tool_score = 0.2 if prompt.tool in rule.tool_triggers else 0.0
        spike_score = min(rule.adaptive_spike, self.SPIKE_CAP)
        return domain_score + consequence_score + tool_score + spike_score

    def domain_specificity(self, rule: Rule, prompt: Prompt) -> int:
        """v3 tiebreaker: explicit domain (1) > universal (0) > no match (-1)"""
        if prompt.domain in rule.domains:
            return 1
        elif "all" in rule.domains:
            return 0
        return -1

    def retrieve(self, prompt: Prompt) -> list[tuple[Rule, float]]:
        scored = []
        for rule in self.rules.values():
            s = self.score(rule, prompt)
            if s >= self.THRESHOLD:
                scored.append((rule, s))

        # v3: Sort by score, then domain specificity as tiebreaker
        scored.sort(key=lambda x: (x[1], self.domain_specificity(x[0], prompt)), reverse=True)
        activated = scored[:self.BUDGET]

        # Spreading activation
        activated_ids = {r.id for r, _ in activated}
        spread_candidates = []
        for rule, sc in activated:
            for conn_id, weight in rule.connections.items():
                if conn_id not in activated_ids and conn_id in self.rules:
                    conn_rule = self.rules[conn_id]
                    if not conn_rule.dormant:
                        base_score = self.score(conn_rule, prompt)
                        spread_bonus = weight * self.SPREAD_BONUS_FACTOR
                        total = base_score + spread_bonus
                        if total >= self.THRESHOLD:
                            spread_candidates.append((conn_rule, total))

        spread_candidates.sort(key=lambda x: x[1], reverse=True)
        remaining_budget = self.BUDGET - len(activated)
        if remaining_budget > 0:
            activated.extend(spread_candidates[:remaining_budget])

        activated_ids_final = {r.id for r, _ in activated}
        for rule, _ in activated:
            rule.last_activated = "today"
            rule.activation_count += 1
            rule.days_since_activation = 0

        # v2 FIX: Exclude "all"-domain rules from co-activation merge tracking
        non_universal = [rid for rid in activated_ids_final
                         if "all" not in self.rules[rid].domains]
        ids = sorted(non_universal)
        for i, r1 in enumerate(ids):
            for r2 in ids[i+1:]:
                key = (r1, r2)
                if key not in self.co_activation_tracker:
                    self.co_activation_tracker[key] = {"both": 0, "either": 0}
                self.co_activation_tracker[key]["both"] += 1
                self.co_activation_tracker[key]["either"] += 1

        for r_id in non_universal:
            for other_id in self.rules:
                if (other_id != r_id and other_id not in activated_ids_final
                        and "all" not in self.rules[other_id].domains):
                    key = tuple(sorted([r_id, other_id]))
                    if key in self.co_activation_tracker:
                        self.co_activation_tracker[key]["either"] += 1

        # Log for analysis
        self.activation_log.append({
            "prompt": prompt.domain + "/" + prompt.tool,
            "activated": [(r.id, f"{s:.2f}") for r, s in activated],
            "eligible_count": len(scored),
        })

        self.prompt_count += 1
        return activated

    def record_event(self, event: SessionEvent):
        if event.rule_id and event.rule_id in self.rules:
            rule = self.rules[event.rule_id]
            # v2: Immune reactivation with stronger spike
            if rule.dormant:
                rule.dormant = False
                rule.adaptive_spike = self.IMMUNE_SPIKE
                rule.spike_expires = "10_days"
                return f"IMMUNE REACTIVATION: {rule.id} ({rule.name}) spike={self.IMMUNE_SPIKE}"

            spike = self.SPIKE_AMOUNT.get(event.source, 0.08)
            rule.adaptive_spike = min(rule.adaptive_spike + spike, self.SPIKE_CAP)
            rule.spike_expires = "10_days"
        return None

    def decay_spikes(self, days: int = 1):
        for rule in self.rules.values():
            if rule.adaptive_spike > 0:
                rule.adaptive_spike = max(0, rule.adaptive_spike - self.SPIKE_DECAY_PER_DAY * days)
                if rule.adaptive_spike <= 0.001:
                    rule.adaptive_spike = 0
                    rule.spike_expires = None
            if rule.last_activated != "today":
                rule.days_since_activation += days
            rule.last_activated = None

    def advance_day(self):
        self.decay_spikes(1)
        # v3: Tick un-merge cooldowns
        expired = [rid for rid, days in self.recently_unmerged.items() if days <= 1]
        for rid in expired:
            del self.recently_unmerged[rid]
        for rid in self.recently_unmerged:
            self.recently_unmerged[rid] -= 1

    def detect_merge_candidates(self) -> list[tuple[str, str, float]]:
        candidates = []
        for (r1, r2), counts in self.co_activation_tracker.items():
            if counts["either"] >= 10:
                ratio = counts["both"] / counts["either"]
                if ratio >= self.CO_ACTIVATION_MERGE_THRESHOLD:
                    # v3: Skip pairs in un-merge cooldown
                    if r1 in self.recently_unmerged or r2 in self.recently_unmerged:
                        continue
                    candidates.append((r1, r2, ratio))
        return candidates

    def unmerge(self, rule_id: str):
        """Mark a rule as recently un-merged (exempt from merge detection)."""
        self.recently_unmerged[rule_id] = self.UNMERGE_COOLDOWN_DAYS

    def detect_inactive(self) -> list[Rule]:
        return [r for r in self.rules.values()
                if r.days_since_activation >= self.INACTIVE_THRESHOLD_DAYS
                and not r.dormant and not r.pinned]

    def add_rule(self, rule: Rule):
        self.rules[rule.id] = rule

    def remove_rule(self, rule_id: str):
        if rule_id in self.rules:
            del self.rules[rule_id]
            # Clean co-activation tracker
            keys_to_remove = [k for k in self.co_activation_tracker if rule_id in k]
            for k in keys_to_remove:
                del self.co_activation_tracker[k]

    def summary(self) -> dict:
        active = [r for r in self.rules.values() if not r.dormant]
        dormant = [r for r in self.rules.values() if r.dormant]
        values = [r for r in active if r.tier == "value"]
        principles = [r for r in active if r.tier == "principle"]
        practices = [r for r in active if r.tier == "practice"]
        spiked = [r for r in active if r.adaptive_spike > 0]
        return {
            "total": len(self.rules),
            "active": len(active),
            "dormant": len(dormant),
            "values": len(values),
            "principles": len(principles),
            "practices": len(practices),
            "spiked": len(spiked),
            "prompts_processed": self.prompt_count,
        }

    def budget_analysis(self, last_n: int = 20) -> dict:
        """Analyze recent activation patterns."""
        recent = self.activation_log[-last_n:] if self.activation_log else []
        if not recent:
            return {"avg_eligible": 0, "avg_loaded": 0, "dropped_pct": 0}
        eligible = sum(e["eligible_count"] for e in recent) / len(recent)
        loaded = sum(len(e["activated"]) for e in recent) / len(recent)
        dropped = (eligible - loaded) / eligible * 100 if eligible > 0 else 0
        return {
            "avg_eligible": round(eligible, 1),
            "avg_loaded": round(loaded, 1),
            "dropped_pct": round(dropped, 1),
        }


# ============================================================
# SEED DATA
# ============================================================

def create_seed_rules() -> list[Rule]:
    return [
        Rule("R1", "Interrogation > Assumptions", "value", True,
             ["all"], 0.3, [], ["Mistake #1"], connections={"R12": 0.5, "R6": 0.4}),
        Rule("R4", "Read Before Editing", "value", True,
             ["code", "writing"], 0.3, ["edit", "write"], ["Mistake #4", "Mistake #29"],
             connections={"R9": 0.6, "R86": 0.5}),
        Rule("R5", "Code > Tokens", "value", True,
             ["all"], 0.3, [], ["Mistake #40"], connections={"R8": 0.5}),
        Rule("R9", "Verify Everything", "value", True,
             ["all"], 0.3, ["bash"], ["Mistake #41"],
             connections={"R4": 0.6, "R30": 0.4}),
        Rule("R14", "Markdown Is The Superpower", "value", True,
             ["all"], 0.2, [], [], connections={"R27": 0.5}),
        Rule("R6", "Don't Add Ideas", "principle", False,
             ["writing", "advisory"], 0.2, ["write", "skill"], ["Mistake #10"],
             connections={"R1": 0.4, "R12": 0.6}),
        Rule("R8", "Build Systems Not Fixes", "principle", False,
             ["code", "scraping"], 0.2, [], ["Mistake #30"], connections={"R5": 0.5}),
        Rule("R12", "Do What Was Asked", "principle", False,
             ["all"], 0.2, [], ["Mistake #6", "Mistake #12"],
             connections={"R6": 0.6, "R1": 0.5}),
        Rule("R27", "Cross-Reference & Propagate", "principle", False,
             ["writing", "code"], 0.2, ["edit", "write"], [],
             connections={"R14": 0.5, "R4": 0.3}),
        Rule("R30", "Git Discipline", "principle", False,
             ["git", "code"], 0.2, ["bash"], ["Mistake #59"],
             connections={"R9": 0.4}),
        Rule("R36", "Pre-Execution Gate", "principle", False,
             ["all"], 0.2, ["skill", "bash", "edit"], ["Mistake #36"],
             connections={"R9": 0.3, "R4": 0.3}),
        Rule("R42", "Correct Audio Terms", "practice", False,
             ["audio"], 0.1, [], [], connections={}),
        Rule("R67", "Table After 2 Iterations", "principle", False,
             ["all"], 0.1, [], ["Mistake #67"], connections={"R87": 0.4}),
        Rule("R70", "Confirm Priority Before PRDs", "principle", False,
             ["writing"], 0.2, ["write", "skill"], ["Mistake #70"], connections={"R1": 0.3}),
        Rule("R75", "Budget Awareness", "principle", False,
             ["budget"], 0.2, [], ["Mistake #75"], connections={"R5": 0.3}),
        Rule("R84", "Permanent Locations Only", "practice", False,
             ["code"], 0.2, ["write", "bash"], ["Mistake #84"], connections={}),
        Rule("R86", "Filesystem Is Ground Truth", "principle", False,
             ["code", "scraping"], 0.2, ["bash", "glob"], ["Mistake #86"],
             connections={"R4": 0.5, "R9": 0.3}),
        Rule("R87", "Diverge Before Converging", "principle", False,
             ["all"], 0.2, [], ["Mistake #103"],
             connections={"R67": 0.4, "R1": 0.3}),
        Rule("R50", "Security Non-Negotiable", "principle", False,
             ["code", "git"], 0.3, ["bash", "write"], ["Mistake #50"],
             connections={"R9": 0.4}),
        Rule("R99", "End With Actionable Steps", "practice", False,
             ["all"], 0.1, [], [], connections={}),
    ]


# ============================================================
# PROMPT GENERATORS
# ============================================================

def generate_coding_session(n_prompts: int = 15) -> list[Prompt]:
    tools = ["edit", "edit", "edit", "bash", "read", "glob", "edit", "bash",
             "write", "edit", "bash", "edit", "read", "bash", "edit"]
    return [Prompt("code", tools[i % len(tools)], f"code {i+1}") for i in range(n_prompts)]

def generate_writing_session(n_prompts: int = 10) -> list[Prompt]:
    tools = ["read", "write", "write", "edit", "write", "read", "write",
             "skill", "write", "edit"]
    return [Prompt("writing", tools[i % len(tools)], f"write {i+1}") for i in range(n_prompts)]

def generate_mixed_session(n_prompts: int = 12) -> list[Prompt]:
    prompts = [
        Prompt("advisory", "skill", "ask advisor"),
        Prompt("code", "read", "read code"),
        Prompt("code", "edit", "edit code"),
        Prompt("code", "edit", "edit more"),
        Prompt("git", "bash", "git commit"),
        Prompt("writing", "write", "write doc"),
        Prompt("code", "bash", "run tests"),
        Prompt("advisory", "skill", "ask another advisor"),
        Prompt("code", "edit", "fix bug"),
        Prompt("git", "bash", "git push"),
        Prompt("budget", "bash", "check budget"),
        Prompt("code", "edit", "final edit"),
    ]
    return prompts[:n_prompts]

def generate_audio_session(n_prompts: int = 8) -> list[Prompt]:
    prompts = [
        Prompt("audio", "read", "read DSP"), Prompt("audio", "edit", "edit filter"),
        Prompt("audio", "bash", "audio test"), Prompt("code", "edit", "edit plugin"),
        Prompt("audio", "edit", "tune params"), Prompt("audio", "bash", "build plugin"),
        Prompt("audio", "write", "write docs"), Prompt("audio", "edit", "final tweak"),
    ]
    return prompts[:n_prompts]

def generate_scraping_session(n_prompts: int = 10) -> list[Prompt]:
    tools = ["bash", "bash", "bash", "read", "bash", "write", "bash", "bash", "read", "bash"]
    return [Prompt("scraping", tools[i % len(tools)], f"scrape {i+1}") for i in range(n_prompts)]

def generate_rapid_switch_session() -> list[Prompt]:
    """Rapid domain switching — worst case for activation."""
    return [
        Prompt("code", "edit", "edit code"),
        Prompt("audio", "edit", "edit filter"),
        Prompt("writing", "write", "write PRD"),
        Prompt("git", "bash", "commit"),
        Prompt("code", "bash", "run test"),
        Prompt("advisory", "skill", "ask advisor"),
        Prompt("audio", "bash", "build plugin"),
        Prompt("writing", "edit", "edit doc"),
        Prompt("scraping", "bash", "scrape data"),
        Prompt("code", "edit", "fix bug"),
        Prompt("budget", "bash", "check budget"),
        Prompt("code", "write", "write new file"),
    ]

def generate_git_heavy_session() -> list[Prompt]:
    """Session dominated by git operations."""
    return [
        Prompt("git", "bash", "git status"),
        Prompt("git", "bash", "git diff"),
        Prompt("code", "edit", "fix conflict"),
        Prompt("git", "bash", "git add"),
        Prompt("git", "bash", "git commit"),
        Prompt("code", "read", "review change"),
        Prompt("git", "bash", "git push"),
        Prompt("git", "bash", "gh pr create"),
    ]


# ============================================================
# SCENARIO RUNNER
# ============================================================

def run_scenario(name, description, engine, weeks, sessions_per_week,
                 events_schedule=None, new_rules_schedule=None,
                 remove_rules_schedule=None):
    print(f"\n{'='*70}")
    print(f"SCENARIO: {name}")
    print(f"{description}")
    print(f"{'='*70}")

    for week in range(1, weeks + 1):
        week_activations = {}
        week_events = []

        if new_rules_schedule and week in new_rules_schedule:
            for rule in new_rules_schedule[week]:
                engine.add_rule(rule)
                week_events.append(f"  + NEW: {rule.id} ({rule.name})")

        if remove_rules_schedule and week in remove_rules_schedule:
            for rid in remove_rules_schedule[week]:
                name_removed = engine.rules[rid].name if rid in engine.rules else "?"
                engine.remove_rule(rid)
                week_events.append(f"  - MERGED: {rid} ({name_removed})")

        session_types = sessions_per_week[(week - 1) % len(sessions_per_week)]
        if not isinstance(session_types, list):
            session_types = [session_types]

        for session_fn in session_types:
            prompts = session_fn()
            for prompt in prompts:
                activated = engine.retrieve(prompt)
                for rule, sc in activated:
                    week_activations[rule.id] = week_activations.get(rule.id, 0) + 1

            if events_schedule and week in events_schedule:
                for event in events_schedule[week]:
                    result = engine.record_event(event)
                    if result:
                        week_events.append(f"  ! {result}")
                    else:
                        week_events.append(f"  ! {event.event_type}: {event.rule_id} (src:{event.source})")

            engine.advance_day()

        remaining_days = 7 - len(session_types)
        for _ in range(remaining_days):
            engine.advance_day()

        summary = engine.summary()
        merge_candidates = engine.detect_merge_candidates()
        inactive = engine.detect_inactive()
        budget = engine.budget_analysis(20)
        top_activated = sorted(week_activations.items(), key=lambda x: x[1], reverse=True)[:7]
        spiked_rules = [(r.id, f"{r.adaptive_spike:.3f}")
                        for r in engine.rules.values() if r.adaptive_spike > 0]

        print(f"\n--- Week {week} ---")
        print(f"  Rules: {summary['active']}active ({summary['values']}V/{summary['principles']}P/{summary['practices']}Pr) {summary['dormant']}dormant | Prompts: {summary['prompts_processed']}")
        print(f"  Budget: avg {budget['avg_eligible']} eligible → {budget['avg_loaded']} loaded ({budget['dropped_pct']}% dropped)")
        if week_events:
            for e in week_events:
                print(e)
        print(f"  Top: {', '.join(f'{rid}({cnt})' for rid, cnt in top_activated)}")
        if spiked_rules:
            print(f"  Spikes: {', '.join(f'{rid}={spike}' for rid, spike in spiked_rules)}")
        if merge_candidates:
            print(f"  MERGE: {', '.join(f'{r1}+{r2}({ratio:.0%})' for r1, r2, ratio in merge_candidates)}")
        if inactive:
            print(f"  INACTIVE {engine.INACTIVE_THRESHOLD_DAYS}d+: {', '.join(f'{r.id}({r.days_since_activation}d)' for r in inactive)}")


# ============================================================
# ALL SCENARIOS
# ============================================================

def main():
    print("=" * 70)
    print("ADAPTIVE RULE ENGINE SIMULATION v2")
    print("Tuned: spike=0.15, decay=0.010/d, immune=0.20, inactive=60d")
    print("Fixed: merge excludes 'all' domain, immune spike forceful")
    print("=" * 70)

    # S1: Steady State
    engine1 = RuleEngine(create_seed_rules())
    run_scenario("1: Steady State",
        "Normal mixed sessions, no violations, no new rules.\n"
        "Q: Activation patterns correct? Values dominate?",
        engine1, weeks=4,
        sessions_per_week=[
            [generate_coding_session, generate_writing_session],
            [generate_mixed_session, generate_coding_session],
            [generate_coding_session, generate_audio_session],
            [generate_writing_session, generate_mixed_session],
        ])

    # S2: Rule Accumulation (10 new over 4 weeks)
    engine2 = RuleEngine(create_seed_rules())
    new_rules = {
        1: [Rule("R101", "Check imports before edit", "practice", False,
                 ["code"], 0.1, ["edit"], [], adaptive_spike=0.15),
            Rule("R102", "Validate YAML before write", "practice", False,
                 ["code", "writing"], 0.1, ["write"], [], adaptive_spike=0.15)],
        2: [Rule("R103", "Brainstorm before fixing", "practice", False,
                 ["all"], 0.2, [], ["Mistake #103"], adaptive_spike=0.15, connections={"R87": 0.5}),
            Rule("R104", "Check test coverage", "practice", False,
                 ["code"], 0.1, ["bash"], [], adaptive_spike=0.15),
            Rule("R105", "Confirm scope with user", "practice", False,
                 ["writing", "advisory"], 0.2, ["skill"], [], adaptive_spike=0.15, connections={"R1": 0.4})],
        3: [Rule("R106", "Use dedicated tools not bash", "practice", False,
                 ["code"], 0.2, ["bash"], [], adaptive_spike=0.15),
            Rule("R107", "Check for stale locks", "practice", False,
                 ["code", "git"], 0.1, ["bash"], [], adaptive_spike=0.15)],
        4: [Rule("R108", "Verify webhook responses", "practice", False,
                 ["code"], 0.1, ["bash"], [], adaptive_spike=0.15),
            Rule("R109", "Don't duplicate subagent work", "practice", False,
                 ["code", "advisory"], 0.2, [], [], adaptive_spike=0.15),
            Rule("R110", "Check domain before scraping", "practice", False,
                 ["scraping"], 0.2, ["bash"], [], adaptive_spike=0.15)],
    }
    run_scenario("2: Rule Accumulation",
        "10 new rules over 4 weeks. Budget=5 per prompt.\n"
        "Q: Do new rules crowd out Values?",
        engine2, weeks=4,
        sessions_per_week=[
            [generate_coding_session, generate_writing_session],
            [generate_mixed_session, generate_coding_session],
            [generate_coding_session, generate_mixed_session],
            [generate_coding_session, generate_writing_session]],
        new_rules_schedule=new_rules)

    # S3: Repeated Violations (tuned spikes)
    engine3 = RuleEngine(create_seed_rules())
    run_scenario("3: Repeated Violations (tuned)",
        "R12 violated weeks 1-3, clean weeks 4-6.\n"
        "Q: Do tuned spikes (0.15) last long enough? Decay properly?",
        engine3, weeks=6,
        sessions_per_week=[
            [generate_coding_session], [generate_mixed_session],
            [generate_coding_session], [generate_coding_session],
            [generate_mixed_session], [generate_coding_session]],
        events_schedule={
            1: [SessionEvent("violation", "R12", "user")],
            2: [SessionEvent("violation", "R12", "user"),
                SessionEvent("omission", "R12", "self_check")],
            3: [SessionEvent("violation", "R12", "user")]})

    # S4: Dormancy + Immune (tuned)
    engine4 = RuleEngine(create_seed_rules())
    engine4.rules["R42"].days_since_activation = 55
    engine4.rules["R42"].dormant = True  # v2: actually set dormant
    run_scenario("4: Dormancy + Immune (tuned)",
        "R42 dormant (55d). Week 3: audio correction → immune reactivation.\n"
        "Q: Does immune spike (0.20) actually make R42 appear in activated?",
        engine4, weeks=4,
        sessions_per_week=[
            [generate_coding_session, generate_writing_session],
            [generate_mixed_session, generate_coding_session],
            [generate_audio_session],
            [generate_audio_session, generate_coding_session]],
        events_schedule={3: [SessionEvent("omission", "R42", "user")]})

    # S5: Budget Pressure (35 rules)
    engine5 = RuleEngine(create_seed_rules())
    for i in range(15):
        engine5.add_rule(Rule(
            f"R{200+i}", f"Code practice {i+1}", "practice", False,
            ["code"], 0.2 if i < 5 else 0.1, ["edit"], [],
            connections={"R4": 0.3} if i % 3 == 0 else {}))
    run_scenario("5: Budget Pressure (35 rules)",
        "35 rules, 15 code-domain. Budget=5. Heavy coding.\n"
        "Q: What % of eligible rules get dropped? Do Values win?",
        engine5, weeks=2,
        sessions_per_week=[[generate_coding_session], [generate_coding_session]])

    # S6: Spike Context Isolation
    engine6 = RuleEngine(create_seed_rules())
    run_scenario("6: Spike Context Isolation",
        "R70 (Confirm Priority, writing-only) violated week 1.\n"
        "Q: Does spike boost R70 in writing WITHOUT leaking into code?",
        engine6, weeks=3,
        sessions_per_week=[
            [generate_writing_session],
            [generate_coding_session, generate_writing_session],
            [generate_writing_session]],
        events_schedule={1: [SessionEvent("violation", "R70", "user")]})

    # ==================== NEW SCENARIOS ====================

    # S7: Rapid Domain Switching
    engine7 = RuleEngine(create_seed_rules())
    run_scenario("7: Rapid Domain Switching",
        "Session with 12 prompts across 6 different domains.\n"
        "Q: Do rules swap in/out correctly? Any stickiness from previous domain?",
        engine7, weeks=3,
        sessions_per_week=[
            [generate_rapid_switch_session],
            [generate_rapid_switch_session, generate_coding_session],
            [generate_rapid_switch_session]])

    # S8: Multi-Violation Spike Stacking
    engine8 = RuleEngine(create_seed_rules())
    run_scenario("8: Multi-Violation Spike Stacking",
        "3 different rules violated in same session (R4, R12, R86).\n"
        "Q: Do spikes stack correctly? Do they compete for budget?",
        engine8, weeks=4,
        sessions_per_week=[
            [generate_coding_session], [generate_mixed_session],
            [generate_coding_session], [generate_coding_session]],
        events_schedule={
            1: [SessionEvent("violation", "R4", "user"),
                SessionEvent("violation", "R12", "user"),
                SessionEvent("omission", "R86", "hook")]})

    # S9: Merge + Remove — System adapts after consolidation
    engine9 = RuleEngine(create_seed_rules())
    # Add two similar rules that should merge
    engine9.add_rule(Rule("R91", "Check refs before edit", "practice", False,
                          ["code"], 0.2, ["edit"], [], connections={"R4": 0.6}))
    engine9.add_rule(Rule("R92", "Verify file exists before edit", "practice", False,
                          ["code"], 0.2, ["edit"], [], connections={"R4": 0.5, "R91": 0.7}))
    run_scenario("9: Merge + Remove",
        "R91+R92 are similar code/edit rules. Run 3 weeks, then merge in week 4.\n"
        "Q: Does merge detection flag them? Does removal affect other rules?",
        engine9, weeks=6,
        sessions_per_week=[
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session, generate_writing_session],
            [generate_coding_session], [generate_mixed_session],
            [generate_coding_session]],
        remove_rules_schedule={
            4: ["R92"]  # Merge R92 into R91
        })

    # S10: Single-Domain Marathon (audio only for 8 weeks)
    engine10 = RuleEngine(create_seed_rules())
    run_scenario("10: Single-Domain Marathon (audio 8wk)",
        "Audio sessions exclusively for 8 weeks.\n"
        "Q: Do non-audio rules all go inactive? How many by week 8?",
        engine10, weeks=8,
        sessions_per_week=[
            [generate_audio_session], [generate_audio_session],
            [generate_audio_session, generate_audio_session],
            [generate_audio_session], [generate_audio_session],
            [generate_audio_session], [generate_audio_session],
            [generate_audio_session]])

    # S11: Graduation Effect — Remove a graduated rule from scoring
    engine11 = RuleEngine(create_seed_rules())
    run_scenario("11: Graduation Effect",
        "R84 (Permanent Locations) graduated to hook in week 3.\n"
        "Removed from scoring. Q: Does it open a budget slot for other rules?",
        engine11, weeks=5,
        sessions_per_week=[
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session]],
        remove_rules_schedule={3: ["R84"]})

    # S12: Extreme Growth — 50 new rules over 8 weeks
    engine12 = RuleEngine(create_seed_rules())
    extreme_rules = {}
    for w in range(1, 9):
        rules_this_week = []
        for i in range(6):
            idx = (w - 1) * 6 + i
            domain = ["code", "writing", "audio", "scraping", "git", "advisory"][i % 6]
            consequence = [0.1, 0.1, 0.2, 0.1, 0.2, 0.1][i % 6]
            tool = ["edit", "write", "bash", "bash", "bash", "skill"][i % 6]
            rules_this_week.append(Rule(
                f"R{400+idx}", f"Rule {400+idx} ({domain})", "practice", False,
                [domain], consequence, [tool], [],
                adaptive_spike=0.15 if idx < 12 else 0))
        extreme_rules[w] = rules_this_week

    run_scenario("12: Extreme Growth (48 new over 8wk)",
        "6 new rules/week across all domains for 8 weeks (48 total added).\n"
        "Q: Does system degrade? Budget pressure? Merge candidates?",
        engine12, weeks=8,
        sessions_per_week=[
            [generate_coding_session, generate_writing_session],
            [generate_mixed_session, generate_audio_session],
            [generate_coding_session, generate_scraping_session],
            [generate_writing_session, generate_mixed_session],
            [generate_coding_session, generate_writing_session],
            [generate_mixed_session, generate_audio_session],
            [generate_coding_session, generate_scraping_session],
            [generate_writing_session, generate_mixed_session]],
        new_rules_schedule=extreme_rules)

    # ----------------------------------------------------------
    # FINDINGS
    # ----------------------------------------------------------
    print(f"\n{'='*70}")
    print("SIMULATION v2 COMPLETE")
    print(f"{'='*70}")
    print("""
KEY QUESTIONS TO ANSWER:

1. TUNED SPIKES: Are 0.15 spikes with 0.010/day decay visible in weeks 2-3?
   (Compare S3 weeks 1-3 vs v1 where spikes were invisible)

2. IMMUNE REACTIVATION: Does R42 actually appear in activated (S4 week 3)?
   (v1 failed here — immune spike was too weak)

3. MERGE FALSE POSITIVES: Are R1+R4 still flagged as merge candidates?
   (v2 excludes 'all' domain from co-activation — should be fixed)

4. DOMAIN ISOLATION: Does rapid switching (S7) cause rules to stick?
   (Each prompt should activate only its domain's rules)

5. SPIKE STACKING: When 3 rules spike simultaneously (S8), do they
   all get budget slots or do they compete?

6. EXTREME GROWTH: At 68 rules (S12 week 8), what's the drop rate?
   (budget=5 means ~93% of eligible rules get dropped — is that OK?)

7. SINGLE-DOMAIN MARATHON: How many rules go inactive after 8 weeks
   of audio-only work? (S10)

8. GRADUATION BENEFIT: Does removing a graduated rule (S11) visibly
   open budget space for other rules?
""")


if __name__ == "__main__":
    main()
