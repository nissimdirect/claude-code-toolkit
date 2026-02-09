# Circuit Modeling & Virtual Analog Reference

> **Purpose:** Master source list for circuit-level audio plugin development.
> **Created:** 2026-02-09 | **Topics:** 15 | **Sources:** 150+
> **Related:** JUCE docs, DSP Cookbook, Audio DSP Projects reference docs
> **Skills:** /cto, /plugin, /audio-production

---

## Coverage Checklist

| # | Topic | Status | Sources |
|---|-------|--------|---------|
| 1 | Component-level SPICE modeling | COVERED | 12 |
| 2 | Circuit modeling (general) | COVERED | 15 |
| 3 | ML + circuit modeling | COVERED | 20 |
| 4 | White-box circuit analysis | COVERED | 8 |
| 5 | Wave Digital Filters (WDF) | COVERED | 18 |
| 6 | Nodal analysis | COVERED | 10 |
| 7 | SPICE simulation | COVERED | 10 |
| 8 | Newton-Raphson iteration | COVERED | 8 |
| 9 | Classic pedal schematics | COVERED | 12 |
| 10 | Distortion modules | COVERED | 10 |
| 11 | Space Echo (Roland RE-201) | COVERED | 8 |
| 12 | Studio gear repair forums | COVERED | 10 |
| 13 | EE textbooks & SPICE tutorials | COVERED | 12 |
| 14 | Academic papers (WDF/VA) | COVERED | 15 |
| 15 | Spring reverb modeling | COVERED | 25 |

---

## 1. SPICE Modeling & Simulation

### SPICE Tools
- **LTspice** (Analog Devices): https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html
- **ngspice** (open source): https://ngspice.sourceforge.io/
- **LiveSPICE** (real-time audio): https://www.livespice.org/ | GitHub: https://github.com/dsharlet/LiveSPICE
- **KiCad SPICE**: https://www.kicad.org/discover/spice/

### SPICE Tutorials
- ngspice beginner tutorial: https://ngspice.sourceforge.io/ngspice-tutorial.html
- ngspice control language: https://ngspice.sourceforge.io/ngspice-control-language-tutorial.html
- All tutorials: https://ngspice.sourceforge.io/tutorials.html
- Simulating audio effects with SPICE: https://hforsten.com/simulating-audio-effects-with-spice.html
- MIT SPICE Lab: https://pcb.mit.edu/labs/lab_02/
- eCircuitCenter SPICE Basics: https://www.ecircuitcenter.com/Basics.htm
- Virtual SPICE Guide (UMN): http://www.hkn.umn.edu/resources/files/spice/VirtualSpice.pdf

### LTspice Guitar Pedal Tutorials
- Tube Screamer in LTspice: https://cushychicken.github.io/posts/ltspice-tube-screamer/
- Rockin' Out in LTspice (Hackaday): https://hackaday.com/2020/10/29/rockin-out-in-ltspice-simulating-classic-guitar-pedals/
- GitHub repo: https://github.com/Cushychicken/ltspice-guitar-pedals
- PedalPCB LTspice tutorials: Parts 1-3 at https://forum.pedalpcb.com/
- ProCo RAT 2 LTspice simulation: https://github.com/JoshFalejczyk/ProCo-RAT-2-LTSpice-Simulation

### Vacuum Tube SPICE Models
- Norman Koren tube models Part 1: https://www.normankoren.com/Audio/Tubemodspice_article.html
- Norman Koren tube models Part 2: https://www.normankoren.com/Audio/Tubemodspice_article_2.html
- Leach tube amp SPICE models (PDF): https://leachlegacy.ece.gatech.edu/papers/tubeamp/tubeamp.pdf
- Electronic Design nonlinear tube models: https://www.electronicdesign.com/technologies/analog/article/55246421/
- Bartola valve SPICE models: https://www.bartola.co.uk/valves/2020/06/10/d3a-spice-model-pentode-triode/
- LTSpice tube models (GitHub Gist): https://gist.github.com/chanmix51/6947361
- diyAudio tube SPICE models: https://www.diyaudio.com/community/threads/vacuum-tube-spice-models.243950/

### Component Modeling
- SPICE models for resistors/capacitors: https://www.allaboutcircuits.com/textbook/designing-analog-chips/simulation/spice-models-for-resistors-and-capacitors/
- Capacitor model: http://www.ecircuitcenter.com/Circuits/cmodel1/cmodel1.htm
- Cadence SPICE parameters: https://resources.pcb.cadence.com/blog/2020-spice-model-parameters-for-semiconductor-components

---

## 2. Wave Digital Filters (WDF)

### Essential Reading
- David Yeh WDF Tutorial (PDF): https://ccrma.stanford.edu/~dtyeh/papers/wdftutorial.pdf
- Kurt Werner WDF Dissertation (261pp PDF): https://stacks.stanford.edu/file/druid:jy057cz8322/KurtJamesWernerDissertation-augmented.pdf
- Julius O. Smith WDF chapter: https://www.dsprelated.com/freebooks/pasp/Wave_Digital_Filters_I.html
- Jatin Chowdhury WDF in C++ slides: https://ccrma.stanford.edu/~jatin/slides/TAP_WDFs.pdf

### Code Libraries
- **chowdsp_wdf** (production C++ WDF): https://github.com/Chowdhury-DSP/chowdsp_wdf
- chowdsp_wdf docs: https://ccrma.stanford.edu/~jatin/chowdsp/chowdsp_wdf/
- chowdsp_wdf paper: https://www.researchgate.net/publication/364689194_chowdsp_wdf_An_Advanced_C_Library_for_Wave_Digital_Circuit_Modelling
- WDF Examples (JUCE): https://github.com/jatinchowdhury18/WaveDigitalFilters
- Differentiable WDFs: https://github.com/jatinchowdhury18/differentiable-wdfs
- Pultec EQP-1A WDF (VST3): https://github.com/ABSounds/EQP-WDF-1A
- WDFplusplus: https://github.com/AndrewBelt/WDFplusplus
- Faust WDF library: https://faustlibraries.grame.fr/libs/wdmodels/

### Key Papers
- Werner & Smith "Recent Progress in WDF" (PDF): https://www.ntnu.edu/documents/1001201110/0/werner+and+smith+2015,+recent+progress+in+wave+digital+audio+effects.pdf
- WDF adaptors for arbitrary topologies (DAFx 2015): https://dafx.de/paper-archive/2015/DAFx-15_submission_53.pdf
- RT-WDF modular library (DAFx 2016): https://www.dafx.de/paper-archive/2016/dafxpapers/40-DAFx-16_paper_35-PN.pdf
- WDF with op-amps: https://www.researchgate.net/publication/305982704_Wave_Digital_Filter_Modeling_of_Circuits_with_Operational_Amplifiers
- Antiderivative antialiasing in WDF (DAFx 2020): https://dafx2020.mdw.ac.at/proceedings/papers/DAFx2020_paper_35.pdf
- Wave Digital Newton-Raphson: https://re.public.polimi.it/bitstream/11311/1203185/1/WD_NR_TASLP_Bernardini_etal_2021_RG.pdf
- Explicit Vector WDF (DAFx 2023): https://www.dafx.de/paper-archive/2023/DAFx23_paper_60.pdf
- WDF tutorial (DAFx 2019 Kurt Werner): https://dafx2019.bcu.ac.uk/programme/mon/tutorial-werner

---

## 3. Virtual Analog (VA) Modeling

### Essential Books (FREE)
- **Vadim Zavalishin "The Art of VA Filter Design"**: https://www.native-instruments.com/fileadmin/ni_media/downloads/pdf/VAFilterDesign_2.1.0.pdf
- Julius O. Smith "Physical Audio Signal Processing": https://ccrma.stanford.edu/~jos/pasp/
- Julius O. Smith "Introduction to Digital Filters": https://ccrma.stanford.edu/~jos/filters/
- Julius O. Smith "Spectral Audio Signal Processing": https://ccrma.stanford.edu/~jos/sasp/
- Will Pirkle VA Filter Comparison (PDF): https://forum.audulus.com/uploads/default/original/2X/8/82ea1a4ef055962ff4a50bcdf5e21f7aa895bebd.pdf

### Nodal Analysis & DK-Method
- David Yeh "Automated Physical Modeling Part I" (PDF): https://ccrma.stanford.edu/~dtyeh/papers/yeh10_taslp.pdf
- David Yeh "Automated Physical Modeling Part II" (PDF): https://ccrma.stanford.edu/~dtyeh/papers/yeh12_taslp.pdf
- NDK Framework (GitHub, ADC 2019): https://github.com/dstrub18/NDKFramework
- Simulation framework for Nodal DK: https://www.researchgate.net/publication/263013830_Simulation_Framework_for_Analog_Audio_Circuits_based_on_Nodal_DK_Method
- MNA for real-time audio (GitHub): https://github.com/eliot-des/Modified-Nodal-Analysis-Algorithm
- MNA tutorial (Swarthmore): https://cheever.domains.swarthmore.edu/Ref/mna/MNA2.html
- Generalized state-space derivation: https://www.researchgate.net/publication/282074338

### Newton-Raphson for Audio
- Newton-Raphson in WDF: https://www.researchgate.net/publication/351938266_A_Wave_Digital_Newton-Raphson_Method
- Diode clipper convergence: https://www.researchgate.net/figure/Diode-clipper-Iterations-of-Newton-Raphson_fig2_354380067
- Diode limiter simulation: https://www.researchgate.net/publication/266049262_Simulation_of_the_diode_limiter_in_guitar_distortion_circuits
- KVR Newton-Raphson discussion: https://www.kvraudio.com/forum/viewtopic.php?t=501994
- Diode clipper WDF model: https://www.researchgate.net/publication/299514713_An_Improved_and_Generalized_Diode_Clipper_Model_for_Wave_Digital_Filters

### White-Box Circuit Analysis
- Differentiable white-box VA modeling (DAFx 2021): https://dafx.de/paper-archive/2021/proceedings/papers/DAFx20in21_paper_39.pdf
- Lightweight VA modeling (PDF): https://dangelo.audio/docs/lightweightva.pdf
- AIDA DSP modeling techniques review: https://aidadsp.github.io/2020/04/13/analog-modeling-techniques-review.html
- Sound on Sound "Plug-in Modelling: How Industry Experts Do It": https://www.soundonsound.com/techniques/plug-in-modelling-how-industry-experts-do-it

---

## 4. Classic Pedal Schematics & Analysis

### ElectroSmash (GOLD STANDARD for pedal analysis)
- Main site: https://www.electrosmash.com/
- Big Muff Pi analysis: https://www.electrosmash.com/big-muff-pi-analysis
- Fuzz Face analysis: https://www.electrosmash.com/fuzz-face
- Tube Screamer analysis: https://electrosmash.com/tube-screamer-analysis
- Klon Centaur analysis: https://www.electrosmash.com/klon-centaur-analysis
- Boss DS-1 analysis: https://www.electrosmash.com/boss-ds1-analysis
- MXR Distortion+ analysis: https://www.electrosmash.com/mxr-distortion-plus-analysis
- Germanium Fuzz: https://www.electrosmash.com/germanium-fuzz
- BBD MN3007 analysis: https://www.electrosmash.com/mn3007-bucket-brigade-devices

### Schematic Archives
- Freestompboxes.org schematics index: https://www.freestompboxes.org/viewtopic.php?t=1295
- Freestompboxes.org projects by effect: https://www.freestompboxes.org/viewtopic.php?t=11622
- DIYstompboxes schematics: https://www.diystompboxes.com/pedals/schematics.html
- Audio Schematics DK (90,000+ schematics): https://audioschematics.dk/
- Coda Effects Klon Centaur analysis: https://www.coda-effects.com/p/klon-centaur-circuit-analysis.html
- Geofex Fuzz Face technology: http://www.geofex.com/article_folders/fuzzface/fftech.htm

### Distortion Circuits
- DIYstompboxes diode guide: https://www.diystompboxes.com/pedals/diodes.html
- Electric Druid distortion design: https://electricdruid.net/designing-the-hard-bargain-distortion-pedal/
- General Guitar Gadgets distortion design: https://generalguitargadgets.com/how-to-build-it/technical-help/articles/design-distortion/
- Wampler basic overdrive design: https://www.wamplerpedals.com/blog/latest-news/2020/05/how-to-design-a-basic-overdrive-pedal-circuit/

### Tube Amplifier Circuits
- Will Pirkle vacuum tube emulation (PDF): http://willpirkle.com/special/Addendum_A19_Pirkle_v1.0.pdf
- Review of tube amp modeling techniques: https://www.semanticscholar.org/paper/A-Review-of-Digital-Techniques-for-Modeling-Guitar-Pakarinen-Yeh/9c46afe07f0097511d84a3236adbb216abac99fd
- WDF vacuum tube simulation: https://www.researchgate.net/publication/224642046_Wave_Digital_Simulation_of_a_Vacuum-Tube_Amplifier

---

## 5. Space Echo (Roland RE-201) & BBD Delays

### RE-201 Circuit Analysis
- RE-201 circuit analysis (Freestompboxes): https://www.freestompboxes.org/viewtopic.php?t=29048
- RE-201 service manuals (Soundgas): https://soundgas.com/blogs/resources/roland-tape-echo-service-manuals
- RE-201 digital models (GitHub, VST3/AU): https://github.com/je3928/RE201models
- Inside the RE-202 (BOSS): https://articles.boss.info/inside-the-re-202-space-echo/

### BBD (Bucket Brigade Device) Modeling
- Practical BBD modeling (Colin Raffel, PDF): https://colinraffel.com/publications/dafx2010practical.pdf
- Combined BBD + filter model: https://www.researchgate.net/publication/327550964
- How BBDs work (EffDub Audio): https://effdubaudio.com/how-bbds-work/
- Anasounds BBD history: https://anasounds.com/miniaturization-of-the-delay-the-bbd/

### Tape Saturation
- Tape emulation explained (KVR): https://www.kvraudio.com/forum/viewtopic.php?t=499395
- Tape saturation filters (KVR): https://www.kvraudio.com/forum/viewtopic.php?t=318629
- Audio tape saturation patent: https://patents.google.com/patent/US5596646A/en

---

## 6. Spring Reverb Modeling (COMPREHENSIVE)

### Physical Modeling & DSP Algorithms
- Efficient dispersion for spring reverb: https://www.researchgate.net/publication/220057482
- Numerical simulation of spring reverberation: https://www.researchgate.net/publication/262731418
- Spring reverb physical perspective (Academia.edu): https://www.academia.edu/251885/Spring_Reverberation_A_Physical_Perspective
- ML plate and spring reverb model: https://arxiv.org/abs/1910.10105 | GitHub: https://github.com/mchijmma/modeling-plate-spring-reverb
- KVR spring reverb papers discussion: https://www.kvraudio.com/forum/viewtopic.php?t=452562
- music-dsp spring reverb modeling: https://music-dsp.music.columbia.narkive.com/bMxaRT85/modelling-a-spring-reverb
- CCRMA spring reverb work (Nolting): https://ccrma.stanford.edu/~nolting/424/

### Sean Costello / Valhalla DSP (Spring Reverb Expert)
- AES 2015 reverb presentation (PDF): https://www.aes-media.org/sections/pnw/ppt/costello/AES2015ReverbPresentation.pdf
- Minimalism in algorithm design: https://valhalladsp.com/2017/06/01/minimalism-algorithm-design/
- Algorithmic reverbs + distortion: https://valhalladsp.com/2011/07/07/algorithmic-reverbs-distortion-and-noise/
- Audio Programmer interview: https://www.theaudioprogrammer.com/podcast/the-magic-behind-valhalla-reverbs-w-sean-costello-valhalla-dsp-ep-10
- KVR reverb design discussion: https://www.kvraudio.com/forum/viewtopic.php?t=531202

### Accutronics Spring Tanks
- Spring tanks explained and compared: https://www.amplifiedparts.com/tech-articles/spring-reverb-tanks-explained-and-compared
- Accutronics specifications: https://www.amplifiedparts.com/tech-articles/accutronics-products-and-specifications
- Accutronics impulse response data: https://www.researchgate.net/figure/Example-impulse-response-measured-on-a-single-spring-of-an-Accutronics-Belton-9EB2C1B_fig1_344166234

### Fender Spring Reverb Circuits
- How spring reverb works (Rob Robinette): https://robrobinette.com/How_Spring_Reverb_Works.htm
- Fender 6G15 schematic (PDF): https://www.thetubestore.com/lib/thetubestore/schematics/Fender/Fender-Reverb-6G15-Schematic.pdf
- Build your own tube spring reverb: https://guitar.com/guides/diy-workshop/build-tube-spring-reverb-unit-amplifier/
- Lamington reverb (valve-based): https://valveheaven.com/2016/10/the-lamington-reverb/
- TDPRI solid-state spring reverb: https://www.tdpri.com/threads/solid-state-spring-tank-reverb-circuit.614834/

### Hammond Spring Reverb
- GroupDIY 1960s spring reverb: https://groupdiy.com/threads/spring-reverb-from-the-60s.69451/
- Organ Forum Hammond tank specifics: https://organforum.com/forums/forum/electronic-organs-midi/hammond-organs/33777
- Gearspace Hammond necklace spring tanks: https://gearspace.com/board/diy-electronic-build-refurbishment-photo-diaries/1356300
- History of spring reverb (Pulsar Audio): https://pulsar.audio/blog/the-history-of-spring-reverb/

### General Spring Reverb Technical
- Sound-AU spring reverb overview: https://sound-au.com/articles/reverb.htm
- Sound-AU Project 34 (DIY spring reverb): https://sound-au.com/project34.htm
- How analog spring reverb works (Anasounds): https://anasounds.com/analog-spring-reverb-how-it-works/
- How spring reverb circuits work (Bulinski): https://bulinskipedals.com/how-spring-reverb-circuits-work/
- Lords of the springs (Premier Guitar): https://www.premierguitar.com/articles/27240-lords-of-the-springs

### IR vs Physical Modeling
- Algorithmic vs convolution reverb (LiquidSonics): https://www.liquidsonics.com/2019/06/26/what-is-the-difference-between-algorithmic-and-convolution-reverb/
- Convolution basics (iZotope): https://www.izotope.com/en/learn/the-basics-of-convolution-in-audio-production.html
- Gearspace IR vs spring reverb discussion: https://gearspace.com/board/so-much-gear-so-little-time/194943

---

## 7. ML + Circuit Modeling

### Neural Amp Modeling
- **Neural Amp Modeler (NAM)**: https://github.com/sdatkinson/neural-amp-modeler
- NAM docs: https://neural-amp-modeler.readthedocs.io
- AIDA-X overview: https://mod.audio/neural-modeling/
- AIDA-X best practices: https://mod.audio/modeling-amps-and-pedals-for-the-aida-x-plugin-best-practices/
- Review of NN guitar amp emulation: https://www.mdpi.com/2076-3417/12/12/5894
- Real-time amp emulation with deep learning: https://www.mdpi.com/2076-3417/10/3/766
- Neural DSP technology overview: https://neuraldsp.com/news/neural-dsp-amplifier-modeling-technology

### LSTM/RNN for Audio
- GuitarLSTM (Keras): https://github.com/GuitarML/GuitarLSTM
- Stateful LSTM tutorial: https://towardsdatascience.com/neural-networks-for-real-time-audio-stateful-lstm-b534babeae5d/
- Comparative RNN study (DAFx 2019): https://dafx.de/paper-archive/2019/DAFx2019_paper_43.pdf
- LSTM nonlinear system modeling: https://www.sciencedirect.com/science/article/pii/S2405896318310814

### WaveNet for Audio
- PedalNetRT (PyTorch WaveNet): https://github.com/GuitarML/PedalNetRT
- WaveNet for audio tutorial: https://towardsdatascience.com/neural-networks-for-real-time-audio-wavenet-2b5cdf791c4f/
- Deep learning for tube amp emulation: https://www.researchgate.net/publication/328685761

### RTNeural (Real-Time Inference for JUCE)
- **RTNeural library**: https://github.com/jatinchowdhury18/RTNeural
- RTNeural example JUCE plugin: https://github.com/jatinchowdhury18/RTNeural-example
- RTNeural article (Medium): https://medium.com/mlearning-ai/real-time-neural-network-inferencing-for-audio-processing-857313fd84e1
- RTNeural paper: https://www.researchgate.net/publication/352209447

### Hybrid ML + Physics
- DDSP (Google Magenta): https://magenta.tensorflow.org/ddsp | GitHub: https://github.com/magenta/ddsp
- DDSP guitar amp: https://arxiv.org/html/2408.11405v1
- End-to-end amp modeling: https://arxiv.org/html/2403.08559v1
- Differentiable black-box + gray-box: https://arxiv.org/pdf/2502.14405
- Review of differentiable DSP: https://arxiv.org/pdf/2308.15422
- Alec Wright doctoral thesis: https://aaltodoc.aalto.fi/items/f376f16e-982a-485e-8412-1cb8362f9908

### Training Data & Methodology
- Sampling user controls: https://asmp-eurasipjournals.springeropen.com/articles/10.1186/s13636-024-00347-5
- Automated guitar amp modeling: https://github.com/Alec-Wright/Automated-GuitarAmpModelling
- Perceptual loss for audio: https://arxiv.org/abs/1911.08922
- Audio loss functions overview: https://www.soundsandwords.io/audio-loss-functions/
- ML/DSP papers collection: https://github.com/GuitarML/mldsp-papers

### Open Source Plugins (Source Code)
- ChowCentaur (WDF + RNN): https://github.com/jatinchowdhury18/KlonCentaur
- ChowTapeModel (tape emulation): https://github.com/jatinchowdhury18/AnalogTapeModel
- SmartGuitarPedal: https://github.com/GuitarML/SmartGuitarPedal
- SwankyAmp (tube amp sim): https://github.com/resonantdsp/SwankyAmp

---

## 8. EE Textbooks (Free Online)

### Tony R. Kuphaldt "Lessons in Electric Circuits" (6 volumes)
- Main site: https://www.ibiblio.org/kuphaldt/electricCircuits/
- Internet Archive: https://archive.org/details/lessonsinelectriccircuits
- All About Circuits version: https://www.allaboutcircuits.com/textbook/
- Covers: DC, AC, semiconductors, digital, reference, experiments

### Other Free Textbooks
- Jim Fiore free textbooks (DC/AC, op-amps): https://www2.mvcc.edu/users/faculty/jfiore/freebooks.html
- AC Circuit Analysis (Open Textbook): https://open.umn.edu/opentextbooks/textbooks/883
- MNA tutorial (Swarthmore): https://cheever.domains.swarthmore.edu/Ref/mna/MNA2.html
- MNA PDF (Spinning Numbers): https://spinningnumbers.org/assets/modified-nodal-analysis.pdf
- TU Delft Structured Electronics Design: https://analog-electronics.ewi.tudelft.nl/webbook/SED/

---

## 9. Studio Gear Repair Forums

### Major Forums
- **Gearspace** (400K+ members): https://gearspace.com/board/
- **GroupDIY**: https://groupdiy.com/
- **DIYAudio**: https://www.diyaudio.com/
- **TalkBass amp forum**: https://www.talkbass.com/wiki/technical-amplifier/
- **TDPRI Amp Central**: https://www.tdpri.com/forums/amp-central-station.11/
- **MOD WIGGLER** (modular): https://modwiggler.com/
- **KVR DSP Forum**: https://www.kvraudio.com/forum/viewforum.php?f=33

### Schematic Archives
- Audio Schematics DK (90,000+): https://audioschematics.dk/
- Audio Circuit DK: https://audiocircuit.dk
- Oak Tree Vintage repair links: http://www.oaktreevintage.com/repair_links_outside.htm
- musicdsp.org archive: http://www.musicdsp.org/archive.php
- Awesome MusicDSP: https://github.com/olilarkin/awesome-musicdsp

---

## 10. Academic Papers & Conference Archives

### DAFx (Digital Audio Effects Conference)
- **Paper archive (all years)**: https://www.dafx.de/paper-archive/
- DAFx 2019 WDF tutorial: https://dafx2019.bcu.ac.uk/programme/mon/tutorial-werner
- DAFx 2015 proceedings: https://www.ntnu.edu/dafx15/proceedings
- DAFx VA modeling tutorial 2016 (PDF): https://dafx16.vutbr.cz/files/dafx16_tutorial_macak.pdf

### Key Researchers
- **Kurt Werner** (Soundtoys): https://ccrma.stanford.edu/~kwerner/ | Scholar: https://scholar.google.com/citations?user=EfdaqWIAAAAJ
- **Jatin Chowdhury** (ChowDSP): https://ccrma.stanford.edu/~jatin/ | GitHub: https://github.com/jatinchowdhury18
- **Julius O. Smith III** (Stanford): https://ccrma.stanford.edu/~jos/
- **Alec Wright** (Edinburgh/Aalto): https://www.research.ed.ac.uk/en/persons/alec-wright
- **Vesa Valimaki** (Aalto): http://users.spa.aalto.fi/vpv/publications.htm
- **Maarten van Walstijn** (QUB): https://pure.qub.ac.uk/en/persons/maarten-van-walstijn/

### AES (Audio Engineering Society)
- JAES main: https://aes2.org/publications/journal/
- AES E-Library: https://aes2.org/publications/

### JUCE-Specific
- JUCE analogue modelling module: https://forum.juce.com/t/juce-module-for-analogue-modelling/28534
- JUCE StateVariableTPTFilter: https://docs.juce.com/master/classdsp_1_1StateVariableFilter_1_1Filter.html
- JUCE DSP Introduction: https://docs.juce.com/master/tutorial_dsp_introduction.html
- JUCE DSP Module Demo: https://github.com/juce-framework/JUCE/blob/master/examples/Plugins/DSPModulePluginDemo.h
- awesome-juce: https://github.com/sudara/awesome-juce
- WolfSound JUCE filter tutorial: https://thewolfsound.com/lowpass-highpass-filter-plugin-with-juce/

---

## Scraping Priority

### Tier 1 — Download Immediately (PDFs)
1. Zavalishin "Art of VA Filter Design" (130pp)
2. Kurt Werner WDF Dissertation (261pp)
3. David Yeh WDF Tutorial
4. David Yeh Automated Physical Modeling Parts I & II
5. Jatin Chowdhury WDF slides

### Tier 2 — Scrape (HTML, high value)
6. Julius O. Smith 4 online books (ccrma.stanford.edu)
7. ElectroSmash full site (all pedal analyses)
8. All About Circuits textbook
9. DAFx paper archive (200+ relevant PDFs)
10. KVR DSP forum key threads

### Tier 3 — Clone (GitHub repos)
11. chowdsp_wdf library
12. RTNeural library
13. GuitarLSTM / PedalNetRT
14. Neural Amp Modeler
15. RE201models

### Tier 4 — Selective Scrape (Forums, specific threads)
16. Gearspace spring reverb threads
17. GroupDIY vintage reverb threads
18. DIYAudio spring reverb circuits
19. TalkBass amp repair threads
20. TDPRI amp schematics

---

## Skill Mapping

| KB Source | Maps To Skills |
|-----------|---------------|
| WDF/VA modeling | /cto, /plugin, /audio-production |
| Pedal schematics | /plugin, /audio-production |
| Spring reverb | /plugin, /audio-production |
| ML/Neural modeling | /cto, /plugin, /mad-scientist |
| EE textbooks | /plugin (beginner reference) |
| SPICE tutorials | /plugin, /audio-production |
| DAFx papers | /cto, /plugin |

## JUCE Cross-References

| Topic | JUCE Connection |
|-------|----------------|
| WDF | chowdsp_wdf integrates as JUCE module |
| VA Filters | juce::dsp::StateVariableTPTFilter implements Zavalishin's TPT |
| Neural modeling | RTNeural + JUCE = real-time ML plugins |
| Nodal DK | NDKFramework demonstrated at ADC 2019 |
| Distortion | JUCE WaveShaper + custom nonlinear functions |
| Reverb | JUCE dsp::Convolution for IR, custom for algorithmic |
