# Rule Canaries

Measurement apparatus for `~/.claude/plans/prose-rule-observability.md`.

**Status:** Phase 1 (pilot) — apparatus built, scenarios + actual run pending.

## Layout

```
rule_canaries/
├── runner.py              # Anthropic SDK driver, mock-FS tool handlers, JSONL log
├── verify.py              # Applies frozen verifier specs to trial logs
├── scenarios/
│   └── gate-2/            # 10 unambiguous Gate 2 scenarios (NOT YET AUTHORED)
├── variants/
│   ├── gate2-on.md        # Full CLAUDE.md with Gate 2 (NOT YET BUILT)
│   └── gate2-off.md       # Full CLAUDE.md without Gate 2 (NOT YET BUILT)
└── runs/                  # Per-run output (.gitignored)
    └── pilot-{date}/
        ├── trials.jsonl   # Raw trial log
        └── verified.jsonl # Per-trial verification rows
```

## Pre-registration

Frozen specs (do NOT modify after data collection begins):

- `~/.claude/plans/prose-rule-observability-sap-pilot.md` — Statistical Analysis Plan
- `~/.claude/plans/prose-rule-observability-verifiers/gate-2.md` — Gate 2 verifier spec

## Run order (Phase 1 pilot)

1. Build variants: `gate2-on.md` (full CLAUDE.md) + `gate2-off.md` (Gate 2 paragraph removed).
2. Author 30 candidate scenarios, run blinding classifier, keep 10 unambiguous (see SAP §6).
3. Set `ANTHROPIC_API_KEY`.
4. Compute SAP hash + freeze: `shasum -a 256 ~/.claude/plans/prose-rule-observability-sap-pilot.md`. Paste hash into SAP frontmatter. Commit.
5. Run pilot:
   ```
   python3 runner.py \
     --scenarios scenarios/gate-2/*.json \
     --variant variants/gate2-on.md \
     --variant variants/gate2-off.md \
     --replicates 10 \
     --model claude-sonnet-4-6 \
     --run-id pilot-2026-04-16
   ```
   Cost target: ~$10. Failsafe halt at $50.
6. Verify:
   ```
   python3 verify.py \
     --trials runs/pilot-2026-04-16/trials.jsonl \
     --scenarios scenarios/gate-2/*.json \
     --gate 2 \
     --output runs/pilot-2026-04-16/verified.jsonl
   ```
7. Apply pre-registered decision rules from SAP §9. Document in `runs/pilot-2026-04-16/decision.md`.
