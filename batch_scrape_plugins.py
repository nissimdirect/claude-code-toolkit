#!/usr/bin/env python3
"""
Batch scrape all 30 plugin companies
"""

import subprocess
import time
from pathlib import Path

# Company data
COMPANIES = [
    ("FabFilter", "https://www.fabfilter.com"),
    ("Valhalla DSP", "https://valhalladsp.com"),
    ("Soundtoys", "https://www.soundtoys.com"),
    ("Baby Audio", "https://babyaud.io"),
    ("Minimal Audio", "https://www.minimalaudio.com"),
    ("iZotope", "https://www.izotope.com"),
    ("Plugin Alliance", "https://www.plugin-alliance.com"),
    ("Slate Digital", "https://slatedigital.com"),
    ("Native Instruments", "https://www.native-instruments.com"),
    ("Waves Audio", "https://www.waves.com"),
    ("Universal Audio", "https://www.uaudio.com"),
    ("Arturia", "https://www.arturia.com"),
    ("Output", "https://output.com"),
    ("Kilohearts", "https://kilohearts.com"),
    ("Spectrasonics", "https://www.spectrasonics.net"),
    ("Celemony", "https://www.celemony.com"),
    ("Softube", "https://www.softube.com"),
    ("U-he", "https://u-he.com"),
    ("Tokyo Dawn Records", "https://www.tokyodawn.net"),
    ("Auburn Sounds", "https://www.auburnsounds.com"),
    ("Sonnox", "https://www.sonnox.com"),
    ("DMG Audio", "https://dmgaudio.com"),
    ("Audio Damage", "https://audiodamage.com"),
    ("Klevgrand", "https://klevgrand.com"),
    ("Newfangled Audio", "https://www.eventideaudio.com/newfangled"),
    ("Unfiltered Audio", "https://unfilteredaudio.com"),
    ("Denise Audio", "https://www.denise.io"),
    ("Lunacy Audio", "https://lunacyaudio.com"),
    ("Goodhertz", "https://goodhertz.com"),
    ("Melda Production", "https://www.meldaproduction.com"),
]

OUTPUT_BASE = Path.home() / "Documents/Obsidian/VST-Research"
VENV_PYTHON = Path.home() / "Development/tools/venv/bin/python"
SCRAPER = Path.home() / "Development/tools/plugin_doc_scraper.py"

OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

success = 0
failed = 0

print("=" * 50)
print("Plugin Documentation Batch Scraper")
print("=" * 50)
print(f"Total companies: {len(COMPANIES)}")
print(f"Output: {OUTPUT_BASE}")
print()

for i, (name, url) in enumerate(COMPANIES, 1):
    print(f"\n[{i}/{len(COMPANIES)}] Scraping: {name}")
    print(f"URL: {url}")

    # Create safe directory name
    dir_name = name.lower().replace(" ", "-").replace("(", "").replace(")", "")
    output_dir = OUTPUT_BASE / dir_name

    # Run scraper
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), str(SCRAPER), name, url, str(output_dir)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per company
        )

        if result.returncode == 0:
            print(f"✅ Success: {name}")
            success += 1
        else:
            print(f"⚠️  Failed: {name}")
            print(f"Error: {result.stderr[:200]}")
            failed += 1

    except subprocess.TimeoutExpired:
        print(f"⏱️  Timeout: {name} (took >5 minutes)")
        failed += 1
    except Exception as e:
        print(f"❌ Error: {name} - {e}")
        failed += 1

    # Rate limiting between companies
    if i < len(COMPANIES):
        print("⏳ Waiting 5 seconds...")
        time.sleep(5)

print("\n" + "=" * 50)
print("Batch Scraping Complete!")
print("=" * 50)
print(f"Total: {len(COMPANIES)}")
print(f"✅ Success: {success}")
print(f"⚠️  Failed: {failed}")
print(f"\nResults: {OUTPUT_BASE}")

# Create summary
summary_file = OUTPUT_BASE / "SCRAPING-SUMMARY.md"
with open(summary_file, 'w') as f:
    f.write(f"# Plugin Documentation Scraping Summary\n\n")
    f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"**Total Companies:** {len(COMPANIES)}\n")
    f.write(f"**Successful:** {success}\n")
    f.write(f"**Failed:** {failed}\n\n")
    f.write("---\n\n## Companies Scraped\n\n")

    for dir_path in sorted(OUTPUT_BASE.iterdir()):
        if dir_path.is_dir() and dir_path.name != "valhalla-dsp-test":
            index_file = dir_path / "INDEX.md"
            if index_file.exists():
                f.write(f"- [{dir_path.name}]({dir_path.name}/INDEX.md)\n")

print(f"\nSummary: {summary_file}")
