# Audio DSP Creative Projects - Inspiration Library

> **Purpose:** Curated collection of real-world creative audio projects using Python DSP tools.
> Intended as a reference for prototyping audio plugin ideas before building in JUCE/C++.
>
> **Last Updated:** 2026-02-07

---

## Table of Contents

1. [Creative Audio Projects on GitHub](#1-creative-audio-projects-on-github)
2. [librosa Creative Applications](#2-librosa-creative-applications)
3. [scipy.signal Creative Uses](#3-scipysignal-creative-uses)
4. [Sound Art and Experimental Audio](#4-sound-art-and-experimental-audio)
5. [Audio + MIDI Creative Tools](#5-audio--midi-creative-tools)
6. [DSP Algorithm Implementations](#6-dsp-algorithm-implementations)
7. [Neural Audio Projects](#7-neural-audio-projects)
8. [Real-Time Audio in Python](#8-real-time-audio-in-python)

---

## 1. Creative Audio Projects on GitHub

### Pedalboard (Spotify)
- **URL:** https://github.com/spotify/pedalboard
- **Stack:** JUCE (C++ backend), Python bindings, numpy, compatible with VST3/AU plugins
- **What:** Spotify's production-grade audio effects library. Chain effects like a guitar pedalboard. Wraps JUCE DSP internally and exposes it to Python.
- **Why It's Interesting:** Built on JUCE -- the same framework we use for plugins. Up to 300x faster than other Python audio packages. Can load and host VST3/AU plugins directly from Python. Releases the GIL for multi-core use.
- **Key Algorithm:** Full effects chain: Compressor, Chorus, Delay, Distortion, Gain, HighpassFilter, Phaser, Reverb, LowpassFilter, Limiter, NoiseGate, PitchShift, Resample, Convolution.
- **Plugin Potential:** HIGH. Perfect prototyping tool -- design effect chains in Python, then port the DSP logic to JUCE C++. Use it to A/B test your plugin output against known-good implementations.

### python_audio_dsp (Metallicode)
- **URL:** https://github.com/Metallicode/python_audio_dsp
- **Stack:** numpy, scipy, soundfile
- **What:** Comprehensive Python DSP library covering synthesis (oscillators, wavetable, additive, FM, granular), effects (distortion, delay, reverb, chorus, flanger, phaser, compressor), and sequencing.
- **Why It's Interesting:** Unified API: `effect(signal, sample_rate, **params) -> numpy.ndarray`. Covers nearly every standard DSP building block in clean, readable Python. Multi-band saturation and sidechain compression included.
- **Key Algorithm:** Multi-band saturation with crossover networks, sidechain compression, granular synthesis engine.
- **Plugin Potential:** HIGH. Each effect is a standalone function -- perfect for extracting and porting individual algorithms to JUCE. The sidechain compress maps directly to Sidechain Operator plugin.

### EmissionControl2 (EC2)
- **URL:** https://github.com/EmissionControl2/EmissionControl2
- **Stack:** C++ (allolib framework), cross-platform (OSX/Linux/Windows)
- **What:** Standalone real-time granular synthesis application. Interactive sound file granulation with comprehensive parameter control.
- **Why It's Interesting:** Production-quality granular engine with real-time parameter modulation. Shows how to build a complete granular synth UI with waveform display, grain visualization, and preset management.
- **Key Algorithm:** Grain cloud generation with per-grain pitch, position, duration, and amplitude envelopes. Asynchronous grain scheduling.
- **Plugin Potential:** MEDIUM. Architecture reference for building a granular synthesis plugin. The parameter modulation system is worth studying.

### SoundGrain
- **URL:** https://github.com/belangeo/soundgrain
- **Stack:** Python, wxPython (GUI), pyo (audio engine)
- **What:** Graphical interface where users draw and edit trajectories to control granular sound synthesis. Trajectory paths determine how grains are selected and played.
- **Why It's Interesting:** Visual-to-audio mapping -- draw shapes, hear sounds. This is the cross-modal creative interaction pattern: visual gesture drives audio parameters. Users draw paths through a sound file and the path controls grain selection.
- **Key Algorithm:** 2D trajectory-to-grain-parameter mapping. XY position maps to grain start position and playback speed.
- **Plugin Potential:** HIGH for cross-modal experiments. The "draw a shape, hear a sound" paradigm could become a unique plugin interface.

### PySoundConcat
- **URL:** https://github.com/Pezz89/PySoundConcat
- **Stack:** Python, librosa, numpy, scipy
- **What:** Concatenative synthesis driven by audio database analysis. Analyzes a target sound and reconstructs it using grains from a database of source sounds.
- **Why It's Interesting:** Concatenative synthesis is how tools like CataRT (IRCAM) work -- it rebuilds one sound from fragments of other sounds. The audio analysis pipeline (feature extraction, matching, crossfading) is directly applicable to creative audio tools.
- **Key Algorithm:** Audio feature extraction (MFCCs, spectral centroid), nearest-neighbor grain matching, overlap-add crossfading.
- **Plugin Potential:** MEDIUM. A concatenative synthesis engine could be a unique plugin offering. "Feed it drums, it rebuilds your vocal from drum fragments."

---

## 2. librosa Creative Applications

### Spotify basic-pitch
- **URL:** https://github.com/spotify/basic-pitch
- **Stack:** librosa, TensorFlow/TFLite, numpy
- **What:** Lightweight neural network for Automatic Music Transcription (AMT). Converts audio to MIDI with pitch bend detection. Instrument-agnostic and handles polyphonic input.
- **Why It's Interesting:** Audio-to-MIDI is the bridge between audio and MIDI worlds. This is production-quality (used at Spotify), runs on lightweight hardware, and handles polyphony -- most open-source solutions only handle monophonic input.
- **Key Algorithm:** Neural AMT model trained on polyphonic music. Outputs MIDI notes with onset/offset times, pitch, velocity, and pitch bend.
- **Plugin Potential:** HIGH. Audio-to-MIDI inside a plugin would be transformative. Feed audio in, get MIDI out to control synths, lights, visuals, other effects.

### audio_to_midi_melodia
- **URL:** https://github.com/justinsalamon/audio_to_midi_melodia
- **Stack:** librosa, numpy, vamp (Melodia plugin)
- **What:** Extracts continuous fundamental frequency of the melody from polyphonic recordings using the Melodia melody extraction algorithm. Outputs MIDI.
- **Why It's Interesting:** Melodia is one of the most cited melody extraction algorithms in MIR. This bridges the gap between music analysis research and practical creative tools. Can extract a vocal melody from a full mix.
- **Key Algorithm:** Melodia pitch tracking with salience function, contour extraction, and melody selection. Uses harmonic summation in the frequency domain.
- **Plugin Potential:** HIGH. Melody extraction from a mix could drive harmony generation, auto-accompaniment, or visualization.

### librosa HPSS (Harmonic-Percussive Source Separation)
- **URL:** https://librosa.org/doc/main/generated/librosa.decompose.hpss.html
- **Stack:** librosa, numpy, scipy
- **What:** Built-in librosa function that separates audio into harmonic (pitched) and percussive (transient) components using median filtering on the spectrogram.
- **Why It's Interesting:** Simple but powerful -- one function call splits any audio into melody vs. rhythm. Creative remixing potential: apply different effects to harmonic and percussive components independently. Swap the percussive layer of one song with another.
- **Key Algorithm:** Median filtering along time and frequency axes of the STFT magnitude. Harmonic content has horizontal continuity in the spectrogram; percussive content has vertical continuity. Soft masking for cleaner separation.
- **Plugin Potential:** HIGH. A real-time HPSS plugin could let users independently EQ, compress, or effect the harmonic and percussive layers of any input. Novel mixing tool.

### aubio
- **URL:** https://github.com/aubio/aubio
- **Stack:** C with Python bindings, numpy
- **What:** Library for audio labelling: onset detection, pitch tracking, beat/tempo tracking, MFCC extraction. Written in C for speed, with clean Python API.
- **Why It's Interesting:** Multiple onset detection methods (energy, HFC, complex domain, phase, spectral flux, KL divergence). Multiple pitch detection methods (YIN, YINfast, fcomb, mcomb, schmitt, specacf). Battle-tested in real-time applications. The C core means these algorithms can run in real-time inside a plugin.
- **Key Algorithm:** Spectral flux onset detection, YIN pitch tracking, beat tracking with dynamic programming.
- **Plugin Potential:** HIGH. Onset detection drives beat-reactive effects. Pitch tracking enables auto-tune or pitch-following effects. Beat tracking enables tempo-synced effects.

### audioFlux
- **URL:** https://github.com/libAudioFlux/audioFlux
- **Stack:** C core with Python bindings, numpy
- **What:** High-performance audio analysis library supporting dozens of time-frequency transforms: CQT, VQT, S-Transform, Fast S-Transform, DWT, WPT, SWT, and hundreds of feature combinations.
- **Why It's Interesting:** Goes far beyond standard FFT/STFT. The Constant-Q Transform (CQT) maps directly to musical pitch. The Variable-Q Transform allows different frequency resolutions at different frequency ranges. Wavelet transforms provide multi-resolution analysis.
- **Key Algorithm:** CQT (logarithmic frequency resolution matching musical intervals), VQT (variable resolution), wavelet decomposition (DWT/SWT/WPT).
- **Plugin Potential:** MEDIUM. The analysis capabilities could drive sophisticated audio-reactive visual systems or adaptive effects that respond to musical content.

---

## 3. scipy.signal Creative Uses

### Hilbert Transform Frequency Shifter
- **URL:** https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.hilbert.html
- **Stack:** scipy.signal, numpy
- **What:** Using `scipy.signal.hilbert()` to create a frequency shifter effect. The Hilbert transform produces the analytic signal (complex-valued), which enables single-sideband modulation -- shifting all frequencies by a constant amount.
- **Why It's Interesting:** Frequency shifting (not pitch shifting) is a classic studio effect that creates inharmonic, metallic, bell-like tones. Unlike pitch shifting, it breaks harmonic relationships. Used extensively by Stockhausen and in experimental electronic music. Ring modulation is a simpler cousin -- frequency shifting is the sophisticated version.
- **Key Algorithm:** Hilbert transform to get analytic signal -> multiply by complex exponential `e^(j*2*pi*f_shift*t)` -> take real part. The Hilbert transform is implemented via FFT: zero out negative frequencies, inverse FFT.
- **Plugin Potential:** HIGH. A frequency shifter plugin with wet/dry mix, LFO modulation of shift amount, and feedback path would be a unique creative tool. Few plugins implement true frequency shifting well.

### Convolution with Unusual Impulse Responses
- **URL:** (technique, not single project)
- **Stack:** scipy.signal.fftconvolve, numpy, soundfile
- **What:** Convolving audio with non-traditional impulse responses: other audio files, noise bursts, synthesized waveforms, recordings of objects being struck, even image data converted to audio.
- **Why It's Interesting:** Convolution reverb uses room IRs. But convolving with a cymbal crash imprints the cymbal's resonant character onto any sound. Convolving speech with a piano note makes the piano "speak." Convolving two different songs creates ghostly hybrid textures.
- **Key Algorithm:** `scipy.signal.fftconvolve(signal_a, signal_b, mode='full')`. FFT-based convolution: FFT both signals, multiply spectra, inverse FFT. O(n log n) vs O(n^2) for direct convolution.
- **Plugin Potential:** HIGH. A "creative convolution" plugin where users load any audio as the IR. Not just rooms -- convolve with textures, instruments, noise. Add pre-delay, decay envelope, and wet/dry.

### Morphing Filter Design
- **URL:** (technique using scipy.signal.butter, cheby1, ellip, etc.)
- **Stack:** scipy.signal, numpy
- **What:** Designing unusual filter shapes by interpolating between different filter types (Butterworth, Chebyshev, Elliptic), morphing cutoff frequencies, or creating multi-peak resonant filters by combining bandpass filters.
- **Why It's Interesting:** Standard plugin filters are boring (LP/HP/BP/Notch). Morphing between filter types creates evolving, organic timbral changes. Stacking multiple resonant bandpass filters at harmonic intervals creates vowel-like formant filtering.
- **Key Algorithm:** `scipy.signal.sosfilt()` for cascaded second-order sections. Cross-fade between filter coefficient sets for morphing. Parallel bandpass filters at formant frequencies (F1, F2, F3) for vowel synthesis.
- **Plugin Potential:** HIGH. A morphable filter plugin with XY pad control (X = filter type morph, Y = resonance) would be unique. Formant filter for "talking" effects.

### Spectral Analysis for Sonification
- **URL:** (technique)
- **Stack:** scipy.signal.spectrogram, scipy.signal.stft, numpy
- **What:** Using `scipy.signal.spectrogram()` and `scipy.signal.stft()` to analyze audio and then re-synthesize or sonify the spectral data in creative ways -- mapping frequency bins to MIDI notes, using spectral energy to drive parameters, or resynthesizing with modified phase.
- **Why It's Interesting:** The spectrogram is a 2D image (time x frequency). You can manipulate it like an image: blur it, threshold it, rotate it, apply edge detection -- then resynthesize. Image processing on spectrograms is a powerful creative technique.
- **Key Algorithm:** STFT -> spectral manipulation (masking, blurring, morphing) -> ISTFT. Phase reconstruction via Griffin-Lim algorithm when phase is lost.
- **Plugin Potential:** MEDIUM. Spectral manipulation effects (spectral blur, spectral gate, spectral morph) are used in tools like iZotope and could be implemented as plugins.

---

## 4. Sound Art and Experimental Audio

### sonipy
- **URL:** https://github.com/lockepatton/sonipy
- **Stack:** numpy, scipy, soundfile
- **What:** Turns scatter plots into perceptually uniform sound files. Developed as part of TransientZoo, a citizen science program allowing blind and visually impaired participants to classify supernova lightcurves using sound.
- **Why It's Interesting:** Data-to-sound mapping with perceptual uniformity -- meaning equal changes in data produce equal perceived changes in sound. This is the gold standard for sonification. The accessibility angle is powerful.
- **Key Algorithm:** Perceptually uniform frequency mapping (logarithmic pitch scaling), amplitude mapping, temporal mapping of data points.
- **Plugin Potential:** LOW for plugins, HIGH for cross-modal tools. The data-to-audio mapping techniques could drive visual-to-audio conversion in glitch art tools.

### Astronify
- **URL:** https://astronify.readthedocs.io/
- **Stack:** numpy, astropy, pyo
- **What:** Open-source Python package from MAST (Mikulski Archive for Space Telescopes) for sonifying astronomical data. Maps one axis to time, another to pitch.
- **Why It's Interesting:** Built by NASA-affiliated researchers. Clean architecture for mapping arbitrary data dimensions to audio parameters. The mapping strategies (linear, logarithmic, exponential) are well-documented and transferable to any sonification project.
- **Key Algorithm:** Configurable parameter mapping: data value -> MIDI note (pitch), data density -> note duration, data category -> timbre selection.
- **Plugin Potential:** LOW for plugins, HIGH for creative tools. The parameter mapping framework is reusable for any data-driven audio project.

### STRAUSS (Sonification Tools and Resources for Analysis Using Sound Synthesis)
- **URL:** https://github.com/james-trayford/strauss
- **Stack:** numpy, scipy, pyo
- **What:** Python package for scientific sonification. Converts data to sound with support for multiple mapping strategies, spatialization, and both musical and non-musical output modes.
- **Why It's Interesting:** Supports spatial audio (positioning sounds in 3D space based on data coordinates). Multiple sonification modes: audification (direct data-to-waveform), parameter mapping (data controls synth params), and musical sonification (data drives melodic/rhythmic patterns).
- **Key Algorithm:** Multi-dimensional parameter mapping with spatialization. Data coordinates map to azimuth/elevation for spatial positioning.
- **Plugin Potential:** MEDIUM. The spatialization techniques could inform surround/immersive audio plugin design.

### sci-sonify
- **URL:** https://github.com/philipc2/sci-sonify
- **Stack:** numpy, pandas, xarray
- **What:** Converts data from Scientific Python Ecosystem (NumPy, Pandas, Xarray) into musical notes. Simple API for quick sonification of any dataset.
- **Why It's Interesting:** Bridges data science and audio directly. Feed it a Pandas DataFrame and hear your data. The simplicity of the API is a design lesson -- making complex things accessible.
- **Key Algorithm:** Value-to-pitch mapping with configurable scales (chromatic, major, minor, pentatonic). Temporal mapping with configurable BPM.
- **Plugin Potential:** LOW for plugins, MEDIUM for creative tools. The scale-quantized mapping is useful for any generative music system.

### AudioLazy
- **URL:** https://pypi.org/project/audiolazy/
- **Stack:** Pure Python (no dependencies for core), optional numpy
- **What:** Real-time audio DSP using lazy evaluation. Infinite audio streams processed sample-by-sample without loading entire files into memory. Includes Z-transform based filter design, LPC analysis, and real-time processing.
- **Why It's Interesting:** Lazy evaluation for audio is a paradigm shift -- process infinite streams with finite memory. The Z-transform filter design API lets you express filters as mathematical transfer functions: `H(z) = (1 - z^-1) / (1 - 0.5*z^-1)`. This maps directly to how DSP textbooks describe filters.
- **Key Algorithm:** Z-transform filter creation, LPC (Linear Predictive Coding) analysis/synthesis, lazy stream processing with operator overloading.
- **Plugin Potential:** MEDIUM. The Z-transform filter design approach is educational -- understanding transfer functions helps design better JUCE filters. LPC is used in vocoder effects.

---

## 5. Audio + MIDI Creative Tools

### isobar
- **URL:** https://github.com/ideoforms/isobar
- **Stack:** Python, mido (MIDI), numpy (optional)
- **What:** Python library for creating and manipulating musical patterns. Generates MIDI events, MIDI files, OSC messages. Includes Euclidean rhythms, L-systems, Markov chains, arpeggiators, and probability-weighted pattern generators.
- **Why It's Interesting:** The most comprehensive algorithmic composition library in Python. Euclidean rhythms (distributing N pulses across M steps as evenly as possible) are used everywhere in electronic music. L-systems generate fractal-like recursive patterns. Markov chains create statistically-derived melodies from training data.
- **Key Algorithm:** Euclidean rhythm generator (Bjorklund's algorithm), L-system pattern expansion, Markov chain sequence generation, probability-weighted note selection.
- **Plugin Potential:** HIGH. A MIDI effect plugin that generates Euclidean rhythms, Markov melodies, or L-system patterns would be a unique offering. MIDI effect plugins are underserved in the market.

### FoxDot
- **URL:** https://github.com/Qirky/FoxDot
- **Stack:** Python, SuperCollider (audio engine), OSC
- **What:** Python-driven live coding environment. Write Python code that generates music in real-time via SuperCollider. Pattern-based syntax for defining melodies, rhythms, and effects.
- **Why It's Interesting:** Live coding is performance art meets programming. FoxDot's pattern syntax is elegant: `p1 >> pluck([0,1,2,3], dur=[1,0.5,0.5])` creates a plucked pattern. The real-time feedback loop (change code, hear result immediately) is the ideal creative workflow.
- **Key Algorithm:** Pattern scheduling system with clock synchronization. OSC message generation for SuperCollider control. Pattern transformations (reverse, shuffle, rotate, mirror).
- **Plugin Potential:** LOW for direct plugin, HIGH for workflow inspiration. The pattern syntax could inspire a "pattern programming" interface for a generative MIDI plugin.

### mido
- **URL:** https://github.com/mido/mido
- **Stack:** Pure Python
- **What:** Low-level MIDI library for Python. Full support for reading, writing, creating, and playing MIDI files. Access every message including all meta messages. Real-time MIDI I/O via PortMidi or rtmidi backends.
- **Why It's Interesting:** Foundation library -- every Python MIDI project uses mido or python-midi underneath. Understanding MIDI at the message level (note_on, note_off, control_change, pitch_bend) is essential for building MIDI-capable plugins.
- **Key Algorithm:** MIDI message parsing and generation, MIDI file format I/O, real-time MIDI port management.
- **Plugin Potential:** MEDIUM. Essential for prototyping any MIDI-related plugin feature in Python before porting to JUCE.

### python-generative-music
- **URL:** https://github.com/oscgonfer/python-generative-music
- **Stack:** Python, mido, FluidSynth (MIDI playback)
- **What:** Builds Markov chains from MIDI files and uses them to generate endless generative music. Instructions generated from MIDI converted to JSON, then played through FluidSynth.
- **Why It's Interesting:** Clean implementation of the Markov chain approach to generative music. Feed it a MIDI file of Bach, it generates infinite "Bach-like" music. The transition probabilities capture the statistical structure of the input music.
- **Key Algorithm:** First-order Markov chain on MIDI note sequences. Transition probability matrix built from training MIDI. Random walk through state space generates new sequences.
- **Plugin Potential:** MEDIUM. A plugin that "learns" from incoming MIDI and generates variations would be novel. Feed it a loop, it generates endless variations.

### audio2midi (ZZWaang)
- **URL:** https://github.com/ZZWaang/audio2midi
- **Stack:** PyTorch, librosa, numpy
- **What:** Audio-to-symbolic generative model that transfers input audio to its piano arrangement in MIDI. Preserves chord, groove, and lead melody while converting to piano representation.
- **Why It's Interesting:** Not just transcription -- it's creative interpretation. Converts any audio (vocals, full mix, drum loops) into a piano arrangement that captures the musical essence. This is AI-assisted arranging.
- **Key Algorithm:** Neural audio-to-symbolic model with separate modules for chord recognition, groove extraction, and melody transcription.
- **Plugin Potential:** HIGH. "Audio to Piano" as a plugin or tool would be useful for songwriters who want to quickly sketch arrangements from recordings.

---

## 6. DSP Algorithm Implementations

### stftPitchShift
- **URL:** https://github.com/jurihock/stftPitchShift
- **Stack:** C++ and Python, numpy, scipy
- **What:** STFT-based real-time pitch and timbre shifting. The Vocoder module transforms DFT complex values into magnitude/frequency representation, then resamples according to desired pitch shift factor. Available as both C++ library and Python package.
- **Why It's Interesting:** Dual C++/Python implementation means you can prototype in Python and reference the C++ when porting to JUCE. Real-time capable. Proper phase vocoder with phase unwrapping and accumulation.
- **Key Algorithm:** Phase vocoder: STFT -> phase unwrapping -> magnitude/frequency interpolation for pitch shift -> phase accumulation -> ISTFT. Overlap-add with Hann windowing.
- **Plugin Potential:** HIGH. Pitch shifting is a core effect. The dual C++/Python codebase is ideal for our workflow (prototype in Python, build in JUCE).

### pvc (Phase Vocoder with Formant Correction)
- **URL:** https://github.com/lewark/pvc
- **Stack:** Python, numpy, scipy
- **What:** Phase vocoder that does independent pitch shifting with optional formant correction. Time-stretching and pitch-shifting of audio files.
- **Why It's Interesting:** Formant correction is what separates good pitch shifters from bad ones. Without it, pitched-up vocals sound like chipmunks. This implementation shows how to preserve vocal formant structure while shifting pitch -- critical for any vocal processing plugin.
- **Key Algorithm:** STFT-based pitch shifting with spectral envelope estimation (via cepstral analysis) for formant preservation. Separate pitch and formant manipulation.
- **Plugin Potential:** HIGH. Pitch shifting with formant control is a premium plugin feature (see Soundtoys Little AlterBoy, Antares Throat).

### Karplus-Strong Implementations
- **URL:** https://github.com/topics/karplus-strong (multiple projects)
- **Stack:** numpy, scipy, soundfile
- **What:** Physical modeling synthesis using a delay line with filtered feedback. Simulates plucked strings, drums, and other physically-resonant sounds. The delay length determines the pitch; the filter determines the decay character.
- **Why It's Interesting:** Simplest form of physical modeling -- just a delay line and a lowpass filter. Yet it produces remarkably realistic plucked string sounds. The algorithm maps directly to standard DSP building blocks available in JUCE. Extensions: add nonlinear feedback for distorted strings, modulate delay length for vibrato, use different excitation signals.
- **Key Algorithm:** Noise burst -> delay line (length = sample_rate / frequency) -> averaging filter (average adjacent samples) -> feedback to delay input. The averaging filter simulates energy loss in a vibrating string.
- **Plugin Potential:** HIGH. A Karplus-Strong synth plugin with extended controls (excitation type, filter shape, feedback amount, body resonance) is a viable product. Physical modeling synths command premium prices.

### Schroeder/Freeverb Reverb Networks
- **URL:** (multiple implementations, reference: https://ccrma.stanford.edu/~jos/pasp/Freeverb.html)
- **Stack:** numpy, scipy
- **What:** Classic reverb algorithm: parallel comb filters feeding into series allpass filters. Freeverb uses 8 comb filters + 4 allpass filters with specific tuned delay lengths.
- **Why It's Interesting:** Understanding Schroeder reverb is foundational for all reverb design. The specific delay lengths, damping coefficients, and allpass diffusion stages determine the reverb character. Modifying these parameters creates different room types, from small rooms to infinite drones.
- **Key Algorithm:** 8 parallel comb filters (with lowpass feedback) -> 4 series allpass filters. Each comb filter: `y[n] = x[n-M] + g * y[n-M]` where M is delay length, g is feedback. Allpass: `y[n] = -g*x[n] + x[n-M] + g*y[n-M]`.
- **Plugin Potential:** HIGH. Reverb is a fundamental plugin category. Understanding the internals enables creating custom reverb characters rather than using generic algorithms.

### Waveshaping / Unusual Distortion Curves
- **URL:** https://github.com/Metallicode/python_audio_dsp (effects module), https://www.musicdsp.org/
- **Stack:** numpy, scipy
- **What:** Non-standard distortion implementations: asymmetric waveshaping (different curves for positive and negative signal), foldback distortion (signal folds back on itself at threshold), polynomial waveshaping, and tube simulation using tanh + DC offset.
- **Why It's Interesting:** Standard `tanh()` distortion is overused. Asymmetric waveshaping generates even harmonics (warmer, tube-like). Foldback distortion creates complex, evolving timbres. Using envelope follower output as DC offset to the waveshaper creates dynamic, input-responsive distortion character.
- **Key Algorithm:** Asymmetric: different transfer functions for x > 0 and x < 0. Foldback: `y = abs(abs(fmod(x-threshold, 4*threshold) - 2*threshold) - threshold)`. Tube sim: `tanh(gain * (x + dc_offset))` where dc_offset from envelope follower.
- **Plugin Potential:** HIGH. Distortion/saturation is a huge market. A plugin with multiple selectable waveshaping curves including foldback and asymmetric modes would stand out. Sidechain Operator could incorporate dynamic waveshaping.

---

## 7. Neural Audio Projects

### RAVE (Real-time Audio Variational autoEncoder)
- **URL:** https://github.com/acids-ircam/RAVE
- **Stack:** PyTorch, numpy, torchaudio
- **What:** Variational autoencoder for fast, high-quality neural audio synthesis. Generates 48kHz audio at 20x real-time on a laptop CPU. Two-stage training: representation learning then adversarial fine-tuning. Enables timbre transfer (make a violin sound like a saxophone while preserving the performance).
- **Why It's Interesting:** Real-time neural audio is here. RAVE can run inside a DAW via the RAVE VST plugin. The timbre transfer capability is mind-blowing -- play any instrument and have it sound like any other instrument in real-time. Pre-trained models available for guitar, saxophone, church organ, and more.
- **Key Algorithm:** Variational autoencoder with multi-band decomposition. Encoder compresses audio to latent space, decoder reconstructs. Latent space manipulation enables timbre transfer, interpolation between sounds, and generation of new timbres.
- **Plugin Potential:** HIGH. RAVE already has a VST plugin (beta). Understanding the architecture informs what neural audio effects are possible. The latent space manipulation concept could inspire unique plugin interfaces.

### DDSP (Differentiable Digital Signal Processing)
- **URL:** https://github.com/magenta/ddsp
- **Stack:** TensorFlow, numpy, scipy
- **What:** Google Magenta library combining classical DSP with deep learning. Neural networks learn to control synthesizer parameters (oscillator frequencies, filter coefficients, reverb settings) rather than generating raw audio. The synth components are differentiable, so the whole system trains end-to-end.
- **Why It's Interesting:** Bridges neural networks and traditional DSP. Instead of a black-box neural network generating audio, DDSP uses neural networks to control interpretable synth parameters. This means you can extract the learned parameters and implement them in a traditional DSP plugin.
- **Key Algorithm:** Harmonic additive synthesizer + filtered noise synthesizer, controlled by neural network. The network outputs: fundamental frequency, harmonic amplitudes, noise filter magnitudes, and reverb IR. All components are differentiable for end-to-end training.
- **Plugin Potential:** HIGH. The DDSP architecture could be used to create "AI-assisted" plugins where a neural network suggests synth parameters. Train on a corpus of sounds, then the network can "dial in" any sound from that corpus.

### Neural Amp Modeler (NAM)
- **URL:** https://github.com/sdatkinson/neural-amp-modeler
- **Stack:** PyTorch, numpy
- **What:** Uses deep learning to create highly accurate models of guitar amplifiers and pedals. Record your amp with a standardized test signal, train a neural network, get a digital clone that runs in real-time as a VST plugin.
- **Why It's Interesting:** State-of-the-art accuracy for amp modeling. The companion NeuralAmpModelerPlugin runs these models as VST3/AU plugins. Community has created hundreds of models of famous amps and pedals. Shows the full pipeline from training to plugin deployment.
- **Key Algorithm:** Recurrent neural networks (LSTMs, GRUs) and WaveNet-style temporal convolutional networks trained on input/output audio pairs from real hardware.
- **Plugin Potential:** HIGH. Direct inspiration for building neural-modeled effects. The training pipeline could be adapted to model any audio hardware (compressors, EQs, tape machines), not just guitar amps.

### Demucs / HTDemucs (Meta)
- **URL:** https://github.com/facebookresearch/demucs (likely location)
- **Stack:** PyTorch, torchaudio, numpy
- **What:** State-of-the-art music source separation. Separates any song into 4 stems: vocals, drums, bass, other. HTDemucs is the hybrid transformer version with improved quality.
- **Why It's Interesting:** Best-in-class source separation. Works on any music, no training required (pre-trained models provided). The separation quality is good enough for creative remixing. Enables "unmixing" a finished song into components.
- **Key Algorithm:** Hybrid architecture: U-Net for waveform processing + transformer for spectrogram processing. Both branches are merged for final separation. Cross-attention between time-domain and frequency-domain representations.
- **Plugin Potential:** HIGH. Real-time source separation in a plugin would be revolutionary for DJs, producers, and remix artists. Even partial separation (just isolating vocals) is commercially valuable.

### Open-Unmix
- **URL:** https://github.com/sigsep/open-unmix-pytorch
- **Stack:** PyTorch, numpy, torchaudio
- **What:** Reference implementation for music source separation. Three-layer bidirectional LSTM that predicts target source magnitude spectrogram from mixture spectrogram. Separates into vocals, drums, bass, other.
- **Why It's Interesting:** Simpler architecture than Demucs -- easier to understand and modify. Pre-trained models available (umxl is the best). The mask-based approach (predict a soft mask, apply to mixture spectrogram) is a fundamental technique applicable to many spectral processing tasks.
- **Key Algorithm:** Bi-LSTM on magnitude spectrogram -> soft mask prediction -> Wiener filtering for final separation. Mean squared error loss in magnitude domain.
- **Plugin Potential:** MEDIUM. Lighter weight than Demucs, potentially easier to run in real-time. The mask-based spectral processing approach is broadly useful.

### Spleeter (Deezer)
- **URL:** https://github.com/deezer/spleeter (likely location)
- **Stack:** TensorFlow, librosa, numpy
- **What:** Audio source separation library with pre-trained models for 2-stem (vocals/accompaniment), 4-stem (vocals/drums/bass/other), and 5-stem separation. One of the first widely-used ML source separation tools.
- **Why It's Interesting:** Pioneer of accessible ML source separation. While Demucs has surpassed it in quality, Spleeter's architecture is simpler and well-documented. Good for learning the fundamentals of neural source separation.
- **Key Algorithm:** U-Net architecture on spectrograms. Encoder-decoder with skip connections. Predicts soft masks for each source.
- **Plugin Potential:** MEDIUM. Useful for understanding source separation architectals, but Demucs is the current state-of-the-art.

### AudioCraft / MusicGen (Meta)
- **URL:** https://github.com/facebookresearch/audiocraft
- **Stack:** PyTorch, torchaudio, numpy
- **What:** Meta's audio generation library. MusicGen generates music from text descriptions ("epic orchestral battle music") or melodic conditioning (hum a melody, get a full arrangement). EnCodec provides neural audio compression. AudioGen generates sound effects from text.
- **Why It's Interesting:** Text-to-music is here and it is good. MusicGen trained on 20K hours of licensed music. Melodic conditioning means you can hum an idea and get a produced version. EnCodec's neural compression achieves high quality at very low bitrates -- useful for understanding learned audio representations.
- **Key Algorithm:** Auto-regressive transformer over EnCodec tokens. EnCodec compresses 32kHz audio to discrete tokens at 50Hz with 4 codebooks. MusicGen uses a single-stage transformer with delay pattern for parallel codebook generation.
- **Plugin Potential:** LOW for direct plugin (too heavy for real-time), HIGH for creative workflow tools. "Generate a backing track from a text description" or "generate variations of this melody" as studio tools.

### RVC (Retrieval-based Voice Conversion)
- **URL:** https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
- **Stack:** PyTorch, numpy, librosa, faiss
- **What:** Voice conversion system that can change any voice to sound like a target voice. Train on as little as 10 minutes of target voice data. Supports both speech and singing. Uses HuBERT for content extraction, FAISS for retrieval, and a neural vocoder for synthesis.
- **Why It's Interesting:** State-of-the-art voice conversion with minimal training data. The singing support with auto-tune makes it directly applicable to music production. The architecture (content extraction -> retrieval -> synthesis) is a general pattern for any "style transfer" system.
- **Key Algorithm:** HuBERT content feature extraction -> FAISS nearest-neighbor retrieval from target voice database -> neural vocoder (HiFi-GAN) for waveform synthesis. Optional pitch guidance for singing.
- **Plugin Potential:** MEDIUM. Real-time voice conversion as a plugin would be powerful for vocalists. The architecture is too heavy for current real-time use but getting closer.

### Seed-VC (Zero-shot Voice Conversion)
- **URL:** https://github.com/Plachtaa/seed-vc
- **Stack:** PyTorch, numpy
- **What:** Zero-shot voice conversion -- convert to any target voice without training, just provide a reference audio clip. Supports both speech and singing.
- **Why It's Interesting:** Zero-shot means no per-voice training needed. Provide a 5-second clip of anyone's voice, and it can convert your voice to sound like them in real-time. This is the future of voice effects.
- **Key Algorithm:** Self-supervised speech representations + diffusion-based vocoder. Speaker embedding from reference audio guides the conversion.
- **Plugin Potential:** MEDIUM. When real-time performance improves, this becomes a killer plugin: "sing like anyone" in real-time.

---

## 8. Real-Time Audio in Python

### pyo
- **URL:** https://github.com/belangeo/pyo
- **Stack:** C core, Python interface, PortAudio
- **What:** Comprehensive Python DSP module for real-time audio synthesis and processing. Includes oscillators, filters, delays, granular, spectral processing, physical modeling, MIDI, and OSC support. Used as the audio engine for SoundGrain and Zyne.
- **Why It's Interesting:** The most complete real-time audio framework in Python. Primitives include: mathematical operations on audio signals, basic signal processing (filters, delays, synthesis generators), and complex algorithms (granulation, spectral processing). Built-in Scope for real-time waveform visualization. Supports Jack, CoreAudio, ASIO.
- **Key Algorithm:** Everything -- pyo is a complete DSP toolkit. Key highlights: granular synthesis engine, phase vocoder, spectral processing, physical modeling (waveguide), feedback delay networks.
- **Plugin Potential:** HIGH for prototyping. Build and test complete audio processing chains in real-time before porting to JUCE. The pyo source code (C) can serve as a reference for JUCE implementations.

### pm_synth
- **URL:** https://github.com/guestdaniel/pm_synth
- **Stack:** Python, numpy, pyo (or PyAudio)
- **What:** Real-time phase modulation / granular synthesizer. Source waveform sampled by grain generator; sum of all active grains produces output. Combines PM synthesis with granular techniques.
- **Why It's Interesting:** Hybrid synthesis: phase modulation (like FM synthesis but with phase instead of frequency) combined with granular processing. This creates textures impossible with either technique alone. The grain generator adds spatial and temporal richness to PM tones.
- **Key Algorithm:** Phase modulation: `y[n] = sin(2*pi*f_c*n + I * sin(2*pi*f_m*n))` where I is modulation index. Granular: window function * time-shifted PM output. Grain cloud management (voice allocation, envelope application).
- **Plugin Potential:** MEDIUM. PM/granular hybrid synthesis is unusual and could be a unique plugin offering.

### sounddevice
- **URL:** https://python-sounddevice.readthedocs.io/
- **Stack:** PortAudio bindings, numpy
- **What:** Python bindings to PortAudio for real-time audio I/O. Callback-based API for low-latency processing. Supports recording, playback, and simultaneous input/output.
- **Why It's Interesting:** The standard way to do real-time audio I/O in Python. The callback architecture mirrors how audio plugins work (process a buffer of samples per callback). Understanding sounddevice callbacks directly prepares you for writing JUCE `processBlock()` methods.
- **Key Algorithm:** Audio callback: `def callback(indata, outdata, frames, time, status)`. Buffer-based processing identical to plugin architecture. Ring buffer patterns for inter-thread communication.
- **Plugin Potential:** HIGH for learning. The callback-based buffer processing is the same paradigm used in JUCE plugins. Prototype effects using sounddevice callbacks, then translate to JUCE processBlock.

### DawDreamer
- **URL:** https://github.com/DBraun/DawDreamer (likely location)
- **Stack:** JUCE (C++ backend), Python bindings, numpy
- **What:** Python DAW -- load VST instruments and effects, render audio offline or in real-time. Can host and automate VST/AU plugins from Python scripts. Uses JUCE internally.
- **Why It's Interesting:** Write Python scripts that act like a DAW: load a synth plugin, send it MIDI, process through effect plugins, render to audio. Built on JUCE, so the audio processing pipeline is production-quality. Excellent for batch processing, automated testing, and parameter space exploration.
- **Key Algorithm:** JUCE AudioProcessorGraph in Python. Plugin loading, parameter automation, MIDI sequencing, and audio rendering via Python API.
- **Plugin Potential:** HIGH for testing. Use DawDreamer to automate testing of your JUCE plugins from Python. Script parameter sweeps, A/B comparisons, and regression tests.

### Make Art with Python (Resonance/Audio Art)
- **URL:** https://www.makeartwithpython.com/
- **Stack:** Python, numpy, scipy, wave module
- **What:** Creative coding tutorials including audio synthesis from scratch (using just wave, math, and array modules), and a project that breaks a wine glass by detecting and playing its resonant frequency.
- **Why It's Interesting:** The "break a wine glass" project demonstrates resonance detection and synthesis: record the glass being tapped, FFT to find the resonant frequency, then generate a pure tone at that frequency with increasing amplitude. Shows the power of even basic DSP.
- **Key Algorithm:** FFT peak detection for resonance finding. Pure tone synthesis at detected frequency. Amplitude ramping to demonstrate resonance buildup.
- **Plugin Potential:** LOW for direct plugin, HIGH for understanding. Resonance detection and exploitation is fundamental to many audio effects (resonant filters, feedback systems, sympathetic resonance simulation).

---

## Cross-Reference: Plugin Potential Summary

### Highest Potential (Direct Plugin Ideas)

| Project | Plugin Concept | Market Category |
|---------|---------------|-----------------|
| stftPitchShift / pvc | Pitch shifter with formant preservation | Vocal Effects |
| Hilbert Frequency Shifter | True frequency shifting with modulation | Creative Effects |
| HPSS (librosa) | Independent harmonic/percussive processing | Mixing Tools |
| Karplus-Strong | Physical modeling string synth | Instruments |
| isobar | Euclidean/Markov/L-system MIDI generator | MIDI Effects |
| NAM architecture | Neural modeling of any analog hardware | Amp/Effect Modeling |
| Demucs approach | Real-time source separation | Mixing/DJ Tools |
| Waveshaping curves | Multi-mode creative distortion | Saturation/Distortion |
| Creative Convolution | Convolve with any audio as IR | Creative Effects |
| basic-pitch | Audio-to-MIDI inside a plugin | Utility/Creative |

### Connections to Existing PRDs

| PRD | Relevant Projects |
|-----|-------------------|
| Sidechain Operator | python_audio_dsp (sidechain compress), aubio (onset detection), dynamic waveshaping |
| Future vocal plugin | pvc (formant correction), RVC, Seed-VC, HPSS, Demucs |
| Future synth plugin | Karplus-Strong, pm_synth, DDSP, SoundGrain (granular), isobar (sequencing) |
| Cross-modal tools | SoundGrain (visual->audio), sonipy (data->audio), librosa (audio->data->visuals) |

---

## Quick-Start Recipes

### Recipe 1: Prototype a Pitch Shifter
```python
# Uses stftPitchShift approach
import numpy as np
from scipy.signal import stft, istft

def pitch_shift(audio, sr, semitones):
    factor = 2 ** (semitones / 12.0)
    f, t, Zxx = stft(audio, fs=sr, nperseg=2048, noverlap=1536)
    # Resample magnitude along frequency axis
    # Phase vocoder accumulation for phase coherence
    # ... (see stftPitchShift for full implementation)
    _, shifted = istft(Zxx_shifted, fs=sr)
    return shifted
```

### Recipe 2: Beat-Reactive Effect
```python
import librosa
import numpy as np

# Load and analyze
y, sr = librosa.load('track.wav')
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
beat_times = librosa.frames_to_time(beats, sr=sr)
# Now beat_times drives your effect parameters
```

### Recipe 3: Harmonic-Percussive Split Processing
```python
import librosa
import numpy as np

y, sr = librosa.load('track.wav')
y_harmonic, y_percussive = librosa.effects.hpss(y)
# Apply different effects to each
# y_harmonic -> reverb, chorus
# y_percussive -> compression, transient shaping
# Recombine with independent level control
```

### Recipe 4: Creative Convolution
```python
from scipy.signal import fftconvolve
import soundfile as sf

audio, sr = sf.read('input.wav')
ir, _ = sf.read('cymbal_hit.wav')  # Use ANY sound as IR
convolved = fftconvolve(audio, ir, mode='full')
convolved = convolved / np.max(np.abs(convolved))  # Normalize
```

### Recipe 5: Frequency Shifter
```python
from scipy.signal import hilbert
import numpy as np

def freq_shift(audio, sr, shift_hz):
    analytic = hilbert(audio)
    t = np.arange(len(audio)) / sr
    shifted = np.real(analytic * np.exp(2j * np.pi * shift_hz * t))
    return shifted
```

---

## Resources and Further Reading

### Essential Libraries (Install All)
```bash
pip install librosa scipy numpy soundfile pydub pedalboard aubio
pip install mido isobar audioflux
pip install torch torchaudio  # For neural projects
```

### Key Documentation
- librosa: https://librosa.org/doc/
- scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
- pedalboard: https://spotify.github.io/pedalboard/
- pyo: https://belangeo.github.io/pyo/
- aubio: https://aubio.org/manual/latest/

### Academic References
- Julius O. Smith, "Physical Audio Signal Processing": https://ccrma.stanford.edu/~jos/pasp/
- musicdsp.org (algorithm cookbook): https://www.musicdsp.org/
- DAFX (Digital Audio Effects) textbook examples
- CCRMA Stanford DSP resources: https://ccrma.stanford.edu/

### Communities
- KVR Audio DSP Forum: https://www.kvraudio.com/forum/
- music-dsp mailing list archives
- r/DSP and r/AudioProgramming on Reddit
- The Audio Programmer (YouTube/Discord)
