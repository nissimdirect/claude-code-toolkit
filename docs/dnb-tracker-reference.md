# Drum and Bass Tracker Production Reference

> Comprehensive guide to tracker-based DnB production: tools, techniques, history, and resources.

---

## Installed Trackers (macOS)

| Tracker | Version | Type | Path |
|---------|---------|------|------|
| **MilkyTracker** | 1.05.01 | FastTracker II clone (XM/MOD) | /Applications/MilkyTracker.app |
| **SunVox** | 2.1.4d | Modular synth + tracker | /Applications/SunVox.app |
| **Schism Tracker** | 20251014 | Impulse Tracker clone (IT/S3M) | /Applications/Schism Tracker.app |
| **Furnace** | latest | Chiptune multi-system tracker | /Applications/Furnace.app (if installed) |

### MilkyTracker
- **Format:** .XM (FastTracker II), .MOD
- **Strengths:** Classic tracker workflow, lightweight, open source (GPL)
- **Best for:** Learning tracker basics, classic jungle/breakbeat style
- **Channels:** Up to 32
- **Effects:** Volume slides, arpeggio, portamento, retrigger, tremolo, vibrato
- **Limitations:** No VST support, no audio recording, sample-only

### SunVox
- **Format:** .sunvox (proprietary)
- **Strengths:** Built-in modular synths, effects, cross-platform (even iOS)
- **Best for:** Sound design, experimental DnB, modular synthesis + sequencing
- **Modules:** FM synth, analog synth, sampler, drumsynth, generator, filters, delays, reverbs
- **Unique:** Modular patching + tracker sequencing = hybrid workflow

### Schism Tracker
- **Format:** .IT (Impulse Tracker), .S3M, .XM, .MOD
- **Strengths:** Most authentic classic tracker experience, NNA (New Note Actions)
- **Best for:** Complex sample manipulation, old-school jungle production
- **Channels:** Up to 64
- **Effects:** Full Impulse Tracker effects set including filters, resonance

### Furnace
- **Format:** .fur (multi-system)
- **Strengths:** 50+ chip emulations (YM2612, SID, SNES SPC700, etc.)
- **Best for:** Chiptune-flavored DnB, retro sound design, FM bass
- **Unique:** Real chip emulation for authentic retro timbres

---

## DnB Production in Trackers

### Why Trackers Excel at DnB

1. **Hex-based sample offsets** — Load a break, auto-chop to 16ths
2. **Per-step control** — Every note can have unique volume, panning, effects
3. **Retrigger effects** — Rapid-fire breakbeat programming (E9x in XM)
4. **Pattern chaining** — Non-linear arrangement perfect for DnB structure
5. **Sample manipulation** — Pitch, reverse, loop points, all per-step
6. **Low CPU** — Run on anything, focus on music not menus

### DnB Tempo Settings

| Style | BPM | Speed/Ticks |
|-------|-----|-------------|
| Liquid DnB | 160-165 | Speed 3, BPM 160 |
| Standard DnB | 170-174 | Speed 3, BPM 174 |
| Jump-Up | 172-176 | Speed 3, BPM 174 |
| Neurofunk | 172-178 | Speed 3, BPM 176 |
| Jungle | 160-170 | Speed 6, BPM 160 (for swing) |
| Darkstep | 174-180 | Speed 3, BPM 176 |

### Essential DnB Pattern Structure

```
Intro:    16-32 bars  (atmospheric, build tension)
Drop 1:   16-32 bars  (full energy, main break + bass)
Break:    8-16 bars   (half-time, melodic, tension build)
Drop 2:   16-32 bars  (variation, heavier or more complex)
Outro:    16-32 bars  (wind down, DJ-friendly)
```

### Tracker Effect Commands (XM/IT)

| Effect | Hex | Use in DnB |
|--------|-----|-----------|
| Arpeggio | 0xy | Rapid chord stabs |
| Portamento Up | 1xx | Rising bass sweeps |
| Portamento Down | 2xx | Falling bass dives |
| Tone Portamento | 3xx | Smooth bass slides |
| Vibrato | 4xy | Wobble bass (slow), lead shimmer |
| Volume Slide | Axy | Swells, builds |
| Retrigger | E9x | **ESSENTIAL** — breakbeat programming |
| Note Cut | ECx | Tight hi-hat programming |
| Note Delay | EDx | Swing/shuffle, ghost notes |
| Set Sample Offset | 9xx | **ESSENTIAL** — play from different positions in a break |
| Tremolo | 7xy | Rhythmic volume modulation |
| Set Panning | 8xx | Stereo placement |

### Breakbeat Programming Techniques

**Classic Amen Break Chopping:**
```
Row 00: C-5 01 .. 900  ; Start of break
Row 01: ... .. .. ...   ; Let ring
Row 02: C-5 01 .. 940  ; Skip to snare hit
Row 03: ... .. .. ...
Row 04: C-5 01 .. 900  ; Back to kick
Row 05: C-5 01 .. 980  ; Late snare ghost
Row 06: C-5 01 .. 920  ; Hi-hat section
Row 07: C-5 01 .. 900  ; Kick return
```

**Retrigger for Drill Rolls:**
```
Row 00: C-5 01 40 E93  ; Retrigger every 3 ticks
Row 01: C-5 01 30 E92  ; Faster retrigger
Row 02: C-5 01 20 E91  ; Machine-gun effect
Row 03: C-5 01 40 000  ; Normal hit
```

**Ghost Notes with Delay:**
```
Row 00: C-5 01 40 ...  ; Main hit (full volume)
Row 01: C-5 01 18 ED2  ; Ghost note delayed 2 ticks (low volume)
Row 02: ... .. .. ...   ; Rest
Row 03: C-5 01 10 ED1  ; Softer ghost, 1 tick delay
```

---

## DnB Elements (What to Sample/Synthesize)

### Drums
- **Kick:** Sub-heavy (40-80Hz fundamental), punchy attack
- **Snare:** Layered: acoustic snap + electronic crack + noise tail
- **Hi-hats:** Tight closed hats (8-12kHz), open hat for accents
- **Breaks:** Amen, Think, Funky Drummer, Apache, Hot Pants
- **Percussion:** Ride cymbal, shaker, tamb, clap layers

### Bass
- **Sub Bass:** Clean sine/triangle, 30-60Hz
- **Mid Bass:** Reese (detuned saw), Neuro (FM/wavetable), Hoover
- **Processing:** Distortion, bitcrushing, comb filtering, formant filters

### Atmosphere
- **Pads:** Lush reverb tails, granular textures
- **FX:** Risers, downlifters, impacts, vinyl crackle
- **Vocals:** Chopped, pitched, timestretched, amened

---

## Notable DnB Tracker Artists

| Artist | Tracker Used | Style |
|--------|-------------|-------|
| Venetian Snares | OctaMED → Renoise | Breakcore/DnB fusion |
| Squarepusher | Hardware + trackers | Jazz-DnB-breakcore |
| Luke Vibert (Wagon Christ) | Amiga trackers | IDM/jungle |
| Paradox | Renoise | Drum and bass |
| Cristian Vogel | Various trackers | Techno/experimental |
| µ-Ziq | Various | IDM/jungle |

---

## Free DnB Sample Resources

### Sample Packs
| Source | URL | Content |
|--------|-----|---------|
| DNB Academy | dnbacademy.net/free | 174 Production Marathon pack |
| KAN Samples | kansamples.com/blogs/free-drum-and-bass-sample-packs | Classic break homages |
| Kulture Samples | kulturesamples.com | 134 DnB samples (royalty-free) |
| MusicRadar | musicradar.com (DnB Essentials) | 485 free samples (160-175 BPM) |
| Samplephonics | samplephonics.com/products/free/jungle-dnb | Free jungle/DnB |
| Antidote Audio | antidoteaudio.com/free-drum-and-bass-sample-packs | 19 free packs |

### Tracker Module Archives
| Source | URL | Format |
|--------|-----|--------|
| The Mod Archive | modarchive.org | MOD/XM/IT/S3M (search "jungle", "dnb") |
| Scene.org | scene.org/dir.php?dir=/music/ | Demoscene music |
| Battle of the Bits | battleofthebits.com | Tracker community modules |

---

## Python Music Libraries (Installed)

| Library | Version | Use For |
|---------|---------|---------|
| **mido** | 1.3.3 | MIDI file read/write, real-time MIDI |
| **music21** | 9.9.1 | Music theory, analysis, notation |
| **pretty_midi** | 0.2.11 | MIDI manipulation, piano rolls |
| **MIDIUtil** | 1.2.1 | Programmatic MIDI file creation |
| **pydub** | 0.25.1 | Audio manipulation, format conversion |
| **librosa** | 0.11.0 | Audio analysis, beat detection, spectral |
| **FoxDot** | 0.9.0 | Live coding music (SuperCollider) |

### MIDI Generation for Trackers
```python
from midiutil import MIDIFile

# Create a basic DnB drum pattern
midi = MIDIFile(1)
midi.addTempo(0, 0, 174)  # 174 BPM

# Kick pattern (C1 = 36)
kicks = [0, 2.5, 4, 6.75]
for beat in kicks:
    midi.addNote(0, 9, 36, beat, 0.25, 100)

# Snare pattern (D1 = 38)
snares = [1, 3, 5, 7]
for beat in snares:
    midi.addNote(0, 9, 38, beat, 0.25, 110)

# Hi-hats (F#1 = 42)
for i in range(16):
    midi.addNote(0, 9, 42, i * 0.5, 0.25, 70 + (i % 2) * 20)

with open("dnb_pattern.mid", "wb") as f:
    midi.writeFile(f)
```

---

## DnB Music Theory Quick Reference

### Common Chord Progressions
- **Am - F - C - G** (classic liquid DnB)
- **Dm - Bb - F - C** (dark, cinematic)
- **Em - C - G - D** (uplifting)
- **Fm - Db - Ab - Eb** (deep, rolling)

### Key Signatures Popular in DnB
- **A minor / C major** (most common)
- **D minor / F major** (dark/deep)
- **E minor / G major** (rolling)
- **F minor / Ab major** (heavy/neurofunk)

### Bass Note Patterns
- **Two-step:** Hit on 1 and the "and" of 2 (syncopated)
- **Rolling:** Continuous 8th or 16th note patterns
- **Reese:** Long sustained notes with slow modulation
- **Stab:** Short percussive bass hits, often with delay

### Drum Pattern Fundamentals
```
Standard DnB (2-step):
Kick:   X . . . . X . . X . . . . . . .
Snare:  . . . . X . . . . . . . X . . .
HH:     X . X . X . X . X . X . X . X .

Jungle (breakbeat):
[Amen break chopped and rearranged]
Emphasis on ghost notes, syncopation, rapid fills

Halftime:
Kick:   X . . . . . . . . . . . . . . .
Snare:  . . . . . . . . X . . . . . . .
HH:     X . X . X . X . X . X . X . X .
```

---

## Workflow: Tracker → DAW Pipeline

1. **Compose in tracker** (MilkyTracker/Schism) — drum patterns, bass lines, melodies
2. **Export as WAV** (render pattern/song to audio)
3. **Import to DAW** (Logic Pro X, Ableton) for mixing/mastering
4. **OR** use Renoise (paid) as full DAW-tracker hybrid with VST support

### Export Commands
- **MilkyTracker:** Ctrl+Shift+E → Export as WAV
- **Schism Tracker:** F10 → Save, or render with command line
- **SunVox:** File → Export to WAV

---

## Learning Path

1. **Week 1:** Install MilkyTracker, learn navigation (F1-F12 keys, pattern editor)
2. **Week 2:** Load Amen break, practice chopping with sample offset (9xx)
3. **Week 3:** Build basic DnB beat (kick, snare, hats, break layers)
4. **Week 4:** Add bass (sub + mid layers), learn volume automation
5. **Week 5:** Arrangement (intro, drop, break, drop 2, outro)
6. **Week 6:** Effects processing, try SunVox for sound design
7. **Week 7:** Full track, export to DAW for mixing
8. **Week 8:** Experiment with Schism Tracker for IT format features
