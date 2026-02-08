# SciPy 1.17.0 - Signal Processing Reference

> Focus: `scipy.signal` module for audio DSP and plugin prototyping.
> Install: `pip install scipy`
> Docs: https://docs.scipy.org/doc/scipy/reference/signal.html

---

## Table of Contents

1. [Filter Design (IIR)](#filter-design-iir)
2. [Filter Design (FIR)](#filter-design-fir)
3. [Filter Application](#filter-application)
4. [Spectral Analysis](#spectral-analysis)
5. [Window Functions](#window-functions)
6. [Convolution and Correlation](#convolution-and-correlation)
7. [Peak Finding](#peak-finding)
8. [Resampling](#resampling)
9. [Hilbert Transform (Envelope Detection)](#hilbert-transform-envelope-detection)
10. [Filter Analysis and Visualization](#filter-analysis-and-visualization)
11. [Short-Time Fourier Transform](#short-time-fourier-transform)
12. [Filter Coefficient Conversions](#filter-coefficient-conversions)
13. [Use Cases for Audio Plugin Prototyping](#use-cases-for-audio-plugin-prototyping)

---

## Filter Design (IIR)

IIR (Infinite Impulse Response) filters are the workhorses of audio processing -- EQs, crossovers, and tone controls are all IIR filters.

### Butterworth (butter)

Maximally flat magnitude response in the passband. No ripple. The "safe default" for audio.

```python
from scipy.signal import butter, sosfilt
import numpy as np

# Design a lowpass Butterworth filter
# fs = sample rate, fc = cutoff frequency
fs = 44100
fc = 1000  # 1 kHz cutoff

# Second-order sections format (ALWAYS prefer sos over ba)
sos = butter(N=4, Wn=fc, btype='low', fs=fs, output='sos')
# N=4 means 4th order (24 dB/octave slope)

# Apply filter to audio
y_filtered = sosfilt(sos, audio_data)

# Highpass filter
sos_hp = butter(N=2, Wn=80, btype='high', fs=fs, output='sos')

# Bandpass filter
sos_bp = butter(N=4, Wn=[200, 5000], btype='band', fs=fs, output='sos')

# Bandstop (notch) filter
sos_bs = butter(N=4, Wn=[950, 1050], btype='bandstop', fs=fs, output='sos')
```

**Butterworth slopes:** Order N gives N*6 dB/octave rolloff.

| Order | Slope | Typical Use |
|-------|-------|-------------|
| 1 | 6 dB/oct | Gentle tilt EQ |
| 2 | 12 dB/oct | Standard crossover, gentle filter |
| 4 | 24 dB/oct | Linkwitz-Riley crossover |
| 8 | 48 dB/oct | Sharp filter, synth filter |

### Chebyshev Type I (cheby1)

Steeper rolloff than Butterworth, but has passband ripple.

```python
from scipy.signal import cheby1

# rp = maximum ripple in passband (dB)
sos = cheby1(N=4, rp=0.5, Wn=1000, btype='low', fs=44100, output='sos')
# rp=0.5 means 0.5 dB ripple allowed in passband

# More aggressive: 1dB ripple for steeper cutoff
sos_steep = cheby1(N=4, rp=1.0, Wn=1000, btype='low', fs=44100, output='sos')
```

### Chebyshev Type II (cheby2)

Flat passband (like Butterworth) but has stopband ripple.

```python
from scipy.signal import cheby2

# rs = minimum attenuation in stopband (dB)
sos = cheby2(N=4, rs=40, Wn=1000, btype='low', fs=44100, output='sos')
# rs=40 means at least 40 dB attenuation in stopband
```

### Elliptic (ellip)

Steepest transition of all standard IIR filters. Has both passband and stopband ripple.

```python
from scipy.signal import ellip

# rp = passband ripple (dB), rs = stopband attenuation (dB)
sos = ellip(N=4, rp=0.5, rs=40, Wn=1000, btype='low', fs=44100, output='sos')
# Best transition band but most ripple
```

### Bessel (bessel)

Best phase response (most linear phase). Gentlest slope. Preserves waveform shape.

```python
from scipy.signal import bessel

sos = bessel(N=4, Wn=1000, btype='low', fs=44100, output='sos', norm='phase')
# norm='phase': normalize for phase response
# norm='mag': normalize for magnitude response (default)
# norm='delay': normalize for group delay
```

### Filter Type Comparison

| Filter | Passband | Stopband | Transition | Phase | Audio Use |
|--------|----------|----------|------------|-------|-----------|
| Butterworth | Flat | Smooth | Moderate | Good | General EQ, crossovers |
| Chebyshev I | Ripple | Smooth | Steep | Fair | Synth filters |
| Chebyshev II | Flat | Ripple | Steep | Fair | Anti-alias pre-filters |
| Elliptic | Ripple | Ripple | Steepest | Poor | Brick-wall filters |
| Bessel | Flat | Smooth | Gentle | Best | Waveform-preserving |

### Design by Specification (iirdesign)

Specify passband and stopband requirements, let scipy choose the order.

```python
from scipy.signal import iirdesign

# Design filter meeting specifications
# wp = passband edge, ws = stopband edge (normalized 0-1 or Hz with fs)
# gpass = max passband loss (dB), gstop = min stopband attenuation (dB)
sos = iirdesign(
    wp=1000,        # Passband edge: 1 kHz
    ws=1500,        # Stopband edge: 1.5 kHz
    gpass=1.0,      # Max 1 dB loss in passband
    gstop=40.0,     # At least 40 dB attenuation in stopband
    fs=44100,
    ftype='butter',  # 'butter', 'cheby1', 'cheby2', 'ellip', 'bessel'
    output='sos'
)
```

---

## Filter Design (FIR)

FIR (Finite Impulse Response) filters have linear phase by design. Used for precise filtering without phase distortion.

### firwin - Window-based FIR design

```python
from scipy.signal import firwin, lfilter

fs = 44100

# Lowpass FIR filter
# Use odd number of taps for type I linear phase
taps = firwin(numtaps=101, cutoff=1000, fs=fs, window='hamming')

# Apply FIR filter
y_filtered = lfilter(taps, 1.0, audio_data)

# Highpass FIR filter (pass_zero=False)
taps_hp = firwin(101, cutoff=80, fs=fs, window='hamming', pass_zero=False)

# Bandpass FIR filter
taps_bp = firwin(101, cutoff=[200, 5000], fs=fs, window='hamming', pass_zero=False)

# Bandstop FIR filter
taps_bs = firwin(101, cutoff=[950, 1050], fs=fs, window='hamming')
```

### firwin2 - Arbitrary frequency response

```python
from scipy.signal import firwin2

# Design a custom frequency response
# freqs and gains define the desired shape
freqs = [0, 200, 200, 5000, 5000, fs/2]  # Hz
gains = [0, 0, 1, 1, 0, 0]  # Bandpass 200-5000 Hz

taps = firwin2(numtaps=501, freq=freqs, gain=gains, fs=fs)
```

**FIR vs IIR for Audio:**

| Property | FIR | IIR |
|----------|-----|-----|
| Phase | Linear (exact) | Non-linear |
| Latency | High (N/2 samples) | Low |
| CPU cost | Higher | Lower |
| Stability | Always stable | Can be unstable |
| Audio use | Mastering EQ, linear-phase crossover | Real-time EQ, synth filters |

---

## Filter Application

### sosfilt - Second-Order Sections (RECOMMENDED)

The preferred method for applying IIR filters. More numerically stable than lfilter.

```python
from scipy.signal import sosfilt, butter

sos = butter(8, 1000, btype='low', fs=44100, output='sos')

# Basic filtering
y_filtered = sosfilt(sos, audio_data)

# Process in chunks (for real-time simulation)
chunk_size = 1024
zi = np.zeros((sos.shape[0], 2))  # Initial conditions

for i in range(0, len(audio_data), chunk_size):
    chunk = audio_data[i:i+chunk_size]
    filtered_chunk, zi = sosfilt(sos, chunk, zi=zi)
    # output filtered_chunk to audio buffer
```

### lfilter - Direct Form II (Legacy)

```python
from scipy.signal import lfilter, butter

# ba (transfer function) format
b, a = butter(4, 1000, btype='low', fs=44100)

# Apply filter
y_filtered = lfilter(b, a, audio_data)

# With initial conditions (for streaming/real-time)
from scipy.signal import lfilter_zi
zi = lfilter_zi(b, a) * audio_data[0]
y_filtered, zf = lfilter(b, a, audio_data, zi=zi)
```

**WARNING:** For high-order filters (N > 4), ba format can be numerically unstable. ALWAYS use sos format with sosfilt for production code.

### filtfilt - Zero-Phase Filtering

Applies filter forward then backward, eliminating phase distortion. Output has zero phase shift but double the filter order.

```python
from scipy.signal import filtfilt, butter

b, a = butter(4, 1000, btype='low', fs=44100)

# Zero-phase filtering (NOT real-time, requires full signal)
y_filtered = filtfilt(b, a, audio_data)
# Result has 8th-order magnitude response (double the designed 4th order)
# but ZERO phase shift
```

**filtfilt is offline only** -- it requires the entire signal. Cannot be used for real-time audio processing.

---

## Spectral Analysis

### Welch's Method (Recommended for Audio)

Averaged periodogram with overlapping segments. Gives smooth, reliable PSD estimates.

```python
from scipy.signal import welch
import numpy as np

fs = 44100

# Power spectral density estimation
freqs, psd = welch(audio_data, fs=fs, nperseg=4096, noverlap=2048, window='hann')
# freqs: frequency array (Hz)
# psd: power spectral density (V^2/Hz)

# Convert to dB
psd_db = 10 * np.log10(psd + 1e-10)

# Plot
import matplotlib.pyplot as plt
plt.semilogx(freqs, psd_db)
plt.xlabel('Frequency (Hz)')
plt.ylabel('PSD (dB/Hz)')
plt.xlim(20, 20000)
plt.grid(True)
plt.show()
```

**welch Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `x` | required | Input signal |
| `fs` | 1.0 | Sample rate (Hz) |
| `window` | 'hann' | Window function |
| `nperseg` | 256 | Samples per segment (frequency resolution) |
| `noverlap` | nperseg/2 | Overlap between segments |
| `nfft` | nperseg | FFT length (zero-pad for interpolation) |
| `scaling` | 'density' | 'density' (V^2/Hz) or 'spectrum' (V^2) |
| `detrend` | 'constant' | Remove mean. 'linear' removes trend. False disables |

**Frequency resolution:** `fs / nperseg` Hz. With fs=44100, nperseg=4096: ~10.8 Hz.

### Periodogram

Simple FFT-based PSD. Noisier than Welch but uses full resolution.

```python
from scipy.signal import periodogram

freqs, psd = periodogram(audio_data, fs=fs, window='hann')
```

### Spectrogram

Time-frequency representation (like STFT but returns power).

```python
from scipy.signal import spectrogram

freqs, times, Sxx = spectrogram(audio_data, fs=fs, nperseg=1024,
                                  noverlap=512, window='hann')
# Sxx shape: (n_freqs, n_times)

# Plot spectrogram
plt.pcolormesh(times, freqs, 10 * np.log10(Sxx + 1e-10), shading='auto')
plt.ylabel('Frequency (Hz)')
plt.xlabel('Time (s)')
plt.ylim(20, 20000)
plt.yscale('log')
plt.colorbar(label='Power (dB)')
plt.show()
```

---

## Window Functions

Windows reduce spectral leakage in FFT analysis. Available in `scipy.signal.windows`.

```python
from scipy.signal import windows
import numpy as np

N = 1024  # Window length

# Common windows for audio
w_hann = windows.hann(N)           # Good all-around (default for most)
w_hamming = windows.hamming(N)     # Slightly less sidelobe suppression than Hann
w_blackman = windows.blackman(N)   # Better sidelobe suppression, wider main lobe
w_kaiser = windows.kaiser(N, beta=8.6)  # Adjustable: beta controls trade-off
w_flattop = windows.flattop(N)    # Best amplitude accuracy, worst freq resolution

# Tukey window (tapered cosine) - good for overlap-add
w_tukey = windows.tukey(N, alpha=0.5)
# alpha=0 is rectangular, alpha=1 is Hann

# Generic window accessor
w = windows.get_window('hann', N)
w = windows.get_window(('kaiser', 8.6), N)  # Parameterized
```

### Window Selection Guide for Audio

| Window | Main Lobe Width | Sidelobe Level | Best For |
|--------|----------------|----------------|----------|
| Rectangular | Narrowest | Worst (-13 dB) | Maximum frequency resolution |
| Hann | Moderate | Good (-31 dB) | General spectral analysis |
| Hamming | Moderate | Good (-42 dB) | FIR filter design |
| Blackman | Wide | Very good (-58 dB) | Low-leakage analysis |
| Kaiser (beta=8.6) | Wide | Very good (-60 dB) | Adjustable trade-off |
| Flat-top | Widest | Good | Amplitude measurement |

**Rule of thumb:** Use Hann for spectral analysis, Hamming for FIR design, Blackman/Kaiser for precision measurement.

---

## Convolution and Correlation

### Convolution

```python
from scipy.signal import convolve, fftconvolve

# Time-domain convolution (for short signals/kernels)
y = convolve(signal, kernel, mode='full')
# mode: 'full' (default), 'same' (same length as signal), 'valid'

# FFT-based convolution (MUCH faster for long signals)
y = fftconvolve(signal, impulse_response, mode='same')
# Use for: convolution reverb, applying impulse responses

# Example: Convolution reverb
ir, sr_ir = librosa.load('impulse_response.wav', sr=44100)
dry_signal, sr = librosa.load('dry_audio.wav', sr=44100)
wet_signal = fftconvolve(dry_signal, ir, mode='full')[:len(dry_signal)]
# Mix dry/wet
output = 0.7 * dry_signal + 0.3 * wet_signal[:len(dry_signal)]
```

### Correlation

```python
from scipy.signal import correlate

# Cross-correlation (for delay estimation, template matching)
correlation = correlate(signal_a, signal_b, mode='full')

# Find delay between two signals
delay_samples = np.argmax(correlation) - len(signal_b) + 1
delay_ms = delay_samples / fs * 1000
print(f"Signal B is delayed by {delay_ms:.1f} ms")

# Normalized cross-correlation
norm_corr = correlate(signal_a, signal_b, mode='full')
norm_corr /= np.sqrt(np.sum(signal_a**2) * np.sum(signal_b**2))
```

---

## Peak Finding

### find_peaks

Essential for onset detection, frequency peak identification, and beat detection.

```python
from scipy.signal import find_peaks

# Basic peak finding
peaks, properties = find_peaks(signal)
# peaks: indices of peaks
# properties: dict of peak properties

# With constraints
peaks, props = find_peaks(signal,
    height=0.5,           # Minimum peak height
    threshold=None,       # Min height difference to neighbors
    distance=100,         # Min samples between peaks
    prominence=0.1,       # Min prominence (how much peak stands out)
    width=5,              # Min peak width (samples)
)

# Access properties
peak_heights = props['peak_heights']       # Only if height specified
peak_prominences = props['prominences']    # Only if prominence specified
peak_widths = props['widths']              # Only if width specified

# Example: Find spectral peaks
S = np.abs(np.fft.rfft(audio_frame))
freqs = np.fft.rfftfreq(len(audio_frame), 1/fs)
peaks, props = find_peaks(S, height=np.max(S)*0.1, distance=10, prominence=np.max(S)*0.05)
peak_freqs = freqs[peaks]
print(f"Dominant frequencies: {peak_freqs[:5]} Hz")
```

**find_peaks Parameters:**

| Parameter | Description |
|-----------|-------------|
| `height` | Required height of peaks (scalar or (min, max)) |
| `threshold` | Required vertical distance to neighbors |
| `distance` | Minimum horizontal distance between peaks (samples) |
| `prominence` | Required prominence of peaks |
| `width` | Required width of peaks at half-prominence |
| `plateau_size` | Required size of the flat peak top |

---

## Resampling

### resample - FFT-based (Exact)

```python
from scipy.signal import resample

# Resample from 44100 to 48000 Hz
original_sr = 44100
target_sr = 48000
num_samples = int(len(audio_data) * target_sr / original_sr)
resampled = resample(audio_data, num_samples)

# Resample a specific number of samples
resampled_to_n = resample(audio_data, 1000)  # Exactly 1000 samples
```

### decimate - Integer Downsampling

```python
from scipy.signal import decimate

# Downsample by integer factor (includes anti-alias filter)
downsampled = decimate(audio_data, q=2)  # 44100 -> 22050 Hz
downsampled = decimate(audio_data, q=4)  # 44100 -> 11025 Hz

# With specific filter
downsampled = decimate(audio_data, q=2, ftype='fir')  # FIR anti-alias
downsampled = decimate(audio_data, q=2, ftype='iir')  # IIR anti-alias (default)
downsampled = decimate(audio_data, q=2, n=8)  # Filter order

# For non-integer factors, use resample instead
```

### resample_poly - Polyphase Resampling

```python
from scipy.signal import resample_poly

# Efficient resampling by rational factor (up/down)
# 44100 -> 48000 = multiply by 48000/44100 = 160/147
resampled = resample_poly(audio_data, up=160, down=147)
```

---

## Hilbert Transform (Envelope Detection)

The Hilbert transform computes the analytic signal, from which you can extract the amplitude envelope and instantaneous frequency.

```python
from scipy.signal import hilbert
import numpy as np

# Compute analytic signal
analytic_signal = hilbert(audio_data)

# Amplitude envelope (important for dynamics analysis)
amplitude_envelope = np.abs(analytic_signal)

# Instantaneous phase
instantaneous_phase = np.unwrap(np.angle(analytic_signal))

# Instantaneous frequency
instantaneous_freq = np.diff(instantaneous_phase) / (2.0 * np.pi) * fs

# Example: Envelope follower for sidechain compressor
envelope = np.abs(hilbert(audio_data))

# Smooth the envelope (attack/release simulation)
from scipy.signal import butter, sosfilt
sos = butter(2, 30, btype='low', fs=fs, output='sos')  # 30 Hz smoothing
smooth_envelope = sosfilt(sos, envelope)

# Example: AM demodulation
carrier_freq = 1000
t = np.arange(len(audio_data)) / fs
# Remove carrier, extract modulating signal
demodulated = audio_data * np.cos(2 * np.pi * carrier_freq * t)
sos_lp = butter(4, 100, btype='low', fs=fs, output='sos')
baseband = sosfilt(sos_lp, demodulated)
```

---

## Filter Analysis and Visualization

### Frequency Response

```python
from scipy.signal import freqz, sosfreqz, butter
import numpy as np
import matplotlib.pyplot as plt

fs = 44100

# Design filter
sos = butter(4, 1000, btype='low', fs=fs, output='sos')

# Get frequency response from SOS
w, h = sosfreqz(sos, worN=8192, fs=fs)
# w: frequencies (Hz when fs is specified)
# h: complex frequency response

# Magnitude response in dB
magnitude_db = 20 * np.log10(np.abs(h) + 1e-10)

# Phase response in degrees
phase_deg = np.degrees(np.unwrap(np.angle(h)))

# Plot magnitude response
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
ax1.semilogx(w, magnitude_db)
ax1.set_xlabel('Frequency (Hz)')
ax1.set_ylabel('Magnitude (dB)')
ax1.set_xlim(20, 20000)
ax1.set_ylim(-60, 5)
ax1.grid(True)
ax1.set_title('Butterworth 4th Order Lowpass @ 1 kHz')

# Plot phase response
ax2.semilogx(w, phase_deg)
ax2.set_xlabel('Frequency (Hz)')
ax2.set_ylabel('Phase (degrees)')
ax2.set_xlim(20, 20000)
ax2.grid(True)

plt.tight_layout()
plt.show()

# For ba-format filters
b, a = butter(4, 1000, btype='low', fs=fs)
w, h = freqz(b, a, worN=8192, fs=fs)
```

### Group Delay

```python
from scipy.signal import group_delay

b, a = butter(4, 1000, btype='low', fs=fs)
w, gd = group_delay((b, a), fs=fs)
# gd: group delay in samples

plt.semilogx(w, gd / fs * 1000)  # Convert to ms
plt.xlabel('Frequency (Hz)')
plt.ylabel('Group Delay (ms)')
plt.show()
```

### Pole-Zero Plot

```python
from scipy.signal import tf2zpk

b, a = butter(4, 1000, btype='low', fs=fs)
z, p, k = tf2zpk(b, a)
# z: zeros, p: poles, k: gain

# Plot
fig, ax = plt.subplots()
theta = np.linspace(0, 2*np.pi, 100)
ax.plot(np.cos(theta), np.sin(theta), 'k--', alpha=0.3)  # Unit circle
ax.plot(np.real(z), np.imag(z), 'bo', label='Zeros')
ax.plot(np.real(p), np.imag(p), 'rx', label='Poles')
ax.set_aspect('equal')
ax.legend()
ax.set_title('Pole-Zero Plot')
ax.grid(True)
plt.show()

# Stability check: all poles must be inside unit circle
is_stable = np.all(np.abs(p) < 1.0)
print(f"Filter is {'stable' if is_stable else 'UNSTABLE'}")
```

---

## Short-Time Fourier Transform

```python
from scipy.signal import ShortTimeFFT
from scipy.signal.windows import hann

# Create STFT instance
window = hann(1024)
stft = ShortTimeFFT(win=window, hop=256, fs=44100, mfft=2048)

# Forward STFT
Sx = stft.stft(audio_data)
# Sx: complex array shape (n_freq, n_time)

# Inverse STFT (reconstruct signal)
y_reconstructed = stft.istft(Sx)

# Access properties
print(f"Time step: {stft.delta_t:.4f} s")
print(f"Frequency step: {stft.delta_f:.2f} Hz")
print(f"Number of frequency bins: {stft.f_pts}")
```

---

## Filter Coefficient Conversions

```python
from scipy.signal import (
    tf2zpk, zpk2tf,     # Transfer function <-> Zeros-Poles-Gain
    tf2sos, sos2tf,     # Transfer function <-> Second-Order Sections
    zpk2sos, sos2zpk,   # ZPK <-> SOS
    bilinear,            # Analog -> Digital (s-domain -> z-domain)
    lp2lp, lp2hp,       # Prototype transformations
    lp2bp, lp2bs,
)

# Example: Convert ba to sos (for numerical stability)
b, a = butter(8, 1000, fs=44100)
sos = tf2sos(b, a)

# Example: Analog prototype to digital filter
# Design analog 2nd-order lowpass with wc = 2*pi*1000 rad/s
import numpy as np
wc = 2 * np.pi * 1000
b_analog = [wc**2]
a_analog = [1, np.sqrt(2)*wc, wc**2]

# Convert to digital using bilinear transform
b_digital, a_digital = bilinear(b_analog, a_analog, fs=44100)
```

---

## Use Cases for Audio Plugin Prototyping

### 1. Prototyping Filter Responses Before C++ Implementation

```python
"""
Workflow: Design and test filter in Python, then port to JUCE C++.
"""
from scipy.signal import butter, sosfilt, sosfreqz
import numpy as np
import matplotlib.pyplot as plt
import soundfile as sf

# Read test audio
audio, fs = sf.read('test_audio.wav')

# Design parametric EQ band (second-order peaking filter)
def design_peaking_eq(fc, gain_db, Q, fs):
    """Design a peaking EQ filter (biquad).

    Args:
        fc: Center frequency (Hz)
        gain_db: Gain at center frequency (dB)
        Q: Quality factor (bandwidth control)
        fs: Sample rate (Hz)

    Returns:
        sos: Second-order section coefficients
    """
    A = 10**(gain_db / 40.0)
    w0 = 2 * np.pi * fc / fs
    alpha = np.sin(w0) / (2 * Q)

    b0 = 1 + alpha * A
    b1 = -2 * np.cos(w0)
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * np.cos(w0)
    a2 = 1 - alpha / A

    # Normalize
    b = np.array([b0/a0, b1/a0, b2/a0])
    a = np.array([1.0, a1/a0, a2/a0])

    # Convert to sos
    sos = np.array([[b[0], b[1], b[2], 1.0, a[1], a[2]]])
    return sos

# Design 3-band EQ
eq_low = design_peaking_eq(fc=200, gain_db=3.0, Q=1.0, fs=fs)
eq_mid = design_peaking_eq(fc=2000, gain_db=-2.0, Q=1.5, fs=fs)
eq_high = design_peaking_eq(fc=8000, gain_db=4.0, Q=0.7, fs=fs)

# Chain filters
sos_combined = np.vstack([eq_low, eq_mid, eq_high])

# Apply to audio
processed = sosfilt(sos_combined, audio)

# Visualize combined response
w, h = sosfreqz(sos_combined, worN=8192, fs=fs)
plt.semilogx(w, 20*np.log10(np.abs(h)))
plt.xlabel('Frequency (Hz)')
plt.ylabel('Gain (dB)')
plt.title('3-Band Parametric EQ')
plt.xlim(20, 20000)
plt.ylim(-10, 10)
plt.grid(True)
plt.show()

# Write output for A/B comparison in DAW
sf.write('processed.wav', processed, fs)
```

### 2. Analyzing Frequency Response of Designed Filters

```python
"""
Compare different filter types to choose the best for your plugin.
"""
from scipy.signal import butter, cheby1, bessel, ellip, sosfreqz
import matplotlib.pyplot as plt

fs = 44100
fc = 1000
N = 4

# Design all filter types
filters = {
    'Butterworth': butter(N, fc, btype='low', fs=fs, output='sos'),
    'Chebyshev I (0.5dB)': cheby1(N, 0.5, fc, btype='low', fs=fs, output='sos'),
    'Bessel': bessel(N, fc, btype='low', fs=fs, output='sos', norm='phase'),
    'Elliptic': ellip(N, 0.5, 40, fc, btype='low', fs=fs, output='sos'),
}

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

for name, sos in filters.items():
    w, h = sosfreqz(sos, worN=8192, fs=fs)
    ax1.semilogx(w, 20*np.log10(np.abs(h) + 1e-10), label=name)
    ax2.semilogx(w, np.degrees(np.unwrap(np.angle(h))), label=name)

ax1.set_ylabel('Magnitude (dB)')
ax1.set_xlim(20, 20000)
ax1.set_ylim(-80, 5)
ax1.legend()
ax1.grid(True)
ax1.set_title('Filter Comparison: 4th Order Lowpass @ 1 kHz')

ax2.set_xlabel('Frequency (Hz)')
ax2.set_ylabel('Phase (degrees)')
ax2.set_xlim(20, 20000)
ax2.legend()
ax2.grid(True)

plt.tight_layout()
plt.show()
```

### 3. Testing DSP Algorithms Before Porting to JUCE

```python
"""
Prototype a simple compressor in Python, then port coefficients to C++.
"""
import numpy as np
from scipy.signal import butter, sosfilt
import soundfile as sf

def compressor(audio, fs, threshold_db=-20, ratio=4.0,
               attack_ms=5.0, release_ms=50.0, makeup_db=0.0):
    """Simple compressor for prototyping.

    This demonstrates the algorithm you'd port to JUCE C++.
    """
    # Convert parameters
    threshold = 10**(threshold_db / 20.0)
    makeup_gain = 10**(makeup_db / 20.0)

    # Envelope follower coefficients (same math as JUCE)
    attack_coeff = np.exp(-1.0 / (attack_ms * 0.001 * fs))
    release_coeff = np.exp(-1.0 / (release_ms * 0.001 * fs))

    # Process sample-by-sample (same as JUCE processBlock)
    envelope = 0.0
    output = np.zeros_like(audio)

    for i in range(len(audio)):
        # Input level
        input_level = np.abs(audio[i])

        # Envelope follower
        if input_level > envelope:
            envelope = attack_coeff * envelope + (1 - attack_coeff) * input_level
        else:
            envelope = release_coeff * envelope + (1 - release_coeff) * input_level

        # Gain computation
        if envelope > threshold:
            gain_db = threshold_db + (20*np.log10(envelope + 1e-10) - threshold_db) / ratio
            gain = 10**(gain_db / 20.0) / (envelope + 1e-10)
        else:
            gain = 1.0

        output[i] = audio[i] * gain * makeup_gain

    return output

# Test
audio, fs = sf.read('drums.wav')
compressed = compressor(audio, fs, threshold_db=-18, ratio=4.0,
                        attack_ms=1.0, release_ms=100.0, makeup_db=6.0)
sf.write('drums_compressed.wav', compressed, fs)
```

### 4. Impulse Response Analysis

```python
"""
Analyze impulse responses for convolution reverb plugins.
"""
from scipy.signal import fftconvolve
from scipy.signal import welch
import numpy as np
import soundfile as sf

def analyze_ir(ir_path):
    """Analyze an impulse response file."""
    ir, fs = sf.read(ir_path)
    if ir.ndim > 1:
        ir = ir[:, 0]  # Use left channel

    # RT60 estimation (time for -60dB decay)
    energy = np.cumsum(ir[::-1]**2)[::-1]
    energy_db = 10 * np.log10(energy / energy[0] + 1e-10)

    # Find -60dB point
    rt60_idx = np.argmax(energy_db < -60)
    rt60 = rt60_idx / fs if rt60_idx > 0 else len(ir) / fs

    # Frequency response
    freqs, response = welch(ir, fs=fs, nperseg=min(4096, len(ir)))
    response_db = 10 * np.log10(response + 1e-10)

    print(f"IR Duration: {len(ir)/fs:.2f}s")
    print(f"Estimated RT60: {rt60:.2f}s")
    print(f"Sample Rate: {fs} Hz")

    return {'rt60': rt60, 'freqs': freqs, 'response_db': response_db}

# Apply reverb
dry, fs = sf.read('dry_vocals.wav')
ir, _ = sf.read('hall_ir.wav')
wet = fftconvolve(dry, ir[:, 0] if ir.ndim > 1 else ir, mode='full')[:len(dry)]
wet /= np.max(np.abs(wet))  # Normalize
mixed = 0.7 * dry + 0.3 * wet
sf.write('vocals_with_reverb.wav', mixed, fs)
```

---

## Quick Reference: Import Cheatsheet

```python
# Filter design
from scipy.signal import butter, cheby1, cheby2, ellip, bessel
from scipy.signal import firwin, firwin2, iirdesign

# Filter application
from scipy.signal import sosfilt, lfilter, filtfilt

# Spectral analysis
from scipy.signal import welch, periodogram, spectrogram

# Windows
from scipy.signal.windows import hann, hamming, blackman, kaiser, get_window

# Convolution
from scipy.signal import convolve, fftconvolve, correlate

# Peaks
from scipy.signal import find_peaks

# Resampling
from scipy.signal import resample, decimate, resample_poly

# Envelope
from scipy.signal import hilbert

# Analysis
from scipy.signal import freqz, sosfreqz, group_delay, tf2zpk
```
