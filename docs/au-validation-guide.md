# Audio Unit Development & Validation Guide

> Comprehensive reference for macOS Audio Unit plugin development and validation.
> Sources: Apple Developer Documentation, community guides, practical testing resources.

---

## Table of Contents

1. [AU Component Structure](#au-component-structure)
2. [AU Validation Tool (auval/auvaltool)](#au-validation-tool-auvalauvaltool)
3. [Sandbox Requirements for macOS](#sandbox-requirements-for-macos)
4. [Code Signing for AU Plugins](#code-signing-for-au-plugins)
5. [AU v2 vs AU v3 Differences](#au-v2-vs-au-v3-differences)
6. [Logic Pro X Specific Requirements](#logic-pro-x-specific-requirements)
7. [Troubleshooting Reference](#troubleshooting-reference)

---

## AU Component Structure

### Bundle Architecture

Audio Units are packaged as macOS component bundles with the `.component` extension:

```
MyAudioUnit.component/
  Contents/
    Info.plist              (critical metadata -- plugin identity)
    MacOS/
      MyAudioUnit           (compiled executable)
    Resources/
      MyAudioUnitView.bundle  (optional custom view)
```

### Installation Locations

| Path | Scope | Notes |
|------|-------|-------|
| `~/Library/Audio/Plug-Ins/Components/` | Current user only | Recommended for development |
| `/Library/Audio/Plug-Ins/Components/` | All users | Requires admin install |
| `/System/Library/Components/` | Apple only | Never install here |

### Audio Unit Identification

Every AU is uniquely identified by a **four-character code triplet**:

```
Type (4 chars)         -- Defines the plugin API category
Subtype (4 chars)      -- Describes specific function
Manufacturer (4 chars) -- Developer identifier (must include uppercase)
```

**Example**: `aufx` `lpas` `Nsdm` = Effect / Low-pass / nissimdirect

### Audio Unit Types

| Type Code | Name | Purpose | Example |
|-----------|------|---------|---------|
| `aufx` | Effect | Modify audio streams | EQ, reverb, compressor |
| `aumf` | Music Effect | Effect + MIDI response | Vocoder, looper |
| `aumu` | Music Device (Instrument) | MIDI in, audio out | Synth, sampler |
| `augn` | Generator | Create audio programmatically | Tone generator |
| `auol` | Offline Effect | Non-real-time processing | Time stretch |
| `aumx` | Mixer | Combine audio streams | Submixer |
| `aufc` | Format Converter | Sample rate / bit depth | SRC |
| `aupn` | Panner | Spatialization | 3D panner |

### Version Number Format

Hexadecimal 8-digit code: `0xMMmmRR`

| Component | Hex Digits | Example |
|-----------|-----------|---------|
| Major version | 4 digits (MM) | `001d` = 29 |
| Minor version | 2 digits (mm) | `21` = 33 |
| Dot release | 2 digits (RR) | `28` = 40 |

**Critical**: Version must be strictly higher than any previous version for the Audio Component Registrar to recognize updates.

### Info.plist Configuration

Essential keys for AU recognition:

```xml
<key>AudioComponents</key>
<array>
  <dict>
    <key>description</key>
    <string>My Awesome Plugin</string>
    <key>manufacturer</key>
    <string>Nsdm</string>
    <key>type</key>
    <string>aufx</string>
    <key>subtype</key>
    <string>mypl</string>
    <key>version</key>
    <integer>65536</integer>
    <key>sandboxSafe</key>
    <true/>
    <key>tags</key>
    <array>
      <string>Effects</string>
    </array>
  </dict>
</array>
```

### Core Audio SDK Class Hierarchy

When building without JUCE (native SDK):

| Base Class | Use For |
|-----------|---------|
| `AUBase` | All audio units (base scaffolding) |
| `AUEffectBase` | Effect units (`aufx`) |
| `AUInstrumentBase` | Instrument units (`aumu`) |
| `AUGeneratorBase` | Generator units (`augn`) |
| `AUMIDIEffectBase` | Music effects (`aumf`) |

### Processing Model (Pull Architecture)

Audio Units use a **pull model**:

```
Host requests audio from final node
  --> Final node pulls from upstream AU
    --> Upstream AU pulls from its input
      --> Input renders via callback
Audio data flows FORWARD through the chain
Control flow goes BACKWARD (pull)
```

Default frame slice: **512 frames** (configurable 24-4096).

Each render cycle:
1. Receive render callback with fresh audio frames
2. Process audio data
3. Place results in output buffers

**Reset requirement**: All AUs must implement `Reset()` to clear internal DSP buffers and prevent artifacts between audio segments.

---

## AU Validation Tool (auval/auvaltool)

### Overview

The `auvaltool` (aliased as `auval` on macOS 15+) is Apple's official validation tool that tests AU plugins for API conformance. **Passing auval is mandatory for plugins to appear in Logic Pro and other Apple DAWs.**

### Basic Usage

```bash
# List all installed Audio Units
auval -a

# List only AUv2 plugins
auvaltool -al

# Validate a specific plugin (strict mode)
auval -strict -v TYPE SUBT MANU

# Examples:
auval -strict -v aufx mypl Nsdm     # Effect plugin
auval -strict -v aumu synt Nsdm     # Instrument plugin
auval -strict -v aumf myfx Nsdm     # Music effect
```

### Command Options

| Flag | Purpose |
|------|---------|
| `-v TYPE SUBT MANU` | Validate specific AU |
| `-a` | List all Audio Units |
| `-al` | List all AUv2 only |
| `-strict` | Enable strict validation (recommended) |
| `-stress N` | Stress test for N simulated seconds |
| `-de` | Validate in-process (for debugging) |

### What auval Tests

| Category | Tests |
|----------|-------|
| **API Conformance** | All required methods implemented correctly |
| **Channel Configurations** | Supports declared I/O layouts |
| **Instantiation** | Opens quickly, multiple instances work |
| **State Persistence** | Save/restore produces identical state |
| **Parameter Ranges** | All parameters within declared bounds |
| **Render Capability** | Can actually produce audio output |
| **Initialization** | Allocate/deallocate cycles work |
| **Bypass** | Bypass mode passes audio unchanged |

### What auval Does NOT Test

- Custom views / GUI
- Architecture pattern (MVC)
- Audio Unit Event API usage
- DSP quality or correctness
- Real-world performance in a DAW

### Common Failures and Fixes

#### Error 4099: Cannot Open Component

**Cause**: Audio/MIDI input/output configuration mismatch with registered AU type.

**Fix**: Verify your type code matches your actual I/O:
- `aufx` must have audio inputs AND outputs
- `aumu` must have MIDI input and audio output (no audio input)
- `augn` must have audio output only (no audio or MIDI input)

#### Initialization Failure

**Cause**: Plugin takes too long to initialize or crashes during init.

**Fix**:
- Keep initialization lightweight
- Do heavy loading (samples, IR files) asynchronously
- Copy protection checks go in `Initialize()`, not constructor

#### State Persistence Failure

**Cause**: State saved and restored doesn't match.

**Fix**:
- Ensure every parameter is saved in `getState()` and restored in `setState()`
- Read/write in the same order
- Handle version migration

#### Channel Configuration Failure

**Cause**: Plugin doesn't support the channel layouts it claims to.

**Fix**: Implement `SupportedNumChannels()` correctly and test all declared configurations.

#### Parameter Clamping Failure

**Cause**: Parameter values outside declared min/max range.

**Fix**: Always clamp parameter values in both get and set methods.

### Debugging auval

**Challenge**: `auvaltool` lacks the `com.apple.security.get-task-allow` entitlement needed for debugger attachment.

**Solution 1 -- x86_64 slice** (temporary, Rosetta sunsets Fall 2027):
```bash
# Extract x86_64 slice
lipo -extract x86_64 /usr/bin/auvaltool -output ~/auvaltool_x86
# Ad-hoc sign
codesign -f -s - ~/auvaltool_x86
# Debug via Rosetta
~/auvaltool_x86 -strict -v aufx mypl Nsdm
```

**Solution 2 -- Disable SIP** (development only):
```bash
# Boot to Recovery Mode, then:
csrutil disable
# Now you can attach debugger to /usr/bin/auvaltool
# Re-enable when done:
csrutil enable
```

**Solution 3 -- Use pluginval**:
```bash
# Install pluginval (open-source, more configurable)
brew install pluginval
# Run with strictness level
pluginval --strictness-level 5 "path/to/MyPlugin.component"
```

### Registry Management

The `AudioComponentRegistrar` service monitors plugin folders automatically. When updates aren't recognized:

```bash
# Force re-scan
killall -9 AudioComponentRegistrar

# Nuclear option: change plugin name or manufacturer code to force re-registration
```

---

## Sandbox Requirements for macOS

### Why Sandboxing Matters

Starting with macOS 10.15 (Catalina), Apple tightened security requirements. Logic Pro X runs in a sandboxed environment, meaning plugins must be declared `sandboxSafe` to load.

### Making a Plugin Sandbox-Safe

1. **Set `sandboxSafe` to `true`** in your Info.plist `AudioComponents` dictionary
2. **Avoid accessing files outside your container** without user consent
3. **Do not use deprecated APIs** that bypass sandbox restrictions
4. **Handle App Transport Security** for any network requests

### What Sandbox-Safe Means

Your plugin must NOT:
- Access arbitrary filesystem locations
- Open network connections without declaration
- Use inter-process communication without entitlements
- Access hardware directly (camera, microphone) without entitlements
- Execute external processes

Your plugin CAN:
- Read/write to its own container and app group containers
- Access user-selected files (via host-provided file dialogs)
- Use standard audio/MIDI APIs
- Allocate memory normally

### JUCE and Sandboxing

If using JUCE, set these in your CMakeLists.txt:
```cmake
juce_add_plugin(MyPlugin
    ...
    APP_SANDBOX_ENABLED TRUE
    APP_SANDBOX_OPTIONS
        com.apple.security.device.audio-input
    ...
)
```

---

## Code Signing for AU Plugins

### Why Code Signing is Required

- macOS Gatekeeper blocks unsigned code from running
- Logic Pro X requires signed (and ideally notarized) plugins
- Users get security warnings for unsigned plugins

### Signing Process

```bash
# 1. Sign the component bundle
codesign --force --sign "Developer ID Application: Your Name (TEAMID)" \
    --options runtime \
    --timestamp \
    "MyPlugin.component"

# 2. Verify signature
codesign --verify --verbose "MyPlugin.component"

# 3. For distribution: notarize with Apple
# Create a ZIP for notarization
ditto -c -k --keepParent "MyPlugin.component" "MyPlugin.zip"

# Submit for notarization
xcrun notarytool submit "MyPlugin.zip" \
    --apple-id "your@email.com" \
    --team-id "TEAMID" \
    --password "app-specific-password" \
    --wait

# Staple the notarization ticket
xcrun stapler staple "MyPlugin.component"
```

### Development Signing

For local development/testing, ad-hoc signing is sufficient:

```bash
codesign --force --sign - "MyPlugin.component"
```

### Hardened Runtime

For notarization, enable hardened runtime with required exceptions:

```xml
<!-- entitlements.plist -->
<key>com.apple.security.cs.allow-unsigned-executable-memory</key>
<true/>
<key>com.apple.security.cs.disable-library-validation</key>
<true/>
```

---

## AU v2 vs AU v3 Differences

### Architecture Comparison

| Feature | AU v2 | AU v3 |
|---------|-------|-------|
| **Process Model** | In-process (loaded into host) | App extension (separate process) |
| **Platform** | macOS only | macOS + iOS |
| **Sandboxing** | Host's sandbox | Own extension sandbox |
| **UI Framework** | Carbon/Cocoa view | AUViewController (UIKit/AppKit) |
| **Memory** | Shares host address space | Isolated memory space |
| **Crash Impact** | Crashes the host | Extension crashes independently |
| **API Framework** | AudioToolbox | AudioUnit framework |
| **Distribution** | .component bundle | App with .appex extension |
| **Minimum OS** | macOS 10.0+ | macOS 10.11+ / iOS 9+ |

### AU v3 App Extension Structure

```
MyAUHost.app/
  Contents/
    PlugIns/
      MyAU.appex/         (the AU v3 extension)
        Contents/
          Info.plist
          MacOS/
            MyAU
```

### AU v3 Implementation Requirements

```objc
// Principal class must conform to AUAudioUnitFactory
@interface MyAUViewController : AUViewController <AUAudioUnitFactory>

- (AUAudioUnit *)createAudioUnitWithComponentDescription:
    (AudioComponentDescription)desc error:(NSError **)error
{
    // Handle async loading -- UI and AU load in unpredictable order
    audioUnit = [[MyAudioUnit alloc] initWithComponentDescription:desc error:error];
    if (self.isViewLoaded) {
        [self connectUIToAudioUnit];
    }
    return audioUnit;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    if (audioUnit) {
        [self connectUIToAudioUnit];
    }
}
@end
```

**Required AUAudioUnit overrides:**
- `inputBusses` -- define audio input connection points
- `outputBusses` -- define audio output connection points
- `internalRenderBlock` -- implement audio rendering loop
- `allocateRenderResourcesAndReturnError:` -- called before rendering starts
- `deallocateRenderResources` -- called after rendering ends

### Extension Point Identifiers

| Type | Identifier |
|------|-----------|
| With UI | `com.apple.AudioUnit-UI` |
| Without UI | `com.apple.AudioUnit` |

### Bridging Between Versions

- v3 hosts CAN use v2 AUs (automatic bridging)
- v2 hosts need minor API changes to host v3 AUs
- Apple provides automatic wrapping in both directions

### Current Adoption Status (2026)

| DAW | AU v2 | AU v3 |
|-----|-------|-------|
| Logic Pro | Full | Full |
| GarageBand | Full | Full |
| Ableton Live | Full | Limited |
| Reaper | Full | Experimental |
| Most others | Full | Partial |

**Recommendation**: Build both AU v2 and AU v3 for maximum compatibility. JUCE handles this automatically with `FORMATS AU AUv3` in CMakeLists.txt.

### Deprecation Timeline

Apple has stated that AU v2 will be deprecated in a future OS release. However, as of macOS 15, AU v2 still works. Plan for migration but don't drop v2 support yet.

---

## Logic Pro X Specific Requirements

### Plugin Discovery

Logic Pro scans plugins at launch and validates them with auval. Failed plugins are blacklisted.

**Force rescan**: Delete the Logic plugin cache:
```bash
# Logic Pro plugin cache
rm ~/Library/Caches/com.apple.audiounits.cache
# Or for newer versions:
rm ~/Library/Caches/AudioUnitCache/
```

### Manufacturer Code Requirements

For **GarageBand 10.3+** compatibility (which Logic shares components with):
- First character must be **uppercase**
- Remaining characters must be **lowercase**
- Example: `Nsdm` (not `NSDM` or `nsdm`)

### Channel Layout Support

Logic Pro expects plugins to support at minimum:
- Mono in / Mono out
- Stereo in / Stereo out
- Mono in / Stereo out (for instruments/generators)

### Tail Time

Logic Pro queries `GetTailTime()` to determine how long to continue processing after audio stops (for reverb tails, delay feedback, etc.). Implement this correctly or your effect will be cut short.

### Bypass Behavior

Logic Pro uses its own bypass mechanism. Your plugin must:
1. Respond to the bypass parameter
2. Pass audio through unchanged when bypassed
3. Not click or pop during bypass transitions (use crossfading)

### Latency Reporting

Report any processing latency accurately via `GetLatency()`. Logic Pro uses this for automatic delay compensation. Incorrect reporting causes phase issues.

### Factory Presets

Logic Pro displays factory presets in its preset browser. Implement `GetPresets()` to provide a list of named presets with their parameter values.

---

## Troubleshooting Reference

### Plugin Not Showing in DAW

1. Verify `.component` is in the correct location
2. Run `auval -a` to check if AU is registered
3. Check type code matches expected category
4. Verify version number is higher than any previous
5. Kill AudioComponentRegistrar: `killall -9 AudioComponentRegistrar`
6. Clear DAW plugin cache
7. Check Console.app for error messages

### auval Passes but DAW Rejects

1. Check code signing: `codesign --verify --verbose MyPlugin.component`
2. Verify `sandboxSafe` is `true` in Info.plist
3. Check for hardened runtime issues
4. Look for system library loading issues in Console.app

### Audio Glitches / Dropouts

1. Check `GetLatency()` is correctly reported
2. Verify no memory allocation in render callback
3. Check thread priority -- render thread must not be blocked
4. Profile with Instruments.app (Time Profiler)
5. Reduce buffer size sensitivity

### Parameter Automation Not Working

1. Verify Audio Unit Event API is implemented
2. Check parameter flags include `kAudioUnitParameterFlag_IsWritable`
3. Ensure `beginEdit`/`performEdit`/`endEdit` sequence is correct
4. Test with different DAWs (some have stricter requirements)

---

## References

- [Apple Audio Unit Programming Guide](https://developer.apple.com/library/archive/documentation/MusicAudio/Conceptual/AudioUnitProgrammingGuide/Introduction/Introduction.html)
- [Apple Audio Unit Framework Reference](https://developer.apple.com/documentation/audiounit/)
- [Apple App Extension Programming Guide - Audio Unit](https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/AudioUnit.html)
- [Debugging AU with auvaltool](https://moonbase.sh/articles/debugging-your-audio-unit-plugin-with-auval-aka-auvaltool/)
- [KVR Forum - AUv2 vs AUv3](https://www.kvraudio.com/forum/viewtopic.php?t=557169)
- [JUCE Forum - AUv3 Explained](https://forum.juce.com/t/auv3-what-is-it/55887)
