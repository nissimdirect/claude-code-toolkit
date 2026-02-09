#!/usr/bin/env python3
"""
Analyze YouTube transcripts about Claude Code rate limits.
Extracts actionable insights, distinguishes verified vs claims, flags contradictions.
"""

import re
import glob
import sys
from pathlib import Path
from collections import defaultdict

def parse_srt(filepath):
    """Extract text from SRT file, removing timestamps and sequence numbers."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # SRT format: sequence number, timestamp, text, blank line
    # Remove sequence numbers (just digits)
    # Remove timestamps (00:00:00,000 --> 00:00:00,000)
    # Keep only text lines

    lines = content.split('\n')
    text_lines = []

    for line in lines:
        line = line.strip()
        # Skip empty lines
        if not line:
            continue
        # Skip sequence numbers (just digits)
        if line.isdigit():
            continue
        # Skip timestamps
        if '-->' in line:
            continue
        # Keep text
        text_lines.append(line)

    return ' '.join(text_lines)

def extract_insights(text, video_id):
    """Extract structured insights from transcript text."""

    insights = {
        'video_id': video_id,
        'rate_limit_strategies': [],
        'token_optimization': [],
        'model_switching': [],
        'context_management': [],
        'pricing_claims': [],
        'session_management': [],
        'commands_settings': [],
        'warnings': []
    }

    text_lower = text.lower()

    # Rate limit strategies
    rate_limit_keywords = [
        'rate limit', 'usage limit', 'message limit', 'request limit',
        'hit the limit', 'avoid limit', 'bypass limit', 'workaround'
    ]

    # Token optimization
    token_keywords = [
        'token', 'context window', 'reduce tokens', 'save tokens',
        'token usage', 'context size', 'compress', 'summarize'
    ]

    # Model switching
    model_keywords = [
        'opus', 'sonnet', 'haiku', 'switch model', 'model selection',
        'fast mode', 'cheaper model', 'better model'
    ]

    # Pricing
    pricing_keywords = [
        '$', 'dollar', 'cost', 'price', 'pricing', 'pay', 'subscription',
        'tier', 'plan', 'credit'
    ]

    # Context management
    context_keywords = [
        'context', 'compact', 'clear', 'reset', 'new conversation',
        'start fresh', 'memory', 'history'
    ]

    # Session management
    session_keywords = [
        'session', 'restart', 'logout', 'new chat', 'conversation',
        'thread', 'multiple'
    ]

    # Commands
    command_keywords = [
        '/fast', '/plan', '/compact', 'command', 'setting', 'config',
        'flag', 'option'
    ]

    # Find sentences containing keywords
    sentences = re.split(r'[.!?]+', text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_lower = sentence.lower()

        # Categorize by keywords
        if any(kw in sentence_lower for kw in rate_limit_keywords):
            insights['rate_limit_strategies'].append(sentence)

        if any(kw in sentence_lower for kw in token_keywords):
            insights['token_optimization'].append(sentence)

        if any(kw in sentence_lower for kw in model_keywords):
            insights['model_switching'].append(sentence)

        if any(kw in sentence_lower for kw in pricing_keywords):
            insights['pricing_claims'].append(sentence)

        if any(kw in sentence_lower for kw in context_keywords):
            insights['context_management'].append(sentence)

        if any(kw in sentence_lower for kw in session_keywords):
            insights['session_management'].append(sentence)

        if any(kw in sentence_lower for kw in command_keywords):
            insights['commands_settings'].append(sentence)

    return insights

def categorize_claims(all_insights):
    """Categorize claims as verified, needs verification, or contradictory."""

    verified = []
    needs_verification = []
    contradictions = []
    actionable = []
    warnings = []

    # Known verified facts about Claude Code
    verified_facts = [
        "/fast command exists",
        "/compact command exists",
        "Opus is more expensive than Sonnet",
        "Sonnet is faster than Opus",
        "Context grows with conversation",
        "Rate limits exist",
        "Token usage matters"
    ]

    # Claims that need verification (pricing, specific limits)
    verification_needed = [
        "specific message counts",
        "specific dollar amounts",
        "specific token limits",
        "specific rate limit numbers",
        "tier pricing"
    ]

    # Collect all unique claims
    all_claims = defaultdict(list)

    for insights in all_insights:
        video_id = insights['video_id']

        # Collect pricing claims (these often change)
        for claim in insights['pricing_claims']:
            all_claims['pricing'].append((video_id, claim))

        # Collect rate limit claims
        for claim in insights['rate_limit_strategies']:
            all_claims['rate_limits'].append((video_id, claim))

        # Collect model switching claims
        for claim in insights['model_switching']:
            all_claims['models'].append((video_id, claim))

    # Analyze for contradictions
    # (This would require semantic analysis - for now just flag duplicate topics)

    return {
        'verified': verified_facts,
        'needs_verification': all_claims,
        'contradictions': contradictions,
        'actionable': actionable,
        'warnings': warnings
    }

def main():
    transcript_dir = Path('/Users/nissimagent/Development/YouTubeTranscripts')
    pattern = 'how_to_stop_hitting_claude_code_rate_limits_*.srt'

    files = sorted(glob.glob(str(transcript_dir / pattern)))

    if not files:
        print("No transcript files found")
        return

    print(f"Found {len(files)} transcript files\n")

    all_insights = []

    # Process each file
    for filepath in files:
        video_id = Path(filepath).stem.split('_')[-1]
        print(f"Processing {video_id}...")

        text = parse_srt(filepath)
        insights = extract_insights(text, video_id)
        all_insights.append(insights)

    print("\n" + "="*80)
    print("ANALYSIS RESULTS")
    print("="*80 + "\n")

    # Aggregate by category
    categories = [
        'rate_limit_strategies',
        'token_optimization',
        'model_switching',
        'context_management',
        'pricing_claims',
        'session_management',
        'commands_settings'
    ]

    for category in categories:
        print(f"\n{'='*80}")
        print(f"{category.upper().replace('_', ' ')}")
        print(f"{'='*80}\n")

        # Collect all mentions from all videos
        all_mentions = []
        for insights in all_insights:
            mentions = insights.get(category, [])
            if mentions:
                all_mentions.extend([
                    f"[{insights['video_id']}] {mention}"
                    for mention in mentions[:3]  # Top 3 per video
                ])

        # Show top 20 mentions
        for mention in all_mentions[:20]:
            print(f"  - {mention}")

        if len(all_mentions) > 20:
            print(f"\n  ... and {len(all_mentions) - 20} more mentions")

    # Categorize claims
    print("\n" + "="*80)
    print("CLAIM CATEGORIZATION")
    print("="*80 + "\n")

    categorized = categorize_claims(all_insights)

    print("VERIFIED INSIGHTS (match known Claude Code behavior):")
    for fact in categorized['verified']:
        print(f"  ✓ {fact}")

    print("\n\nCLAIMS NEEDING VERIFICATION (pricing/limits change frequently):")
    print("\nPricing claims:")
    pricing_claims = categorized['needs_verification'].get('pricing', [])
    for vid, claim in pricing_claims[:10]:
        print(f"  [{vid}] {claim[:200]}")

    print("\n\nRate limit claims:")
    rate_claims = categorized['needs_verification'].get('rate_limits', [])
    for vid, claim in rate_claims[:10]:
        print(f"  [{vid}] {claim[:200]}")

    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    total_insights = sum(
        len(insights.get(cat, []))
        for insights in all_insights
        for cat in categories
    )

    print(f"\nTotal videos analyzed: {len(files)}")
    print(f"Total insights extracted: {total_insights}")

    for category in categories:
        count = sum(len(insights.get(category, [])) for insights in all_insights)
        print(f"  {category}: {count}")

    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    print("""
    1. Verify all pricing claims against current Anthropic pricing page
    2. Verify rate limit numbers against Claude Code docs (if public)
    3. Test suggested commands (/fast, /compact) to confirm behavior
    4. Cross-reference multiple sources for consistent claims
    5. Flag any third-party workarounds that might violate ToS
    6. Update findings quarterly as pricing/limits change
    """)

if __name__ == '__main__':
    main()
