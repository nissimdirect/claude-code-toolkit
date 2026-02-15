#!/usr/bin/env python3
"""Knowledge Base Loader - Injects advisor knowledge into agent prompts.

Maps advisor names to their scraped knowledge base directories,
searches for relevant articles, and returns formatted excerpts
ready for prompt injection.

Usage:
    # From CLI
    python3 kb_loader.py search --advisor lenny --query "product market fit"
    python3 kb_loader.py search --advisor cherie --query "AI music tools"
    python3 kb_loader.py list                    # Show all advisors and article counts
    python3 kb_loader.py context --advisor lenny --query "pricing" --max-tokens 4000

    # From Python
    from kb_loader import KBLoader
    loader = KBLoader()
    context = loader.get_context("lenny", "product market fit", max_tokens=4000)
"""

import subprocess
import re
import sys
from pathlib import Path
from typing import Optional


# ── Advisor → Knowledge Base Mapping ────────────────────────────────
ADVISORS = {
    "lenny": {
        "name": "Lenny Rachitsky",
        "source": "Lenny's Podcast + Full UX Stack (Norman, NNGroup, Baymard, LukeW, Laws of UX, UX Myths, Deceptive Design, ALA, Smashing)",
        "article_dirs": [
            Path("~/Development/lennys-podcast-transcripts/episodes").expanduser(),
            Path("~/Development/don-norman/articles").expanduser(),
            Path("~/Development/nngroup/articles").expanduser(),
            Path("~/Development/ux-design/baymard/articles").expanduser(),
            Path("~/Development/ux-design/lukew/articles").expanduser(),
            Path("~/Development/ux-design/lawsofux/articles").expanduser(),
            Path("~/Development/ux-design/uxmyths/articles").expanduser(),
            Path("~/Development/ux-design/deceptive-design/articles").expanduser(),
            Path("~/Development/ux-design/alistapart/articles").expanduser(),
            Path("~/Development/ux-design/smashingmag/articles").expanduser(),
        ],
        "index_dir": Path("~/Development/lennys-podcast-transcripts/index").expanduser(),
        "pattern": "*.md",
        "article_count": 4006,  # Verified 2026-02-09
        "excerpt_lines": 80,  # Transcripts are huge, take more context
    },
    "music-biz": {
        "name": "Music Business (Cherie Hu + Jesse Cannon + Ari Herstand + Bandzoogle Blog)",
        "source": "Water & Music + Music Marketing Trends + Ari's Take + DMN + Bandzoogle Blog + Guest Articles",
        "article_dirs": [
            Path("~/Development/cherie-hu/articles").expanduser(),
            Path("~/Development/jesse-cannon/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand-dmn/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand-guest/articles").expanduser(),
            # Full Bandzoogle blog (direct-to-fan marketing, artist websites)
            Path("~/Development/music-marketing/bandzoogle-blog/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 3068,  # 1710 (cherie) + 148 (jesse) + 466 (ari) + 265 (dmn) + 13 (guest) + 466 (bandzoogle blog)
        "excerpt_lines": 40,
    },
    "chatprd": {
        "name": "Claire Vo / ChatPRD",
        "source": "ChatPRD Blog",
        "article_dirs": [Path("~/Development/chatprd-blog/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 119,
        "excerpt_lines": 40,
    },
    "indie-trinity": {
        "name": "Pieter Levels + Justin Welsh + Daniel Vassallo",
        "source": "Indie Hackers",
        "article_dirs": [
            Path("~/Development/indie-hackers/pieter-levels/articles").expanduser(),
            Path("~/Development/indie-hackers/justin-welsh/articles").expanduser(),
            Path("~/Development/indie-hackers/daniel-vassallo/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 160,
        "excerpt_lines": 40,
    },
    "cto": {
        "name": "CTO / Technical Knowledge",
        "source": "Plugin Dev Blogs (Valhalla, Airwindows, FabFilter) + Circuit Modeling KB + CTO Leaders",
        "article_dirs": [
            # Plugin dev blogs (core DSP knowledge)
            Path("~/Development/plugin-devs/valhalla-dsp/articles").expanduser(),
            Path("~/Development/plugin-devs/airwindows/articles").expanduser(),
            Path("~/Development/plugin-devs/fabfilter/articles").expanduser(),
            # Circuit modeling (VA, WDF, SPICE, ML, schematics, clippers)
            Path("~/Development/circuit-modeling/articles/wdf").expanduser(),
            Path("~/Development/circuit-modeling/articles/va").expanduser(),
            Path("~/Development/circuit-modeling/articles/spice").expanduser(),
            Path("~/Development/circuit-modeling/articles/nodal").expanduser(),
            Path("~/Development/circuit-modeling/articles/ml").expanduser(),
            Path("~/Development/circuit-modeling/articles/whitebox").expanduser(),
            Path("~/Development/circuit-modeling/articles/clippers").expanduser(),
            # CTO thought leaders (Wave 1-3 scrape targets)
            Path("~/Development/cto-leaders/melatonin/articles").expanduser(),
            Path("~/Development/cto-leaders/pamplejuce/articles").expanduser(),
            Path("~/Development/cto-leaders/ross-bencina/articles").expanduser(),
            Path("~/Development/cto-leaders/patrick-mckenzie/articles").expanduser(),
            Path("~/Development/cto-leaders/julia-evans/articles").expanduser(),
            Path("~/Development/cto-leaders/wolfsound/articles").expanduser(),
            Path("~/Development/cto-leaders/getdunne/articles").expanduser(),
            Path("~/Development/cto-leaders/simon-willison/articles").expanduser(),
            Path("~/Development/cto-leaders/kent-beck/articles").expanduser(),
            Path("~/Development/cto-leaders/swyx/articles").expanduser(),
            # Security leaders
            Path("~/Development/security-leaders/daniel-miessler/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 6057,  # Verified 2026-02-09 (plugin-devs 637 + circuit 29 + Wave 1: 194 + Wave 2: julia-evans 589, miessler 2812, wolfsound 63, getdunne 30 + Wave 3: willison 500, kent-beck 407, swyx 796)
        "excerpt_lines": 40,
    },
    "obsidian-docs": {
        "name": "Obsidian Documentation",
        "source": "Obsidian Help Docs (App Usage)",
        "article_dirs": [
            Path("~/Development/obsidian-docs/raw").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 165,
        "excerpt_lines": 40,
    },
    "don-norman": {
        "name": "Don Norman + UX Research Frontier",
        "source": "jnd.org + NNGroup + Baymard + LukeW + Laws of UX + UX Myths + Deceptive Design + A List Apart + Smashing Mag",
        "article_dirs": [
            Path("~/Development/don-norman/articles").expanduser(),
            Path("~/Development/nngroup/articles").expanduser(),
            Path("~/Development/ux-design/baymard/articles").expanduser(),
            Path("~/Development/ux-design/lukew/articles").expanduser(),
            Path("~/Development/ux-design/lawsofux/articles").expanduser(),
            Path("~/Development/ux-design/uxmyths/articles").expanduser(),
            Path("~/Development/ux-design/deceptive-design/articles").expanduser(),
            Path("~/Development/ux-design/alistapart/articles").expanduser(),
            Path("~/Development/ux-design/smashingmag/articles").expanduser(),
            Path("~/Development/tools/kb/accessibility").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 3714,  # Verified 2026-02-09
        "excerpt_lines": 40,
    },
    "nngroup": {
        "name": "Nielsen Norman Group",
        "source": "nngroup.com Articles",
        "article_dirs": [Path("~/Development/nngroup/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 273,
        "excerpt_lines": 40,
    },
    # ── UX Frontier Individual Sources ──
    "baymard": {
        "name": "Baymard Institute",
        "source": "Baymard UX Research (E-commerce UX)",
        "article_dirs": [Path("~/Development/ux-design/baymard/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 471,
        "excerpt_lines": 40,
    },
    "lukew": {
        "name": "Luke Wroblewski",
        "source": "LukeW Ideation + Inspiration",
        "article_dirs": [Path("~/Development/ux-design/lukew/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 2118,
        "excerpt_lines": 40,
    },
    "lawsofux": {
        "name": "Jon Yablonski / Laws of UX",
        "source": "Laws of UX (Psychology-backed design principles)",
        "article_dirs": [Path("~/Development/ux-design/lawsofux/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 45,
        "excerpt_lines": 60,
    },
    "uxmyths": {
        "name": "UX Myths",
        "source": "UX Myths (Debunking common UX misconceptions)",
        "article_dirs": [Path("~/Development/ux-design/uxmyths/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 34,
        "excerpt_lines": 40,
    },
    "deceptive-design": {
        "name": "Deceptive Design (Harry Brignull)",
        "source": "Deceptive Design (Dark patterns taxonomy)",
        "article_dirs": [Path("~/Development/ux-design/deceptive-design/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 18,
        "excerpt_lines": 60,
    },
    "alistapart": {
        "name": "A List Apart",
        "source": "A List Apart (Web design + UX essays)",
        "article_dirs": [Path("~/Development/ux-design/alistapart/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 281,
        "excerpt_lines": 40,
    },
    "smashingmag": {
        "name": "Smashing Magazine",
        "source": "Smashing Magazine (UX Design category)",
        "article_dirs": [Path("~/Development/ux-design/smashingmag/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 114,
        "excerpt_lines": 40,
    },
    # ── Art Direction Sources ──
    "art-director": {
        "name": "Art Director (Brand Identity + Visual Design + Creative Philosophy)",
        "source": "Brand New + Design Observer + Creative Review + Hyperallergic + e-flux + Brian Eno Interviews + It's Nice That + Creative Boom + Fonts In Use + The Brand Identity",
        "article_dirs": [
            Path("~/Development/art-direction/brandnew/articles").expanduser(),
            Path("~/Development/art-direction/designobserver/articles").expanduser(),
            Path("~/Development/art-direction/creativereview/articles").expanduser(),
            Path("~/Development/art-criticism/hyperallergic/articles").expanduser(),
            Path("~/Development/art-criticism/e-flux-journal/articles").expanduser(),
            # Brian Eno creative philosophy (generative systems, oblique strategies, ambient thinking)
            Path("~/Development/creative-interviews/brian-eno/articles").expanduser(),
            Path("~/Development/creative-interviews/brian-eno-enoweb/articles").expanduser(),
            # New art direction sources (scrapers in progress)
            Path("~/Development/art-direction/its-nice-that/articles").expanduser(),
            Path("~/Development/creative-boom/articles").expanduser(),
            Path("~/Development/fonts-in-use/articles").expanduser(),
            Path("~/Development/art-direction/the-brand-identity/articles").expanduser(),
            Path("~/Development/tools/kb/accessibility").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 6379,  # 6212 + 12 (eno more-dark-than-shark) + 155 (eno enoweb)
        "excerpt_lines": 40,
    },
    "brandnew": {
        "name": "Brand New / Under Consideration",
        "source": "Brand New (Brand identity critiques)",
        "article_dirs": [Path("~/Development/art-direction/brandnew/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 4062,
        "excerpt_lines": 40,
    },
    "designobserver": {
        "name": "Design Observer",
        "source": "Design Observer (Design criticism + culture)",
        "article_dirs": [Path("~/Development/art-direction/designobserver/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 12,
        "excerpt_lines": 40,
    },
    "creativereview": {
        "name": "Creative Review",
        "source": "Creative Review (Advertising + branding)",
        "article_dirs": [Path("~/Development/art-direction/creativereview/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 12,
        "excerpt_lines": 40,
    },
    "valhalla": {
        "name": "Sean Costello / Valhalla DSP",
        "source": "Valhalla DSP Blog",
        "article_dirs": [Path("~/Development/plugin-devs/valhalla-dsp/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 214,
        "excerpt_lines": 40,
    },
    "airwindows": {
        "name": "Chris Johnson / Airwindows",
        "source": "Airwindows Blog",
        "article_dirs": [Path("~/Development/plugin-devs/airwindows/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 400,
        "excerpt_lines": 40,
    },
    "fabfilter": {
        "name": "FabFilter",
        "source": "FabFilter Learn",
        "article_dirs": [Path("~/Development/plugin-devs/fabfilter/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 23,
        "excerpt_lines": 60,  # Educational content, take more context
    },
    "eflux": {
        "name": "e-flux Journal",
        "source": "e-flux Journal (Art Critical Theory)",
        "article_dirs": [Path("~/Development/art-criticism/e-flux-journal/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 1559,
        "excerpt_lines": 40,
    },
    "hyperallergic": {
        "name": "Hyperallergic",
        "source": "Hyperallergic (Art Criticism & News)",
        "article_dirs": [Path("~/Development/art-criticism/hyperallergic/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 538,
        "excerpt_lines": 40,
    },
    "creative-capital": {
        "name": "Creative Capital",
        "source": "Creative Capital Awardees",
        "article_dirs": [Path("~/Development/art-criticism/creative-capital/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 70,
        "excerpt_lines": 40,
    },
    "ubuweb": {
        "name": "UbuWeb Papers",
        "source": "UbuWeb (Avant-Garde Theory)",
        "article_dirs": [Path("~/Development/art-criticism/ubuweb-papers/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 260,
        "excerpt_lines": 60,  # Theory texts deserve more context
    },
    "stanford-aesthetics": {
        "name": "Stanford Encyclopedia - Aesthetics",
        "source": "Stanford Encyclopedia of Philosophy",
        "article_dirs": [Path("~/Development/art-criticism/stanford-aesthetics/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 33,
        "excerpt_lines": 80,  # Deep philosophy entries
    },
    "marxists-aesthetics": {
        "name": "Marxists.org Art & Aesthetics",
        "source": "Marxists.org (Critical Theory)",
        "article_dirs": [Path("~/Development/art-criticism/marxists-aesthetics/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 0,  # Hub page needs two-level scrape — TODO
        "excerpt_lines": 60,
    },
    "situationist": {
        "name": "Situationist International",
        "source": "Bureau of Public Secrets (SI Texts)",
        "article_dirs": [Path("~/Development/art-criticism/situationist-international/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 88,
        "excerpt_lines": 60,
    },
    "creative-capital-awardees": {
        "name": "Creative Capital Awardees",
        "source": "Creative Capital (Grant Recipients)",
        "article_dirs": [Path("~/Development/art-criticism/creative-capital-awardees/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 831,
        "excerpt_lines": 40,
    },
    "artadia": {
        "name": "Artadia Awardees",
        "source": "Artadia Awards (Grant Recipients)",
        "article_dirs": [Path("~/Development/art-criticism/artadia-awardees/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 305,
        "excerpt_lines": 40,
    },
    "usa-fellows": {
        "name": "United States Artists Fellows",
        "source": "USA Fellows (Grant Recipients)",
        "article_dirs": [Path("~/Development/art-criticism/usa-fellows/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 1038,
        "excerpt_lines": 40,
    },
    "bomb-magazine": {
        "name": "BOMB Magazine",
        "source": "BOMB Magazine (Artist Interviews)",
        "article_dirs": [Path("~/Development/art-criticism/bomb-magazine/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 1500,
        "excerpt_lines": 50,
    },
    "texte-zur-kunst": {
        "name": "Texte zur Kunst",
        "source": "Texte zur Kunst (Critical Theory Journal)",
        "article_dirs": [Path("~/Development/art-criticism/texte-zur-kunst/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 801,
        "excerpt_lines": 50,
    },
    "momus": {
        "name": "Momus",
        "source": "Momus (Art Criticism)",
        "article_dirs": [Path("~/Development/art-criticism/momus/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 1076,
        "excerpt_lines": 40,
    },
    "atrium": {
        "name": "Atrium (Art Critical Theory + Grants + Publications)",
        "source": "e-flux + Hyperallergic + Creative Capital + UbuWeb + Stanford + Situationist + CC Awardees + Artadia + USA Fellows + BOMB + Texte zur Kunst + Momus",
        "article_dirs": [
            # Original 3
            Path("~/Development/art-criticism/e-flux-journal/articles").expanduser(),
            Path("~/Development/art-criticism/hyperallergic/articles").expanduser(),
            Path("~/Development/art-criticism/creative-capital/articles").expanduser(),
            # Critical theory
            Path("~/Development/art-criticism/ubuweb-papers/articles").expanduser(),
            Path("~/Development/art-criticism/stanford-aesthetics/articles").expanduser(),
            Path("~/Development/art-criticism/situationist-international/articles").expanduser(),
            # Grant recipients
            Path("~/Development/art-criticism/creative-capital-awardees/articles").expanduser(),
            Path("~/Development/art-criticism/artadia-awardees/articles").expanduser(),
            Path("~/Development/art-criticism/usa-fellows/articles").expanduser(),
            # Publications
            Path("~/Development/art-criticism/bomb-magazine/articles").expanduser(),
            Path("~/Development/art-criticism/texte-zur-kunst/articles").expanduser(),
            Path("~/Development/art-criticism/momus/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 8099,  # Total across 12 sources (updated 2026-02-08: eflux 1559, hyperallergic 538)
        "excerpt_lines": 50,
    },
    "plugin-devs": {
        "name": "Plugin Developer Blogs",
        "source": "Valhalla + Airwindows + FabFilter",
        "article_dirs": [
            Path("~/Development/plugin-devs/valhalla-dsp/articles").expanduser(),
            Path("~/Development/plugin-devs/airwindows/articles").expanduser(),
            Path("~/Development/plugin-devs/fabfilter/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 637,  # 214 + 400 + 23
        "excerpt_lines": 40,
    },
    # ── Circuit Modeling (VA, WDF, SPICE, ML, Spring Reverb) ──
    "circuit-modeling": {
        "name": "Circuit Modeling (VA, WDF, SPICE, Neural, Spring Reverb, Clippers)",
        "source": "DAFx papers, ElectroSmash, CCRMA, KVR, GitHub repos (chowdsp_wdf, RTNeural, NAM, PeakEater, etc.)",
        "article_dirs": [
            Path("~/Development/circuit-modeling/articles/wdf").expanduser(),
            Path("~/Development/circuit-modeling/articles/va").expanduser(),
            Path("~/Development/circuit-modeling/articles/spice").expanduser(),
            Path("~/Development/circuit-modeling/articles/nodal").expanduser(),
            Path("~/Development/circuit-modeling/articles/newton-raphson").expanduser(),
            Path("~/Development/circuit-modeling/articles/schematics").expanduser(),
            Path("~/Development/circuit-modeling/articles/distortion").expanduser(),
            Path("~/Development/circuit-modeling/articles/space-echo").expanduser(),
            Path("~/Development/circuit-modeling/articles/spring-reverb").expanduser(),
            Path("~/Development/circuit-modeling/articles/ml").expanduser(),
            Path("~/Development/circuit-modeling/articles/whitebox").expanduser(),
            Path("~/Development/circuit-modeling/articles/textbooks").expanduser(),
            Path("~/Development/circuit-modeling/articles/juce").expanduser(),
            Path("~/Development/circuit-modeling/articles/clippers").expanduser(),
            Path("~/Development/circuit-modeling/forums").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 85,  # Verified 2026-02-09
        "excerpt_lines": 60,
    },
    # ── Music Composition + Production ──
    "music-composer": {
        "name": "Music Composer (DnB Production + Sound Design + Music Tech)",
        "source": "Airwindows + Valhalla DSP + FabFilter + Music Biz (Cherie/Jesse/Ari) + Splice Blog + Attack Magazine",
        "article_dirs": [
            # Core audio/sound design
            Path("~/Development/plugin-devs/airwindows/articles").expanduser(),
            Path("~/Development/plugin-devs/valhalla-dsp/articles").expanduser(),
            Path("~/Development/plugin-devs/fabfilter/articles").expanduser(),
            # Music business context (shared with music-biz)
            Path("~/Development/cherie-hu/articles").expanduser(),
            Path("~/Development/jesse-cannon/articles").expanduser(),
            # Wave 4: Music production (electronic, DnB, tutorials)
            Path("~/Development/music-production/splice/articles").expanduser(),
            Path("~/Development/music-production/attack-magazine/articles").expanduser(),
            # Wave 5: Budget production, free plugins, tutorials
            Path("~/Development/music-production/bedroom-producers-blog/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 9904,  # 400 + 214 + 23 + 1710 + 148 + 1571 (splice) + 3838 (attack) + 2000 (BPB)
        "excerpt_lines": 50,
    },
    "label": {
        "name": "Record Label (Music Business + Hypebot + MBW + Bandzoogle Blog)",
        "source": "Music Biz (Cherie + Jesse + Ari) + Hypebot + Music Business Worldwide + Bandzoogle Blog",
        "article_dirs": [
            # All music-biz sources
            Path("~/Development/cherie-hu/articles").expanduser(),
            Path("~/Development/jesse-cannon/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand-dmn/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand-guest/articles").expanduser(),
            # Bandzoogle blog (direct-to-fan, artist websites)
            Path("~/Development/music-marketing/bandzoogle-blog/articles").expanduser(),
            # Hypebot (label-specific: indie news, streaming, deals)
            Path("~/Development/music-business/hypebot/articles").expanduser(),
            # Music Business Worldwide (streaming economics, label deals)
            Path("~/Development/music-business/music-biz-worldwide/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 7068,  # 3068 (music-biz) + 2000 (hypebot) + 2000 (mbw)
        "excerpt_lines": 40,
    },
    "audio-production": {
        "name": "Audio Production (DSP + Sound Design + Music Tech + Circuit Modeling)",
        "source": "Plugin Devs + Cherie Hu + Circuit Modeling KB (spring reverb, distortion, schematics)",
        "article_dirs": [
            Path("~/Development/plugin-devs/valhalla-dsp/articles").expanduser(),
            Path("~/Development/plugin-devs/airwindows/articles").expanduser(),
            Path("~/Development/plugin-devs/fabfilter/articles").expanduser(),
            Path("~/Development/cherie-hu/articles").expanduser(),
            # Circuit modeling (production-relevant: reverb, distortion, schematics)
            Path("~/Development/circuit-modeling/articles/spring-reverb").expanduser(),
            Path("~/Development/circuit-modeling/articles/distortion").expanduser(),
            Path("~/Development/circuit-modeling/articles/schematics").expanduser(),
            Path("~/Development/circuit-modeling/articles/space-echo").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 2380,  # Verified 2026-02-09
        "excerpt_lines": 50,
    },
    # ── Lyric Analyst + Ghostwriter ──
    "lyric-analyst": {
        "name": "Lyric Analyst (Poetry + Prosody Education)",
        "source": "Poetry Foundation + Poets.org + Songwriting Education",
        "article_dirs": [
            Path("~/Development/lyric-analyst/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 3,  # 3 educational guides (prosody, rhyme-scheme, flow-taxonomy)
        "excerpt_lines": 60,
    },
    "ghostwriter": {
        "name": "Ghostwriter (Lyrics KB + Analysis + Songwriting Education)",
        "source": "Genius Lyrics (enriched) + Songwriting Education",
        "article_dirs": [
            Path("~/Development/ghostwriter/articles").expanduser(),
            Path("~/Development/ghostwriter/education").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 3,  # 3 educational guides + lyrics populated by genius_scraper.py
        "excerpt_lines": 50,
    },
    # ── Marketing Hacker (SEO, GEO, Growth) ──
    "marketing-hacker": {
        "name": "Marketing Hacker (SEO + AI SEO/GEO + Growth Hacking)",
        "source": "Kevin Indig, SparkToro, Arvid Kahl, Backlinko, Zyppy, Eli Schwartz, GEO Research",
        "article_dirs": [
            Path("~/Development/marketing-hacker/articles").expanduser(),
            Path("~/Development/marketing-hacker/zyppy/articles").expanduser(),
            Path("~/Development/marketing-hacker/arvid-kahl/articles").expanduser(),
            Path("~/Development/marketing-hacker/sparktoro/articles").expanduser(),
            Path("~/Development/marketing-hacker/kevin-indig/articles").expanduser(),
            Path("~/Development/marketing-hacker/backlinko/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 1776,  # Zyppy: 26, Arvid Kahl: 436, SparkToro: 442, Kevin Indig: 426, Backlinko: 446
        "excerpt_lines": 50,
    },
}

# Aliases for flexible matching
ALIASES = {
    "lenny": "lenny",
    "ask-lenny": "lenny",
    "lennys": "lenny",
    "music-biz": "music-biz",
    "cherie": "music-biz",
    "ask-cherie": "music-biz",
    "cherie-hu": "music-biz",
    "water-and-music": "music-biz",
    "jesse": "music-biz",
    "ask-jesse": "music-biz",
    "jesse-cannon": "music-biz",
    "chatprd": "chatprd",
    "ask-chatprd": "chatprd",
    "claire-vo": "chatprd",
    "indie-trinity": "indie-trinity",
    "ask-indie-trinity": "indie-trinity",
    "pieter": "indie-trinity",
    "pieter-levels": "indie-trinity",
    "justin": "indie-trinity",
    "justin-welsh": "indie-trinity",
    "daniel": "indie-trinity",
    "daniel-vassallo": "indie-trinity",
    "cto": "cto",
    # Circuit Modeling
    "circuit-modeling": "circuit-modeling",
    "circuit": "circuit-modeling",
    "wdf": "circuit-modeling",
    "wave-digital": "circuit-modeling",
    "spice": "circuit-modeling",
    "virtual-analog": "circuit-modeling",
    "va-modeling": "circuit-modeling",
    "spring-reverb": "circuit-modeling",
    "pedal-schematics": "circuit-modeling",
    "neural-amp": "circuit-modeling",
    "nodal-analysis": "circuit-modeling",
    "clipper": "circuit-modeling",
    "clippers": "circuit-modeling",
    "waveshaper": "circuit-modeling",
    "soft-clipping": "circuit-modeling",
    "hard-clipping": "circuit-modeling",
    "saturation": "circuit-modeling",
    "diode-clipper": "circuit-modeling",
    "adaa": "circuit-modeling",
    # Obsidian docs
    "obsidian-docs": "obsidian-docs",
    "obsidian": "obsidian-docs",
    "obsidian-help": "obsidian-docs",
    "vault": "obsidian-docs",
    # Don Norman / UX
    "don-norman": "don-norman",
    "don": "don-norman",
    "norman": "don-norman",
    "jnd": "don-norman",
    "ux": "don-norman",
    # NNGroup
    "nngroup": "nngroup",
    "nn-group": "nngroup",
    "nielsen-norman": "nngroup",
    # UX Frontier sources
    "baymard": "baymard",
    "baymard-institute": "baymard",
    "ecommerce-ux": "baymard",
    "lukew": "lukew",
    "luke": "lukew",
    "luke-wroblewski": "lukew",
    "wroblewski": "lukew",
    "lawsofux": "lawsofux",
    "laws-of-ux": "lawsofux",
    "yablonski": "lawsofux",
    "uxmyths": "uxmyths",
    "ux-myths": "uxmyths",
    "deceptive-design": "deceptive-design",
    "deceptive": "deceptive-design",
    "dark-patterns": "deceptive-design",
    "brignull": "deceptive-design",
    "alistapart": "alistapart",
    "ala": "alistapart",
    "a-list-apart": "alistapart",
    "smashingmag": "smashingmag",
    "smashing": "smashingmag",
    "smashing-magazine": "smashingmag",
    # Art direction sources
    "art-director": "art-director",
    "art-direction": "art-director",
    "brand-identity": "art-director",
    "visual-design": "art-director",
    "brandnew": "brandnew",
    "brand-new": "brandnew",
    "underconsideration": "brandnew",
    "armin-vit": "brandnew",
    "designobserver": "designobserver",
    "design-observer": "designobserver",
    "bierut": "designobserver",
    "creativereview": "creativereview",
    "creative-review": "creativereview",
    # CTO thought leaders
    "melatonin": "cto",
    "melatonin-dev": "cto",
    "code-signing": "cto",
    "notarization": "cto",
    "pamplejuce": "cto",
    "ross-bencina": "cto",
    "bencina": "cto",
    "lock-free": "cto",
    "real-time-audio": "cto",
    "patrick-mckenzie": "cto",
    "patio11": "cto",
    "kalzumeus": "cto",
    "bitsaboutmoney": "cto",
    "julia-evans": "cto",
    "jvns": "cto",
    "b0rk": "cto",
    "wolfsound": "cto",
    "wolf-sound": "cto",
    "getdunne": "cto",
    "simon-willison": "cto",
    "simonw": "cto",
    "kent-beck": "cto",
    "tidy-first": "cto",
    "swyx": "cto",
    "latent-space": "cto",
    # Security leaders
    "daniel-miessler": "cto",
    "miessler": "cto",
    "ai-security": "cto",
    "red-team": "cto",
    "fabric": "cto",
    # Plugin devs
    "valhalla": "valhalla",
    "valhalla-dsp": "valhalla",
    "sean-costello": "valhalla",
    "airwindows": "airwindows",
    "chris-johnson": "airwindows",
    "fabfilter": "fabfilter",
    "fab-filter": "fabfilter",
    "plugin-devs": "plugin-devs",
    "plugin-developers": "plugin-devs",
    # Art / Atrium
    "eflux": "eflux",
    "e-flux": "eflux",
    "hyperallergic": "hyperallergic",
    "creative-capital": "creative-capital",
    "atrium": "atrium",
    "art-criticism": "atrium",
    "art-grants": "atrium",
    "art-theory": "atrium",
    "critical-theory": "atrium",
    "grants": "atrium",
    # New individual sources
    "ubuweb": "ubuweb",
    "ubu-web": "ubuweb",
    "ubu": "ubuweb",
    "stanford-aesthetics": "stanford-aesthetics",
    "stanford": "stanford-aesthetics",
    "sep": "stanford-aesthetics",
    "marxists": "marxists-aesthetics",
    "marxists-aesthetics": "marxists-aesthetics",
    "marxist": "marxists-aesthetics",
    "situationist": "situationist",
    "situationist-international": "situationist",
    "debord": "situationist",
    "spectacle": "situationist",
    "creative-capital-awardees": "creative-capital-awardees",
    "cc-awardees": "creative-capital-awardees",
    "artadia": "artadia",
    "usa-fellows": "usa-fellows",
    "usa": "usa-fellows",
    "united-states-artists": "usa-fellows",
    "bomb": "bomb-magazine",
    "bomb-magazine": "bomb-magazine",
    "texte": "texte-zur-kunst",
    "texte-zur-kunst": "texte-zur-kunst",
    "tzk": "texte-zur-kunst",
    "momus": "momus",
    # Music Composition + Production
    "music-composer": "music-composer",
    "composer": "music-composer",
    "composition": "music-composer",
    "dnb": "music-composer",
    "drum-and-bass": "music-composer",
    "music-production": "music-composer",
    "splice": "music-composer",
    "splice-blog": "music-composer",
    "attack-magazine": "music-composer",
    "attack": "music-composer",
    # Record Label
    "label": "label",
    "record-label": "label",
    "music-business": "label",
    "music-industry": "label",
    "distribution": "label",
    "hypebot": "label",
    # Ari Herstand
    "ari-herstand": "music-biz",
    "ari": "music-biz",
    "aristake": "music-biz",
    "bandzoogle": "music-biz",
    "sonicbids": "music-biz",
    # Music Business Worldwide
    "mbw": "label",
    "music-business-worldwide": "label",
    # Brian Eno / EnoWeb → Art Director (creative philosophy)
    "enoweb": "art-director",
    "eno": "art-director",
    "brian-eno": "art-director",
    # Audio Production
    "audio-production": "audio-production",
    "audio": "audio-production",
    "dsp": "audio-production",
    "sound-design": "audio-production",
    "mixing": "audio-production",
    "mastering": "audio-production",
    # Creative Interviews → Art Director
    "creative-interviews": "art-director",
    "interviews": "art-director",
    "eno-interviews": "art-director",
    "creative-independent": "art-director",
    # Lyric Analyst
    "lyric-analyst": "lyric-analyst",
    "lyrics": "lyric-analyst",
    "prosody": "lyric-analyst",
    "rhyme-scheme": "lyric-analyst",
    "syllables": "lyric-analyst",
    "meter": "lyric-analyst",
    "poetry": "lyric-analyst",
    # Ghostwriter
    "ghostwriter": "ghostwriter",
    "ghostwrite": "ghostwriter",
    "songwriting": "ghostwriter",
    "rap-lyrics": "ghostwriter",
    "verse-writing": "ghostwriter",
    # Marketing Hacker
    "marketing-hacker": "marketing-hacker",
    "marketing": "marketing-hacker",
    "seo": "marketing-hacker",
    "ai-seo": "marketing-hacker",
    "geo": "marketing-hacker",
    "growth-hack": "marketing-hacker",
    "growth-hacking": "marketing-hacker",
    "zero-click": "marketing-hacker",
    "backlinks": "marketing-hacker",
    "organic-traffic": "marketing-hacker",
    "programmatic-seo": "marketing-hacker",
    "kevin-indig": "marketing-hacker",
    "sparktoro": "marketing-hacker",
    "arvid-kahl": "marketing-hacker",
    "backlinko": "marketing-hacker",
    "zyppy": "marketing-hacker",
    "cyrus-shepard": "marketing-hacker",
    "brian-dean": "marketing-hacker",
    "content-marketing": "marketing-hacker",
    "guerrilla-marketing": "marketing-hacker",
    # Bandzoogle Blog (full blog → music-biz, different from guest posts)
    "bandzoogle-blog": "music-biz",
}


class KBLoader:
    """Knowledge Base Loader - searches advisor KBs and returns context."""

    def __init__(self):
        self.advisors = ADVISORS
        self.aliases = ALIASES

    def resolve_advisor(self, name: str) -> Optional[str]:
        """Resolve advisor name/alias to canonical key."""
        key = name.lower().strip()
        return self.aliases.get(key)

    def search(self, advisor: str, query: str, max_results: int = 5) -> list[dict]:
        """Search an advisor's KB for articles matching query.

        Returns list of dicts with: path, title, author, relevance_score, excerpt
        """
        key = self.resolve_advisor(advisor)
        if not key:
            return []

        config = self.advisors[key]
        matches = []

        # Split query into search terms
        terms = query.lower().split()

        for article_dir in config["article_dirs"]:
            if not article_dir.exists():
                continue

            # Use ripgrep for fast search (fall back to grep)
            import re as _re
            for term in terms:
                # Escape regex special chars to prevent ReDoS / unintended matches
                safe_term = _re.escape(term)
                try:
                    result = subprocess.run(
                        ["rg", "-l", "-i", safe_term, str(article_dir)],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        for path in result.stdout.strip().split("\n"):
                            if path and path.endswith(".md"):
                                matches.append(path)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    # Fall back to grep
                    try:
                        result = subprocess.run(
                            ["grep", "-rl", "-i", safe_term, str(article_dir)],
                            capture_output=True, text=True, timeout=10
                        )
                        if result.returncode == 0:
                            for path in result.stdout.strip().split("\n"):
                                if path and path.endswith(".md"):
                                    matches.append(path)
                    except subprocess.TimeoutExpired:
                        pass

        # Score by frequency (more terms matched = higher score)
        from collections import Counter
        freq = Counter(matches)
        scored = sorted(freq.items(), key=lambda x: -x[1])

        # Extract metadata and excerpts for top results
        results = []
        for path, score in scored[:max_results]:
            article = self._read_article(path, config["excerpt_lines"])
            if article:
                article["relevance_score"] = score
                results.append(article)

        return results

    def _read_article(self, path: str, excerpt_lines: int) -> Optional[dict]:
        """Read article metadata and excerpt."""
        try:
            p = Path(path)
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")

            # Extract YAML frontmatter
            metadata = {}
            body_start = 0

            if lines[0].strip() == "---":
                # YAML frontmatter format
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "---":
                        body_start = i + 1
                        break
                    # Simple YAML parsing (key: value)
                    m = re.match(r'^(\w[\w_-]*)\s*:\s*(.+)', line)
                    if m:
                        metadata[m.group(1)] = m.group(2).strip().strip('"\'')
            elif lines[0].strip().startswith("# "):
                # Markdown-header format (from new scrapers)
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith("# ") and "title" not in metadata:
                        metadata["title"] = stripped[2:].strip()
                    elif stripped.startswith("**Author:**"):
                        metadata["author"] = stripped.replace("**Author:**", "").strip()
                    elif stripped.startswith("**Date:**"):
                        metadata["date"] = stripped.replace("**Date:**", "").strip()
                    elif stripped.startswith("**URL:**"):
                        metadata["source_url"] = stripped.replace("**URL:**", "").strip()
                    elif stripped == "---" and i > 0:
                        body_start = i + 1
                        break
                    elif i > 15:
                        body_start = 0
                        break

            # Get excerpt (skip empty lines at start of body)
            body_lines = lines[body_start:]
            # Strip leading empty lines
            while body_lines and not body_lines[0].strip():
                body_lines = body_lines[1:]

            excerpt = "\n".join(body_lines[:excerpt_lines]).strip()

            # Clean up markdown images and links that add noise
            excerpt = re.sub(r'!\[.*?\]\(.*?\)', '', excerpt)  # Remove images
            excerpt = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', excerpt)  # Simplify links
            excerpt = re.sub(r'\n{3,}', '\n\n', excerpt)  # Collapse blank lines

            return {
                "path": path,
                "title": metadata.get("title", metadata.get("guest", p.stem)),
                "author": metadata.get("author", metadata.get("guest", "Unknown")),
                "date": metadata.get("date", metadata.get("publish_date", metadata.get("date_published", ""))),
                "source": metadata.get("source", ""),
                "excerpt": excerpt,
            }
        except Exception:
            return None

    def get_context(self, advisor: str, query: str,
                    max_tokens: int = 4000, max_results: int = 5) -> str:
        """Get formatted context block ready for prompt injection.

        Returns a string like:
        ## Knowledge Base Context (Lenny Rachitsky)
        ### Article 1: "How to find PMF" by Rahul Vohra
        [excerpt...]
        ### Article 2: ...
        """
        key = self.resolve_advisor(advisor)
        if not key:
            return f"[No knowledge base found for advisor: {advisor}]"

        config = self.advisors[key]

        # Also check index files for Lenny (topic-based lookup)
        index_context = ""
        if config["index_dir"] and config["index_dir"].exists():
            index_context = self._search_index(config["index_dir"], query)

        results = self.search(advisor, query, max_results=max_results)

        if not results and not index_context:
            return f"[No relevant articles found in {config['name']}'s knowledge base for: {query}]"

        # Build context block
        lines = [
            f"## Knowledge Base Context: {config['name']} ({config['source']})",
            f"Query: \"{query}\"",
            f"Matched: {len(results)} articles from {config['article_count']} total",
            "",
        ]

        if index_context:
            lines.append("### Topic Index Matches")
            lines.append(index_context)
            lines.append("")

        # Estimate tokens (~4 chars per token) and truncate
        char_budget = max_tokens * 4
        current_chars = sum(len(l) for l in lines)

        for i, result in enumerate(results, 1):
            header = f"### [{i}] \"{result['title']}\" by {result['author']}"
            if result["date"]:
                header += f" ({result['date']})"

            article_text = f"{header}\n{result['excerpt']}\n"

            if current_chars + len(article_text) > char_budget:
                # Truncate this article to fit
                remaining = char_budget - current_chars - len(header) - 50
                if remaining > 200:
                    truncated = result["excerpt"][:remaining] + "\n[...truncated]"
                    lines.append(f"{header}\n{truncated}\n")
                break

            lines.append(article_text)
            current_chars += len(article_text)

        return "\n".join(lines)

    def _search_index(self, index_dir: Path, query: str) -> str:
        """Search topic index files (Lenny-specific)."""
        terms = query.lower().split()
        matches = []

        for md_file in index_dir.glob("*.md"):
            if md_file.name == "README.md":
                continue
            topic = md_file.stem.replace("-", " ")
            # Score: how many query terms appear in the topic name
            score = sum(1 for t in terms if t in topic)
            if score > 0:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                matches.append((score, topic, content.strip()))

        if not matches:
            return ""

        matches.sort(key=lambda x: -x[0])
        lines = []
        for score, topic, content in matches[:3]:
            lines.append(f"**{topic}:**")
            # Just show episode list (first 10 lines)
            for line in content.split("\n")[:12]:
                if line.strip():
                    lines.append(f"  {line.strip()}")
        return "\n".join(lines)

    def list_advisors(self) -> str:
        """List all available advisors and their KB stats."""
        lines = ["# Available Knowledge Bases", ""]
        lines.append(f"{'Advisor':<20} {'Source':<30} {'Articles':<10} {'Status'}")
        lines.append("-" * 80)

        for key, config in self.advisors.items():
            exists = any(d.exists() for d in config["article_dirs"])
            actual = 0
            if exists:
                for d in config["article_dirs"]:
                    if d.exists():
                        actual += sum(1 for _ in d.rglob("*.md"))

            status = f"OK ({actual} files)" if exists else "MISSING"
            lines.append(f"{key:<20} {config['source']:<30} {config['article_count']:<10} {status}")

        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge Base Loader for advisor agents")
    sub = parser.add_subparsers(dest="command")

    # search
    sp = sub.add_parser("search", help="Search an advisor's KB")
    sp.add_argument("--advisor", required=True, help="Advisor name (lenny, cherie, etc.)")
    sp.add_argument("--query", required=True, help="Search query")
    sp.add_argument("--max", type=int, default=5, help="Max results")

    # context (for prompt injection)
    cp = sub.add_parser("context", help="Get formatted context for prompt injection")
    cp.add_argument("--advisor", required=True, help="Advisor name")
    cp.add_argument("--query", required=True, help="Search query")
    cp.add_argument("--max-tokens", type=int, default=4000, help="Max token budget")

    # list
    sub.add_parser("list", help="List all advisors and KB stats")

    args = parser.parse_args()
    loader = KBLoader()

    if args.command == "search":
        results = loader.search(args.advisor, args.query, max_results=args.max)
        print(f"\nFound {len(results)} results for '{args.query}' in {args.advisor}'s KB:\n")
        for r in results:
            print(f"  [{r['relevance_score']}] {r['title']} - {r['author']} ({r['date']})")
            print(f"      {r['path']}")
            print()

    elif args.command == "context":
        context = loader.get_context(args.advisor, args.query, max_tokens=args.max_tokens)
        print(context)

    elif args.command == "list":
        print(loader.list_advisors())

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
