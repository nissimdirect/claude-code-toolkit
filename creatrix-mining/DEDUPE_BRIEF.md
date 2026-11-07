# Creatrix ledger — semantic dedupe brief (Sonnet)

Input: one or more TSV files under ~/Development/creatrix-lessons/batches/dedupe-*.tsv
Columns: row_id \t date \t source \t type \t incident_key \t symptom

## Task
Group rows that describe the SAME failure: same component/feature AND same failure mode. Two cases count:
1. the same incident reported in several sources (a git fix + its PR + a UAT doc line + a user prompt about it);
2. the same failure RECURRING at different dates (e.g. "pop-out preview renders black" fixed in May and again in July).
Do NOT group rows that merely share an area or a vague theme ("UI bug", "test flaked"). When unsure, don't group.

## Rules (binding)
1. Read-only except your single output file. Do not edit the TSVs or anything else.
2. Copy row_ids EXACTLY (they look like `git-03.jsonl::G-74f130399f`). Never invent ids.
3. Use code for the mechanical part if helpful (e.g. a python one-liner to list rows sharing an incident_key prefix), but the grouping decision is yours.

## Output
Write a JSON array of groups (each group = array of >=2 row_ids) to the output path you are given, e.g.
[["git-03.jsonl::G-1", "docs-02.jsonl::D-x-2"], [...]]
Oracle: `python3 -c "import json,sys; g=json.load(open(sys.argv[1])); assert all(isinstance(x,list) and len(x)>1 for x in g); print(len(g))" <out>`
Also check every id you emitted appears in your input TSV(s) (grep -c).
Final message: exactly one line `DONE <name> groups=<n> rows_grouped=<m>`.
