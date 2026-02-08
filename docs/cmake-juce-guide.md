# CMake for JUCE Audio Plugins

> Complete guide to building JUCE audio plugins with CMake.
> Sources: Official JUCE CMake API docs, Pamplejuce template, Melatonin blog, community guides.

---

## Table of Contents

1. [Minimal CMakeLists.txt for a JUCE Plugin](#minimal-cmakeliststxt-for-a-juce-plugin)
2. [Universal Binary Configuration (arm64 + x86_64)](#universal-binary-configuration-arm64--x86_64)
3. [Debug vs Release Builds](#debug-vs-release-builds)
4. [Adding JUCE Modules](#adding-juce-modules)
5. [Common CMake Errors and Fixes](#common-cmake-errors-and-fixes)
6. [Compile Flags for Audio Performance](#compile-flags-for-audio-performance)
7. [Advanced Configuration](#advanced-configuration)
8. [CI/CD and Distribution](#cicd-and-distribution)

---

## Minimal CMakeLists.txt for a JUCE Plugin

### Project Structure

```
MyPlugin/
  |-- CMakeLists.txt
  |-- JUCE/                    (git submodule)
  |-- source/
  |     |-- PluginProcessor.h
  |     |-- PluginProcessor.cpp
  |     |-- PluginEditor.h
  |     |-- PluginEditor.cpp
  |-- .gitmodules
```

### Setting Up JUCE as a Submodule

```bash
cd ~/Development/AudioPlugins/MyPlugin
git init
git submodule add https://github.com/juce-framework/JUCE.git JUCE
```

### Complete Minimal CMakeLists.txt

```cmake
# ==============================================================================
# Minimum CMake version (JUCE requires 3.22+)
# ==============================================================================
cmake_minimum_required(VERSION 3.22)

# ==============================================================================
# Project definition
# ==============================================================================
project(MyPlugin VERSION 1.0.0)

# ==============================================================================
# Include JUCE
# ==============================================================================
add_subdirectory(JUCE)

# ==============================================================================
# Plugin target
# ==============================================================================
juce_add_plugin(MyPlugin
    # Unique identifiers
    COMPANY_NAME "nissimdirect"
    PLUGIN_MANUFACTURER_CODE Nsdm           # 4 chars, first uppercase for AU
    PLUGIN_CODE Mypl                         # 4 chars, unique per plugin

    # Plugin formats to build
    FORMATS AU VST3 Standalone               # AU only on macOS

    # Plugin metadata
    PRODUCT_NAME "My Plugin"                 # Display name in DAW

    # Plugin type
    IS_SYNTH FALSE                           # TRUE for instruments
    NEEDS_MIDI_INPUT FALSE                   # TRUE for MIDI processors
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE

    # Copy to system plugin folders after build
    COPY_PLUGIN_AFTER_BUILD TRUE
    VST3_COPY_DIR "$ENV{HOME}/Library/Audio/Plug-Ins/VST3"
    AU_COPY_DIR "$ENV{HOME}/Library/Audio/Plug-Ins/Components"
)

# ==============================================================================
# Source files
# ==============================================================================
target_sources(MyPlugin
    PRIVATE
        source/PluginProcessor.cpp
        source/PluginEditor.cpp
)

# ==============================================================================
# Compile definitions
# ==============================================================================
target_compile_definitions(MyPlugin
    PUBLIC
        JUCE_WEB_BROWSER=0                   # Don't need web browser
        JUCE_USE_CURL=0                      # Don't need CURL
        JUCE_VST3_CAN_REPLACE_VST2=0        # No VST2 compatibility
        JUCE_DISPLAY_SPLASH_SCREEN=0         # No JUCE splash (requires license)
)

# ==============================================================================
# Link JUCE modules
# ==============================================================================
target_link_libraries(MyPlugin
    PRIVATE
        juce::juce_audio_utils               # Includes audio_basics, audio_devices, etc.
        juce::juce_dsp                       # DSP module (filters, oversampling, etc.)
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)
```

### Build Commands

```bash
# Navigate to project
cd ~/Development/AudioPlugins/MyPlugin

# Create build directory and configure
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Debug

# Build
cmake --build .

# Build with parallel compilation (faster)
cmake --build . --parallel $(sysctl -n hw.ncpu)

# Clean rebuild
cmake --build . --clean-first
```

---

## Universal Binary Configuration (arm64 + x86_64)

### Why Universal Binaries

macOS runs on both Apple Silicon (arm64) and Intel (x86_64). Universal binaries contain both architectures so your plugin works on all Macs.

### Configuration

```bash
# Configure for universal binary
cmake -B build \
    -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64" \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=10.15 \
    -DCMAKE_BUILD_TYPE=Release

# Build
cmake --build build --parallel $(sysctl -n hw.ncpu)
```

### In CMakeLists.txt (Alternative)

```cmake
# Set at the TOP of CMakeLists.txt, before project()
set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64" CACHE STRING "")
set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "Minimum macOS version")

cmake_minimum_required(VERSION 3.22)
project(MyPlugin VERSION 1.0.0)
# ... rest of config
```

### Verifying Universal Binary

```bash
# Check architectures in the built plugin
file "build/MyPlugin_artefacts/VST3/My Plugin.vst3/Contents/MacOS/My Plugin"
# Should show: Mach-O universal binary with 2 architectures:
#   Mach-O 64-bit bundle x86_64
#   Mach-O 64-bit bundle arm64

# Alternative check
lipo -info "build/MyPlugin_artefacts/VST3/My Plugin.vst3/Contents/MacOS/My Plugin"
```

### Deployment Target Reference

| Minimum macOS | Reason |
|--------------|--------|
| 10.13 | Oldest reasonable target |
| 10.15 | Catalina (required for notarization) |
| 11.0 | Big Sur (first with Apple Silicon native) |
| 12.0 | Monterey (modern baseline) |

**Recommendation**: Target 10.15 for maximum compatibility with modern security requirements.

---

## Debug vs Release Builds

### Build Types

| Type | Optimization | Debug Info | Use Case |
|------|-------------|-----------|----------|
| `Debug` | None (-O0) | Full (-g) | Development, debugging |
| `Release` | Full (-O3) | None | Distribution |
| `RelWithDebInfo` | Some (-O2) | Full (-g) | Performance debugging |
| `MinSizeRel` | Size (-Os) | None | Size-constrained targets |

### Configure Each Build Type

```bash
# Debug build (for development)
cmake -B build-debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build-debug

# Release build (for distribution)
cmake -B build-release -DCMAKE_BUILD_TYPE=Release
cmake --build build-release

# Release with debug info (for profiling)
cmake -B build-reldbg -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-reldbg
```

### Xcode Generator (Multi-Config)

When using the Xcode generator, build type is selected at build time:

```bash
# Configure with Xcode generator
cmake -B build -G Xcode

# Build Debug
cmake --build build --config Debug

# Build Release
cmake --build build --config Release
```

### Output Locations

JUCE places built artifacts in:
```
build/
  MyPlugin_artefacts/
    Debug/                    (or Release/)
      Standalone/
        My Plugin.app
      VST3/
        My Plugin.vst3
      AU/
        My Plugin.component
```

---

## Adding JUCE Modules

### Core JUCE Modules

| Module | Purpose | Include When |
|--------|---------|-------------|
| `juce_audio_basics` | Audio buffer, MIDI classes | Always (included by audio_utils) |
| `juce_audio_devices` | Audio hardware I/O | Standalone apps |
| `juce_audio_formats` | WAV, AIFF, MP3 reading | Sample playback |
| `juce_audio_processors` | Plugin processor base | Always for plugins |
| `juce_audio_utils` | AudioProcessorEditor, etc. | Always for plugins (umbrella) |
| `juce_core` | Strings, files, threads | Always (auto-included) |
| `juce_data_structures` | ValueTree, UndoManager | State management |
| `juce_dsp` | Filters, FFT, oversampling | DSP-heavy plugins |
| `juce_events` | Timers, message loop | Always (auto-included) |
| `juce_graphics` | Drawing, fonts, images | GUI plugins |
| `juce_gui_basics` | Components, layout | GUI plugins |
| `juce_gui_extra` | WebBrowser, CodeEditor | Rarely needed |
| `juce_opengl` | OpenGL rendering | GPU-accelerated UI |

### How to Add Modules

```cmake
target_link_libraries(MyPlugin
    PRIVATE
        # Core plugin modules
        juce::juce_audio_utils          # Pulls in audio_basics, audio_processors, etc.

        # DSP module (add this for filters, oversampling, convolution)
        juce::juce_dsp

        # OpenGL (only if using GPU rendering)
        # juce::juce_opengl

    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)
```

### Adding Third-Party JUCE Modules

```cmake
# Add a third-party module from a path
juce_add_module(${CMAKE_CURRENT_SOURCE_DIR}/modules/my_custom_module)

# Then link it
target_link_libraries(MyPlugin PRIVATE my_custom_module)
```

### Adding Binary Resources (Images, Fonts, etc.)

```cmake
# Create a binary data target from files
juce_add_binary_data(MyPluginData
    SOURCES
        resources/background.png
        resources/knob.png
        resources/font.ttf
)

# Link to plugin
target_link_libraries(MyPlugin PRIVATE MyPluginData)

# Access in code:
# #include "BinaryData.h"
# auto image = juce::ImageCache::getFromMemory(BinaryData::background_png,
#                                               BinaryData::background_pngSize);
```

### Module Configuration Options

Override module defaults via compile definitions:

```cmake
target_compile_definitions(MyPlugin
    PUBLIC
        # Disable features you don't need
        JUCE_WEB_BROWSER=0
        JUCE_USE_CURL=0

        # DSP module config
        JUCE_DSP_USE_INTEL_MKL=0
        JUCE_DSP_USE_STATIC_FFTW=0

        # Audio processor config
        JUCE_VST3_CAN_REPLACE_VST2=0

        # GUI config
        JUCE_DISPLAY_SPLASH_SCREEN=0
)
```

---

## Common CMake Errors and Fixes

### Error: "CMake version too old"

```
CMake Error at CMakeLists.txt:1:
  CMake 3.22 or higher is required.  You are running version 3.16.
```

**Fix**:
```bash
# macOS: Install latest CMake
brew install cmake
# Or download from https://cmake.org/download/

# Verify
cmake --version
```

**Important**: On macOS, avoid Homebrew's CMake if it causes compiler detection issues. Download the official binary from cmake.org instead.

### Error: "JUCE not found" / "add_subdirectory cannot find"

```
CMake Error at CMakeLists.txt:X:
  add_subdirectory given source "JUCE" which is not an existing directory.
```

**Fix**:
```bash
# Initialize JUCE submodule
git submodule update --init --recursive

# Or if not using submodules, clone JUCE
git clone https://github.com/juce-framework/JUCE.git
```

### Error: "No CMAKE_CXX_COMPILER found"

**Fix**:
```bash
# Install Xcode Command Line Tools
xcode-select --install

# If already installed, reset
sudo xcode-select --reset
```

### Error: "Signing identity not found"

```
Code Signing Error: No signing identity found
```

**Fix** (for development):
```cmake
# Add to CMakeLists.txt for ad-hoc signing
set(CMAKE_XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY "-" CACHE STRING "")
```

Or via command line:
```bash
cmake -B build -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY="-"
```

### Error: "Unknown target" / Link order issues

```
CMake Error: Target "MyPlugin" links to target "juce::juce_dsp" but the target was not found.
```

**Fix**: Ensure `add_subdirectory(JUCE)` appears BEFORE `juce_add_plugin()`:

```cmake
# CORRECT ORDER:
add_subdirectory(JUCE)           # 1. Load JUCE first
juce_add_plugin(MyPlugin ...)    # 2. Define plugin
target_sources(...)              # 3. Add sources
target_link_libraries(...)       # 4. Link modules
```

### Error: "Multiple definitions" / Duplicate symbols

**Fix**: Ensure source files are only listed once in `target_sources`. Check for glob patterns picking up duplicates:

```cmake
# Prefer explicit file listing over GLOB
target_sources(MyPlugin
    PRIVATE
        source/PluginProcessor.cpp
        source/PluginEditor.cpp
)

# If using GLOB, use CONFIGURE_DEPENDS
file(GLOB_RECURSE SOURCE_FILES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/source/*.cpp")
target_sources(MyPlugin PRIVATE ${SOURCE_FILES})
```

### Error: AU plugin not appearing in DAW

**Possible causes**:
1. Plugin failed auval validation
2. Manufacturer code doesn't start with uppercase
3. Plugin cache is stale

**Fix**:
```bash
# 1. Run auval to check
auval -strict -v aufx Mypl Nsdm

# 2. Check manufacturer code (first char must be uppercase for GarageBand)
# In CMakeLists.txt: PLUGIN_MANUFACTURER_CODE Nsdm  (N is uppercase)

# 3. Clear caches
killall -9 AudioComponentRegistrar
rm ~/Library/Caches/com.apple.audiounits.cache
```

### Error: "Cache is stale / mysterious build failures"

**Fix**: Delete the build directory and reconfigure:
```bash
rm -rf build
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
```

**CMake is very much a "turn it off and on again" piece of software.** When in doubt, nuke the build directory.

---

## Compile Flags for Audio Performance

### Optimization Flags

| Flag | Effect | Recommendation |
|------|--------|---------------|
| `-O0` | No optimization | Debug only |
| `-O2` | Good optimization | Safe for release |
| `-O3` | Aggressive optimization | Best for audio DSP |
| `-Os` | Optimize for size | Not recommended for audio |
| `-Ofast` | `-O3` + fast-math | Use with caution |

### Fast Math: Pros and Cons

`-ffast-math` enables several floating-point optimizations:

**What it does**:
- `-fno-math-errno` -- don't set errno for math functions
- `-funsafe-math-optimizations` -- allow reordering of FP operations
- `-ffinite-math-only` -- assume no NaN or Inf
- `-fno-rounding-math` -- assume default rounding mode
- `-fno-signaling-nans` -- no signaling NaN support
- `-fcx-limited-range` -- limited range for complex division
- **Enables flush-to-zero** -- denormal numbers become zero (GOOD for audio)

**Pros for audio**:
- Prevents denormal CPU spikes (biggest win)
- Faster math operations (10-30% DSP speedup)
- Enables SIMD auto-vectorization

**Cons for audio**:
- NaN/Inf values propagate silently (can cause silent output)
- Floating-point operations may be reordered (breaks some algorithms)
- `std::isnan()` and `std::isinf()` may not work
- Can change audible output of carefully tuned DSP

**Recommendation**: Use `-ffast-math` for the DSP processing code, but NOT for parameter handling or state management.

### Setting Flags in CMake

```cmake
# Per-target compile options
target_compile_options(MyPlugin
    PRIVATE
        $<$<CONFIG:Release>:-O3>
        $<$<CONFIG:Release>:-ffast-math>     # Optional: see pros/cons above
        $<$<CONFIG:Debug>:-O0>
        $<$<CONFIG:Debug>:-g>
)

# Or use JUCE's recommended flags (safe defaults)
target_link_libraries(MyPlugin
    PUBLIC
        juce::juce_recommended_config_flags    # Sensible defaults per config
        juce::juce_recommended_lto_flags       # Link-time optimization
        juce::juce_recommended_warning_flags   # Helpful warnings
)
```

### JUCE's Recommended Flags

These are provided by JUCE and handle platform differences automatically:

| Target | What It Adds |
|--------|-------------|
| `juce_recommended_config_flags` | `-O3` for Release, `-O0 -g` for Debug |
| `juce_recommended_lto_flags` | Link-time optimization for Release |
| `juce_recommended_warning_flags` | `-Wall -Wextra -Wpedantic` etc. |

### Denormal Prevention (Without -ffast-math)

If you don't use `-ffast-math`, handle denormals explicitly:

```cmake
# macOS/Linux: Set FTZ and DAZ flags at runtime
target_compile_definitions(MyPlugin
    PRIVATE
        JUCE_USE_VDSP_FRAMEWORK=1    # macOS vDSP (uses Accelerate framework)
)
```

```cpp
// In your processor's prepareToPlay()
#include <xmmintrin.h>
_mm_setcsr(_mm_getcsr() | 0x8040);  // Set FTZ and DAZ bits
```

### SIMD / Vectorization

```cmake
# Enable specific SIMD instruction sets
target_compile_options(MyPlugin
    PRIVATE
        $<$<CONFIG:Release>:-march=native>    # Use all CPU features available
        # Or be specific:
        # -msse4.2   (Intel SSE)
        # -mavx2     (Intel AVX2)
        # No flag needed for ARM NEON (always available on Apple Silicon)
)
```

**Warning**: `-march=native` optimizes for YOUR CPU. For distribution, use a safe baseline or build universal binaries.

---

## Advanced Configuration

### Sidechain Support

To enable sidechain (aux) input buses:

```cmake
juce_add_plugin(MySidechainPlugin
    ...
    # The buses API in your C++ code handles this
    # No special CMake flag needed
    ...
)
```

In your processor:
```cpp
MySidechainPlugin()
    : AudioProcessor(BusesProperties()
        .withInput("Input", juce::AudioChannelSet::stereo(), true)
        .withInput("Sidechain", juce::AudioChannelSet::mono(), true)
        .withOutput("Output", juce::AudioChannelSet::stereo(), true))
{}
```

### Multiple Plugin Formats

```cmake
juce_add_plugin(MyPlugin
    FORMATS
        AU              # Audio Unit v2 (macOS only)
        AUv3            # Audio Unit v3 (macOS/iOS, Xcode generator only)
        VST3            # VST3 (all platforms)
        Standalone      # Standalone application
        # AAX           # Pro Tools (requires AAX SDK)
        # LV2           # Linux (JUCE 7+)
        # Unity         # Unity game engine
)
```

### Setting SDK Paths

For AAX or VST2 support (if you have licenses):

```cmake
# AAX SDK path (Pro Tools)
juce_set_aax_sdk_path("/path/to/AAX_SDK")

# VST2 SDK path (deprecated, requires license)
# juce_set_vst2_sdk_path("/path/to/VST2_SDK")
```

### Plugin Category/Type for VST3

```cmake
juce_add_plugin(MyPlugin
    ...
    VST3_CATEGORIES "Fx" "Dynamics"    # VST3 category tags
    ...
)
```

Common VST3 categories: `Fx`, `Instrument`, `Analyzer`, `Delay`, `Distortion`, `Dynamics`, `EQ`, `Filter`, `Generator`, `Mastering`, `Modulation`, `Reverb`, `Spatial`, `Synth`, `Tools`

### Using CPM for Dependency Management

For a more modern approach (used by Pamplejuce template):

```cmake
# Download CPM.cmake
file(DOWNLOAD
    https://github.com/cpm-cmake/CPM.cmake/releases/latest/download/CPM.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/cmake/CPM.cmake
)
include(${CMAKE_CURRENT_BINARY_DIR}/cmake/CPM.cmake)

# Add JUCE via CPM
CPMAddPackage(
    NAME JUCE
    GITHUB_REPOSITORY juce-framework/JUCE
    GIT_TAG 8.0.0
)
```

### Unit Testing with Catch2

```cmake
# Add test executable
CPMAddPackage("gh:catchorg/Catch2@3.7.1")

add_executable(MyPluginTests
    tests/PluginProcessorTest.cpp
)

target_link_libraries(MyPluginTests
    PRIVATE
        Catch2::Catch2WithMain
        MyPlugin                # Link against plugin target
)

# Register with CTest
include(CTest)
include(Catch)
catch_discover_tests(MyPluginTests)
```

---

## CI/CD and Distribution

### GitHub Actions Workflow (Minimal)

```yaml
# .github/workflows/build.yml
name: Build Plugin

on: [push, pull_request]

jobs:
  build:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive

      - name: Configure
        run: cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64"

      - name: Build
        run: cmake --build build --config Release --parallel $(sysctl -n hw.ncpu)

      - name: Validate AU
        run: auval -strict -v aufx Mypl Nsdm

      - name: Upload Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: MyPlugin
          path: |
            build/MyPlugin_artefacts/Release/VST3/
            build/MyPlugin_artefacts/Release/AU/
```

### Pluginval Integration

```bash
# Install pluginval
brew install pluginval

# Validate VST3
pluginval --strictness-level 5 "build/MyPlugin_artefacts/Release/VST3/My Plugin.vst3"

# Validate AU
pluginval --strictness-level 5 "build/MyPlugin_artefacts/Release/AU/My Plugin.component"
```

### Code Signing and Notarization

```bash
# Sign for distribution
codesign --force --sign "Developer ID Application: Your Name (TEAMID)" \
    --options runtime --timestamp \
    "My Plugin.vst3"

# Create ZIP for notarization
ditto -c -k --keepParent "My Plugin.vst3" "MyPlugin.zip"

# Submit for notarization
xcrun notarytool submit "MyPlugin.zip" \
    --apple-id "your@email.com" \
    --team-id "TEAMID" \
    --password "app-specific-password" \
    --wait

# Staple
xcrun stapler staple "My Plugin.vst3"
```

---

## Quick Reference: Build Commands Cheat Sheet

```bash
# === First-Time Setup ===
cd ~/Development/AudioPlugins/MyPlugin
git submodule update --init --recursive

# === Debug Build (Development) ===
cmake -B build -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build --parallel $(sysctl -n hw.ncpu)

# === Release Build (Distribution) ===
cmake -B build-release \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64" \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=10.15
cmake --build build-release --parallel $(sysctl -n hw.ncpu)

# === Clean Rebuild ===
cmake --build build --clean-first

# === Nuclear Clean ===
rm -rf build && cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build

# === Validate ===
auval -strict -v aufx Mypl Nsdm

# === Find Built Plugins ===
find build -name "*.vst3" -o -name "*.component" -o -name "*.app"
```

---

## References

- [JUCE CMake API Documentation](https://github.com/juce-framework/JUCE/blob/master/docs/CMake%20API.md)
- [JUCE Official CMake AudioPlugin Example](https://github.com/juce-framework/JUCE/blob/master/examples/CMake/AudioPlugin/CMakeLists.txt)
- [Pamplejuce Template (JUCE 8 + CMake + CI/CD)](https://github.com/sudara/pamplejuce)
- [How to Use CMake with JUCE - Melatonin](https://melatonin.dev/blog/how-to-use-cmake-with-juce/)
- [WolfSound - Build Audio Plugin with JUCE and CMake](https://thewolfsound.com/how-to-build-audio-plugin-with-juce-cpp-framework-cmake-and-unit-tests/)
- [JUCE CMake Plugin Template](https://github.com/anthonyalfimov/JUCE-CMake-Plugin-Template)
- [JUCE Forum - CMake Universal Binary](https://forum.juce.com/t/cmake-plugin-and-os-11-universal-binary/41997)
