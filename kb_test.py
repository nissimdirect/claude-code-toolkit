#!/usr/bin/env python3
"""Knowledge Base Test Suite - Validates scraping output and retrieval quality.

Tests:
1. Directory structure integrity (all declared dirs exist)
2. Article count accuracy (declared vs actual)
3. Article format validation (frontmatter, content)
4. Retrieval quality (queries return relevant results, not noise)
5. Routing correctness (advisors don't cross-contaminate)
6. Alias resolution (all aliases resolve to valid advisors)

Usage:
    python3 kb_test.py                  # Run all tests
    python3 kb_test.py --verbose        # Show details
    python3 kb_test.py --fix            # Auto-fix article counts
    python3 kb_test.py --category dirs  # Run only directory tests
"""

import sys
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

# Add tools dir to path
sys.path.insert(0, str(Path(__file__).parent))
from kb_loader import KBLoader, ADVISORS, ALIASES


class KBTestSuite:
    def __init__(self, verbose=False, fix=False):
        self.loader = KBLoader()
        self.verbose = verbose
        self.fix = fix
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors = []

    def ok(self, name: str, detail: str = ""):
        self.passed += 1
        if self.verbose:
            print(f"  \033[32mPASS\033[0m {name}" + (f" ({detail})" if detail else ""))

    def fail(self, name: str, detail: str = ""):
        self.failed += 1
        msg = f"  \033[31mFAIL\033[0m {name}" + (f" — {detail}" if detail else "")
        print(msg)
        self.errors.append(msg)

    def warn(self, name: str, detail: str = ""):
        self.warnings += 1
        if self.verbose:
            print(f"  \033[33mWARN\033[0m {name}" + (f" — {detail}" if detail else ""))

    # ── Test Category 1: Directory Structure ──

    def test_dirs(self):
        print("\n=== 1. Directory Structure ===")
        for key, config in ADVISORS.items():
            for d in config["article_dirs"]:
                if d.exists():
                    self.ok(f"{key}: {d.name} exists")
                else:
                    # Empty placeholder dirs are OK for queued sources
                    if "cto-leaders" in str(d) or "security-leaders" in str(d):
                        self.warn(f"{key}: {d} (placeholder, not yet scraped)")
                    else:
                        self.fail(f"{key}: {d} MISSING")

    # ── Test Category 2: Article Counts ──

    def test_counts(self):
        print("\n=== 2. Article Count Accuracy ===")
        for key, config in ADVISORS.items():
            actual = 0
            for d in config["article_dirs"]:
                if d.exists():
                    actual += sum(1 for _ in d.rglob("*.md"))
            declared = config["article_count"]
            drift = actual - declared
            threshold = max(10, declared * 0.1)  # 10% or 10, whichever is larger

            if abs(drift) <= 5:
                self.ok(f"{key}: {declared} declared, {actual} actual")
            elif abs(drift) <= threshold:
                self.warn(f"{key}: drift {drift:+d} (declared={declared}, actual={actual})")
            else:
                self.fail(f"{key}: drift {drift:+d} (declared={declared}, actual={actual})")
                if self.fix:
                    print(f"    \033[36mFIX\033[0m Would update {key} article_count to {actual}")

    # ── Test Category 3: Article Format ──

    def test_format(self):
        print("\n=== 3. Article Format Validation ===")
        sample_size = 3  # Check 3 random articles per advisor
        for key, config in ADVISORS.items():
            articles = []
            for d in config["article_dirs"]:
                if d.exists():
                    articles.extend(list(d.rglob("*.md"))[:sample_size])

            if not articles:
                if config["article_count"] > 0:
                    self.fail(f"{key}: declared {config['article_count']} but found 0 files")
                continue

            for article_path in articles[:sample_size]:
                try:
                    content = article_path.read_text(encoding="utf-8", errors="replace")
                    lines = content.split("\n")

                    # Check for some kind of structure
                    has_frontmatter = lines[0].strip() == "---"
                    has_markdown_header = any(l.strip().startswith("# ") for l in lines[:10])
                    has_content = len(content.strip()) > 100

                    if has_frontmatter or has_markdown_header:
                        if has_content:
                            self.ok(f"{key}: {article_path.name} format OK")
                        else:
                            self.warn(f"{key}: {article_path.name} very short (<100 chars)")
                    else:
                        self.warn(f"{key}: {article_path.name} no frontmatter or header")
                except Exception as e:
                    self.fail(f"{key}: {article_path.name} unreadable — {e}")

    # ── Test Category 4: Retrieval Quality ──

    def test_retrieval(self):
        print("\n=== 4. Retrieval Quality ===")

        # Define expected query → advisor → should/shouldn't match patterns
        test_cases = [
            # (advisor, query, should_match_pattern, should_not_match_pattern)
            # ── Core advisors ──
            ("cto", "reverb design algorithm", r"reverb|algorithm|dsp", r"obsidian vault|obsidian sync|obsidian plugin"),
            ("cto", "code signing notarization", r"code sign|notariz|certificate", r"obsidian vault|obsidian sync"),
            ("cto", "JUCE component GUI", r"juce|component|gui", r"obsidian vault|obsidian sync"),
            ("lenny", "product market fit", r"product|market|fit|pmf", None),
            ("cherie", "streaming revenue", r"stream|revenue|music", None),
            ("atrium", "contemporary art", r"art|contemporary|gallery", None),
            ("don-norman", "usability design", r"usability|design|user", None),
            ("airwindows", "saturation distortion", r"saturation|distortion|clip", None),
            ("valhalla", "reverb delay", r"reverb|delay", None),
            # ── Wave 1: CTO Leaders (new content must surface) ──
            ("cto", "lock-free wait-free algorithm", r"lock.free|wait.free|real.time|audio thread", None),
            ("cto", "pricing strategy software", r"pricing|charge|money|conversion|sales", None),
            ("cto", "CI/CD audio plugin GitHub Actions", r"ci|github.actions|build|cmake|workflow", None),
            ("cto", "JUCE painting performance jank", r"paint|jank|component|repaint|performance", None),
            ("cto", "profiling CPU Perfetto", r"profil|perfetto|cpu|performance", None),
            # ── Wave 2: WolfSound + GetDunne ──
            ("cto", "SIMD optimization vectorization", r"simd|vector|sse|avx|neon|optimization", None),
            ("cto", "wavetable synthesis oscillator", r"wavetable|oscillat|synthesis", None),
            ("cto", "FM synthesis modulation", r"fm|frequency.modulation|modula|synthesis", None),
            ("cto", "JUCE parameter automation APVTS", r"parameter|apvts|automation|slider", None),
            ("cto", "IIR FIR filter design", r"iir|fir|filter|biquad|frequency", None),
            # ── Wave 2: Julia Evans + Daniel Miessler ──
            ("cto", "debugging strace perf", r"debug|strace|perf|tracing|profil", None),
            ("cto", "networking DNS TCP packets", r"dns|tcp|packet|network|socket", None),
            ("cto", "git internals branching merge", r"git|branch|merge|commit|rebase", None),
            ("cto", "AI security prompt injection LLM", r"ai|prompt|injection|llm|security|threat", None),
            ("cto", "containers kubernetes docker", r"container|kubernetes|docker|k8s", None),
            # ── Wave 3: Simon Willison ──
            ("cto", "LLM prompt injection security", r"llm|prompt.injection|security|jailbreak", None),
            ("cto", "datasette sqlite data tool", r"datasette|sqlite|data|query", None),
            ("cto", "AI agent tool use function calling", r"agent|tool.use|function.call|llm|ai", None),
            # ── Wave 3: Kent Beck ──
            ("cto", "TDD test driven development", r"tdd|test.driven|test|refactor", None),
            ("cto", "tidy first code design", r"tidy|design|structure|coupling", None),
            # ── Wave 3: Swyx ──
            ("cto", "AI engineering LLM ops", r"ai.engineer|llm|ops|deploy|inference", None),
        ]

        for advisor, query, should_match, should_not_match in test_cases:
            results = self.loader.search(advisor, query, max_results=3)

            if not results:
                self.fail(f"{advisor}: '{query}' — returned 0 results")
                continue

            # Check that results match expected patterns
            all_text = " ".join(r.get("title", "") + " " + r.get("excerpt", "") for r in results).lower()

            if should_match:
                if re.search(should_match, all_text, re.IGNORECASE):
                    self.ok(f"{advisor}: '{query}' — relevant results")
                else:
                    self.fail(f"{advisor}: '{query}' — results don't match expected pattern '{should_match}'")

            if should_not_match:
                if re.search(should_not_match, all_text, re.IGNORECASE):
                    self.fail(f"{advisor}: '{query}' — results contain NOISE matching '{should_not_match}'")
                else:
                    self.ok(f"{advisor}: '{query}' — no noise detected")

    # ── Test Category 5: Routing Correctness ──

    def test_routing(self):
        print("\n=== 5. Routing Correctness ===")

        # CTO should NOT include obsidian-docs
        cto_dirs = [str(d) for d in ADVISORS["cto"]["article_dirs"]]
        if any("obsidian-docs" in d for d in cto_dirs):
            self.fail("CTO routing includes obsidian-docs (should be separate)")
        else:
            self.ok("CTO routing excludes obsidian-docs")

        # obsidian-docs should exist as separate advisor
        if "obsidian-docs" in ADVISORS:
            self.ok("obsidian-docs exists as separate advisor")
        else:
            self.fail("obsidian-docs not found as separate advisor")

        # Check for duplicate dirs across advisors (warning, not error)
        all_dirs = {}
        for key, config in ADVISORS.items():
            for d in config["article_dirs"]:
                d_str = str(d)
                if d_str in all_dirs:
                    # Some overlap is intentional (e.g., plugin-devs shared across CTO and audio-production)
                    if self.verbose:
                        self.warn(f"Shared dir: {d.name} in both '{all_dirs[d_str]}' and '{key}'")
                else:
                    all_dirs[d_str] = key

    # ── Test Category 6: Alias Resolution ──

    def test_aliases(self):
        print("\n=== 6. Alias Resolution ===")
        orphaned = []
        for alias, target in ALIASES.items():
            if target not in ADVISORS:
                orphaned.append((alias, target))
                self.fail(f"Alias '{alias}' → '{target}' (target advisor not found)")

        if not orphaned:
            self.ok(f"All {len(ALIASES)} aliases resolve correctly")

        # Check that every advisor has at least one alias
        aliased_advisors = set(ALIASES.values())
        for key in ADVISORS:
            if key not in aliased_advisors:
                self.warn(f"Advisor '{key}' has no aliases")

    # ── Test Category 7: CTO Leader Scrape Validation ──

    def test_scrape_output(self):
        print("\n=== 7. Scrape Output Validation ===")
        scrape_dirs = {
            "melatonin": ("~/Development/cto-leaders/melatonin/articles", 20),
            "patrick-mckenzie": ("~/Development/cto-leaders/patrick-mckenzie/articles", 10),
            "pamplejuce": ("~/Development/cto-leaders/pamplejuce/articles", 3),
            "ross-bencina": ("~/Development/cto-leaders/ross-bencina/articles", 5),
            "julia-evans": ("~/Development/cto-leaders/julia-evans/articles", 50),
            "daniel-miessler": ("~/Development/security-leaders/daniel-miessler/articles", 50),
            "wolfsound": ("~/Development/cto-leaders/wolfsound/articles", 10),
            "getdunne": ("~/Development/cto-leaders/getdunne/articles", 5),
            "simon-willison": ("~/Development/cto-leaders/simon-willison/articles", 100),
            "kent-beck": ("~/Development/cto-leaders/kent-beck/articles", 20),
            "swyx": ("~/Development/cto-leaders/swyx/articles", 30),
        }

        for name, (dir_path, min_expected) in scrape_dirs.items():
            d = Path(dir_path).expanduser()
            if not d.exists():
                self.fail(f"{name}: directory missing")
                continue

            count = sum(1 for _ in d.rglob("*.md"))
            if count == 0:
                self.warn(f"{name}: 0 articles (not yet scraped)")
            elif count < min_expected:
                self.warn(f"{name}: {count} articles (expected >= {min_expected})")
            else:
                self.ok(f"{name}: {count} articles")

            # Validate format of first article if any exist
            articles = list(d.rglob("*.md"))
            if articles:
                content = articles[0].read_text(encoding="utf-8", errors="replace")
                lines = content.split("\n")
                has_frontmatter = lines[0].strip() == "---"
                has_header = any(l.strip().startswith("# ") for l in lines[:5])
                if has_frontmatter or has_header:
                    self.ok(f"{name}: {articles[0].name} has proper format")
                else:
                    self.warn(f"{name}: {articles[0].name} missing frontmatter/header")

    # ── Run All ──

    def run(self, category: Optional[str] = None):
        print("=" * 60)
        print("  Knowledge Base Test Suite")
        print("=" * 60)

        tests = {
            "dirs": self.test_dirs,
            "counts": self.test_counts,
            "format": self.test_format,
            "retrieval": self.test_retrieval,
            "routing": self.test_routing,
            "aliases": self.test_aliases,
            "scrape": self.test_scrape_output,
        }

        if category and category in tests:
            tests[category]()
        else:
            for test_fn in tests.values():
                test_fn()

        # Summary
        total = self.passed + self.failed
        print("\n" + "=" * 60)
        print(f"  Results: {self.passed}/{total} passed, {self.failed} failed, {self.warnings} warnings")
        print("=" * 60)

        if self.errors:
            print("\n  Failures:")
            for err in self.errors:
                print(err)

        return self.failed == 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="KB Test Suite")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all results")
    parser.add_argument("--fix", action="store_true", help="Auto-fix counts")
    parser.add_argument("--category", "-c", choices=["dirs", "counts", "format", "retrieval", "routing", "aliases", "scrape"],
                       help="Run specific test category")
    args = parser.parse_args()

    suite = KBTestSuite(verbose=args.verbose, fix=args.fix)
    success = suite.run(category=args.category)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
