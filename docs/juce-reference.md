# JUCE 8 Reference Documentation

> Scraped 2026-02-07. Sources: juce.com, docs.juce.com, github.com/juce-framework/JUCE

---

## JUCE 8 -- What's New

### Major Features

#### WebView UI Support
Cross-platform WebView integration for building plugin interfaces using web frameworks. Provides hardware-accelerated graphics via WebGL. Allows web developers to contribute to audio software UI.

#### Unicode and Text Rendering Overhaul
2+ person-years invested into low-level text rendering. Consistent cross-platform Unicode support including emoji handling.

#### Animation Framework
New animation module with expressive API. Standard easings, hardware refresh rate sync, complex animation graphs.

#### Direct2D Renderer (Windows)
GPU-accelerated rendering via Direct2D. Hardware-backed image support. Significant performance uplift on Windows.

#### AAX SDK Bundled
AAX SDK source now included with JUCE. Reduces setup complexity for Pro Tools plugin development.

### Minimum Requirements (JUCE 8)

| Platform | Requirement |
|----------|-------------|
| C++ Standard | C++17 |
| macOS/iOS | Xcode 12.4+ |
| Windows | Visual Studio 2019+ |
| Linux | g++ 7.0+ or Clang 6.0+ |
| Android | NDK 26 |
| macOS Deploy | 10.11+ |
| Windows Deploy | 10+ |
| iOS Deploy | 12+ |
| Android Deploy | API 21+ |

---

## JUCE DSP Module Reference (`juce_dsp`)

Classes for audio buffer manipulation, digital audio processing, filtering, oversampling, fast math functions.

### Core Containers

| Class | Purpose |
|-------|---------|
| `AudioBlock` | Efficient multi-channel audio data structure |
| `SIMDRegister` | SIMD register abstraction for vectorized ops |

### Filters

| Class | Description |
|-------|-------------|
| `IIR::Filter` | Infinite Impulse Response filter (Transposed Direct Form II) |
| `FIR::Filter` | Finite Impulse Response filter |
| `StateVariableTPTFilter` | TPT-based SVF -- best for fast modulation, 12dB/oct |
| `FirstOrderTPTFilter` | TPT first-order filter |
| `LadderFilter` | Moog-style ladder filter with drive/resonance |
| `LinkwitzRileyFilter` | Crossover filter for multi-way systems |
| `BallisticsFilter` | Envelope follower with attack/release |

### Effects / Processors

| Class | Description |
|-------|-------------|
| `Chorus` | Modulated delay chorus |
| `Compressor` | Dynamic range compressor |
| `Limiter` | Peak amplitude limiter |
| `NoiseGate` | Gate below threshold |
| `Phaser` | Phase-shifting effect |
| `Reverb` | Algorithmic/convolution reverb |
| `WaveShaper` | Nonlinear distortion/waveshaping |
| `Gain` | Volume control with smoothing |
| `Panner` | Stereo panning |
| `Bias` | DC offset control |
| `DryWetMixer` | Blend dry/wet signals |
| `DelayLine` | Configurable delay (None/Linear/Lagrange3rd/Thiran interpolation) |

### Synthesis

| Class | Description |
|-------|-------------|
| `Oscillator` | Wavetable oscillator |

### Frequency Domain

| Class | Description |
|-------|-------------|
| `FFT` | Fast Fourier Transform |
| `Convolution` | Partitioned convolution engine |
| `ConvolutionMessageQueue` | Thread-safe message queue for convolution |
| `WindowingFunction` | Window functions for spectral analysis |

### Oversampling

| Class | Description |
|-------|-------------|
| `Oversampling` | 2x/4x/8x/16x oversampling with FIR or IIR filters |

### Processing Infrastructure

| Class | Description |
|-------|-------------|
| `ProcessSpec` | Sample rate, block size, channel count |
| `ProcessContextReplacing` | In-place processing context |
| `ProcessContextNonReplacing` | Separate I/O buffer context |
| `ProcessorChain` | Serial chain of processors |
| `ProcessorDuplicator` | Mono-to-multichannel duplication |
| `ProcessorWrapper` | Generic processor wrapper |

### Math Utilities

| Class | Description |
|-------|-------------|
| `FastMathApproximations` | Optimized math approximations |
| `LogRampedValue` | Logarithmic parameter ramping |
| `LookupTable` | Fast function evaluation |
| `LookupTableTransform` | Transform via lookup table |
| `Matrix` | Multi-channel matrix ops |
| `Phase` | Phase angle management |
| `Polynomial` | Polynomial evaluation |

### Configuration Macros

| Macro | Purpose |
|-------|---------|
| `JUCE_DSP_ENABLE_SNAP_TO_ZERO` | Denormal suppression |
| `JUCE_DSP_USE_INTEL_MKL` | Intel MKL integration |
| `JUCE_DSP_USE_SHARED_FFTW` | Shared FFTW linking |
| `JUCE_DSP_USE_STATIC_FFTW` | Static FFTW linking |

---

## JUCE Changelog (7.x -- 8.x)

### JUCE 8.0.12
- Visual Studio 2026 default in Projucer
- Fixed Android In-App Purchases compilation

### JUCE 8.0.11
- MIDI 2.0 Universal MIDI Packet demo
- Visual Studio 2026 exporter
- macOS/iOS 26 support
- **VST3 SDK updated to 3.8.0 (MIT license)**
- **AAX SDK updated to 2.9.0**
- ASIO SDK source files included (GPLv3)
- New `juce_audio_processors_headless` module
- Font and glyph cache performance improvements

### JUCE 8.0.10
- Fixed Android Activity restart on theme change
- Fixed iOS screen size in plug-ins
- Fixed LLVM 21 warnings

### JUCE 8.0.9
- Configurable font features (ligatures, kerning)
- macOS/iOS 26 support
- 32-bit int WAV file support
- Fixed MIDI FX AAX on any channel layout
- Accessibility navigation enabled by default

### JUCE 8.0.8
- TextEditor layout improvements
- Text line spacing control
- Direct2D performance improvements

### JUCE 8.0.7
- Unicode/TextEditor performance
- iOS 18 external device sample rate fix
- `MessageManager::callSync` added
- Fixed Ableton window closing crash

### JUCE 8.0.5
- **Windows Arm support**
- Local notifications support
- VST3 parameter migrations support
- VST2 and VST3 MIDI note names

### JUCE 8.0.4
- Simplified singleton creation
- Exact MIDI CC timestamp passthrough
- C++ and JavaScript interoperability fixes

### JUCE 8.0.3
- AAX SDK updated to 2.8.0
- iOS 18 buffer size/sample rate fix

### JUCE 8.0.2
- C++20 and C++23 support
- VST3 SDK updated to 3.7.12
- Windows 11 rounded window corners

### JUCE 8.0.0 (Major Release)
- **Direct2D renderer**
- **WebView-based UI support**
- **Consistent unicode support across platforms**
- **New animation module**
- **Bundled AAX SDK**

### JUCE 7.0.0 (Major Release)
- **ARA (Audio Random Access) SDK support**
- **LV2 plug-in authoring and hosting**
- Default macOS/iOS renderer
- Hardware-synchronized drawing
- Revamped AudioPlayHead
- Improved accessibility

### Key JUCE 7.x Highlights
- 7.0.3: AudioProcessorGraph refactor, threading classes
- 7.0.6: VST3 bundles and moduleinfo.json
- 7.0.8: macOS AudioWorkgroup support, serialisation tools
- 7.0.9: MIDI-CI support
- 7.0.10: FLAC update, Timer fixes, ChildProcessManager

---

## Quick Reference: Linking DSP Module

```cmake
target_link_libraries(MyPlugin
    PRIVATE
        juce::juce_audio_utils
        juce::juce_dsp          # Required for all DSP classes
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)
```

## Quick Reference: ProcessSpec Initialization

```cpp
void prepareToPlay(double sampleRate, int samplesPerBlock) override
{
    juce::dsp::ProcessSpec spec;
    spec.sampleRate = sampleRate;
    spec.maximumBlockSize = static_cast<juce::uint32>(samplesPerBlock);
    spec.numChannels = static_cast<juce::uint32>(getTotalNumOutputChannels());

    // Call prepare on all DSP processors
    myFilter.prepare(spec);
    myGain.prepare(spec);
}
```
