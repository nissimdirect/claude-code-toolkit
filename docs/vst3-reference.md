# VST3 SDK Reference Documentation

> Comprehensive reference for VST3 plugin development.
> Sources: Steinberg VST3 Developer Portal, SDK documentation, community resources.

---

## Table of Contents

1. [Architecture: Processor/Controller Split](#architecture-processorcontroller-split)
2. [Bus Arrangements and Channel Layouts](#bus-arrangements-and-channel-layouts)
3. [Parameter Handling](#parameter-handling)
4. [State Saving/Loading (IBStream)](#state-savingloading-ibstream)
5. [GUI Integration (VST3Editor)](#gui-integration-vst3editor)
6. [VST3 vs VST2 Differences](#vst3-vs-vst2-differences)
7. [Common Pitfalls](#common-pitfalls)
8. [Quick Reference: First Plugin Structure](#quick-reference-first-plugin-structure)

---

## Architecture: Processor/Controller Split

### Core Design

A VST3 plugin consists of **two separate components**:

| Component | Interface | Thread | Responsibility |
|-----------|-----------|--------|----------------|
| **Processor** | `Vst::IAudioProcessor` + `Vst::IComponent` | Audio thread | DSP, audio rendering, state storage |
| **Controller** | `Vst::IEditController` | UI thread | Parameters, GUI, host communication |

This separation allows hosts to run each component in different contexts -- even on different machines (networked setups like Vienna Ensemble Pro).

### Why the Split Matters

- **Thread safety**: Audio processing never touches the UI thread
- **Distributed processing**: Host can farm DSP to another CPU/machine
- **Clean automation**: Parameter changes always route through the host
- **Testability**: Processor can be validated without GUI

### IComponent Interface

Provides host access to:
- Edit controller association via class ID retrieval
- Bus configuration information and routing details
- Bus activation/deactivation (including side-chains)
- Plugin activation control
- State persistence (presets and projects)

### IAudioProcessor Interface

Extends IComponent by adding:
- Configuration phase (before activation)
- Process setup with maximum sample block sizes
- Dynamic speaker arrangement negotiation
- Processing state management (`setProcessing`)
- The actual `process()` method for audio computation

### Processing Pipeline

The `process()` method receives a `ProcessData` struct containing:

```
ProcessData
  |-- inputParameterChanges   (IParameterChanges)
  |-- outputParameterChanges  (IParameterChanges)
  |-- inputEvents             (IEventList - MIDI, etc.)
  |-- outputEvents            (IEventList)
  |-- inputs[]                (AudioBusBuffers)
  |-- outputs[]               (AudioBusBuffers)
  |-- processContext           (timing, tempo, transport)
  |-- numSamples              (block size)
```

**Key rule**: The host can call `process()` without audio buffers to flush parameter changes only.

### Threading Model

| Thread | Safe to Call |
|--------|-------------|
| **UI Thread** | All initialization, GUI operations, `setState`, `getState` |
| **Audio Thread** | ONLY `process()` and `setProcessing()` |

**Never** allocate memory, lock mutexes, or do I/O on the audio thread.

### Communication Between Components

**Standard channel**: Parameter changes flow bidirectionally through the host. The host serializes parameter values and delivers them in the `process()` call.

**Private channel**: `IConnectionPoint` interface enables direct message passing for host-unknown data via `IMessage` and `IAttributeList`. Use this for non-automatable internal state.

---

## Bus Arrangements and Channel Layouts

### Bus Types

| Bus Type | Purpose |
|----------|---------|
| **Main Input** | Primary audio input (effect plugins) |
| **Main Output** | Primary audio output (all plugins) |
| **Aux Input** | Side-chain input |
| **Aux Output** | Additional outputs (surround, stems) |

### Speaker Arrangements

Common arrangements defined in `Vst::SpeakerArr`:

| Arrangement | Channels | Use Case |
|-------------|----------|----------|
| `kMono` | 1 | Mono processing |
| `kStereo` | 2 | Standard stereo |
| `kStereoSurround` | 2 | Surround stereo |
| `k51` | 6 | 5.1 surround |
| `k71` | 8 | 7.1 surround |

### Negotiation Process

1. Host proposes speaker arrangements via `setBusArrangements()`
2. Plugin accepts or rejects (returns `kResultFalse`)
3. If rejected, host queries preferred arrangement via `getBusArrangement()`
4. Host tries again with plugin's preference

```cpp
tresult PLUGIN_API MyProcessor::setBusArrangements(
    SpeakerArrangement* inputs, int32 numIns,
    SpeakerArrangement* outputs, int32 numOuts)
{
    // Accept only stereo in / stereo out
    if (numIns == 1 && numOuts == 1
        && inputs[0] == SpeakerArr::kStereo
        && outputs[0] == SpeakerArr::kStereo)
    {
        return AudioEffect::setBusArrangements(inputs, numIns, outputs, numOuts);
    }
    return kResultFalse;
}
```

### Side-Chain Configuration

Side-chain buses are auxiliary input buses. They must:
- Be declared during construction with `addAudioInput("Sidechain", SpeakerArr::kMono, kAux)`
- Default to **inactive** (host activates when user enables)
- Be validated in `setBusArrangements()` to maintain expected channel count

```cpp
// In constructor
addAudioInput(STR16("Stereo In"), SpeakerArr::kStereo, kMain);
addAudioInput(STR16("Sidechain"), SpeakerArr::kMono, kAux);
addAudioOutput(STR16("Stereo Out"), SpeakerArr::kStereo, kMain);
```

---

## Parameter Handling

### Normalized Values

**All parameter values in VST3 are normalized to the range [0.0, 1.0]** as 64-bit doubles.

The processor is responsible for converting normalized values to DSP-meaningful ranges:

```cpp
// Example: Convert normalized [0,1] to dB range [-60, 0]
float gainDb = normalizedValue * 60.0f - 60.0f;

// Example: Convert normalized [0,1] to frequency [20, 20000] (logarithmic)
float freq = 20.0f * std::pow(1000.0f, normalizedValue);
```

### Parameter IDs

| ID Range | Owner |
|----------|-------|
| 0 to 2,147,483,647 | Plugin-defined parameters |
| 2,147,483,648 to 4,294,967,295 | Reserved for host |

Define IDs in a shared header:

```cpp
// plugids.h
enum MyParams : Steinberg::Vst::ParamID
{
    kParamGainId     = 100,
    kParamFreqId     = 101,
    kParamMixId      = 102,
    kBypassId        = 103,
};
```

### Step Count and Discrete Parameters

| Step Count | Type | Example |
|------------|------|---------|
| 0 | Continuous | Gain knob |
| 1 | Toggle (on/off) | Bypass switch |
| n | Discrete with n+1 states | Mode selector |

Conversion formulas for discrete parameters:
```
Normalize:   normalized = discreteValue / stepCount
Denormalize: discreteValue = min(stepCount, normalized * (stepCount + 1))
```

### Registering Parameters (Controller Side)

```cpp
tresult PLUGIN_API MyController::initialize(FUnknown* context)
{
    EditController::initialize(context);

    // Continuous parameter: Gain [0dB to +24dB]
    parameters.addParameter(
        STR16("Gain"),          // title
        STR16("dB"),            // units
        0,                      // stepCount (0 = continuous)
        0.5,                    // defaultNormalizedValue
        Vst::ParameterInfo::kCanAutomate,  // flags
        kParamGainId            // tag/ID
    );

    // Discrete parameter: Mode [Clean, Warm, Hot]
    auto* modeParam = new Vst::StringListParameter(
        STR16("Mode"), kParamModeId, nullptr,
        Vst::ParameterInfo::kCanAutomate | Vst::ParameterInfo::kIsList
    );
    modeParam->appendString(STR16("Clean"));
    modeParam->appendString(STR16("Warm"));
    modeParam->appendString(STR16("Hot"));
    parameters.addParameter(modeParam);

    return kResultTrue;
}
```

### Reading Parameters in the Processor

Parameters arrive in the `process()` call via `IParameterChanges`:

```cpp
void MyProcessor::process(ProcessData& data)
{
    // Read parameter changes
    if (auto* paramChanges = data.inputParameterChanges)
    {
        int32 numParamsChanged = paramChanges->getParameterCount();
        for (int32 i = 0; i < numParamsChanged; i++)
        {
            auto* paramQueue = paramChanges->getParameterData(i);
            if (paramQueue)
            {
                Vst::ParamValue value;
                int32 sampleOffset;
                int32 numPoints = paramQueue->getPointCount();

                // Get the last value in this block
                if (paramQueue->getPoint(numPoints - 1, sampleOffset, value) == kResultTrue)
                {
                    switch (paramQueue->getParameterId())
                    {
                        case kParamGainId:
                            fGain = (float)value;
                            break;
                    }
                }
            }
        }
    }

    // Process audio with current parameter values...
}
```

### Automation Workflow

**Recording** (UI thread, triggered by user interaction):

```
beginEdit(paramId)       -- signals gesture start
  performEdit(paramId, value)  -- reports value changes
endEdit(paramId)         -- signals gesture end
```

**Playback**: The host delivers automation data via `IParameterChanges` with sample-accurate offsets in the `process()` call.

### Notifying Host of Changes

Call `restartComponent()` with flags:
- `kParamTitlesChanged` -- when titles, defaults, or flags change
- `kParamValuesChanged` -- when multiple values change (e.g., program switch)
- `kLatencyChanged` -- when plugin latency changes

---

## State Saving/Loading (IBStream)

### How State Persistence Works

1. **Save**: Host calls `getState()` on the processor. Processor writes DSP parameters to `IBStream`.
2. **Restore**: Host calls `setState()` on the processor, then passes the same state to the controller via `setComponentState()`.
3. **Controller state**: Controller can optionally save/load its own GUI state separately via its own `getState()`/`setState()`.

### Implementation Pattern

```cpp
// Processor: Save state
tresult PLUGIN_API MyProcessor::getState(IBStream* state)
{
    IBStreamer streamer(state, kLittleEndian);

    // Write a version number for future compatibility
    streamer.writeInt32(1);  // state version

    // Write parameters
    streamer.writeFloat(fGain);
    streamer.writeFloat(fFrequency);
    streamer.writeInt32(fMode);

    return kResultOk;
}

// Processor: Load state
tresult PLUGIN_API MyProcessor::setState(IBStream* state)
{
    IBStreamer streamer(state, kLittleEndian);

    int32 version = 0;
    streamer.readInt32(version);

    if (version >= 1)
    {
        streamer.readFloat(fGain);
        streamer.readFloat(fFrequency);
        streamer.readInt32(fMode);
    }

    return kResultOk;
}

// Controller: Sync from processor state
tresult PLUGIN_API MyController::setComponentState(IBStream* state)
{
    IBStreamer streamer(state, kLittleEndian);

    int32 version = 0;
    streamer.readInt32(version);

    if (version >= 1)
    {
        float gain, freq;
        int32 mode;
        streamer.readFloat(gain);
        streamer.readFloat(freq);
        streamer.readInt32(mode);

        // Update controller parameters WITHOUT triggering performEdit
        setParamNormalized(kParamGainId, gain);
        setParamNormalized(kParamFreqId, freq);
        setParamNormalized(kParamModeId, mode);
    }

    return kResultOk;
}
```

### Critical Rules

- **Version your state format** -- always write a version number first
- **Read in the same order you write** -- `IBStream` is sequential
- **Use `kLittleEndian`** -- consistent across platforms
- **Controller must NOT call `performEdit()`** during `setComponentState()` -- this would create unwanted automation

---

## GUI Integration (VST3Editor)

### Creating a View

The controller creates the editor view:

```cpp
IPlugView* PLUGIN_API MyController::createView(FIDString name)
{
    if (FIDStringsEqual(name, Vst::ViewType::kEditor))
    {
        // Option 1: VSTGUI-based editor with .uidesc
        return new VSTGUI::VST3Editor(this, "editor", "myPlugin.uidesc");

        // Option 2: Custom view (more control)
        return new MyCustomView(this);
    }
    return nullptr;
}
```

### Parameter Notification Flow

```
User moves knob in GUI
  |
  v
Controller::beginEdit(paramId)
Controller::performEdit(paramId, normalizedValue)
Controller::endEdit(paramId)
  |
  v
Host stores automation data
Host sends value to Processor via IParameterChanges in process()
  |
  v
Processor applies new value in next audio block
```

### GUI Thread Safety

- All GUI code runs on the **UI thread**
- Never access audio buffers from the GUI
- Use `IComponentHandler::performEdit()` to send values to host (which routes to processor)
- For custom data (non-parameter), use `IConnectionPoint` messaging

### VSTGUI Integration

Steinberg provides VSTGUI as the recommended GUI toolkit. It includes:
- A WYSIWYG editor for creating `.uidesc` XML layout files
- Pre-built controls (knobs, sliders, buttons, VU meters)
- Skinning support with bitmap-based graphics

**Alternative**: Many developers use JUCE's built-in GUI instead, which handles the VST3 wrapper automatically.

---

## VST3 vs VST2 Differences

### Architecture

| Feature | VST2 | VST3 |
|---------|------|------|
| **Component model** | Single `AudioEffect` class | Separate Processor + Controller |
| **Audio processing** | `processReplacing()` | Unified `process()` with events |
| **Parameter values** | Any range | Normalized [0.0, 1.0] only |
| **MIDI** | Direct MIDI CC access | Events through `IEventList`; MIDI CC mapped to parameters |
| **Side-chain** | Not standardized | First-class bus support |
| **64-bit audio** | Optional | Natively supported |
| **Dynamic I/O** | Fixed at init | Negotiable at runtime |
| **Silence detection** | Manual | Built-in silence flags |

### MIDI Handling Change

This is the **biggest pain point** for VST2 developers porting to VST3:

- VST3 has no direct MIDI CC support
- MIDI CC events must be mapped to parameters via `getMidiControllerAssignment()`
- The host converts MIDI CC to parameter changes before delivering to the processor
- This means MIDI CC values appear as automation-style `IParameterChanges`

```cpp
tresult PLUGIN_API MyController::getMidiControllerAssignment(
    int32 busIndex, int16 channel,
    Vst::CtrlNumber midiControllerNumber,
    Vst::ParamID& id)
{
    if (busIndex == 0 && midiControllerNumber == Vst::kCtrlModWheel)
    {
        id = kParamModWheelId;
        return kResultTrue;
    }
    return kResultFalse;
}
```

### Processing Differences

```cpp
// VST2: Simple buffer processing
void processReplacing(float** inputs, float** outputs, VstInt32 sampleFrames)
{
    for (int i = 0; i < sampleFrames; i++)
        outputs[0][i] = inputs[0][i] * gain;
}

// VST3: Unified process with parameter changes + events
tresult PLUGIN_API process(ProcessData& data)
{
    // 1. Read parameter changes from data.inputParameterChanges
    // 2. Read events from data.inputEvents
    // 3. Process audio from data.inputs to data.outputs
    // 4. Check data.numSamples, silence flags, etc.
}
```

---

## Common Pitfalls

### 1. Missing performEdit() Calls

**Problem**: Parameter changes from GUI don't reach the processor.

**Fix**: Always call the full sequence:
```cpp
handler->beginEdit(paramId);
handler->performEdit(paramId, normalizedValue);
handler->endEdit(paramId);
```

### 2. State Persistence Failures

**Problem**: Settings don't survive when reopening a project.

**Checklist**:
- Is `getState()` writing all parameters?
- Is `setState()` reading in the same order?
- Is `setComponentState()` syncing controller without calling `performEdit()`?
- Are you versioning your state format?

### 3. Audio Thread Violations

**Problem**: Crashes, glitches, or priority inversion.

**Rules for `process()`**:
- No memory allocation (`new`, `malloc`, `std::vector::push_back`)
- No mutex locks
- No file I/O
- No system calls
- No string operations
- Pre-allocate everything in `setupProcessing()` or `setActive()`

### 4. Bus Arrangement Rejection

**Problem**: Plugin doesn't appear in DAW or shows wrong channel count.

**Fix**: Implement `setBusArrangements()` to accept common configurations. At minimum, accept stereo in/out for effects.

### 5. MIDI CC Conflicts

**Problem**: When using `getMidiControllerAssignment()`, MIDI controller enum values may conflict with custom parameter IDs.

**Fix**: Use a dedicated ID range for MIDI-mapped parameters (e.g., start at 1000).

### 6. Thread Safety in notify()

**Problem**: `notify()` callbacks from controller may execute off the main thread.

**Fix**: Use timer-based GUI refresh rather than direct updates from notifications.

### 7. Silence Flag Handling

**Problem**: CPU usage stays high even during silence.

**Fix**: Check `data.inputs[0].silenceFlags` and skip processing when silent. Set output silence flags appropriately.

```cpp
if (data.inputs[0].silenceFlags != 0 && !hasTail())
{
    data.outputs[0].silenceFlags = data.inputs[0].silenceFlags;
    return kResultOk;  // Skip processing
}
```

### 8. Forgetting to Bypass Correctly

**Problem**: Bypass doesn't work or causes clicks.

**Fix**: Implement proper bypass by checking the bypass parameter and copying input to output with crossfading.

---

## Quick Reference: First Plugin Structure

### File Layout

```
MyPlugin/
  |-- CMakeLists.txt
  |-- source/
  |     |-- plugids.h          (parameter IDs, class IDs)
  |     |-- plugprocessor.h    (processor declaration)
  |     |-- plugprocessor.cpp  (audio DSP)
  |     |-- plugcontroller.h   (controller declaration)
  |     |-- plugcontroller.cpp (parameters, GUI)
  |     |-- plugentry.cpp      (factory registration)
  |-- resource/
        |-- myPlugin.uidesc    (optional VSTGUI layout)
```

### Class Registration (plugentry.cpp)

```cpp
#include "plugprocessor.h"
#include "plugcontroller.h"
#include "plugids.h"
#include "public.sdk/source/main/pluginfactory.h"

BEGIN_FACTORY_DEF("nissimdirect", "https://nissimdirect.com", "mailto:nissim.direct@gmail.com")

    DEF_CLASS2(INLINE_UID_FROM_FUID(MyProcessorUID),
        PClassInfo::kManyInstances,
        kVstAudioEffectClass,
        "My Plugin",
        Vst::kDistributable,
        Vst::PlugType::kFx,
        "1.0.0",
        kVstVersionString,
        MyProcessor::createInstance)

    DEF_CLASS2(INLINE_UID_FROM_FUID(MyControllerUID),
        PClassInfo::kManyInstances,
        kVstComponentControllerClass,
        "My Plugin Controller",
        0, "",
        "1.0.0",
        kVstVersionString,
        MyController::createInstance)

END_FACTORY
```

### Minimal Processor

```cpp
tresult PLUGIN_API MyProcessor::process(ProcessData& data)
{
    // 1. Read parameters
    readParameterChanges(data);

    // 2. Process audio
    if (data.numSamples > 0)
    {
        for (int32 ch = 0; ch < data.outputs[0].numChannels; ch++)
        {
            float* in  = data.inputs[0].channelBuffers32[ch];
            float* out = data.outputs[0].channelBuffers32[ch];

            for (int32 i = 0; i < data.numSamples; i++)
            {
                out[i] = in[i] * fGain;
            }
        }
    }
    return kResultOk;
}
```

---

## References

- [Steinberg VST3 Developer Portal](https://steinbergmedia.github.io/vst3_dev_portal/)
- [VST3 SDK GitHub](https://github.com/steinbergmedia/vst3sdk)
- [VST3 API Documentation](https://steinbergmedia.github.io/vst3_dev_portal/pages/Technical+Documentation/API+Documentation/Index.html)
- [VST3 Parameters & Automation](https://steinbergmedia.github.io/vst3_dev_portal/pages/Technical+Documentation/Parameters+Automation/Index.html)
- [Code Your First Plugin Tutorial](https://steinbergmedia.github.io/vst3_dev_portal/pages/Tutorials/Code+your+first+plug-in.html)
- [Porting VST2 to VST3 - Adam Monroe](https://adammonroemusic.com/blog/porting_vst2_plugins_to_vst3.html)
