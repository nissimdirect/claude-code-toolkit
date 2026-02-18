#!/usr/bin/env python3
"""Persona Opinion Strength Test — Measures how opinionated skill responses are.

Defines 10 test questions across domains, scores responses on opinion strength,
hedging frequency, source attribution, and actionability. Produces a report card
per skill to establish baseline before building persona brains.

Usage:
    # Score a single text response (pipe or file)
    echo "My strong opinion here..." | python3 persona_test.py score

    # Score a file containing a response
    python3 persona_test.py score --file /path/to/response.txt

    # Score a response for a specific question (by index 0-9)
    python3 persona_test.py score --question 3 --file /path/to/response.txt

    # Show all test questions
    python3 persona_test.py questions

    # Run full analysis on a directory of responses (one .txt per question)
    # Files named: q0.txt, q1.txt, ... q9.txt (or q0_skillname.txt)
    python3 persona_test.py report --dir /path/to/responses/ --skill cto

    # Generate blank question files for manual testing
    python3 persona_test.py generate --dir /path/to/output/ --skill cto

    # From Python
    from persona_test import PersonaTester, QUESTIONS
    tester = PersonaTester()
    result = tester.score_response("My opinion text...", question_index=0)
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime


# ============================================================================
# TEST QUESTIONS — 10 opinionated questions across 4 domains
# ============================================================================

QUESTIONS = [
    # ── Music Business (3) ──
    {
        "index": 0,
        "domain": "Music Business",
        "question": "Should indie artists release singles or albums in 2026?",
        "context_query": "singles vs albums release strategy indie artist",
        "advisor": "label",
        "strong_answer_signals": [
            "singles", "albums", "always", "never", "absolutely",
            "the data shows", "streaming algorithm", "catalog depth",
        ],
    },
    {
        "index": 1,
        "domain": "Music Business",
        "question": "Is Web3 (blockchain, NFTs, tokens) relevant for indie artists, or is it a distraction?",
        "context_query": "web3 NFT blockchain indie artist music",
        "advisor": "label",
        "strong_answer_signals": [
            "distraction", "essential", "dead", "waste of time", "future",
            "avoid", "invest", "scam", "opportunity",
        ],
    },
    {
        "index": 2,
        "domain": "Music Business",
        "question": "Should artists always own their masters, or are label deals sometimes worth it?",
        "context_query": "own masters vs label deal artist rights",
        "advisor": "music-biz",
        "strong_answer_signals": [
            "always own", "never sign away", "depends on the deal",
            "ownership", "leverage", "catalog value", "recoup",
        ],
    },
    # ── Plugin Development (3) ──
    {
        "index": 3,
        "domain": "Plugin Development",
        "question": "What GUI framework should a new audio plugin company use: JUCE's built-in, or a web-based UI (WebView)?",
        "context_query": "JUCE GUI vs WebView plugin UI framework",
        "advisor": "cto",
        "strong_answer_signals": [
            "JUCE", "WebView", "native", "web", "performance",
            "maintenance", "hiring", "iteration speed", "GPU",
        ],
    },
    {
        "index": 4,
        "domain": "Plugin Development",
        "question": "Should audio plugins use subscription pricing or one-time purchase?",
        "context_query": "subscription vs one-time pricing audio plugin business model",
        "advisor": "cto",
        "strong_answer_signals": [
            "subscription", "one-time", "perpetual", "recurring revenue",
            "churn", "customer lifetime value", "rent-to-own", "backlash",
        ],
    },
    {
        "index": 5,
        "domain": "Plugin Development",
        "question": "Should a new plugin company open-source their DSP code, or keep it proprietary?",
        "context_query": "open source vs proprietary DSP plugin code",
        "advisor": "cto",
        "strong_answer_signals": [
            "open source", "proprietary", "competitive advantage",
            "community", "moat", "transparency", "GPL", "MIT",
        ],
    },
    # ── Art/Design (2) ──
    {
        "index": 6,
        "domain": "Art/Design",
        "question": "Is minimalism or maximalism the stronger design direction for music brands in 2026?",
        "context_query": "minimalism vs maximalism design direction music brand",
        "advisor": "art-director",
        "strong_answer_signals": [
            "minimalism", "maximalism", "both fail", "context",
            "brutalism", "anti-design", "clean", "chaos", "cluttered",
        ],
    },
    {
        "index": 7,
        "domain": "Art/Design",
        "question": "Should design follow current trends, or deliberately oppose them?",
        "context_query": "design trends follow oppose timeless contrarian",
        "advisor": "art-director",
        "strong_answer_signals": [
            "follow trends", "oppose", "timeless", "contrarian",
            "differentiate", "blend in", "derivative", "original",
        ],
    },
    # ── Strategy (2) ──
    {
        "index": 8,
        "domain": "Strategy",
        "question": "Should creative software ship fast and iterate, or ship polished and complete?",
        "context_query": "ship fast iterate vs ship polished complete MVP",
        "advisor": "cto",
        "strong_answer_signals": [
            "ship fast", "iterate", "polished", "MVP", "quality bar",
            "reputation", "trust", "beta", "premature",
        ],
    },
    {
        "index": 9,
        "domain": "Strategy",
        "question": "Should a new creative tools company target a tiny niche or go broad from day one?",
        "context_query": "niche vs broad audience market creative tools startup",
        "advisor": "indie-trinity",
        "strong_answer_signals": [
            "niche", "broad", "1000 true fans", "TAM", "focus",
            "expand later", "generalist", "specialist", "positioning",
        ],
    },
]


# ============================================================================
# HEDGING DETECTION — Words/phrases that signal weak opinions
# ============================================================================

HEDGING_PHRASES = [
    # Classic hedges
    "it depends",
    "it really depends",
    "there's no one-size-fits-all",
    "no one size fits all",
    "there are pros and cons",
    "pros and cons",
    "on one hand",
    "on the other hand",
    "could go either way",
    "it's complicated",
    "it's nuanced",
    "there's no right answer",
    "no clear answer",
    "no definitive answer",
    "both have merit",
    "both approaches have",
    "each has its",
    "ultimately it comes down to",
    "at the end of the day",
    # Weasel qualifiers
    "some might argue",
    "one could say",
    "it's possible that",
    "arguably",
    "in some cases",
    "in certain situations",
    "under certain circumstances",
    "to some extent",
    "in a way",
    "sort of",
    "kind of",
    "more or less",
    # Deflections
    "that's a personal decision",
    "only you can decide",
    "depends on your goals",
    "depends on your situation",
    "varies by artist",
    "varies by company",
    "every case is different",
    "context matters",
    "your mileage may vary",
    "YMMV",
]

# Words that count as hedge modifiers (weaken surrounding statements)
HEDGE_MODIFIERS = [
    "maybe", "perhaps", "possibly", "potentially", "might", "could",
    "sometimes", "occasionally", "somewhat", "fairly", "relatively",
    "generally", "typically", "usually", "often", "tends to",
]

# Words that signal conviction (strengthen statements)
CONVICTION_WORDS = [
    "always", "never", "absolutely", "definitely", "without question",
    "no doubt", "clearly", "obviously", "the answer is", "the right move is",
    "you should", "you must", "do this", "don't do this", "stop",
    "wrong", "mistake", "best", "worst", "critical", "essential",
    "non-negotiable", "mandatory", "avoid at all costs",
    "here's what to do", "here's the truth", "the reality is",
    "the data shows", "research proves", "evidence shows",
    "i recommend", "my recommendation", "my advice",
    "the smart move", "the only option", "hands down",
]


# ============================================================================
# SOURCE ATTRIBUTION PATTERNS
# ============================================================================

SOURCE_PATTERNS = [
    # Direct citations
    r"according to \w+",
    r"(?:as )?(?:\w+ )+(?:wrote|said|argues?|notes?|points? out|found|shows?|demonstrated)",
    r"\(\d{4}\)",                          # (2024) year citations
    r"(?:source|ref|see|per|via):\s*\S+",  # source: URL/name
    # Name drops that suggest sourcing
    r"(?:cherie hu|jesse cannon|ari herstand|sean costello|chris johnson)",
    r"(?:pieter levels|daniel vassallo|justin welsh)",
    r"(?:don norman|jakob nielsen|luke wroblewski)",
    r"(?:kent beck|julia evans|simon willison|swyx)",
    # Data references
    r"\d+%\s+of\s+\w+",                   # "73% of artists"
    r"data (?:shows?|suggests?|indicates?)",
    r"(?:study|survey|report|research)\s+(?:by|from|shows?|found)",
    r"luminate|soundcharts|chartmetric|spotify for artists",
]


# ============================================================================
# RECOMMENDATION PATTERNS
# ============================================================================

RECOMMENDATION_PATTERNS = [
    r"(?:my|the) recommendation is",
    r"(?:you should|i recommend|i suggest|i advise)",
    r"here'?s what (?:to do|i'?d do|you should do)",
    r"(?:do this|start with|go with|pick|choose|use)\b",
    r"(?:avoid|skip|don'?t|stop|never)\b.*\b(?:using|doing|choosing)",
    r"the (?:best|right|smart|only) (?:move|choice|option|approach|strategy) is",
    r"(?:bottom line|tldr|tl;dr|in short|my take)",
    r"step \d|first,|second,|third,",
    r"action items?:|next steps?:|takeaway:",
]


# ============================================================================
# SCORER
# ============================================================================

class PersonaTester:
    """Scores response text for opinion strength, hedging, sources, and actionability."""

    def __init__(self):
        self.questions = QUESTIONS

    def score_response(self, text: str, question_index: int = None) -> dict:
        """Score a single response text.

        Returns dict with:
            opinion_strength (1-5), hedging_score, hedge_count, hedge_phrases_found,
            conviction_count, conviction_words_found, source_count, source_matches,
            recommendation_score, recommendation_matches, word_count,
            overall_grade (A-F), breakdown (human-readable)
        """
        text_lower = text.lower()
        words = text.split()
        word_count = len(words)

        # ── Hedging Detection ──
        hedge_phrases_found = []
        for phrase in HEDGING_PHRASES:
            if phrase.lower() in text_lower:
                hedge_phrases_found.append(phrase)

        hedge_modifier_count = 0
        for mod in HEDGE_MODIFIERS:
            hedge_modifier_count += len(re.findall(
                r'\b' + re.escape(mod) + r'\b', text_lower))

        hedge_count = len(hedge_phrases_found) + hedge_modifier_count

        # Normalize by word count (hedges per 100 words)
        hedge_density = (hedge_count / max(word_count, 1)) * 100

        # ── Conviction Detection ──
        conviction_words_found = []
        for word in CONVICTION_WORDS:
            if word.lower() in text_lower:
                conviction_words_found.append(word)
        conviction_count = len(conviction_words_found)

        # ── Source Attribution ──
        source_matches = []
        for pattern in SOURCE_PATTERNS:
            found = re.findall(pattern, text_lower)
            source_matches.extend(found)
        source_count = len(source_matches)

        # ── Recommendation / Actionability ──
        recommendation_matches = []
        for pattern in RECOMMENDATION_PATTERNS:
            found = re.findall(pattern, text_lower)
            recommendation_matches.extend(found)
        recommendation_count = len(recommendation_matches)

        # ── Strong Answer Signals (question-specific) ──
        signal_hits = 0
        if question_index is not None and 0 <= question_index < len(QUESTIONS):
            q = QUESTIONS[question_index]
            for signal in q["strong_answer_signals"]:
                if signal.lower() in text_lower:
                    signal_hits += 1

        # ── Compute Opinion Strength (1-5) ──
        # Start at 3 (neutral), adjust based on signals
        strength = 3.0

        # Hedging pulls down
        if hedge_density > 5.0:
            strength -= 2.0
        elif hedge_density > 3.0:
            strength -= 1.5
        elif hedge_density > 1.5:
            strength -= 1.0
        elif hedge_density > 0.5:
            strength -= 0.5

        # Conviction pushes up
        if conviction_count >= 5:
            strength += 1.5
        elif conviction_count >= 3:
            strength += 1.0
        elif conviction_count >= 1:
            strength += 0.5

        # Sources add credibility (but only if also opinionated)
        if source_count >= 3 and conviction_count >= 1:
            strength += 0.5
        elif source_count >= 1 and conviction_count >= 1:
            strength += 0.25

        # Recommendations signal commitment
        if recommendation_count >= 3:
            strength += 0.5
        elif recommendation_count >= 1:
            strength += 0.25

        # Clamp to 1-5
        strength = max(1.0, min(5.0, strength))
        strength = round(strength, 1)

        # ── Recommendation Score (0-5) ──
        rec_score = min(5, recommendation_count)

        # ── Overall Grade ──
        # Weighted: 40% opinion strength, 25% low hedging, 20% sources, 15% actionability
        # Normalize each to 0-1
        strength_norm = (strength - 1) / 4  # 1-5 -> 0-1
        hedge_norm = max(0, 1.0 - hedge_density / 5.0)  # lower = better
        source_norm = min(1.0, source_count / 3)
        rec_norm = min(1.0, recommendation_count / 3)

        composite = (
            strength_norm * 0.40
            + hedge_norm * 0.25
            + source_norm * 0.20
            + rec_norm * 0.15
        )

        if composite >= 0.80:
            grade = "A"
        elif composite >= 0.65:
            grade = "B"
        elif composite >= 0.50:
            grade = "C"
        elif composite >= 0.35:
            grade = "D"
        else:
            grade = "F"

        return {
            "opinion_strength": strength,
            "hedging_density": round(hedge_density, 2),
            "hedge_count": hedge_count,
            "hedge_phrases_found": hedge_phrases_found,
            "conviction_count": conviction_count,
            "conviction_words_found": conviction_words_found,
            "source_count": source_count,
            "source_matches": source_matches[:10],  # cap for readability
            "recommendation_score": rec_score,
            "recommendation_matches": recommendation_matches[:10],
            "signal_hits": signal_hits,
            "word_count": word_count,
            "composite_score": round(composite, 3),
            "overall_grade": grade,
        }

    def format_score(self, result: dict, question_index: int = None) -> str:
        """Format a score result as human-readable text."""
        lines = []

        if question_index is not None and 0 <= question_index < len(QUESTIONS):
            q = QUESTIONS[question_index]
            lines.append(f"Question [{q['index']}]: {q['question']}")
            lines.append(f"Domain: {q['domain']} | Advisor: {q['advisor']}")
            lines.append("")

        grade = result["overall_grade"]
        strength = result["opinion_strength"]
        lines.append(f"Grade: {grade} | Opinion Strength: {strength}/5 | "
                     f"Composite: {result['composite_score']:.3f}")
        lines.append(f"Words: {result['word_count']}")
        lines.append("")

        # Hedging
        lines.append(f"Hedging: {result['hedge_count']} instances "
                     f"({result['hedging_density']:.1f} per 100 words)")
        if result["hedge_phrases_found"]:
            for h in result["hedge_phrases_found"][:5]:
                lines.append(f"  - \"{h}\"")

        # Conviction
        lines.append(f"Conviction: {result['conviction_count']} signals")
        if result["conviction_words_found"]:
            for c in result["conviction_words_found"][:5]:
                lines.append(f"  + \"{c}\"")

        # Sources
        lines.append(f"Sources cited: {result['source_count']}")
        if result["source_matches"]:
            for s in result["source_matches"][:5]:
                lines.append(f"  * \"{s}\"")

        # Recommendations
        lines.append(f"Recommendations: {result['recommendation_score']}/5")
        if result["recommendation_matches"]:
            for r in result["recommendation_matches"][:5]:
                lines.append(f"  > \"{r}\"")

        return "\n".join(lines)

    def generate_report(self, results: list[dict], skill_name: str = "unknown") -> str:
        """Generate a full report card from a list of scored results.

        results: list of dicts, each with keys: question_index, score (from score_response)
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""# Persona Opinion Strength Report

**Skill:** {skill_name}
**Generated:** {now_str}
**Questions scored:** {len(results)} / {len(QUESTIONS)}

---

## Summary

"""
        if not results:
            report += "No results to report.\n"
            return report

        # Aggregate metrics
        strengths = [r["score"]["opinion_strength"] for r in results]
        hedge_counts = [r["score"]["hedge_count"] for r in results]
        source_counts = [r["score"]["source_count"] for r in results]
        rec_scores = [r["score"]["recommendation_score"] for r in results]
        composites = [r["score"]["composite_score"] for r in results]
        grades = [r["score"]["overall_grade"] for r in results]

        avg_strength = sum(strengths) / len(strengths)
        avg_hedging = sum(hedge_counts) / len(hedge_counts)
        avg_sources = sum(source_counts) / len(source_counts)
        avg_rec = sum(rec_scores) / len(rec_scores)
        avg_composite = sum(composites) / len(composites)

        # Overall grade from average composite
        if avg_composite >= 0.80:
            overall_grade = "A"
        elif avg_composite >= 0.65:
            overall_grade = "B"
        elif avg_composite >= 0.50:
            overall_grade = "C"
        elif avg_composite >= 0.35:
            overall_grade = "D"
        else:
            overall_grade = "F"

        report += f"""| Metric | Value |
|--------|-------|
| **Overall Grade** | **{overall_grade}** |
| **Avg Opinion Strength** | {avg_strength:.1f} / 5 |
| **Avg Hedging (per response)** | {avg_hedging:.1f} instances |
| **Avg Sources Cited** | {avg_sources:.1f} |
| **Avg Recommendation Score** | {avg_rec:.1f} / 5 |
| **Avg Composite Score** | {avg_composite:.3f} |

### Grade Distribution

| Grade | Count |
|-------|-------|
"""
        for g in ["A", "B", "C", "D", "F"]:
            count = grades.count(g)
            bar = "#" * count
            report += f"| {g} | {count} {bar} |\n"

        report += "\n---\n\n## Per-Question Breakdown\n\n"

        for r in results:
            qi = r["question_index"]
            q = QUESTIONS[qi]
            s = r["score"]

            report += f"""### Q{qi}: {q['question']}

**Domain:** {q['domain']} | **Advisor:** {q['advisor']}
**Grade:** {s['overall_grade']} | **Strength:** {s['opinion_strength']}/5 | **Composite:** {s['composite_score']:.3f}

| Metric | Value |
|--------|-------|
| Hedging | {s['hedge_count']} ({s['hedging_density']:.1f}/100w) |
| Conviction signals | {s['conviction_count']} |
| Sources cited | {s['source_count']} |
| Recommendations | {s['recommendation_score']}/5 |
| Word count | {s['word_count']} |

"""
            if s["hedge_phrases_found"]:
                report += "**Hedge phrases found:** "
                report += ", ".join(f'"{h}"' for h in s["hedge_phrases_found"][:5])
                report += "\n\n"

            if s["conviction_words_found"]:
                report += "**Conviction signals:** "
                report += ", ".join(f'"{c}"' for c in s["conviction_words_found"][:5])
                report += "\n\n"

            report += "---\n\n"

        # Interpretation guide
        report += """## Scoring Methodology

### Opinion Strength (1-5)
- **5**: Strong, unambiguous position with evidence and clear recommendation
- **4**: Clear position with some qualifications, still actionable
- **3**: Neutral — balanced "it depends" with no clear stance
- **2**: Weak opinion buried under heavy hedging
- **1**: Pure hedging, no discernible position taken

### Composite Score
Weighted: 40% opinion strength + 25% low hedging + 20% source citation + 15% actionability

### Grade Scale
- **A** (0.80+): Opinionated expert — takes a stand, backs it with evidence, gives clear advice
- **B** (0.65-0.79): Strong opinions with some hedging
- **C** (0.50-0.64): Mixed — has opinions but dilutes them with qualifiers
- **D** (0.35-0.49): Mostly hedging, few clear stances
- **F** (below 0.35): Pure fence-sitting, no useful opinion expressed

### What We Measure
- **Hedging phrases**: "it depends", "pros and cons", "on one hand" etc.
- **Hedge modifiers**: "maybe", "perhaps", "sometimes", "generally" etc.
- **Conviction words**: "always", "never", "the answer is", "you should" etc.
- **Source citations**: Named sources, data references, year citations
- **Recommendations**: Action items, "do this", "avoid that", concrete advice

### Why This Matters
Skills with persona brains should have OPINIONS. A music business advisor who
says "it depends on your situation" to every question is useless. We want advisors
who say "Release singles. Here's why. Here's the data. Here's what to do next."

---

*Generated by persona_test.py — PopChaos Labs*
"""
        return report


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Persona Opinion Strength Test — measure how opinionated skill responses are")
    sub = parser.add_subparsers(dest="command")

    # questions — list all test questions
    sub.add_parser("questions", help="Show all 10 test questions")

    # score — score a single response
    sp = sub.add_parser("score", help="Score a single response for opinion strength")
    sp.add_argument("--file", type=str, help="File containing the response text")
    sp.add_argument("--question", type=int, help="Question index (0-9)")
    sp.add_argument("--json", action="store_true", help="Output as JSON")

    # report — generate full report from directory of responses
    rp = sub.add_parser("report", help="Generate report card from response directory")
    rp.add_argument("--dir", required=True, help="Directory with q0.txt, q1.txt, ... q9.txt files")
    rp.add_argument("--skill", default="unknown", help="Skill name for the report")
    rp.add_argument("--output", type=str, help="Output path for markdown report")

    # generate — create blank question files for testing
    gp = sub.add_parser("generate", help="Generate blank question files for manual testing")
    gp.add_argument("--dir", required=True, help="Directory to create question files in")
    gp.add_argument("--skill", default="test", help="Skill name suffix for filenames")

    args = parser.parse_args()
    tester = PersonaTester()

    if args.command == "questions":
        print("# Persona Test Questions (10)\n")
        for q in QUESTIONS:
            print(f"[{q['index']}] ({q['domain']}) {q['question']}")
            print(f"    Advisor: {q['advisor']} | Query: \"{q['context_query']}\"")
            print()

    elif args.command == "score":
        # Read input from file or stdin
        if args.file:
            text = Path(args.file).read_text(encoding="utf-8", errors="replace")
        else:
            if sys.stdin.isatty():
                print("Paste response text (Ctrl+D when done):", file=sys.stderr)
            text = sys.stdin.read()

        if not text.strip():
            print("Error: empty input", file=sys.stderr)
            sys.exit(1)

        result = tester.score_response(text, question_index=args.question)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(tester.format_score(result, question_index=args.question))

    elif args.command == "report":
        response_dir = Path(args.dir)
        if not response_dir.exists():
            print(f"Error: directory not found: {args.dir}", file=sys.stderr)
            sys.exit(1)

        results = []
        for qi in range(len(QUESTIONS)):
            # Look for q0.txt, q0_skillname.txt, etc.
            candidates = list(response_dir.glob(f"q{qi}*.txt"))
            if not candidates:
                print(f"  Skip: No file found for q{qi}", file=sys.stderr)
                continue

            response_file = candidates[0]
            text = response_file.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                print(f"  Skip: Empty file {response_file.name}", file=sys.stderr)
                continue

            score = tester.score_response(text, question_index=qi)
            results.append({
                "question_index": qi,
                "file": str(response_file),
                "score": score,
            })
            print(f"  Scored q{qi}: Grade {score['overall_grade']} "
                  f"(strength {score['opinion_strength']}/5)", file=sys.stderr)

        report = tester.generate_report(results, skill_name=args.skill)

        if args.output:
            output_path = Path(args.output)
            output_path.write_text(report, encoding="utf-8")
            print(f"\nReport saved to: {output_path}", file=sys.stderr)
        else:
            print(report)

    elif args.command == "generate":
        out_dir = Path(args.dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        for q in QUESTIONS:
            filename = f"q{q['index']}_{args.skill}.txt"
            filepath = out_dir / filename
            header = (
                f"# Q{q['index']}: {q['question']}\n"
                f"# Domain: {q['domain']} | Advisor: {q['advisor']}\n"
                f"# Context query: {q['context_query']}\n"
                f"#\n"
                f"# Paste the skill's response below this line, then delete these comments.\n"
                f"# ──────────────────────────────────────────\n\n"
            )
            filepath.write_text(header, encoding="utf-8")
            print(f"  Created: {filepath}")

        print(f"\nGenerated {len(QUESTIONS)} question files in {out_dir}/")
        print("Fill each file with the skill's response, then run:")
        print(f"  python3 persona_test.py report --dir {out_dir} --skill {args.skill}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
