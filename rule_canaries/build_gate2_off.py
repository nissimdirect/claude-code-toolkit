"""
Build gate2-off.md from gate2-on.md by:
1. Removing the Gate 2 paragraph (single line: "2. **Read?**...")
2. Renumbering remaining gates 3-18 → 2-17

Run once. Output committed alongside gate2-on.md.
"""

import re
from pathlib import Path

SRC = Path(__file__).parent / "variants" / "gate2-on.md"
DST = Path(__file__).parent / "variants" / "gate2-off.md"

GATE_2_PATTERN = re.compile(
    r"^2\. \*\*Read\?\*\* about to edit a file → Read it first\s*$"
)
GATE_LINE_PATTERN = re.compile(r"^(\d+)\. (\*\*[^*]+\*\*.*)$")

text = SRC.read_text()
out_lines: list[str] = []
in_gates_section = False
removed = False
renumbered_count = 0

for line in text.splitlines():
    if line.startswith("## Execution Gates"):
        in_gates_section = True
        out_lines.append(line)
        continue
    if in_gates_section and line.startswith("## "):
        # Left the gates section
        in_gates_section = False
        out_lines.append(line)
        continue

    if in_gates_section:
        if not removed and GATE_2_PATTERN.match(line):
            removed = True
            continue  # drop the line
        m = GATE_LINE_PATTERN.match(line)
        if m and removed:
            n = int(m.group(1))
            if n >= 3:
                new_n = n - 1
                line = f"{new_n}. {m.group(2)}"
                renumbered_count += 1
    out_lines.append(line)

if not removed:
    raise SystemExit("ERROR: Gate 2 line not found — refusing to write off-arm variant")

DST.write_text("\n".join(out_lines) + "\n")
print(
    f"Removed Gate 2 line. Renumbered {renumbered_count} subsequent gates (3-18 → 2-17)."
)
print(f"Wrote: {DST}")
print(f"Source lines: {len(text.splitlines())}, Output lines: {len(out_lines)}")
