#!/bin/bash
# Scrape documentation from all 30 plugin companies
# Based on TOP-30-PLUGIN-COMPANIES.md

# Output base directory
OUTPUT_BASE="$HOME/Documents/Obsidian/VST-Research"
mkdir -p "$OUTPUT_BASE"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Scraper script and Python environment
VENV_PYTHON="$HOME/Development/tools/venv/bin/python"
SCRAPER="$HOME/Development/tools/plugin_doc_scraper.py"

# Company data: "Name|URL"
# Tier 1: Market Leaders
COMPANIES=(
    "FabFilter|https://www.fabfilter.com"
    "Valhalla DSP|https://valhalladsp.com"
    "Soundtoys|https://www.soundtoys.com"
    "Baby Audio|https://babyaud.io"
    "Minimal Audio|https://www.minimalaudio.com"
    "iZotope|https://www.izotope.com"
    "Plugin Alliance|https://www.plugin-alliance.com"
    "Slate Digital|https://slatedigital.com"
    "Native Instruments|https://www.native-instruments.com"
    "Waves Audio|https://www.waves.com"
    "Universal Audio|https://www.uaudio.com"

    # Tier 2: Established Players
    "Arturia|https://www.arturia.com"
    "Output|https://output.com"
    "Kilohearts|https://kilohearts.com"
    "Spectrasonics|https://www.spectrasonics.net"
    "Celemony|https://www.celemony.com"
    "Softube|https://www.softube.com"

    # Tier 3: Indie Success Stories
    "U-he|https://u-he.com"
    "Tokyo Dawn Records|https://www.tokyodawn.net"
    "Auburn Sounds|https://www.auburnsounds.com"
    "Sonnox|https://www.sonnox.com"
    "DMG Audio|https://dmgaudio.com"
    "Audio Damage|https://audiodamage.com"
    "Klevgrand|https://klevgrand.com"

    # Tier 4: Emerging/Niche Players
    "Newfangled Audio|https://www.eventideaudio.com/newfangled"
    "Unfiltered Audio|https://unfilteredaudio.com"
    "Denise Audio|https://www.denise.io"
    "Lunacy Audio|https://lunacyaudio.com"
    "Goodhertz|https://goodhertz.com"
    "Melda Production|https://www.meldaproduction.com"
)

# Priority order (scrape these first - most likely to have good docs)
PRIORITY_INDICES=(0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29)

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}Plugin Documentation Scraper${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
echo "Total companies: ${#COMPANIES[@]}"
echo "Output directory: $OUTPUT_BASE"
echo ""
echo -e "${YELLOW}Starting in 3 seconds...${NC}"
sleep 3

# Track stats
TOTAL=0
SUCCESS=0
FAILED=0

# Scrape each company
for idx in "${PRIORITY_INDICES[@]}"; do
    IFS='|' read -r NAME URL <<< "${COMPANIES[$idx]}"

    TOTAL=$((TOTAL + 1))

    echo ""
    echo -e "${BLUE}[$TOTAL/${#COMPANIES[@]}] Scraping: $NAME${NC}"
    echo -e "${BLUE}URL: $URL${NC}"

    # Create safe directory name
    DIR_NAME=$(echo "$NAME" | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
    OUTPUT_DIR="$OUTPUT_BASE/$DIR_NAME"

    # Run scraper with venv Python
    if "$VENV_PYTHON" "$SCRAPER" "$NAME" "$URL" "$OUTPUT_DIR"; then
        echo -e "${GREEN}✅ Success: $NAME${NC}"
        SUCCESS=$((SUCCESS + 1))
    else
        echo -e "${YELLOW}⚠️  Failed: $NAME${NC}"
        FAILED=$((FAILED + 1))
    fi

    # Rate limiting: 5 seconds between companies
    if [ $TOTAL -lt ${#COMPANIES[@]} ]; then
        echo -e "${YELLOW}Waiting 5 seconds before next company...${NC}"
        sleep 5
    fi
done

# Final report
echo ""
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}Scraping Complete!${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
echo "Total: $TOTAL companies"
echo -e "${GREEN}Success: $SUCCESS${NC}"
echo -e "${YELLOW}Failed: $FAILED${NC}"
echo ""
echo "Results saved to: $OUTPUT_BASE"
echo ""

# Generate summary report
SUMMARY_FILE="$OUTPUT_BASE/SCRAPING-SUMMARY.md"
cat > "$SUMMARY_FILE" <<EOF
# Plugin Documentation Scraping Summary

**Date:** $(date '+%Y-%m-%d %H:%M:%S')
**Total Companies:** $TOTAL
**Successful:** $SUCCESS
**Failed:** $FAILED

---

## Companies Scraped

EOF

# List all scraped directories
for dir in "$OUTPUT_BASE"/*/; do
    if [ -d "$dir" ]; then
        DIR_NAME=$(basename "$dir")
        INDEX_FILE="$dir/INDEX.md"

        echo "- [$DIR_NAME]($DIR_NAME/INDEX.md)" >> "$SUMMARY_FILE"

        if [ -f "$INDEX_FILE" ]; then
            # Extract product count from INDEX.md
            PRODUCT_COUNT=$(grep -o "Products Found: [0-9]*" "$INDEX_FILE" | grep -o "[0-9]*" || echo "0")
            echo "  - Products: $PRODUCT_COUNT" >> "$SUMMARY_FILE"
        fi
    fi
done

echo "Summary report: $SUMMARY_FILE"
