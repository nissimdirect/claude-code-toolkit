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

# ===== EXISTING SOURCES =====

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

# Indie Hackers - Pieter Levels (levels.io)
echo "5️⃣  Pieter Levels - Indie Hacker"
python "$TOOLS_DIR/scraper.py" levelsio \
    https://levels.io \
    "$DEV_DIR/indie-hackers/pieter-levels"

echo ""

# Justin Welsh (Beehiiv)
echo "6️⃣  Justin Welsh - Solopreneur"
python "$TOOLS_DIR/scraper.py" beehiiv \
    https://justinwelsh.beehiiv.com \
    "$DEV_DIR/indie-hackers/justin-welsh"

echo ""

# Daniel Vassallo (Small Bets)
echo "7️⃣  Daniel Vassallo - Small Bets"
python "$TOOLS_DIR/scraper.py" smallbets \
    https://dvassallo.me \
    "$DEV_DIR/indie-hackers/daniel-vassallo"

echo ""

# ===== NEW SOURCES (Added 2026-02-07 Session 9) =====

# Don Norman (jnd.org)
echo "8️⃣  Don Norman - Design & UX Essays"
python "$TOOLS_DIR/scraper.py" jnd \
    https://jnd.org \
    "$DEV_DIR/don-norman"

echo ""

# Valhalla DSP (Sean Costello)
echo "9️⃣  Valhalla DSP - Plugin Design Blog"
python "$TOOLS_DIR/scraper.py" valhalla \
    https://valhalladsp.com \
    "$DEV_DIR/plugin-devs/valhalla-dsp"

echo ""

# Airwindows (Chris Johnson)
echo "🔟 Airwindows - Open Source Plugin Philosophy"
python "$TOOLS_DIR/scraper.py" airwindows \
    https://www.airwindows.com \
    "$DEV_DIR/plugin-devs/airwindows"

echo ""

# e-flux Journal (Art Critical Theory)
echo "1️⃣1️⃣ e-flux Journal - Art Critical Theory"
python "$TOOLS_DIR/scraper.py" eflux \
    https://www.e-flux.com \
    "$DEV_DIR/art-criticism/e-flux-journal"

echo ""

# Hyperallergic (Art Criticism)
echo "1️⃣2️⃣ Hyperallergic - Art Criticism & News"
python "$TOOLS_DIR/scraper.py" hyperallergic \
    https://hyperallergic.com \
    "$DEV_DIR/art-criticism/hyperallergic"

echo ""

# FabFilter Learn (Audio Education)
echo "1️⃣3️⃣ FabFilter Learn - Audio Education"
python "$TOOLS_DIR/scraper.py" fabfilter \
    https://www.fabfilter.com \
    "$DEV_DIR/plugin-devs/fabfilter"

echo ""

# Creative Capital (Grants)
echo "1️⃣4️⃣ Creative Capital - Grant Awardees"
python "$TOOLS_DIR/scraper.py" creativecapital \
    https://creative-capital.org \
    "$DEV_DIR/art-criticism/creative-capital"

echo ""
echo "✅ All sources scraped!"
echo ""
echo "📊 Summary:"
echo "   --- Existing ---"
echo "   Jesse Cannon: $(find $DEV_DIR/jesse-cannon/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   ChatPRD: $(find $DEV_DIR/chatprd-blog/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Lenny: $(find $DEV_DIR/lennys-podcast-transcripts/episodes -name 'transcript.md' 2>/dev/null | wc -l | tr -d ' ') episodes"
echo "   Cherie Hu: $(find $DEV_DIR/cherie-hu/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Pieter Levels: $(find $DEV_DIR/indie-hackers/pieter-levels/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Justin Welsh: $(find $DEV_DIR/indie-hackers/justin-welsh/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Daniel Vassallo: $(find $DEV_DIR/indie-hackers/daniel-vassallo/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   --- New Sources ---"
echo "   Don Norman: $(find $DEV_DIR/don-norman/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Valhalla DSP: $(find $DEV_DIR/plugin-devs/valhalla-dsp/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Airwindows: $(find $DEV_DIR/plugin-devs/airwindows/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   e-flux Journal: $(find $DEV_DIR/art-criticism/e-flux-journal/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Hyperallergic: $(find $DEV_DIR/art-criticism/hyperallergic/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   FabFilter: $(find $DEV_DIR/plugin-devs/fabfilter/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Creative Capital: $(find $DEV_DIR/art-criticism/creative-capital/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo ""
echo "💰 Tokens burned: 0"
echo "🌳 Carbon impact: Minimal (code execution only)"
