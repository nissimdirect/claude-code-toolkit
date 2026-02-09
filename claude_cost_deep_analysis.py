#!/usr/bin/env python3
"""
Deep analysis of Claude Code cost patterns.
Extract specific technical details from key transcripts.
"""

import re
import json
from pathlib import Path

def parse_srt_clean(file_path):
    """Parse SRT and return clean text without duplicates."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    seen = set()
    text_lines = []

    for line in lines:
        line = line.strip()
        if line and not line.isdigit() and '-->' not in line:
            # Deduplicate (SRT files often repeat lines)
            if line not in seen or len(line) > 100:
                text_lines.append(line)
                seen.add(line)

    return ' '.join(text_lines)

def extract_technical_details(text):
    """Extract specific technical implementation details."""
    details = {}

    # Look for specific file paths
    path_pattern = r'~/?\.[a-z]+/[a-zA-Z0-9_/.-]+'
    paths = re.findall(path_pattern, text)
    if paths:
        details['file_paths'] = list(set(paths))

    # Look for specific commands
    command_pattern = r'(?:^|\s)(\/[a-z-]+)(?:\s|$)'
    commands = re.findall(command_pattern, text, re.IGNORECASE)
    if commands:
        details['commands'] = list(set(commands))

    # Look for quota numbers
    quota_pattern = r'(\d+)%?\s*(?:quota|limit|usage)'
    quotas = re.findall(quota_pattern, text, re.IGNORECASE)
    if quotas:
        details['quota_numbers'] = list(set(quotas))

    # Look for time windows
    time_pattern = r'(\d+)[- ]?(?:hour|hr|h)s?'
    times = re.findall(time_pattern, text, re.IGNORECASE)
    if times:
        details['time_windows'] = list(set(times))

    # Look for file formats
    format_pattern = r'(?:JSONL|JSON|\.json|\.jsonl|\.log)'
    formats = re.findall(format_pattern, text, re.IGNORECASE)
    if formats:
        details['file_formats'] = list(set(formats))

    # Look for specific token counts
    token_pattern = r'(\d+)\s*(?:tokens?|k tokens?)'
    tokens = re.findall(token_pattern, text, re.IGNORECASE)
    if tokens:
        details['token_numbers'] = list(set(tokens))[:10]  # Limit

    return details

def extract_key_quotes(text):
    """Extract key sentences with specific insights."""
    quotes = []

    # Patterns for important statements
    patterns = [
        r'(?:anthropic|claude)[^.]{10,150}(?:hid|hiding|hidden)[^.]{5,100}\.',
        r'(?:cost|pricing|price)[^.]{10,150}(?:would be|monthly|cheaper)[^.]{5,100}\.',
        r'(?:token|message|quota)[^.]{10,150}(?:usage|limit|reset)[^.]{5,100}\.',
        r'(?:local|directory|file)[^.]{10,150}(?:contains|stores|written)[^.]{5,100}\.',
        r'(?:api|monthly plan)[^.]{10,150}(?:cheaper|expensive|save|saved)[^.]{5,100}\.',
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            quote = match.group(0).strip()
            # Clean up
            quote = re.sub(r'\s+', ' ', quote)
            if 50 < len(quote) < 250:
                quotes.append(quote)

    return quotes[:15]  # Limit to top 15

def analyze_video_detailed(video_id, transcript_dir):
    """Deep analysis of a single video."""
    file_path = transcript_dir / f"claude_code_hidden_cost_{video_id}.en.srt"
    if not file_path.exists():
        return None

    text = parse_srt_clean(file_path)

    return {
        'video_id': video_id,
        'length': len(text),
        'technical_details': extract_technical_details(text),
        'key_quotes': extract_key_quotes(text),
    }

def main():
    transcript_dir = Path('/Users/nissimagent/Development/YouTubeTranscripts')

    # Load previous analysis to find key videos
    json_path = Path('/Users/nissimagent/Development/tools/claude_cost_analysis.json')
    with open(json_path) as f:
        all_results = json.load(f)

    # Identify key videos (ones with most strategies/warnings)
    scored = []
    for result in all_results:
        score = (
            len(result['reduction_strategies']) * 3 +
            len(result['warnings']) * 2 +
            len(result['tools_mentioned'])
        )
        scored.append((score, result['video_id'].replace('.en', '')))

    top_videos = sorted(scored, reverse=True)[:5]

    print("=" * 80)
    print("DEEP DIVE: Technical Details from Top 5 Videos")
    print("=" * 80)
    print()

    detailed_results = []
    for score, video_id in top_videos:
        print(f"\nAnalyzing: {video_id} (score: {score})")
        result = analyze_video_detailed(video_id, transcript_dir)
        if result:
            detailed_results.append(result)

    # Generate detailed report
    report = []
    report.append("=" * 80)
    report.append("CLAUDE CODE COSTS - TECHNICAL DEEP DIVE")
    report.append("=" * 80)
    report.append("")

    # Aggregate technical findings
    all_paths = set()
    all_commands = set()
    all_formats = set()

    for result in detailed_results:
        details = result['technical_details']
        all_paths.update(details.get('file_paths', []))
        all_commands.update(details.get('commands', []))
        all_formats.update(details.get('file_formats', []))

    report.append("## TECHNICAL IMPLEMENTATION DETAILS")
    report.append("")

    if all_paths:
        report.append("### File Paths Mentioned:")
        for path in sorted(all_paths):
            report.append(f"  - {path}")
        report.append("")

    if all_commands:
        report.append("### Commands Available:")
        for cmd in sorted(all_commands):
            report.append(f"  - {cmd}")
        report.append("")

    if all_formats:
        report.append("### Data Formats:")
        for fmt in sorted(all_formats):
            report.append(f"  - {fmt}")
        report.append("")

    report.append("=" * 80)
    report.append("## KEY INSIGHTS (Direct Quotes)")
    report.append("")

    for result in detailed_results:
        if result['key_quotes']:
            report.append(f"### Video: {result['video_id']}")
            report.append("")
            for i, quote in enumerate(result['key_quotes'][:5], 1):
                report.append(f"{i}. {quote}")
                report.append("")

    report.append("=" * 80)
    report.append("## IMPLEMENTATION RECOMMENDATIONS")
    report.append("")

    report.append("Based on the technical details extracted:")
    report.append("")

    report.append("1. LOCAL DATA ACCESS")
    report.append("   Location: ~/.claude/projects/")
    report.append("   Format: JSONL (one JSON object per line)")
    report.append("   Contains: input_tokens, output_tokens per message")
    report.append("   ACTION: Build custom analytics from this raw data")
    report.append("")

    report.append("2. USAGE MONITORING")
    report.append("   Tool: Claude Code Usage Monitor (open-source)")
    report.append("   GitHub: Search for 'claude-code-usage-monitor'")
    report.append("   Features: --plan flag, --view flag (session/daily/monthly)")
    report.append("   ACTION: Install and integrate with our resource tracker")
    report.append("")

    report.append("3. COST CALCULATION")
    report.append("   Method: token_count * price_per_token")
    report.append("   Pricing: Check anthropic.com/pricing (changes frequently)")
    report.append("   Compare: Monthly subscription vs API usage-based")
    report.append("   ACTION: Monthly review to optimize plan choice")
    report.append("")

    report.append("4. QUOTA MANAGEMENT")
    report.append("   Window: 5-hour rolling reset")
    report.append("   Limits: Both token AND message quotas (hit either = blocked)")
    report.append("   Tracking: Session view shows time until next reset")
    report.append("   ACTION: Monitor quota usage to avoid mid-session blocks")
    report.append("")

    report.append("5. HIDDEN COST AWARENESS")
    report.append("   - /cost command only works with API key (not monthly plans)")
    report.append("   - Anthropic has data but doesn't surface it in UI")
    report.append("   - Light users likely subsidizing power users")
    report.append("   - Top 5% of users forced introduction of caps")
    report.append("   ACTION: Be aware of incentive misalignment")
    report.append("")

    # Write report
    output_path = Path('/Users/nissimagent/Development/tools/claude_cost_deep_dive.txt')
    output_path.write_text('\n'.join(report))
    print(f"\nDeep dive report written to: {output_path}")

    # Print report
    print("\n" + '\n'.join(report))

if __name__ == '__main__':
    main()
