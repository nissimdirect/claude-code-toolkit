# JUCE DSP Cookbook

> Scraped 2026-02-07. Sources: juce.com tutorials, docs.juce.com, JUCE forum, JUCE GitHub examples

---

## Table of Contents
1. [DSP Architecture Patterns](#dsp-architecture-patterns)
2. [Filter Designs](#filter-designs)
3. [Saturation / Waveshaping](#saturation--waveshaping)
4. [Sidechain Compression](#sidechain-compression)
5. [Convolution Reverb](#convolution-reverb)
6. [Oversampling](#oversampling)
7. [Delay Lines](#delay-lines)
8. [LFO Modulation](#lfo-modulation)
9. [Complete Signal Chains](#complete-signal-chains)

---

## DSP Architecture Patterns

### The Three Lifecycle Methods

Every JUCE DSP processor implements:

```cpp
void prepare(const juce::dsp::ProcessSpec& spec);   // Init with sample rate, block size, channels
void process(const ProcessContext& context);          // Process audio block
void reset();                                         // Clear internal state
```

### ProcessSpec Setup (in prepareToPlay)

```cpp
void prepareToPlay(double sampleRate, int samplesPerBlock) override
{
    juce::dsp::ProcessSpec spec;
    spec.sampleRate = sampleRate;
    spec.maximumBlockSize = static_cast<juce::uint32>(samplesPerBlock);
    spec.numChannels = static_cast<juce::uint32>(getTotalNumOutputChannels());

    processorChain.prepare(spec);
}
```

### ProcessorChain Pattern

Chain multiple processors in series using template composition:

```cpp
enum {
    filterIndex,
    gainIndex,
    waveshaperIndex
};

juce::dsp::ProcessorChain<
    juce::dsp::StateVariableTPTFilter<float>,
    juce::dsp::Gain<float>,
    juce::dsp::WaveShaper<float>
> processorChain;

// Access individual processors
auto& filter = processorChain.template get<filterIndex>();
auto& gain = processorChain.template get<gainIndex>();
```

### AudioBlock / ProcessContext in processBlock

```cpp
void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
{
    juce::dsp::AudioBlock<float> block(buffer);
    juce::dsp::ProcessContextReplacing<float> context(block);
    processorChain.process(context);
}
```

### Sub-Block Processing

```cpp
auto block = juce::dsp::AudioBlock<float>(buffer);
auto subBlock = block.getSubBlock((size_t)startSample, (size_t)numSamples);
auto context = juce::dsp::ProcessContextReplacing<float>(subBlock);
processorChain.process(context);
```

---

## Filter Designs

### StateVariableTPTFilter (Recommended for Modulation)

Best choice when cutoff frequency changes frequently. TPT structure prevents loud artifacts during modulation.

```cpp
juce::dsp::StateVariableTPTFilter<float> svfFilter;

void prepare(const juce::dsp::ProcessSpec& spec)
{
    svfFilter.prepare(spec);
    svfFilter.setType(juce::dsp::StateVariableTPTFilterType::lowpass);
    svfFilter.setCutoffFrequency(1000.0f);  // Hz
    svfFilter.setResonance(1.0f / std::sqrt(2.0f));  // Standard 12dB/oct (Butterworth)
}
```

**Filter Types:**
| Type | Enum Value |
|------|-----------|
| Low-pass | `StateVariableTPTFilterType::lowpass` |
| Band-pass | `StateVariableTPTFilterType::bandpass` |
| High-pass | `StateVariableTPTFilterType::highpass` |

**Notes:**
- Band-pass output may exceed 0 dB (different from RBJ cookbook)
- Standard resonance for flat 12dB/oct: `1.0f / std::sqrt(2.0f)`
- Per-sample processing: `float out = svfFilter.processSample(channel, inputSample);`

### LadderFilter (Moog-Style)

Analog ladder filter emulation with drive (saturation) and self-oscillation capability.

```cpp
juce::dsp::LadderFilter<float> ladderFilter;

void prepare(const juce::dsp::ProcessSpec& spec)
{
    ladderFilter.prepare(spec);
    ladderFilter.setCutoffFrequencyHz(1000.0f);
    ladderFilter.setResonance(0.7f);  // 0.0-1.0, high values = self-oscillation
    ladderFilter.setDrive(1.0f);      // >= 1.0, higher = more saturation
    ladderFilter.setEnabled(true);
}
```

**Modes:** Check `LadderFilterMode` enum for available filter slopes (12dB, 24dB, etc.).

### IIR Biquad Filters

Classic IIR filter with coefficient-based design. Use `ProcessorDuplicator` for multi-channel.

```cpp
using Filter = juce::dsp::IIR::Filter<float>;
using Coefficients = juce::dsp::IIR::Coefficients<float>;

// In ProcessorChain
juce::dsp::ProcessorDuplicator<Filter, Coefficients> iirFilter;

void prepare(const juce::dsp::ProcessSpec& spec)
{
    // Low-pass at 1kHz
    *iirFilter.state = *Coefficients::makeLowPass(spec.sampleRate, 1000.0f);
    iirFilter.prepare(spec);
}
```

**Available Coefficient Factories:**
```cpp
Coefficients::makeLowPass(sampleRate, frequency);
Coefficients::makeLowPass(sampleRate, frequency, Q);
Coefficients::makeHighPass(sampleRate, frequency);
Coefficients::makeHighPass(sampleRate, frequency, Q);
Coefficients::makeBandPass(sampleRate, frequency);
Coefficients::makeBandPass(sampleRate, frequency, Q);
Coefficients::makeNotch(sampleRate, frequency);
Coefficients::makeNotch(sampleRate, frequency, Q);
Coefficients::makeAllPass(sampleRate, frequency);
Coefficients::makeAllPass(sampleRate, frequency, Q);
Coefficients::makePeakFilter(sampleRate, frequency, Q, gainFactor);
Coefficients::makeLowShelf(sampleRate, frequency, Q, gainFactor);
Coefficients::makeHighShelf(sampleRate, frequency, Q, gainFactor);
Coefficients::makeFirstOrderLowPass(sampleRate, frequency);
Coefficients::makeFirstOrderHighPass(sampleRate, frequency);
Coefficients::makeFirstOrderAllPass(sampleRate, frequency);
```

### High-Pass Before Distortion Pattern

Remove low-end mud before waveshaping:

```cpp
using Filter = juce::dsp::IIR::Filter<float>;
using FilterCoefs = juce::dsp::IIR::Coefficients<float>;

juce::dsp::ProcessorChain<
    juce::dsp::ProcessorDuplicator<Filter, FilterCoefs>,
    juce::dsp::Gain<float>,
    juce::dsp::WaveShaper<float>,
    juce::dsp::Gain<float>
> distortionChain;

void prepare(const juce::dsp::ProcessSpec& spec)
{
    auto& filter = distortionChain.template get<0>();
    filter.state = FilterCoefs::makeFirstOrderHighPass(spec.sampleRate, 1000.0f);
    distortionChain.prepare(spec);
}
```

---

## Saturation / Waveshaping

### WaveShaper Setup

```cpp
juce::dsp::WaveShaper<float> waveshaper;

// Assign transfer function
waveshaper.functionToUse = [] (float x) {
    return std::tanh(x);  // Soft clipping
};
```

### Transfer Functions (Distortion Recipes)

| Function | Character | Code |
|----------|-----------|------|
| Hard clip | Extreme, digital | `juce::jlimit(-0.1f, 0.1f, x)` |
| Soft clip (tanh) | Warm, analog-like | `std::tanh(x)` |
| Boosted tanh | Adjustable saturation | `std::tanh(drive * x)` |
| Asymmetric | Tube-like, even harmonics | `x >= 0 ? std::tanh(x) : std::tanh(0.5f * x)` |
| Polynomial | Subtle warmth | `x - (x*x*x / 3.0f)` |
| Sine fold | Wavefolding, metallic | `std::sin(x * gain)` |
| Signum | Bit-crusher-like | `(x > 0) ? 1.0f : -1.0f` |

### Complete Saturation Chain

```cpp
enum {
    preGainIndex,
    waveshaperIndex,
    postGainIndex
};

juce::dsp::ProcessorChain<
    juce::dsp::Gain<float>,
    juce::dsp::WaveShaper<float>,
    juce::dsp::Gain<float>
> saturationChain;

void init()
{
    // Pre-gain drives the waveshaper harder
    auto& preGain = saturationChain.template get<preGainIndex>();
    preGain.setGainDecibels(30.0f);

    // Soft clipping
    auto& ws = saturationChain.template get<waveshaperIndex>();
    ws.functionToUse = [] (float x) { return std::tanh(x); };

    // Post-gain compensates for clipping
    auto& postGain = saturationChain.template get<postGainIndex>();
    postGain.setGainDecibels(-20.0f);
}
```

**Key Insight:** Pre-gain controls how hard the signal hits the waveshaper. Higher pre-gain = more distortion. Post-gain compensates for volume change.

---

## Sidechain Compression

### Bus Layout Setup

```cpp
// In constructor -- define 3 buses: main in, main out, sidechain in
MyCompressor()
    : AudioProcessor(BusesProperties()
        .withInput("Input", juce::AudioChannelSet::stereo())
        .withOutput("Output", juce::AudioChannelSet::stereo())
        .withInput("Sidechain", juce::AudioChannelSet::stereo()))
{
    // Add parameters...
}
```

### Bus Layout Validation

```cpp
bool isBusesLayoutSupported(const BusesLayout& layouts) const override
{
    // Main in and out must match
    return layouts.getMainInputChannelSet() == layouts.getMainOutputChannelSet()
        && !layouts.getMainInputChannelSet().isDisabled();
    // Sidechain layout is flexible
}
```

### Accessing Sidechain in processBlock

```cpp
void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
{
    // Bus 0 = main input/output
    auto mainBuffer = getBusBuffer(buffer, true, 0);

    // Bus 1 = sidechain input
    auto sideChainInput = getBusBuffer(buffer, true, 1);

    float threshold = thresholdParam->get();
    float alpha = alphaParam->get();  // Smoothing coefficient

    for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
    {
        // 1. Mix sidechain to mono
        float scMixed = 0.0f;
        for (int ch = 0; ch < sideChainInput.getNumChannels(); ++ch)
            scMixed += sideChainInput.getReadPointer(ch)[sample];
        scMixed /= static_cast<float>(sideChainInput.getNumChannels());

        // 2. Envelope follower (first-order low-pass)
        envelope = (alpha * envelope) + ((1.0f - alpha) * std::abs(scMixed));

        // 3. Compute gain reduction
        float gainReduction = 1.0f;
        if (envelope > threshold)
        {
            // Simple compression ratio
            gainReduction = threshold / envelope;
        }

        // 4. Apply to main signal
        for (int ch = 0; ch < mainBuffer.getNumChannels(); ++ch)
        {
            mainBuffer.getWritePointer(ch)[sample] *= gainReduction;
        }
    }
}
```

### Noise Gate (Sidechain Keyed)

From JUCE's official NoiseGatePluginDemo:

```cpp
void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
{
    auto mainIO = getBusBuffer(buffer, true, 0);
    auto scInput = getBusBuffer(buffer, true, 1);

    for (int j = 0; j < buffer.getNumSamples(); ++j)
    {
        // Mix sidechain channels to mono
        float mixedSC = 0.0f;
        for (int i = 0; i < scInput.getNumChannels(); ++i)
            mixedSC += scInput.getReadPointer(i)[j];
        mixedSC /= static_cast<float>(scInput.getNumChannels());

        // Low-pass filter the sidechain
        lowPassCoeff = (alpha * lowPassCoeff) + ((1.0f - alpha) * mixedSC);

        // Gate trigger
        if (lowPassCoeff >= threshold)
            sampleCountDown = (int)getSampleRate();  // Hold open for 1 second

        // Apply gate
        for (int i = 0; i < mainIO.getNumChannels(); ++i)
            *mainIO.getWritePointer(i, j) =
                sampleCountDown > 0 ? *mainIO.getReadPointer(i, j) : 0.0f;

        if (sampleCountDown > 0) --sampleCountDown;
    }
}
```

### CMake: Sidechain Bus Configuration

No special CMake changes needed. Bus configuration is done in C++ constructor. Just ensure your plugin type supports it:
```cmake
juce_add_plugin(MySidechainPlugin
    PLUGIN_IS_SYNTH FALSE
    # Sidechain is configured in C++, not CMake
)
```

---

## Convolution Reverb

### Loading an Impulse Response

```cpp
juce::dsp::Convolution convolution;

void prepare(const juce::dsp::ProcessSpec& spec)
{
    convolution.prepare(spec);

    // Load from file
    convolution.loadImpulseResponse(
        juce::File("/path/to/impulse_response.wav"),
        juce::dsp::Convolution::Stereo::yes,
        juce::dsp::Convolution::Trim::no,
        1024  // Maximum IR length in samples (0 = no limit)
    );
}
```

### Loading from Binary Data

```cpp
convolution.loadImpulseResponse(
    BinaryData::reverb_wav,
    BinaryData::reverb_wavSize,
    juce::dsp::Convolution::Stereo::yes,
    juce::dsp::Convolution::Trim::yes,
    0  // No length limit
);
```

### Cabinet Simulator Pattern

```cpp
enum { convolutionIndex };

juce::dsp::ProcessorChain<juce::dsp::Convolution> cabChain;

void init()
{
    auto& conv = cabChain.template get<convolutionIndex>();
    conv.loadImpulseResponse(
        juce::File("guitar_amp.wav"),
        juce::dsp::Convolution::Stereo::yes,
        juce::dsp::Convolution::Trim::no,
        1024
    );
}
```

### Convolution + Dry/Wet Mix

```cpp
juce::dsp::DryWetMixer<float> dryWetMixer;
juce::dsp::Convolution convolution;

void prepare(const juce::dsp::ProcessSpec& spec)
{
    dryWetMixer.prepare(spec);
    dryWetMixer.setMixingRule(juce::dsp::DryWetMixingRule::linear);
    dryWetMixer.setWetMixProportion(0.5f);  // 50% wet

    convolution.prepare(spec);
    // Load IR...
}

void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::dsp::AudioBlock<float> block(buffer);

    dryWetMixer.pushDrySamples(block);

    juce::dsp::ProcessContextReplacing<float> context(block);
    convolution.process(context);

    dryWetMixer.mixWetSamples(block);
}
```

---

## Oversampling

Use oversampling to reduce aliasing in nonlinear processing (waveshaping, saturation, etc.).

### Setup

```cpp
// 4x oversampling (factor=2 means 2^2=4x), IIR filters, max quality
juce::dsp::Oversampling<float> oversampling(
    2,      // numChannels
    2,      // factor (2^factor = oversampling amount)
    juce::dsp::Oversampling<float>::filterHalfBandPolyphaseIIR,  // Low latency
    true    // isMaxQuality
);
```

### Filter Type Choice

| Type | Latency | Phase | Best For |
|------|---------|-------|----------|
| `filterHalfBandFIREquiripple` | Higher | Linear | Mastering, clean signal |
| `filterHalfBandPolyphaseIIR` | Lower | Compromised near Nyquist | Real-time, live use |

### Processing Pattern

```cpp
void prepareToPlay(double sampleRate, int samplesPerBlock) override
{
    oversampling.initProcessing(static_cast<size_t>(samplesPerBlock));

    // Report latency to host
    setLatencySamples(static_cast<int>(oversampling.getLatencyInSamples()));

    // Prepare internal processors at oversampled rate
    juce::dsp::ProcessSpec spec;
    spec.sampleRate = sampleRate * oversampling.getOversamplingFactor();
    spec.maximumBlockSize = static_cast<juce::uint32>(
        samplesPerBlock * oversampling.getOversamplingFactor());
    spec.numChannels = 2;
    waveshaper.prepare(spec);
}

void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
{
    juce::dsp::AudioBlock<float> block(buffer);

    // Upsample
    auto oversampledBlock = oversampling.processSamplesUp(block);

    // Process at higher sample rate (nonlinear processing here)
    juce::dsp::ProcessContextReplacing<float> context(oversampledBlock);
    waveshaper.process(context);

    // Downsample back
    oversampling.processSamplesDown(block);
}
```

### Oversampling Factors

| Factor Parameter | Actual Rate | Use Case |
|-----------------|-------------|----------|
| 0 | 1x (no oversampling) | Bypass |
| 1 | 2x | Light saturation |
| 2 | 4x | Standard distortion |
| 3 | 8x | Heavy waveshaping |
| 4 | 16x | Maximum quality, high CPU |

---

## Delay Lines

### Basic Delay

```cpp
juce::dsp::DelayLine<float, juce::dsp::DelayLineInterpolationTypes::Linear> delayLine;

void prepare(const juce::dsp::ProcessSpec& spec)
{
    delayLine.prepare(spec);
    delayLine.setMaximumDelayInSamples(static_cast<int>(spec.sampleRate * 2.0));  // 2 sec max
    delayLine.setDelay(static_cast<float>(spec.sampleRate * 0.5));  // 500ms delay
}
```

### Interpolation Types

| Type | Quality | CPU | Best For |
|------|---------|-----|----------|
| `None` | Lowest | Lowest | Fixed integer delays |
| `Linear` | Good | Low | General purpose |
| `Lagrange3rd` | High | Medium | Pitch shifting, chorus |
| `Thiran` | Highest | Medium | All-pass fractional delay |

### Per-Sample Delay Processing

```cpp
for (int ch = 0; ch < numChannels; ++ch)
{
    for (int sample = 0; sample < numSamples; ++sample)
    {
        float input = channelData[ch][sample];
        float delayed = delayLine.popSample(ch);

        // Write input + feedback to delay line
        delayLine.pushSample(ch, input + delayed * feedbackAmount);

        // Mix dry + wet
        channelData[ch][sample] = input * dryLevel + delayed * wetLevel;
    }
}
```

---

## LFO Modulation

### Reduced-Rate LFO Pattern

Process LFO at a fraction of the audio sample rate to save CPU:

```cpp
static constexpr size_t lfoUpdateRate = 100;  // Update every 100 samples
size_t lfoUpdateCounter = lfoUpdateRate;
juce::dsp::Oscillator<float> lfo;

void prepare(const juce::dsp::ProcessSpec& spec)
{
    // LFO runs at reduced rate
    lfo.prepare({ spec.sampleRate / lfoUpdateRate,
                  spec.maximumBlockSize,
                  spec.numChannels });
    lfo.initialise([] (float x) { return std::sin(x); }, 128);
    lfo.setFrequency(3.0f);  // 3 Hz modulation rate
}
```

### LFO Modulation in processBlock

```cpp
void renderBlock(juce::dsp::AudioBlock<float>& output, int numSamples)
{
    for (size_t pos = 0; pos < (size_t)numSamples;)
    {
        auto max = juce::jmin((size_t)numSamples - pos, lfoUpdateCounter);
        auto block = output.getSubBlock(pos, max);
        juce::dsp::ProcessContextReplacing<float> context(block);
        processorChain.process(context);

        pos += max;
        lfoUpdateCounter -= max;

        if (lfoUpdateCounter == 0)
        {
            lfoUpdateCounter = lfoUpdateRate;
            auto lfoOut = lfo.processSample(0.0f);

            // Modulate filter cutoff between 100Hz and 2000Hz
            auto cutoff = juce::jmap(lfoOut, -1.0f, 1.0f, 100.0f, 2000.0f);
            processorChain.get<filterIndex>().setCutoffFrequency(cutoff);
        }
    }
}
```

---

## Complete Signal Chains

### Guitar Amp Simulator

```
Input → High-Pass (1kHz) → Pre-Gain (30dB) → Tanh WaveShaper →
Post-Gain (-20dB) → Convolution (Cabinet IR) → Output
```

### Synth Voice

```
Oscillator 1 + Oscillator 2 (detuned 1%) → LadderFilter →
Master Gain → Reverb → Output
```

### Sidechain Ducker

```
Main Input → Gain Reducer ← Sidechain Envelope Follower ← Sidechain Input
```

### Mastering Limiter

```
Input → Oversampling (4x up) → Soft Clipper → Oversampling (4x down) →
Lookahead Limiter → Output
```

---

## Essential Resources

- [JUCE DSP Introduction Tutorial](https://juce.com/tutorials/tutorial_dsp_introduction)
- [JUCE Waveshaping & Convolution Tutorial](https://juce.com/tutorials/tutorial_dsp_convolution/)
- [JUCE Audio Bus Layouts Tutorial](https://juce.com/tutorials/tutorial_audio_bus_layouts/)
- [JUCE NoiseGate Example (Sidechain)](https://github.com/juce-framework/JUCE/blob/master/examples/Plugins/NoiseGatePluginDemo.h)
- [JUCE DSP Module Docs](https://docs.juce.com/master/group__juce__dsp.html)
- [chowdsp_utils (Extended DSP)](https://github.com/Chowdhury-DSP/chowdsp_utils)
- [CTAGDRC Compressor (Open Source)](https://github.com/p-hlp/CTAGDRC)
- [Cytomic SVF (Forum)](https://forum.juce.com/t/cytomic-virtual-analog-svf-with-frequency-response/47147)
