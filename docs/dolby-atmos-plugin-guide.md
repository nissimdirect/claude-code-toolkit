# Dolby Atmos Plugin Development Guide

> Reference documentation for building spatial audio plugins targeting Dolby Atmos.
> Last updated: 2026-02-07

---

## Table of Contents

1. [Atmos Renderer Architecture](#atmos-renderer-architecture)
2. [Object-Based vs Channel-Based Audio](#object-based-vs-channel-based-audio)
3. [ADM BWF Format Basics](#adm-bwf-format-basics)
4. [Making a JUCE Plugin Atmos-Aware](#making-a-juce-plugin-atmos-aware)
5. [Binaural Rendering for Headphone Monitoring](#binaural-rendering-for-headphone-monitoring)
6. [Market Opportunity for Indie Atmos Plugins](#market-opportunity-for-indie-atmos-plugins)
7. [Tools and Software](#tools-and-software)
8. [Resources and Links](#resources-and-links)

---

## Atmos Renderer Architecture

### What the Renderer Does

The Dolby Atmos Renderer is the central processing hub in any Atmos workflow. It handles:

- **Real-time monitoring and playback** of spatial mixes
- **Rendering to speaker configurations** for immediate feedback during mixing
- **Generation of standard channel-based layouts** for distribution (stereo, 5.1, 7.1, 7.1.4)
- **Recording Dolby Atmos master files** for 4K Blu-ray encoding
- **ADM BWF export** for streaming service workflows (Apple Music, Tidal, Amazon Music)

### How Rendering Works

The renderer converts the **object-based mix format** to a **channel-based playback format** (speakers or headphones). It needs information about:

1. **What objects exist** -- each with X, Y, Z coordinates and associated audio
2. **What bed channels exist** -- traditional channel-based stems (e.g., 7.1.2 surround)
3. **What playback system is available** -- the speaker setup to render for

The Monitoring Format selection in the Dolby Atmos plug-in provides speaker setup information to the renderer, which then simulates various playback systems.

### Rendering Pipeline

```
Audio Objects (with metadata)    Channel-Based Beds (7.1.2)
         |                                |
         v                                v
    +-----------------------------------------+
    |        Dolby Atmos Renderer              |
    |  - Receives object positions (X,Y,Z)    |
    |  - Receives bed channel assignments      |
    |  - Applies panning laws                  |
    |  - Maps to output speaker config         |
    +-----------------------------------------+
                     |
                     v
         Speaker Output (e.g., 7.1.4)
         OR Binaural Output (headphones)
         OR Master File (.atmos / ADM BWF)
```

### Rendering and Mastering Unit (RMU)

In professional workflows, the **Rendering and Mastering Unit (RMU)** runs the Dolby Atmos Mastering Suite software. During mixing:

- Bed channels, object audio, and object metadata are sent to the RMU
- The RMU handles monitoring and master file creation
- Alternative: **Dolby Atmos Production Suite** provides similar functionality running directly on the DAW machine

### Supported DAWs

The system supports integration with: **Logic Pro, Pro Tools, Nuendo, Studio One, Cubase, Pyramix, and DaVinci Resolve**.

Routing architecture allows creators to direct sources to either **multichannel beds** or to **object busses**, which are available in the I/O dropdown selection.

---

## Object-Based vs Channel-Based Audio

### Channel-Based Audio (Beds)

Traditional surround sound approach:

- Audio is pre-mixed to specific speaker channels (e.g., 7.1.2)
- The **7.1.2 surround mix** establishes the foundation with **overhead bed channels**
- Each channel maps directly to a physical speaker
- Good for: ambient sounds, music stems, backgrounds, reverb tails
- Limited: cannot adapt to different speaker configurations without downmixing

**Bed Configuration:**

| Channel | Position |
|---------|----------|
| L / R | Front Left / Right |
| C | Center |
| LFE | Subwoofer |
| Ls / Rs | Side Left / Right |
| Lrs / Rrs | Rear Left / Right |
| Ltf / Rtf | Top Front Left / Right |

### Object-Based Audio

Modern spatial audio approach:

- Individual audio elements can be **placed anywhere in the room**, independent of the surround beds
- Each object carries **metadata**: X, Y, Z coordinates, size, and speaker configuration data
- The renderer dynamically maps objects to whatever speaker layout is available
- Good for: dialogue, spot effects, instruments that need precise placement
- Advantage: automatically adapts to any playback system

**Object Metadata Properties:**
- **Position**: X (left/right), Y (front/back), Z (up/down)
- **Size**: How large the sound source appears in space
- **Snap**: Whether the object should snap to the nearest speaker
- **Zone constraints**: Limit rendering to specific speaker zones
- **Divergence**: How much the sound spreads across speakers

### Hybrid Approach

Dolby Atmos uses **both** simultaneously:

- **Beds** for the ambient foundation (up to 7.1.2)
- **Objects** for precise sound placement (up to 118 objects in cinema, 16 in music)
- Combined in a single Atmos session

### Why This Matters for Plugin Developers

Plugins can process:
1. **Bed channels** -- standard multi-channel processing (reverb, EQ, dynamics)
2. **Individual objects** -- per-object processing before they reach the renderer
3. **Object metadata** -- modifying position/size/parameters programmatically
4. **Binaural output** -- headphone rendering of the complete Atmos mix

---

## ADM BWF Format Basics

### What is ADM BWF?

**ADM BWF** (Audio Definition Model - Broadcast Wave Format) is the standard interchange format for Dolby Atmos mixes.

Key facts:
- **Not proprietary to Dolby** -- it is an open standard (ITU-R BS.2076)
- A single file that is basically a **broadcast WAV** with a large XML data chunk at the head
- The XML chunk contains `.atmos` and `.atmos.metadata` information
- Used for exchanging Atmos mixes between DAWs, collaborators, and delivery services

### File Structure

```
+------------------------------------------+
|  RIFF Header                              |
+------------------------------------------+
|  fmt chunk (audio format info)            |
+------------------------------------------+
|  axml chunk (ADM XML metadata)            |
|  - audioProgramme                         |
|  - audioContent                           |
|  - audioObject (positions, gains, etc.)   |
|  - audioPackFormat                        |
|  - audioChannelFormat                     |
|  - audioTrackUID                          |
|  - audioTrackFormat                       |
+------------------------------------------+
|  chna chunk (channel/track assignments)   |
+------------------------------------------+
|  data chunk (interleaved PCM audio)       |
+------------------------------------------+
```

### ADM XML Elements

| Element | Purpose |
|---------|---------|
| `audioProgramme` | Top-level container for the complete mix |
| `audioContent` | Groups of related audio (e.g., "dialogue", "music") |
| `audioObject` | Individual sound elements with position metadata |
| `audioPackFormat` | Channel configuration (e.g., 7.1.4, stereo) |
| `audioChannelFormat` | Per-channel spatial info (azimuth, elevation, distance) |
| `audioTrackUID` | Links audio tracks to ADM elements |
| `audioBlockFormat` | Time-varying position/gain data for objects |

### Workflow

1. **Mix in DAW** with Atmos panning and object routing
2. **Export ADM BWF** from the DAW (Logic Pro: File > Export > Dolby Atmos ADM BWF)
3. **Deliver** to streaming services (Apple Music, Tidal, Amazon Music)
4. **Import** ADM BWF into another DAW for collaboration or revision

### For Plugin Developers

The Dolby Atmos Master Audio Definition Model (ADM) profile documentation is intended primarily for **application developers** who wish to implement support for ADM BWF `.wav` files in a manner that enables interoperability with Dolby tools and other industry tools.

Key developer considerations:
- Parse the `axml` chunk to read object positions and metadata
- Respect the `chna` chunk for track-to-channel mapping
- Handle time-varying `audioBlockFormat` data for animated objects
- Support both **DirectSpeaker** (bed) and **Object** type definitions

---

## Making a JUCE Plugin Atmos-Aware

### Why JUCE for Spatial Audio

JUCE is the most widely used framework for audio plugin development. Benefits:

- Handles all backend (VST3, AU, AAX, LV2 export) so you focus on DSP and GUI
- Cross-platform compilation (Windows, macOS, Linux)
- Built-in support for ambisonic channel sets via `AudioChannelSet`
- Active community with spatial audio projects to reference

### JUCE AudioChannelSet for Immersive Formats

JUCE provides built-in support for spatial audio channel layouts:

```cpp
// Standard Atmos bed configurations
auto bed_7_1_2 = juce::AudioChannelSet::create7point1point2();
auto bed_7_1_4 = juce::AudioChannelSet::create7point1point4();

// Ambisonic formats (used in some spatial audio workflows)
auto ambi_1st = juce::AudioChannelSet::ambisonic(1);  // 4 channels
auto ambi_3rd = juce::AudioChannelSet::ambisonic(3);  // 16 channels
auto ambi_5th = juce::AudioChannelSet::ambisonic(5);  // 36 channels

// Check channel layout
bool isAmbi = channelSet.isAmbisonic();
int order = channelSet.getAmbisonicOrder();
```

### Plugin Architecture Approaches

**Approach 1: Multi-Channel Bed Processing**
Process the Atmos bed channels (up to 7.1.4 = 12 channels):

```cpp
class AtmosBedProcessor : public juce::AudioProcessor
{
    // Accept 7.1.4 input and output
    bool isBusesLayoutSupported(const BusesLayout& layouts) const override
    {
        auto main = layouts.getMainOutputChannelSet();
        return main == juce::AudioChannelSet::create7point1point4()
            || main == juce::AudioChannelSet::create7point1point2()
            || main == juce::AudioChannelSet::create7point1()
            || main == juce::AudioChannelSet::create5point1();
    }

    void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
    {
        // Process all channels of the bed
        for (int ch = 0; ch < buffer.getNumChannels(); ++ch)
        {
            auto* data = buffer.getWritePointer(ch);
            // Apply your DSP per channel...
        }
    }
};
```

**Approach 2: Object-Based Panning Plugin**
Create a panner that outputs position metadata alongside audio:

```cpp
class AtmosObjectPanner : public juce::AudioProcessor
{
    // Parameters for 3D position
    juce::AudioParameterFloat* azimuth;    // -180 to 180 degrees
    juce::AudioParameterFloat* elevation;  // -90 to 90 degrees
    juce::AudioParameterFloat* distance;   // 0.0 to 1.0

    void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
    {
        // Read automation values
        float az = azimuth->get();
        float el = elevation->get();
        float dist = distance->get();

        // Convert spherical to Cartesian for Atmos
        float x = dist * cos(el) * sin(az);
        float y = dist * cos(el) * cos(az);
        float z = dist * sin(el);

        // Apply panning gains to output channels...
    }
};
```

**Approach 3: Binaural Renderer Plugin**
Use HRTFs to render spatial audio to headphones:

```cpp
// Load HRTF from SOFA file
// Apply convolution per-object with appropriate HRTF pair
// Sum binaural output for headphone monitoring
```

### Reference Projects (Open Source on GitHub)

| Project | What It Does | URL |
|---------|-------------|-----|
| **SPARTA** | Suite of spatial audio VST/LV2 plugins (ambisonics, binaural, panning) | github.com/leomccormack/SPARTA |
| **3D-Spatial-Audio** | HRTF-based 3D spatializer using JUCE | github.com/Amphicheiras/3D-Spatial-Audio |
| **ambix** | Cross-platform Ambisonic VST/LV2 with variable order | github.com/kronihias/ambix |
| **LAC19 Workshop** | JUCE ambisonic plugin tutorial from LAC 2019 | github.com/gzalles/LAC19_workshop |
| **Spatial Audio Framework** | Core DSP library used by SPARTA | github.com/leomccormack/Spatial_Audio_Framework |

### SPARTA Plugin Suite (JUCE-Based Reference)

SPARTA is the gold standard open-source reference for spatial audio plugins built with JUCE:

- **Open-source** VST, VST3, AU, LV2, and AAX plugins
- Supports up to **tenth-order ambisonics**
- **Binaural rendering** with custom HRTF loading via SOFA files
- **Head-tracking** via OSC messages
- Architecture: **Spatial Audio Framework (SAF)** for DSP + **JUCE** for GUI/host communication
- Available for macOS, Linux, and Windows

### Key Technical Concepts

**HRTF (Head-Related Transfer Function):**
Models how sound reaches each ear from a specific direction. Each HRTF impulse response represents the sound as perceived from a specific direction, allowing accurate spatialization with changes to azimuth, elevation, and distance applied in real-time with low latency.

**SOFA Files:**
Standard format for storing HRTF data. SPARTA and other plugins support loading custom HRTFs via SOFA files, enabling personalized spatial rendering.

**Ambisonics:**
A full-sphere surround sound technique. JUCE supports ACN (Ambisonic Channel Numbering) and SN3D normalization. Higher orders = better spatial resolution but more channels.

| Order | Channels | Spatial Resolution |
|-------|----------|-------------------|
| 1st (FOA) | 4 | ~60 degree blur |
| 3rd | 16 | ~25 degree blur |
| 5th | 36 | ~15 degree blur |
| 7th | 64 | ~10 degree blur |

---

## Binaural Rendering for Headphone Monitoring

### Why Binaural Matters

Over **3.5 billion Dolby Atmos-enabled devices** exist worldwide, and many consumers listen through headphones. Binaural rendering is how Atmos translates to headphone playback.

For mixing: binaural rendering allows checking Atmos mixes on headphones, which is critical for producers without access to full Atmos speaker rigs.

### How Binaural Rendering Works

1. **HRTF Selection**: Choose or measure head-related transfer functions
2. **Convolution**: For each audio object/channel, convolve with the appropriate HRTF pair (left ear, right ear) based on the object's spatial position
3. **Summation**: Sum all convolved signals for the left and right ear outputs
4. **Head-tracking (optional)**: Adjust HRTF selection in real-time based on head orientation via OSC or other protocols

```
Object Audio + Position Metadata
          |
          v
   Select HRTF pair for (azimuth, elevation, distance)
          |
          v
   Convolve audio with left-ear HRTF → Left output
   Convolve audio with right-ear HRTF → Right output
          |
          v
   Sum all objects → Stereo binaural output
```

### Existing Binaural Plugins (Competitive Landscape)

| Plugin | Developer | Key Features |
|--------|-----------|-------------|
| **dearVR PRO** | Dear Reality | All-in-one spatializer, binaural + ambisonics + 26 multi-channel formats up to 9.1.6 |
| **APL Virtuoso v2** | APL | Virtualizes stereo and immersive speaker setups, 5 built-in HRTF presets + custom SOFA |
| **Anaglyph** | IRCAM | Research-grade binaural renderer, personalizable morphological ITD model, near-field ILD corrections |
| **Audiomovers Binaural Renderer** | Audiomovers | Apple Music-specific binaural preview outside Logic Pro |
| **SPARTA Binaural** | Leo McCormack | Open-source, custom HRTF via SOFA, head-tracking via OSC |
| **Spatializer** | Blue Lab Audio | Free HRTF binaural spatializer |

### Personalized HRTFs

The next frontier in binaural rendering. Standard HRTFs work for most listeners but personalized ones provide significantly better externalization and localization. Methods:
- **Ear scanning** (photo-based measurement)
- **Morphological models** (predict HRTF from head/ear dimensions)
- **Subjective selection** (choose from presets that sound most accurate)

---

## Market Opportunity for Indie Atmos Plugins

### Market Size

- Global Audio Software Plugin market: **USD 1,794.79 million in 2026**, projected to reach **USD 6,699.47 million by 2035** (CAGR 15.76%)
- **Spatial Audio Rendering AI market**: $5.56 billion opportunity (2024-2029 forecast)
- Over **2,100 spatial audio plugin tools** created by mid-2025
- Over **400 Dolby Atmos-compatible plugins** released with object panning and spatial rendering as primary features

### Growth Indicators

- Dolby Atmos-compatible plugin downloads: **+31% year-over-year**
- Binaural simulation tool downloads: **+42% year-over-year**
- **48% of plugin releases in 2024** were compatible with immersive audio standards
- Object-based mixing installations rose **~40%** in professional post-production facilities

### Creator Economy

- **60+ million independent music creators** globally as of 2024
- Growing demand for accessible, high-quality DSP tools
- Most creators lack access to full Atmos speaker rigs -- headphone tools are the entry point

### Gaps Where Indie Developers Can Win

| Gap | Opportunity |
|-----|------------|
| **DAW compatibility** | Atmos tools for DAWs without native support (Ableton, FL Studio, Bitwig) |
| **Affordable binaural rendering** | Sub-$100 binaural monitoring plugins with personalized HRTF |
| **Object panning with creative features** | Motion sequencers, LFO-driven panning, audio-reactive position |
| **Upmixing tools** | Stereo-to-immersive conversion for legacy content |
| **Format conversion** | Easy translation between Atmos, Auro 3D, DTS:X, Ambisonics |
| **Room correction** | Affordable speaker calibration for home Atmos setups |
| **Headphone reference** | Binaural rendering calibrated to specific streaming platforms |
| **Creative spatial effects** | Spatial reverbs, spatial delays, 3D granular synthesis |
| **Metadata editors** | Visual ADM BWF inspection and editing tools |

### Existing Utility Plugins (Competitive Reference)

| Plugin | Function | Price Range |
|--------|----------|------------|
| Dolby Atmos Music Panner | Free 3D object panner (VST3/AU/AAX) | Free |
| Nugen Audio Halo Upmix | Stereo to 7.1.2 upmixer, phaseless | $399-799 |
| Sonarworks SoundID Reference | Room correction for Atmos up to 9.1.6 | $199-399 |
| PerfectSurround Penteo 16 Pro | Upmix/downmix, multi-format | $499+ |
| Fiedler Audio Dolby Atmos Composer | Master bus encoder + 3D panner | Free (Essential) / $299 |
| Audiomovers Binaural Renderer | Apple Music binaural preview | $99-199 |

---

## Tools and Software

### Dolby Atmos Renderer

- **Purpose**: Central processing hub for Atmos mixing, monitoring, and mastering
- **Formats**: Renders to any speaker configuration from stereo to 9.1.6
- **Output**: Creates Atmos master files, ADM BWF for streaming delivery
- **Access**: Requires Dolby Professional account
- **URL**: https://professional.dolby.com/product/dolby-atmos-content-creation/dolby-atmos-renderer/

### Dolby Atmos Production Suite

- **Purpose**: Renderer + binaural monitoring as a DAW plugin
- **Replaces**: External RMU hardware for smaller studios
- **Includes**: Dolby Atmos Renderer, Binaural Settings Plugin

### Spatial Audio Designer

- **Purpose**: Visual 3D panning interface for DAWs
- **Features**: Drag objects in 3D space, automate paths, visualize speaker layouts
- **Alternatives**: FLUX:: Spat Revolution, DearVR SPATIAL CONNECT

### Dolby Atmos Windows API SDK

- **Version**: 1.1.7.32 (latest as of 2024)
- **Languages**: C++, C#, JavaScript
- **Purpose**: Integrate Atmos into Windows Desktop/Universal applications
- **Access**: Requires Dolby Developer account at developer.dolby.com

### SPARTA Suite

- **Purpose**: Open-source spatial audio plugins (ambisonic encoding, decoding, binaural rendering, panning)
- **Framework**: JUCE + Spatial Audio Framework
- **Formats**: VST, VST3, AU, LV2, AAX
- **Platforms**: macOS, Linux, Windows
- **URL**: https://leomccormack.github.io/sparta-site/
- **Source**: https://github.com/leomccormack/SPARTA

---

## Resources and Links

### Official Dolby

- [Dolby Developer Portal](https://developer.dolby.com/)
- [Dolby Atmos Renderer](https://professional.dolby.com/product/dolby-atmos-content-creation/dolby-atmos-renderer/)
- [Dolby Atmos ADM Profile Documentation](https://developer.dolby.com/technology/dolby-atmos/adm-atmos-profile/)
- [Dolby Creator Lab](https://professional.dolby.com/content-creation/Dolby-Atmos-for-content-creators/)
- [Dolby Laboratories GitHub](https://github.com/DolbyLaboratories)

### JUCE / Spatial Audio Development

- [JUCE Framework](https://juce.com/)
- [JUCE AudioChannelSet Docs](https://docs.juce.com/master/classAudioChannelSet.html)
- [JUCE Forum: Spatial Audio Support](https://forum.juce.com/t/juce-spatial-audio-support/30509)
- [JUCE for Spatial Audio (SSA Plugins Blog)](https://www.ssa-plugins.com/blog/2017/09/08/juce-for-spatial-audio/)

### Open Source Projects

- [SPARTA Plugins](https://github.com/leomccormack/SPARTA)
- [Spatial Audio Framework](https://github.com/leomccormack/Spatial_Audio_Framework)
- [3D-Spatial-Audio (HRTF-based)](https://github.com/Amphicheiras/3D-Spatial-Audio)
- [ambix Ambisonic Plugins](https://github.com/kronihias/ambix)
- [LAC19 JUCE Ambisonics Workshop](https://github.com/gzalles/LAC19_workshop)

### Binaural / HRTF

- [Anaglyph Binaural Plugin](https://anaglyph.dalembert.upmc.fr/)
- [APL Virtuoso v2](https://apl-hud.com/product/virtuoso/)
- [SOFA File Format Convention](https://www.sofaconventions.org/)

### Market Research

- [Audio Software Plugin Market Report](https://www.360researchreports.com/market-reports/audio-software-plugin-market-211995)
- [Spatial Audio Rendering AI Market ($5.56B)](https://www.globenewswire.com/news-release/2026/01/29/3228497/0/en/Spatial-Audio-Rendering-Artificial-Intelligence-AI-Research-Report-2025-5-56-Bn-Market-Opportunities-Trends-Competitive-Analysis-Strategies-and-Forecasts-2019-2024-2024-2029F-2034F.html)
- [Best Spatial Audio Plugins (Audiocube)](https://www.audiocube.app/blog/spatial-audio-plugin)
- [6 Must-Have Utility Plugins for Atmos (Production Expert)](https://www.production-expert.com/production-expert-1/6-must-have-utility-plugins-for-dolby-atmos-production)

---

## Real-World Atmos Plugin Examples

> Added: 2026-02-07 | Research on commercial and open-source spatial audio plugins built with JUCE and related frameworks.

### Commercial Plugins Built with JUCE / Spatial Audio Frameworks

#### dearVR PRO 2 (Dear Reality / Dolby)

- **Developer**: Dear Reality (acquired by Dolby)
- **Technology**: Custom spatial audio engine, outputs up to **9.1.6 Dolby Atmos** and Ambisonics
- **Key Features**: All-in-one spatializer, 26 multi-channel formats, binaural monitoring, room simulation
- **Pricing**: ~$199
- **Note**: Computationally expensive but considered the gold standard for spatial panning
- **URL**: [Dear Reality](https://www.dearvr.com/)

#### Spacelab Interstellar (Fiedler Audio)

- **Developer**: Fiedler Audio
- **Technology**: Spectral-spatial reverb engine with granular object-based panning
- **Key Features**:
  - Combines state-of-the-art reverberation with object-based 3D panning
  - **Only reverb plugin that directly connects to the Dolby Atmos Composer** on any DAW (even stereo-only DAWs)
  - Spacelab sources become dynamic objects in Dolby Atmos with one click
  - Renders reverb to any speaker layout for Atmos mixes
- **Architecture**: Plugin communicates with the Atmos Composer via local network protocol
- **URL**: [Spacelab Interstellar](https://fiedler-audio.com/spacelab-interstellar-immersive-3d-reverb/)

#### Dolby Atmos Composer (Fiedler Audio)

- **Developer**: Fiedler Audio (in partnership with Dolby)
- **Technology**: Master bus encoder + 3D panner for Dolby Atmos
- **Key Features**:
  - Works as an alternative to the official Dolby Atmos Production Suite
  - Integrates with any DAW (not just Pro Tools/Logic)
  - Free Essential version available, Pro version ~$299
- **URL**: [Dolby Atmos Composer](https://fiedler-audio.com/dolby-atmos-composer/)

#### Eventide Immersive Plugins

- **Developer**: Eventide
- **Technology**: Classic Eventide algorithms adapted for immersive formats
- **Key Features**: Multi-channel versions of flagship effects (reverb, delay, modulation)
- **Formats**: Support up to 7.1.4 Atmos bed processing
- **URL**: [Eventide Immersive](https://store.eventideaudio.com/collections/immersive-plugins)

#### APL Virtuoso v2

- **Developer**: APL
- **Technology**: Binaural virtualizer for stereo and immersive speaker setups
- **Key Features**: 5 built-in HRTF presets + custom SOFA file loading
- **Use Case**: Monitoring immersive mixes on headphones
- **URL**: [APL Virtuoso](https://apl-hud.com/product/virtuoso/)

#### Anaglyph (IRCAM)

- **Developer**: IRCAM (French research institute)
- **Technology**: Research-grade binaural renderer
- **Key Features**: Personalizable morphological ITD model, near-field ILD corrections
- **Use Case**: Scientific-grade binaural rendering for research and production
- **URL**: [Anaglyph](https://anaglyph.dalembert.upmc.fr/)

### Open-Source JUCE-Based Spatial Audio Plugins

#### SPARTA Suite (Leo McCormack)

- **Source**: [github.com/leomccormack/SPARTA](https://github.com/leomccormack/SPARTA)
- **Framework**: JUCE + Spatial Audio Framework (SAF)
- **Plugins Included**:
  - **AmbiENC**: Ambisonic encoder/panner (up to 10th order, 128 input channels)
  - **AmbiDEC**: Ambisonic decoder for loudspeaker arrays
  - **AmbiDRC**: Dynamic range compressor for ambisonics
  - **Binauraliser**: Binaural renderer with custom HRTF via SOFA files
  - **Panner**: Multi-source 3D panner
  - **Rotator**: Scene rotation for ambisonics
  - **SLDoA**: Direction-of-arrival analysis
  - **Compass**: Sound field visualization
- **Formats**: VST, VST3, AU, LV2, AAX
- **Platforms**: macOS, Linux, Windows
- **Build System**: CMake, requires JUCE and SAF as submodules
- **Why It Matters**: Best open-source reference for learning how to build spatial audio plugins with JUCE

#### Spatial Audio Framework (SAF)

- **Source**: [github.com/leomccormack/Spatial_Audio_Framework](https://github.com/leomccormack/Spatial_Audio_Framework)
- **Language**: Pure C (no JUCE dependency for the core)
- **Features**: HRTF processing, ambisonics, beamforming, room simulation, SOFA file I/O
- **Use Case**: DSP backend that SPARTA and other plugins use for spatial audio math

#### ambix (Matthias Kronlachner)

- **Source**: [github.com/kronihias/ambix](https://github.com/kronihias/ambix)
- **Framework**: JUCE
- **Features**: Variable-order ambisonics encoding/decoding, binaural decoding
- **Platforms**: macOS, Linux, Windows

#### EAR Production Suite (EBU)

- **Source**: [github.com/ebu/ear-production-suite](https://github.com/ebu/ear-production-suite/releases)
- **Purpose**: Official EBU tools for ADM (Audio Definition Model) production
- **Features**: Object-based audio authoring, ADM BWF export, monitoring tools
- **Integration**: Works with REAPER; demonstrates ADM metadata handling

#### Sound Field (mbarzach)

- **Source**: [github.com/mbarzach/Sound-Field](https://github.com/mbarzach/Sound-Field)
- **Technology**: JUCE 8 WebView integration with React frontend
- **Why Notable**: Demonstrates using JUCE 8's WebBrowserComponent for a spatial audio plugin UI

### DAW Integration Patterns

#### Logic Pro

- Native Atmos support since Logic Pro 10.7
- Built-in Dolby Atmos Renderer integration
- Supports up to 7.1.4 bed + 118 objects (cinema) / 16 objects (music)
- Third-party plugins work via AU format on Atmos busses

#### Pro Tools

- Industry standard for Atmos post-production
- Dolby Atmos Production Suite runs as AAX plugin
- Object routing via dedicated Atmos busses
- Third-party plugins must support multi-channel AAX formats

#### Nuendo / Cubase

- Built-in Dolby Atmos Renderer integration in Nuendo
- Nuendo Renderer for Dolby Atmos provides binaural downmix
- Steinberg's "Headphones Match" plugin for headphone correction
- VST3 format required for multi-channel support

#### Ableton / FL Studio / Bitwig (Gap Opportunity)

- **No native Atmos support** -- biggest gap in the market
- Workaround: Use Fiedler Audio Dolby Atmos Composer as a bridge
- Third-party solutions needed for object panning and metadata
- **Opportunity for indie developers**: Build Atmos bridge plugins for these DAWs

### Key Technical Patterns for Atmos Plugin Development

#### Pattern 1: Multi-Channel Bus Processing

Process the full Atmos bed (7.1.4 = 12 channels) with standard DSP:

```cpp
// In isBusesLayoutSupported():
// Accept 7.1.4 (12ch), 7.1.2 (10ch), 7.1 (8ch), 5.1 (6ch)
// Apply EQ, compression, reverb to all bed channels
// No metadata handling needed -- pure audio processing
```

**Examples**: Eventide immersive plugins, FabFilter Pro-Q (multi-channel mode)

#### Pattern 2: Object Panning with Metadata

Create a panner that positions audio objects in 3D space:

```cpp
// Parameters: azimuth (-180 to 180), elevation (-90 to 90), distance (0 to 1)
// Convert spherical to Cartesian for Atmos renderer
// Communicate position via DAW-specific object bus routing
// Automate positions for moving sources
```

**Examples**: Dolby Atmos Music Panner, dearVR PRO, SPARTA Panner

#### Pattern 3: Binaural Monitoring

Render spatial audio to headphones using HRTFs:

```cpp
// Load HRTF from SOFA file (standard format)
// For each audio source:
//   1. Look up HRTF pair for source's azimuth + elevation
//   2. Convolve audio with left-ear and right-ear HRTFs
//   3. Sum all sources for stereo binaural output
// Optional: Head-tracking via OSC for real-time HRTF updates
```

**Examples**: SPARTA Binauraliser, APL Virtuoso, Anaglyph

#### Pattern 4: Ambisonics Encoding/Decoding

Encode audio into ambisonics format, decode for speakers or headphones:

```cpp
// JUCE built-in: AudioChannelSet::ambisonic(order)
// Order 1 = 4 channels (FOA), Order 3 = 16 channels (HOA)
// Encode: source position -> SH coefficients -> ambisonic channels
// Decode: ambisonic channels -> speaker feeds or binaural
```

**Examples**: SPARTA AmbiENC/AmbiDEC, ambix, IEM Plugin Suite

#### Pattern 5: Bridge Plugin (Atmos for Non-Native DAWs)

Connect DAWs without native Atmos support to the Atmos renderer:

```cpp
// Run as a bus plugin in the DAW
// Communicate with Dolby Atmos Renderer via local network (OSC/proprietary)
// Send audio + metadata to external renderer
// Receive monitoring feeds back
```

**Examples**: Fiedler Audio Dolby Atmos Composer, FLUX:: Spat Revolution

### Development Considerations

| Consideration | Details |
|---------------|---------|
| **VST3 required** | Multi-channel support (7.1.4+) requires VST3 or AU; VST2 is limited |
| **Channel ordering** | JUCE's front-channel ordering matches VST3 SDK for Atmos versions |
| **SOFA files** | Standard for HRTF data; use libmysofa or SAF for parsing |
| **OSC protocol** | Common for head-tracking data and inter-app communication |
| **Thread safety** | HRTF convolution is CPU-intensive; use lockless queues for parameter updates |
| **Latency** | Binaural convolution adds latency; use partitioned convolution for low-latency |
| **Certification** | Commercial Atmos plugins may need Dolby certification for professional use |
| **Testing** | Test in multiple DAWs; Atmos routing differs significantly between hosts |

### Resources for Getting Started

1. **Build SPARTA from source** -- best way to learn JUCE spatial audio architecture
2. **Study the Spatial Audio Framework** -- understand the DSP math behind spatial audio
3. **Start with binaural** -- lowest barrier to entry, huge market demand
4. **Use REAPER for testing** -- most flexible multi-channel routing, free to try
5. **Join the JUCE Forum** -- active spatial audio discussion threads
6. **Attend ADC (Audio Developer Conference)** -- annual JUCE/audio dev conference with spatial audio workshops
