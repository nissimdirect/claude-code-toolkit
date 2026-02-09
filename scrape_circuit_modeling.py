#!/usr/bin/env python3
"""
Circuit Modeling Knowledge Base Scraper
Downloads PDFs, scrapes HTML articles, clones GitHub docs.
Zero token burn — all code execution.

Usage:
    python3 scrape_circuit_modeling.py                  # Scrape everything
    python3 scrape_circuit_modeling.py --tier 1         # Tier 1 only (PDFs)
    python3 scrape_circuit_modeling.py --tier 2         # Tier 2 only (HTML)
    python3 scrape_circuit_modeling.py --tier 3         # Tier 3 only (GitHub)
    python3 scrape_circuit_modeling.py --tier 4         # Tier 4 only (Forums)
    python3 scrape_circuit_modeling.py --category wdf   # Just WDF sources
    python3 scrape_circuit_modeling.py --dry-run        # Show what would be scraped
    python3 scrape_circuit_modeling.py --report         # Show collection stats
"""

import os
import sys
import time
import json
import hashlib
import re
import subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
except ImportError:
    print("Missing dependencies. Run:")
    print("  source ~/Development/tools/venv/bin/activate")
    print("  pip install requests beautifulsoup4 markdownify")
    sys.exit(1)


# ============================================================
# SOURCE REGISTRY
# Each entry: (url, filename, category, tier, description)
# ============================================================

SOURCES = [
    # ── TIER 1: PDFs (download directly) ──────────────────────
    # WDF
    ("https://ccrma.stanford.edu/~dtyeh/papers/wdftutorial.pdf",
     "yeh-wdf-tutorial.pdf", "wdf", 1, "David Yeh WDF Tutorial"),
    ("https://stacks.stanford.edu/file/druid:jy057cz8322/KurtJamesWernerDissertation-augmented.pdf",
     "werner-wdf-dissertation.pdf", "wdf", 1, "Kurt Werner WDF Dissertation (261pp)"),
    ("https://ccrma.stanford.edu/~jatin/slides/TAP_WDFs.pdf",
     "chowdhury-wdf-cpp-slides.pdf", "wdf", 1, "Jatin Chowdhury WDF in C++ Slides"),

    # VA Modeling
    ("https://www.native-instruments.com/fileadmin/ni_media/downloads/pdf/VAFilterDesign_2.1.0.pdf",
     "zavalishin-va-filter-design.pdf", "va", 1, "Zavalishin Art of VA Filter Design (130pp)"),
    ("https://ccrma.stanford.edu/~dtyeh/papers/yeh10_taslp.pdf",
     "yeh-automated-modeling-part1.pdf", "nodal", 1, "Yeh Automated Physical Modeling Part I"),
    ("https://ccrma.stanford.edu/~dtyeh/papers/yeh12_taslp.pdf",
     "yeh-automated-modeling-part2.pdf", "nodal", 1, "Yeh Automated Physical Modeling Part II"),

    # Spring Reverb
    ("https://www.aes-media.org/sections/pnw/ppt/costello/AES2015ReverbPresentation.pdf",
     "costello-aes2015-reverb.pdf", "spring-reverb", 1, "Sean Costello AES 2015 Reverb"),
    ("https://www.thetubestore.com/lib/thetubestore/schematics/Fender/Fender-Reverb-6G15-Schematic.pdf",
     "fender-6g15-schematic.pdf", "spring-reverb", 1, "Fender 6G15 Spring Reverb Schematic"),

    # SPICE
    ("http://www.hkn.umn.edu/resources/files/spice/VirtualSpice.pdf",
     "umn-virtual-spice-guide.pdf", "spice", 1, "UMN Virtual SPICE Guide"),

    # Tube Models
    ("https://leachlegacy.ece.gatech.edu/papers/tubeamp/tubeamp.pdf",
     "leach-tube-amp-spice.pdf", "spice", 1, "Leach Tube Amp SPICE Models"),

    # Will Pirkle Vacuum Tube
    ("http://willpirkle.com/special/Addendum_A19_Pirkle_v1.0.pdf",
     "pirkle-vacuum-tube-emulation.pdf", "va", 1, "Pirkle Vacuum Tube Emulation"),

    # VA Filter Comparison
    ("https://forum.audulus.com/uploads/default/original/2X/8/82ea1a4ef055962ff4a50bcdf5e21f7aa895bebd.pdf",
     "pirkle-va-filter-comparison.pdf", "va", 1, "Pirkle VA Filter Comparison"),

    # DAFx Papers
    ("https://dafx.de/paper-archive/2015/DAFx-15_submission_53.pdf",
     "dafx2015-wdf-arbitrary-topologies.pdf", "wdf", 1, "WDF Arbitrary Topologies (DAFx 2015)"),
    ("https://www.dafx.de/paper-archive/2016/dafxpapers/40-DAFx-16_paper_35-PN.pdf",
     "dafx2016-rt-wdf.pdf", "wdf", 1, "RT-WDF Modular Framework (DAFx 2016)"),
    ("https://dafx2020.mdw.ac.at/proceedings/papers/DAFx2020_paper_35.pdf",
     "dafx2020-antialiasing-wdf.pdf", "wdf", 1, "Antiderivative Antialiasing in WDF (DAFx 2020)"),
    ("https://www.dafx.de/paper-archive/2023/DAFx23_paper_60.pdf",
     "dafx2023-explicit-vector-wdf.pdf", "wdf", 1, "Explicit Vector WDF (DAFx 2023)"),
    ("https://dafx.de/paper-archive/2019/DAFx2019_paper_43.pdf",
     "dafx2019-rnn-comparison.pdf", "ml", 1, "Comparative RNN Study (DAFx 2019)"),
    ("https://dafx16.vutbr.cz/files/dafx16_tutorial_macak.pdf",
     "dafx2016-va-tutorial.pdf", "va", 1, "VA Modeling Tutorial (DAFx 2016)"),

    # White-box / Differentiable
    ("https://dafx.de/paper-archive/2021/proceedings/papers/DAFx20in21_paper_39.pdf",
     "dafx2021-differentiable-whitebox.pdf", "whitebox", 1, "Differentiable White-Box VA (DAFx 2021)"),
    ("https://dangelo.audio/docs/lightweightva.pdf",
     "dangelo-lightweight-va.pdf", "whitebox", 1, "Lightweight VA Modeling"),

    # Newton-Raphson / WDF
    ("https://re.public.polimi.it/bitstream/11311/1203185/1/WD_NR_TASLP_Bernardini_etal_2021_RG.pdf",
     "bernardini-wave-digital-newton-raphson.pdf", "newton-raphson", 1, "Wave Digital Newton-Raphson"),

    # BBD
    ("https://colinraffel.com/publications/dafx2010practical.pdf",
     "raffel-practical-bbd.pdf", "space-echo", 1, "Practical BBD Modeling (Colin Raffel)"),

    # ML
    ("https://arxiv.org/pdf/2502.14405",
     "differentiable-blackbox-graybox.pdf", "ml", 1, "Differentiable Black-Box + Gray-Box"),
    ("https://arxiv.org/pdf/2308.15422",
     "review-differentiable-dsp.pdf", "ml", 1, "Review of Differentiable DSP"),

    # MNA
    ("https://spinningnumbers.org/assets/modified-nodal-analysis.pdf",
     "spinning-numbers-mna.pdf", "nodal", 1, "MNA PDF (Spinning Numbers)"),

    # ── TIER 2: HTML Articles (scrape to markdown) ────────────
    # ElectroSmash (gold standard)
    ("https://www.electrosmash.com/big-muff-pi-analysis",
     "electrosmash-big-muff.md", "schematics", 2, "Big Muff Pi Analysis"),
    ("https://www.electrosmash.com/fuzz-face",
     "electrosmash-fuzz-face.md", "schematics", 2, "Fuzz Face Analysis"),
    ("https://electrosmash.com/tube-screamer-analysis",
     "electrosmash-tube-screamer.md", "schematics", 2, "Tube Screamer Analysis"),
    ("https://www.electrosmash.com/klon-centaur-analysis",
     "electrosmash-klon-centaur.md", "schematics", 2, "Klon Centaur Analysis"),
    ("https://www.electrosmash.com/boss-ds1-analysis",
     "electrosmash-boss-ds1.md", "schematics", 2, "Boss DS-1 Analysis"),
    ("https://www.electrosmash.com/mxr-distortion-plus-analysis",
     "electrosmash-mxr-distortion-plus.md", "schematics", 2, "MXR Distortion+ Analysis"),
    ("https://www.electrosmash.com/germanium-fuzz",
     "electrosmash-germanium-fuzz.md", "schematics", 2, "Germanium Fuzz Analysis"),
    ("https://www.electrosmash.com/mn3007-bucket-brigade-devices",
     "electrosmash-bbd-mn3007.md", "space-echo", 2, "BBD MN3007 Analysis"),

    # Julius O. Smith Online Books
    ("https://ccrma.stanford.edu/~jos/pasp/",
     "jos-physical-audio.md", "va", 2, "Julius O. Smith - Physical Audio Signal Processing"),
    ("https://ccrma.stanford.edu/~jos/filters/",
     "jos-digital-filters.md", "va", 2, "Julius O. Smith - Intro to Digital Filters"),
    ("https://www.dsprelated.com/freebooks/pasp/Wave_Digital_Filters_I.html",
     "jos-wdf-chapter.md", "wdf", 2, "JOS WDF Chapter"),

    # SPICE Tutorials
    ("https://ngspice.sourceforge.io/ngspice-tutorial.html",
     "ngspice-beginner-tutorial.md", "spice", 2, "ngspice Beginner Tutorial"),
    ("https://ngspice.sourceforge.io/ngspice-control-language-tutorial.html",
     "ngspice-control-language.md", "spice", 2, "ngspice Control Language Tutorial"),
    ("https://hforsten.com/simulating-audio-effects-with-spice.html",
     "hforsten-audio-spice.md", "spice", 2, "Simulating Audio Effects with SPICE"),
    ("https://pcb.mit.edu/labs/lab_02/",
     "mit-spice-lab.md", "spice", 2, "MIT SPICE Lab"),
    ("https://www.ecircuitcenter.com/Basics.htm",
     "ecircuitcenter-basics.md", "spice", 2, "eCircuitCenter SPICE Basics"),

    # LTspice Guitar Pedals
    ("https://cushychicken.github.io/posts/ltspice-tube-screamer/",
     "ltspice-tube-screamer.md", "spice", 2, "Tube Screamer in LTspice"),

    # Tube SPICE Models
    ("https://www.normankoren.com/Audio/Tubemodspice_article.html",
     "koren-tube-models-part1.md", "spice", 2, "Norman Koren Tube Models Part 1"),
    ("https://www.normankoren.com/Audio/Tubemodspice_article_2.html",
     "koren-tube-models-part2.md", "spice", 2, "Norman Koren Tube Models Part 2"),

    # Component Modeling
    ("https://www.allaboutcircuits.com/textbook/designing-analog-chips/simulation/spice-models-for-resistors-and-capacitors/",
     "aac-spice-component-models.md", "spice", 2, "SPICE Models for R/C Components"),

    # Distortion Design
    ("https://electricdruid.net/designing-the-hard-bargain-distortion-pedal/",
     "electricdruid-distortion-design.md", "distortion", 2, "Electric Druid Distortion Design"),
    ("https://generalguitargadgets.com/how-to-build-it/technical-help/articles/design-distortion/",
     "ggg-distortion-design.md", "distortion", 2, "GGG Distortion Design Guide"),
    ("https://www.wamplerpedals.com/blog/latest-news/2020/05/how-to-design-a-basic-overdrive-pedal-circuit/",
     "wampler-overdrive-design.md", "distortion", 2, "Wampler Basic Overdrive Design"),
    ("http://www.geofex.com/article_folders/fuzzface/fftech.htm",
     "geofex-fuzzface-tech.md", "schematics", 2, "Geofex Fuzz Face Technology"),

    # Spring Reverb Technical
    ("https://robrobinette.com/How_Spring_Reverb_Works.htm",
     "robrobinette-spring-reverb.md", "spring-reverb", 2, "How Spring Reverb Works (Rob Robinette)"),
    ("https://sound-au.com/articles/reverb.htm",
     "sound-au-spring-reverb.md", "spring-reverb", 2, "Sound-AU Spring Reverb Overview"),
    ("https://sound-au.com/project34.htm",
     "sound-au-diy-spring-reverb.md", "spring-reverb", 2, "Sound-AU DIY Spring Reverb"),
    ("https://anasounds.com/analog-spring-reverb-how-it-works/",
     "anasounds-spring-reverb.md", "spring-reverb", 2, "Anasounds Spring Reverb How It Works"),
    ("https://bulinskipedals.com/how-spring-reverb-circuits-work/",
     "bulinski-spring-reverb-circuits.md", "spring-reverb", 2, "Bulinski Spring Reverb Circuits"),
    ("https://www.premierguitar.com/articles/27240-lords-of-the-springs",
     "premierguitar-lords-of-springs.md", "spring-reverb", 2, "Premier Guitar Lords of the Springs"),
    ("https://pulsar.audio/blog/the-history-of-spring-reverb/",
     "pulsar-spring-reverb-history.md", "spring-reverb", 2, "Pulsar Audio History of Spring Reverb"),
    ("https://www.amplifiedparts.com/tech-articles/spring-reverb-tanks-explained-and-compared",
     "accutronics-tanks-explained.md", "spring-reverb", 2, "Accutronics Spring Tanks Explained"),
    ("https://www.amplifiedparts.com/tech-articles/accutronics-products-and-specifications",
     "accutronics-specs.md", "spring-reverb", 2, "Accutronics Specifications"),
    ("https://guitar.com/guides/diy-workshop/build-tube-spring-reverb-unit-amplifier/",
     "guitar-com-tube-spring-reverb.md", "spring-reverb", 2, "Build Tube Spring Reverb Unit"),
    ("https://valveheaven.com/2016/10/the-lamington-reverb/",
     "valveheaven-lamington-reverb.md", "spring-reverb", 2, "Lamington Valve Spring Reverb"),

    # Valhalla DSP (Spring Reverb Expert)
    ("https://valhalladsp.com/2017/06/01/minimalism-algorithm-design/",
     "valhalla-minimalism.md", "spring-reverb", 2, "Valhalla Minimalism in Algorithm Design"),
    ("https://valhalladsp.com/2011/07/07/algorithmic-reverbs-distortion-and-noise/",
     "valhalla-reverbs-distortion.md", "spring-reverb", 2, "Valhalla Algorithmic Reverbs + Distortion"),

    # BBD / Space Echo
    ("https://effdubaudio.com/how-bbds-work/",
     "effdub-bbd-howto.md", "space-echo", 2, "How BBDs Work (EffDub Audio)"),
    ("https://anasounds.com/miniaturization-of-the-delay-the-bbd/",
     "anasounds-bbd-history.md", "space-echo", 2, "BBD History (Anasounds)"),
    ("https://articles.boss.info/inside-the-re-202-space-echo/",
     "boss-re202-inside.md", "space-echo", 2, "Inside the RE-202 (BOSS)"),

    # White-box / General
    ("https://aidadsp.github.io/2020/04/13/analog-modeling-techniques-review.html",
     "aida-modeling-review.md", "whitebox", 2, "AIDA Modeling Techniques Review"),
    ("https://www.soundonsound.com/techniques/plug-in-modelling-how-industry-experts-do-it",
     "sos-plugin-modelling.md", "whitebox", 2, "SOS Plugin Modelling How Experts Do It"),

    # MNA
    ("https://cheever.domains.swarthmore.edu/Ref/mna/MNA2.html",
     "swarthmore-mna-tutorial.md", "nodal", 2, "MNA Tutorial (Swarthmore)"),

    # ML - Neural Amp Modeling
    ("https://neural-amp-modeler.readthedocs.io",
     "nam-docs.md", "ml", 2, "Neural Amp Modeler Docs"),
    ("https://mod.audio/neural-modeling/",
     "aida-x-overview.md", "ml", 2, "AIDA-X Overview"),
    ("https://mod.audio/modeling-amps-and-pedals-for-the-aida-x-plugin-best-practices/",
     "aida-x-best-practices.md", "ml", 2, "AIDA-X Best Practices"),
    ("https://www.soundsandwords.io/audio-loss-functions/",
     "audio-loss-functions.md", "ml", 2, "Audio Loss Functions Overview"),

    # EE Textbooks (free online)
    ("https://www.allaboutcircuits.com/textbook/",
     "aac-textbook-index.md", "textbooks", 2, "All About Circuits Textbook Index"),
    ("https://www2.mvcc.edu/users/faculty/jfiore/freebooks.html",
     "fiore-free-textbooks.md", "textbooks", 2, "Jim Fiore Free EE Textbooks"),

    # JUCE DSP
    ("https://docs.juce.com/master/tutorial_dsp_introduction.html",
     "juce-dsp-intro.md", "juce", 2, "JUCE DSP Introduction Tutorial"),
    ("https://thewolfsound.com/lowpass-highpass-filter-plugin-with-juce/",
     "wolfsound-juce-filter.md", "juce", 2, "WolfSound JUCE Filter Tutorial"),

    # Reverb comparison
    ("https://www.liquidsonics.com/2019/06/26/what-is-the-difference-between-algorithmic-and-convolution-reverb/",
     "liquidsonics-algo-vs-convolution.md", "spring-reverb", 2, "Algorithmic vs Convolution Reverb"),
    ("https://www.izotope.com/en/learn/the-basics-of-convolution-in-audio-production.html",
     "izotope-convolution-basics.md", "spring-reverb", 2, "iZotope Convolution Basics"),

    # ── TIER 3: GitHub Repos (clone README + key docs) ────────
    ("https://github.com/Chowdhury-DSP/chowdsp_wdf",
     "chowdsp-wdf", "wdf", 3, "chowdsp_wdf — Production C++ WDF Library"),
    ("https://github.com/jatinchowdhury18/RTNeural",
     "rtneural", "ml", 3, "RTNeural — Real-Time Neural Network Inference"),
    ("https://github.com/GuitarML/GuitarLSTM",
     "guitar-lstm", "ml", 3, "GuitarLSTM — LSTM Guitar Amp Modeling"),
    ("https://github.com/GuitarML/PedalNetRT",
     "pedalnet-rt", "ml", 3, "PedalNetRT — WaveNet Guitar Pedal"),
    ("https://github.com/sdatkinson/neural-amp-modeler",
     "neural-amp-modeler", "ml", 3, "Neural Amp Modeler"),
    ("https://github.com/je3928/RE201models",
     "re201-models", "space-echo", 3, "RE-201 Digital Models (VST3/AU)"),
    ("https://github.com/jatinchowdhury18/KlonCentaur",
     "chow-centaur", "schematics", 3, "ChowCentaur — WDF + RNN Klon Clone"),
    ("https://github.com/jatinchowdhury18/AnalogTapeModel",
     "chow-tape", "va", 3, "ChowTapeModel — Tape Emulation"),
    ("https://github.com/GuitarML/SmartGuitarPedal",
     "smart-guitar-pedal", "ml", 3, "SmartGuitarPedal — Neural Pedal"),
    ("https://github.com/resonantdsp/SwankyAmp",
     "swanky-amp", "va", 3, "SwankyAmp — Tube Amp Simulator"),
    ("https://github.com/dstrub18/NDKFramework",
     "ndk-framework", "nodal", 3, "NDK Framework — Nodal DK Method"),
    ("https://github.com/jatinchowdhury18/WaveDigitalFilters",
     "wdf-examples", "wdf", 3, "WDF Examples (JUCE)"),
    ("https://github.com/jatinchowdhury18/differentiable-wdfs",
     "differentiable-wdfs", "wdf", 3, "Differentiable WDFs"),
    ("https://github.com/Chowdhury-DSP/chowdsp_utils",
     "chowdsp-utils", "va", 3, "chowdsp_utils — DSP Utilities"),
    ("https://github.com/magenta/ddsp",
     "ddsp", "ml", 3, "Google DDSP — Differentiable DSP"),
    ("https://github.com/dsharlet/LiveSPICE",
     "live-spice", "spice", 3, "LiveSPICE — Real-Time Audio SPICE"),
    ("https://github.com/eliot-des/Modified-Nodal-Analysis-Algorithm",
     "mna-algorithm", "nodal", 3, "MNA for Real-Time Audio"),
    ("https://github.com/Cushychicken/ltspice-guitar-pedals",
     "ltspice-guitar-pedals", "spice", 3, "LTspice Guitar Pedal Models"),
    ("https://github.com/JoshFalejczyk/ProCo-RAT-2-LTSpice-Simulation",
     "ltspice-proco-rat", "spice", 3, "ProCo RAT 2 LTspice Simulation"),
    ("https://github.com/GuitarML/mldsp-papers",
     "mldsp-papers", "ml", 3, "ML/DSP Papers Collection"),
    ("https://github.com/olilarkin/awesome-musicdsp",
     "awesome-musicdsp", "va", 3, "Awesome MusicDSP Collection"),
    ("https://github.com/sudara/awesome-juce",
     "awesome-juce", "juce", 3, "awesome-juce — JUCE Resources"),
    ("https://github.com/mchijmma/modeling-plate-spring-reverb",
     "ml-spring-reverb", "spring-reverb", 3, "ML Plate & Spring Reverb Model"),
    ("https://github.com/ABSounds/EQP-WDF-1A",
     "eqp-wdf", "wdf", 3, "Pultec EQP-1A WDF (VST3)"),
    ("https://github.com/jatinchowdhury18/RTNeural-example",
     "rtneural-example", "ml", 3, "RTNeural JUCE Example Plugin"),
    ("https://github.com/Alec-Wright/Automated-GuitarAmpModelling",
     "automated-amp-modelling", "ml", 3, "Automated Guitar Amp Modelling"),

    # ── TIER 1 ADDITIONS: More PDFs ─────────────────────────
    # Werner & Smith 2015 overview
    ("https://www.ntnu.edu/documents/1001201110/0/werner+and+smith+2015,+recent+progress+in+wave+digital+audio+effects.pdf",
     "werner-smith-2015-progress-wdf.pdf", "wdf", 1, "Werner & Smith - Recent Progress in WDF (2015)"),
    # Arxiv ML papers
    ("https://arxiv.org/pdf/1910.10105",
     "ml-plate-spring-reverb-paper.pdf", "spring-reverb", 1, "ML Plate & Spring Reverb Model Paper"),
    ("https://arxiv.org/pdf/1911.08922",
     "perceptual-loss-audio.pdf", "ml", 1, "Perceptual Loss for Audio"),
    ("https://arxiv.org/pdf/2408.11405",
     "ddsp-guitar-amp.pdf", "ml", 1, "DDSP Guitar Amp Paper"),
    ("https://arxiv.org/pdf/2403.08559",
     "end-to-end-amp-modeling.pdf", "ml", 1, "End-to-End Amp Modeling Paper"),
    # ResearchGate PDFs
    ("https://www.researchgate.net/profile/Vesa-Vaelimaeki/publication/220057482/links/0deec51e6f0c32bba5000000/Spring-Reverberation-A-Physical-Perspective.pdf",
     "valimaki-spring-reverb-physical.pdf", "spring-reverb", 1, "Valimaki - Spring Reverb Physical Perspective"),
    # Alec Wright thesis
    ("https://aaltodoc.aalto.fi/bitstreams/7a523f71-1e3f-49e0-86f2-db7096e3c267/download",
     "alec-wright-doctoral-thesis.pdf", "ml", 1, "Alec Wright Doctoral Thesis (Neural Audio)"),
    # MDPI open access
    ("https://www.mdpi.com/2076-3417/10/3/766/pdf",
     "mdpi-realtime-amp-deep-learning.pdf", "ml", 1, "Real-Time Amp Emulation Deep Learning"),
    ("https://www.mdpi.com/2076-3417/12/12/5894/pdf",
     "mdpi-nn-guitar-amp-review.pdf", "ml", 1, "Review of NN Guitar Amp Emulation"),
    # Pakarinen & Yeh review
    ("https://www.semanticscholar.org/paper/A-Review-of-Digital-Techniques-for-Modeling-Guitar-Pakarinen-Yeh/9c46afe07f0097511d84a3236adbb216abac99fd",
     "pakarinen-yeh-tube-amp-review.pdf", "va", 1, "Pakarinen & Yeh Tube Amp Modeling Review"),

    # ── TIER 2 ADDITIONS: More HTML articles ──────────────────
    # Schematic archives
    ("https://www.diystompboxes.com/pedals/schematics.html",
     "diystompboxes-schematics.md", "schematics", 2, "DIYStompboxes Schematics Index"),
    ("https://www.diystompboxes.com/pedals/diodes.html",
     "diystompboxes-diode-guide.md", "distortion", 2, "DIYStompboxes Diode Guide"),
    ("https://www.coda-effects.com/p/klon-centaur-circuit-analysis.html",
     "coda-klon-centaur.md", "schematics", 2, "Coda Effects Klon Centaur Analysis"),

    # Component SPICE models
    ("http://www.ecircuitcenter.com/Circuits/cmodel1/cmodel1.htm",
     "ecircuitcenter-capacitor-model.md", "spice", 2, "eCircuitCenter Capacitor Model"),
    ("https://www.bartola.co.uk/valves/2020/06/10/d3a-spice-model-pentode-triode/",
     "bartola-valve-spice.md", "spice", 2, "Bartola Valve SPICE Models"),
    ("https://resources.pcb.cadence.com/blog/2020-spice-model-parameters-for-semiconductor-components",
     "cadence-spice-parameters.md", "spice", 2, "Cadence SPICE Parameters"),
    ("https://www.electronicdesign.com/technologies/analog/article/55246421/",
     "electronicdesign-tube-models.md", "spice", 2, "Electronic Design Nonlinear Tube Models"),

    # LTspice
    ("https://hackaday.com/2020/10/29/rockin-out-in-ltspice-simulating-classic-guitar-pedals/",
     "hackaday-ltspice-pedals.md", "spice", 2, "Hackaday Rockin Out in LTspice"),

    # Spring reverb extras
    ("https://ccrma.stanford.edu/~nolting/424/",
     "ccrma-nolting-spring-reverb.md", "spring-reverb", 2, "CCRMA Nolting Spring Reverb"),
    ("https://www.theaudioprogrammer.com/podcast/the-magic-behind-valhalla-reverbs-w-sean-costello-valhalla-dsp-ep-10",
     "audio-programmer-costello.md", "spring-reverb", 2, "Audio Programmer - Sean Costello Interview"),

    # Space Echo extras
    ("https://soundgas.com/blogs/resources/roland-tape-echo-service-manuals",
     "soundgas-re201-manuals.md", "space-echo", 2, "Soundgas RE-201 Service Manuals"),

    # EE textbooks
    ("https://www.ibiblio.org/kuphaldt/electricCircuits/",
     "kuphaldt-lessons-index.md", "textbooks", 2, "Kuphaldt Lessons in Electric Circuits"),
    ("https://analog-electronics.ewi.tudelft.nl/webbook/SED/",
     "tudelft-structured-electronics.md", "textbooks", 2, "TU Delft Structured Electronics Design"),
    ("https://open.umn.edu/opentextbooks/textbooks/883",
     "open-umn-ac-circuits.md", "textbooks", 2, "Open UMN AC Circuit Analysis"),

    # ML tutorials
    ("https://medium.com/mlearning-ai/real-time-neural-network-inferencing-for-audio-processing-857313fd84e1",
     "medium-rtneural-article.md", "ml", 2, "RTNeural Article (Medium)"),
    ("https://neuraldsp.com/news/neural-dsp-amplifier-modeling-technology",
     "neuraldsp-technology.md", "ml", 2, "Neural DSP Technology Overview"),

    # Faust WDF
    ("https://faustlibraries.grame.fr/libs/wdmodels/",
     "faust-wdf-library.md", "wdf", 2, "Faust WDF Library Docs"),

    # JUCE extras
    ("https://docs.juce.com/master/classdsp_1_1StateVariableFilter_1_1Filter.html",
     "juce-svf-tpt-reference.md", "juce", 2, "JUCE StateVariableTPTFilter Reference"),

    # Musicdsp archive
    ("http://www.musicdsp.org/archive.php",
     "musicdsp-archive.md", "va", 2, "musicdsp.org Archive"),

    # chowdsp_wdf docs
    ("https://ccrma.stanford.edu/~jatin/chowdsp/chowdsp_wdf/",
     "chowdsp-wdf-docs.md", "wdf", 2, "chowdsp_wdf Documentation"),

    # Sampling user controls (ML training data)
    ("https://asmp-eurasipjournals.springeropen.com/articles/10.1186/s13636-024-00347-5",
     "sampling-user-controls.md", "ml", 2, "Sampling User Controls for ML Training"),

    # ── TIER 3 ADDITIONS: More GitHub repos ───────────────────
    ("https://github.com/AndrewBelt/WDFplusplus",
     "wdfplusplus", "wdf", 3, "WDFplusplus — Easy C++ WDF Classes"),

    # ── TIER 4 ADDITIONS: More forum threads ──────────────────
    # ── TIER 4: Forum Threads (selective scrape) ──────────────
    ("https://www.kvraudio.com/forum/viewtopic.php?t=501994",
     "kvr-newton-raphson.md", "newton-raphson", 4, "KVR Newton-Raphson Discussion"),
    ("https://www.kvraudio.com/forum/viewtopic.php?t=452562",
     "kvr-spring-reverb-papers.md", "spring-reverb", 4, "KVR Spring Reverb Papers"),
    ("https://www.kvraudio.com/forum/viewtopic.php?t=531202",
     "kvr-reverb-design.md", "spring-reverb", 4, "KVR Reverb Design Discussion"),
    ("https://www.kvraudio.com/forum/viewtopic.php?t=499395",
     "kvr-tape-emulation.md", "space-echo", 4, "KVR Tape Emulation Discussion"),
    ("https://www.kvraudio.com/forum/viewtopic.php?t=318629",
     "kvr-tape-saturation-filters.md", "space-echo", 4, "KVR Tape Saturation Filters"),
    ("https://www.freestompboxes.org/viewtopic.php?t=29048",
     "fsb-re201-analysis.md", "space-echo", 4, "RE-201 Circuit Analysis (FSB)"),
    ("https://groupdiy.com/threads/spring-reverb-from-the-60s.69451/",
     "groupdiy-60s-spring-reverb.md", "spring-reverb", 4, "GroupDIY 1960s Spring Reverb"),
    ("https://www.tdpri.com/threads/solid-state-spring-tank-reverb-circuit.614834/",
     "tdpri-spring-reverb.md", "spring-reverb", 4, "TDPRI Solid-State Spring Reverb"),
    ("https://www.diyaudio.com/community/threads/vacuum-tube-spice-models.243950/",
     "diyaudio-tube-spice.md", "spice", 4, "DIYAudio Tube SPICE Models"),
    ("https://forum.juce.com/t/juce-module-for-analogue-modelling/28534",
     "juce-forum-analogue-modelling.md", "juce", 4, "JUCE Forum Analogue Modelling Module"),
]

# ============================================================
# CATEGORIES for filtering
# ============================================================
CATEGORIES = {
    "wdf": "Wave Digital Filters",
    "va": "Virtual Analog Modeling",
    "spice": "SPICE Simulation",
    "nodal": "Nodal Analysis / DK-Method",
    "newton-raphson": "Newton-Raphson Iteration",
    "schematics": "Classic Pedal Schematics",
    "distortion": "Distortion Modules",
    "space-echo": "Space Echo / BBD / Tape",
    "spring-reverb": "Spring Reverb Modeling",
    "ml": "ML + Circuit Modeling",
    "whitebox": "White-Box Circuit Analysis",
    "textbooks": "EE Textbooks",
    "juce": "JUCE Integration",
}


class CircuitModelingScraper:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or os.path.expanduser("~/Development/circuit-modeling"))
        self.pdfs_dir = self.base_dir / "pdfs"
        self.articles_dir = self.base_dir / "articles"
        self.repos_dir = self.base_dir / "repos"
        self.forums_dir = self.base_dir / "forums"
        self.metadata_dir = self.base_dir / "metadata"

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        self.stats = {
            "downloaded": 0,
            "skipped": 0,
            "errors": 0,
            "bytes": 0,
        }
        self.errors = []

    def setup_dirs(self):
        """Create directory structure."""
        for d in [self.pdfs_dir, self.articles_dir, self.repos_dir,
                  self.forums_dir, self.metadata_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Category subdirs for articles
        for cat in CATEGORIES:
            (self.articles_dir / cat).mkdir(exist_ok=True)
            (self.pdfs_dir / cat).mkdir(exist_ok=True)

    def _get_output_path(self, filename, category, tier):
        """Get the output path based on tier."""
        if tier == 1:
            return self.pdfs_dir / category / filename
        elif tier == 2:
            return self.articles_dir / category / filename
        elif tier == 3:
            return self.repos_dir / filename
        elif tier == 4:
            return self.forums_dir / filename
        return self.base_dir / filename

    def _already_downloaded(self, path):
        """Check if file already exists and has content."""
        if path.is_file() and path.stat().st_size > 100:
            return True
        if path.is_dir() and any(path.iterdir()):
            return True
        return False

    def download_pdf(self, url, filepath, description):
        """Download a PDF file."""
        if self._already_downloaded(filepath):
            print(f"  SKIP (exists): {description}")
            self.stats["skipped"] += 1
            return True

        print(f"  GET: {description}")
        try:
            time.sleep(0.5)
            resp = self.session.get(url, timeout=60, stream=True)
            resp.raise_for_status()

            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            size = filepath.stat().st_size
            self.stats["downloaded"] += 1
            self.stats["bytes"] += size
            print(f"       OK ({size // 1024}KB)")
            return True

        except Exception as e:
            self.errors.append({"url": url, "error": str(e)})
            self.stats["errors"] += 1
            print(f"       FAIL: {e}")
            return False

    def scrape_html(self, url, filepath, description):
        """Scrape HTML page and convert to markdown."""
        if self._already_downloaded(filepath):
            print(f"  SKIP (exists): {description}")
            self.stats["skipped"] += 1
            return True

        print(f"  GET: {description}")
        try:
            time.sleep(1.0)  # Be polite
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Remove nav, footer, scripts, styles
            for tag in soup.find_all(['nav', 'footer', 'script', 'style',
                                       'header', 'aside']):
                tag.decompose()

            # Try to find main content
            main = (soup.find('article') or
                    soup.find('main') or
                    soup.find('div', class_=re.compile(r'content|post|article|entry')) or
                    soup.find('body'))

            if main is None:
                main = soup

            # Get title
            title_tag = soup.find('title')
            title = title_tag.get_text().strip() if title_tag else description

            # Convert to markdown
            content = md(str(main), heading_style="ATX", strip=['img'])

            # Build output with frontmatter
            output = f"""---
title: "{title}"
source: "{url}"
category: "{filepath.parent.name}"
scraped: "{datetime.now().isoformat()}"
---

# {title}

> Source: {url}

{content.strip()}
"""
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(output, encoding='utf-8')

            size = filepath.stat().st_size
            self.stats["downloaded"] += 1
            self.stats["bytes"] += size
            print(f"       OK ({size // 1024}KB)")
            return True

        except Exception as e:
            self.errors.append({"url": url, "error": str(e)})
            self.stats["errors"] += 1
            print(f"       FAIL: {e}")
            return False

    def clone_repo(self, url, dirname, description):
        """Clone GitHub repo (shallow, docs only)."""
        repo_path = self.repos_dir / dirname

        if self._already_downloaded(repo_path):
            print(f"  SKIP (exists): {description}")
            self.stats["skipped"] += 1
            return True

        print(f"  CLONE: {description}")
        try:
            # Shallow clone (depth 1, no blobs except top-level)
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url + ".git", str(repo_path)],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode != 0:
                # Try without .git suffix
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", url, str(repo_path)],
                    capture_output=True, text=True, timeout=120
                )

            if result.returncode == 0:
                # Remove .git to save space
                git_dir = repo_path / ".git"
                if git_dir.exists():
                    subprocess.run(["rm", "-rf", str(git_dir)], check=True)

                self.stats["downloaded"] += 1
                # Count bytes
                total = sum(f.stat().st_size for f in repo_path.rglob("*") if f.is_file())
                self.stats["bytes"] += total
                print(f"       OK ({total // 1024}KB)")
                return True
            else:
                raise Exception(result.stderr[:200])

        except Exception as e:
            self.errors.append({"url": url, "error": str(e)})
            self.stats["errors"] += 1
            print(f"       FAIL: {e}")
            return False

    def scrape_source(self, url, filename, category, tier, description):
        """Route to correct handler based on tier."""
        filepath = self._get_output_path(filename, category, tier)

        if tier == 1:
            return self.download_pdf(url, filepath, description)
        elif tier == 2:
            return self.scrape_html(url, filepath, description)
        elif tier == 3:
            return self.clone_repo(url, filename, description)
        elif tier == 4:
            return self.scrape_html(url, filepath, description)

    def run(self, tier_filter=None, category_filter=None, dry_run=False):
        """Run the scraper."""
        self.setup_dirs()

        sources = SOURCES
        if tier_filter is not None:
            sources = [s for s in sources if s[3] == tier_filter]
        if category_filter is not None:
            sources = [s for s in sources if s[2] == category_filter]

        print(f"\n{'='*60}")
        print(f"Circuit Modeling KB Scraper")
        print(f"{'='*60}")
        print(f"Sources: {len(sources)} | Output: {self.base_dir}")
        if tier_filter:
            print(f"Filter: Tier {tier_filter}")
        if category_filter:
            print(f"Filter: Category '{category_filter}'")
        print(f"{'='*60}\n")

        if dry_run:
            for url, filename, category, tier, desc in sources:
                path = self._get_output_path(filename, category, tier)
                exists = "EXISTS" if self._already_downloaded(path) else "NEW"
                print(f"  [{exists}] T{tier} [{category}] {desc}")
                print(f"         {url}")
            print(f"\nTotal: {len(sources)} sources")
            return

        # Group by tier for organized output
        for t in sorted(set(s[3] for s in sources)):
            tier_sources = [s for s in sources if s[3] == t]
            tier_names = {1: "PDFs", 2: "HTML Articles", 3: "GitHub Repos", 4: "Forum Threads"}
            print(f"\n── Tier {t}: {tier_names.get(t, 'Unknown')} ({len(tier_sources)} sources) ──\n")

            for url, filename, category, tier, desc in tier_sources:
                self.scrape_source(url, filename, category, tier, desc)

        # Write metadata
        self._write_metadata()
        self._print_summary()

    def _write_metadata(self):
        """Write scraping metadata."""
        meta = {
            "scraped_at": datetime.now().isoformat(),
            "stats": self.stats,
            "errors": self.errors,
            "total_sources": len(SOURCES),
            "categories": {k: v for k, v in CATEGORIES.items()},
        }
        meta_file = self.metadata_dir / "scrape-log.json"
        meta_file.write_text(json.dumps(meta, indent=2))

        # Also write a manifest of what we have
        manifest = []
        for url, filename, category, tier, desc in SOURCES:
            path = self._get_output_path(filename, category, tier)
            exists = self._already_downloaded(path)
            size = 0
            if exists:
                if path.is_file():
                    size = path.stat().st_size
                elif path.is_dir():
                    size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            manifest.append({
                "url": url,
                "filename": filename,
                "category": category,
                "tier": tier,
                "description": desc,
                "downloaded": exists,
                "size_bytes": size,
            })

        manifest_file = self.metadata_dir / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2))

    def _print_summary(self):
        """Print scraping summary."""
        print(f"\n{'='*60}")
        print(f"SCRAPING COMPLETE")
        print(f"{'='*60}")
        print(f"  Downloaded: {self.stats['downloaded']}")
        print(f"  Skipped:    {self.stats['skipped']}")
        print(f"  Errors:     {self.stats['errors']}")
        print(f"  Total size: {self.stats['bytes'] // 1024}KB ({self.stats['bytes'] // (1024*1024)}MB)")
        print(f"  Output:     {self.base_dir}")

        if self.errors:
            print(f"\n  Errors:")
            for err in self.errors[:10]:
                print(f"    - {err['url'][:60]}...")
                print(f"      {err['error'][:80]}")

        print(f"\n  Tokens burned: 0")
        print(f"  Carbon impact: Minimal (code execution only)")
        print(f"{'='*60}\n")

    def report(self):
        """Print current collection stats."""
        self.setup_dirs()
        print(f"\n{'='*60}")
        print(f"Circuit Modeling KB — Collection Report")
        print(f"{'='*60}")

        for t in [1, 2, 3, 4]:
            tier_names = {1: "PDFs", 2: "HTML Articles", 3: "GitHub Repos", 4: "Forum Threads"}
            tier_sources = [s for s in SOURCES if s[3] == t]
            collected = 0
            total_size = 0
            for url, filename, category, tier, desc in tier_sources:
                path = self._get_output_path(filename, category, tier)
                if self._already_downloaded(path):
                    collected += 1
                    if path.is_file():
                        total_size += path.stat().st_size
                    elif path.is_dir():
                        total_size += sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

            print(f"\n  Tier {t} ({tier_names[t]}): {collected}/{len(tier_sources)} collected ({total_size // 1024}KB)")

        print(f"\n  By Category:")
        for cat, label in CATEGORIES.items():
            cat_sources = [s for s in SOURCES if s[2] == cat]
            collected = sum(1 for s in cat_sources
                           if self._already_downloaded(self._get_output_path(s[1], s[2], s[3])))
            print(f"    {label}: {collected}/{len(cat_sources)}")

        print(f"\n{'='*60}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Circuit Modeling KB Scraper")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4],
                        help="Only scrape specific tier")
    parser.add_argument("--category", type=str, choices=list(CATEGORIES.keys()),
                        help="Only scrape specific category")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be scraped without downloading")
    parser.add_argument("--report", action="store_true",
                        help="Show collection statistics")
    parser.add_argument("--output", type=str,
                        default=os.path.expanduser("~/Development/circuit-modeling"),
                        help="Output directory")
    args = parser.parse_args()

    scraper = CircuitModelingScraper(base_dir=args.output)

    if args.report:
        scraper.report()
    else:
        scraper.run(
            tier_filter=args.tier,
            category_filter=args.category,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
