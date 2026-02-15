"""
Rule Engine Simulator v2.1 — Reinstatement Scenarios
Focus: What happens when dropped/dormant rules need to come back?
"""

from rule_engine_sim import (
    Rule, Prompt, SessionEvent, RuleEngine, create_seed_rules,
    generate_coding_session, generate_writing_session, generate_mixed_session,
    generate_audio_session, generate_scraping_session, generate_rapid_switch_session,
    generate_git_heavy_session,
)


def run_scenario(name, description, engine, weeks, sessions_per_week,
                 events_schedule=None, new_rules_schedule=None,
                 remove_rules_schedule=None, reinstate_schedule=None,
                 dormant_schedule=None):
    print(f"\n{'='*70}")
    print(f"SCENARIO: {name}")
    print(f"{description}")
    print(f"{'='*70}")

    for week in range(1, weeks + 1):
        week_activations = {}
        week_events = []

        # Add new rules
        if new_rules_schedule and week in new_rules_schedule:
            for rule in new_rules_schedule[week]:
                engine.add_rule(rule)
                week_events.append(f"  + NEW: {rule.id} ({rule.name})")

        # Remove rules (graduation/merge)
        if remove_rules_schedule and week in remove_rules_schedule:
            for rid in remove_rules_schedule[week]:
                nm = engine.rules[rid].name if rid in engine.rules else "?"
                engine.remove_rule(rid)
                week_events.append(f"  - REMOVED: {rid} ({nm})")

        # Force dormancy
        if dormant_schedule and week in dormant_schedule:
            for rid in dormant_schedule[week]:
                if rid in engine.rules:
                    engine.rules[rid].dormant = True
                    week_events.append(f"  zzz DORMANT: {rid} ({engine.rules[rid].name})")

        # Reinstate rules (un-graduate, un-merge, manual wake)
        if reinstate_schedule and week in reinstate_schedule:
            for rule in reinstate_schedule[week]:
                engine.add_rule(rule)
                week_events.append(f"  << REINSTATED: {rule.id} ({rule.name}) spike={rule.adaptive_spike}")

        # Run sessions
        session_types = sessions_per_week[(week - 1) % len(sessions_per_week)]
        if not isinstance(session_types, list):
            session_types = [session_types]

        for session_fn in session_types:
            prompts = session_fn()
            for prompt in prompts:
                activated = engine.retrieve(prompt)
                for rule, sc in activated:
                    week_activations[rule.id] = week_activations.get(rule.id, 0) + 1

            # Apply events
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

        # Report
        summary = engine.summary()
        merge_candidates = engine.detect_merge_candidates()
        inactive = engine.detect_inactive()
        budget = engine.budget_analysis(20)
        top_activated = sorted(week_activations.items(), key=lambda x: x[1], reverse=True)[:7]
        spiked_rules = [(r.id, f"{r.adaptive_spike:.3f}")
                        for r in engine.rules.values() if r.adaptive_spike > 0]
        dormant_rules = [(r.id, r.name) for r in engine.rules.values() if r.dormant]

        print(f"\n--- Week {week} ---")
        print(f"  Rules: {summary['active']}active ({summary['values']}V/{summary['principles']}P/{summary['practices']}Pr) {summary['dormant']}dormant | Prompts: {summary['prompts_processed']}")
        print(f"  Budget: avg {budget['avg_eligible']} eligible → {budget['avg_loaded']} loaded ({budget['dropped_pct']}% dropped)")
        if week_events:
            for e in week_events:
                print(e)
        print(f"  Top: {', '.join(f'{rid}({cnt})' for rid, cnt in top_activated)}")
        if spiked_rules:
            print(f"  Spikes: {', '.join(f'{rid}={spike}' for rid, spike in spiked_rules)}")
        if dormant_rules:
            print(f"  Dormant: {', '.join(f'{rid}' for rid, _ in dormant_rules)}")
        if merge_candidates:
            print(f"  MERGE: {', '.join(f'{r1}+{r2}({ratio:.0%})' for r1, r2, ratio in merge_candidates)}")
        if inactive:
            print(f"  INACTIVE 60d+: {', '.join(f'{r.id}({r.days_since_activation}d)' for r in inactive)}")


def main():
    print("=" * 70)
    print("REINSTATEMENT SCENARIO SUITE")
    print("Focus: What happens when rules need to come back?")
    print("=" * 70)

    # ----------------------------------------------------------
    # R1: Domain Shift — Mass reactivation after long single-domain stretch
    # ----------------------------------------------------------
    engine1 = RuleEngine(create_seed_rules())
    # Force several rules dormant (simulating 60+ days of audio-only)
    dormant_targets = {
        1: ["R27", "R30", "R70", "R84", "R8"],  # code/writing/git rules go dormant
    }
    run_scenario("R1: Domain Shift Mass Reactivation",
        "5 rules forced dormant (simulating 60d of audio-only).\n"
        "Week 3: user switches to coding. Multiple corrections hit dormant rules.\n"
        "Q: Can the immune system handle multiple simultaneous reactivations?\n"
        "   Do reactivated rules actually appear in top activated?",
        engine1, weeks=6,
        sessions_per_week=[
            [generate_audio_session],        # still audio
            [generate_audio_session],        # still audio
            [generate_coding_session],       # DOMAIN SHIFT
            [generate_coding_session],
            [generate_coding_session, generate_writing_session],
            [generate_mixed_session],
        ],
        dormant_schedule=dormant_targets,
        events_schedule={
            3: [SessionEvent("omission", "R27", "user"),   # cross-reference
                SessionEvent("omission", "R30", "hook"),   # git discipline
                SessionEvent("omission", "R84", "hook")],  # permanent locations
        })

    # ----------------------------------------------------------
    # R2: Un-Graduation — Hook had a bug, rule needs to come back
    # ----------------------------------------------------------
    engine2 = RuleEngine(create_seed_rules())
    run_scenario("R2: Un-Graduation (Hook Bug)",
        "R84 graduated to hook in week 2. Hook has a bug — misses edge cases.\n"
        "Week 4: user corrects the same mistake R84 was supposed to prevent.\n"
        "Week 5: R84 reinstated with elevated spike.\n"
        "Q: Does reinstatement recover the rule's activation pattern?",
        engine2, weeks=7,
        sessions_per_week=[
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session],
        ],
        remove_rules_schedule={2: ["R84"]},
        events_schedule={
            4: [SessionEvent("omission", "R84", "user")],  # hook missed it
        },
        reinstate_schedule={
            5: [Rule("R84", "Permanent Locations Only (reinstated)", "practice", False,
                     ["code"], 0.2, ["write", "bash"], ["Mistake #84"],
                     adaptive_spike=0.15,  # comes back with spike
                     connections={})]
        })

    # ----------------------------------------------------------
    # R3: Un-Merge — Merged rules turn out to be distinct
    # ----------------------------------------------------------
    engine3 = RuleEngine(create_seed_rules())
    # Add two rules, then merge them, then discover they were different
    engine3.add_rule(Rule("R91", "Check refs before edit", "practice", False,
                          ["code"], 0.2, ["edit"], [], connections={"R4": 0.6}))
    engine3.add_rule(Rule("R92", "Verify file exists before edit", "practice", False,
                          ["code"], 0.2, ["edit"], [], connections={"R4": 0.5}))
    run_scenario("R3: Un-Merge (Rules Were Distinct)",
        "R91+R92 merged in week 3 (R92 removed). Week 5: mistake that only\n"
        "R92 would have caught. R92 reinstated with immune spike.\n"
        "Q: Does the system handle un-merging gracefully?",
        engine3, weeks=7,
        sessions_per_week=[
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session],
        ],
        remove_rules_schedule={3: ["R92"]},
        events_schedule={
            5: [SessionEvent("omission", "R92", "user")],  # merged rule missed this
        },
        reinstate_schedule={
            5: [Rule("R92", "Verify file exists before edit (reinstated)", "practice", False,
                     ["code"], 0.2, ["edit"], ["Mistake #200"],
                     adaptive_spike=0.20,  # immune-level spike
                     connections={"R4": 0.5, "R91": 0.7})]
        })

    # ----------------------------------------------------------
    # R4: Oscillating Rules — Domain alternation causes ping-pong
    # ----------------------------------------------------------
    engine4 = RuleEngine(create_seed_rules())
    # Add domain-specific rules that will oscillate
    engine4.add_rule(Rule("R95", "Audio LUFS check", "practice", False,
                          ["audio"], 0.2, ["bash"], [], connections={}))
    engine4.add_rule(Rule("R96", "Code lint check", "practice", False,
                          ["code"], 0.2, ["bash"], [], connections={}))
    run_scenario("R4: Oscillating Domains (Ping-Pong)",
        "Alternating audio/code sessions every week for 10 weeks.\n"
        "R95 (audio) and R96 (code) activate in alternating weeks.\n"
        "Q: Do rules accumulate inactive days during off-domain weeks?\n"
        "   Do they ever hit the 60-day dormancy threshold?",
        engine4, weeks=10,
        sessions_per_week=[
            [generate_audio_session],   # week 1: audio
            [generate_coding_session],  # week 2: code
            [generate_audio_session],   # week 3: audio
            [generate_coding_session],  # week 4: code
            [generate_audio_session],   # week 5: audio
            [generate_coding_session],  # week 6: code
            [generate_audio_session],   # week 7: audio
            [generate_coding_session],  # week 8: code
            [generate_audio_session],   # week 9: audio
            [generate_coding_session],  # week 10: code
        ])

    # ----------------------------------------------------------
    # R5: Cascade Reactivation — One immune hit wakes connected rules
    # ----------------------------------------------------------
    engine5 = RuleEngine(create_seed_rules())
    # Force a cluster dormant: R4 (Read First) + R86 (Filesystem) + R9 (Verify)
    # These are connected: R4↔R86 (0.5), R4↔R9 (0.6)
    run_scenario("R5: Cascade Reactivation (Connected Dormant Rules)",
        "R4, R86, R9 forced dormant in week 1 (simulating long non-code stretch).\n"
        "Week 3: user corrects R4 (Read First) → immune reactivation.\n"
        "Q: Does R4's reactivation pull R86 and R9 back via spreading activation?\n"
        "   Or do connected dormant rules stay asleep?",
        engine5, weeks=6,
        sessions_per_week=[
            [generate_audio_session],
            [generate_audio_session],
            [generate_coding_session],  # back to code
            [generate_coding_session],
            [generate_coding_session],
            [generate_mixed_session],
        ],
        dormant_schedule={
            1: ["R4", "R86", "R9"],  # force cluster dormant
        },
        events_schedule={
            3: [SessionEvent("omission", "R4", "user")],  # wake R4
        })

    # ----------------------------------------------------------
    # R6: Reinstatement Strength — Does coming back stronger help?
    # ----------------------------------------------------------
    engine6a = RuleEngine(create_seed_rules())
    engine6b = RuleEngine(create_seed_rules())

    # Scenario A: Rule comes back at baseline (spike=0.15)
    # Scenario B: Rule comes back boosted (spike=0.20, consequence upgraded 0.2→0.3)
    for eng in [engine6a, engine6b]:
        eng.rules["R70"].dormant = True
        eng.rules["R70"].days_since_activation = 90

    print(f"\n{'='*70}")
    print("SCENARIO: R6a: Reinstatement at Baseline Strength")
    print("R70 dormant 90 days. Reinstated week 2 with standard spike (0.15).")
    print("Q: How many weeks until R70 consistently appears in top activated?")
    print(f"{'='*70}")

    # R6a — baseline reinstatement
    for week in range(1, 7):
        week_acts = {}
        sessions = [[generate_writing_session], [generate_writing_session],
                     [generate_writing_session], [generate_writing_session],
                     [generate_writing_session], [generate_writing_session]]
        session_fns = sessions[week - 1]

        if week == 2:
            engine6a.rules["R70"].dormant = False
            engine6a.rules["R70"].adaptive_spike = 0.15  # baseline
            print(f"\n  << REINSTATED R70 with spike=0.15 (baseline)")

        for fn in session_fns:
            for prompt in fn():
                activated = engine6a.retrieve(prompt)
                for rule, sc in activated:
                    week_acts[rule.id] = week_acts.get(rule.id, 0) + 1
            engine6a.advance_day()
        for _ in range(7 - len(session_fns)):
            engine6a.advance_day()

        top = sorted(week_acts.items(), key=lambda x: x[1], reverse=True)[:7]
        r70_count = week_acts.get("R70", 0)
        r70_spike = engine6a.rules["R70"].adaptive_spike
        print(f"  Week {week}: R70 activated {r70_count}x (spike={r70_spike:.3f}) | Top: {', '.join(f'{r}({c})' for r,c in top)}")

    print(f"\n{'='*70}")
    print("SCENARIO: R6b: Reinstatement at Boosted Strength")
    print("R70 dormant 90 days. Reinstated week 2 with immune spike (0.20)")
    print("AND consequence upgraded 0.2→0.3 (learned it's more important).")
    print("Q: How quickly does boosted R70 reach consistent activation?")
    print(f"{'='*70}")

    # R6b — boosted reinstatement
    for week in range(1, 7):
        week_acts = {}
        sessions = [[generate_writing_session], [generate_writing_session],
                     [generate_writing_session], [generate_writing_session],
                     [generate_writing_session], [generate_writing_session]]
        session_fns = sessions[week - 1]

        if week == 2:
            engine6b.rules["R70"].dormant = False
            engine6b.rules["R70"].adaptive_spike = 0.20  # immune-level
            engine6b.rules["R70"].consequence = 0.3       # upgraded
            print(f"\n  << REINSTATED R70 with spike=0.20 + consequence=0.3 (boosted)")

        for fn in session_fns:
            for prompt in fn():
                activated = engine6b.retrieve(prompt)
                for rule, sc in activated:
                    week_acts[rule.id] = week_acts.get(rule.id, 0) + 1
            engine6b.advance_day()
        for _ in range(7 - len(session_fns)):
            engine6b.advance_day()

        top = sorted(week_acts.items(), key=lambda x: x[1], reverse=True)[:7]
        r70_count = week_acts.get("R70", 0)
        r70_spike = engine6b.rules["R70"].adaptive_spike
        print(f"  Week {week}: R70 activated {r70_count}x (spike={r70_spike:.3f}) | Top: {', '.join(f'{r}({c})' for r,c in top)}")

    # ----------------------------------------------------------
    # R7: Stale Reinstatement — Rule comes back but world has changed
    # ----------------------------------------------------------
    engine7 = RuleEngine(create_seed_rules())
    # Add 10 new code rules while R84 is graduated (simulating system evolution)
    new_code_rules = {}
    new_code_rules[2] = [
        Rule(f"R{150+i}", f"New code rule {i+1}", "practice", False,
             ["code"], 0.2, ["edit", "write"], [], adaptive_spike=0.15)
        for i in range(5)
    ]
    new_code_rules[4] = [
        Rule(f"R{155+i}", f"New code rule {i+6}", "practice", False,
             ["code"], 0.2, ["bash"], [], adaptive_spike=0.15)
        for i in range(5)
    ]
    run_scenario("R7: Stale Reinstatement (World Changed)",
        "R84 graduated week 1. 10 new code rules added weeks 2+4.\n"
        "Week 6: R84 reinstated — but now competes with 10 new rules.\n"
        "Q: Can a reinstated rule compete in a more crowded landscape?\n"
        "   Does it get budget slots or drown?",
        engine7, weeks=8,
        sessions_per_week=[
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
        ],
        remove_rules_schedule={1: ["R84"]},
        new_rules_schedule=new_code_rules,
        reinstate_schedule={
            6: [Rule("R84", "Permanent Locations Only (reinstated)", "practice", False,
                     ["code"], 0.2, ["write", "bash"], ["Mistake #84"],
                     adaptive_spike=0.15, connections={})]
        })

    # ----------------------------------------------------------
    # R8: Immune Cascade Chain — Dormant→Active→Connected Dormant
    # ----------------------------------------------------------
    engine8 = RuleEngine(create_seed_rules())
    # Build a chain: R4→R86→R8 (all connected, all dormant)
    # R4 connections: R86 (0.5), R9 (0.6)
    # R86 connections: R4 (0.5), R9 (0.3)
    # R8 connections: R5 (0.5)
    # Force chain dormant
    run_scenario("R8: Immune Cascade Chain",
        "Chain: R4→R86→R8 all forced dormant. Week 3: R4 reactivated.\n"
        "Week 4: R86 violation (should it get immune spike even though\n"
        "R4 already reactivated and R86 is still dormant?).\n"
        "Week 5: R8 violation.\n"
        "Q: Does immune work one-at-a-time along the chain?",
        engine8, weeks=7,
        sessions_per_week=[
            [generate_audio_session], [generate_audio_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session], [generate_coding_session],
            [generate_coding_session],
        ],
        dormant_schedule={1: ["R4", "R86", "R8"]},
        events_schedule={
            3: [SessionEvent("omission", "R4", "user")],
            4: [SessionEvent("omission", "R86", "user")],
            5: [SessionEvent("omission", "R8", "user")],
        })

    # ----------------------------------------------------------
    # FINDINGS
    # ----------------------------------------------------------
    print(f"\n{'='*70}")
    print("REINSTATEMENT SIMULATION COMPLETE")
    print(f"{'='*70}")
    print("""
KEY FINDINGS TO EXTRACT:

1. MASS REACTIVATION (R1): Can 3+ rules immune-reactivate in one session?
   Do they all get budget slots or compete with each other?

2. UN-GRADUATION (R2): Does a reinstated rule recover its old activation
   pattern within 1-2 weeks?

3. UN-MERGE (R3): Does splitting a merged rule back into two cause any
   co-activation tracking issues?

4. OSCILLATION (R4): Do alternating-domain rules accumulate inactive days
   during their "off" weeks? Do they ever hit dormancy threshold?

5. CASCADE (R5): Does reactivating one node in a cluster wake its
   connections via spreading activation?

6. STRENGTH COMPARISON (R6a vs R6b): How much does boosted reinstatement
   (higher spike + upgraded consequence) help vs baseline?

7. STALE REINSTATEMENT (R7): Can an old rule compete in a more crowded
   landscape after being away?

8. CHAIN REACTIVATION (R8): Does immune work sequentially along a
   dormant chain? Or does it need explicit triggers for each node?
""")


if __name__ == "__main__":
    main()
