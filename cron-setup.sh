#!/bin/bash
# Cron Job Setup for PopChaos Labs
# Run this once to install all recurring automation
#
# Jobs installed:
#   1. Daily (8am): Resource tracking → RESOURCE-TRACKER.md
#   2. Bi-weekly (1st & 15th, 2am): TF-IDF auto-tagging
#   3. Monthly (1st, 3am): Full advisor scrape

set -e

TOOLS_DIR="$HOME/Development/tools"
VENV="$TOOLS_DIR/venv/bin/python"
LOG_DIR="$HOME/Development/tools/logs"

# Create log directory
mkdir -p "$LOG_DIR"

# Build crontab entries
CRON_ENTRIES=$(cat <<'CRONTAB'
# === PopChaos Labs Automated Tasks ===

# Daily at 8am: Resource tracking (updates RESOURCE-TRACKER.md)
0 8 * * * /Users/nissimagent/Development/tools/venv/bin/python /Users/nissimagent/Development/tools/track_resources.py >> /Users/nissimagent/Development/tools/logs/resource-tracker.log 2>&1

# Bi-weekly (1st and 15th at 2am): TF-IDF auto-tagging of knowledge base
0 2 1,15 * * /Users/nissimagent/Development/tools/venv/bin/python /Users/nissimagent/Development/tools/auto_tag_corpus.py --auto-confirm >> /Users/nissimagent/Development/tools/logs/auto-tag.log 2>&1

# Monthly (1st at 3am): Full advisor data scrape
0 3 1 * * cd /Users/nissimagent/Development/tools && source venv/bin/activate && ./scrape-all.sh >> /Users/nissimagent/Development/tools/logs/scrape-all.log 2>&1

# === End PopChaos Labs ===
CRONTAB
)

echo "📋 Installing cron jobs..."
echo ""

# Preserve any existing crontab entries
EXISTING=$(crontab -l 2>/dev/null || true)

if echo "$EXISTING" | grep -q "PopChaos Labs"; then
    echo "⚠️  PopChaos cron jobs already installed. Replacing..."
    # Remove old PopChaos entries
    EXISTING=$(echo "$EXISTING" | sed '/=== PopChaos Labs/,/=== End PopChaos/d')
fi

# Install combined crontab
echo "$EXISTING
$CRON_ENTRIES" | crontab -

echo "✅ Cron jobs installed!"
echo ""
echo "📊 Verify with: crontab -l"
echo ""
echo "Jobs:"
echo "  1. Daily 8am    → Resource tracking"
echo "  2. 1st/15th 2am → TF-IDF auto-tagging"
echo "  3. 1st 3am      → Full advisor scrape"
echo ""
echo "Logs: $LOG_DIR/"
