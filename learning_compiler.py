#!/usr/bin/env python3
"""Learning Compiler — Builds keyword-indexed JSON from learnings.md

Reads the full learnings.md, extracts all documented mistakes,
deduplicates numbering, auto-extracts keywords, and outputs
a JSON index that learning_hook.py uses for dynamic injection.

Usage:
    python3 learning_compiler.py              # Build index
    python3 learning_compiler.py --stats      # Show statistics
    python3 learning_compiler.py --test       # Run self-tests
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# === PATHS ===
LEARNINGS_FILE = (
    Path.home()
    / ".claude/projects/-Users-nissimagent/memory/learnings.md"
)
PRINCIPLES_FILE = (
    Path.home()
    / ".claude/projects/-Users-nissimagent/memory/behavioral-principles.md"
)
INDEX_OUTPUT = Path.home() / ".claude/.locks/learning-index.json"

# === STOP WORDS (excluded from keyword extraction) ===
STOP_WORDS = {
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for", "of",
    "and", "or", "but", "not", "with", "from", "by", "as", "be", "was",
    "were", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must", "shall",
    "can", "need", "dare", "ought", "used", "that", "this", "these",
    "those", "i", "you", "he", "she", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "its", "our", "their", "what",
    "which", "who", "whom", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "if", "then", "else", "while", "about", "up", "out",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "again", "further", "once", "here", "there",
    "also", "don", "didn", "doesn", "isn", "wasn", "weren", "won",
    "shouldn", "couldn", "wouldn", "aren", "hasn", "haven", "hadn",
    "thing", "things", "way", "even", "still", "already", "always",
    "never", "ever", "something", "anything", "nothing", "everything",
    "make", "made", "like", "well", "back", "much", "many", "going",
    "want", "get", "got", "sure", "said", "one", "two", "first",
    "new", "now", "know", "see", "use", "using", "used",
}

# === MANUAL KEYWORD OVERRIDES ===
# For abstract/judgment learnings where auto-extraction isn't enough.
# Format: mistake_title_substring → [keywords]
MANUAL_OVERRIDES = {
    "assuming builds work": ["build", "verify", "output", "ship", "done"],
    "not reading files first": ["read", "edit", "file", "before"],
    "working from memory": ["memory", "read", "grep", "assume", "context"],
    "shipping without testing": ["ship", "test", "deploy", "launch", "done"],
    "over-engineering": ["build", "simple", "complex", "feature", "scope"],
    "scaling before testing": ["scrape", "batch", "scale", "test", "curl"],
    "not invoking actual skills": ["skill", "invoke", "lenny", "cto", "cherie", "jesse", "don-norman"],
    "delegating skill reviews": ["skill", "task", "agent", "delegate", "review", "advisor"],
    "config files as ground truth": ["config", "json", "filesystem", "scan", "data-sources"],
    "patching symptoms": ["fix", "patch", "root", "cause", "premise", "partial"],
    "stale skill name": ["skill", "rename", "merge", "propagate", "reference"],
    "documenting but not implementing": ["document", "implement", "code", "skill", "behavior"],
    "building before user testing": ["build", "test", "user", "feedback", "example", "prototype"],
    "not ending with actionable steps": ["action", "next", "step", "unblock", "end"],
    "adding ideas to prds": ["prd", "scope", "feature", "stakeholder", "idea"],
    "recursive logging": ["recursion", "memory", "log", "error", "handler", "loop"],
    "not communicating failures": ["fail", "error", "success", "report", "count", "metric"],
    "not self-documenting mistakes": ["mistake", "learning", "log", "proactive"],
    "background agent timeouts": ["agent", "background", "timeout", "web", "research"],
    "sub-agents proposing": ["agent", "sub-agent", "rebuild", "existing", "inventory"],
    "not searching all doc versions": ["search", "document", "version", "obsidian", "find"],
    "artifact types must have skill": ["artifact", "prd", "owner", "skill", "review"],
    "project indexes save": ["index", "project", "document", "read", "token"],
    "not recognizing the table signal": ["feedback", "iterate", "table", "stop", "satisfaction"],
    "solution size must match": ["engineer", "complex", "simple", "size", "approach"],
    "question your premises": ["premise", "assumption", "root", "cause", "why"],
    "losing terminal aesthetic": ["ui", "gui", "terminal", "design", "aesthetic"],
    "security audits need systematic": ["security", "audit", "enumerate", "ls", "directory"],
    "verify kills": ["kill", "process", "port", "lsof", "verify"],
    "check what the server serves": ["server", "curl", "endpoint", "verify", "live"],
    "feature freeze before deadlines": ["deadline", "freeze", "feature", "ship", "bug"],
    "shallow task surfacing": ["task", "active", "source", "index", "surface"],
    "not scoping jobs-to-be-done": ["scope", "jtbd", "job", "user", "purpose", "build"],
}

# === SKILL KEYWORDS (for skill-specific injection) ===
SKILL_KEYWORDS = {
    "forge": ["scrape", "forge", "crawl", "download", "articles"],
    "cto": ["cto", "architecture", "security", "feasibility", "technical"],
    "plugin": ["plugin", "juce", "vst", "au", "audio plugin", "daw"],
    "qa-redteam": ["red team", "security", "audit", "attack", "vulnerability"],
    "quality": ["quality", "review", "test", "verify", "ship"],
    "reflect": ["reflect", "learn", "mistake", "improve"],
    "label": ["label", "release", "catalog", "music"],
    "music-composer": ["compose", "melody", "harmony", "tracker", "dnb"],
    "glitch-video": ["glitch", "datamosh", "video", "effect", "entropic"],
    "art-director": ["art", "brand", "design", "visual", "typography"],
    "today": ["today", "plan", "session", "start"],
    "session-close": ["close", "session", "end", "commit", "wrap"],
    "ship": ["ship", "build", "deploy", "implement", "create"],
}


def parse_learnings(text: str) -> list[dict]:
    """Parse all numbered mistakes from learnings.md.

    Handles the mixed format:
    - Main "Mistakes to Never Repeat" section
    - Session-specific mistake blocks
    - Scattered mistakes throughout meta-learning sections
    """
    entries = []
    # Match: N. **Title** - Description (possibly multi-line until next numbered entry)
    # The pattern captures: number, title (bold), and the rest of the line
    pattern = re.compile(
        r'^(\d+)\.\s+\*\*(.+?)\*\*\s*[-—–:]\s*(.+)',
        re.MULTILINE,
    )

    for match in pattern.finditer(text):
        num = int(match.group(1))
        title = match.group(2).strip()
        description = match.group(3).strip()

        # Skip non-mistake numbered items (like "1. Actually Do the Work")
        # These are in the work verification checklist, not mistakes
        if title in ("Actually Do the Work", "Test It", "Validate Results",
                      "Present to User", "Get User Sign-Off"):
            continue

        # Skip session-specific composition feedback (numbered 1-10 in Session 36)
        # These are user quotes about music quality, not system mistakes
        line_start = match.start()
        preceding = text[max(0, line_start - 500):line_start]
        if "CRITICAL USER FEEDBACK" in preceding or "composition quality" in preceding:
            continue
        # Also skip by title pattern — composition feedback titles are distinctive
        composition_titles = {
            "vangelis", "tigran", "thundercat", "reese", "one-patch",
            "snippets", "bad voice leading", "tempo/key", "no space",
            "too non-diatonic",
        }
        if any(ct in title.lower() for ct in composition_titles):
            continue

        entries.append({
            "original_num": num,
            "title": title,
            "description": description,
            "full_text": f"{title}: {description}",
        })

    return entries


def deduplicate_and_renumber(entries: list[dict]) -> list[dict]:
    """Fix duplicate numbering. Option B: keep originals, only renumber dupes."""
    seen_nums = {}
    next_available = max((e["original_num"] for e in entries), default=0) + 1

    for entry in entries:
        num = entry["original_num"]
        if num not in seen_nums:
            seen_nums[num] = entry
            entry["id"] = num
        else:
            # Duplicate found — assign new unique ID
            entry["id"] = next_available
            entry["renumbered_from"] = num
            next_available += 1

    return entries


def extract_keywords(entry: dict) -> tuple[list[str], list[list[str]]]:
    """Extract keywords from a learning entry.

    Returns (exact_keywords, compound_keywords).
    Hybrid: auto-extraction + manual overrides.
    """
    text = entry["full_text"].lower()
    title_lower = entry["title"].lower()

    # === Manual overrides (highest priority) ===
    exact_from_manual = []
    for substr, keywords in MANUAL_OVERRIDES.items():
        if substr in title_lower:
            exact_from_manual.extend(keywords)

    # === Auto-extraction: significant words from title + first 100 chars of desc ===
    sample = (entry["title"] + " " + entry["description"][:150]).lower()
    words = re.findall(r'[a-z][a-z_-]+', sample)
    auto_words = [
        w for w in words
        if w not in STOP_WORDS and len(w) > 2
    ]

    # Frequency-based: keep words that appear or are domain-significant
    word_freq = Counter(auto_words)
    # Keep top 8 most frequent unique words
    top_auto = [w for w, _ in word_freq.most_common(8)]

    # === Combine ===
    exact = list(dict.fromkeys(exact_from_manual + top_auto))  # dedup, preserve order

    # === Compound keywords: extract 2-word patterns from title ===
    title_words = re.findall(r'[a-z][a-z_-]+', title_lower)
    title_words = [w for w in title_words if w not in STOP_WORDS and len(w) > 2]
    compounds = []
    for i in range(len(title_words) - 1):
        pair = [title_words[i], title_words[i + 1]]
        if pair[0] != pair[1]:
            compounds.append(pair)

    # === Add skill keywords if text mentions skills ===
    for skill, skill_kws in SKILL_KEYWORDS.items():
        if any(kw in text for kw in skill_kws):
            exact.append(skill)

    return exact[:15], compounds[:5]  # Cap sizes


def classify_type(entry: dict) -> str:
    """Classify as mechanical (can be hooked) or judgment (cannot)."""
    text = (entry["full_text"] + " " + entry.get("description", "")).lower()

    # Mechanical indicators: specific tool actions, file operations, commands
    mechanical_signals = [
        "read before", "edit without", "invoke skill", "task agent",
        "git commit", "git add", "test before", "curl", "lsof",
        "verify", "check output", "run test", "enumerate",
        "signal.sigalrm", "recursion limit", ".env", "api key",
        "hook", "permission", "register", "config",
    ]

    # Judgment indicators: abstract reasoning, user interaction
    judgment_signals = [
        "over-engineer", "scope", "premise", "assumption",
        "user satisfaction", "read between", "table signal",
        "aesthetic", "ritual", "feedback", "creative",
        "simple", "complex", "approach", "strategy",
        "not recognizing", "not communicating", "opportunity cost",
    ]

    mech_score = sum(1 for s in mechanical_signals if s in text)
    judg_score = sum(1 for s in judgment_signals if s in text)

    return "mechanical" if mech_score > judg_score else "judgment"


def detect_graduation_candidates(entry: dict, entry_type: str = None) -> bool:
    """Flag entries that could potentially become hook rules."""
    etype = entry_type or entry.get("type", "")
    if etype != "mechanical":
        return False
    text = entry["full_text"].lower()
    # Patterns that suggest automatable checks
    automatable = [
        r"always .+ before",
        r"never .+ without",
        r"must .+ first",
        r"\brule:",
        r"check .+ before",
        r"read .+ before .+ edit",
        r"test .+ before .+ ship",
        r"invoke .+ skill",
        r"verify .+ after",
        r"enumerate .+ before",
        r"git .+ before",
        r"scan .+ filesystem",
        r"never use .+ in",
    ]
    # Also check the full description, not just the short text
    full = entry.get("description", "").lower()
    combined = text + " " + full
    return any(re.search(p, combined) for p in automatable)


def load_cross_references() -> dict[int, list[str]]:
    """Load mistake→principle mappings from behavioral-principles.md."""
    xrefs = {}
    if not PRINCIPLES_FILE.exists():
        return xrefs

    text = PRINCIPLES_FILE.read_text()
    # Parse: | N | Description | P1, P2 |
    pattern = re.compile(r'\|\s*(\d+)\s*\|[^|]+\|\s*([^|]+)\|')
    for match in pattern.finditer(text):
        num = int(match.group(1))
        principles = match.group(2).strip()
        xrefs[num] = [p.strip() for p in principles.split(",") if p.strip()]

    return xrefs


def build_index() -> dict:
    """Main function: parse, deduplicate, extract keywords, build index."""
    if not LEARNINGS_FILE.exists():
        return {"error": f"File not found: {LEARNINGS_FILE}"}

    text = LEARNINGS_FILE.read_text()

    # Step 1: Parse all entries
    entries = parse_learnings(text)

    # Step 2: Deduplicate numbering
    entries = deduplicate_and_renumber(entries)

    # Step 3: Load cross-references
    xrefs = load_cross_references()

    # Step 4: Build index entries
    index_entries = []
    for entry in entries:
        exact_kw, compound_kw = extract_keywords(entry)
        entry_type = classify_type(entry)

        index_entry = {
            "id": entry["id"],
            "original_num": entry["original_num"],
            "title": entry["title"],
            "text": entry["description"][:200],  # Truncate for injection
            "keywords_exact": exact_kw,
            "keywords_compound": compound_kw,
            "confidence_threshold": 0.5,
            "type": entry_type,
            "status": "active",
            "violation_count": 0,
            "last_violated": None,
            "graduated_to": None,
            "graduation_candidate": detect_graduation_candidates(entry, entry_type),
            "inject_as": "question" if entry_type == "judgment" else "statement",
            "source_principles": xrefs.get(entry["original_num"], []),
        }

        # Renumbered entries get a note
        if "renumbered_from" in entry:
            index_entry["renumbered_from"] = entry["renumbered_from"]

        index_entries.append(index_entry)

    # Step 5: Build final index
    from datetime import datetime, timezone

    index = {
        "version": 1,
        "generated": datetime.now(timezone.utc).isoformat(),
        "source_file": str(LEARNINGS_FILE),
        "total_learnings": len(index_entries),
        "graduated_count": sum(
            1 for e in index_entries if e["status"] == "graduated"
        ),
        "graduation_candidates": sum(
            1 for e in index_entries if e["graduation_candidate"]
        ),
        "mechanical_count": sum(
            1 for e in index_entries if e["type"] == "mechanical"
        ),
        "judgment_count": sum(
            1 for e in index_entries if e["type"] == "judgment"
        ),
        "entries": index_entries,
    }

    return index


def write_index(index: dict) -> Path:
    """Write index to JSON file."""
    INDEX_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    INDEX_OUTPUT.write_text(json.dumps(index, indent=2, default=str))
    return INDEX_OUTPUT


def show_stats(index: dict):
    """Print human-readable statistics."""
    print(f"Total learnings: {index['total_learnings']}")
    print(f"  Mechanical: {index['mechanical_count']}")
    print(f"  Judgment:   {index['judgment_count']}")
    print(f"  Graduated:  {index['graduated_count']}")
    print(f"  Graduation candidates: {index['graduation_candidates']}")
    print()

    # Show duplicate renumbering
    renumbered = [e for e in index["entries"] if "renumbered_from" in e]
    if renumbered:
        print(f"Renumbered {len(renumbered)} duplicate entries:")
        for e in renumbered:
            print(f"  #{e['renumbered_from']} → #{e['id']}: {e['title'][:60]}")
        print()

    # Show graduation candidates
    candidates = [e for e in index["entries"] if e["graduation_candidate"]]
    if candidates:
        print(f"Graduation candidates ({len(candidates)}):")
        for e in candidates:
            print(f"  #{e['id']}: {e['title'][:60]}")


def run_tests():
    """Self-tests for the compiler."""
    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}")

    print("Running compiler self-tests...")
    print()

    # Test 1: Parse basic format
    sample = '1. **Test mistake** - Description here\n2. **Another one** - More desc'
    entries = parse_learnings(sample)
    check("Parse basic format", len(entries) == 2)
    check("Parse extracts title", entries[0]["title"] == "Test mistake")
    check("Parse extracts description", entries[0]["description"] == "Description here")

    # Test 2: Duplicate detection
    sample = '1. **First** - Desc1\n1. **Second** - Desc2\n2. **Third** - Desc3'
    entries = parse_learnings(sample)
    entries = deduplicate_and_renumber(entries)
    ids = [e["id"] for e in entries]
    check("Dedup: no duplicate IDs", len(ids) == len(set(ids)))
    check("Dedup: first keeps original", entries[0]["id"] == 1)
    check("Dedup: second gets new ID", entries[1]["id"] > 2)

    # Test 3: Keyword extraction
    entry = {
        "title": "Shipping without testing",
        "description": "Always test code before shipping to production",
        "full_text": "Shipping without testing: Always test code before shipping to production",
    }
    exact, compound = extract_keywords(entry)
    check("Keywords: has 'ship'", "ship" in exact or "shipping" in exact)
    check("Keywords: has 'test'", "test" in exact or "testing" in exact)

    # Test 4: Classification
    mech_entry = {
        "full_text": "Not reading files first: Read before editing, always invoke skill tool",
    }
    judg_entry = {
        "full_text": "Over-engineering: The approach was too complex and the solution was not simple enough",
    }
    check("Classify mechanical", classify_type(mech_entry) == "mechanical")
    check("Classify judgment", classify_type(judg_entry) == "judgment")

    # Test 5: Skip non-mistakes
    sample = '1. **Actually Do the Work** - Create files\n2. **Real mistake** - Bad stuff'
    entries = parse_learnings(sample)
    check("Skip non-mistakes", len(entries) == 1)
    check("Keep real mistakes", entries[0]["title"] == "Real mistake")

    # Test 6: Full pipeline on real file
    if LEARNINGS_FILE.exists():
        index = build_index()
        check("Full build succeeds", "entries" in index)
        check("Has entries", index["total_learnings"] > 50)
        check("No duplicate IDs", len(set(e["id"] for e in index["entries"])) == len(index["entries"]))
        check("All have keywords", all(len(e["keywords_exact"]) > 0 for e in index["entries"]))
        check("Classification works", index["mechanical_count"] > 0 and index["judgment_count"] > 0)
    else:
        print(f"  SKIP  Full pipeline (file not found: {LEARNINGS_FILE})")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def main():
    if "--test" in sys.argv:
        success = run_tests()
        sys.exit(0 if success else 1)

    index = build_index()

    if "error" in index:
        print(f"Error: {index['error']}", file=sys.stderr)
        sys.exit(1)

    path = write_index(index)

    if "--stats" in sys.argv:
        show_stats(index)
    else:
        print(f"Index built: {path}")
        print(f"  {index['total_learnings']} learnings indexed")
        print(f"  {index['mechanical_count']} mechanical, {index['judgment_count']} judgment")
        print(f"  {index['graduation_candidates']} graduation candidates")


if __name__ == "__main__":
    main()
