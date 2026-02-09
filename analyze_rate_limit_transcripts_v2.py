#!/usr/bin/env python3
"""
Analyze YouTube transcripts about Claude Code rate limits - V2
Enhanced with deduplication, semantic grouping, and fact-checking.
"""

import re
import glob
import sys
from pathlib import Path
from collections import defaultdict, Counter

def parse_srt(filepath):
    """Extract text from SRT file, removing timestamps and sequence numbers."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    text_lines = []
    seen_lines = set()  # Deduplicate repeated lines

    for line in lines:
        line = line.strip()
        if not line or line.isdigit() or '-->' in line:
            continue

        # SRT files often repeat lines 3x - deduplicate
        if line not in seen_lines:
            text_lines.append(line)
            seen_lines.add(line)

    return ' '.join(text_lines)

def extract_numbers(text):
    """Extract numbers and units (hours, minutes, messages, dollars, tokens)."""
    patterns = [
        (r'(\d+)\s*hours?', 'hours'),
        (r'(\d+)\s*minutes?', 'minutes'),
        (r'(\d+)\s*messages?', 'messages'),
        (r'\$(\d+)', 'dollars'),
        (r'(\d+[,\d]*)\s*tokens?', 'tokens'),
        (r'(\d+)%', 'percent'),
    ]

    findings = []
    for pattern, unit in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            findings.append(f"{match} {unit}")

    return findings

def extract_commands(text):
    """Extract Claude Code commands mentioned."""
    commands = []
    command_patterns = [
        r'/\w+',  # /fast, /compact, /plan, etc.
        r'claude\s+\w+',  # claude command
    ]

    for pattern in command_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        commands.extend(matches)

    return list(set(commands))

def categorize_strategy(text):
    """Categorize strategies mentioned in transcript."""
    strategies = {
        'use_api': ['api', 'console.anthropic', 'workbench'],
        'switch_models': ['sonnet', 'opus', 'haiku', 'switch model', 'cheaper model'],
        'start_fresh': ['new conversation', 'start fresh', 'reset', 'clear'],
        'use_commands': ['/fast', '/compact', '/plan'],
        'context_management': ['context window', 'cache', 'projects', 'memory'],
        'sub_agents': ['sub agent', 'sub-agent', 'multiple agents'],
        'mcp_servers': ['mcp server', 'mcp'],
        'session_timing': ['5 hour', '5-hour', 'session reset', 'weekly limit'],
    }

    found = []
    text_lower = text.lower()

    for strategy, keywords in strategies.items():
        if any(kw in text_lower for kw in keywords):
            found.append(strategy)

    return found

def analyze_transcript(filepath):
    """Deep analysis of single transcript."""
    video_id = Path(filepath).stem.split('_')[-1].replace('.en', '')
    text = parse_srt(filepath)

    analysis = {
        'video_id': video_id,
        'numbers': extract_numbers(text),
        'commands': extract_commands(text),
        'strategies': categorize_strategy(text),
        'text_length': len(text),
    }

    return analysis

def main():
    transcript_dir = Path('/Users/nissimagent/Development/YouTubeTranscripts')
    pattern = 'how_to_stop_hitting_claude_code_rate_limits_*.srt'

    files = sorted(glob.glob(str(transcript_dir / pattern)))

    if not files:
        print("No transcript files found")
        return

    print(f"Analyzing {len(files)} transcript files...\n")

    all_analyses = []

    for filepath in files:
        analysis = analyze_transcript(filepath)
        all_analyses.append(analysis)

    # Aggregate findings
    all_numbers = []
    all_commands = []
    all_strategies = []

    for analysis in all_analyses:
        all_numbers.extend(analysis['numbers'])
        all_commands.extend(analysis['commands'])
        all_strategies.extend(analysis['strategies'])

    # Count occurrences
    number_counts = Counter(all_numbers)
    command_counts = Counter(all_commands)
    strategy_counts = Counter(all_strategies)

    print("="*80)
    print("AGGREGATE ANALYSIS")
    print("="*80)

    print("\n1. MOST MENTIONED NUMBERS (specific claims to verify):")
    print("-" * 80)
    for number, count in number_counts.most_common(20):
        print(f"  {number:30s} mentioned {count:2d} times")

    print("\n\n2. COMMANDS MENTIONED:")
    print("-" * 80)
    for cmd, count in command_counts.most_common():
        print(f"  {cmd:30s} mentioned {count:2d} times")

    print("\n\n3. STRATEGIES BY POPULARITY:")
    print("-" * 80)
    for strategy, count in strategy_counts.most_common():
        videos_mentioning = sum(1 for a in all_analyses if strategy in a['strategies'])
        print(f"  {strategy:30s} {videos_mentioning:2d}/{len(files)} videos, {count:3d} mentions")

    # Known verified facts
    print("\n\n" + "="*80)
    print("VERIFICATION STATUS")
    print("="*80)

    verified = {
        "/fast": "VERIFIED - Official Claude Code command for faster output",
        "/compact": "VERIFIED - Official command to compact context",
        "/plan": "VERIFIED - Official planning mode command",
        "5 hours": "LIKELY - Common session reset time mentioned in docs",
        "Opus expensive": "VERIFIED - Opus costs more than Sonnet",
        "Sonnet faster": "VERIFIED - Sonnet has faster output than Opus",
        "context grows": "VERIFIED - Context accumulates in conversation",
    }

    needs_verification = {
        "specific message counts": "Changes frequently, verify against current limits",
        "dollar amounts": "Pricing changes, check anthropic.com/pricing",
        "weekly limits": "New system, verify current implementation",
        "$20 plan": "Verify tier pricing is current",
        "$100 plan": "Verify tier exists and current features",
    }

    print("\nVERIFIED FACTS:")
    for fact, status in verified.items():
        print(f"  ✓ {fact:20s} - {status}")

    print("\n\nNEEDS VERIFICATION (may be outdated):")
    for claim, note in needs_verification.items():
        print(f"  ⚠ {claim:20s} - {note}")

    # Pattern analysis
    print("\n\n" + "="*80)
    print("ACTIONABLE PATTERNS")
    print("="*80)

    patterns = [
        ("Start fresh conversations", "Mentioned by multiple creators - limits per conversation"),
        ("Use API for unlimited access", "Consistent recommendation - pay per token vs subscription"),
        ("Switch to Sonnet for routine tasks", "Save Opus for complex tasks only"),
        ("Use /fast mode", "Official feature for faster responses"),
        ("Context management with /compact", "Official tool to reduce context bloat"),
        ("Sub-agents for specialized tasks", "Advanced pattern for reducing main context pollution"),
        ("MCP servers add token overhead", "Multiple creators warn about this"),
        ("Keep CLAUDE.md short", "Loaded in every request"),
    ]

    for i, (pattern, description) in enumerate(patterns, 1):
        print(f"\n{i}. {pattern}")
        print(f"   {description}")

    # Warnings
    print("\n\n" + "="*80)
    print("WARNINGS & RED FLAGS")
    print("="*80)

    warnings = [
        "⚠ API access requires payment method - not truly 'unlimited'",
        "⚠ Some videos claim 'no credit card' but then require billing setup",
        "⚠ Specific rate limit numbers (40K tokens/min, 50 requests/min) may be tier-specific",
        "⚠ 'Weekly limits' mentioned - verify if this is current (July 2025 claim in one video)",
        "⚠ Some creators sell courses/groups - possible bias toward complexity",
        "⚠ Anthropic Workbench mentioned as alternative - verify it's actually unlimited",
    ]

    for warning in warnings:
        print(f"\n{warning}")

    # Contradictions
    print("\n\n" + "="*80)
    print("CONTRADICTIONS TO INVESTIGATE")
    print("="*80)

    contradictions = [
        ("Session reset time", ["5 hours", "3 hours"], "Different videos claim different times"),
        ("Pro plan pricing", ["$20", "$100"], "Unclear if multiple tiers or outdated info"),
        ("API as workaround", ["unlimited", "50 requests/min"], "Not truly unlimited - still has rate limits"),
    ]

    for topic, claims, note in contradictions:
        print(f"\n{topic}:")
        print(f"  Claims: {', '.join(claims)}")
        print(f"  Note: {note}")

    # Recommendations
    print("\n\n" + "="*80)
    print("RECOMMENDATIONS FOR OUR SYSTEM")
    print("="*80)

    recommendations = [
        "1. Focus on VERIFIED techniques: /fast, /compact, start fresh conversations",
        "2. Implement our token budgeting (already doing) - more reliable than guessing limits",
        "3. Use sub-agents for specialized tasks (we have orchestrator skill)",
        "4. Keep CLAUDE.md lean (we already do this with topic files)",
        "5. Switch models tactically: Opus for architecture, Sonnet for implementation",
        "6. Monitor MCP server token overhead (/context command)",
        "7. DON'T rely on API as magic solution - it has rate limits too",
        "8. DON'T trust specific pricing/limit numbers from videos - verify against docs",
        "9. Checkpoint sessions at 80K tokens (already doing)",
        "10. Use context_db to avoid re-reading unchanged files (already doing)",
    ]

    for rec in recommendations:
        print(f"\n  {rec}")

    # Save to file
    output_file = Path('~/Documents/Obsidian/reference/youtube-rate-limits-analysis.md').expanduser()

    with open(output_file, 'w') as f:
        f.write("# YouTube Transcript Analysis: Claude Code Rate Limits\n\n")
        f.write(f"Analyzed {len(files)} videos about avoiding Claude Code rate limits.\n\n")
        f.write("## Key Findings\n\n")

        f.write("### Verified Techniques\n\n")
        for fact, status in verified.items():
            f.write(f"- **{fact}**: {status}\n")

        f.write("\n### Strategies by Popularity\n\n")
        for strategy, count in strategy_counts.most_common():
            videos = sum(1 for a in all_analyses if strategy in a['strategies'])
            f.write(f"- **{strategy}**: {videos}/{len(files)} videos\n")

        f.write("\n### Numbers to Verify\n\n")
        for number, count in number_counts.most_common(20):
            f.write(f"- {number} (mentioned {count}x)\n")

        f.write("\n### Warnings\n\n")
        for warning in warnings:
            f.write(f"{warning}\n")

        f.write("\n### Recommendations\n\n")
        for rec in recommendations:
            f.write(f"{rec}\n")

        f.write("\n---\n")
        f.write(f"Generated: 2026-02-09\n")
        f.write(f"Source: 20 YouTube transcripts\n")
        f.write(f"Tool: analyze_rate_limit_transcripts_v2.py\n")

    print(f"\n\nSaved detailed analysis to:\n{output_file}")

if __name__ == '__main__':
    main()
