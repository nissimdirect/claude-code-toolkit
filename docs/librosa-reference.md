# Librosa 0.11.0 - Audio Analysis Reference

> Python library for audio and music signal analysis.
> Install: `pip install librosa`
> Docs: https://librosa.org/doc/0.11.0/

---

## Table of Contents

1. [Loading Audio](#loading-audio)
2. [Spectral Representations](#spectral-representations)
3. [Spectral Features](#spectral-features)
4. [Rhythm and Tempo Analysis](#rhythm-and-tempo-analysis)
5. [Onset Detection](#onset-detection)
6. [Pitch Detection and Tracking](#pitch-detection-and-tracking)
7. [Audio Effects](#audio-effects)
8. [Display Utilities](#display-utilities)
9. [Magnitude Scaling Utilities](#magnitude-scaling-utilities)
10. [Feature Manipulation](#feature-manipulation)
11. [Integration with soundfile](#integration-with-soundfile)
12. [Use Cases for Plugin Development](#use-cases-for-plugin-development)

---

## Loading Audio

### librosa.load()

Loads an audio file as a floating-point time series (NumPy array).

```python
import librosa
import numpy as np

# Basic load - resamples to 22050 Hz mono by default
y, sr = librosa.load('audio.wav')
# y: np.ndarray shape (n_samples,)
# sr: int (sample rate)

# Load at native sample rate (no resampling)
y, sr = librosa.load('audio.wav', sr=None)

# Load at specific sample rate
y, sr = librosa.load('audio.wav', sr=44100)

# Load stereo (don't mix to mono)
y, sr = librosa.load('audio.wav', mono=False)
# y shape: (n_channels, n_samples) for stereo

# Load a specific time range (in seconds)
y, sr = librosa.load('audio.wav', offset=10.0, duration=5.0)

# Load one of librosa's built-in example files
filename = librosa.example('nutcracker')
y, sr = librosa.load(filename)
# Available examples: 'nutcracker', 'trumpet', 'brahms', 'choice', etc.
```

**Key Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `path` | required | Path to audio file (WAV, MP3, FLAC, OGG, etc.) |
| `sr` | 22050 | Target sample rate. Use `None` for native rate |
| `mono` | True | Mix to mono if True |
| `offset` | 0.0 | Start reading at this time (seconds) |
| `duration` | None | Load only this much audio (seconds). None = entire file |
| `dtype` | np.float32 | Data type for the output array |
| `res_type` | 'soxr_hq' | Resampling algorithm |

**Important Notes:**
- Audio is always returned as float32 in range [-1.0, 1.0]
- Default sr=22050 is standard for MIR (Music Information Retrieval) but too low for production audio. Use sr=44100 or sr=None for production work.
- Uses soundfile as backend for I/O; falls back to audioread for unsupported formats

---

## Spectral Representations

### STFT (Short-Time Fourier Transform)

The foundation of most librosa analysis. Converts time-domain signal to time-frequency representation.

```python
# Compute STFT
D = librosa.stft(y, n_fft=2048, hop_length=512, win_length=None, window='hann')
# D: complex np.ndarray shape (1 + n_fft/2, n_frames)
# D.shape example: (1025, 431) for ~10s at sr=22050

# Get magnitude and phase separately
magnitude, phase = librosa.magphase(D)

# Get magnitude spectrogram (power=1 for amplitude, power=2 for power)
S = np.abs(D)           # Amplitude spectrogram
S_power = np.abs(D)**2  # Power spectrogram

# Convert to dB scale for visualization
S_db = librosa.amplitude_to_db(S, ref=np.max)

# Inverse STFT (reconstruct audio from STFT)
y_reconstructed = librosa.istft(D, hop_length=512)
```

**STFT Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `y` | required | Audio time series |
| `n_fft` | 2048 | FFT window size (frequency resolution) |
| `hop_length` | None | Hop between frames. Default = win_length // 4 |
| `win_length` | None | Window length. Default = n_fft |
| `window` | 'hann' | Window function (string, tuple, or array) |
| `center` | True | Center-pad the signal |
| `pad_mode` | 'constant' | Padding mode for centered frames |

**Frequency resolution:** `sr / n_fft` Hz per bin. With sr=22050, n_fft=2048: ~10.7 Hz per bin.

**Time resolution:** `hop_length / sr` seconds per frame. With hop=512, sr=22050: ~23ms per frame.

### Mel Spectrogram

Maps the STFT to the mel scale (perceptual frequency scale closer to human hearing).

```python
# Compute mel spectrogram directly from audio
S_mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000)
# S_mel shape: (n_mels, n_frames), e.g., (128, 431)

# Convert to dB for visualization
S_mel_db = librosa.power_to_db(S_mel, ref=np.max)

# Compute from pre-computed STFT (more efficient if you need both)
S = np.abs(librosa.stft(y))**2
S_mel = librosa.feature.melspectrogram(S=S, sr=sr, n_mels=128)

# Custom frequency range for specific analysis
S_mel_low = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmin=20, fmax=2000)
S_mel_high = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmin=2000, fmax=16000)
```

**Mel Spectrogram Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `y` | None | Audio time series |
| `sr` | 22050 | Sample rate |
| `S` | None | Pre-computed power spectrogram (use instead of y) |
| `n_fft` | 2048 | FFT window size |
| `hop_length` | 512 | Hop length between frames |
| `n_mels` | 128 | Number of mel bands |
| `fmin` | 0.0 | Lowest frequency (Hz) |
| `fmax` | None | Highest frequency (Hz). None = sr/2 |
| `power` | 2.0 | Exponent for magnitude spectrogram |

### Constant-Q Transform (CQT)

Logarithmically-spaced frequency bins. Better frequency resolution at low frequencies.

```python
# Compute CQT
C = librosa.cqt(y=y, sr=sr, hop_length=512, fmin=None, n_bins=84, bins_per_octave=12)
# Default: 7 octaves (84 bins / 12 per octave), starting at C1 (~32.7 Hz)

C_db = librosa.amplitude_to_db(np.abs(C), ref=np.max)
```

---

## Spectral Features

### MFCC (Mel-Frequency Cepstral Coefficients)

Compact representation of the spectral envelope. Standard in speech/music analysis.

```python
# Compute MFCCs
mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
# mfcc shape: (n_mfcc, n_frames), e.g., (13, 431)

# From pre-computed mel spectrogram
S_mel = librosa.feature.melspectrogram(y=y, sr=sr)
mfcc = librosa.feature.mfcc(S=librosa.power_to_db(S_mel), n_mfcc=20)

# Compute delta (first derivative) and delta-delta (second derivative)
mfcc_delta = librosa.feature.delta(mfcc)
mfcc_delta2 = librosa.feature.delta(mfcc, order=2)

# Stack all features
mfcc_full = np.vstack([mfcc, mfcc_delta, mfcc_delta2])
# Shape: (39, n_frames) for n_mfcc=13
```

**MFCC Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `y` | None | Audio time series |
| `sr` | 22050 | Sample rate |
| `S` | None | Pre-computed log-power mel spectrogram |
| `n_mfcc` | 20 | Number of MFCCs to return |
| `n_fft` | 2048 | FFT window size |
| `hop_length` | 512 | Hop length |
| `n_mels` | 128 | Number of mel bands |
| `fmin` | 0.0 | Lowest frequency |
| `fmax` | None | Highest frequency |

### Chroma Features

Represents the 12 pitch classes (C, C#, D, ..., B). Great for harmonic analysis.

```python
# Chroma from STFT
chroma_stft = librosa.feature.chroma_stft(y=y, sr=sr, n_chroma=12)
# Shape: (12, n_frames)

# Chroma from CQT (generally better for music)
chroma_cqt = librosa.feature.chroma_cqt(y=y, sr=sr)

# CENS (Chroma Energy Normalized Statistics) - good for cover song detection
chroma_cens = librosa.feature.chroma_cens(y=y, sr=sr)

# Use harmonic component for cleaner chroma
y_harmonic = librosa.effects.harmonic(y)
chroma_harm = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr)
```

### Spectral Centroid

The "center of mass" of the spectrum. Correlates with brightness / perceived timbre.

```python
cent = librosa.feature.spectral_centroid(y=y, sr=sr)
# Shape: (1, n_frames)

# Higher values = brighter sound, lower values = darker/warmer
# Typical ranges: bass 200-800 Hz, vocals 1000-4000 Hz, cymbals 5000-15000 Hz
```

### Spectral Bandwidth

Width of the spectrum around the centroid.

```python
bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
# Shape: (1, n_frames)
```

### Spectral Rolloff

Frequency below which a specified percentage of total spectral energy lies.

```python
rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)
# Shape: (1, n_frames)
# roll_percent=0.85 means 85% of energy is below this frequency
```

### Spectral Contrast

Difference between peaks and valleys in the spectrum across sub-bands.

```python
contrast = librosa.feature.spectral_contrast(y=y, sr=sr, n_bands=6)
# Shape: (n_bands + 1, n_frames), e.g., (7, 431)
```

### Spectral Flatness

Measure of how noise-like vs. tone-like a signal is (0 = tonal, 1 = noise).

```python
flatness = librosa.feature.spectral_flatness(y=y)
# Shape: (1, n_frames)
```

### Zero Crossing Rate

Rate at which the signal changes sign. Higher for noisy/percussive content.

```python
zcr = librosa.feature.zero_crossing_rate(y)
# Shape: (1, n_frames)
```

### RMS Energy

Root-mean-square energy per frame.

```python
rms = librosa.feature.rms(y=y)
# Shape: (1, n_frames)
```

### Tonnetz (Tonal Centroid Features)

6-dimensional tonal space representation (fifths, minor thirds, major thirds).

```python
tonnetz = librosa.feature.tonnetz(y=y, sr=sr)
# Shape: (6, n_frames)
```

### Complete Feature Extraction Example

```python
import librosa
import numpy as np

y, sr = librosa.load('track.wav', sr=22050)

# Extract all common features
features = {
    'mfcc': librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13),
    'chroma': librosa.feature.chroma_cqt(y=y, sr=sr),
    'spectral_centroid': librosa.feature.spectral_centroid(y=y, sr=sr),
    'spectral_bandwidth': librosa.feature.spectral_bandwidth(y=y, sr=sr),
    'spectral_rolloff': librosa.feature.spectral_rolloff(y=y, sr=sr),
    'spectral_contrast': librosa.feature.spectral_contrast(y=y, sr=sr),
    'spectral_flatness': librosa.feature.spectral_flatness(y=y),
    'zero_crossing_rate': librosa.feature.zero_crossing_rate(y),
    'rms': librosa.feature.rms(y=y),
    'tonnetz': librosa.feature.tonnetz(y=y, sr=sr),
}

# Print shapes
for name, feat in features.items():
    print(f"{name}: {feat.shape}")

# Aggregate over time for a single feature vector per track
summary = {}
for name, feat in features.items():
    summary[f"{name}_mean"] = np.mean(feat, axis=1)
    summary[f"{name}_std"] = np.std(feat, axis=1)
```

---

## Rhythm and Tempo Analysis

### Beat Tracking

```python
# Detect beats and estimate tempo
tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
# tempo: estimated BPM (float or ndarray)
# beat_frames: frame indices where beats occur

# Convert beat frames to timestamps
beat_times = librosa.frames_to_time(beat_frames, sr=sr)

# Convert beat frames to sample indices
beat_samples = librosa.frames_to_samples(beat_frames)

# Get onset envelope used for beat tracking (useful for debugging)
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
```

**beat_track Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `y` | None | Audio time series |
| `sr` | 22050 | Sample rate |
| `onset_envelope` | None | Pre-computed onset envelope |
| `hop_length` | 512 | Hop length for onset computation |
| `start_bpm` | 120.0 | Initial tempo estimate |
| `tightness` | 100.0 | How closely to follow estimated tempo |
| `trim` | True | Trim leading/trailing beats |
| `units` | 'frames' | Return type: 'frames', 'samples', or 'time' |

### Tempo Estimation

```python
# Estimate tempo (can return multiple candidates)
tempo = librosa.feature.tempo(y=y, sr=sr)
# Returns: array of estimated tempi, e.g., [120.0]

# Get tempogram (local tempo estimates over time)
tempogram = librosa.feature.tempogram(y=y, sr=sr)
# Shape: (win_length, n_frames)

# Fourier tempogram (complex-valued)
ftempogram = librosa.feature.fourier_tempogram(y=y, sr=sr)
```

### Synchronize Features to Beats

```python
# Aggregate features per beat (very useful for MIR)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

# Average features between beats
beat_mfcc = librosa.util.sync(mfcc, beats, aggregate=np.mean)
beat_chroma = librosa.util.sync(chroma, beats, aggregate=np.median)
# Shapes: (n_features, n_beats)
```

---

## Onset Detection

Onsets are the beginning of musical events (notes, drum hits, transients).

```python
# Compute onset strength envelope
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
# Shape: (n_frames,)

# Detect onset events (as frame indices)
onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
# or from pre-computed envelope:
onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)

# Convert to timestamps
onset_times = librosa.frames_to_time(onset_frames, sr=sr)

# Backtrack onsets to nearest preceding local minimum of energy
# (finds the true start of the transient, not just the peak)
onset_bt = librosa.onset.onset_backtrack(onset_frames, onset_env)
onset_bt_times = librosa.frames_to_time(onset_bt, sr=sr)

# Multi-channel onset strength (e.g., different frequency bands)
onset_multi = librosa.onset.onset_strength_multi(y=y, sr=sr)
```

**onset_detect Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `y` | None | Audio time series |
| `sr` | 22050 | Sample rate |
| `onset_envelope` | None | Pre-computed onset envelope |
| `hop_length` | 512 | Hop length |
| `backtrack` | False | Backtrack onset events |
| `units` | 'frames' | Return 'frames', 'samples', or 'time' |
| `delta` | 0.07 | Threshold for peak picking |
| `wait` | 30 | Minimum frames between onsets |

---

## Pitch Detection and Tracking

### YIN Algorithm

```python
# YIN fundamental frequency estimation
f0 = librosa.yin(y, fmin=65, fmax=2093, sr=sr)
# f0 shape: (n_frames,)
# Values in Hz. Unvoiced frames may show unreliable values.
```

### Probabilistic YIN (pYIN)

More robust than YIN - provides voicing probability.

```python
# pYIN returns f0, voiced flag, and voicing probability
f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=65, fmax=2093, sr=sr)
# f0: fundamental frequency (Hz), NaN for unvoiced frames
# voiced_flag: boolean array
# voiced_probs: probability of voicing per frame

# Filter to only voiced frames
voiced_f0 = f0[voiced_flag]
```

**pyin Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `y` | required | Audio time series |
| `fmin` | required | Minimum expected frequency (Hz) |
| `fmax` | required | Maximum expected frequency (Hz) |
| `sr` | 22050 | Sample rate |
| `frame_length` | 2048 | Frame length for analysis |
| `hop_length` | None | Hop length (default = frame_length // 4) |
| `resolution` | 0.1 | Frequency resolution in cents |

### Piptrack (Parabolic Interpolated Pitch Tracking)

```python
# Pitch tracking from STFT
pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
# pitches shape: (n_fft/2 + 1, n_frames)
# magnitudes shape: same

# Get dominant pitch per frame
dominant_pitch = []
for frame in range(pitches.shape[1]):
    idx = magnitudes[:, frame].argmax()
    dominant_pitch.append(pitches[idx, frame])
```

### Common Pitch Ranges

| Instrument | fmin (Hz) | fmax (Hz) |
|-----------|-----------|-----------|
| Bass guitar | 41 | 400 |
| Guitar | 82 | 1200 |
| Vocals (male) | 85 | 600 |
| Vocals (female) | 165 | 1050 |
| Piano | 27.5 | 4186 |

---

## Audio Effects

### Time Stretch

Change speed without changing pitch.

```python
# Stretch to twice the duration (half speed)
y_slow = librosa.effects.time_stretch(y, rate=0.5)

# Compress to half duration (double speed)
y_fast = librosa.effects.time_stretch(y, rate=2.0)

# Subtle tempo adjustment
y_adjusted = librosa.effects.time_stretch(y, rate=1.05)  # 5% faster
```

### Pitch Shift

Change pitch without changing speed.

```python
# Shift up by 4 semitones
y_up = librosa.effects.pitch_shift(y, sr=sr, n_steps=4)

# Shift down by 2 semitones
y_down = librosa.effects.pitch_shift(y, sr=sr, n_steps=-2)

# Shift by fractional semitones (microtonal)
y_micro = librosa.effects.pitch_shift(y, sr=sr, n_steps=0.5)

# Specify bins_per_octave for non-12-TET tuning
y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=1, bins_per_octave=24)
```

### Harmonic/Percussive Source Separation (HPSS)

Separates audio into harmonic (tonal) and percussive (transient) components.

```python
# Basic separation
y_harmonic, y_percussive = librosa.effects.hpss(y)

# With custom kernel size (larger = smoother separation)
y_harmonic, y_percussive = librosa.effects.hpss(y, kernel_size=31)

# Extract only harmonic or only percussive
y_harmonic = librosa.effects.harmonic(y)
y_percussive = librosa.effects.percussive(y)

# Use soft masking for smoother separation (less artifacts)
y_harmonic, y_percussive = librosa.effects.hpss(y, mask=True)
```

### Trim Silence

```python
# Remove silence from beginning and end
y_trimmed, index = librosa.effects.trim(y, top_db=20)
# index: [start_sample, end_sample] of non-silent region

# More aggressive trimming
y_trimmed, index = librosa.effects.trim(y, top_db=30)  # 30dB below peak
```

### Split on Silence

```python
# Split audio into non-silent intervals
intervals = librosa.effects.split(y, top_db=20)
# intervals: array of [start, end] sample indices

# Extract non-silent segments
segments = [y[start:end] for start, end in intervals]
```

### Pre-emphasis / De-emphasis

High-pass filter for boosting high frequencies (common in speech processing).

```python
# Pre-emphasis (boost high frequencies)
y_preemph = librosa.effects.preemphasis(y, coef=0.97)

# De-emphasis (undo pre-emphasis)
y_deemph = librosa.effects.deemphasis(y_preemph, coef=0.97)
```

### Remix

Reorder time intervals (for creative effects or beat rearrangement).

```python
# Rearrange audio based on beat positions
tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
beat_samples = librosa.frames_to_samples(beats)

# Create intervals between beats
intervals = librosa.util.frame(np.append(beat_samples, len(y)),
                                frame_length=2, hop_length=1).T

# Reverse the order of beats
y_reversed_beats = librosa.effects.remix(y, intervals[::-1])
```

---

## Display Utilities

Requires matplotlib: `pip install matplotlib`

### specshow - Display Spectrograms

```python
import librosa.display
import matplotlib.pyplot as plt

# Basic spectrogram display
fig, ax = plt.subplots()
S_db = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
img = librosa.display.specshow(S_db, sr=sr, x_axis='time', y_axis='hz', ax=ax)
fig.colorbar(img, ax=ax, format='%+2.0f dB')
ax.set_title('Spectrogram')
plt.show()

# Mel spectrogram display
fig, ax = plt.subplots()
S_mel = librosa.feature.melspectrogram(y=y, sr=sr)
S_mel_db = librosa.power_to_db(S_mel, ref=np.max)
img = librosa.display.specshow(S_mel_db, sr=sr, x_axis='time', y_axis='mel', ax=ax)
fig.colorbar(img, ax=ax, format='%+2.0f dB')
ax.set_title('Mel Spectrogram')
plt.show()

# Chromagram display
fig, ax = plt.subplots()
chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
img = librosa.display.specshow(chroma, sr=sr, x_axis='time', y_axis='chroma', ax=ax)
fig.colorbar(img, ax=ax)
ax.set_title('Chromagram')
plt.show()

# Tempogram display
fig, ax = plt.subplots()
tempogram = librosa.feature.tempogram(y=y, sr=sr)
img = librosa.display.specshow(tempogram, sr=sr, x_axis='time', y_axis='tempo', ax=ax)
ax.set_title('Tempogram')
plt.show()
```

**specshow y_axis options:** 'hz', 'mel', 'log', 'chroma', 'tonnetz', 'tempo', 'fourier_tempo', 'cqt_hz', 'cqt_note', 'cqt_svara'

**specshow x_axis options:** 'time', 's', 'ms', 'frames', 'lag', 'lag_s', 'lag_ms', 'tempo'

### waveshow - Display Waveform

```python
fig, ax = plt.subplots()
librosa.display.waveshow(y, sr=sr, ax=ax)
ax.set_title('Waveform')
plt.show()

# Overlay harmonic and percussive
y_harm, y_perc = librosa.effects.hpss(y)
fig, ax = plt.subplots()
librosa.display.waveshow(y_harm, sr=sr, alpha=0.5, label='Harmonic', ax=ax)
librosa.display.waveshow(y_perc, sr=sr, alpha=0.5, color='r', label='Percussive', ax=ax)
ax.legend()
plt.show()
```

### Multi-Panel Display

```python
fig, axes = plt.subplots(nrows=3, figsize=(12, 8), sharex=True)

# Waveform
librosa.display.waveshow(y, sr=sr, ax=axes[0])
axes[0].set_title('Waveform')

# Mel spectrogram
S_mel = librosa.feature.melspectrogram(y=y, sr=sr)
S_mel_db = librosa.power_to_db(S_mel, ref=np.max)
img = librosa.display.specshow(S_mel_db, sr=sr, x_axis='time', y_axis='mel', ax=axes[1])
fig.colorbar(img, ax=axes[1])
axes[1].set_title('Mel Spectrogram')

# Chromagram
chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
img = librosa.display.specshow(chroma, sr=sr, x_axis='time', y_axis='chroma', ax=axes[2])
fig.colorbar(img, ax=axes[2])
axes[2].set_title('Chromagram')

plt.tight_layout()
plt.savefig('analysis.png', dpi=150)
plt.show()
```

---

## Magnitude Scaling Utilities

```python
# Amplitude to dB (for amplitude/magnitude spectrograms)
S = np.abs(librosa.stft(y))
S_db = librosa.amplitude_to_db(S, ref=np.max)
# ref=np.max normalizes so peak = 0 dB

# Power to dB (for power spectrograms, e.g., mel)
S_power = np.abs(librosa.stft(y))**2
S_db = librosa.power_to_db(S_power, ref=np.max)

# dB back to amplitude
S_recovered = librosa.db_to_amplitude(S_db)

# dB back to power
S_power_recovered = librosa.db_to_power(S_db)
```

| Function | Input | Output | Use When |
|----------|-------|--------|----------|
| `amplitude_to_db` | Magnitude spectrogram | dB scale | `np.abs(stft(y))` |
| `power_to_db` | Power spectrogram | dB scale | `np.abs(stft(y))**2` or mel |
| `db_to_amplitude` | dB values | Amplitude | Inverse of amplitude_to_db |
| `db_to_power` | dB values | Power | Inverse of power_to_db |

---

## Feature Manipulation

### Delta (Derivative) Features

```python
# First-order delta (velocity)
mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
delta = librosa.feature.delta(mfcc)

# Second-order delta (acceleration)
delta2 = librosa.feature.delta(mfcc, order=2)

# Stack for full feature set
features = np.vstack([mfcc, delta, delta2])
```

### Stack Memory (Short-Term History)

```python
# Embed short-term history into features
mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
mfcc_stacked = librosa.feature.stack_memory(mfcc, n_steps=3)
# Shape: (13 * 3, n_frames) = (39, n_frames)
```

### Feature Inversion (Reconstructing Audio)

```python
# MFCC -> audio (rough reconstruction)
mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
y_reconstructed = librosa.feature.inverse.mfcc_to_audio(mfcc, sr=sr)

# Mel spectrogram -> audio
S_mel = librosa.feature.melspectrogram(y=y, sr=sr)
y_reconstructed = librosa.feature.inverse.mel_to_audio(S_mel, sr=sr)
```

---

## Integration with soundfile

librosa uses soundfile as its primary audio I/O backend.

```python
import soundfile as sf
import librosa

# Read with soundfile, process with librosa
data, sr = sf.read('audio.wav')  # Native sample rate
# Resample if needed
if sr != 22050:
    data = librosa.resample(data, orig_sr=sr, target_sr=22050)
    sr = 22050

# Process with librosa
mfcc = librosa.feature.mfcc(y=data, sr=sr)

# Write processed audio with soundfile
y_stretched = librosa.effects.time_stretch(data, rate=1.5)
sf.write('output.wav', y_stretched, sr)

# For formats soundfile can't handle, librosa falls back to audioread
# audioread supports: MP3, AAC, WMA via system codecs
```

---

## Use Cases for Plugin Development

### 1. Analyzing Reference Tracks for Loudness/Spectrum

```python
import librosa
import numpy as np

def analyze_reference_track(filepath):
    """Analyze a reference track for loudness and spectral characteristics."""
    y, sr = librosa.load(filepath, sr=44100, mono=False)

    # Mix to mono for analysis
    if y.ndim > 1:
        y_mono = np.mean(y, axis=0)
    else:
        y_mono = y

    # RMS loudness over time
    rms = librosa.feature.rms(y=y_mono, frame_length=2048, hop_length=512)
    rms_db = 20 * np.log10(np.mean(rms) + 1e-10)

    # Peak level
    peak_db = 20 * np.log10(np.max(np.abs(y_mono)) + 1e-10)

    # Spectral centroid (average brightness)
    centroid = librosa.feature.spectral_centroid(y=y_mono, sr=sr)
    avg_centroid = np.mean(centroid)

    # Spectral rolloff (where most energy lives)
    rolloff = librosa.feature.spectral_rolloff(y=y_mono, sr=sr, roll_percent=0.85)
    avg_rolloff = np.mean(rolloff)

    # Average spectrum (for EQ reference)
    S = np.abs(librosa.stft(y_mono, n_fft=4096))
    avg_spectrum = np.mean(S, axis=1)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)

    return {
        'rms_db': rms_db,
        'peak_db': peak_db,
        'avg_centroid_hz': avg_centroid,
        'avg_rolloff_hz': avg_rolloff,
        'avg_spectrum': avg_spectrum,
        'frequencies': freqs,
        'duration_s': len(y_mono) / sr,
    }

# Compare two tracks
ref = analyze_reference_track('reference.wav')
mix = analyze_reference_track('my_mix.wav')
print(f"Loudness diff: {mix['rms_db'] - ref['rms_db']:.1f} dB")
print(f"Brightness diff: {mix['avg_centroid_hz'] - ref['avg_centroid_hz']:.0f} Hz")
```

### 2. Beat Detection for Sidechain Timing

```python
def get_sidechain_triggers(filepath, subdivisions=1):
    """Detect beats for sidechain compressor timing.

    Args:
        filepath: Path to audio file
        subdivisions: 1=quarter notes, 2=eighth notes, 4=sixteenth notes
    """
    y, sr = librosa.load(filepath, sr=44100)

    # Detect beats
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    print(f"Detected tempo: {tempo:.1f} BPM")
    print(f"Beat interval: {60.0/tempo*1000:.1f} ms")

    # Calculate sidechain envelope parameters
    beat_interval_ms = 60000.0 / tempo  # ms per beat
    subdivision_ms = beat_interval_ms / subdivisions

    # Suggested sidechain settings
    attack_ms = 0.5  # Fast attack
    release_ms = subdivision_ms * 0.7  # Release before next hit
    hold_ms = subdivision_ms * 0.1

    return {
        'tempo': tempo,
        'beat_times': beat_times,
        'beat_interval_ms': beat_interval_ms,
        'suggested_attack_ms': attack_ms,
        'suggested_release_ms': release_ms,
        'suggested_hold_ms': hold_ms,
    }
```

### 3. Spectral Analysis for EQ Decisions

```python
def eq_analysis(filepath, n_bands=10):
    """Analyze frequency balance for EQ decisions."""
    y, sr = librosa.load(filepath, sr=44100)

    # Compute power spectrum
    S = np.abs(librosa.stft(y, n_fft=4096))**2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)

    # Average power per frequency bin
    avg_power = np.mean(S, axis=1)
    avg_power_db = 10 * np.log10(avg_power + 1e-10)

    # Define EQ bands
    eq_bands = [
        ('Sub Bass', 20, 60),
        ('Bass', 60, 250),
        ('Low Mids', 250, 500),
        ('Mids', 500, 2000),
        ('Upper Mids', 2000, 4000),
        ('Presence', 4000, 6000),
        ('Brilliance', 6000, 10000),
        ('Air', 10000, 20000),
    ]

    band_energy = {}
    for name, fmin, fmax in eq_bands:
        mask = (freqs >= fmin) & (freqs < fmax)
        if np.any(mask):
            energy = 10 * np.log10(np.mean(avg_power[mask]) + 1e-10)
            band_energy[name] = energy

    # Spectral balance visualization
    for name, energy in band_energy.items():
        bar = '#' * max(0, int(energy + 60))
        print(f"{name:15s}: {energy:6.1f} dB  {bar}")

    return band_energy
```

### 4. Transient Detection for Drum Separation

```python
def detect_drum_transients(filepath, sensitivity=0.5):
    """Detect drum transients for separation or sample extraction."""
    y, sr = librosa.load(filepath, sr=44100)

    # Separate percussive component
    y_harm, y_perc = librosa.effects.hpss(y)

    # Detect onsets on percussive component
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env, sr=sr,
        delta=sensitivity, wait=10
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    onset_samples = librosa.frames_to_samples(onset_frames)

    # Extract individual hits (50ms windows around each onset)
    window_samples = int(0.05 * sr)  # 50ms
    hits = []
    for sample in onset_samples:
        start = max(0, sample - int(0.005 * sr))  # 5ms before onset
        end = min(len(y_perc), start + window_samples)
        hits.append(y_perc[start:end])

    print(f"Found {len(hits)} drum transients")
    print(f"Onset times: {onset_times[:10]}...")

    return {
        'percussive': y_perc,
        'harmonic': y_harm,
        'onset_times': onset_times,
        'hits': hits,
    }
```

---

## Quick Reference: Common Patterns

```python
import librosa
import numpy as np

# Load
y, sr = librosa.load('file.wav', sr=None)

# Duration
duration = librosa.get_duration(y=y, sr=sr)

# Resample
y_resampled = librosa.resample(y, orig_sr=sr, target_sr=22050)

# Frames <-> Time <-> Samples conversions
times = librosa.frames_to_time(frames, sr=sr, hop_length=512)
frames = librosa.time_to_frames(times, sr=sr, hop_length=512)
samples = librosa.frames_to_samples(frames, hop_length=512)
frames = librosa.samples_to_frames(samples, hop_length=512)

# Note <-> Hz conversions
freq = librosa.note_to_hz('A4')         # 440.0
note = librosa.hz_to_note(440.0)        # 'A4'
midi = librosa.note_to_midi('C4')       # 60
freq = librosa.midi_to_hz(60)           # 261.63

# Frequency <-> Mel conversions
mel = librosa.hz_to_mel(440.0)          # ~549.64
hz = librosa.mel_to_hz(549.64)          # ~440.0
```
