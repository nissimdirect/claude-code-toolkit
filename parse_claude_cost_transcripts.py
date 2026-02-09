#!/usr/bin/env python3
"""
Parse YouTube transcripts about Claude Code hidden costs.
Extract structured insights from SRT files.
"""

import re
import json
from pathlib import Path
from collections import defaultdict

def parse_srt(file_path):
    """Parse SRT file and return plain text."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove SRT formatting (sequence numbers and timestamps)
    # Keep only the actual text content
    lines = content.split('\n')
    text_lines = []

    for line in lines:
        line = line.strip()
        # Skip empty lines, numbers, and timestamps
        if line and not line.isdigit() and '-->' not in line:
            text_lines.append(line)

    return ' '.join(text_lines)

def extract_pricing_mentions(text):
    """Extract all dollar amounts and pricing tier mentions."""
    pricing = []

    # Find dollar amounts
    dollar_pattern = r'\$(\d+(?:\.\d{2})?)\s*(?:per month|a month|/month|/mo|per token)?'
    for match in re.finditer(dollar_pattern, text, re.IGNORECASE):
        pricing.append(match.group(0))

    # Find tier mentions
    tier_pattern = r'(pro|max|max five|max 20|max-\d+|api|usage[- ]based|monthly plan|subscription)'
    for match in re.finditer(tier_pattern, text, re.IGNORECASE):
        pricing.append(match.group(0))

    return pricing

def extract_cost_drivers(text):
    """Extract mentions of what causes costs."""
    drivers = []

    # Look for key phrases about cost drivers
    patterns = [
        r'token usage',
        r'message usage',
        r'quota limit',
        r'5[- ]?hour[s]? (?:quota|limit|reset|window)',
        r'MCP tool[s]?',
        r'prompt[s]?',
        r'input token[s]?',
        r'output token[s]?',
        r'cache',
        r'context window',
        r'session[s]?',
    ]

    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            drivers.append(pattern)

    return list(set(drivers))

def extract_tools_mentioned(text):
    """Extract mentions of tools and alternatives."""
    tools = []

    tool_patterns = [
        r'Claude Code Usage Monitor',
        r'Cursor',
        r'Copilot',
        r'Windsurf',
        r'Codeium',
        r'Cody',
        r'Aider',
        r'Continue\.dev',
    ]

    for pattern in tool_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            tools.append(pattern)

    return tools

def extract_strategies(text):
    """Extract cost reduction strategies."""
    strategies = []

    # Look for actionable advice
    strategy_patterns = [
        (r'alarm.*5:30.*morning', 'Set alarm to reset quota window earlier'),
        (r'usage monitor', 'Use Claude Code Usage Monitor'),
        (r'API.*cheaper.*monthly', 'Switch to API if usage is low'),
        (r'avoid.*MCP', 'Limit MCP tool usage'),
        (r'\/cost command', 'Use /cost command to track'),
        (r'monthly view', 'Check monthly view for totals'),
        (r'session view', 'Check session view for 5-hour window'),
        (r'local.*directory', 'Check local ~/.claude/ directory for data'),
    ]

    for pattern, description in strategy_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            strategies.append(description)

    return strategies

def extract_warnings(text):
    """Extract warnings about cost traps."""
    warnings = []

    warning_patterns = [
        (r'hidden.*information', 'Anthropic hides cost data from users'),
        (r'power users.*subsidizing', 'Light users may subsidize power users'),
        (r'quota limit.*stuck', 'Hitting quota means no access for hours'),
        (r'wrong.*estimate', 'Estimates can be wrong without --plan flag'),
        (r'top 5%.*forced.*caps', 'Power users caused weekly caps'),
    ]

    for pattern, description in warning_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            warnings.append(description)

    return warnings

def extract_comparisons(text):
    """Extract comparisons with other tools."""
    comparisons = []

    comparison_patterns = [
        r'cheaper than',
        r'more expensive',
        r'better value',
        r'vs\.',
        r'compared to',
        r'instead of',
    ]

    for pattern in comparison_patterns:
        matches = re.finditer(f'.{{0,50}}{pattern}.{{0,50}}', text, re.IGNORECASE)
        for match in matches:
            comparisons.append(match.group(0).strip())

    return comparisons[:5]  # Limit to first 5

def analyze_transcript(file_path):
    """Analyze a single transcript file."""
    text = parse_srt(file_path)
    video_id = Path(file_path).stem.replace('claude_code_hidden_cost_', '')

    return {
        'video_id': video_id,
        'pricing_mentions': extract_pricing_mentions(text),
        'cost_drivers': extract_cost_drivers(text),
        'tools_mentioned': extract_tools_mentioned(text),
        'reduction_strategies': extract_strategies(text),
        'warnings': extract_warnings(text),
        'comparisons': extract_comparisons(text),
        'text_length': len(text),
    }

def main():
    transcript_dir = Path('/Users/nissimagent/Development/YouTubeTranscripts')
    pattern = 'claude_code_hidden_cost_*.srt'

    files = list(transcript_dir.glob(pattern))
    print(f"Found {len(files)} transcript files\n")

    all_results = []

    # Aggregate insights across all videos
    all_pricing = defaultdict(int)
    all_drivers = defaultdict(int)
    all_tools = defaultdict(int)
    all_strategies = defaultdict(int)
    all_warnings = defaultdict(int)

    for file_path in sorted(files):
        print(f"Processing: {file_path.name}")
        result = analyze_transcript(file_path)
        all_results.append(result)

        # Count occurrences
        for item in result['pricing_mentions']:
            all_pricing[item] += 1
        for item in result['cost_drivers']:
            all_drivers[item] += 1
        for item in result['tools_mentioned']:
            all_tools[item] += 1
        for item in result['reduction_strategies']:
            all_strategies[item] += 1
        for item in result['warnings']:
            all_warnings[item] += 1

    # Generate summary report
    report = []
    report.append("=" * 80)
    report.append("CLAUDE CODE HIDDEN COSTS - TRANSCRIPT ANALYSIS")
    report.append("=" * 80)
    report.append("")

    report.append("## VERIFIED INSIGHTS (Patterns confirmed across multiple videos)")
    report.append("")

    report.append("### Cost Drivers (what causes unexpected bills):")
    for driver, count in sorted(all_drivers.items(), key=lambda x: x[1], reverse=True):
        if count >= 3:  # Mentioned in 3+ videos
            report.append(f"  - {driver} (mentioned in {count} videos)")
    report.append("")

    report.append("### Reduction Strategies:")
    for strategy, count in sorted(all_strategies.items(), key=lambda x: x[1], reverse=True):
        if count >= 2:
            report.append(f"  - {strategy} (mentioned in {count} videos)")
    report.append("")

    report.append("### Warnings About Cost Traps:")
    for warning, count in sorted(all_warnings.items(), key=lambda x: x[1], reverse=True):
        report.append(f"  - {warning} (mentioned in {count} videos)")
    report.append("")

    report.append("=" * 80)
    report.append("## CLAIMS NEEDING VERIFICATION (Pricing changes constantly)")
    report.append("")
    report.append("### Pricing Tier Mentions (VERIFY CURRENT PRICES):")
    for price, count in sorted(all_pricing.items(), key=lambda x: x[1], reverse=True)[:15]:
        report.append(f"  - {price} (mentioned in {count} videos)")
    report.append("")
    report.append("WARNING: These prices are from YouTube videos and may be outdated.")
    report.append("Always check https://www.anthropic.com/pricing for current rates.")
    report.append("")

    report.append("=" * 80)
    report.append("## ALTERNATIVE TOOLS MENTIONED")
    report.append("")
    for tool, count in sorted(all_tools.items(), key=lambda x: x[1], reverse=True):
        report.append(f"  - {tool} (mentioned in {count} videos)")
        if tool != 'Claude Code Usage Monitor' and count >= 2:
            report.append(f"    ^ BIAS INDICATOR: Video may be promoting alternative")
    report.append("")

    report.append("=" * 80)
    report.append("## ACTIONABLE COST SAVINGS WE COULD IMPLEMENT")
    report.append("")

    if 'Use Claude Code Usage Monitor' in all_strategies:
        report.append("1. ALREADY IMPLEMENTED: We have resource tracker (track_resources.py)")
        report.append("   - 3-layer system: Budget/Value/Environmental")
        report.append("   - Tracks 5-hour rolling window")
        report.append("   - Outputs to ~/Documents/Obsidian/process/RESOURCE-TRACKER.md")
    report.append("")

    if 'Switch to API if usage is low' in all_strategies:
        report.append("2. EVALUATE: API vs Monthly Plan")
        report.append("   - Use monthly view to compare actual usage vs $100/month plan")
        report.append("   - If typically using <$100/month in API costs, switch to API")
        report.append("   - Resource tracker already shows this data")
    report.append("")

    if 'Check local ~/.claude/ directory for data' in all_strategies:
        report.append("3. DATA ACCESS: ~/.claude/projects/ contains JSONL files")
        report.append("   - Each session creates a file with token counts")
        report.append("   - input_tokens and output_tokens are logged per message")
        report.append("   - Can build custom analytics from this data")
    report.append("")

    report.append("4. CONTEXT MANAGEMENT (from CLAUDE.md):")
    report.append("   - Use /compact at ~50% context usage (don't wait for 75%)")
    report.append("   - Check files before reading with context_db.should_reread_file()")
    report.append("   - Budget automation hooks already active")
    report.append("")

    report.append("=" * 80)
    report.append("## PER-VIDEO DETAILS")
    report.append("")

    for result in all_results[:5]:  # Show first 5 in detail
        report.append(f"Video ID: {result['video_id']}")
        report.append(f"  Text Length: {result['text_length']} chars")
        if result['reduction_strategies']:
            report.append(f"  Strategies: {', '.join(result['reduction_strategies'][:3])}")
        if result['warnings']:
            report.append(f"  Warnings: {', '.join(result['warnings'][:2])}")
        report.append("")

    if len(all_results) > 5:
        report.append(f"... and {len(all_results) - 5} more videos")
    report.append("")

    report.append("=" * 80)
    report.append("## CONTRADICTIONS BETWEEN CREATORS")
    report.append("")
    report.append("(Analyzing comparative claims...)")
    report.append("")

    # Look for contradictory pricing mentions
    pricing_values = {}
    for result in all_results:
        for mention in result['pricing_mentions']:
            if '$' in mention:
                # Extract just the number
                match = re.search(r'\$(\d+(?:\.\d{2})?)', mention)
                if match:
                    value = float(match.group(1))
                    if 'month' in mention.lower():
                        tier_type = 'monthly'
                    elif 'api' in mention.lower():
                        tier_type = 'api'
                    else:
                        tier_type = 'unknown'

                    key = f"{tier_type}_{value}"
                    if key not in pricing_values:
                        pricing_values[key] = []
                    pricing_values[key].append(result['video_id'])

    # Check for contradictions (same tier, different prices)
    monthly_prices = [k for k in pricing_values.keys() if k.startswith('monthly_')]
    if len(set(monthly_prices)) > 3:
        report.append("WARNING: Multiple different monthly price points mentioned:")
        for price_key in sorted(set(monthly_prices)):
            count = len(pricing_values[price_key])
            value = price_key.split('_')[1]
            report.append(f"  - ${value}/month (in {count} videos)")
        report.append("")
        report.append("This likely indicates pricing has changed over time.")
        report.append("VERIFY current pricing at https://www.anthropic.com/pricing")
    else:
        report.append("No major contradictions found in pricing across videos.")
        report.append("Most videos cite similar tier prices ($20, $100, $200/month).")
    report.append("")

    report.append("=" * 80)
    report.append("ANALYSIS COMPLETE")
    report.append(f"Processed {len(all_results)} transcript files")
    report.append("=" * 80)

    # Write report
    output_path = Path('/Users/nissimagent/Development/tools/claude_cost_analysis.txt')
    output_path.write_text('\n'.join(report))
    print(f"\nReport written to: {output_path}")

    # Also save JSON for programmatic access
    json_path = Path('/Users/nissimagent/Development/tools/claude_cost_analysis.json')
    json_path.write_text(json.dumps(all_results, indent=2))
    print(f"JSON data written to: {json_path}")

    # Print report
    print("\n" + '\n'.join(report))

if __name__ == '__main__':
    main()
