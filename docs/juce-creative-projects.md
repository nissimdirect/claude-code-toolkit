# JUCE Creative Projects Inspiration Library

> **Purpose:** Reference library of real-world JUCE projects, creative plugin implementations, architecture patterns, and learning resources for nissimdirect's plugin development.
>
> **Last Updated:** 2026-02-07
>
> **How to Use:** Browse by category. Each entry links to source code you can study. Entries tagged with `[PRD Match]` directly relate to our 5 plugin PRDs (Sidechain Operator, Saturation, Bitcrusher, Transient Detector, Stereo Imager).

---

## Table of Contents

1. [Creative JUCE Plugins on GitHub](#1-creative-juce-plugins-on-github)
2. [Tutorials and Advanced Learning](#2-tutorials-and-advanced-learning)
3. [Architecture Patterns](#3-architecture-patterns)
4. [JUCE + AI / Neural Audio](#4-juce--ai--neural-audio)
5. [PRD-Specific Plugin Examples](#5-prd-specific-plugin-examples)
6. [JUCE WebView UI Examples](#6-juce-webview-ui-examples)
7. [Meta-Resources](#7-meta-resources)

---

## 1. Creative JUCE Plugins on GitHub

### Chowdhury-DSP BYOD (Build Your Own Distortion)
- **URL:** https://github.com/Chowdhury-DSP/BYOD
- **What:** A modular guitar distortion plugin with a customizable signal chain. Contains analog-modeled circuits, digital creations, tone-shaping filters, and other signal processors.
- **Why It's Interesting:** The plugin's architecture is a modular processing chain where users wire up "processors" via "cables" -- essentially a node-based effects graph inside a plugin. Includes neural network-based amp models alongside traditional DSP.
- **Key Pattern:** Modular processor chain architecture. Each effect is a self-contained processor class that can be added/removed/reordered at runtime. Great model for building extensible plugin architectures.
- **Relevance:** [PRD Match: Saturation] -- Contains multiple waveshaping and saturation algorithms to study. Also relevant to the Bitcrusher PRD (has a "Krusher" module).

---

### Chowdhury-DSP ChowTapeModel
- **URL:** https://github.com/Chowdhury-DSP/AnalogTapeModel
- **What:** Physical model of an analog tape machine. Models hysteresis, wow/flutter, tape degradation, loss effects, and more.
- **Why It's Interesting:** One of the most academically rigorous open-source audio plugins. Jatin Chowdhury published papers on the DSP techniques used. Demonstrates how to translate academic DSP research into a shipping plugin.
- **Key Pattern:** Uses the Jatin Chowdhury hysteresis model (a modified Jiles-Atherton model) for magnetic tape saturation. Excellent oversampling implementation. Shows how to structure complex DSP with multiple interacting physical models.
- **Relevance:** [PRD Match: Saturation] -- The hysteresis/saturation modeling is directly applicable.

---

### hollance/mda-plugins-juce
- **URL:** https://github.com/hollance/mda-plugins-juce
- **What:** Modern JUCE implementations of the classic MDA plugin suite (originally by Paul Kellett). Includes ~30 plugins: dynamics, delay, pitch shift, stereo tools, degradation, and more.
- **Why It's Interesting:** Written by Matthijs Hollemans (hollance) as a learning resource. Each plugin is cleanly implemented in modern JUCE with detailed code comments explaining the DSP. The original MDA plugins are legendary in audio programming education.
- **Key Pattern:** Clean, well-commented DSP code. Each plugin is a standalone, minimal example of a specific effect type. Great for studying how classic effects work under the hood.
- **Relevance:** [PRD Match: ALL] -- The MDA suite includes compressors, degradation effects (bitcrusher-like), stereo tools, and dynamics processors. A goldmine for our 5 PRDs.

---

### hollance/TheKissOfShame
- **URL:** https://github.com/hollance/TheKissOfShame
- **What:** DSP magnetic tape emulation plugin. Models tape saturation, wow/flutter, and analog character.
- **Why It's Interesting:** Another tape saturation implementation from hollance, focused on the "shame" of tape artifacts. Simpler than ChowTapeModel, making it easier to study.
- **Key Pattern:** Straightforward tape saturation DSP with clean JUCE integration. Good intermediate-level code to study before tackling ChowTapeModel.
- **Relevance:** [PRD Match: Saturation] -- Direct tape saturation modeling reference.

---

### vvvar/PeakEater
- **URL:** https://github.com/vvvar/PeakEater
- **What:** A free, open-source wave shaper plugin (VST3/AU/LV2/CLAP). Designed for clipping/saturating peaks in a controlled way.
- **Why It's Interesting:** Clean, modern JUCE codebase with CLAP support. Implements multiple waveshaping curves. Has a polished UI with real-time waveform display. Ships cross-platform with CI/CD.
- **Key Pattern:** Multiple waveshaping transfer functions in a single plugin with user-selectable curves. Real-time waveform visualization. Modern CMake build system with GitHub Actions CI.
- **Relevance:** [PRD Match: Saturation] -- Waveshaping curves and clipping algorithms directly applicable.

---

### ffAudio/Frequalizer
- **URL:** https://github.com/ffAudio/Frequalizer
- **What:** A parametric equalizer built using JUCE's `juce::dsp` module. One of the earliest and most-referenced examples of using the JUCE DSP module.
- **Why It's Interesting:** Written by Daniel Walz (foleys), one of the most prominent JUCE community members. Shows proper use of `juce::dsp::IIR::Filter`, frequency response visualization, and real-time spectrum analysis.
- **Key Pattern:** `juce::dsp::ProcessorChain` usage. Real-time spectrum analyzer with FFT. Draggable filter band UI with frequency response overlay. Clean parameter-to-filter coefficient mapping.
- **Relevance:** Architecture patterns applicable to all PRDs. The filter band UI pattern is useful for any plugin with frequency-domain visualization.

---

### ZL-Audio/ZLEqualizer
- **URL:** https://github.com/ZL-Audio/ZLEqualizer
- **What:** A dynamic equalizer plugin with advanced features like dynamic EQ, sidechain per band, and collision detection.
- **Why It's Interesting:** Very active development (updated Jan 2026). Professional-quality open-source plugin with a polished UI. Demonstrates modern JUCE 8 practices and advanced dynamic processing.
- **Key Pattern:** Dynamic EQ architecture: per-band envelope followers, sidechain detection, sophisticated UI with OpenGL rendering. Multi-band processing with crossover filters.
- **Relevance:** [PRD Match: Sidechain Operator] -- The per-band sidechain detection is directly relevant.

---

### ZL-Audio/ZLCompressor
- **URL:** https://github.com/ZL-Audio/ZLCompressor
- **What:** A dynamic range processor plugin with advanced compression algorithms, look-ahead, and multi-band capabilities.
- **Why It's Interesting:** Actively maintained (Feb 2026). Modern JUCE 8 codebase from the same team as ZLEqualizer. Clean architecture for dynamics processing.
- **Key Pattern:** Modern compressor architecture with look-ahead buffer management, RMS/peak detection, and knee curve calculations.
- **Relevance:** [PRD Match: Sidechain Operator] -- Direct compressor implementation reference.

---

### ZL-Audio/ZLSplitter
- **URL:** https://github.com/ZL-Audio/ZLSplitter
- **What:** A multi-band splitter plugin that divides audio into frequency bands for parallel processing.
- **Why It's Interesting:** Essential utility for multi-band processing architectures. Clean implementation of crossover filters and band splitting.
- **Key Pattern:** Crossover filter design, band splitting, and recombination. Useful architecture pattern for any multi-band plugin.
- **Relevance:** Architecture pattern applicable to multi-band versions of any of our PRDs.

---

### p-hlp/CTAGDRC
- **URL:** https://github.com/p-hlp/CTAGDRC
- **What:** An audio compressor plugin with a clean, well-structured codebase. Includes gain reduction metering and standard compressor controls.
- **Why It's Interesting:** One of the most-referenced open-source JUCE compressors. Clean separation of DSP and UI. Well-documented code that's been forked many times as a learning resource.
- **Key Pattern:** Classic compressor topology: detector -> gain computer -> gain smoothing -> gain application. Clean `AudioProcessorValueTreeState` usage for parameter management.
- **Relevance:** [PRD Match: Sidechain Operator] -- Primary compressor reference implementation.

---

### Camomile (pierreguillot/Camomile)
- **URL:** https://github.com/pierreguillot/Camomile
- **What:** A plugin that embeds Pure Data (Pd) patches inside a VST3/AU plugin shell built with JUCE. Load any Pd patch and run it as a standard plugin.
- **Why It's Interesting:** Bridges visual patching (Pd) with the standard plugin ecosystem. Novel architecture: JUCE handles the plugin wrapper while Pd handles the DSP. Shows how to embed an entire runtime inside a JUCE plugin.
- **Key Pattern:** Embedding an external DSP runtime (libpd) inside a JUCE plugin shell. Inter-process communication between JUCE and the embedded engine.
- **Relevance:** Architecture inspiration -- shows how far you can push JUCE as a host/wrapper.

---

### PluginCollider (asb2m10/plugincollider)
- **URL:** https://github.com/asb2m10/plugincollider
- **What:** SuperCollider as a VST3 plugin. Write SuperCollider code and run it inside your DAW.
- **Why It's Interesting:** Similar concept to Camomile but with SuperCollider. Embeds the SC synthesis engine inside JUCE.
- **Key Pattern:** Embedding a live-coding audio engine inside a standard plugin format. Real-time code compilation within a plugin context.
- **Relevance:** Creative architecture inspiration for experimental plugin designs.

---

### OpenPiano (michele-perrone/OpenPiano)
- **URL:** https://github.com/michele-perrone/OpenPiano
- **What:** An open-source real-time piano engine based on physical modeling. Uses JUCE for the plugin wrapper and UI.
- **Why It's Interesting:** Demonstrates physical modeling synthesis in JUCE -- a rare and complex DSP domain. Models string vibration, hammer interaction, and soundboard resonance.
- **Key Pattern:** Physical modeling DSP: coupled oscillator systems, excitation models, resonance networks. Shows how to implement computationally expensive DSP within JUCE's real-time constraints.
- **Relevance:** Advanced DSP reference. Physical modeling techniques could inspire novel saturation or transient shaping approaches.

---

### RSBrokenMedia (reillypascal/RSBrokenMedia)
- **URL:** https://github.com/reillypascal/RSBrokenMedia
- **What:** A stereo glitch plugin with tape FX, CD skips, data errors, lo-fi codecs, and more. Simulates various forms of broken/degraded media.
- **Why It's Interesting:** Directly in the creative/experimental category. Combines multiple degradation algorithms: bitcrushing, sample rate reduction, buffer glitching, codec artifacts. Highly relevant to your glitch video aesthetic.
- **Key Pattern:** Multiple degradation algorithms in one plugin with blend controls. Buffer manipulation for stutter/glitch effects. Lo-fi codec emulation.
- **Relevance:** [PRD Match: Bitcrusher] -- Direct reference for degradation effects. Also aligns with your glitch video aesthetic.

---

### 1hoookkk/spectralcanvas-pro-v2
- **URL:** https://github.com/1hoookkk/spectralcanvas-pro-v2
- **What:** Real-time spectral synthesis plugin with a paint-to-audio interface. Users draw in the spectral domain to create sounds. JUCE 8 compatible.
- **Why It's Interesting:** Extremely creative concept: visual painting becomes audio through inverse FFT. Novel UI paradigm for sound design.
- **Key Pattern:** FFT/IFFT pipeline for spectral synthesis. Custom drawing/painting UI that maps to spectral data. Real-time spectral manipulation.
- **Relevance:** Creative UI inspiration. Spectral processing techniques applicable to advanced versions of any PRD.

---

### Azteriisk/SpectralSubtractor
- **URL:** https://github.com/Azteriisk/SpectralSubtractor
- **What:** A real-time spectral subtraction VST3 plugin for noise reduction and audio analysis. Built with JUCE.
- **Why It's Interesting:** Demonstrates real-time FFT-based processing in a plugin context. Spectral subtraction is a fundamental technique for noise reduction and source separation.
- **Key Pattern:** Real-time FFT overlap-add processing. Spectral analysis and modification. Noise profile capture and subtraction.
- **Relevance:** Spectral processing techniques applicable to the Transient Detector PRD.

---

### luismrguimaraes/SpectralPanner
- **URL:** https://github.com/luismrguimaraes/SpectralPanner
- **What:** An audio plugin for frequency-based panning. Different frequency ranges can be panned to different stereo positions.
- **Why It's Interesting:** Creative combination of spectral processing and stereo imaging. Each frequency band gets its own pan position.
- **Key Pattern:** FFT-based frequency-dependent stereo processing. Per-bin panning in the spectral domain.
- **Relevance:** [PRD Match: Stereo Imager] -- Directly relevant spectral stereo processing approach.

---

### Schrammel_OJD (JanosGit/Schrammel_OJD)
- **URL:** https://github.com/JanosGit/Schrammel_OJD
- **What:** Audio plugin model of a classic guitar overdrive pedal (OCD clone). Uses circuit modeling for analog-accurate distortion.
- **Why It's Interesting:** Written by Janos Buttgereit (also known for PluginGuiMagic). Uses the foleys_gui_magic module for a drag-and-drop GUI builder. Demonstrates analog circuit modeling for distortion.
- **Key Pattern:** Analog circuit modeling for overdrive/distortion. Uses `foleys_gui_magic` for rapid UI development without writing UI code by hand.
- **Relevance:** [PRD Match: Saturation] -- Circuit modeling approach to saturation/distortion.

---

### keithhearne/VSTPlugins
- **URL:** https://github.com/keithhearne/VSTPlugins
- **What:** A collection of VST plugins including reverbs (Schroeder, Moorer, Gardner), delay effects, and more. Implementations based on classic DSP literature.
- **Why It's Interesting:** Each plugin implements a well-known algorithm from DSP textbooks. Great for learning how classic effects work. Includes multiple reverb topologies for comparison.
- **Key Pattern:** Classic reverb topologies: comb filters, allpass chains, feedback delay networks. Each algorithm is clearly implemented following textbook descriptions.
- **Relevance:** Educational reference for understanding fundamental DSP building blocks.

---

### juandagilc/Audio-Effects
- **URL:** https://github.com/juandagilc/Audio-Effects
- **What:** Collection of audio effects plugins implemented from the book "Audio Effects: Theory, Implementation and Application" by Reiss and McPherson. Includes delay, flanger, chorus, phaser, tremolo, ring mod, compressor, wah, and more.
- **Why It's Interesting:** Textbook implementations in JUCE. Each effect is a standalone project with clear, academic-quality code. Based on one of the most widely used audio effects textbooks.
- **Key Pattern:** Textbook DSP implementations: LFOs, delay lines, feedback networks, envelope followers, sidechain detection. Each effect demonstrates a core DSP concept.
- **Relevance:** [PRD Match: ALL] -- Contains compressor, distortion, and other effects that map to our PRDs. Essential learning resource.

---

### cvde/RoomReverb
- **URL:** https://github.com/cvde/RoomReverb
- **What:** Mono/stereo algorithmic reverb with many presets. Clean implementation of room simulation.
- **Why It's Interesting:** Well-structured reverb with preset management system. Good example of shipping a polished free plugin with professional UI.
- **Key Pattern:** Preset management architecture. Algorithmic reverb design with multiple room types. Clean mono-to-stereo signal flow.
- **Relevance:** Preset management pattern applicable to all PRDs.

---

## 2. Tutorials and Advanced Learning

### The Audio Programmer (TheAudioProgrammer)
- **URL:** https://github.com/TheAudioProgrammer
- **Website:** https://www.theaudioprogrammer.com/
- **What:** YouTube channel and community run by Joshua Hodge focused on JUCE audio plugin development. Includes a Discord community, book ("Creating Synthesizer Plug-Ins With C++ and JUCE"), and multiple GitHub repos.
- **Why It's Interesting:** The largest JUCE-focused educational community. Covers beginner to advanced topics. The Discord is an active place to get help.
- **Key Resources:**
  - `BuildASynthPluginBook` -- Source code for the synth plugin book
  - `webview_juce_plugin_choc` -- Minimal JUCE + Choc WebView example
  - YouTube channel with hundreds of JUCE tutorials
- **Relevance:** Primary learning resource for JUCE development at all levels.

---

### WolfSound / Jan Wilczek (thewolfsound.com)
- **URL:** https://github.com/JanWilczek
- **Website:** https://thewolfsound.com/
- **What:** Blog and YouTube channel by Jan Wilczek focused on audio DSP and JUCE plugin development. Covers topics like WebView UI, FFT, filters, and plugin architecture.
- **Why It's Interesting:** High-quality written tutorials with accompanying code. Covers advanced topics like JUCE WebView integration, which is hard to find elsewhere.
- **Key Resources:**
  - `audio-plugin-template` -- Modern JUCE plugin template with CMake, CPM, and GoogleTest
  - `juce-webview-tutorial` -- Step-by-step JUCE WebView UI tutorial
- **Relevance:** Advanced tutorials directly applicable to our plugin development. The WebView tutorial is particularly valuable.

---

### hollance / Matthijs Hollemans
- **URL:** https://github.com/hollance
- **What:** Developer known for clear, educational audio plugin code. Author of the MDA plugins JUCE port, TheKissOfShame tape emulation, and the "Code Your Own Synth Plug-Ins" book.
- **Why It's Interesting:** Every repo is written as a teaching resource with extensive comments. If you want to understand how a specific DSP algorithm works, hollance's code is the place to look.
- **Key Resources:**
  - `synth-plugin-book` -- Source code for the synth plugin book
  - `mda-plugins-juce` -- 30+ classic effects ported to modern JUCE
  - `TheKissOfShame` -- Tape emulation
- **Relevance:** Primary code study resource. The mda-plugins-juce repo alone covers most effect types.

---

### Sudara / pamplejuce
- **URL:** https://github.com/sudara/pamplejuce
- **What:** A production-ready JUCE plugin template with JUCE 8, Catch2 testing, Pluginval validation, macOS notarization, and GitHub Actions CI/CD.
- **Why It's Interesting:** The most mature open-source JUCE plugin template. Handles all the boring-but-essential infrastructure: testing, validation, signing, CI/CD. Start here for any new plugin project.
- **Key Pattern:** CMake-based JUCE 8 project structure. Catch2 unit testing integration. GitHub Actions for automated builds and pluginval testing. macOS code signing and notarization.
- **Relevance:** **Use this as our plugin project template.** Saves weeks of infrastructure setup.

---

### JUCE Official Free Course (2026)
- **URL:** https://juce.com/
- **What:** JUCE launched a free audio plugin development course for beginners in January 2026.
- **Why It's Interesting:** Official, up-to-date material from the JUCE team. Covers JUCE 8 with current best practices.
- **Relevance:** Beginner-friendly starting point aligned with our skill level.

---

### awesome-musicdsp (olilarkin/awesome-musicdsp)
- **URL:** https://github.com/olilarkin/awesome-musicdsp
- **What:** A curated list of music DSP and audio programming resources. Covers DSP theory, books, libraries, forums, and tools.
- **Why It's Interesting:** Comprehensive index of DSP learning resources beyond JUCE. Includes links to papers, books, and code for specific DSP algorithms.
- **Relevance:** Reference for DSP algorithm research when implementing specific effects.

---

### Audio Plugin Development Resources (jareddrayton)
- **URL:** https://github.com/jareddrayton/Audio-Plugin-Development-Resources
- **What:** Curated collection of resources for audio plugin development including books, tutorials, forums, and tools.
- **Why It's Interesting:** Well-organized resource index covering the full plugin development landscape.
- **Relevance:** Meta-resource for finding specific tutorials and references.

---

## 3. Architecture Patterns

### Pattern: AudioProcessorValueTreeState (APVTS)
- **Best Example:** p-hlp/CTAGDRC, ffAudio/Frequalizer
- **What:** JUCE's recommended way to manage plugin parameters. Provides thread-safe parameter access, undo/redo support, DAW automation, and state save/restore.
- **Key Code Pattern:**
  ```cpp
  // In PluginProcessor.h
  juce::AudioProcessorValueTreeState apvts;

  // In constructor
  apvts(*this, nullptr, "Parameters", createParameterLayout())

  // Parameter layout factory
  static juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout()
  {
      std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;
      params.push_back(std::make_unique<juce::AudioParameterFloat>(
          "gain", "Gain", -60.0f, 12.0f, 0.0f));
      return { params.begin(), params.end() };
  }
  ```
- **Why It Matters:** This is the foundation pattern for every JUCE plugin. Get this right first.

---

### Pattern: Modular Processor Chain
- **Best Example:** Chowdhury-DSP/BYOD
- **What:** Instead of a monolithic `processBlock()`, break DSP into independent processor modules that can be chained, reordered, and individually bypassed.
- **Key Code Pattern:**
  ```cpp
  // Each processor inherits from a common base
  class BaseProcessor {
  public:
      virtual void prepare(const juce::dsp::ProcessSpec& spec) = 0;
      virtual void processBlock(juce::AudioBuffer<float>&) = 0;
      virtual void reset() = 0;
  };

  // Chain manages ordering and routing
  std::vector<std::unique_ptr<BaseProcessor>> processorChain;
  ```
- **Why It Matters:** Essential for plugins with multiple processing stages (like our Sidechain Operator with its detector + compressor + makeup gain stages).

---

### Pattern: juce::dsp::ProcessorChain
- **Best Example:** ffAudio/Frequalizer, JUCE DSPModulePluginDemo
- **What:** JUCE's built-in template for chaining DSP processors. Compile-time chain with zero overhead.
- **Key Code Pattern:**
  ```cpp
  using MonoChain = juce::dsp::ProcessorChain<
      juce::dsp::IIR::Filter<float>,   // Low cut
      juce::dsp::IIR::Filter<float>,   // Peak
      juce::dsp::IIR::Filter<float>,   // High cut
      juce::dsp::Gain<float>           // Output gain
  >;
  ```
- **Why It Matters:** The official JUCE way to chain processors. Type-safe and efficient.

---

### Pattern: Oversampling
- **Best Example:** Chowdhury-DSP/BYOD, vvvar/PeakEater
- **What:** Process audio at a higher internal sample rate to reduce aliasing from nonlinear operations (distortion, waveshaping, saturation).
- **Key Code Pattern:**
  ```cpp
  // In prepare()
  oversampling = std::make_unique<juce::dsp::Oversampling<float>>(
      numChannels, oversamplingFactor, filterType);
  oversampling->initProcessing(samplesPerBlock);

  // In processBlock()
  auto oversampledBlock = oversampling->processSamplesUp(inputBlock);
  // ... do nonlinear processing at higher rate ...
  oversampling->processSamplesDown(outputBlock);
  ```
- **Why It Matters:** [PRD Match: Saturation, Bitcrusher] -- Any plugin with nonlinear processing needs oversampling to sound professional.

---

### Pattern: Look-Ahead Buffer
- **Best Example:** JUCE forum SimpleCompressor, ZL-Audio/ZLCompressor
- **What:** Delay the audio signal while the detector analyzes upcoming samples. Allows the compressor to react before transients arrive, preventing overshoot.
- **Key Code Pattern:**
  ```cpp
  // Circular delay buffer for look-ahead
  juce::AudioBuffer<float> lookAheadBuffer;
  int writePosition = 0;

  // In processBlock: write to delay, read from (writePos - lookAheadSamples)
  ```
- **Why It Matters:** [PRD Match: Sidechain Operator] -- Look-ahead is essential for transparent limiting and precise transient control.

---

### Pattern: Preset Management
- **Best Example:** cvde/RoomReverb
- **What:** Save and load parameter states as presets. Includes factory presets, user presets, and A/B comparison.
- **Key Code Pattern:**
  ```cpp
  // Save state to XML
  void getStateInformation(juce::MemoryBlock& destData) override {
      auto state = apvts.copyState();
      auto xml = state.createXml();
      copyXmlToBinary(*xml, destData);
  }

  // Restore state from XML
  void setStateInformation(const void* data, int sizeInBytes) override {
      auto xml = getXmlFromBinary(data, sizeInBytes);
      if (xml && xml->hasTagName(apvts.state.getType()))
          apvts.replaceState(juce::ValueTree::fromXml(*xml));
  }
  ```
- **Why It Matters:** Every shipping plugin needs preset management. Get the state save/restore right early.

---

### Pattern: Thread-Safe Metering
- **Best Example:** p-hlp/CTAGDRC (gain reduction meter), ffAudio/Frequalizer (spectrum)
- **What:** Safely pass metering data (levels, gain reduction, spectrum) from the audio thread to the UI thread without locks.
- **Key Code Pattern:**
  ```cpp
  // Atomic values for simple metering
  std::atomic<float> gainReduction { 0.0f };

  // FIFO for complex data (spectrum, waveform)
  juce::AbstractFifo fifo;
  ```
- **Why It Matters:** All our PRDs need metering. This pattern prevents audio glitches from UI updates.

---

### Pattern: foleys_gui_magic (No-Code UI)
- **Best Example:** ffAudio/PluginGuiMagic, JanosGit/Schrammel_OJD
- **URL:** https://github.com/ffAudio/PluginGuiMagic
- **What:** A JUCE module that lets you design plugin UIs visually using XML/CSS-like stylesheets, without writing UI code. Drag-and-drop in a live editor.
- **Why It Matters:** Dramatically speeds up UI development. Good for prototyping before building a custom UI.

---

## 4. JUCE + AI / Neural Audio

### DDSP-VST (Google Magenta)
- **URL:** https://github.com/magenta/ddsp-vst
- **What:** Real-time DDSP (Differentiable Digital Signal Processing) neural synthesizer and audio effect. VST3/AU plugins built with JUCE. Includes both a synth (MIDI input) and an effect (audio input for timbre transfer).
- **Why It's Interesting:** Production-quality neural audio from Google. The DDSP approach decomposes audio into pitch + loudness, then resynthesizes using learned timbres. Users can train custom models for free using Google Colab.
- **Key Pattern:** Neural network inference in real-time audio context. Uses a tiny CREPE pitch detection model (~160k params, 137x smaller than original). Two-stage architecture: detection -> neural synthesis control -> additive/subtractive synthesis.
- **Relevance:** Reference for integrating ML models into JUCE plugins. The architecture (detect features -> neural control -> DSP synthesis) is applicable to intelligent audio effects.

---

### GuitarML SmartGuitarAmp
- **URL:** https://github.com/GuitarML/SmartGuitarAmp
- **What:** Guitar amp emulation plugin using neural networks (LSTM) to model real tube amplifiers. Built with JUCE.
- **Why It's Interesting:** One of the first widely-used neural amp modelers. Uses a WaveNet-style architecture for real-time inference. Demonstrated that neural networks can replace traditional circuit modeling.
- **Key Pattern:** WaveNet-based real-time inference for audio. Model loading and switching at runtime. Balancing neural network complexity with real-time performance constraints.
- **Relevance:** [PRD Match: Saturation] -- Neural approach to amp/tube emulation as an alternative to traditional waveshaping.

---

### GuitarML Proteus
- **URL:** https://github.com/GuitarML/Proteus
- **What:** Guitar amp and pedal capture plugin using LSTM neural networks. Successor to SmartGuitarAmp with dramatically reduced CPU usage. Users can capture their own gear.
- **Why It's Interesting:** Uses RTNeural for highly optimized inference. Includes a "capture utility" for users to train models of their own gear. Supports "knob captures" that model the full range of a physical knob.
- **Key Pattern:** RTNeural integration for real-time LSTM inference. Model capture/training pipeline. Parameterized neural models (modeling knob positions, not just static snapshots).
- **Relevance:** [PRD Match: Saturation] -- Shows how neural networks can model analog saturation characteristics.

---

### GuitarML NeuralPi
- **URL:** https://github.com/GuitarML/NeuralPi
- **What:** Neural amp modeling on Raspberry Pi 4. A JUCE VST3 plugin that runs on Elk Audio OS for embedded hardware.
- **Why It's Interesting:** Demonstrates JUCE running on embedded Linux (Raspberry Pi). Cross-compilation workflow for ARM targets. WiFi-based remote control from a desktop plugin instance.
- **Key Pattern:** Cross-compilation of JUCE plugins for embedded targets. Remote parameter control over network. Optimizing neural inference for resource-constrained hardware.
- **Relevance:** Future reference if we ever want to build hardware.

---

### RTNeural (jatinchowdhury18/RTNeural)
- **URL:** https://github.com/jatinchowdhury18/RTNeural
- **What:** Lightweight C++ neural network inference library designed specifically for real-time audio. Supports LSTM, GRU, Dense layers. Used by GuitarML Proteus, Chowdhury-DSP plugins, and many others.
- **Why It's Interesting:** The standard library for running neural networks inside audio plugins. Designed to be real-time safe (no memory allocation on audio thread). Header-only option available. Supports Eigen, xsimd, or STL backends.
- **Key Pattern:** Real-time safe neural inference. Load trained model weights from JSON. Choose compute backend based on performance needs. No dynamic memory allocation during inference.
- **Relevance:** **The library to use** if we ever add neural network features to our plugins.

---

### Anira
- **URL:** https://anira-project.github.io/anira/
- **What:** High-performance library for real-time safe neural network inference in audio applications. Supports LibTorch, ONNXRuntime, and TensorFlow Lite backends.
- **Why It's Interesting:** Backend-agnostic (supports 3 major ML frameworks). Designed specifically for audio's real-time constraints. More flexible than RTNeural for larger/more complex models.
- **Key Pattern:** Abstraction layer over multiple ML inference backends. Real-time safe execution scheduling. Model format conversion and optimization.
- **Relevance:** Alternative to RTNeural for more complex ML models.

---

### WaveNetVA (damskaggep/WaveNetVA)
- **URL:** https://github.com/damskaggep/WaveNetVA
- **What:** WaveNet for virtual analog modeling, implemented as a real-time JUCE audio plugin. Models analog circuits using a WaveNet architecture.
- **Why It's Interesting:** One of the earliest implementations of WaveNet for real-time audio plugin use. Academic project that demonstrated the viability of neural network-based analog modeling.
- **Key Pattern:** WaveNet architecture adapted for real-time use. Dilated causal convolutions for temporal modeling. Training pipeline for analog circuit modeling.
- **Relevance:** [PRD Match: Saturation] -- Academic reference for neural analog modeling.

---

### ronn (csteinmetz1/ronn)
- **URL:** https://github.com/csteinmetz1/ronn
- **What:** Randomized Overdrive Neural Networks. Explores using randomly initialized neural networks as nonlinear audio effects (no training required).
- **Why It's Interesting:** Radical concept: the neural network IS the effect, not a model of an existing effect. Random weights create unique, never-heard-before distortion characteristics. Each random seed = a unique distortion pedal.
- **Key Pattern:** Using neural networks as novel audio effects rather than emulations. Random parameter exploration for creative sound design. Lightweight neural network architectures for real-time use.
- **Relevance:** [PRD Match: Saturation, Bitcrusher] -- Creative approach to generating novel distortion/degradation effects. Aligns with our experimental aesthetic.

---

### grandMatronPlugin (nicholasbulka/grandMatronPlugin)
- **URL:** https://github.com/nicholasbulka/grandMatronPlugin
- **What:** An audio neural network plugin modeling a low pass filter. Built in JUCE.
- **Why It's Interesting:** Simpler neural audio example, good for learning the basics of ML integration in JUCE without the complexity of amp modeling.
- **Key Pattern:** Basic neural network integration in a JUCE plugin. Filter modeling with ML.
- **Relevance:** Learning resource for ML + JUCE integration.

---

### juce-ddsp (SMC704/juce-ddsp)
- **URL:** https://github.com/SMC704/juce-ddsp
- **What:** JUCE implementation of DDSP (Differentiable Digital Signal Processing). Uses TensorFlow for inference.
- **Why It's Interesting:** Alternative DDSP implementation to Google's official ddsp-vst. Shows TensorFlow integration in JUCE.
- **Key Pattern:** TensorFlow DLL integration with JUCE. DDSP synthesis pipeline in C++.
- **Relevance:** Reference for TensorFlow-based ML in JUCE plugins.

---

## 5. PRD-Specific Plugin Examples

### Sidechain Compressor Implementations

#### p-hlp/CTAGDRC
- **URL:** https://github.com/p-hlp/CTAGDRC
- **What:** Clean compressor implementation with gain reduction meter, highpass sidechain filter.
- **Key Pattern:** Classic feedforward compressor topology. Envelope follower with adjustable attack/release. Soft-knee implementation.
- **Relevance:** [PRD Match: Sidechain Operator] -- **Primary reference.**

#### freddlv/Sidechained
- **URL:** https://github.com/freddlv/Sidechained
- **What:** Plugin that sidechains audio with a customizable UI envelope and different time intervals. Specifically designed around the sidechain concept.
- **Key Pattern:** Customizable envelope for sidechain ducking. Different time interval modes. Visual envelope editor UI.
- **Relevance:** [PRD Match: Sidechain Operator] -- Directly relevant sidechain-specific plugin.

#### jcurtis4207/Juce-Plugins (Compressor)
- **URL:** https://github.com/jcurtis4207/Juce-Plugins
- **What:** Collection including a versatile compressor with stereo gain reduction meter, highpass filter sidechain, and switchable stereo/multi-mono linking modes.
- **Key Pattern:** Stereo linking modes (stereo vs. dual-mono). Sidechain highpass filter. Gain reduction metering.
- **Relevance:** [PRD Match: Sidechain Operator] -- Stereo linking and sidechain filter features.

#### buosseph/JuceCompressor
- **URL:** https://github.com/buosseph/JuceCompressor
- **What:** A straightforward compressor plugin in JUCE. Minimal but functional.
- **Key Pattern:** Minimal compressor implementation. Good starting point before studying more complex implementations.
- **Relevance:** [PRD Match: Sidechain Operator] -- Simplest compressor reference.

---

### Saturation / Tube Emulation Implementations

#### Chowdhury-DSP/BYOD
- **URL:** https://github.com/Chowdhury-DSP/BYOD
- **What:** Modular distortion chain with many saturation algorithms: tube models, transistor models, waveshapers, neural amp models.
- **Key Pattern:** Multiple waveshaping transfer functions. Circuit-modeled nonlinearities. Neural network-based amp models alongside traditional DSP.
- **Relevance:** [PRD Match: Saturation] -- **Primary reference.** Contains multiple saturation approaches to compare.

#### vvvar/PeakEater
- **URL:** https://github.com/vvvar/PeakEater
- **What:** Waveshaping plugin with multiple clipping curves. Clean, modern implementation.
- **Key Pattern:** Waveshaping transfer function library. Input/output gain staging. Real-time waveform display.
- **Relevance:** [PRD Match: Saturation] -- Waveshaping curve implementations.

#### DubzyWubzy/MMUDD
- **URL:** https://github.com/DubzyWubzy/MMUDD
- **What:** A distortion/saturation/overdrive plugin. Starting codebase from WolfSound Academy's JUCE course.
- **Key Pattern:** Multiple distortion modes (distortion, saturation, overdrive) in one plugin. Based on educational course material.
- **Relevance:** [PRD Match: Saturation] -- Clean educational implementation of multiple saturation types.

#### JanosGit/Schrammel_OJD
- **URL:** https://github.com/JanosGit/Schrammel_OJD
- **What:** Analog circuit model of the OCD overdrive pedal. Uses foleys_gui_magic for UI.
- **Key Pattern:** Component-level analog circuit modeling. Asymmetric clipping. Tone stack modeling.
- **Relevance:** [PRD Match: Saturation] -- Circuit modeling approach.

---

### Bitcrusher / Decimator Implementations

#### dfilaretti/bitcrusher-demo-2
- **URL:** https://github.com/dfilaretti/bitcrusher-demo-2
- **What:** Simple bitcrusher plugin. Clean, tutorial-quality code.
- **Key Pattern:** Bit depth reduction. Sample rate reduction (decimation). Simple but effective implementation.
- **Relevance:** [PRD Match: Bitcrusher] -- **Start here.** Simplest, cleanest bitcrusher implementation.

#### sunquan8094/Krush3x
- **URL:** https://github.com/sunquan8094/Krush3x
- **What:** Experimental bitcrusher with additional creative parameters beyond basic bit/rate reduction.
- **Key Pattern:** Extended bitcrusher with experimental parameters. Goes beyond the basics of bit depth and sample rate reduction.
- **Relevance:** [PRD Match: Bitcrusher] -- Creative/experimental take on bitcrushing.

#### kasiadamska/bitcrusher
- **URL:** https://github.com/kasiadamska/bitcrusher
- **What:** Bitcrusher with additional delay and highpass filter for more interesting sound.
- **Key Pattern:** Combining bitcrusher with delay and filtering for musical results. Shows how to layer simple effects for creative outcomes.
- **Relevance:** [PRD Match: Bitcrusher] -- Multi-effect approach to bitcrushing.

#### nathanshaw/juce_decimator
- **URL:** https://github.com/nathanshaw/juce_decimator
- **What:** Audio plugin presenting several different ways to "destroy" audio. Multiple decimation algorithms.
- **Key Pattern:** Multiple audio destruction algorithms in one plugin. Different approaches to sample rate reduction and bit depth quantization.
- **Relevance:** [PRD Match: Bitcrusher] -- Multiple destruction algorithms to compare.

#### reillypascal/RSBrokenMedia
- **URL:** https://github.com/reillypascal/RSBrokenMedia
- **What:** Glitch plugin with tape FX, CD skips, data errors, lo-fi codecs. Comprehensive media degradation.
- **Key Pattern:** Buffer glitching, codec emulation, multiple degradation modes. Goes far beyond simple bitcrushing into creative territory.
- **Relevance:** [PRD Match: Bitcrusher] -- Extended degradation effects. Inspiration for creative bitcrusher features.

---

### Transient Detector / Drum Separator Implementations

#### juandagilc/Audio-Effects (Compressor/Gate)
- **URL:** https://github.com/juandagilc/Audio-Effects
- **What:** The compressor and gate implementations include envelope follower and transient detection code.
- **Key Pattern:** Envelope follower implementations (peak, RMS). Attack/release envelope shaping. Threshold-based detection.
- **Relevance:** [PRD Match: Transient Detector] -- Core envelope follower and detection algorithms.

#### Azteriisk/SpectralSubtractor
- **URL:** https://github.com/Azteriisk/SpectralSubtractor
- **What:** Spectral subtraction for noise removal. The spectral analysis techniques are applicable to transient detection.
- **Key Pattern:** FFT-based audio analysis. Spectral profile capture. Frequency-domain signal separation.
- **Relevance:** [PRD Match: Transient Detector] -- Spectral analysis techniques for frequency-aware transient detection.

#### p-hlp/CTAGDRC (Detector Section)
- **URL:** https://github.com/p-hlp/CTAGDRC
- **What:** The compressor's detector section implements peak and RMS envelope following that can be studied for transient detection.
- **Key Pattern:** Ballistics modeling (attack/release curves). Peak vs. RMS detection modes. Logarithmic gain computation.
- **Relevance:** [PRD Match: Transient Detector] -- The detector/envelope follower code is the core of transient detection.

---

### Stereo Imaging Implementations

#### joericook/mid-side-stereo-shaper
- **URL:** https://github.com/joericook/mid-side-stereo-shaper
- **What:** VST3 plugin for mid-side stereo processing. Encodes L/R to M/S, applies independent gain, then decodes back to L/R.
- **Key Pattern:** M/S encoding: `mid = (L + R) * 0.5; side = (L - R) * 0.5;`. Independent mid/side gain control. M/S decoding: `L = mid + side; R = mid - side;`.
- **Relevance:** [PRD Match: Stereo Imager] -- **Primary reference.** Clean, focused M/S implementation.

#### liquid1224/LPanner
- **URL:** https://github.com/liquid1224/LPanner
- **What:** Stereo manager VST3 plugin with both Classic Mode (mid/side width control) and Modern Mode (delay-based stereo enhancement).
- **Key Pattern:** Two stereo widening approaches: M/S gain ratio (Classic) and delay-based Haas effect (Modern). Stereo rotation/balance. Correlation metering.
- **Relevance:** [PRD Match: Stereo Imager] -- **Key reference.** Multiple stereo imaging algorithms in one plugin.

#### luismrguimaraes/SpectralPanner
- **URL:** https://github.com/luismrguimaraes/SpectralPanner
- **What:** Frequency-based panning. Different frequency ranges panned to different stereo positions.
- **Key Pattern:** FFT-based per-frequency stereo positioning. Spectral domain stereo manipulation.
- **Relevance:** [PRD Match: Stereo Imager] -- Advanced spectral approach to stereo imaging.

#### Harsha-vardhan-R/Analytiks
- **URL:** https://github.com/Harsha-vardhan-R/Analytiks
- **What:** JUCE plugin for spectral and stereo analysis. Open-source Voxengo SPAN alternative with OpenGL rendering.
- **Key Pattern:** Stereo correlation metering. Lissajous/goniometer display. Phase correlation analysis. OpenGL-rendered audio visualization.
- **Relevance:** [PRD Match: Stereo Imager] -- Stereo analysis and visualization techniques for the UI.

---

## 6. JUCE WebView UI Examples

### TheAudioProgrammer/webview_juce_plugin_choc
- **URL:** https://github.com/TheAudioProgrammer/webview_juce_plugin_choc
- **What:** Most basic implementation of a JUCE plugin with a JavaScript/HTML/CSS user interface using the Choc library. Registers a GAIN parameter and controls it from a web UI.
- **Why It's Interesting:** Minimal, easy-to-understand starting point for WebView-based plugin UIs. Uses Choc (by Julian Storer, JUCE's creator) for the WebView bridge.
- **Key Pattern:** Choc WebView integration with JUCE. JavaScript-to-C++ parameter bridging. HTML/CSS for plugin UI layout.
- **Relevance:** **Starting template** if we want web-based UIs for our plugins.

---

### JanWilczek/juce-webview-tutorial
- **URL:** https://github.com/JanWilczek/juce-webview-tutorial
- **What:** Step-by-step tutorial repo for building JUCE plugin UIs using web technologies. Accompanies a detailed written tutorial.
- **Why It's Interesting:** The most thorough tutorial on JUCE WebView integration. Goes beyond basics into parameter sync, event handling, and production considerations.
- **Key Pattern:** JUCE 8 `juce::WebBrowserComponent` integration. Bidirectional C++/JS communication. Parameter state synchronization between DSP and UI.
- **Relevance:** Detailed learning resource for WebView UI approach.

---

### JoshMarler/react-juce (Blueprint)
- **URL:** https://github.com/JoshMarler/react-juce
- **What:** Write JUCE plugin UIs using React.js. Embeds a JavaScript engine (Duktape) and renders React components to native `juce::Component` instances. Uses Yoga for flexbox layout.
- **Why It's Interesting:** React Native-style approach for audio plugins. Write UI in JavaScript/React, render as native JUCE components. Flexbox layout engine for responsive UIs.
- **Key Pattern:** Embedded JS engine (Duktape) for React rendering. React component tree -> juce::Component tree mapping. Yoga flexbox layout integration.
- **Relevance:** Alternative to raw WebView. More "native" feel while using web technologies.

---

### spherop/vst-loop-engine
- **URL:** https://github.com/spherop/vst-loop-engine
- **What:** JUCE audio loop engine plugin with WebView UI. Combines audio looping with a web-based interface.
- **Why It's Interesting:** Real-world example of a complete plugin with WebView UI (not just a demo/tutorial). Shows how WebView UIs work in a production context.
- **Key Pattern:** WebView UI for a complex plugin (looper). State management between audio engine and web frontend.
- **Relevance:** Production reference for WebView UI approach.

---

### spherop/fuzz-delay-plugin
- **URL:** https://github.com/spherop/fuzz-delay-plugin
- **What:** JUCE delay plugin with BBD analog modeling and WebView UI. Includes sample-based testing.
- **Why It's Interesting:** Combines analog modeling DSP with modern WebView UI. Also includes sample-based testing (comparing output to reference audio files).
- **Key Pattern:** BBD (Bucket Brigade Device) analog delay modeling. WebView UI for effects plugin. Sample-based audio testing methodology.
- **Relevance:** [PRD Match: Saturation] -- BBD modeling is an analog emulation technique. Also WebView UI reference.

---

### vidaliATWIT/616WebView
- **URL:** https://github.com/vidaliATWIT/616WebView
- **What:** React frontend for a delay/looper plugin using JUCE WebViews.
- **Why It's Interesting:** Shows React + JUCE WebView integration for a specific plugin type. Demonstrates the full React development workflow alongside JUCE.
- **Key Pattern:** React build pipeline integrated with JUCE CMake build. Component-based UI architecture using React.
- **Relevance:** Reference for React-based plugin UIs.

---

### tomduncalf/WebUISynth
- **URL:** https://github.com/tomduncalf/WebUISynth
- **What:** A simple synth with JUCE audio engine and React/TypeScript web UI. Built using a custom `juce_browser_integration` module.
- **Why It's Interesting:** TypeScript-first approach to web UI development. Custom JUCE module for browser integration (cleaner than ad-hoc Choc integration).
- **Key Pattern:** TypeScript/React UI with JUCE backend. Custom JUCE module for web UI integration. Type-safe JavaScript-to-C++ communication.
- **Relevance:** TypeScript approach for web-based plugin UIs.

---

### tomduncalf/tomduncalf_juce_web_ui
- **URL:** https://github.com/tomduncalf/tomduncalf_juce_web_ui
- **What:** A JUCE module providing helper classes for integrating web-based UIs with JUCE applications.
- **Why It's Interesting:** Reusable JUCE module (not a full plugin) that can be dropped into any project to add web UI support.
- **Key Pattern:** JUCE module architecture for web UI integration. Reusable helper classes for C++/JS bridging.
- **Relevance:** Reusable module approach for adding web UI to our plugins.

---

## 7. Meta-Resources

### awesome-juce (sudara/awesome-juce)
- **URL:** https://github.com/sudara/awesome-juce
- **What:** The definitive curated list of open-source JUCE modules, templates, plugins, and utilities. Updated nightly with activity indicators.
- **Why It's Interesting:** Color-coded activity status (green = active, orange = stale, red = abandoned). Categorized by type (templates, modules, plugins, tools). The single best index of the JUCE open-source ecosystem.
- **Key Categories:**
  - **Templates:** pamplejuce, JUCECmakeRepoPrototype
  - **Modules:** melatonin_blur (fast CPU blurs/shadows), melatonin_inspector (component inspector like browser DevTools), chowdsp_utils (DSP utilities)
  - **Tools:** pluginval (cross-platform plugin validation by Tracktion)
  - **UI:** juce_murka (GPU-accelerated ImGui-style UI for JUCE)
- **Relevance:** **Bookmark this.** Check it before building anything -- someone may have already built a module for it.

---

### OpenAudio (openaudio.webprofusion.com)
- **URL:** http://openaudio.webprofusion.com/
- **What:** Directory of open-source audio plugins and applications. Searchable and filterable by format, platform, and category.
- **Why It's Interesting:** Broader than awesome-juce (includes non-JUCE plugins). Good for finding inspiration across the entire open-source audio ecosystem.
- **Relevance:** Discovery tool for finding reference implementations of specific effect types.

---

### KVR Audio Forums (DSP and Plugin Development)
- **URL:** https://www.kvraudio.com/forum/viewforum.php?f=33
- **What:** The largest audio plugin development forum. Active discussions on DSP algorithms, JUCE development, plugin architecture, and business.
- **Why It's Interesting:** Decades of accumulated knowledge. Many professional plugin developers participate. Search for specific DSP topics to find expert discussions.
- **Relevance:** Go-to forum for DSP algorithm questions and implementation advice.

---

### JUCE Forum
- **URL:** https://forum.juce.com/
- **What:** Official JUCE community forum. Includes categories for audio plugins, DSP, UI, and general discussion.
- **Why It's Interesting:** Direct access to JUCE team members. Searchable archive of solutions to common JUCE problems.
- **Key Threads:**
  - SimpleCompressor with look-ahead article: https://forum.juce.com/t/simplecompressor-juce-processor-with-article-of-how-to-implement-look-ahead/34942
  - External sidechain compressor discussion: https://forum.juce.com/t/external-sidechain-compressor/12094
  - Mid-side encoding/decoding: https://forum.juce.com/t/mid-side-encoding-decoding-plugin/45520
  - Blueprint/React-JUCE announcement: https://forum.juce.com/t/introducing-blueprint-build-native-juce-interfaces-with-react-js/34174
- **Relevance:** Primary support resource for JUCE development questions.

---

### plugin-freedom-system (glittercowboy/plugin-freedom-system)
- **URL:** https://github.com/glittercowboy/plugin-freedom-system
- **What:** AI-assisted JUCE plugin development system for macOS by TACHES. A framework/workflow for using AI tools to accelerate plugin development.
- **Why It's Interesting:** Directly aligned with our Claude-assisted workflow. Shows how other developers are using AI to build JUCE plugins.
- **Key Pattern:** AI-in-the-loop plugin development workflow. Templates and prompts for AI-assisted coding.
- **Relevance:** Meta-reference for our own AI-assisted development approach.

---

## Quick Reference: PRD to Plugin Mapping

| Our PRD | Primary References | Secondary References |
|---------|-------------------|---------------------|
| **Sidechain Operator** | CTAGDRC, Sidechained, ZLCompressor | jcurtis4207 Compressor, Audio-Effects (compressor), SimpleCompressor forum thread |
| **Saturation** | BYOD, PeakEater, ChowTapeModel | TheKissOfShame, Schrammel_OJD, MMUDD, ronn, SmartGuitarAmp (neural) |
| **Bitcrusher** | bitcrusher-demo-2, RSBrokenMedia, juce_decimator | Krush3x, kasiadamska/bitcrusher, BYOD (Krusher module) |
| **Transient Detector** | Audio-Effects (gate/compressor), CTAGDRC detector | SpectralSubtractor, ZLCompressor (detection section) |
| **Stereo Imager** | mid-side-stereo-shaper, LPanner | SpectralPanner, Analytiks (visualization) |

---

## Quick Reference: Technology Decisions

| Decision | Recommended Tool | Why |
|----------|-----------------|-----|
| **Project Template** | pamplejuce | CI/CD, testing, notarization out of the box |
| **UI Approach (v1)** | Native JUCE Components | Simpler, faster to build, no web stack needed |
| **UI Approach (v2)** | Choc WebView or react-juce | Modern look, web dev skills transfer |
| **GUI Builder (prototyping)** | foleys_gui_magic | Drag-and-drop UI without writing code |
| **Neural Networks** | RTNeural | Standard library, real-time safe, header-only |
| **Plugin Validation** | pluginval (Tracktion) | Industry standard, catches common bugs |
| **Component Inspector** | melatonin_inspector | Browser DevTools-style inspection for JUCE |
| **Fast Blur/Shadows** | melatonin_blur | CPU-rendered, cross-platform, fast |
| **Learning DSP** | mda-plugins-juce, Audio-Effects | Clean, commented textbook implementations |
| **Learning JUCE** | The Audio Programmer, WolfSound | Video + written tutorials, active communities |
