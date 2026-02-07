# Advisor Training Data Scraper

**Purpose:** Scrape web content with ZERO token burn.
**Philosophy:** Build tools, don't be the tool.

---

## Quick Start

### One Command - Scrape Everything

```bash
cd ~/Development/tools
./scrape-all.sh
```

**What it does:**
1. Scrapes Jesse Cannon newsletter (146 articles)
2. Scrapes ChatPRD blog (119 articles)
3. Updates Lenny transcripts (git pull)
4. Saves all as structured markdown
5. **Tokens burned: 0** ✅

**Time:** ~10-20 minutes (runs independently)

---

## Individual Scrapers

### Jesse Cannon (Music Marketing)
```bash
source ~/Development/tools/venv/bin/activate
python ~/Development/tools/scraper.py beehiiv \
    https://musicmarketingtrends.beehiiv.com \
    ~/Development/jesse-cannon
```

**Output:**
- `~/Development/jesse-cannon/articles/*.md`
- `~/Development/jesse-cannon/INDEX.md`
- `~/Development/jesse-cannon/metadata/metadata.json`

### ChatPRD (AI Workflows)
```bash
source ~/Development/tools/venv/bin/activate
python ~/Development/tools/scraper.py chatprd \
    https://chatprd.ai/blog \
    ~/Development/chatprd-blog
```

**Output:**
- `~/Development/chatprd-blog/articles/*.md`
- `~/Development/chatprd-blog/INDEX.md`
- `~/Development/chatprd-blog/metadata/metadata.json`

### Lenny (Already complete via GitHub)
```bash
cd ~/Development/lennys-podcast-transcripts
git pull origin main
```

---

## Architecture

### Why This Approach?

**Before (Token-Heavy):**
```
User → Claude → WebFetch → Process HTML → Extract content → Convert markdown
                ↑ BURNS TOKENS FOR EVERY PAGE
```

**After (Token-Free):**
```
User → Python Script → Fetch + Extract + Convert → Save files
Claude → Read saved files (no processing cost)
       ↑ ZERO TOKENS BURNED
```

**Token Savings:**
- Per article: ~2-5K tokens saved
- 265 articles: ~530K-1.3M tokens saved
- Cost savings: **$7.95-$19.50**
- Environmental: **1-2.6 kWh saved** (~500-1,300g CO2)

---

## File Structure

```
~/Development/
├── tools/
│   ├── scraper.py          # Main scraper
│   ├── scrape-all.sh       # Run all scrapers
│   ├── requirements.txt    # Python deps
│   ├── venv/               # Virtual environment
│   └── README.md           # This file
├── jesse-cannon/
│   ├── articles/           # 146 markdown files
│   ├── metadata/           # JSON metadata
│   └── INDEX.md            # Catalog
├── chatprd-blog/
│   ├── articles/           # 119 markdown files
│   ├── metadata/
│   └── INDEX.md
└── lennys-podcast-transcripts/
    ├── episodes/           # 269 transcripts
    └── index/              # Topic index
```

---

## Updating Data

### Weekly Auto-Update (Recommended)

Add to crontab:
```bash
# Every Sunday at 2am
0 2 * * 0 /Users/nissimagent/Development/tools/scrape-all.sh >> ~/scrape.log 2>&1
```

Or use macOS launchd (see `/refresh` skill for setup).

### Manual Update

Just run:
```bash
~/Development/tools/scrape-all.sh
```

---

## Adding New Sources

### Example: Water & Music

1. **Identify structure:**
   - Is it a blog, newsletter, docs site?
   - What's the URL pattern?
   - Where's the archive?

2. **Extend scraper:**
   ```python
   class WaterMusicScraper(AdvisorScraper):
       def extract_article_urls(self, archive_url):
           # Custom logic for Water & Music
           pass

       def extract_article_content(self, url):
           # Extract their specific format
           pass
   ```

3. **Add to scrape-all.sh:**
   ```bash
   echo "3️⃣  Water & Music"
   python "$TOOLS_DIR/scraper.py" watermusic \
       https://waterandmusic.com \
       "$DEV_DIR/water-music"
   ```

---

## Troubleshooting

### "Module not found"
```bash
cd ~/Development/tools
source venv/bin/activate
pip install -r requirements.txt
```

### "Rate limited / 429 error"
- Script has built-in rate limiting (1 req/sec)
- If still rate limited, edit `rate_limit=1.0` → `rate_limit=2.0` in script
- Some sites may block scrapers - respect robots.txt

### "Extraction failed"
- Website structure may have changed
- Check the HTML manually
- Update scraper class for that source
- Open an issue or ask me to fix

---

## Token Economics

### Cost Comparison

**Without Scraper (Using WebFetch):**
- 265 articles × 3K tokens/article = 795K tokens
- Cost: ~$2.39 (input) + $9.56 (output) = **$11.95**
- Environmental: ~1.6 kWh (~800g CO2)

**With Scraper (Python Script):**
- Tokens used: **0**
- Cost: **$0**
- Environmental: ~0.1 kWh (~50g CO2, just computer running)

**Savings:** $11.95 + 750g CO2 per full scrape

**ROI:** ∞ (infinite - pays for itself instantly)

---

## Philosophy

This is the paradigm:
- **Build tools** (one-time token cost)
- **Run tools** (zero ongoing tokens)
- **Claude reads results** (minimal tokens)

Not:
- ~~Claude processes everything~~ (wasteful)

---

## Next Steps

1. **Run full scrape:**
   ```bash
   ~/Development/tools/scrape-all.sh
   ```

2. **Wait 10-20 minutes** (get coffee)

3. **Verify results:**
   ```bash
   cat ~/Development/jesse-cannon/INDEX.md
   cat ~/Development/chatprd-blog/INDEX.md
   ```

4. **Use advisors:**
   ```
   /ask-jesse [music marketing question]
   /ask-chatprd [AI workflow question]
   /ask-lenny [product strategy question]
   ```

5. **Set up weekly auto-update** (optional but recommended)

---

*Built with: Python, BeautifulSoup, Markdownify, Requests*
*Token cost: 0*
*Philosophy: Code > Tokens*
