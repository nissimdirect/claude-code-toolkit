"""
Rule Engine Simulator v3b — Fix Candidates for Budget Crowding
Tests 4 approaches to prevent universal rules from drowning domain-specific ones.
"""

from rule_engine_sim import Rule, Prompt, create_seed_rules
from copy import deepcopy

# The 8 failing test cases (all budget-drop failures)
FAILING_TESTS = [
    ("C1: code+edit → R50", Prompt("code", "edit", "editing Python"), "R50"),
    ("C2: audio+read → R42", Prompt("audio", "read", "reading DSP"), "R42"),
    ("C6: budget+bash → R75", Prompt("budget", "bash", "check budget"), "R75"),
    ("C7: scraping+bash → R8", Prompt("scraping", "bash", "run scraper"), "R8"),
    ("C-X1: audio+edit → R42", Prompt("audio", "edit", "editing DSP"), "R42"),
    ("C-X3: writing+skill → R70", Prompt("writing", "skill", "PRD review"), "R70"),
    ("S8-9: audio+edit → R42", Prompt("audio", "edit", "tuning DSP"), "R42"),
    ("S8-10: budget+bash → R75", Prompt("budget", "bash", "track resources"), "R75"),
]


class FixAEngine:
    """Fix A: Raise Practice consequence from 0.1 to 0.2"""
    THRESHOLD = 0.5
    BUDGET = 5
    NAME = "Fix A: Raise Practice consequence (0.1→0.2)"

    def __init__(self, rules):
        self.rules = {r.id: r for r in rules}
        # Boost all practices
        for r in self.rules.values():
            if r.tier == "practice" and r.consequence == 0.1:
                r.consequence = 0.2

    def score(self, rule, prompt):
        if rule.dormant:
            return 0.0
        domain_score = 0.4 if (prompt.domain in rule.domains or "all" in rule.domains) else 0.0
        consequence_score = rule.consequence
        tool_score = 0.2 if prompt.tool in rule.tool_triggers else 0.0
        spike_score = min(rule.adaptive_spike, 0.15)
        return domain_score + consequence_score + tool_score + spike_score

    def retrieve_top5(self, prompt):
        scored = [(r, self.score(r, prompt)) for r in self.rules.values()]
        scored = [(r, s) for r, s in scored if s >= self.THRESHOLD]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:self.BUDGET]


class FixBEngine:
    """Fix B: Domain affinity tiebreaker — explicit domain beats 'all' at same score"""
    THRESHOLD = 0.5
    BUDGET = 5
    NAME = "Fix B: Domain affinity tiebreaker"

    def __init__(self, rules):
        self.rules = {r.id: r for r in rules}

    def score(self, rule, prompt):
        if rule.dormant:
            return 0.0
        domain_score = 0.4 if (prompt.domain in rule.domains or "all" in rule.domains) else 0.0
        consequence_score = rule.consequence
        tool_score = 0.2 if prompt.tool in rule.tool_triggers else 0.0
        spike_score = min(rule.adaptive_spike, 0.15)
        return domain_score + consequence_score + tool_score + spike_score

    def domain_specificity(self, rule, prompt):
        """Tiebreaker: 1 if explicit domain match, 0 if 'all' match, -1 if no match"""
        if prompt.domain in rule.domains:
            return 1
        elif "all" in rule.domains:
            return 0
        return -1

    def retrieve_top5(self, prompt):
        scored = [(r, self.score(r, prompt)) for r in self.rules.values()]
        scored = [(r, s) for r, s in scored if s >= self.THRESHOLD]
        # Sort by score first, then by domain specificity as tiebreaker
        scored.sort(key=lambda x: (x[1], self.domain_specificity(x[0], prompt)), reverse=True)
        return scored[:self.BUDGET]


class FixCEngine:
    """Fix C: Reserved budget slots — 1 slot reserved for domain-specific rules"""
    THRESHOLD = 0.5
    BUDGET = 5
    RESERVED_DOMAIN_SLOTS = 1
    NAME = "Fix C: Reserved domain slot (1 of 5)"

    def __init__(self, rules):
        self.rules = {r.id: r for r in rules}

    def score(self, rule, prompt):
        if rule.dormant:
            return 0.0
        domain_score = 0.4 if (prompt.domain in rule.domains or "all" in rule.domains) else 0.0
        consequence_score = rule.consequence
        tool_score = 0.2 if prompt.tool in rule.tool_triggers else 0.0
        spike_score = min(rule.adaptive_spike, 0.15)
        return domain_score + consequence_score + tool_score + spike_score

    def retrieve_top5(self, prompt):
        scored = [(r, self.score(r, prompt)) for r in self.rules.values()]
        scored = [(r, s) for r, s in scored if s >= self.THRESHOLD]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Separate domain-specific from universal
        domain_specific = [(r, s) for r, s in scored
                          if prompt.domain in r.domains and "all" not in r.domains]
        universal = [(r, s) for r, s in scored if "all" in r.domains]
        other = [(r, s) for r, s in scored
                 if r not in [x[0] for x in domain_specific + universal]]

        # Reserve slots for domain-specific
        result = []
        reserved = domain_specific[:self.RESERVED_DOMAIN_SLOTS]
        result.extend(reserved)
        reserved_ids = {r.id for r, _ in reserved}

        # Fill remaining from all eligible (sorted by score)
        remaining = self.BUDGET - len(result)
        all_remaining = [(r, s) for r, s in scored if r.id not in reserved_ids]
        all_remaining.sort(key=lambda x: x[1], reverse=True)
        result.extend(all_remaining[:remaining])

        return result


class FixDEngine:
    """Fix D: Reduce 'all' domain match score from 0.4 to 0.3"""
    THRESHOLD = 0.5
    BUDGET = 5
    NAME = "Fix D: Reduce 'all' domain score (0.4→0.3)"

    def __init__(self, rules):
        self.rules = {r.id: r for r in rules}

    def score(self, rule, prompt):
        if rule.dormant:
            return 0.0
        if prompt.domain in rule.domains:
            domain_score = 0.4  # Explicit match: full score
        elif "all" in rule.domains:
            domain_score = 0.3  # Universal match: reduced score
        else:
            domain_score = 0.0
        consequence_score = rule.consequence
        tool_score = 0.2 if prompt.tool in rule.tool_triggers else 0.0
        spike_score = min(rule.adaptive_spike, 0.15)
        return domain_score + consequence_score + tool_score + spike_score

    def retrieve_top5(self, prompt):
        scored = [(r, self.score(r, prompt)) for r in self.rules.values()]
        scored = [(r, s) for r, s in scored if s >= self.THRESHOLD]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:self.BUDGET]


def run_fix_comparison():
    print("=" * 70)
    print("FIX COMPARISON: 4 Approaches to Budget Crowding")
    print("=" * 70)

    fixes = [
        ("Baseline (no fix)", None),
        (FixAEngine.NAME, FixAEngine),
        (FixBEngine.NAME, FixBEngine),
        (FixCEngine.NAME, FixCEngine),
        (FixDEngine.NAME, FixDEngine),
    ]

    results = {}

    for fix_name, EngineClass in fixes:
        print(f"\n{'='*70}")
        print(f"TESTING: {fix_name}")
        print(f"{'='*70}")

        passes = 0
        fails = 0

        for test_name, prompt, expected_id in FAILING_TESTS:
            if EngineClass is None:
                # Baseline — use original scoring
                rules = create_seed_rules()
                engine = FixBEngine(rules)  # Use any engine for scoring
                engine.__class__ = type('Baseline', (), {
                    'THRESHOLD': 0.5, 'BUDGET': 5,
                    'rules': {r.id: r for r in rules},
                })
                # Simple baseline
                from rule_engine_sim import RuleEngine
                engine = RuleEngine(create_seed_rules())
                activated = engine.retrieve(prompt)
                activated_ids = {r.id for r, _ in activated}
            else:
                rules = create_seed_rules()
                engine = EngineClass(rules)
                activated = engine.retrieve_top5(prompt)
                activated_ids = {r.id for r, _ in activated}

            present = expected_id in activated_ids
            status = "PASS" if present else "FAIL"
            if present:
                passes += 1
            else:
                fails += 1

            scores_detail = {r.id: f"{s:.2f}" for r, s in activated}
            print(f"  [{status}] {test_name}: {sorted(activated_ids)} {scores_detail}")

        results[fix_name] = {"pass": passes, "fail": fails}
        print(f"\n  Result: {passes}/{passes+fails} passing ({passes/(passes+fails)*100:.0f}%)")

    # ================================================================
    # SIDE EFFECT ANALYSIS
    # Do the fixes break anything that was working?
    # ================================================================
    print(f"\n{'='*70}")
    print("SIDE EFFECT ANALYSIS")
    print("Do fixes break things that were working before?")
    print(f"{'='*70}")

    # Tests that PASSED in baseline — verify they still pass
    PASSING_TESTS = [
        ("git+bash → R30+R50", Prompt("git", "bash", "git commit"),
         {"R30", "R50"}, {"R42", "R70"}),
        ("writing+write → R6+R70", Prompt("writing", "write", "write PRD"),
         {"R6", "R70"}, {"R42", "R30"}),
        ("advisory+skill → R6", Prompt("advisory", "skill", "ask advisor"),
         {"R6"}, {"R42", "R30"}),
        ("code+edit → R4 #1", Prompt("code", "edit", "edit code"),
         {"R4"}, {"R42"}),
    ]

    for fix_name, EngineClass in fixes[1:]:  # Skip baseline
        print(f"\n  {fix_name}:")
        for test_name, prompt, required, excluded in PASSING_TESTS:
            rules = create_seed_rules()
            engine = EngineClass(rules)
            activated = engine.retrieve_top5(prompt)
            activated_ids = {r.id for r, _ in activated}

            missing = required - activated_ids
            false_pos = excluded & activated_ids
            ok = len(missing) == 0 and len(false_pos) == 0
            status = "OK" if ok else "BROKEN"
            detail = ""
            if missing:
                detail += f" missing={missing}"
            if false_pos:
                detail += f" false_pos={false_pos}"
            print(f"    [{status}] {test_name}: {sorted(activated_ids)}{detail}")

    # ================================================================
    # DETAILED SCORE TABLES FOR WINNING FIX
    # ================================================================
    print(f"\n{'='*70}")
    print("DETAILED COMPARISON: Fix D (reduced 'all' score)")
    print("Showing score breakdown for the 3 hardest cases")
    print(f"{'='*70}")

    hard_cases = [
        Prompt("audio", "read", "audio+read (R42 must survive)"),
        Prompt("budget", "bash", "budget+bash (R75 must survive)"),
        Prompt("scraping", "bash", "scraping+bash (R8 must survive)"),
    ]

    for prompt in hard_cases:
        engine_d = FixDEngine(create_seed_rules())
        print(f"\n  --- {prompt.description} ---")
        scores = []
        for rule in sorted(engine_d.rules.values(), key=lambda r: r.id):
            s = engine_d.score(rule, prompt)
            if prompt.domain in rule.domains:
                dtype = "EXPLICIT"
            elif "all" in rule.domains:
                dtype = "all"
            else:
                dtype = "none"
            scores.append((rule.id, rule.name[:28], s, dtype, rule.consequence))

        scores.sort(key=lambda x: x[2], reverse=True)
        print(f"  {'ID':<6} {'Name':<30} {'Score':>6} {'DType':>9} {'Csq':>5} {'Slot':>5}")
        for i, (rid, name, s, dtype, csq) in enumerate(scores):
            slot = f"#{i+1}" if s >= 0.5 and i < 5 else ("elig" if s >= 0.5 else "-")
            marker = " <--" if s >= 0.5 and i < 5 else ""
            print(f"  {rid:<6} {name:<30} {s:>6.2f} {dtype:>9} {csq:>5.1f} {slot:>5}{marker}")

    # ================================================================
    # HYBRID FIX TEST: D + B combined
    # ================================================================
    print(f"\n{'='*70}")
    print("HYBRID FIX: D (reduced 'all' score) + B (domain tiebreaker)")
    print(f"{'='*70}")

    class FixDBEngine:
        THRESHOLD = 0.5
        BUDGET = 5
        NAME = "Fix D+B: Reduced 'all' score + domain tiebreaker"

        def __init__(self, rules):
            self.rules = {r.id: r for r in rules}

        def score(self, rule, prompt):
            if rule.dormant:
                return 0.0
            if prompt.domain in rule.domains:
                domain_score = 0.4
            elif "all" in rule.domains:
                domain_score = 0.3
            else:
                domain_score = 0.0
            consequence_score = rule.consequence
            tool_score = 0.2 if prompt.tool in rule.tool_triggers else 0.0
            spike_score = min(rule.adaptive_spike, 0.15)
            return domain_score + consequence_score + tool_score + spike_score

        def domain_specificity(self, rule, prompt):
            if prompt.domain in rule.domains:
                return 1
            elif "all" in rule.domains:
                return 0
            return -1

        def retrieve_top5(self, prompt):
            scored = [(r, self.score(r, prompt)) for r in self.rules.values()]
            scored = [(r, s) for r, s in scored if s >= self.THRESHOLD]
            scored.sort(key=lambda x: (x[1], self.domain_specificity(x[0], prompt)), reverse=True)
            return scored[:self.BUDGET]

    print("\n  Failing tests:")
    passes = 0
    for test_name, prompt, expected_id in FAILING_TESTS:
        engine = FixDBEngine(create_seed_rules())
        activated = engine.retrieve_top5(prompt)
        activated_ids = {r.id for r, _ in activated}
        present = expected_id in activated_ids
        status = "PASS" if present else "FAIL"
        if present: passes += 1
        scores_detail = {r.id: f"{s:.2f}" for r, s in activated}
        print(f"    [{status}] {test_name}: {sorted(activated_ids)}")
    print(f"  Result: {passes}/{len(FAILING_TESTS)} passing")

    print("\n  Side effects:")
    for test_name, prompt, required, excluded in PASSING_TESTS:
        engine = FixDBEngine(create_seed_rules())
        activated = engine.retrieve_top5(prompt)
        activated_ids = {r.id for r, _ in activated}
        missing = required - activated_ids
        false_pos = excluded & activated_ids
        ok = len(missing) == 0 and len(false_pos) == 0
        status = "OK" if ok else "BROKEN"
        print(f"    [{status}] {test_name}: {sorted(activated_ids)}")

    # ================================================================
    # SUMMARY
    # ================================================================
    print(f"\n{'='*70}")
    print("FINAL COMPARISON")
    print(f"{'='*70}")
    print(f"{'Fix':<50} {'Pass':>5} {'Fail':>5} {'Rate':>6}")
    print(f"{'-'*50} {'-'*5} {'-'*5} {'-'*6}")
    for name, r in results.items():
        rate = r['pass'] / (r['pass'] + r['fail']) * 100
        print(f"{name:<50} {r['pass']:>5} {r['fail']:>5} {rate:>5.0f}%")
    print(f"{'Fix D+B (hybrid)':<50} {passes:>5} {len(FAILING_TESTS)-passes:>5} {passes/len(FAILING_TESTS)*100:>5.0f}%")


if __name__ == "__main__":
    run_fix_comparison()
