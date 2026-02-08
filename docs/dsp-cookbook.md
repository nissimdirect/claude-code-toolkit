# DSP Cookbook for Audio Plugin Development

> Comprehensive DSP reference covering the algorithms needed for 5 plugin PRDs:
> 1. **Sidechain Operator** -- Sidechain Compression
> 2. **BB Tubes / Saturator** -- Tube Saturation / Waveshaping
> 3. **Decimate** -- Bitcrusher / Sample Rate Reduction
> 4. **Drum Component Detector** -- Transient Detection / Drum Separation
> 5. **Stereo Image Flipper** -- Mid-Side Processing / Stereo Imaging
>
> Plus: Dynamic Range Compression fundamentals (shared across all dynamics plugins).

---

## Table of Contents

1. [Dynamic Range Compression (Foundation)](#1-dynamic-range-compression-foundation)
2. [Sidechain Compression](#2-sidechain-compression)
3. [Tube Saturation / Waveshaping](#3-tube-saturation--waveshaping)
4. [Bitcrusher / Decimation](#4-bitcrusher--decimation)
5. [Transient Detection / Drum Separation](#5-transient-detection--drum-separation)
6. [Mid-Side Processing / Stereo Imaging](#6-mid-side-processing--stereo-imaging)

---

## 1. Dynamic Range Compression (Foundation)

> This section covers the core compression theory shared by the Sidechain Operator and all dynamics plugins.

### Mathematical Foundation

A compressor reduces the dynamic range of a signal by attenuating levels above a threshold.

**Gain Computer** (in dB domain):

```
Input:  x_dB = 20 * log10(|x|)
Output: y_dB

If x_dB < threshold:
    y_dB = x_dB                          (no compression)

If x_dB >= threshold:
    y_dB = threshold + (x_dB - threshold) / ratio

Gain reduction:
    g_dB = y_dB - x_dB
```

**Soft Knee** (smooths the transition around threshold):

```
knee_width = W  (in dB, typically 0-12)
lower_bound = threshold - W/2
upper_bound = threshold + W/2

If x_dB < lower_bound:
    y_dB = x_dB

If lower_bound <= x_dB <= upper_bound:
    y_dB = x_dB + (1/ratio - 1) * (x_dB - threshold + W/2)^2 / (2*W)

If x_dB > upper_bound:
    y_dB = threshold + (x_dB - threshold) / ratio
```

### Signal Flow (Block Diagram)

```
Input ──────────────────────────[Gain Stage]──── Output
         |                           ^
         v                           |
   [Level Detector]──[Gain Computer]─┘
   (Peak or RMS)     (threshold, ratio, knee)
         |
   [Ballistics]
   (attack, release)
         |
   [Makeup Gain]
```

### Level Detection

**Peak Detection** (fast, responsive):
```cpp
float peakDetect(float input) {
    return std::abs(input);  // Rectified absolute value
}
```

**RMS Detection** (smoother, more musical):
```cpp
// Running RMS over a window
float rmsDetect(float input, float& rmsState, float windowCoeff) {
    rmsState = windowCoeff * rmsState + (1.0f - windowCoeff) * (input * input);
    return std::sqrt(rmsState);
}
```

### Attack/Release Ballistics

The envelope follower smooths the detected level using a one-pole filter with different coefficients for attack and release:

```cpp
// Calculate coefficients from time constants
float attackCoeff  = std::exp(-1.0f / (attackTimeMs * 0.001f * sampleRate));
float releaseCoeff = std::exp(-1.0f / (releaseTimeMs * 0.001f * sampleRate));

// Branched smoothing (simple approach)
float smoothLevel(float input, float& state) {
    float coeff;
    if (input > state)
        coeff = attackCoeff;   // Signal rising: use attack
    else
        coeff = releaseCoeff;  // Signal falling: use release

    state = coeff * state + (1.0f - coeff) * input;
    return state;
}
```

**Decoupled detector** (better transient response):
```cpp
// Stage 1: Instantaneous peak follower
float peakState = std::max(input, releaseCoeff * peakState);

// Stage 2: Smooth with attack filter
float smoothState = attackCoeff * smoothState + (1.0f - attackCoeff) * peakState;

// Use the maximum of both
float envelope = std::max(peakState, smoothState);
```

### Key Parameters and Ranges

| Parameter | Typical Range | Unit | Notes |
|-----------|--------------|------|-------|
| Threshold | -60 to 0 | dB | Where compression begins |
| Ratio | 1:1 to inf:1 | ratio | inf:1 = limiter |
| Attack | 0.01 to 200 | ms | How fast gain reduces |
| Release | 5 to 2000 | ms | How fast gain recovers |
| Knee | 0 to 12 | dB | Hard (0) to soft transition |
| Makeup Gain | 0 to 30 | dB | Compensate for level loss |

### Feedforward vs Feedback Topology

| Topology | Sidechain Source | Character | Use For |
|----------|-----------------|-----------|---------|
| **Feedforward** | Input signal | Precise, modern | Transparent compression |
| **Feedback** | Output signal | Musical, vintage | Colored compression |

**Feedforward** (modern, used in most plugins):
```
Input ──[Detector]──[Gain Computer]──[Apply Gain]── Output
```

**Feedback** (vintage, LA-2A style):
```
Input ──[Apply Gain]── Output
              |            |
              └──[Detector]┘
```

### Look-Ahead

Delays the audio path to allow the compressor to react before transients hit:

```cpp
// Delay line for look-ahead (typically 1-10ms)
int lookAheadSamples = (int)(lookAheadMs * 0.001f * sampleRate);
float delayedInput = delayBuffer[readIndex];
delayBuffer[writeIndex] = input;

// Apply gain computed from the NON-delayed signal to the delayed signal
output = delayedInput * gainReduction;
```

### Common Mistakes

1. **Linear domain math**: Always compute gain in dB domain, convert back for multiplication
2. **Denormal numbers**: Add a tiny DC offset (1e-25) to prevent CPU spikes from denormals
3. **No makeup gain**: Compressed signal sounds quieter -- always offer makeup gain
4. **Forgetting latency reporting**: Look-ahead adds latency; report it to the host
5. **Zipper noise**: Smooth gain changes per-sample, not per-block

---

## 2. Sidechain Compression

> For the **Sidechain Operator** plugin.

### Mathematical Foundation

Sidechain compression uses the same gain computer as standard compression, but the **detection signal** comes from a different source than the audio being processed.

```
Main Input ──────────────────────────[Gain Stage]── Output
                                          ^
Sidechain Input ──[Level Detector]──[Gain Computer]─┘
```

The sidechain signal controls the gain applied to the main signal. Classic use: kick drum ducks the bass.

### Signal Flow

```
Main Audio In ──[Delay (look-ahead)]──[Apply Gain]── Output
                                           ^
                                           |
Sidechain In ──[HPF/LPF Filter]──[Detector]──[Ballistics]──[Gain Computer]
                    ^                                              |
                    |                                              v
              [Sidechain Filter]                           [Gain Reduction]
              (shape detection)
```

### Key Parameters and Ranges

| Parameter | Range | Purpose |
|-----------|-------|---------|
| Threshold | -60 to 0 dB | Level where ducking begins |
| Ratio | 1:1 to inf:1 | Amount of ducking |
| Attack | 0.1 to 100 ms | How fast the duck engages |
| Release | 10 to 1000 ms | How fast the duck recovers |
| Sidechain HPF | 20 to 500 Hz | Filter low rumble from detection |
| Sidechain LPF | 1k to 20k Hz | Filter high content from detection |
| Mix (Dry/Wet) | 0 to 100% | Parallel compression |
| Depth | 0 to 100% | Maximum gain reduction amount |

### JUCE Implementation Hints

```cpp
class SidechainProcessor : public juce::AudioProcessor
{
public:
    // Declare buses: main stereo + sidechain mono
    SidechainProcessor()
        : AudioProcessor(BusesProperties()
            .withInput("Input", juce::AudioChannelSet::stereo(), true)
            .withInput("Sidechain", juce::AudioChannelSet::mono(), true)
            .withOutput("Output", juce::AudioChannelSet::stereo(), true))
    {}

    void processBlock(juce::AudioBuffer<float>& buffer,
                      juce::MidiBuffer& midiMessages) override
    {
        auto mainInput  = getBusBuffer(buffer, true, 0);   // Main stereo
        auto scInput    = getBusBuffer(buffer, true, 1);   // Sidechain mono
        auto output     = getBusBuffer(buffer, false, 0);  // Output stereo

        for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
        {
            // 1. Get sidechain level
            float scSample = scInput.getNumChannels() > 0
                ? scInput.getSample(0, sample) : 0.0f;

            // 2. Apply sidechain filter (optional HPF)
            float filteredSC = scHighPass.processSample(scSample);

            // 3. Detect level (peak)
            float scLevel = std::abs(filteredSC);

            // 4. Convert to dB
            float scLevelDb = juce::Decibels::gainToDecibels(scLevel, -100.0f);

            // 5. Gain computer
            float gainReductionDb = computeGain(scLevelDb, threshold, ratio, knee);

            // 6. Smooth with attack/release
            float smoothedGainDb = applyBallistics(gainReductionDb);

            // 7. Convert to linear gain
            float gain = juce::Decibels::decibelsToGain(smoothedGainDb);

            // 8. Apply to main signal
            for (int ch = 0; ch < mainInput.getNumChannels(); ++ch)
            {
                float mainSample = mainInput.getSample(ch, sample);
                output.setSample(ch, sample, mainSample * gain);
            }
        }
    }
};
```

### Common Mistakes

1. **Forgetting sidechain bus declaration**: Must declare the aux input bus in the constructor
2. **Not checking if sidechain is connected**: Always check `scInput.getNumChannels() > 0`
3. **No sidechain filtering**: Unfiltered sidechain responds to all frequencies; HPF at ~80Hz is usually needed
4. **Ignoring the mix control**: Parallel sidechain compression (dry/wet blend) is essential for musicality
5. **Per-block processing**: For smooth gain changes, compute gain per-sample, not per-block

---

## 3. Tube Saturation / Waveshaping

> For the **BB Tubes / Saturator** plugin.

### Mathematical Foundation

Saturation applies a nonlinear transfer function to an audio signal. The transfer function approximates the identity function `y(x) = x` near the origin and gradually tapers at the extremes, simulating how analog circuits soft-clip.

**Key transfer functions:**

| Function | Formula | Character |
|----------|---------|-----------|
| **Tanh** (classic) | `y = tanh(g * x)` | Smooth, symmetrical |
| **Soft clip** | `y = x - x^3/3` (for abs(x) < 1) | Gentle warmth |
| **Hard clip** | `y = clamp(x, -1, 1)` | Harsh, digital |
| **Arctangent** | `y = (2/pi) * atan(g * x)` | Similar to tanh, cheaper |
| **Tube (asymmetric)** | `y = tanh(g * x) + 0.1 * x^2` | Even harmonics (warm) |
| **Exponential** | `y = sign(x) * (1 - exp(-abs(g*x)))` | Aggressive |

### Harmonic Content

| Symmetry | Harmonics Generated | Sound Character |
|----------|-------------------|-----------------|
| **Symmetric** (tanh, atan) | Odd only (3rd, 5th, 7th...) | Bright, edgy |
| **Asymmetric** (tube, tape) | Even + Odd (2nd, 3rd, 4th...) | Warm, musical |

**Tubes produce even harmonics** primarily because triode circuits have an asymmetric transfer curve. To emulate this:

```cpp
// Asymmetric saturation (tube-like)
float tubeSaturate(float x, float drive) {
    float driven = x * drive;

    // Positive half: gentle saturation
    if (driven >= 0.0f)
        return std::tanh(driven);

    // Negative half: harder saturation (asymmetry creates even harmonics)
    return std::tanh(driven * 1.2f) / 1.2f;
}
```

**Alternative -- DC offset method** (simpler):
```cpp
// Add DC offset before symmetric waveshaper, remove after
float tubeSimple(float x, float drive, float bias = 0.1f) {
    float biased = x + bias;              // Introduce asymmetry
    float saturated = std::tanh(drive * biased);
    return saturated - std::tanh(drive * bias);  // Remove DC
}
```

### Signal Flow

```
Input ──[Input Gain/Drive]──[Pre-Filter]──[Oversampling Up]──[Waveshaper]──[Oversampling Down]──[Post-Filter]──[Mix]── Output
                                                                                                                 ^
                                                                                                                 |
                                                                                                          [Dry Signal]
```

### Oversampling (Critical)

Waveshaping creates harmonics above Nyquist, causing aliasing. **Oversampling is essential for quality saturation.**

```cpp
// Using JUCE's built-in oversampler
juce::dsp::Oversampling<float> oversampling(
    2,       // numChannels
    2,       // oversampling order (2^2 = 4x oversampling)
    juce::dsp::Oversampling<float>::filterHalfBandPolyphaseIIR,
    true     // isMaxQuality
);

void processBlock(juce::AudioBuffer<float>& buffer, ...) {
    // Upsample
    auto oversampledBlock = oversampling.processSamplesUp(
        juce::dsp::AudioBlock<float>(buffer));

    // Apply waveshaping at higher sample rate
    for (int ch = 0; ch < oversampledBlock.getNumChannels(); ++ch)
        for (int i = 0; i < oversampledBlock.getNumSamples(); ++i) {
            float sample = oversampledBlock.getSample(ch, i);
            oversampledBlock.setSample(ch, i, waveshape(sample));
        }

    // Downsample (anti-aliasing filter built in)
    oversampling.processSamplesDown(juce::dsp::AudioBlock<float>(buffer));
}
```

**Oversampling quality vs CPU:**

| Factor | Quality | CPU Cost | Use Case |
|--------|---------|----------|----------|
| 2x | Minimum acceptable | Low | Real-time with light saturation |
| 4x | Good | Medium | Most saturation plugins |
| 8x | Excellent | High | Heavy distortion, mastering |
| 16x | Overkill | Very high | Offline rendering only |

### Key Parameters and Ranges

| Parameter | Range | Purpose |
|-----------|-------|---------|
| Drive/Gain | 0 to 48 dB | How hard signal hits the waveshaper |
| Tone | 20 to 20k Hz | Pre/post filter for character |
| Saturation Type | Enum | Tape, Tube, Transistor, etc. |
| Mix (Dry/Wet) | 0 to 100% | Parallel processing |
| Output Level | -inf to 0 dB | Compensate for added energy |
| Bias | -1 to +1 | Asymmetry control (even harmonics) |

### Lookup Table Optimization

For expensive transfer functions, precompute a lookup table:

```cpp
// Build lookup table at initialization
static constexpr int TABLE_SIZE = 4096;
float lut[TABLE_SIZE];

void buildLUT(float drive) {
    for (int i = 0; i < TABLE_SIZE; ++i) {
        float x = 2.0f * (float)i / (TABLE_SIZE - 1) - 1.0f;  // [-1, 1]
        lut[i] = std::tanh(drive * x);
    }
}

// Interpolated lookup during processing
float lutSaturate(float input) {
    float index = (input + 1.0f) * 0.5f * (TABLE_SIZE - 1);
    int i0 = juce::jlimit(0, TABLE_SIZE - 2, (int)index);
    float frac = index - i0;
    return lut[i0] + frac * (lut[i0 + 1] - lut[i0]);  // Linear interpolation
}
```

### Common Mistakes

1. **No oversampling**: Aliasing sounds harsh and digital -- always oversample
2. **Forgetting DC removal**: Asymmetric waveshaping introduces DC offset; add a DC blocker
3. **Level compensation**: Saturation adds energy; compensate output level
4. **Static LUT with variable drive**: Rebuild the LUT when drive changes, or use a 2D table
5. **Ignoring pre-emphasis**: Frequency-dependent saturation (more drive at certain frequencies) sounds more natural

### DC Blocker (Essential for Asymmetric Saturation)

```cpp
class DCBlocker {
    float x1 = 0.0f, y1 = 0.0f;
    float R = 0.995f;  // Cutoff ~7Hz at 44.1kHz
public:
    float process(float input) {
        float output = input - x1 + R * y1;
        x1 = input;
        y1 = output;
        return output;
    }
};
```

---

## 4. Bitcrusher / Decimation

> For the **Decimate** plugin.

### Mathematical Foundation

Bitcrushing degrades audio quality through two independent operations:

1. **Bit Depth Reduction**: Quantizes amplitude to fewer bits
2. **Sample Rate Reduction**: Decimates the temporal resolution

**Bit Depth Reduction**:
```
quantized = round(input * (2^bits - 1)) / (2^bits - 1)
```

**Sample Rate Reduction**:
```
Hold each sample for N periods, where N = originalRate / targetRate
```

### Signal Flow

```
Input ──[Sample Rate Reducer]──[Bit Depth Reducer]──[Anti-Alias Filter (optional)]──[Mix]── Output
              |                        |
         [Hold Counter]          [Quantizer]
         (decimation factor)     (bit depth)
```

### Bit Depth Reduction

Two quantization methods with different character:

**Mid-Riser Quantizer** (no zero crossing, grittier):
```cpp
float midRiser(float input, int bits) {
    float levels = std::pow(2.0f, bits);
    return std::floor(input * levels + 0.5f) / levels;
}
```

**Mid-Tread Quantizer** (has true zero, cleaner):
```cpp
float midTread(float input, int bits) {
    float levels = std::pow(2.0f, bits) - 1.0f;
    return std::round(input * levels) / levels;
}
```

**Continuous bit depth** (for smooth parameter control):
```cpp
float crushBits(float input, float bits) {
    float levels = std::pow(2.0f, bits);
    return std::round(input * levels) / levels;
}
// bits can be any float from 1.0 to 32.0
```

### Sample Rate Reduction

**Simple hold method** (integer decimation):
```cpp
class SampleRateReducer {
    float holdSample = 0.0f;
    float holdCounter = 0.0f;

public:
    float process(float input, float decimationFactor) {
        holdCounter += 1.0f;
        if (holdCounter >= decimationFactor) {
            holdCounter -= decimationFactor;  // Keep fractional part for smooth control
            holdSample = input;
        }
        return holdSample;
    }
};
```

**Fractional decimation** (smoother parameter changes):
```cpp
class FractionalDecimator {
    float phase = 0.0f;
    float lastSample = 0.0f;

public:
    float process(float input, float rate) {
        // rate = 0.0 (no reduction) to 1.0 (max reduction)
        float increment = 1.0f - rate * 0.99f;  // Never fully stop
        phase += increment;

        if (phase >= 1.0f) {
            phase -= 1.0f;
            lastSample = input;
        }
        return lastSample;
    }
};
```

### Key Parameters and Ranges

| Parameter | Range | Purpose |
|-----------|-------|---------|
| Bit Depth | 1 to 32 bits | Quantization depth (float for smooth) |
| Sample Rate | 100 to sampleRate Hz | Target sample rate |
| Dither | On/Off | Add noise to mask quantization |
| Filter | On/Off | Anti-aliasing filter |
| Mix | 0 to 100% | Dry/wet blend |
| Jitter | 0 to 100% | Randomize sample timing |

### JUCE Implementation

```cpp
void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
{
    float bits = *bitDepthParam;        // e.g., 8.0
    float rateReduction = *rateParam;   // e.g., 0.5 (half sample rate)

    for (int ch = 0; ch < buffer.getNumChannels(); ++ch)
    {
        float* data = buffer.getWritePointer(ch);

        for (int i = 0; i < buffer.getNumSamples(); ++i)
        {
            // 1. Sample rate reduction
            float srReduced = sampleReducer[ch].process(data[i], rateReduction);

            // 2. Bit depth reduction
            float levels = std::pow(2.0f, bits);
            float crushed = std::round(srReduced * levels) / levels;

            // 3. Mix
            data[i] = data[i] * (1.0f - mix) + crushed * mix;
        }
    }
}
```

### Optional: Dithering

Adding dither noise before quantization smooths the harshness:

```cpp
float dither(float input, int bits) {
    float levels = std::pow(2.0f, bits);
    // TPDF dither: triangular probability density function
    float noise = (((float)rand() / RAND_MAX) - 0.5f) +
                  (((float)rand() / RAND_MAX) - 0.5f);
    noise /= levels;
    return std::round((input + noise) * levels) / levels;
}
```

### Common Mistakes

1. **Integer-only bit depth**: Allow fractional bit depths for smooth automation
2. **No anti-aliasing**: Sample rate reduction creates aliases; optionally filter
3. **Forgetting channel independence**: Each channel needs its own hold state
4. **No mix control**: Always provide dry/wet for subtle use
5. **Denormals**: Quantization to very low bit depths creates denormal numbers

---

## 5. Transient Detection / Drum Separation

> For the **Drum Component Detector** plugin.

### Mathematical Foundation

Transient detection separates audio into two components:
- **Attack (transient)**: The sharp onset of a sound
- **Sustain (body)**: The resonant/tonal portion after the attack

The core technique: **dual envelope followers** with different time constants.

```
Attack envelope:   fast attack, zero release
Sustain envelope:  zero attack, slow release

Transient signal = fast_envelope - slow_envelope
```

When the fast envelope rises sharply above the slow envelope, a transient is detected.

### Signal Flow (Transient Shaper)

```
Input ──┬──[Fast Envelope (attack detector)]──┐
        |                                       ├──[Difference = Transient CV]──[Attack Gain]──┐
        ├──[Slow Envelope (sustain detector)]──┘                                                ├──[Sum]── Output
        |                                                                                       |
        └──[Delay (to align with CV)]──────────[Sustain Gain]──────────────────────────────────┘
```

### Envelope Followers

**Fast Envelope** (catches transients):
```cpp
class FastEnvelope {
    float state = 0.0f;
    float attackCoeff;   // Very fast: 0.1 - 5ms
    float releaseCoeff;  // Medium: 10 - 50ms

public:
    void setCoeffs(float attackMs, float releaseMs, float sampleRate) {
        attackCoeff = std::exp(-1.0f / (attackMs * 0.001f * sampleRate));
        releaseCoeff = std::exp(-1.0f / (releaseMs * 0.001f * sampleRate));
    }

    float process(float input) {
        float rectified = std::abs(input);
        if (rectified > state)
            state = attackCoeff * state + (1.0f - attackCoeff) * rectified;
        else
            state = releaseCoeff * state + (1.0f - releaseCoeff) * rectified;
        return state;
    }
};
```

**Slow Envelope** (follows the body/sustain):
```cpp
class SlowEnvelope {
    float state = 0.0f;
    float attackCoeff;   // Slow: 20 - 100ms
    float releaseCoeff;  // Slow: 100 - 500ms

public:
    float process(float input) {
        float rectified = std::abs(input);
        if (rectified > state)
            state = attackCoeff * state + (1.0f - attackCoeff) * rectified;
        else
            state = releaseCoeff * state + (1.0f - releaseCoeff) * rectified;
        return state;
    }
};
```

### Transient/Sustain Separation

```cpp
void processBlock(juce::AudioBuffer<float>& buffer, ...) {
    for (int ch = 0; ch < buffer.getNumChannels(); ++ch) {
        float* data = buffer.getWritePointer(ch);

        for (int i = 0; i < buffer.getNumSamples(); ++i) {
            float sample = data[i];

            // Detect envelopes
            float fastEnv = fastFollower[ch].process(sample);
            float slowEnv = slowFollower[ch].process(sample);

            // Transient amount = difference between fast and slow
            float transientCV = juce::jmax(0.0f, fastEnv - slowEnv);

            // Normalize the CV
            float normalizedCV = juce::jlimit(0.0f, 1.0f, transientCV / (slowEnv + 1e-6f));

            // Apply attack and sustain gains
            float attackGain = 1.0f + (attackKnob * normalizedCV);
            float sustainGain = 1.0f + (sustainKnob * (1.0f - normalizedCV));

            // Blend
            data[i] = sample * attackGain * sustainGain;
        }
    }
}
```

### Spectral Approach (Drum Separation)

For separating specific drum components (kick, snare, hats), use **frequency-domain analysis**:

```
Percussive vs Harmonic Separation:
- Harmonic content = horizontal patterns in spectrogram (sustained tones)
- Percussive content = vertical patterns in spectrogram (sharp onsets)

Method: Median filtering on the STFT magnitude spectrogram
- Horizontal median = harmonic mask
- Vertical median = percussive mask
```

**STFT-based separation** (advanced):
```cpp
// 1. Compute STFT of input
// 2. For each frame:
//    - Compute horizontal median (across time) -> harmonic mask
//    - Compute vertical median (across frequency) -> percussive mask
// 3. Apply Wiener filtering:
//    percussive = input * (percussive_mask / (harmonic_mask + percussive_mask))
//    harmonic = input * (harmonic_mask / (harmonic_mask + percussive_mask))
// 4. Inverse STFT
```

### Key Parameters and Ranges

| Parameter | Range | Purpose |
|-----------|-------|---------|
| Attack | -100% to +100% | Boost/cut transient portion |
| Sustain | -100% to +100% | Boost/cut sustain portion |
| Speed/Sensitivity | 0.1 to 50 ms | Detection speed |
| Separation | Smooth to Focused | How sharply attack/sustain split |
| Listen Mode | Full / Attack / Sustain | Solo each component |
| Mix | 0 to 100% | Dry/wet blend |

### Common Mistakes

1. **Envelope too fast**: Causes distortion by riding on individual audio cycles
2. **No smoothing on CV**: Gain modulation clicks without interpolation
3. **Single-band only**: Multi-band transient shaping is far more useful
4. **Ignoring aliasing in fast modulation**: Gain changes at audio rate create intermodulation
5. **Phase issues**: Ensure delay alignment between detection and audio paths
6. **CPU overhead of STFT**: FFT-based methods need careful buffer management

---

## 6. Mid-Side Processing / Stereo Imaging

> For the **Stereo Image Flipper** plugin.

### Mathematical Foundation

Mid-Side (M/S) processing decomposes a stereo signal into center (mid) and edge (side) components.

**Encoding (L/R to M/S)**:
```
M = (L + R) / 2     (sum: center content)
S = (L - R) / 2     (difference: side content)
```

**Decoding (M/S to L/R)**:
```
L = M + S
R = M - S
```

**Alternative with gain compensation** (preserves energy):
```
M = 0.707 * (L + R)     (0.707 = 1/sqrt(2) = -3dB)
S = 0.707 * (L - R)

L = 0.707 * (M + S)
R = 0.707 * (M - S)
```

### Signal Flow

```
L ──┐                                                    ┌── L
    ├──[M/S Encode]──[Mid Gain]──[Mid Processing]──┐     |
    |                                               ├──[M/S Decode]
    ├──[M/S Encode]──[Side Gain]──[Side Processing]┘     |
R ──┘                                                    └── R
```

### Stereo Width Control

**Simple width control** (0 = mono, 1 = normal, 2 = extra wide):
```cpp
void processWidth(float* left, float* right, int numSamples, float width) {
    for (int i = 0; i < numSamples; ++i) {
        float mid  = (left[i] + right[i]) * 0.5f;
        float side = (left[i] - right[i]) * 0.5f;

        // Scale the side channel by width factor
        side *= width;

        // Decode back to L/R
        left[i]  = mid + side;
        right[i] = mid - side;
    }
}
// width = 0.0: mono (side = 0)
// width = 1.0: unchanged
// width = 2.0: double the stereo spread
```

### Stereo Image Flipping

For the Stereo Image Flipper specifically:

```cpp
// Complete L/R swap
void flipStereo(float* left, float* right, int numSamples) {
    for (int i = 0; i < numSamples; ++i) {
        float temp = left[i];
        left[i] = right[i];
        right[i] = temp;
    }
}

// M/S swap (flip the spatial image without changing sides)
void flipMidSide(float* left, float* right, int numSamples) {
    for (int i = 0; i < numSamples; ++i) {
        float mid  = (left[i] + right[i]) * 0.5f;
        float side = (left[i] - right[i]) * 0.5f;

        // Invert the side channel (flips the image)
        side = -side;

        left[i]  = mid + side;
        right[i] = mid - side;
    }
}

// Partial flip with blend control
void partialFlip(float* left, float* right, int numSamples, float amount) {
    // amount: -1.0 = fully flipped, 0.0 = normal, +1.0 = extra wide
    for (int i = 0; i < numSamples; ++i) {
        float mid  = (left[i] + right[i]) * 0.5f;
        float side = (left[i] - right[i]) * 0.5f;

        // Blend between normal and flipped
        side *= (1.0f - 2.0f * std::abs(amount));
        if (amount < 0.0f) side = -side;

        left[i]  = mid + side;
        right[i] = mid - side;
    }
}
```

### Frequency-Dependent Stereo Processing

For more sophisticated stereo manipulation, use **multiband M/S processing**:

```cpp
// Split into frequency bands using crossover filters
// Process each band's M/S independently

void processBand(float* left, float* right, int numSamples,
                 float lowWidth, float midWidth, float highWidth)
{
    // 1. Apply crossover filters to split into 3 bands
    // 2. For each band:
    //    a. Encode to M/S
    //    b. Apply band-specific width
    //    c. Decode back to L/R
    // 3. Sum all bands
}
```

### Correlation Meter

Essential for monitoring stereo image health:

```cpp
class CorrelationMeter {
    float sumLR = 0.0f, sumLL = 0.0f, sumRR = 0.0f;
    float smoothCoeff = 0.999f;

public:
    float process(float left, float right) {
        // Running correlation (smoothed)
        sumLR = smoothCoeff * sumLR + (1.0f - smoothCoeff) * (left * right);
        sumLL = smoothCoeff * sumLL + (1.0f - smoothCoeff) * (left * left);
        sumRR = smoothCoeff * sumRR + (1.0f - smoothCoeff) * (right * right);

        float denom = std::sqrt(sumLL * sumRR);
        if (denom < 1e-10f) return 0.0f;

        return sumLR / denom;
        // +1 = perfect mono, 0 = uncorrelated, -1 = out of phase
    }
};
```

### Key Parameters and Ranges

| Parameter | Range | Purpose |
|-----------|-------|---------|
| Width | 0% to 200% | Stereo image width (100% = normal) |
| Mid Level | -inf to +12 dB | Center content volume |
| Side Level | -inf to +12 dB | Edge content volume |
| Flip | Toggle or continuous | Swap/invert stereo image |
| Pan | -100% to +100% | M/S balance adjustment |
| Low Width | 0% to 200% | Width for low frequencies |
| High Width | 0% to 200% | Width for high frequencies |
| Mono Below | 20 to 500 Hz | Collapse bass to mono |

### Mono Bass (Important for Club/Dance Music)

Collapsing low frequencies to mono prevents phase cancellation on club systems:

```cpp
void monoBass(float* left, float* right, int numSamples, float crossoverFreq) {
    // Low-pass filter for bass extraction
    // High-pass filter for everything above

    for (int i = 0; i < numSamples; ++i) {
        // Extract bass from each channel
        float bassL = lowpass[0].process(left[i]);
        float bassR = lowpass[1].process(right[i]);

        // Extract high content
        float highL = left[i] - bassL;
        float highR = right[i] - bassR;

        // Sum bass to mono
        float bassMono = (bassL + bassR) * 0.5f;

        // Recombine
        left[i]  = bassMono + highL;
        right[i] = bassMono + highR;
    }
}
```

### Common Mistakes

1. **Phase cancellation**: Boosting side too much causes mono compatibility issues
2. **No correlation metering**: Always provide visual feedback on stereo health
3. **Ignoring mono compatibility**: Test with mono button -- many playback systems sum to mono
4. **Bass width**: Wide bass causes problems on PA systems; mono below ~150Hz
5. **Clipping**: M/S processing can increase peak levels; add limiter or auto-gain
6. **No latency-free crossover**: Use linear-phase crossovers for frequency-dependent processing to avoid phase artifacts

---

## General DSP Best Practices

### Denormal Prevention

```cpp
// Add to every feedback loop and IIR filter
static inline float sanitize(float x) {
    // Flush denormals to zero
    return (std::abs(x) < 1e-15f) ? 0.0f : x;
}

// Or use compiler flags
// -ffast-math (GCC/Clang) -- includes flush-to-zero
// /fp:fast (MSVC)
```

### Smoothing Parameter Changes

```cpp
class SmoothedValue {
    float current = 0.0f;
    float target = 0.0f;
    float coeff = 0.999f;

public:
    void setTarget(float newTarget) { target = newTarget; }

    float getNext() {
        current = current + (target - current) * (1.0f - coeff);
        return current;
    }
};
// JUCE provides: juce::SmoothedValue<float, juce::ValueSmoothingTypes::Linear>
```

### Thread-Safe Parameter Access

```cpp
// Use atomics for parameters shared between audio and UI threads
std::atomic<float> gain { 1.0f };

// UI thread
gain.store(newValue, std::memory_order_relaxed);

// Audio thread
float currentGain = gain.load(std::memory_order_relaxed);
```

---

## References

- [Digital Dynamic Range Compressor Design (Giannoulis et al., JAES 2012)](https://www.eecs.qmul.ac.uk/~josh/documents/2012/GiannoulisMassbergReiss-dynamicrangecompression-JAES2012.pdf)
- [CTAGDRC - JUCE Compressor Implementation](https://github.com/p-hlp/CTAGDRC)
- [Musicdsp.org - Simple Compressor Class](https://www.musicdsp.org/en/latest/Effects/204-simple-compressor-class-c.html)
- [Elementary Audio - Distortion, Saturation, Wave Shaping](https://www.elementary.audio/docs/tutorials/distortion-saturation-wave-shaping)
- [Hack Audio - Mid-Side Processing](https://hackaudio.com/digital-signal-processing/stereo-audio/mid-side-processing/)
- [ISMIR 2011 - Transient Detection via STFT](https://ismir2011.ismir.net/papers/PS2-6.pdf)
- [DAFX - Separation of Transient Information](https://www.dafx.de/paper-archive/2001/papers/duxbury.pdf)
- [KVR Forum - Transient Handling](https://www.kvraudio.com/forum/viewtopic.php?t=466276)
- [KVR Forum - Stereo Expander](https://www.kvraudio.com/forum/viewtopic.php?t=212587)
- [KVR Forum - Bitcrushing](https://www.kvraudio.com/forum/viewtopic.php?t=163880)
- [XMOS Audio DSP Library - Compressor Sidechain](https://www.xmos.com/documentation//XM-015103-UG/html/doc/03_dsp_components/stages/gen/compressor_sidechain.html)
