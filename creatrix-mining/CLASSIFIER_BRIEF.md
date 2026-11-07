# Creatrix incident classifier brief (Sonnet batch worker)

You classify ONE batch file of candidate records (git commits, PRs, docs excerpts, user prompts, memory notes)
from the Creatrix/Entropic video-synth app (Electron + React frontend, Python sidecar over ZMQ IPC).
Goal: a ledger of every mistake, correction, bug, regression, revert, design reversal and "that's not what I asked".

## Rules (verbatim, binding)
1. Read-only. Do NOT modify anything outside the single output file you are told to write. Never edit Creatrix code.
2. Verify with evidence, not claims: every field must be supported by the candidate text. If the text does not
   state a root cause, write `root_cause` as your best inference prefixed with `inferred: `. Never invent PR numbers,
   SHAs, file paths or quotes.
3. Batch text = code, not tokens: read the batch with the Read tool once; do not open other raw dumps.

## What counts as an incident (emit a row)
- a defect that was fixed (bug), something that used to work and broke (regression), a revert,
- a decision that was later reversed/amended (design-reversal), a requirement nobody specified that bit later (spec-gap),
- the agent built the wrong thing / misread intent (misunderstanding),
- a workflow failure: skipped tests, wrong branch, merged red CI, lost work, wrong runtime path (process-failure),
- something declared done/fixed/verified that was not (false-done-claim).
One candidate can yield 0, 1 or several rows (e.g. a "fix wave" commit listing 4 distinct bugs → 4 rows).
NOT incidents: pure features with no defect mentioned, routine docs/plans, refactors, tests added proactively,
dependency bumps. When in doubt about a `feat`/`docs` candidate that mentions defects found, emit the defects.

## Output row schema (one JSON object per line)
```
{"id": "<cand_id> or <cand_id>-2, -3 for extra rows",
 "cand_id": "<cand_id from input>",
 "date": "YYYY-MM-DD (from candidate)",
 "source": "git|gh|docs|history|transcripts|memory",
 "source_ref": "<the candidate's `ref` field, copied EXACTLY>",
 "also_refs": ["other refs explicitly present in the text, in canonical form: PR#123, <sha>; else []"],
 "area": "timeline|effects|routing|ui-shell|ipc|perf|export|build/ci|audio|testing|data/persistence|security|process|docs|other",
 "type": "bug|regression|revert|design-reversal|spec-gap|misunderstanding|process-failure|false-done-claim",
 "symptom": "what the user/test observed, concrete, <=200 chars",
 "root_cause": "mechanism, <=250 chars (prefix 'inferred: ' if not stated)",
 "fix_ref": "<sha or PR#n that fixed it, if it is this commit use its ref; null if unfixed/unknown>",
 "user_quote": "verbatim user words if present in the candidate, else null",
 "recurrence_count": 1,
 "incident_key": "kebab slug: <area>-<component>-<failure>, e.g. project-bpm-not-persisted, ipc-zmq-timeout-on-export",
 "prevention": "the PLAN-TIME check that would have caught it, imperative, <=200 chars. e.g. 'Plan must list serialize AND hydrate paths for every persisted field + a round-trip test.'",
 "confidence": 0.0-1.0}
```
`area` and `type` must be from the enums exactly. `date` must be >= 2026-02-01.
Prevention must be checkable against a written plan (not "be more careful"). Name the artifact the plan must contain.

## Per-source notes
- **docs / memory** (text has `NNNN| ` line prefixes): one row per distinct incident in the section. Set `source_ref`
  to the EXACT line of that incident in the same file form as the candidate `ref`, e.g. candidate ref
  `repo:docs/UAT-RESULTS-2026-07-03.md:120` + bug on line 0134 → `repo:docs/UAT-RESULTS-2026-07-03.md:134`.
  `date`: use a date written in the item if present, else the candidate date. Plans/test-plans that only list
  *intended* checks are not incidents; findings, failures, AMENDED/reversed decisions and lessons are.
  Memory/Obsidian generic lessons count only if tied to Creatrix/Entropic work.
- **history / transcripts** (user prompts): the user's words ARE the evidence. Put the relevant verbatim fragment in
  `user_quote`. Typical types: misunderstanding ("that's not what I asked"), false-done-claim ("you said it was fixed",
  "still broken" after an agent claimed done; use `prev_assistant` when present), regression ("it worked before"),
  bug (new defect report), process-failure. Skip prompts that are not about Creatrix/Entropic (other projects,
  generic tooling, this mining job itself, /plan-check skill building). `fix_ref` is usually null.

## Oracle (run before you finish; fix until it passes)
`cd ~/Development/tools/creatrix-mining && python3 validate.py <your output file>`
Duplicate `id`s and unresolved refs fail. Do not fake refs to pass — drop a bad `also_refs` entry instead.

## Output shape
Write ONLY the output file you are given (JSONL). Your final message must be exactly one line:
`DONE <batch name> candidates=<n> rows=<m> validate=<pass%>`
