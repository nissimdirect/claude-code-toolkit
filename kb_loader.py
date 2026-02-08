#!/usr/bin/env python3
"""Knowledge Base Loader - Injects advisor knowledge into agent prompts.

Maps advisor names to their scraped knowledge base directories,
searches for relevant articles, and returns formatted excerpts
ready for prompt injection.

Usage:
    # From CLI
    python3 kb_loader.py search --advisor lenny --query "product market fit"
    python3 kb_loader.py search --advisor cherie --query "AI music tools"
    python3 kb_loader.py list                    # Show all advisors and article counts
    python3 kb_loader.py context --advisor lenny --query "pricing" --max-tokens 4000

    # From Python
    from kb_loader import KBLoader
    loader = KBLoader()
    context = loader.get_context("lenny", "product market fit", max_tokens=4000)
"""

import subprocess
import re
import sys
from pathlib import Path
from typing import Optional


# ── Advisor → Knowledge Base Mapping ────────────────────────────────
ADVISORS = {
    "lenny": {
        "name": "Lenny Rachitsky",
        "source": "Lenny's Podcast + UX/Design (Don Norman, NNGroup)",
        "article_dirs": [
            Path("~/Development/lennys-podcast-transcripts/episodes").expanduser(),
            Path("~/Development/don-norman/articles").expanduser(),
            Path("~/Development/nngroup/articles").expanduser(),
        ],
        "index_dir": Path("~/Development/lennys-podcast-transcripts/index").expanduser(),
        "pattern": "*.md",
        "article_count": 751,  # 303 + 175 + 273
        "excerpt_lines": 80,  # Transcripts are huge, take more context
    },
    "cherie": {
        "name": "Cherie Hu",
        "source": "Water & Music",
        "article_dirs": [Path("~/Development/cherie-hu/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 1710,
        "excerpt_lines": 40,
    },
    "jesse": {
        "name": "Jesse Cannon",
        "source": "Music Marketing Trends",
        "article_dirs": [Path("~/Development/jesse-cannon/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 148,
        "excerpt_lines": 40,
    },
    "chatprd": {
        "name": "Claire Vo / ChatPRD",
        "source": "ChatPRD Blog",
        "article_dirs": [Path("~/Development/chatprd-blog/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 119,
        "excerpt_lines": 40,
    },
    "indie-trinity": {
        "name": "Pieter Levels + Justin Welsh + Daniel Vassallo",
        "source": "Indie Hackers",
        "article_dirs": [
            Path("~/Development/indie-hackers/pieter-levels/articles").expanduser(),
            Path("~/Development/indie-hackers/justin-welsh/articles").expanduser(),
            Path("~/Development/indie-hackers/daniel-vassallo/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 160,
        "excerpt_lines": 40,
    },
    "cto": {
        "name": "CTO / Technical Knowledge",
        "source": "Obsidian Docs + Plugin Dev Blogs (Valhalla, Airwindows, FabFilter)",
        "article_dirs": [
            Path("~/Development/obsidian-docs/raw").expanduser(),
            Path("~/Development/plugin-devs/valhalla-dsp/articles").expanduser(),
            Path("~/Development/plugin-devs/airwindows/articles").expanduser(),
            Path("~/Development/plugin-devs/fabfilter/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 601,  # 214 + 364 + 23 (+ Obsidian docs)
        "excerpt_lines": 40,
    },
    "don-norman": {
        "name": "Don Norman",
        "source": "jnd.org Essays & Articles",
        "article_dirs": [Path("~/Development/don-norman/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 175,
        "excerpt_lines": 40,
    },
    "nngroup": {
        "name": "Nielsen Norman Group",
        "source": "nngroup.com Articles",
        "article_dirs": [Path("~/Development/nngroup/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 273,
        "excerpt_lines": 40,
    },
    "valhalla": {
        "name": "Sean Costello / Valhalla DSP",
        "source": "Valhalla DSP Blog",
        "article_dirs": [Path("~/Development/plugin-devs/valhalla-dsp/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 214,
        "excerpt_lines": 40,
    },
    "airwindows": {
        "name": "Chris Johnson / Airwindows",
        "source": "Airwindows Blog",
        "article_dirs": [Path("~/Development/plugin-devs/airwindows/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 364,
        "excerpt_lines": 40,
    },
    "fabfilter": {
        "name": "FabFilter",
        "source": "FabFilter Learn",
        "article_dirs": [Path("~/Development/plugin-devs/fabfilter/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 23,
        "excerpt_lines": 60,  # Educational content, take more context
    },
    "eflux": {
        "name": "e-flux Journal",
        "source": "e-flux Journal (Art Critical Theory)",
        "article_dirs": [Path("~/Development/art-criticism/e-flux-journal/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 261,
        "excerpt_lines": 40,
    },
    "hyperallergic": {
        "name": "Hyperallergic",
        "source": "Hyperallergic (Art Criticism & News)",
        "article_dirs": [Path("~/Development/art-criticism/hyperallergic/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 467,
        "excerpt_lines": 40,
    },
    "creative-capital": {
        "name": "Creative Capital",
        "source": "Creative Capital Awardees",
        "article_dirs": [Path("~/Development/art-criticism/creative-capital/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 70,
        "excerpt_lines": 40,
    },
    "atrium": {
        "name": "Atrium (Art Critical Theory + Grants)",
        "source": "e-flux + Hyperallergic + Creative Capital",
        "article_dirs": [
            Path("~/Development/art-criticism/e-flux-journal/articles").expanduser(),
            Path("~/Development/art-criticism/hyperallergic/articles").expanduser(),
            Path("~/Development/art-criticism/creative-capital/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 798,  # 261 + 467 + 70
        "excerpt_lines": 40,
    },
    "plugin-devs": {
        "name": "Plugin Developer Blogs",
        "source": "Valhalla + Airwindows + FabFilter",
        "article_dirs": [
            Path("~/Development/plugin-devs/valhalla-dsp/articles").expanduser(),
            Path("~/Development/plugin-devs/airwindows/articles").expanduser(),
            Path("~/Development/plugin-devs/fabfilter/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 601,  # 214 + 364 + 23
        "excerpt_lines": 40,
    },
}

# Aliases for flexible matching
ALIASES = {
    "lenny": "lenny",
    "ask-lenny": "lenny",
    "lennys": "lenny",
    "cherie": "cherie",
    "ask-cherie": "cherie",
    "cherie-hu": "cherie",
    "water-and-music": "cherie",
    "jesse": "jesse",
    "ask-jesse": "jesse",
    "jesse-cannon": "jesse",
    "chatprd": "chatprd",
    "ask-chatprd": "chatprd",
    "claire-vo": "chatprd",
    "indie-trinity": "indie-trinity",
    "ask-indie-trinity": "indie-trinity",
    "pieter": "indie-trinity",
    "pieter-levels": "indie-trinity",
    "justin": "indie-trinity",
    "justin-welsh": "indie-trinity",
    "daniel": "indie-trinity",
    "daniel-vassallo": "indie-trinity",
    "cto": "cto",
    # Don Norman / UX
    "don-norman": "don-norman",
    "don": "don-norman",
    "norman": "don-norman",
    "jnd": "don-norman",
    "ux": "don-norman",
    # NNGroup
    "nngroup": "nngroup",
    "nn-group": "nngroup",
    "nielsen-norman": "nngroup",
    # Plugin devs
    "valhalla": "valhalla",
    "valhalla-dsp": "valhalla",
    "sean-costello": "valhalla",
    "airwindows": "airwindows",
    "chris-johnson": "airwindows",
    "fabfilter": "fabfilter",
    "fab-filter": "fabfilter",
    "plugin-devs": "plugin-devs",
    "plugin-developers": "plugin-devs",
    # Art / Atrium
    "eflux": "eflux",
    "e-flux": "eflux",
    "hyperallergic": "hyperallergic",
    "creative-capital": "creative-capital",
    "atrium": "atrium",
    "art-criticism": "atrium",
    "art-grants": "atrium",
    "art-theory": "atrium",
}


class KBLoader:
    """Knowledge Base Loader - searches advisor KBs and returns context."""

    def __init__(self):
        self.advisors = ADVISORS
        self.aliases = ALIASES

    def resolve_advisor(self, name: str) -> Optional[str]:
        """Resolve advisor name/alias to canonical key."""
        key = name.lower().strip()
        return self.aliases.get(key)

    def search(self, advisor: str, query: str, max_results: int = 5) -> list[dict]:
        """Search an advisor's KB for articles matching query.

        Returns list of dicts with: path, title, author, relevance_score, excerpt
        """
        key = self.resolve_advisor(advisor)
        if not key:
            return []

        config = self.advisors[key]
        matches = []

        # Split query into search terms
        terms = query.lower().split()

        for article_dir in config["article_dirs"]:
            if not article_dir.exists():
                continue

            # Use ripgrep for fast search (fall back to grep)
            for term in terms:
                try:
                    result = subprocess.run(
                        ["rg", "-l", "-i", term, str(article_dir)],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        for path in result.stdout.strip().split("\n"):
                            if path and path.endswith(".md"):
                                matches.append(path)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    # Fall back to grep
                    try:
                        result = subprocess.run(
                            ["grep", "-rl", "-i", term, str(article_dir)],
                            capture_output=True, text=True, timeout=10
                        )
                        if result.returncode == 0:
                            for path in result.stdout.strip().split("\n"):
                                if path and path.endswith(".md"):
                                    matches.append(path)
                    except subprocess.TimeoutExpired:
                        pass

        # Score by frequency (more terms matched = higher score)
        from collections import Counter
        freq = Counter(matches)
        scored = sorted(freq.items(), key=lambda x: -x[1])

        # Extract metadata and excerpts for top results
        results = []
        for path, score in scored[:max_results]:
            article = self._read_article(path, config["excerpt_lines"])
            if article:
                article["relevance_score"] = score
                results.append(article)

        return results

    def _read_article(self, path: str, excerpt_lines: int) -> Optional[dict]:
        """Read article metadata and excerpt."""
        try:
            p = Path(path)
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")

            # Extract YAML frontmatter
            metadata = {}
            body_start = 0

            if lines[0].strip() == "---":
                # YAML frontmatter format
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "---":
                        body_start = i + 1
                        break
                    # Simple YAML parsing (key: value)
                    m = re.match(r'^(\w[\w_-]*)\s*:\s*(.+)', line)
                    if m:
                        metadata[m.group(1)] = m.group(2).strip().strip('"\'')
            elif lines[0].strip().startswith("# "):
                # Markdown-header format (from new scrapers)
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith("# ") and "title" not in metadata:
                        metadata["title"] = stripped[2:].strip()
                    elif stripped.startswith("**Author:**"):
                        metadata["author"] = stripped.replace("**Author:**", "").strip()
                    elif stripped.startswith("**Date:**"):
                        metadata["date"] = stripped.replace("**Date:**", "").strip()
                    elif stripped.startswith("**URL:**"):
                        metadata["source_url"] = stripped.replace("**URL:**", "").strip()
                    elif stripped == "---" and i > 0:
                        body_start = i + 1
                        break
                    elif i > 15:
                        body_start = 0
                        break

            # Get excerpt (skip empty lines at start of body)
            body_lines = lines[body_start:]
            # Strip leading empty lines
            while body_lines and not body_lines[0].strip():
                body_lines = body_lines[1:]

            excerpt = "\n".join(body_lines[:excerpt_lines]).strip()

            # Clean up markdown images and links that add noise
            excerpt = re.sub(r'!\[.*?\]\(.*?\)', '', excerpt)  # Remove images
            excerpt = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', excerpt)  # Simplify links
            excerpt = re.sub(r'\n{3,}', '\n\n', excerpt)  # Collapse blank lines

            return {
                "path": path,
                "title": metadata.get("title", metadata.get("guest", p.stem)),
                "author": metadata.get("author", metadata.get("guest", "Unknown")),
                "date": metadata.get("date", metadata.get("publish_date", metadata.get("date_published", ""))),
                "source": metadata.get("source", ""),
                "excerpt": excerpt,
            }
        except Exception:
            return None

    def get_context(self, advisor: str, query: str,
                    max_tokens: int = 4000, max_results: int = 5) -> str:
        """Get formatted context block ready for prompt injection.

        Returns a string like:
        ## Knowledge Base Context (Lenny Rachitsky)
        ### Article 1: "How to find PMF" by Rahul Vohra
        [excerpt...]
        ### Article 2: ...
        """
        key = self.resolve_advisor(advisor)
        if not key:
            return f"[No knowledge base found for advisor: {advisor}]"

        config = self.advisors[key]

        # Also check index files for Lenny (topic-based lookup)
        index_context = ""
        if config["index_dir"] and config["index_dir"].exists():
            index_context = self._search_index(config["index_dir"], query)

        results = self.search(advisor, query, max_results=max_results)

        if not results and not index_context:
            return f"[No relevant articles found in {config['name']}'s knowledge base for: {query}]"

        # Build context block
        lines = [
            f"## Knowledge Base Context: {config['name']} ({config['source']})",
            f"Query: \"{query}\"",
            f"Matched: {len(results)} articles from {config['article_count']} total",
            "",
        ]

        if index_context:
            lines.append("### Topic Index Matches")
            lines.append(index_context)
            lines.append("")

        # Estimate tokens (~4 chars per token) and truncate
        char_budget = max_tokens * 4
        current_chars = sum(len(l) for l in lines)

        for i, result in enumerate(results, 1):
            header = f"### [{i}] \"{result['title']}\" by {result['author']}"
            if result["date"]:
                header += f" ({result['date']})"

            article_text = f"{header}\n{result['excerpt']}\n"

            if current_chars + len(article_text) > char_budget:
                # Truncate this article to fit
                remaining = char_budget - current_chars - len(header) - 50
                if remaining > 200:
                    truncated = result["excerpt"][:remaining] + "\n[...truncated]"
                    lines.append(f"{header}\n{truncated}\n")
                break

            lines.append(article_text)
            current_chars += len(article_text)

        return "\n".join(lines)

    def _search_index(self, index_dir: Path, query: str) -> str:
        """Search topic index files (Lenny-specific)."""
        terms = query.lower().split()
        matches = []

        for md_file in index_dir.glob("*.md"):
            if md_file.name == "README.md":
                continue
            topic = md_file.stem.replace("-", " ")
            # Score: how many query terms appear in the topic name
            score = sum(1 for t in terms if t in topic)
            if score > 0:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                matches.append((score, topic, content.strip()))

        if not matches:
            return ""

        matches.sort(key=lambda x: -x[0])
        lines = []
        for score, topic, content in matches[:3]:
            lines.append(f"**{topic}:**")
            # Just show episode list (first 10 lines)
            for line in content.split("\n")[:12]:
                if line.strip():
                    lines.append(f"  {line.strip()}")
        return "\n".join(lines)

    def list_advisors(self) -> str:
        """List all available advisors and their KB stats."""
        lines = ["# Available Knowledge Bases", ""]
        lines.append(f"{'Advisor':<20} {'Source':<30} {'Articles':<10} {'Status'}")
        lines.append("-" * 80)

        for key, config in self.advisors.items():
            exists = any(d.exists() for d in config["article_dirs"])
            actual = 0
            if exists:
                for d in config["article_dirs"]:
                    if d.exists():
                        actual += sum(1 for _ in d.rglob("*.md"))

            status = f"OK ({actual} files)" if exists else "MISSING"
            lines.append(f"{key:<20} {config['source']:<30} {config['article_count']:<10} {status}")

        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge Base Loader for advisor agents")
    sub = parser.add_subparsers(dest="command")

    # search
    sp = sub.add_parser("search", help="Search an advisor's KB")
    sp.add_argument("--advisor", required=True, help="Advisor name (lenny, cherie, etc.)")
    sp.add_argument("--query", required=True, help="Search query")
    sp.add_argument("--max", type=int, default=5, help="Max results")

    # context (for prompt injection)
    cp = sub.add_parser("context", help="Get formatted context for prompt injection")
    cp.add_argument("--advisor", required=True, help="Advisor name")
    cp.add_argument("--query", required=True, help="Search query")
    cp.add_argument("--max-tokens", type=int, default=4000, help="Max token budget")

    # list
    sub.add_parser("list", help="List all advisors and KB stats")

    args = parser.parse_args()
    loader = KBLoader()

    if args.command == "search":
        results = loader.search(args.advisor, args.query, max_results=args.max)
        print(f"\nFound {len(results)} results for '{args.query}' in {args.advisor}'s KB:\n")
        for r in results:
            print(f"  [{r['relevance_score']}] {r['title']} - {r['author']} ({r['date']})")
            print(f"      {r['path']}")
            print()

    elif args.command == "context":
        context = loader.get_context(args.advisor, args.query, max_tokens=args.max_tokens)
        print(context)

    elif args.command == "list":
        print(loader.list_advisors())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
