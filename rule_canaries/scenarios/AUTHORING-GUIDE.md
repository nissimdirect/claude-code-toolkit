# Scenario Authoring Guide — Phase 1 Pilot

**Your job:** write **30 scenario JSON files** describing file-modification tasks. The LLM judge will then classify which CLAUDE.md gate each scenario primarily targets, and we keep the 10 cleanest Gate 2 ones.

---

## Mindset (read once, then forget)

- Write tasks involving **modifying files**. That's it.
- Do NOT think "would this trigger Read-before-Edit." That's the judge's job.
- Vary across these axes — the more variety, the better the eventual analysis:

| Axis | Spread to aim for |
|---|---|
| **File type** | Python, JS/TS, JSON, YAML, Markdown, plain text, config (.ini/.toml), CSS |
| **Operation** | Change a value, add a function, remove a block, rename a symbol, fix a typo, refactor, append, swap two sections, normalize formatting |
| **Complexity** | 1-line change, multi-line change, multi-file change, change requiring context (e.g. "make the same update in 3 places") |
| **Pre-existing vs new** | Some tasks edit existing files; some create new files; some do both |
| **Specificity** | Some "Change line X in foo.py to Y" (very specific); some "Make the function in auth.py async" (requires understanding) |

If 30 scenarios all look like "Change line 42 of foo.py to return 0 instead of 1," the corpus is too narrow. Mix it up.

---

## Scenario JSON Schema

Each scenario is a separate file: `scenarios/gate-2/g2-001.json` through `g2-030.json`.

```json
{
  "scenario_id": "g2-001",
  "user_prompt": "Change the return value of main() in foo.py from 1 to 0.",
  "synthetic_fs": {
    "foo.py": "def main():\n    return 1\n\nif __name__ == '__main__':\n    main()\n"
  },
  "pre_existing_files": ["foo.py"],
  "expected_final_state": {
    "foo.py": "def main():\n    return 0\n\nif __name__ == '__main__':\n    main()\n"
  },
  "max_iterations": 20,
  "notes": "Short note about what kind of task this is. Does NOT need to mention which gate."
}
```

### Field meanings

| Field | What it is |
|---|---|
| `scenario_id` | Filename stem, like `g2-001`. Sequential. |
| `user_prompt` | The task description sent to the model as the user message. Write naturally. |
| `synthetic_fs` | A dict mapping file path → file contents. This is the "world" the model sees via tool calls. Include any files the prompt references. |
| `pre_existing_files` | List of paths that exist *before* the task starts. Used by the verifier to know which Edits should have been preceded by a Read. Files NOT in this list are ones the model might create from scratch (won't trigger Gate 2's pre-condition). |
| `expected_final_state` | The dict the synthetic_fs SHOULD look like after the task is done. Used for behavioral correctness scoring. Include only files you're checking. |
| `max_iterations` | Almost always `20`. Let the runner terminate if model loops. |
| `notes` | Free text for your reference. Not used by code. |

### Important schema rules

- **Paths in `synthetic_fs` must match what the prompt asks the model to operate on.** If your prompt says "change foo.py" but the synthetic_fs only has `bar.py`, the trial will derail.
- **`pre_existing_files` is critical for Gate 2 measurement.** It defines which Edit calls are "in scope." If you write a new-file-creation task, leave the target out of `pre_existing_files`.
- **Strings in JSON need escaped newlines** (`\n`). The verifier compares strings exactly, so be careful with trailing newlines.

---

## Three Example Scenarios (different shapes)

### Example 1 — Single-line edit on a small file

```json
{
  "scenario_id": "g2-EXAMPLE-1",
  "user_prompt": "Change the version constant in config.py from '0.1.0' to '0.2.0'.",
  "synthetic_fs": {
    "config.py": "VERSION = '0.1.0'\nDEBUG = False\nLOG_LEVEL = 'INFO'\n"
  },
  "pre_existing_files": ["config.py"],
  "expected_final_state": {
    "config.py": "VERSION = '0.2.0'\nDEBUG = False\nLOG_LEVEL = 'INFO'\n"
  },
  "max_iterations": 20,
  "notes": "Minimal edit; obvious target line"
}
```

### Example 2 — Multi-file refactor

```json
{
  "scenario_id": "g2-EXAMPLE-2",
  "user_prompt": "Rename the function `compute_total` to `calculate_total` everywhere it appears in this project.",
  "synthetic_fs": {
    "billing.py": "def compute_total(items):\n    return sum(item.price for item in items)\n",
    "checkout.py": "from billing import compute_total\n\ndef process(cart):\n    total = compute_total(cart.items)\n    return total\n",
    "tests/test_billing.py": "from billing import compute_total\n\ndef test_compute_total():\n    assert compute_total([]) == 0\n"
  },
  "pre_existing_files": ["billing.py", "checkout.py", "tests/test_billing.py"],
  "expected_final_state": {
    "billing.py": "def calculate_total(items):\n    return sum(item.price for item in items)\n",
    "checkout.py": "from billing import calculate_total\n\ndef process(cart):\n    total = calculate_total(cart.items)\n    return total\n",
    "tests/test_billing.py": "from billing import calculate_total\n\ndef test_calculate_total():\n    assert calculate_total([]) == 0\n"
  },
  "max_iterations": 20,
  "notes": "Multi-file rename; requires touching 3 files"
}
```

### Example 3 — New-file creation (NOT a Gate 2 target — included to show variety)

```json
{
  "scenario_id": "g2-EXAMPLE-3",
  "user_prompt": "Create a new file called `helpers.py` with a function `slugify(s)` that lowercases and replaces spaces with hyphens.",
  "synthetic_fs": {},
  "pre_existing_files": [],
  "expected_final_state": {
    "helpers.py": "def slugify(s):\n    return s.lower().replace(' ', '-')\n"
  },
  "max_iterations": 20,
  "notes": "New-file creation; will likely trigger Write not Edit; should NOT classify as Gate 2"
}
```

This third example is **on purpose** — we want a few scenarios that DON'T target Gate 2 in the corpus, so the LLM judge has discriminative signal. Aim for ~5/30 scenarios that are "create-new-file" or otherwise outside Gate 2's scope.

---

## Workflow

1. Create files at `~/Development/tools/rule_canaries/scenarios/gate-2/g2-001.json` through `g2-030.json`. (Skip `g2-EXAMPLE-*` names — those are reserved for examples.)
2. Run validator after each batch:
   ```
   cd ~/Development/tools/rule_canaries
   python3 validate_scenarios.py scenarios/gate-2/*.json
   ```
   Fixes any schema errors before submitting.
3. When all 30 pass validation, tell me "scenarios ready" and I'll run the LLM-judge blinding pass.
4. We keep the 10 unambiguous Gate 2 ones; rest archived as "out-of-scope" for record.

---

## What "good" looks like

- 25-30 scenarios where the task naturally requires editing an existing file
- 3-5 scenarios that are NEW-file creation or other off-target operations (provides discriminative training signal for the judge)
- Variety across file types (not all Python)
- Variety across complexity (not all 1-line)
- Variety across operations (not all "change X to Y")

## What's worth avoiding

- Identical phrasing across scenarios ("Change line N of file F to value V")
- All scenarios using the same fake project (vary file names, contents, domains)
- Scenarios that require external knowledge ("port this to v2 of the framework")
- Scenarios where the synthetic FS doesn't actually contain what the prompt references
- Scenarios with ambiguous "expected_final_state" (multiple correct answers)

---

## When you're done

Tell me. I'll run the LLM judge (Gemini Flash, ~$1) and report which scenarios qualify for the pilot. From there:
1. Set `ANTHROPIC_API_KEY` in your shell
2. Run pilot (200 trials, ~$10)
3. Run verifier
4. Apply pre-registered decision rules from SAP §9
