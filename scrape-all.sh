#!/bin/bash
# Scrape all advisor sources
# Run this to update all training data with ZERO token burn

set -e

TOOLS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DEV_DIR="$HOME/Development"

# Activate venv
source "$TOOLS_DIR/venv/bin/activate"

echo "🚀 Scraping all advisor sources (no tokens burned)"
echo ""

# Jesse Cannon (Beehiiv)
echo "1️⃣  Jesse Cannon - Music Marketing Trends"
python "$TOOLS_DIR/scraper.py" beehiiv \
    https://musicmarketingtrends.beehiiv.com \
    "$DEV_DIR/jesse-cannon"

echo ""

# ChatPRD Blog
echo "2️⃣  ChatPRD - AI Workflows"
python "$TOOLS_DIR/scraper.py" chatprd \
    https://chatprd.ai/blog \
    "$DEV_DIR/chatprd-blog"

echo ""

# Lenny (GitHub - just git pull)
echo "3️⃣  Lenny's Podcast (GitHub)"
cd "$DEV_DIR/lennys-podcast-transcripts"
git pull origin main
echo "   ✅ Updated from GitHub"

echo ""

# Water & Music (Cherie Hu)
echo "4️⃣  Water & Music (Cherie Hu)"
python "$TOOLS_DIR/scraper.py" waterandmusic \
    https://www.waterandmusic.com \
    "$DEV_DIR/cherie-hu"

echo ""
echo "✅ All sources scraped!"
echo ""
echo "📊 Summary:"
echo "   Jesse Cannon: $(find $DEV_DIR/jesse-cannon/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   ChatPRD: $(find $DEV_DIR/chatprd-blog/how-i-ai -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Lenny: $(find $DEV_DIR/lennys-podcast-transcripts/episodes -name 'transcript.md' 2>/dev/null | wc -l | tr -d ' ') episodes"
echo "   Cherie Hu: $(find $DEV_DIR/cherie-hu/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo ""
echo "💰 Tokens burned: 0"
echo "🌳 Carbon impact: Minimal (code execution only)"
