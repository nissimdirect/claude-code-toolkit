# PyDub 0.25.1 - Audio Manipulation Reference

> Simple, high-level audio manipulation in Python.
> Install: `pip install pydub`
> Requires: ffmpeg (`brew install ffmpeg`)
> Docs: https://github.com/jiaaro/pydub
> API: https://github.com/jiaaro/pydub/blob/master/API.markdown

---

## Table of Contents

1. [Loading Audio](#loading-audio)
2. [AudioSegment Properties](#audiosegment-properties)
3. [Slicing and Duration](#slicing-and-duration)
4. [Concatenation and Overlay](#concatenation-and-overlay)
5. [Volume Manipulation](#volume-manipulation)
6. [Effects](#effects)
7. [Silence Detection and Splitting](#silence-detection-and-splitting)
8. [Channel Manipulation](#channel-manipulation)
9. [Export and Format Conversion](#export-and-format-conversion)
10. [Generators (Creating Audio)](#generators-creating-audio)
11. [Playback](#playback)
12. [Use Cases](#use-cases)

---

## Loading Audio

PyDub uses ffmpeg as its backend. WAV files can be loaded with pure Python; all other formats require ffmpeg.

```python
from pydub import AudioSegment

# WAV files (pure Python, no ffmpeg needed)
audio = AudioSegment.from_wav("file.wav")

# MP3 files
audio = AudioSegment.from_mp3("file.mp3")

# OGG files
audio = AudioSegment.from_ogg("file.ogg")

# Generic loader (any ffmpeg-supported format)
audio = AudioSegment.from_file("file.mp4", format="mp4")
audio = AudioSegment.from_file("file.wma", format="wma")
audio = AudioSegment.from_file("file.aac", format="aac")
audio = AudioSegment.from_file("file.flac", format="flac")
audio = AudioSegment.from_file("file.m4a", format="m4a")

# From raw audio data
audio = AudioSegment.from_raw(
    raw_data,            # bytes
    sample_width=2,      # bytes per sample (2 = 16-bit)
    frame_rate=44100,    # sample rate
    channels=2           # stereo
)

# From file-like object (BytesIO, HTTP response, etc.)
from io import BytesIO
audio = AudioSegment.from_file(BytesIO(raw_bytes), format="mp3")

# Create silence
silence = AudioSegment.silent(duration=1000)  # 1 second of silence
silence = AudioSegment.silent(duration=500, frame_rate=44100)

# Create empty AudioSegment
empty = AudioSegment.empty()
```

---

## AudioSegment Properties

All AudioSegment objects are **immutable**. Operations return new objects.

```python
audio = AudioSegment.from_wav("file.wav")

# Duration
len(audio)                  # Duration in milliseconds (int)
audio.duration_seconds      # Duration in seconds (float)

# Audio format info
audio.channels              # Number of channels (1=mono, 2=stereo)
audio.sample_width          # Bytes per sample (1=8bit, 2=16bit, 3=24bit, 4=32bit)
audio.frame_rate            # Sample rate in Hz (e.g., 44100)
audio.frame_width           # sample_width * channels (bytes per frame)
audio.frame_count()         # Total number of frames

# Loudness
audio.dBFS                  # RMS loudness in dBFS (0 = digital max)
audio.max                   # Maximum sample value (absolute)
audio.max_dBFS              # Peak level in dBFS
audio.rms                   # RMS value (not in dB)

# Raw data
audio.raw_data              # Raw bytes of audio data
audio.get_array_of_samples()  # Array of sample values (array.array)

# Convert to numpy (for analysis)
import numpy as np
samples = np.array(audio.get_array_of_samples())
# For stereo, samples are interleaved: [L, R, L, R, ...]
# Reshape: samples.reshape((-1, audio.channels))
```

---

## Slicing and Duration

All time values are in **milliseconds**.

```python
audio = AudioSegment.from_wav("file.wav")

# Basic slicing (in milliseconds)
first_10s = audio[:10000]           # First 10 seconds
last_5s = audio[-5000:]             # Last 5 seconds
middle = audio[10000:20000]         # 10s to 20s
every_other_second = audio[::2000]  # (Not supported - use loop)

# Time constants (for readability)
SECOND = 1000
MINUTE = 60 * SECOND

intro = audio[:30 * SECOND]         # First 30 seconds
outro = audio[-15 * SECOND:]        # Last 15 seconds

# Get specific time range
def get_segment(audio, start_s, end_s):
    """Extract segment by seconds."""
    return audio[int(start_s * 1000):int(end_s * 1000)]

verse = get_segment(audio, 15.0, 45.0)
```

---

## Concatenation and Overlay

### Concatenation (Sequential)

```python
# Simple concatenation (one after another)
combined = audio1 + audio2
combined = audio1 + audio2 + audio3

# With crossfade (smooth transition)
combined = audio1.append(audio2, crossfade=1500)  # 1.5s crossfade
combined = audio1.append(audio2, crossfade=0)     # No crossfade (same as +)

# Repeat/loop
looped = audio * 4          # Repeat 4 times
looped = audio * 2 + outro  # Loop then end

# Build a playlist
from functools import reduce
tracks = [track1, track2, track3, track4]
playlist = reduce(lambda a, b: a.append(b, crossfade=2000), tracks)
```

### Overlay (Simultaneous / Mixing)

```python
# Overlay audio2 on top of audio1 (mix together)
mixed = audio1.overlay(audio2)

# Overlay starting at specific position
mixed = audio1.overlay(audio2, position=5000)  # Start audio2 at 5s mark

# Overlay with gain adjustment
mixed = audio1.overlay(audio2 - 6)  # audio2 6dB quieter

# Overlay and loop the shorter track
mixed = audio1.overlay(audio2, loop=True)  # Loop audio2 for duration of audio1

# Overlay with specific number of loops
mixed = audio1.overlay(audio2, times=3)  # Play audio2 3 times

# Layer multiple sounds
beat = AudioSegment.from_wav("beat.wav")
bass = AudioSegment.from_wav("bass.wav")
synth = AudioSegment.from_wav("synth.wav")
mix = beat.overlay(bass).overlay(synth - 3)
```

---

## Volume Manipulation

```python
audio = AudioSegment.from_wav("file.wav")

# Adjust volume in dB
louder = audio + 6          # Boost by 6 dB
quieter = audio - 3         # Reduce by 3 dB
much_louder = audio + 12    # Boost by 12 dB

# Apply specific gain
gained = audio.apply_gain(6.0)  # Same as audio + 6

# Apply different gain to left/right channels (stereo only)
panned = audio.apply_gain_stereo(-3.0, +3.0)  # Left -3dB, Right +3dB

# Pan (stereo field positioning)
panned = audio.pan(-0.5)    # Pan left (-1.0 to +1.0)
panned = audio.pan(+0.5)    # Pan right

# Get current loudness
print(f"RMS: {audio.dBFS:.1f} dBFS")
print(f"Peak: {audio.max_dBFS:.1f} dBFS")
```

---

## Effects

### Fade In / Fade Out

```python
# Linear fade
faded = audio.fade_in(2000)          # 2s fade in
faded = audio.fade_out(3000)         # 3s fade out
faded = audio.fade_in(2000).fade_out(3000)  # Both

# Fade at specific position
faded = audio.fade(from_gain=-120, to_gain=0, start=0, end=2000)
# from_gain/to_gain in dB relative to current level

# Crossfade between two tracks
transition = audio1[-2000:].fade(to_gain=-120, start=0, end=2000)
transition = transition.overlay(audio2[:2000].fade(from_gain=-120, start=0, end=2000))
```

### Normalize

Boost signal so the peak reaches a specified headroom below 0 dBFS.

```python
from pydub.effects import normalize

# Normalize to -0.1 dBFS headroom (default)
normalized = normalize(audio)

# Normalize with specific headroom
normalized = normalize(audio, headroom=1.0)  # Peak at -1.0 dBFS
normalized = normalize(audio, headroom=3.0)  # Peak at -3.0 dBFS

# Check levels after normalization
print(f"Peak after normalize: {normalized.max_dBFS:.1f} dBFS")
```

### Compress Dynamic Range

Simple dynamics compressor.

```python
from pydub.effects import compress_dynamic_range

compressed = compress_dynamic_range(
    audio,
    threshold=-20.0,   # dBFS threshold (compress above this)
    ratio=4.0,         # Compression ratio (4:1)
    attack=5.0,        # Attack time in ms
    release=50.0       # Release time in ms
)

# Heavy compression (limiting)
limited = compress_dynamic_range(audio, threshold=-6.0, ratio=20.0,
                                  attack=0.5, release=20.0)

# Gentle compression
gentle = compress_dynamic_range(audio, threshold=-30.0, ratio=2.0,
                                 attack=10.0, release=100.0)
```

### Reverse

```python
reversed_audio = audio.reverse()
```

### Speed Change

```python
# Speed up (also raises pitch)
def speed_change(audio, speed=1.0):
    """Change playback speed. >1.0 = faster, <1.0 = slower."""
    new_frame_rate = int(audio.frame_rate * speed)
    return audio._spawn(audio.raw_data, overrides={
        "frame_rate": new_frame_rate
    }).set_frame_rate(audio.frame_rate)

faster = speed_change(audio, 1.25)  # 25% faster
slower = speed_change(audio, 0.75)  # 25% slower
```

### Low Pass / High Pass Filter

```python
from pydub.effects import low_pass_filter, high_pass_filter

# Low pass filter (remove highs)
filtered = low_pass_filter(audio, cutoff=3000)  # Cut above 3 kHz

# High pass filter (remove lows)
filtered = high_pass_filter(audio, cutoff=80)   # Cut below 80 Hz

# Bandpass (combine both)
bandpassed = high_pass_filter(low_pass_filter(audio, 5000), 200)

# Telephone effect
telephone = high_pass_filter(low_pass_filter(audio, 3400), 300)
telephone = telephone - 6  # Reduce volume slightly
```

### Strip Silence

```python
from pydub.effects import strip_silence

# Remove silence from beginning and end
stripped = strip_silence(audio, silence_len=100, silence_thresh=-40)
# silence_len: minimum silence length to strip (ms)
# silence_thresh: dBFS below which is "silence"
```

---

## Silence Detection and Splitting

### Detect Silence

```python
from pydub.silence import detect_silence, detect_nonsilent

# Find all silent sections
silent_ranges = detect_silence(audio,
    min_silence_len=500,     # Minimum 500ms to count as silence
    silence_thresh=-40,      # dBFS threshold for silence
    seek_step=10             # Check every 10ms (speed vs precision)
)
# Returns: list of [start_ms, end_ms] pairs
# Example: [[0, 1200], [5400, 5900], [12000, 12800]]

# Find all non-silent sections
speaking_ranges = detect_nonsilent(audio,
    min_silence_len=500,
    silence_thresh=-40,
    seek_step=10
)
# Returns: list of [start_ms, end_ms] for non-silent parts
```

### Split on Silence

```python
from pydub.silence import split_on_silence

# Split audio at silent points
chunks = split_on_silence(audio,
    min_silence_len=500,     # Min silence duration to split (ms)
    silence_thresh=-40,      # Silence threshold (dBFS)
    keep_silence=200,        # Keep 200ms of silence at edges (or True/False)
    seek_step=10             # Precision of silence detection (ms)
)
# Returns: list of AudioSegment chunks

# Export each chunk
for i, chunk in enumerate(chunks):
    chunk.export(f"chunk_{i:03d}.wav", format="wav")

# Useful for: splitting podcast at pauses, extracting phrases, etc.
```

---

## Channel Manipulation

```python
audio = AudioSegment.from_wav("stereo.wav")

# Convert stereo to mono
mono = audio.set_channels(1)

# Convert mono to stereo (duplicates channel)
stereo = audio.set_channels(2)

# Split stereo into separate mono channels
channels = audio.split_to_mono()
left_channel = channels[0]     # Left
right_channel = channels[1]    # Right

# Export channels separately
left_channel.export("left.wav", format="wav")
right_channel.export("right.wav", format="wav")

# Combine two mono tracks into stereo
from pydub import AudioSegment
stereo = AudioSegment.from_mono_audiosegments(left_channel, right_channel)

# Change sample rate
resampled = audio.set_frame_rate(48000)  # Resample to 48kHz

# Change sample width (bit depth)
audio_16bit = audio.set_sample_width(2)  # 16-bit
audio_24bit = audio.set_sample_width(3)  # 24-bit
audio_32bit = audio.set_sample_width(4)  # 32-bit
```

---

## Export and Format Conversion

```python
audio = AudioSegment.from_wav("input.wav")

# Basic export
audio.export("output.mp3", format="mp3")
audio.export("output.wav", format="wav")
audio.export("output.ogg", format="ogg")
audio.export("output.flac", format="flac")
audio.export("output.aac", format="adts")  # AAC

# With bitrate control
audio.export("output.mp3", format="mp3", bitrate="320k")
audio.export("output.mp3", format="mp3", bitrate="192k")
audio.export("output.mp3", format="mp3", bitrate="128k")

# With metadata tags
audio.export("output.mp3", format="mp3",
    bitrate="320k",
    tags={
        'artist': 'nissimdirect',
        'album': 'My Album',
        'title': 'Track Name',
        'track': '1',
        'genre': 'Electronic',
        'year': '2026',
    }
)

# With album art
audio.export("output.mp3", format="mp3",
    tags={'artist': 'Artist'},
    cover="cover.jpg"
)

# With custom ffmpeg parameters
audio.export("output.mp3", format="mp3",
    parameters=["-q:a", "0"]  # VBR V0 quality (highest quality VBR)
)

# Custom codec
audio.export("output.ogg", format="ogg",
    codec="libvorbis",
    parameters=["-q:a", "8"]  # Quality 8/10
)

# Export to BytesIO (in-memory)
from io import BytesIO
buffer = BytesIO()
audio.export(buffer, format="mp3", bitrate="320k")
mp3_bytes = buffer.getvalue()

# Batch conversion
import os
for filename in os.listdir("input_folder"):
    if filename.endswith(".wav"):
        audio = AudioSegment.from_wav(f"input_folder/{filename}")
        name = os.path.splitext(filename)[0]
        audio.export(f"output_folder/{name}.mp3", format="mp3", bitrate="320k")
```

### Common Export Settings

| Format | Extension | Typical Bitrate | Notes |
|--------|-----------|----------------|-------|
| WAV | .wav | N/A (lossless) | Uncompressed, large files |
| FLAC | .flac | N/A (lossless) | Compressed lossless, ~60% of WAV |
| MP3 CBR | .mp3 | 128k-320k | Constant bitrate |
| MP3 VBR | .mp3 | V0-V9 | Variable bitrate (V0 = best) |
| OGG Vorbis | .ogg | q0-q10 | Open format, good quality |
| AAC | .m4a/.aac | 128k-256k | Apple ecosystem |

---

## Generators (Creating Audio)

```python
from pydub.generators import Sine, Square, Sawtooth, WhiteNoise, Pulse

# Generate sine wave
tone = Sine(440).to_audio_segment(duration=1000)  # 440 Hz for 1 second
tone = Sine(440).to_audio_segment(duration=1000, volume=-20.0)  # At -20 dBFS

# Generate square wave
square = Square(440).to_audio_segment(duration=1000)

# Generate sawtooth wave
saw = Sawtooth(440).to_audio_segment(duration=1000)

# Generate white noise
noise = WhiteNoise().to_audio_segment(duration=1000)
noise = WhiteNoise().to_audio_segment(duration=5000, volume=-30.0)

# Generate pulse wave (variable duty cycle)
pulse = Pulse(440, duty_cycle=0.25).to_audio_segment(duration=1000)

# Build a test tone sequence (DTMF-style)
frequencies = [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88, 523.25]
scale = AudioSegment.empty()
for freq in frequencies:
    tone = Sine(freq).to_audio_segment(duration=300, volume=-20.0)
    tone = tone.fade_in(10).fade_out(50)
    scale += tone + AudioSegment.silent(duration=100)

scale.export("c_major_scale.wav", format="wav")

# Generate test signals for plugin testing
test_sweep = AudioSegment.empty()
for freq in range(20, 20001, 100):  # 20 Hz to 20 kHz
    tone = Sine(freq).to_audio_segment(duration=50, volume=-12.0)
    test_sweep += tone
test_sweep.export("frequency_sweep.wav", format="wav")
```

---

## Playback

```python
from pydub import AudioSegment
from pydub.playback import play

# Simple playback (requires simpleaudio, pyaudio, ffplay, or avplay)
audio = AudioSegment.from_wav("file.wav")
play(audio)

# Play a slice
play(audio[:5000])  # Play first 5 seconds

# Play with effects
play(audio.fade_in(1000) + 6)  # Fade in and boost
```

**Playback backends** (install one):
- `pip install simpleaudio` (recommended)
- `pip install pyaudio`
- ffplay (comes with ffmpeg)

---

## Use Cases

### 1. Preparing Test Audio for Plugin Testing

```python
from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise

def create_plugin_test_suite(output_dir="test_audio"):
    """Generate a suite of test audio files for plugin validation."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    # 1. Sine waves at standard frequencies
    for freq in [100, 440, 1000, 5000, 10000]:
        tone = Sine(freq).to_audio_segment(duration=5000, volume=-12.0)
        tone.export(f"{output_dir}/sine_{freq}hz.wav", format="wav")

    # 2. White noise
    noise = WhiteNoise().to_audio_segment(duration=5000, volume=-18.0)
    noise.export(f"{output_dir}/white_noise.wav", format="wav")

    # 3. Silence (for noise floor testing)
    silence = AudioSegment.silent(duration=5000, frame_rate=44100)
    silence.export(f"{output_dir}/silence.wav", format="wav")

    # 4. Impulse (for impulse response testing)
    impulse = AudioSegment.silent(duration=1000, frame_rate=44100)
    # Create a single-sample impulse at 100ms
    samples = impulse.get_array_of_samples()
    samples[int(0.1 * 44100)] = 32767  # Max value at 100ms
    impulse = impulse._spawn(samples.tobytes())
    impulse.export(f"{output_dir}/impulse.wav", format="wav")

    # 5. Frequency sweep
    sweep = AudioSegment.empty()
    for freq in [50, 100, 200, 500, 1000, 2000, 5000, 10000, 15000]:
        tone = Sine(freq).to_audio_segment(duration=500, volume=-12.0)
        tone = tone.fade_in(10).fade_out(10)
        sweep += tone
    sweep.export(f"{output_dir}/frequency_sweep.wav", format="wav")

    # 6. Dynamic range test (quiet to loud)
    dynamic = AudioSegment.empty()
    for vol in [-60, -48, -36, -24, -12, -6, -3, 0]:
        tone = Sine(1000).to_audio_segment(duration=1000, volume=vol)
        dynamic += tone
    dynamic.export(f"{output_dir}/dynamic_range.wav", format="wav")

    print(f"Test suite created in {output_dir}/")

create_plugin_test_suite()
```

### 2. Batch Processing Audio Files

```python
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter, compress_dynamic_range
import os

def batch_process(input_dir, output_dir, target_loudness=-14.0):
    """Normalize and prepare a batch of audio files."""
    os.makedirs(output_dir, exist_ok=True)

    for filename in sorted(os.listdir(input_dir)):
        if not filename.lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
            continue

        filepath = os.path.join(input_dir, filename)
        audio = AudioSegment.from_file(filepath)

        # Remove DC offset / rumble
        audio = high_pass_filter(audio, cutoff=30)

        # Light compression
        audio = compress_dynamic_range(audio,
            threshold=-24.0, ratio=2.0,
            attack=10.0, release=100.0)

        # Normalize
        audio = normalize(audio, headroom=1.0)

        # Target loudness (simple approximation)
        current_loudness = audio.dBFS
        adjustment = target_loudness - current_loudness
        audio = audio + adjustment

        # Export
        name = os.path.splitext(filename)[0]
        output_path = os.path.join(output_dir, f"{name}.wav")
        audio.export(output_path, format="wav")
        print(f"Processed: {filename} -> {audio.dBFS:.1f} dBFS")

batch_process("raw_audio/", "processed_audio/")
```

### 3. Quick Audio Format Conversion

```python
from pydub import AudioSegment
import os

def convert_directory(input_dir, output_format="mp3", bitrate="320k"):
    """Convert all audio files in a directory to a target format."""
    output_dir = f"{input_dir}_{output_format}"
    os.makedirs(output_dir, exist_ok=True)

    supported = ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wma')

    for filename in os.listdir(input_dir):
        if not filename.lower().endswith(supported):
            continue

        input_path = os.path.join(input_dir, filename)
        name = os.path.splitext(filename)[0]
        output_path = os.path.join(output_dir, f"{name}.{output_format}")

        try:
            audio = AudioSegment.from_file(input_path)
            export_args = {"format": output_format}
            if output_format in ("mp3", "aac"):
                export_args["bitrate"] = bitrate
            audio.export(output_path, **export_args)
            print(f"Converted: {filename}")
        except Exception as e:
            print(f"Failed: {filename} - {e}")

# Convert WAVs to high-quality MP3s
convert_directory("stems/", "mp3", "320k")

# Convert to FLAC for archival
convert_directory("masters/", "flac")
```

---

## Quick Reference

```python
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
from pydub.effects import low_pass_filter, high_pass_filter
from pydub.silence import split_on_silence, detect_silence, detect_nonsilent
from pydub.generators import Sine, Square, Sawtooth, WhiteNoise, Pulse
from pydub.playback import play

# Load
audio = AudioSegment.from_file("file.wav")

# Info
print(f"Duration: {audio.duration_seconds:.1f}s")
print(f"Channels: {audio.channels}")
print(f"Sample rate: {audio.frame_rate} Hz")
print(f"Bit depth: {audio.sample_width * 8} bit")
print(f"Loudness: {audio.dBFS:.1f} dBFS")
print(f"Peak: {audio.max_dBFS:.1f} dBFS")

# Process
processed = normalize(audio, headroom=1.0)
processed = high_pass_filter(processed, cutoff=80)

# Export
processed.export("output.wav", format="wav")
```
