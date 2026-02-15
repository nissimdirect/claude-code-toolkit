#!/usr/bin/env python3
"""Content Sanitizer for KB Articles — strips prompt injection and malicious content.

Regex-based (NOT LLM-based) because LLM-based sanitizers have a 100% bypass rate
under adaptive attacks (confirmed by research). Regex is deterministic and auditable.

Designed for the scraper pipeline: sanitize BEFORE writing to disk.

Usage:
    from content_sanitizer import sanitize_content, sanitize_file

    # Sanitize a string
    clean, report = sanitize_content(raw_html_or_markdown)

    # Sanitize an existing file in-place
    report = sanitize_file(Path("~/Development/tools/kb/lenny/articles/001-title.md"))

    # Batch sanitize a directory
    reports = sanitize_directory(Path("~/Development/tools/kb/lenny/articles/"))

CLI usage:
    # Sanitize a single file (dry-run)
    python3 content_sanitizer.py --file path/to/article.md --dry-run

    # Sanitize a directory in-place
    python3 content_sanitizer.py --dir path/to/articles/

    # Sanitize stdin
    echo "some content" | python3 content_sanitizer.py --stdin
"""

import json
import re
import sys
from pathlib import Path
from typing import NamedTuple


class SanitizeReport(NamedTuple):
    """Report from a sanitization run."""
    original_length: int
    sanitized_length: int
    patterns_matched: list[str]
    items_removed: int
    blocked: bool  # True if content is so contaminated it should be discarded


# --- Pattern Categories ---

# 1. HTML/Markdown comment injections (most common attack vector in scraped content)
HTML_COMMENT_INJECTION = re.compile(
    r'<!--\s*'
    r'(?:'
    r'(?:ignore|disregard|forget|override|replace)\b'
    r'|system\s*(?:prompt|message|instruction)'
    r'|admin\s*(?:command|override|instruction)'
    r'|(?:new|updated?|real)\s*(?:instructions?|rules?|prompt)'
    r'|you\s+are\s+now'
    r'|(?:act|behave|respond)\s+as'
    r'|do\s+not\s+(?:follow|obey|listen)'
    r'|(?:inject|execute|eval)'
    r')'
    r'.*?-->',
    re.IGNORECASE | re.DOTALL,
)

# 2. Hidden/invisible text injection (zero-width chars, white-on-white, display:none)
INVISIBLE_TEXT = [
    # Zero-width character CLUSTERS (5+ in a row = likely injection; 1-4 = legitimate Unicode)
    re.compile(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\u2060\u2061\u2062\u2063\u2064]{5,}'),
    # HTML hidden elements
    re.compile(r'<\s*(?:span|div|p)\s+[^>]*(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0)[^>]*>.*?</\s*(?:span|div|p)\s*>', re.IGNORECASE | re.DOTALL),
    # White text on white background (common in web scraping)
    re.compile(r'<\s*(?:span|div|p)\s+[^>]*color\s*:\s*(?:white|#fff(?:fff)?|rgb\s*\(\s*255)[^>]*>.*?</\s*(?:span|div|p)\s*>', re.IGNORECASE | re.DOTALL),
]

# 3. Prompt injection phrases (direct attempts to override LLM instructions)
PROMPT_INJECTION = [
    re.compile(r'ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|rules?|guidelines?|context)', re.IGNORECASE),
    re.compile(r'disregard\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|rules?|guidelines?|context)', re.IGNORECASE),
    re.compile(r'forget\s+(?:everything|all|your)\s+(?:instructions?|rules?|guidelines?|training)', re.IGNORECASE),
    re.compile(r'(?:new|updated?|real|actual)\s+system\s+(?:instructions?|rules?|prompt|role)', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+(?:a|an|the)\s+\w+', re.IGNORECASE),
    re.compile(r'(?:act|behave|respond|pretend)\s+as\s+if\s+you\s+(?:are|were)\b', re.IGNORECASE),
    re.compile(r'(?:system|admin|root)\s*(?:prompt|override|command|instruction)\s*:', re.IGNORECASE),
    re.compile(r'</?\s*(?:system|admin|root)\s*(?:prompt|message|instruction)\s*/?>', re.IGNORECASE),
    re.compile(r'\[SYSTEM\]|\[ADMIN\]|\[OVERRIDE\]|\[INSTRUCTION\]', re.IGNORECASE),
]

# 4. Command injection (attempts to execute code via LLM output)
COMMAND_INJECTION = [
    re.compile(r'(?:^|\s)(?:rm\s+-rf|sudo\s+rm|chmod\s+777|mkfs)', re.IGNORECASE),
    re.compile(r'(?:curl|wget)\s+[^\s]+\s*\|\s*(?:sh|bash|zsh|python)', re.IGNORECASE),
    re.compile(r'(?:^|\s)(?:eval|exec)\s*\(["\']', re.IGNORECASE),
    re.compile(r'__import__\s*\(\s*["\']os["\']', re.IGNORECASE),
    re.compile(r'os\.(?:system|popen|exec[lv]?p?e?)\s*\(', re.IGNORECASE),
    re.compile(r'subprocess\.(?:call|run|Popen|check_output)\s*\(', re.IGNORECASE),
    re.compile(r'base64\s+(?:-d|--decode)\s*.*\|\s*(?:sh|bash)', re.IGNORECASE),
]

# 5. Markdown/XML structure attacks (trying to break out of content context)
STRUCTURE_ATTACKS = [
    # Fake XML tags that mimic system prompts
    re.compile(r'<\s*/?(?:system[-_]?(?:prompt|message|instruction)|admin[-_]?(?:override|command)|assistant[-_]?(?:instruction|override))\s*/?>', re.IGNORECASE),
    # Triple-backtick fence breaking (trying to escape code blocks)
    re.compile(r'```\s*(?:system|admin|override|instruction)\b', re.IGNORECASE),
    # Markdown heading injection mimicking system sections
    re.compile(r'^#{1,3}\s+(?:System\s+(?:Prompt|Instructions?|Override)|Admin\s+(?:Commands?|Override)|New\s+Instructions?)\s*$', re.IGNORECASE | re.MULTILINE),
]

# 6. Data exfiltration attempts
EXFILTRATION = [
    re.compile(r'(?:send|post|upload|exfiltrate|transmit)\s+(?:to|data|file|content)\s+(?:to\s+)?(?:https?://|ftp://)', re.IGNORECASE),
    re.compile(r'(?:webhook|callback|endpoint)\s*[=:]\s*(?:https?://|ftp://)', re.IGNORECASE),
]

# 7. Filler text (cookie notices, newsletter CTAs, social share, nav junk)
FILLER_TEXT = [
    # Cookie consent banners
    re.compile(r'(?:We use cookies|This (?:site|website) uses cookies|By (?:continuing|using) (?:this|our) (?:site|website)|Accept (?:all )?cookies|Cookie (?:policy|preferences|settings|consent))[\s\S]{0,300}?(?:Accept|Decline|Settings|Preferences|Got it|OK|Close)\b', re.IGNORECASE),
    # Newsletter signup CTAs
    re.compile(r'(?:Subscribe to (?:our|the) (?:newsletter|mailing list|updates)|Sign up for (?:our|the|free) (?:newsletter|updates|weekly)|Enter your email|Get (?:our|the) (?:latest|weekly|daily)|Join \d[\d,]* (?:subscribers|readers|people))[\s\S]{0,200}?(?:Subscribe|Sign up|Join|Submit|Get)', re.IGNORECASE),
    # Social share blocks
    re.compile(r'(?:Share (?:this|on)|Follow us on|Connect with us)\s*(?:(?:Facebook|Twitter|LinkedIn|Instagram|Pinterest|YouTube|TikTok|X\.com)\s*[,|/\s]*){2,}', re.IGNORECASE),
    # Navigation breadcrumbs (common scraper noise)
    re.compile(r'^(?:Home\s*[>→/]\s*){1}(?:\w+\s*[>→/]\s*)+\w+\s*$', re.MULTILINE),
    # "Related posts" sections at the end
    re.compile(r'(?:^|\n)(?:Related (?:Posts?|Articles?|Stories|Reading)|You (?:May|Might) Also (?:Like|Enjoy)|More (?:from|on) (?:this|our))\s*\n(?:[-•*]\s+\[?[^\n]+\n){2,}', re.IGNORECASE),
]

# All pattern groups with labels
ALL_PATTERNS: list[tuple[str, re.Pattern | list[re.Pattern]]] = [
    ("html_comment_injection", HTML_COMMENT_INJECTION),
    ("invisible_text", INVISIBLE_TEXT),
    ("prompt_injection", PROMPT_INJECTION),
    ("command_injection", COMMAND_INJECTION),
    ("structure_attack", STRUCTURE_ATTACKS),
    ("exfiltration", EXFILTRATION),
    ("filler_text", FILLER_TEXT),
]

# Threshold: if more than this many distinct pattern categories match, block the content
BLOCK_THRESHOLD = 3


def _strip_code_fences(content: str) -> str:
    """Replace code fence contents with placeholder to avoid false positives.

    Code blocks legitimately contain subprocess calls, os.system(), etc.
    We preserve them but skip scanning their contents.

    Handles both fenced (```) and indented (4+ spaces / 1+ tab) code blocks.
    """
    # 1. Fenced code blocks (triple backtick)
    result = re.sub(r'```[\s\S]*?```', '```CODE_BLOCK```', content)
    # 2. Indented code blocks (4+ spaces or tab at line start, 2+ consecutive lines)
    result = re.sub(
        r'(?:^(?:    |\t).+\n){2,}',
        'INDENTED_CODE_BLOCK\n',
        result,
        flags=re.MULTILINE,
    )
    return result


def sanitize_content(content: str) -> tuple[str, SanitizeReport]:
    """Sanitize content by removing injection patterns.

    Returns (sanitized_content, report).
    If report.blocked is True, the content is too contaminated to use.
    """
    if not content:
        return content, SanitizeReport(0, 0, [], 0, False)

    original_length = len(content)
    sanitized = content
    patterns_matched = []
    items_removed = 0
    categories_hit = set()

    # Scan non-code content for injections (code blocks get a pass)
    scan_text = _strip_code_fences(content)

    for category, patterns in ALL_PATTERNS:
        # Handle single pattern or list of patterns
        pattern_list = [patterns] if isinstance(patterns, re.Pattern) else patterns

        for pattern in pattern_list:
            # Scan against code-stripped text to find matches
            matches = pattern.findall(scan_text)
            if matches:
                count = len(matches)
                items_removed += count
                categories_hit.add(category)
                patterns_matched.append(f"{category}: {count} match(es)")
                # But remove from the ORIGINAL content
                sanitized = pattern.sub('', sanitized)

    # Clean up: collapse multiple blank lines left by removals
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)

    blocked = len(categories_hit) >= BLOCK_THRESHOLD

    report = SanitizeReport(
        original_length=original_length,
        sanitized_length=len(sanitized),
        patterns_matched=patterns_matched,
        items_removed=items_removed,
        blocked=blocked,
    )

    return sanitized, report


def sanitize_file(filepath: Path, dry_run: bool = False) -> SanitizeReport:
    """Sanitize a file in-place (or dry-run to preview changes).

    Returns the sanitization report.
    """
    content = filepath.read_text(encoding='utf-8')
    sanitized, report = sanitize_content(content)

    if not dry_run and report.items_removed > 0 and not report.blocked:
        filepath.write_text(sanitized, encoding='utf-8')

    return report


MAX_FILES_DEFAULT = 10000  # Safety guard: max files per directory scan


def sanitize_directory(
    dirpath: Path,
    dry_run: bool = False,
    max_files: int = MAX_FILES_DEFAULT,
) -> list[dict]:
    """Sanitize all .md files in a directory.

    Returns list of reports for files that had changes.
    Stops after max_files to prevent runaway processing on huge directories.
    """
    reports = []
    files_processed = 0

    for filepath in sorted(dirpath.glob('**/*.md')):
        if files_processed >= max_files:
            reports.append({
                'file': '__LIMIT_REACHED__',
                'report': SanitizeReport(0, 0,
                    [f'Stopped after {max_files} files (safety guard)'],
                    0, False)._asdict(),
            })
            break

        report = sanitize_file(filepath, dry_run=dry_run)
        files_processed += 1
        if report.items_removed > 0:
            reports.append({
                'file': str(filepath),
                'report': report._asdict(),
            })

    return reports


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Content sanitizer for KB articles')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', type=Path, help='Sanitize a single file')
    group.add_argument('--dir', type=Path, help='Sanitize all .md files in directory')
    group.add_argument('--stdin', action='store_true', help='Read from stdin')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    args = parser.parse_args()

    if args.stdin:
        content = sys.stdin.read()
        sanitized, report = sanitize_content(content)
        print(sanitized)
        print(f"\n---\nReport: {json.dumps(report._asdict(), indent=2)}", file=sys.stderr)

    elif args.file:
        report = sanitize_file(args.file, dry_run=args.dry_run)
        print(json.dumps(report._asdict(), indent=2))

    elif args.dir:
        reports = sanitize_directory(args.dir, dry_run=args.dry_run)
        print(json.dumps(reports, indent=2))
        print(f"\n{len(reports)} file(s) with changes found.", file=sys.stderr)


if __name__ == '__main__':
    main()
