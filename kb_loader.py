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

import json
import statistics
import subprocess
import re
import sys
import time
from datetime import datetime
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
            # Leading Product newsletter (product strategy, AI UX, GTM)
            Path("~/Development/lenny/leading-product/articles").expanduser(),
            # Product Talk (Teresa Torres — product discovery, opportunity trees)
            Path("~/Development/lenny/product-talk/articles").expanduser(),
        ],
        "index_dir": Path("~/Development/lennys-podcast-transcripts/index").expanduser(),
        "pattern": "*.md",
        "article_count": 4491,  # 4006 + 46 (Leading Product) + 439 (Product Talk)
        "excerpt_lines": 80,  # Transcripts are huge, take more context
    },
    "music-biz": {
        "name": "Music Business (Cherie Hu + Jesse Cannon + Ari Herstand + Bandzoogle Blog)",
        "source": "Water & Music + Music Marketing Trends + Ari's Take + DMN + Bandzoogle Blog + Guest Articles",
        "article_dirs": [
            # music-biz exclusive: analytics, strategy, indie business
            Path("~/Development/cherie-hu/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand-dmn/articles").expanduser(),
            Path("~/Development/music-marketing/ari-herstand-guest/articles").expanduser(),
            # Shared with label: tactics, direct-to-fan
            Path("~/Development/jesse-cannon/articles").expanduser(),
            Path("~/Development/music-marketing/bandzoogle-blog/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 3628,  # Removed ditto-music (232) from music-biz
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
        "article_count": 157,  # Verified 2026-02-14
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
            # Wave 6: Music technology
            Path("~/Development/cto/cdm/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 8057,  # 6057 (prev) + 2000 (CDM/Create Digital Music)
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
            # Virgil Abloh portfolio (fashion, special projects, lectures)
            Path("~/Development/art-director/virgil-abloh/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 44082,  # 43898 + 184 (Virgil Abloh — RSS + page matching)
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
        "source": "Creative Capital (Handbook + Retreat Transcripts + Project Docs + Winner Analysis)",
        "article_dirs": [Path("~/Development/art-criticism/creative-capital/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 35,
        "excerpt_lines": 80,  # Transcripts need more context
    },
    "nyfa-source": {
        "name": "NYFA Source / Grant Writing Guides",
        "source": "NYFA Source + Format Magazine + ArtConnect + LearnGrantWriting + Winning Application Indices",
        "article_dirs": [Path("~/Development/art-criticism/nyfa-source/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 35,
        "excerpt_lines": 40,
    },
    "fractured-atlas": {
        "name": "Fractured Atlas",
        "source": "Fractured Atlas Blog (Fiscal Sponsorship + Grant Guides + Fundraising)",
        "article_dirs": [Path("~/Development/art-criticism/fractured-atlas/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 27,
        "excerpt_lines": 40,
    },
    "creative-independent": {
        "name": "The Creative Independent",
        "source": "TCI Guides (Grant Writing + Artist Statements + Storytelling)",
        "article_dirs": [Path("~/Development/art-criticism/creative-independent/articles").expanduser()],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 4,
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
        "article_count": 201,  # Verified 2026-02-14
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
            # Wave 6: Music/culture criticism
            Path("~/Development/atrium/the-quietus/articles").expanduser(),
            # Wave 7: TheNeedleDrop (music reviews, criticism)
            Path("~/Development/atrium/theneedledrop/articles").expanduser(),
            # Grant strategy knowledge (scraped 2026-02-15)
            Path("~/Development/art-criticism/nyfa-source/articles").expanduser(),
            Path("~/Development/art-criticism/fractured-atlas/articles").expanduser(),
            Path("~/Development/art-criticism/creative-independent/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 12165,  # 12099 + 35 (NYFA) + 27 (FA) + 4 (TCI)
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
        "name": "Record Label (Hypebot + MBW + Ditto + Jesse + Bandzoogle)",
        "source": "Hypebot + Music Business Worldwide + Ditto Music + Jesse Cannon + Bandzoogle Blog",
        "article_dirs": [
            # Shared with music-biz: tactics, direct-to-fan
            Path("~/Development/jesse-cannon/articles").expanduser(),
            Path("~/Development/music-marketing/bandzoogle-blog/articles").expanduser(),
            # Label exclusive: industry news, streaming economics, distribution
            Path("~/Development/music-business/hypebot/articles").expanduser(),
            Path("~/Development/music-business/music-biz-worldwide/articles").expanduser(),
            Path("~/Development/music-production/ditto-music/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 5406,  # Removed cherie (1710) + ari (744) from label
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
            # Tape Op magazine (recording interviews, studio techniques)
            Path("~/Development/audio-production/tape-op/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 3316,  # 2380 + 936 (Tape Op)
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
        "article_count": 15,  # 3 education + 12 lyrics (growing via free_lyrics_scraper.py)
        "excerpt_lines": 80,  # Lyrics need more lines to capture full song
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
        "article_count": 1775,  # Verified 2026-02-14
        "excerpt_lines": 50,
    },
    # ── Fonts In Use (Dedicated Catalog Advisor) ──
    "fonts-in-use": {
        "name": "Fonts In Use (Typeface Catalog)",
        "source": "Fonts In Use — typeface specimens, usage examples, designer credits",
        "article_dirs": [
            Path("~/Development/fonts-in-use/articles").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 32578,
        "excerpt_lines": 30,  # Catalog entries are short
    },
    # ── First 1000 (Audience Building + PMF + Customer Acquisition) ──
    "first-1000": {
        "name": "First 1000 (Audience Building + PMF + Customer Acquisition)",
        "source": "Hormozi, Arvid Kahl, Pat Flynn, Jay Clouse, Amy Hoy, First Round, YC, MIDiA, Sean Ellis, Kevin Kelly, Li Jin, Andrew Chen, Noah Kagan, Russell Brunson, Dan Martell, Daniel Priestley, Sahil Lavingia, Dickie Bush, Nathan Barry, Demand Curve, Circle.so, Mighty Networks, Patreon",
        "article_dirs": [
            Path("~/Development/knowledge-bases/first-1000/articles").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/hormozi").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/arvid-kahl").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/pat-flynn").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/nathan-barry").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/jay-clouse").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/amy-hoy").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/russell-brunson").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/dan-martell").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/sahil-lavingia").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/daniel-priestley").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/dickie-bush").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/first-round").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/yc-library").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/pmf-show").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/indie-hackers").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/sean-ellis").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/andrew-chen").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/noah-kagan").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/midia-research").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/li-jin").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/circle-so").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/mighty-networks").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/patreon").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/startup-grind").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/mixergy").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/kevin-kelly").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/demand-curve").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/youtube-transcripts").expanduser(),
            Path("~/Development/knowledge-bases/first-1000/supplementary").expanduser(),
        ],
        "index_dir": None,
        "pattern": "*.md",
        "article_count": 2711,  # Wave 9.1: Andrew Chen 657, Pat Flynn 369, First Round 863, YC Library 387, Arvid Kahl 435
        "excerpt_lines": 60,
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
    "tape-op": "audio-production",
    "tapeop": "audio-production",
    # Creative Interviews → Art Director
    "creative-interviews": "art-director",
    "interviews": "art-director",
    "eno-interviews": "art-director",
    "creative-independent": "creative-independent",
    "tci": "creative-independent",
    # Grant strategy sources → atrium
    "nyfa": "nyfa-source",
    "nyfa-source": "nyfa-source",
    "grant-writing": "atrium",
    "grant-tips": "atrium",
    "fractured-atlas": "fractured-atlas",
    "fiscal-sponsorship": "fractured-atlas",
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
    # Leading Product newsletter
    "leading-product": "lenny",
    "leadingproduct": "lenny",
    # Product Talk (Teresa Torres)
    "product-talk": "lenny",
    "producttalk": "lenny",
    "teresa-torres": "lenny",
    # TheNeedleDrop (Anthony Fantano music reviews)
    "theneedledrop": "atrium",
    "needledrop": "atrium",
    "fantano": "atrium",
    "anthony-fantano": "atrium",
    # Virgil Abloh portfolio
    "virgil-abloh": "art-director",
    "virgil": "art-director",
    "off-white": "art-director",
    # Fonts In Use (dedicated catalog)
    "fonts-in-use": "fonts-in-use",
    "fonts": "fonts-in-use",
    "typeface": "fonts-in-use",
    "typefaces": "fonts-in-use",
    "font-catalog": "fonts-in-use",
    "font-specimen": "fonts-in-use",
    # First 1000 (Audience Building + PMF + Customer Acquisition)
    "first-1000": "first-1000",
    "first1000": "first-1000",
    "first_1000": "first-1000",
    "superfans": "first-1000",
    "audience-building": "first-1000",
    "audience": "first-1000",
    "customer-acquisition": "first-1000",
    "funnels": "first-1000",
    "lead-magnet": "first-1000",
    "lead-magnets": "first-1000",
    "true-fans": "first-1000",
    "1000-fans": "first-1000",
    "product-market-fit": "first-1000",
    "sales-safari": "first-1000",
    "waitlist": "first-1000",
    "waiting-list": "first-1000",
    "demand-generation": "first-1000",
    "hormozi": "first-1000",
    "creator-economy": "first-1000",
    "direct-to-fan": "first-1000",
    "d2f": "first-1000",
    "fan-engagement": "first-1000",
    "email-list": "first-1000",
    "first-customers": "first-1000",
    "first-fans": "first-1000",
    "oversubscribed": "first-1000",
}


# ── Source Quality Weights ────────────────────────────────────────
# Multiplied with term frequency in search scoring.
# 1.0 = default, >1.0 = boost high-signal sources, <1.0 = penalize catalog/thin content
# ── Static Quality Weights (judgment-based) ─────────────────────
# Original hand-tuned assessments of source quality/signal density.
# These capture intuitions that article length can't measure
# (e.g., Valhalla DSP posts are short but extremely high-signal).
_STATIC_WEIGHTS = {
    "cherie-hu": 3.0, "creative-capital": 3.0,
    "valhalla-dsp": 2.5, "attack-magazine": 2.5, "fabfilter": 2.5,
    "brandnew": 2.5, "kent-beck": 2.5, "julia-evans": 2.5,
    "don-norman": 2.5, "nngroup": 2.5, "lawsofux": 2.5,
    "nyfa-source": 2.5, "creative-independent": 2.5,
    "airwindows": 2.0, "daniel-miessler": 2.0, "jesse-cannon": 2.0,
    "ari-herstand": 2.0, "splice": 2.0, "e-flux-journal": 2.0,
    "bomb-magazine": 2.0, "simon-willison": 2.0, "ubuweb-papers": 2.0,
    "backlinko": 2.0, "swyx": 2.0, "baymard": 2.0,
    "stanford-aesthetics": 2.0, "brian-eno": 2.0, "tape-op": 2.0,
    "fractured-atlas": 2.0,
    "hyperallergic": 1.5, "the-brand-identity": 1.5, "its-nice-that": 1.5,
    "creative-boom": 1.5, "hypebot": 1.5, "music-biz-worldwide": 1.5,
    "bandzoogle-blog": 1.5, "sparktoro": 1.5, "kevin-indig": 1.5,
    "arvid-kahl": 1.5, "lukew": 1.5, "the-quietus": 1.5, "cdm": 1.5,
    "ditto-music": 1.2, "bedroom-producers-blog": 1.2,
    "texte-zur-kunst": 0.8, "momus": 0.8, "situationist-international": 0.8,
    "marxists-aesthetics": 0.7,
    "creative-capital-awardees": 0.5, "artadia-awardees": 0.5, "usa-fellows": 0.5,
    "fonts-in-use": 0.3,
}

# Weight computation config
WEIGHT_COMPRESSION = 0.45  # Deviation compression (0=all flat, 1=raw ratio)
WEIGHT_BLEND = 0.5  # 0=all static, 1=all data-driven, 0.5=50/50
WEIGHT_FLOOR = 0.70
WEIGHT_CEILING = 1.80
WEIGHT_INDEX_PATH = Path("~/.claude/.locks/kb-source-weights.json").expanduser()
WEIGHT_INDEX_MAX_AGE = 86400  # 24 hours

SOURCE_WEIGHTS: dict[str, float] = {}  # Populated at init by _build_blended_weights()


def _build_blended_weights() -> dict[str, float]:
    """Blend static judgment weights with data-driven article-length weights.

    Static: captures quality intuitions (Valhalla is high-signal despite short posts).
    Data: captures measurable depth (e-flux articles are 53KB median = genuinely deep).
    Blend: 50/50 average after compressing both to 45% of deviation from 1.0.
    Cached to JSON index — rebuilds if >24h stale or missing.
    """
    # Check index cache
    if WEIGHT_INDEX_PATH.exists():
        try:
            age = time.time() - WEIGHT_INDEX_PATH.stat().st_mtime
            if age < WEIGHT_INDEX_MAX_AGE:
                cached = json.loads(WEIGHT_INDEX_PATH.read_text())
                if cached.get("version") == 3:
                    return cached["weights"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    # Step 1: Compress static weights to 45%
    static_compressed = {}
    for key, w in _STATIC_WEIGHTS.items():
        static_compressed[key] = 1.0 + (w - 1.0) * WEIGHT_COMPRESSION

    # Step 2: Compute data-driven weights from article length
    all_dirs: dict[str, list[Path]] = {}
    for config in ADVISORS.values():
        for article_dir in config["article_dirs"]:
            if not article_dir.exists():
                continue
            dir_str = str(article_dir)
            matched_key = None
            for dk in SOURCE_DOMAINS:
                if dk in dir_str:
                    matched_key = dk
                    break
            if not matched_key:
                matched_key = article_dir.parent.name
            if matched_key not in all_dirs:
                all_dirs[matched_key] = []
            all_dirs[matched_key].append(article_dir)

    source_medians: dict[str, float] = {}
    for source_key, dirs in all_dirs.items():
        sizes = []
        for d in dirs:
            for f in d.rglob("*.md"):
                try:
                    sizes.append(f.stat().st_size / 1024)
                except OSError:
                    pass
        if sizes:
            source_medians[source_key] = statistics.median(sizes)

    data_compressed = {}
    if source_medians:
        global_median = statistics.median(list(source_medians.values()))
        if global_median > 0:
            for key, med in source_medians.items():
                ratio = med / global_median
                data_compressed[key] = 1.0 + (ratio - 1.0) * WEIGHT_COMPRESSION

    # Step 3: Blend 50/50
    all_keys = set(static_compressed) | set(data_compressed)
    blended = {}
    for key in all_keys:
        sw = static_compressed.get(key, 1.0)
        dw = data_compressed.get(key, 1.0)
        raw = sw * (1 - WEIGHT_BLEND) + dw * WEIGHT_BLEND
        blended[key] = round(max(WEIGHT_FLOOR, min(raw, WEIGHT_CEILING)), 2)

    # Cache
    try:
        WEIGHT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        WEIGHT_INDEX_PATH.write_text(json.dumps({
            "version": 3,
            "computed_at": time.time(),
            "compression": WEIGHT_COMPRESSION,
            "blend": WEIGHT_BLEND,
            "source_count": len(blended),
            "weights": blended,
        }, indent=2))
    except OSError:
        pass

    return blended


# ── Dynamic Domain Relevance ────────────────────────────────────
# Maps source directory fragments to domain keywords.
# When query terms overlap with a source's domain, that source gets boosted.
# This makes SOURCE_WEIGHTS context-aware instead of static.
SOURCE_DOMAINS = {
    # ── Typography & Fonts ──
    "fonts-in-use": [
        "font", "typeface", "typography", "lettering", "serif", "sans-serif",
        "type design", "foundry", "specimen", "variable font", "grotesque",
        "slab", "display type", "monospace", "italic", "glyph", "opentype",
        "woff", "kerning", "ligature", "blackletter", "humanist", "geometric",
        "grotesk", "didone", "transitional", "type specimen",
    ],
    # ── Grant Strategy ──
    "creative-capital": [
        "grant", "application", "proposal", "funding", "awardee", "retreat",
        "work sample", "budget", "panel review", "award", "creative capital",
        "artist statement", "project description", "catalytic", "innovation",
    ],
    "nyfa-source": [
        "grant", "application", "funding", "proposal", "award", "nyfa",
        "grant writing", "artist fellowship",
    ],
    "fractured-atlas": [
        "grant", "fiscal sponsor", "fundraising", "nonprofit", "fiscal sponsorship",
        "crowdfunding", "donation",
    ],
    "creative-independent": [
        "grant", "artist statement", "application", "storytelling", "narrative",
    ],
    "creative-capital-awardees": [
        "grant", "awardee", "funded", "recipient", "winner", "portfolio",
    ],
    "artadia-awardees": [
        "grant", "awardee", "funded", "visual arts", "painting", "sculpture",
    ],
    "usa-fellows": [
        "grant", "fellowship", "awardee", "national", "usa",
    ],
    # ── Brand / Identity Design ──
    "brandnew": [
        "brand", "logo", "identity", "rebrand", "wordmark", "monogram",
        "visual identity", "brand refresh", "brand system",
    ],
    "the-brand-identity": [
        "brand", "identity", "packaging", "label design", "studio",
        "visual identity", "brand direction",
    ],
    "virgil-abloh": [
        "streetwear", "fashion", "off-white", "virgil", "abloh", "quotation marks",
        "3%", "freegame", "democratize",
    ],
    "designobserver": [
        "design criticism", "graphic design", "design culture", "design writing",
    ],
    "creativereview": [
        "advertising", "branding", "campaign", "commercial", "creative industry",
    ],
    # ── UX / Interaction Design ──
    "baymard": [
        "ecommerce", "checkout", "cart", "product page", "mobile ux",
        "usability", "conversion",
    ],
    "lawsofux": [
        "cognitive", "psychology", "heuristic", "principle", "fitts",
        "hick", "jakob", "miller", "gestalt",
    ],
    "deceptive-design": [
        "dark pattern", "deceptive", "manipulation", "trick", "confirmshaming",
    ],
    "don-norman": [
        "affordance", "signifier", "conceptual model", "feedback", "mapping",
        "constraint", "discoverability", "human error",
    ],
    "nngroup": [
        "usability", "user research", "heuristic evaluation", "information architecture",
        "navigation", "accessibility",
    ],
    "lukew": [
        "mobile first", "form design", "input", "touch", "responsive",
    ],
    "alistapart": [
        "web standards", "responsive", "progressive enhancement", "accessibility",
        "content strategy",
    ],
    "smashingmag": [
        "css", "web design", "front-end", "performance", "accessibility",
    ],
    # ── Audio / DSP / Plugins ──
    "valhalla-dsp": [
        "reverb", "delay", "dsp", "algorithm", "allpass", "diffusion",
        "room", "plate", "shimmer",
    ],
    "airwindows": [
        "plugin", "saturation", "eq", "compressor", "console", "tape",
        "analog modeling", "gain staging",
    ],
    "fabfilter": [
        "eq", "compressor", "limiter", "pro-q", "pro-l", "multiband",
        "dynamics", "spectrum",
    ],
    "attack-magazine": [
        "synth", "synthesis", "tutorial", "production", "sound design",
        "modular", "wavetable", "fm",
    ],
    "splice": [
        "sample", "preset", "production", "tutorial", "sound design",
        "workflow", "collaboration",
    ],
    "tape-op": [
        "recording", "studio", "mixing", "analog", "console", "microphone",
        "preamp", "tape",
    ],
    "bedroom-producers-blog": [
        "free plugin", "budget", "tutorial", "beginner", "daw", "production tips",
    ],
    # ── Circuit Modeling ──
    "circuit-modeling": [
        "circuit", "schematic", "transistor", "diode", "filter", "wdf",
        "spice", "virtual analog", "waveshaper", "clipper", "tube",
        "op-amp", "bjt", "mosfet", "nonlinear", "newton-raphson",
    ],
    # ── Critical Theory / Art Criticism ──
    "e-flux-journal": [
        "theory", "contemporary art", "biennial", "critique", "institutional",
        "post-internet", "accelerationism",
    ],
    "hyperallergic": [
        "exhibition", "review", "gallery", "museum", "public art",
        "censorship", "politics",
    ],
    "ubuweb-papers": [
        "avant-garde", "fluxus", "concrete poetry", "experimental", "sound poetry",
        "dada", "futurism",
    ],
    "stanford-aesthetics": [
        "philosophy", "aesthetics", "beauty", "sublime", "judgment", "taste",
        "ontology", "phenomenology",
    ],
    "situationist-international": [
        "spectacle", "détournement", "psychogeography", "debord", "derive",
    ],
    "marxists-aesthetics": [
        "dialectic", "materialism", "ideology", "class", "production",
        "benjamin", "adorno", "lukacs",
    ],
    "texte-zur-kunst": [
        "institutional critique", "contemporary", "discourse", "curatorial",
    ],
    "momus": [
        "art criticism", "review", "contemporary art", "culture",
    ],
    "bomb-magazine": [
        "interview", "artist talk", "conversation", "studio visit",
    ],
    # ── Music Business ──
    "cherie-hu": [
        "streaming", "ai music", "web3", "music tech", "royalties",
        "distribution", "analytics",
    ],
    "jesse-cannon": [
        "marketing", "social media", "promotion", "strategy", "tiktok",
        "instagram", "youtube", "content",
    ],
    "ari-herstand": [
        "touring", "booking", "revenue", "indie artist", "publishing",
        "sync", "licensing", "live",
    ],
    "hypebot": [
        "industry", "streaming", "deals", "news", "spotify", "label",
    ],
    "music-biz-worldwide": [
        "major label", "deal", "acquisition", "streaming economics",
        "market share", "revenue",
    ],
    "bandzoogle-blog": [
        "artist website", "direct-to-fan", "email list", "fan engagement",
        "merch", "crowdfunding",
    ],
    "ditto-music": [
        "distribution", "release", "indie", "upload", "stores",
    ],
    "the-quietus": [
        "review", "interview", "album", "underground", "experimental music",
    ],
    "theneedledrop": [
        "album review", "rating", "hip-hop", "indie", "experimental",
    ],
    # ── SEO / Marketing ──
    "backlinko": [
        "backlinks", "seo", "link building", "rankings", "on-page",
        "google", "serp",
    ],
    "sparktoro": [
        "audience", "research", "zero-click", "rand fishkin", "social",
    ],
    "kevin-indig": [
        "seo", "ai search", "programmatic", "growth", "technical seo",
    ],
    "arvid-kahl": [
        "indie", "bootstrap", "audience", "building in public", "saas",
    ],
    "zyppy": [
        "technical seo", "ctr", "title tags", "schema",
    ],
    # ── Tech Leaders ──
    "julia-evans": [
        "debugging", "networking", "linux", "systems", "zine", "learning",
    ],
    "kent-beck": [
        "tdd", "testing", "refactoring", "design", "xp", "agile",
    ],
    "simon-willison": [
        "sqlite", "llm", "ai tools", "datasette", "prompt engineering",
    ],
    "swyx": [
        "ai engineering", "agents", "llm", "latent space", "ai infra",
    ],
    "daniel-miessler": [
        "security", "ai", "red team", "fabric", "threat modeling",
    ],
    "patrick-mckenzie": [
        "pricing", "saas", "stripe", "business", "salary negotiation",
    ],
    # ── Brian Eno / Creative Philosophy ──
    "brian-eno": [
        "generative", "ambient", "oblique strategies", "scenius",
        "systems", "process", "chance", "emergence",
    ],
    "brian-eno-enoweb": [
        "generative", "ambient", "oblique strategies", "scenius",
        "interview", "studio", "process",
    ],
    # ── Creative Boom / It's Nice That ──
    "creative-boom": [
        "illustration", "design studio", "creative career", "portfolio",
    ],
    "its-nice-that": [
        "design", "illustration", "animation", "creative", "graduate",
    ],
    # ── CDM (Create Digital Music) ──
    "cdm": [
        "diy", "hardware", "controller", "eurorack", "music tech",
        "open source", "arduino", "raspberry pi",
    ],
    # ── First 1000 (Audience Building + PMF + Customer Acquisition) ──
    "first-1000": [
        "superfan", "fan", "fandom", "audience", "customer", "acquisition",
        "funnel", "lead", "magnet", "email", "list", "waitlist", "pmf",
        "product-market-fit", "conversion", "retention", "community",
        "direct-to-fan", "membership", "patreon", "gumroad", "creator",
        "1000", "true fans", "oversubscribed", "demand", "sales safari",
        "first customers", "audience building", "lead magnet", "value ladder",
        "tripwire", "opt-in", "launch", "pre-launch",
    ],
}

# Domain boost multiplier: how much to amplify when query matches domain
DOMAIN_BOOST_PER_HIT = 2.0
DOMAIN_BOOST_CAP = 6.0  # Max total multiplier from domain relevance



# ── Query Expansion ────────────────────────────────────────────
# Domain synonyms: common abbreviations/aliases → expanded forms
QUERY_SYNONYMS = {
    "seo": ["search engine optimization", "rankings"],
    "ux": ["user experience", "usability"],
    "dsp": ["digital signal processing", "audio processing"],
    "ui": ["user interface", "interface design"],
    "dx": ["developer experience"],
    "ci": ["continuous integration"],
    "cd": ["continuous deployment", "continuous delivery"],
    "api": ["application programming interface", "endpoint"],
    "eq": ["equalizer", "equalization"],
    "daw": ["digital audio workstation"],
    "midi": ["musical instrument digital interface"],
    "lfo": ["low frequency oscillator"],
    "adsr": ["attack decay sustain release", "envelope"],
    "vst": ["virtual studio technology", "plugin"],
    "au": ["audio unit", "plugin"],
    "wdf": ["wave digital filter"],
    "va": ["virtual analog"],
    "ml": ["machine learning"],
    "ai": ["artificial intelligence"],
    "pmf": ["product market fit"],
}


# ── Confidence Gating ──────────────────────────────────────────
MIN_HITS_FOR_CONFIDENCE = 3  # Below this, show low-confidence warning
MIN_KB_ARTICLES = 25  # Below this, show degraded KB warning


class KBLoader:
    """Knowledge Base Loader - searches advisor KBs and returns context."""

    def __init__(self):
        self.advisors = ADVISORS
        self.aliases = ALIASES
        # Build blended weights on first use (cached to disk for 24h)
        if not SOURCE_WEIGHTS:
            SOURCE_WEIGHTS.update(_build_blended_weights())

    def resolve_advisor(self, name: str) -> Optional[str]:
        """Resolve advisor name/alias to canonical key."""
        key = name.lower().strip()
        return self.aliases.get(key)

    @staticmethod
    def _expand_query_terms(query: str) -> list[tuple[str, float]]:
        """Expand query into weighted (term, weight) pairs using 3 layers.

        Layer 1: Original terms (weight 1.0)
        Layer 2: Porter-stemmed variants (weight 0.7)
        Layer 3: Domain synonyms (weight 0.5)
        """
        try:
            from porter_stemmer import stem
        except ImportError:
            stem = None

        raw_terms = query.lower().split()
        expanded = []
        seen = set()

        # Layer 1: Original terms
        for t in raw_terms:
            if t not in seen:
                expanded.append((t, 1.0))
                seen.add(t)

        # Layer 2: Stemmed variants
        if stem:
            for t in raw_terms:
                stemmed = stem(t)
                if stemmed and stemmed != t and stemmed not in seen:
                    expanded.append((stemmed, 0.7))
                    seen.add(stemmed)

        # Layer 3: Domain synonyms
        for t in raw_terms:
            for synonym in QUERY_SYNONYMS.get(t, []):
                # Synonyms can be multi-word; add each word separately
                for word in synonym.lower().split():
                    if word not in seen:
                        expanded.append((word, 0.5))
                        seen.add(word)

        return expanded

    def search(self, advisor: str, query: str, max_results: int = 5) -> list[dict]:
        """Search an advisor's KB for articles matching query.

        Returns list of dicts with: path, title, author, relevance_score, excerpt
        """
        key = self.resolve_advisor(advisor)
        if not key:
            return []

        config = self.advisors[key]
        # weighted_matches: path → cumulative weighted score
        weighted_matches: dict[str, float] = {}

        # Expand query into weighted terms
        expanded_terms = self._expand_query_terms(query)
        # Keep raw terms for dynamic weight computation
        raw_terms = query.lower().split()

        for article_dir in config["article_dirs"]:
            if not article_dir.exists():
                continue

            import re as _re
            for term, weight in expanded_terms:
                safe_term = _re.escape(term)
                try:
                    result = subprocess.run(
                        ["rg", "-l", "-i", safe_term, str(article_dir)],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        for path in result.stdout.strip().split("\n"):
                            if path and path.endswith(".md"):
                                weighted_matches[path] = weighted_matches.get(path, 0) + weight
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    try:
                        result = subprocess.run(
                            ["grep", "-rl", "-i", safe_term, str(article_dir)],
                            capture_output=True, text=True, timeout=10
                        )
                        if result.returncode == 0:
                            for path in result.stdout.strip().split("\n"):
                                if path and path.endswith(".md"):
                                    weighted_matches[path] = weighted_matches.get(path, 0) + weight
                    except subprocess.TimeoutExpired:
                        pass

        # Score by weighted frequency * dynamic weight (quality × domain relevance)
        scored = sorted(
            weighted_matches.items(),
            key=lambda x: -(x[1] * self._compute_dynamic_weight(x[0], raw_terms))
        )

        # Apply recency boost to top 20 pre-scored results only (minimize I/O)
        top_candidates = scored[:20]
        if top_candidates:
            recency_scored = [
                (path, score * self._compute_recency_boost(path))
                for path, score in top_candidates
            ]
            recency_scored.sort(key=lambda x: -x[1])
            scored = recency_scored + scored[20:]

        # Extract metadata and excerpts for top results
        results = []
        for path, score in scored[:max_results]:
            article = self._read_article(path, config["excerpt_lines"])
            if article:
                article["relevance_score"] = score
                results.append(article)

        return results

    @staticmethod
    def _get_source_weight(path: str) -> float:
        """Get static quality weight for a source based on its directory path."""
        for source_key, weight in SOURCE_WEIGHTS.items():
            if source_key in path:
                return weight
        return 1.0  # default weight for unlisted sources

    @staticmethod
    def _compute_dynamic_weight(path: str, query_terms: list[str]) -> float:
        """Compute context-aware weight: static quality + domain relevance.

        Uses ADDITIVE combination so domain relevance can rescue low-base-weight
        sources when the query is clearly in their domain. Multiplicative would
        anchor fonts-in-use (base=0.3) at max 1.8 even with perfect domain match.

        With additive: fonts-in-use + 4 font hits = 0.3 + 6.0 = 6.3 (competitive)
        With multiply: fonts-in-use + 4 font hits = 0.3 * 6.0 = 1.8 (buried)

        Note: query_terms are lowercased internally for case-insensitive matching.
        """
        # Start with the static quality weight
        base_weight = 1.0
        for source_key, weight in SOURCE_WEIGHTS.items():
            if source_key in path:
                base_weight = weight
                break

        # Normalize query terms to lowercase for case-insensitive matching
        query_lower = [qt.lower() for qt in query_terms]

        # Check domain relevance — additive boost independent of base weight
        best_boost = 0.0
        for source_key, domain_keywords in SOURCE_DOMAINS.items():
            if source_key not in path:
                continue
            # Count query terms that match this source's domain
            hits = 0
            for qt in query_lower:
                for dk in domain_keywords:
                    # Exact match, or substring match for terms > 3 chars
                    if qt == dk or (len(qt) > 3 and qt in dk) or (len(dk) > 3 and dk in qt):
                        hits += 1
                        break  # One match per query term is enough
            if hits > 0:
                boost = min(hits * DOMAIN_BOOST_PER_HIT, DOMAIN_BOOST_CAP)
                best_boost = max(best_boost, boost)

        return base_weight + best_boost

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

    @staticmethod
    def _compute_recency_boost(path: str) -> float:
        """Compute recency multiplier from article date in YAML frontmatter.

        Returns: 1.2 (<1yr), 1.0 (1-3yr), 0.8 (>3yr), 1.0 (no date found).
        Only reads first 20 lines to minimize I/O.
        """
        try:
            p = Path(path)
            lines = p.read_text(encoding="utf-8", errors="replace").split("\n")[:20]

            date_str = None
            for line in lines:
                stripped = line.strip()
                # YAML frontmatter: date: 2024-01-15 or date: "January 2024"
                if stripped.startswith("date:") or stripped.startswith("publish_date:") or stripped.startswith("date_published:"):
                    date_str = stripped.split(":", 1)[1].strip().strip("\"'")
                    break
                # Markdown format: **Date:** 2024-01-15
                if stripped.startswith("**Date:**"):
                    date_str = stripped.replace("**Date:**", "").strip()
                    break

            if not date_str:
                return 1.0

            # Parse year from various date formats
            year_match = re.search(r'20[12]\d', date_str)
            if not year_match:
                return 1.0

            year = int(year_match.group())
            current_year = datetime.now().year
            age = current_year - year

            if age < 1:
                return 1.2
            elif age <= 3:
                return 1.0
            else:
                return 0.8
        except (OSError, ValueError):
            return 1.0

    @staticmethod
    def _suggest_alternates(query: str, current_advisor: str) -> list[str]:
        """Suggest alternate advisors that might handle this query better."""
        query_lower = query.lower()
        suggestions = []
        # Check which advisor domains overlap with the query terms
        for source_key, domain_keywords in SOURCE_DOMAINS.items():
            hits = sum(1 for dk in domain_keywords if dk in query_lower)
            if hits >= 2:
                # Find which advisor owns this source
                for adv_key, adv_config in ADVISORS.items():
                    if adv_key == current_advisor:
                        continue
                    for d in adv_config["article_dirs"]:
                        if source_key in str(d):
                            if adv_key not in suggestions:
                                suggestions.append(adv_key)
                            break
        return suggestions[:3]

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

        # Sprint 2.5: MIN_KB_THRESHOLD gate
        warnings = []
        article_count = config.get("article_count", 0)
        if article_count < MIN_KB_ARTICLES:
            warnings.append(
                f"**DEGRADED KB** — {config['name']} has only {article_count} articles "
                f"(minimum recommended: {MIN_KB_ARTICLES}). Results may be incomplete. "
                "Consider expanding this knowledge base."
            )

        # Also check index files for Lenny (topic-based lookup)
        index_context = ""
        if config["index_dir"] and config["index_dir"].exists():
            index_context = self._search_index(config["index_dir"], query)

        results = self.search(advisor, query, max_results=max_results)

        # Sprint 2.2: Confidence gating
        if len(results) < MIN_HITS_FOR_CONFIDENCE:
            alternates = self._suggest_alternates(query, key)
            alt_str = ", ".join(f"`/skill {a}`" for a in alternates) if alternates else "none found"
            warnings.append(
                f"**WARNING: LOW CONFIDENCE** — Only {len(results)} article(s) matched. "
                f"This query may be outside {config['name']}'s domain. "
                f"Try alternate advisors: {alt_str}"
            )

        if not results and not index_context:
            prefix = "\n".join(warnings) + "\n\n" if warnings else ""
            return prefix + f"[No relevant articles found in {config['name']}'s knowledge base for: {query}]"

        # Build context block
        lines = []
        if warnings:
            lines.extend(warnings)
            lines.append("")

        lines.extend([
            f"## Knowledge Base Context: {config['name']} ({config['source']})",
            f"Query: \"{query}\"",
            f"Matched: {len(results)} articles from {config['article_count']} total",
            "",
        ])

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
