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

# Kilohearts Blog (Plugin Development + Sound Design)
echo "1️⃣5️⃣ Kilohearts - Plugin Development & Sound Design"
python "$TOOLS_DIR/scraper.py" kilohearts \
    https://kilohearts.com/blog \
    "$DEV_DIR/plugin-devs/kilohearts"

# ===== CREATIVE INTERVIEW SOURCES (Added 2026-02-08) =====

echo ""

# Brian Eno Interviews (moredarkthanshark.org)
echo "1️⃣6️⃣ Brian Eno - Interview Archive"
python "$TOOLS_DIR/scraper.py" eno \
    https://www.moredarkthanshark.org \
    "$DEV_DIR/creative-interviews/brian-eno"

echo ""

# The Creative Independent (1,000+ creative interviews)
echo "1️⃣7️⃣ The Creative Independent - Creative Interviews"
python "$TOOLS_DIR/scraper.py" creative-independent \
    https://thecreativeindependent.com \
    "$DEV_DIR/creative-interviews/creative-independent"

echo ""

# David Lynch Interviews (lynchnet.com)
echo "1️⃣8️⃣ David Lynch - Interview Archive"
python "$TOOLS_DIR/scraper.py" lynchnet \
    https://www.lynchnet.com \
    "$DEV_DIR/creative-interviews/david-lynch"

echo ""

# BOMB Magazine Interviews
echo "1️⃣9️⃣ BOMB Magazine - Artist Interviews"
python "$TOOLS_DIR/scraper.py" bomb-magazine \
    https://bombmagazine.org \
    "$DEV_DIR/creative-interviews/bomb-magazine"

# ===== ART DIRECTION SOURCES (Added 2026-02-08) =====

echo ""

# It's Nice That (Art Direction Blog)
echo "2️⃣0️⃣ It's Nice That - Art Direction Blog"
python "$TOOLS_DIR/scraper.py" itsnicethat \
    https://www.itsnicethat.com \
    "$DEV_DIR/art-direction/its-nice-that"

echo ""

# Creative Boom (Art/Design Articles)
echo "2️⃣1️⃣ Creative Boom - Art & Design Articles"
python "$TOOLS_DIR/scraper.py" creativeboom \
    https://www.creativeboom.com \
    "$DEV_DIR/art-direction/creative-boom"

echo ""

# Fonts In Use (Typography Specimens)
echo "2️⃣2️⃣ Fonts In Use - Typography Specimens"
python "$TOOLS_DIR/scraper.py" fontsinuse \
    https://fontsinuse.com \
    "$DEV_DIR/art-direction/fonts-in-use"

echo ""

# The Brand Identity (Brand/Identity Design)
echo "2️⃣3️⃣ The Brand Identity - Brand & Identity Design"
python "$TOOLS_DIR/scraper.py" thebrandidentity \
    https://the-brand-identity.com \
    "$DEV_DIR/art-direction/the-brand-identity"

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
echo "   Kilohearts: $(find $DEV_DIR/plugin-devs/kilohearts/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   --- Creative Interviews ---"
echo "   Brian Eno: $(find $DEV_DIR/creative-interviews/brian-eno/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Creative Independent: $(find $DEV_DIR/creative-interviews/creative-independent/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   David Lynch: $(find $DEV_DIR/creative-interviews/david-lynch/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   BOMB Magazine: $(find $DEV_DIR/creative-interviews/bomb-magazine/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   --- Art Direction ---"
echo "   It's Nice That: $(find $DEV_DIR/art-direction/its-nice-that/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Creative Boom: $(find $DEV_DIR/art-direction/creative-boom/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   Fonts In Use: $(find $DEV_DIR/art-direction/fonts-in-use/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo "   The Brand Identity: $(find $DEV_DIR/art-direction/the-brand-identity/articles -name '*.md' 2>/dev/null | wc -l | tr -d ' ') articles"
echo ""
echo "💰 Tokens burned: 0"
echo "🌳 Carbon impact: Minimal (code execution only)"
