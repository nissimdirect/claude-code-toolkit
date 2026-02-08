# Real-Time Video Processing Tools Reference

> Comprehensive guide to creative real-time video processing tools for visual artists and musicians.
> Last updated: 2026-02-07

---

## Table of Contents

1. [Processing / p5.js for Video Manipulation](#processing--p5js-for-video-manipulation)
2. [TouchDesigner for Audio-Reactive Visuals](#touchdesigner-for-audio-reactive-visuals)
3. [OpenCV Python for Creative Video Processing](#opencv-python-for-creative-video-processing)
4. [Shader-Based Glitch Effects (GLSL)](#shader-based-glitch-effects-glsl)
5. [Audio-Reactive Video Techniques](#audio-reactive-video-techniques)
6. [Tools Comparison](#tools-comparison)

---

## Processing / p5.js for Video Manipulation

### What is Processing?

Processing is a free, open-source programming environment designed specifically for visual artists and designers. Created in 2001 by Ben Fry and Casey Reas, it functions as an accessible gateway into creative coding.

**p5.js** is the JavaScript variant that runs in web browsers, making it ideal for web-based creative projects and easy sharing.

Core philosophy: "Code is today's creative medium, just as paint and canvas were for visual artists of the past."

### Sketch Structure

Processing operates on a two-function model:

```java
// Processing (Java)
void setup() {
    size(1280, 720);        // Canvas size
    // Initialize once
}

void draw() {
    // Runs continuously (default 60fps)
    // Frame-by-frame rendering happens here
}
```

```javascript
// p5.js (JavaScript)
function setup() {
    createCanvas(1280, 720);
}

function draw() {
    // Continuous loop
}
```

### Video Playback in p5.js

```javascript
let video;

function setup() {
    createCanvas(640, 480);
    // Create video element (supports MP4, WebM fallback)
    video = createVideo(['clip.mp4', 'clip.webm']);
    video.size(640, 480);
    video.hide();  // Hide the HTML video element
}

function draw() {
    // Draw video frame to canvas
    image(video, 0, 0);
}
```

**Important:** The video plays in an HTML `<video>` element, not directly inside the sketch. Use `video.hide()` and draw it to the canvas with `image()` for manipulation.

**Playback Control Methods:**
- `.play()` / `.pause()` -- control playback state
- `.time()` -- get/set elapsed seconds (seeking)
- `.duration()` -- total video length in seconds
- `.volume()` -- audio level (0-1 range)
- `.loop()` -- repeat playback indefinitely
- `.size()` -- adjust display dimensions
- `.speed()` -- playback speed multiplier

### Pixel Data Access

```javascript
function draw() {
    video.loadPixels();  // Load pixel data from current frame

    // Pixel array: sequential RGBA values
    // Offset calculation: ((y * width) + x) * 4
    for (let y = 0; y < video.height; y++) {
        for (let x = 0; x < video.width; x++) {
            let index = (y * video.width + x) * 4;
            let r = video.pixels[index + 0];
            let g = video.pixels[index + 1];
            let b = video.pixels[index + 2];
            let a = video.pixels[index + 3];

            // Modify pixels here...
            // Example: invert colors
            video.pixels[index + 0] = 255 - r;
            video.pixels[index + 1] = 255 - g;
            video.pixels[index + 2] = 255 - b;
        }
    }
    video.updatePixels();
    image(video, 0, 0);
}
```

### Webcam Capture

```javascript
let capture;

function setup() {
    createCanvas(640, 480);
    capture = createCapture(VIDEO);
    capture.size(640, 480);
    capture.hide();
}

function draw() {
    capture.loadPixels();
    // Process pixels...
    image(capture, 0, 0);
}
```

### p5.glitch Library

A dedicated p5.js library for glitching images and binary files in the browser.

**Installation:**
```html
<script src="https://cdn.jsdelivr.net/npm/p5.glitch@latest/p5.glitch.js"></script>
```

**Core API:**

```javascript
let glitch;

function setup() {
    createCanvas(640, 480);
    glitch = new Glitch();
    glitch.loadType('jpg');        // Format: jpg, png, webp
    glitch.loadQuality(0.5);       // JPEG quality (0.0-1.0)
    glitch.pixelate(1);            // Hard pixel edges
}

function draw() {
    // Load from image, video, or webcam
    glitch.loadImage(capture);

    // Apply glitch effects
    glitch.randomBytes(10);        // Randomize 10 bytes
    glitch.replaceBytes(100, 200); // Find byte 100, replace with 200
    glitch.replaceHex('FF', '00'); // Hex-level replacement

    // Build and display
    glitch.buildImage(function() {
        image(glitch.image, 0, 0);
    });
}

// Reset to original
glitch.resetBytes();

// Save
glitch.saveImage('glitched');       // Raw glitched file
glitch.saveSafe('clean', 'png');    // Stable, playable version
glitch.saveCanvas('screenshot');    // Capture entire canvas
```

**Technical Architecture:** The library operates through byte-level manipulation. After loading content, it exposes `bytes` (original) and `bytesGlitched` (modified) arrays. Users apply transformations, then rebuild visual output through `buildImage()`. The `glitch.image` property stores the compiled p5.Image object for display.

### Processing Strengths for Video Art

- Very beginner-friendly -- minimal code to get visual results
- Real-time rendering at 60fps with hardware acceleration
- Interactive -- responds to mouse, keyboard, MIDI, OSC
- Large community with examples and libraries
- p5.js variant makes sharing via web instant

### Processing Limitations

- Performance ceiling for heavy pixel manipulation (no GPU compute)
- Video scrubbing can be unreliable (browser-dependent in p5.js)
- No built-in shader support in p5.js (need WebGL mode for GLSL)
- Not ideal for production pipelines (better for prototyping and performance)

---

## TouchDesigner for Audio-Reactive Visuals

### What is TouchDesigner?

TouchDesigner is a node-based visual programming environment for creating real-time interactive multimedia content. Made by Derivative, it is the industry standard for:

- Live VJ performances
- Interactive installations
- Projection mapping
- Audio-reactive visuals
- Music videos and content creation

### Node-Based Architecture

TouchDesigner uses four primary operator families:

| Family | Abbreviation | Purpose | Examples |
|--------|-------------|---------|----------|
| **CHOP** | Channel Operators | Time-series data (audio, animation) | Audio Device In, LFO, Math |
| **TOP** | Texture Operators | 2D images and video | Movie File In, Composite, Blur |
| **SOP** | Surface Operators | 3D geometry | Sphere, Grid, Transform |
| **DAT** | Data Operators | Text and tables | Table, Script, Web |

### Audio-Reactive Setup (Step by Step)

**Step 1: Audio Input**

```
Audio Device In CHOP
  - Set Device to your audio interface or system audio
  - Outputs raw audio waveform data
```

**Step 2: Audio Analysis**

```
Audio Device In CHOP --> Audio Spectrum CHOP --> Math CHOP

Or use the Palette component:
  audioAnalysis component (prebuilt)
    - Outputs: low, mid, high, kick, snare, rhythm channels
    - Each channel = normalized 0-1 float value
```

**Step 3: Audio Spectrum Visualization**

```
Audio Device In CHOP --> Audio Spectrum CHOP --> CHOP to TOP
  - Converts frequency data to a texture
  - Each pixel column = a frequency band
  - Brightness = amplitude
```

**Step 4: Connect Audio to Visual Parameters**

Common mappings:
- **Kick drum** (low frequency) -> controls scale, position Y, brightness
- **Snare** (mid frequency) -> controls rotation, color shift, glitch intensity
- **Hi-hat/high** -> controls particle speed, texture detail, noise amount
- **Overall volume** -> controls master opacity, zoom level

**Step 5: Visual Generation**

```
Noise TOP --> Feedback TOP --> Composite TOP --> Output
     ^                            ^
  Audio data                 More audio data
  (controls                  (controls
   noise seed)                blend mode)
```

### Key Components for Audio-Reactive Work

**Audio Analysis (from Palette):**
- Prebuilt component that analyzes sound
- Splits into data streams: low, mid, high, kick, snare, rhythm
- Drag from Palette browser into your project

**CHOP to TOP:**
- Converts channel data to visual texture
- Essential bridge between audio and visuals

**Feedback TOP:**
- Routes output back to input for recursive effects
- Creates trails, echoes, and organic movement
- Controls: feedback amount, scale, rotation per frame

**Noise TOP:**
- Generates Perlin noise, simplex noise, random patterns
- Audio-driven parameters: seed, amplitude, frequency, offset

### TouchDesigner + Audio: Technical Details

**Connecting External Audio:**
1. Use Audio Device In CHOP for line-in or interface input
2. Set sample rate to match your audio interface (44100 or 48000)
3. For virtual routing: use Blackhole, Loopback, or JACK

**Beat Detection:**
- audioAnalysis component provides kick/snare/rhythm channels
- Threshold-based detection for triggering events
- Smooth output with Lag CHOP for gradual reactions

**MIDI/OSC Input:**
- MIDI In CHOP for hardware controllers
- OSC In CHOP for software control (Ableton Link, etc.)

### TouchDesigner Strengths

- No code required for basic setups (visual node patching)
- GPU-accelerated -- handles high-resolution video in real-time
- Built-in audio analysis with the Palette audioAnalysis component
- Supports GLSL shaders for custom effects
- Projection mapping tools built in
- Active community with tutorials and shared projects

### TouchDesigner Limitations

- Commercial license required for output above 1280x1280
- Learning curve for complex node networks
- Windows primary (macOS version exists but less performant)
- Heavy on GPU -- needs decent graphics card
- Not scriptable for batch processing (real-time focused)

---

## OpenCV Python for Creative Video Processing

### What is OpenCV?

OpenCV (Open Computer Vision) is a library primarily designed for computer vision but widely used for creative video processing. It provides fast, optimized C++ operations accessible through Python bindings.

### Basic Video Processing Pipeline

```python
import cv2
import numpy as np

# Open video file or webcam
cap = cv2.VideoCapture("input.mp4")  # or cv2.VideoCapture(0) for webcam

# Get video properties
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# Output writer
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter("output.mp4", fourcc, fps, (width, height))

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Apply effects to frame (NumPy array, shape: height x width x 3, BGR)
    processed = apply_effect(frame)

    out.write(processed)

    # Optional: display in real-time
    cv2.imshow("Preview", processed)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
out.release()
cv2.destroyAllWindows()
```

### Creative Effects with OpenCV

**Chromatic Aberration:**

```python
def chromatic_aberration_cv(frame, offset=10):
    """RGB channel offset for chromatic aberration."""
    b, g, r = cv2.split(frame)

    M_left = np.float32([[1, 0, -offset], [0, 1, 0]])
    M_right = np.float32([[1, 0, offset], [0, 1, 0]])

    h, w = frame.shape[:2]
    r = cv2.warpAffine(r, M_right, (w, h))
    b = cv2.warpAffine(b, M_left, (w, h))

    return cv2.merge([b, g, r])
```

**Scanline Effect:**

```python
def scanlines_cv(frame, spacing=2, darkness=0.3):
    """Add horizontal scanlines."""
    result = frame.copy().astype(np.float64)
    result[::spacing] *= (1.0 - darkness)
    return result.astype(np.uint8)
```

**Pixel Sorting (Row-Based):**

```python
def pixel_sort_cv(frame, threshold_low=50, threshold_high=200):
    """Fast pixel sorting using OpenCV/NumPy."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    for y in range(frame.shape[0]):
        row = frame[y]
        brightness = gray[y]
        mask = (brightness > threshold_low) & (brightness < threshold_high)

        changes = np.diff(mask.astype(int))
        starts = np.where(changes == 1)[0] + 1
        ends = np.where(changes == -1)[0] + 1

        if mask[0]:
            starts = np.concatenate(([0], starts))
        if mask[-1]:
            ends = np.concatenate((ends, [len(mask)]))

        for s, e in zip(starts, ends):
            if e - s > 1:
                segment = row[s:e]
                sort_key = np.mean(segment, axis=1)
                frame[y, s:e] = segment[np.argsort(sort_key)]

    return frame
```

**VHS Distortion:**

```python
def vhs_effect_cv(frame):
    """Composite VHS look."""
    h, w = frame.shape[:2]

    result = chromatic_aberration_cv(frame, offset=5)
    result = scanlines_cv(result, spacing=2, darkness=0.15)

    for y in range(h):
        if np.random.random() < 0.01:
            shift = np.random.randint(-20, 20)
            result[y] = np.roll(result[y], shift, axis=0)

    noise = np.random.randint(0, 30, frame.shape, dtype=np.uint8)
    result = cv2.add(result, noise)
    result = cv2.GaussianBlur(result, (3, 3), 0.5)

    return result
```

**Face Tracking + Glitch:**

```python
import dlib

def face_glitch_cv(frame, detector=None):
    """Detect faces and apply glitch effects to face regions."""
    if detector is None:
        detector = dlib.get_frontal_face_detector()

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = detector(gray)

    for face in faces:
        x1, y1 = face.left(), face.top()
        x2, y2 = face.right(), face.bottom()

        face_region = frame[y1:y2, x1:x2].copy()

        small = cv2.resize(face_region, (8, 8), interpolation=cv2.INTER_LINEAR)
        pixelated = cv2.resize(small, (x2-x1, y2-y1), interpolation=cv2.INTER_NEAREST)

        frame[y1:y2, x1:x2] = pixelated

    return frame
```

### Live-Glitch Project (Reference)

An open-source project providing real-time glitch effects via webcam:

**Effects available:**
1. VHS Date Text and Scanlines (v key)
2. Face Dragging -- stretches facial regions (f key)
3. Face Glitch -- pixelated facial distortions (g key)
4. Tears -- downward streaking effects (t key)
5. Censor Bar -- blackout rectangles (b key)

**Dependencies:** OpenCV, dlib, NumPy, Pillow

**Source:** https://github.com/makew0rld/live-glitch

### OpenCV Strengths

- Very fast -- C++ backend with Python convenience
- Rich feature set -- computer vision, face detection, optical flow
- NumPy native -- frames are NumPy arrays, easy to manipulate
- Cross-platform -- works everywhere
- Good for batch processing and command-line tools

### OpenCV Limitations

- No built-in GUI for real-time parameter tweaking
- Not GPU-accelerated by default (CUDA module available separately)
- Video codec support can be tricky (depends on FFmpeg build)
- Steeper learning curve than Processing for beginners

---

## Shader-Based Glitch Effects (GLSL)

### What are Shaders?

Shaders are programs that run on the GPU, processing every pixel in parallel. They are the fastest way to apply real-time visual effects. GLSL (OpenGL Shading Language) is the most common shader language for creative coding.

### Fragment Shader Basics

A fragment shader runs once per pixel and outputs the color for that pixel:

```glsl
// Minimal fragment shader
precision mediump float;

uniform sampler2D u_texture;  // Input image/video
uniform vec2 u_resolution;    // Canvas size
uniform float u_time;         // Time in seconds

varying vec2 v_texCoord;      // Current pixel's UV coordinate (0-1)

void main() {
    vec2 uv = v_texCoord;
    vec4 color = texture2D(u_texture, uv);
    gl_FragColor = color;  // Output: RGBA
}
```

### Glitch Effect: Chromatic Aberration

```glsl
void main() {
    vec2 uv = v_texCoord;
    float offset = 0.01;  // Adjust for intensity

    float r = texture2D(u_texture, uv + vec2(offset, 0.0)).r;
    float g = texture2D(u_texture, uv).g;
    float b = texture2D(u_texture, uv - vec2(offset, 0.0)).b;

    gl_FragColor = vec4(r, g, b, 1.0);
}
```

### Glitch Effect: Random Stripe Displacement

```glsl
float random(vec2 co) {
    return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
    vec2 uv = v_texCoord;

    float stripe = step(0.5, random(vec2(floor(uv.y * 20.0), u_time)));
    float displacement = stripe * 0.05;
    uv.x += displacement;

    gl_FragColor = texture2D(u_texture, uv);
}
```

### Glitch Effect: Wavy Displacement

```glsl
void main() {
    vec2 uv = v_texCoord;

    float wave = sin(uv.y * 50.0 + u_time * 3.0) * 0.01;
    uv.x += wave;

    gl_FragColor = texture2D(u_texture, uv);
}
```

### Glitch Effect: Block Corruption

```glsl
float random(vec2 co) {
    return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
    vec2 uv = v_texCoord;

    vec2 blockSize = vec2(0.05, 0.1);
    vec2 block = floor(uv / blockSize);

    float r = random(block + floor(u_time * 2.0));

    if (r > 0.8) {
        uv.x += (random(block) - 0.5) * 0.1;
        uv.y += (random(block + 1.0) - 0.5) * 0.05;
    }

    gl_FragColor = texture2D(u_texture, uv);
}
```

### Combined Glitch Shader

```glsl
precision mediump float;

uniform sampler2D u_texture;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_intensity;  // 0.0 - 1.0

varying vec2 v_texCoord;

float random(vec2 co) {
    return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
    vec2 uv = v_texCoord;
    float intensity = u_intensity;

    // 1. Random stripe displacement
    float stripe = step(0.5, random(vec2(floor(uv.y * 30.0), floor(u_time * 5.0))));
    uv.x += stripe * intensity * 0.03;

    // 2. Wavy displacement
    uv.x += sin(uv.y * 40.0 + u_time * 2.0) * intensity * 0.005;

    // 3. Chromatic aberration
    float ca_offset = intensity * 0.015;
    float r = texture2D(u_texture, uv + vec2(ca_offset, 0.0)).r;
    float g = texture2D(u_texture, uv).g;
    float b = texture2D(u_texture, uv - vec2(ca_offset, 0.0)).b;

    // 4. Scanlines
    float scanline = sin(uv.y * u_resolution.y * 1.5) * 0.04 * intensity;

    gl_FragColor = vec4(r - scanline, g - scanline, b - scanline, 1.0);
}
```

### Where to Write and Test Shaders

| Platform | Language | Use Case |
|----------|----------|----------|
| **Shadertoy** (shadertoy.com) | GLSL | Browser-based, great for learning |
| **Processing** (PShader) | GLSL | Desktop creative coding |
| **p5.js** (WebGL mode) | GLSL | Browser-based, video input |
| **TouchDesigner** (GLSL TOP) | GLSL | Real-time performance |
| **Three.js** | GLSL | Web 3D + post-processing |
| **ISF** (Interactive Shader Format) | GLSL | VJ software (VDMX, CoGe) |

### Control Parameters for Live Performance

The shader above uses a `u_intensity` uniform. In a live context, this can be driven by:

- MIDI controller knob (0-127 mapped to 0.0-1.0)
- Audio amplitude (beat detection)
- OSC messages from another application
- Mouse position
- Automated LFO

---

## Audio-Reactive Video Techniques

### General Architecture

```
Audio Source --> Analysis --> Parameter Mapping --> Visual Engine --> Output

Examples:
  DAW output --> FFT spectrum --> frequency bands --> TouchDesigner nodes --> projector
  Microphone --> beat detection --> triggers --> p5.js sketch --> screen
  Audio file --> amplitude envelope --> shader uniforms --> GLSL --> recording
```

### Technique 1: FFT Spectrum Mapping

Split audio into frequency bands and map each to a visual parameter:

```python
import numpy as np

def analyze_audio_frame(audio_samples, sample_rate=44100, num_bands=8):
    """Perform FFT and split into frequency bands."""
    fft = np.abs(np.fft.rfft(audio_samples))
    freqs = np.fft.rfftfreq(len(audio_samples), 1.0 / sample_rate)

    band_edges = np.logspace(np.log10(20), np.log10(20000), num_bands + 1)

    bands = []
    for i in range(num_bands):
        mask = (freqs >= band_edges[i]) & (freqs < band_edges[i + 1])
        bands.append(np.mean(fft[mask]) if np.any(mask) else 0)

    return np.array(bands)
```

**Common Frequency-to-Visual Mappings:**

| Frequency Band | Visual Parameter |
|----------------|-----------------|
| Sub-bass (20-60 Hz) | Background pulse, zoom |
| Bass (60-250 Hz) | Object scale, position Y |
| Low-mid (250-500 Hz) | Color warmth, saturation |
| Mid (500-2000 Hz) | Rotation speed, complexity |
| Upper-mid (2-4 kHz) | Brightness, contrast |
| Presence (4-6 kHz) | Particle speed, detail |
| Brilliance (6-20 kHz) | Noise amount, sparkle |

### Technique 2: Beat Detection

```python
def detect_beat(current_energy, history, threshold_multiplier=1.5):
    """Simple energy-based beat detection."""
    avg_energy = np.mean(history)
    if current_energy > avg_energy * threshold_multiplier:
        return True
    return False
```

Beats can trigger: color changes, scene transitions, glitch bursts, shape transformations, particle explosions.

### Technique 3: Amplitude Envelope Following

```python
def amplitude_envelope(audio_samples):
    """Get RMS amplitude of audio frame."""
    return np.sqrt(np.mean(audio_samples ** 2))

class SmoothedAmplitude:
    def __init__(self, smoothing=0.9):
        self.value = 0
        self.smoothing = smoothing

    def update(self, new_value):
        self.value = self.value * self.smoothing + new_value * (1 - self.smoothing)
        return self.value
```

### Technique 4: Onset Detection

```python
def spectral_flux(current_spectrum, previous_spectrum):
    """Detect onsets via spectral flux."""
    diff = current_spectrum - previous_spectrum
    diff[diff < 0] = 0
    return np.sum(diff)
```

### Tools for Audio-Reactive Work

| Tool | Audio Input | Visual Output | Difficulty | Best For |
|------|------------|---------------|------------|----------|
| **TouchDesigner** | Audio Device In CHOP | GPU-rendered TOPs | Medium | Live performance, installations |
| **Processing** | Minim / Sound library | Canvas rendering | Easy | Learning, prototyping |
| **p5.js** | p5.sound / Web Audio API | Browser canvas | Easy | Web-based, sharing |
| **Python + OpenCV** | pyaudio / sounddevice | OpenCV window / file | Medium | Batch processing, custom tools |
| **Max/MSP + Jitter** | Native audio | Jitter video engine | Hard | Complex interactive systems |
| **VDMX** | Audio input / Syphon | Multiple outputs | Easy | VJ performance |

---

## Tools Comparison

### Processing / p5.js vs TouchDesigner vs Custom Python

| Feature | Processing / p5.js | TouchDesigner | Python (OpenCV/Pillow) |
|---------|-------------------|---------------|----------------------|
| **Learning Curve** | Low | Medium | Medium-High |
| **Real-Time Performance** | Good (60fps typical) | Excellent (GPU-native) | Moderate (CPU-bound) |
| **GPU Acceleration** | WebGL mode only | Native GPU | Requires CUDA setup |
| **Audio Integration** | Minim/p5.sound | Built-in CHOP system | pyaudio/sounddevice |
| **Video Input** | Webcam, files | All sources | Webcam, files |
| **Shader Support** | GLSL (WebGL mode) | GLSL TOP (native) | Requires OpenGL setup |
| **Batch Processing** | Poor | Poor | Excellent |
| **Output Quality** | Screen/web | 4K+, projection | Any resolution |
| **Cost** | Free | Free (limited) / $600+ | Free |
| **Platform** | Cross-platform / Web | Win primary, Mac secondary | Cross-platform |
| **Community** | Massive | Large (growing) | Massive (but not art-focused) |
| **Best For** | Learning, web art, prototyping | Live performance, installations | Offline processing, pipelines |

### Recommended Workflow for Music Video Production

1. **Prototype** effects in p5.js or Processing (fast iteration)
2. **Build pipeline** in Python/OpenCV for batch frame processing
3. **Use TouchDesigner** for audio-reactive elements that need real-time
4. **Write custom GLSL shaders** for GPU-intensive effects
5. **Composite everything** in DaVinci Resolve or After Effects
6. **Use FFmpeg** for final encoding and format conversion

### Recommended Workflow for Live VJ Performance

1. **TouchDesigner** as the main visual engine
2. **MIDI controller** for parameter control
3. **Audio input** via Audio Device In CHOP
4. **Custom GLSL shaders** loaded via GLSL TOP
5. **Syphon/Spout** for routing to other software
6. **Projection mapping** built into TouchDesigner

---

## Resources and Links

### Processing / p5.js
- [Processing.org](https://processing.org/)
- [p5.js](https://p5js.org/)
- [p5.glitch Library](https://github.com/ffd8/p5.glitch)
- [Working with Video (Creative Coding)](https://creative-coding.decontextualize.com/video/)
- [Getting Started with Processing Creative Coding](https://stevezafeiriou.com/processing-creative-coding/)
- [Awesome Creative Coding (GitHub)](https://github.com/terkelg/awesome-creative-coding)
- [FOSDEM 2026: Processing Talk](https://fosdem.org/2026/schedule/event/7TY3JV-processing/)

### TouchDesigner
- [Derivative (TouchDesigner)](https://derivative.ca/)
- [Audio Reactive Beginner Guide](https://interactiveimmersive.io/blog/touchdesigner-3d/audio-reactive-visuals-a-beginner-guide/)
- [Audio Reactive Tutorial (Derivative)](https://derivative.ca/community-post/tutorial/tutorial-23-audio-reactive-motion-controlled-visuals-touchdesigner/68129)
- [Audio Reactive GitHub Guide](https://github.com/LucieMrc/TD_audioreact_love_EN)
- [All TouchDesigner](https://alltd.org/)
- [Music Hackspace: Beat Detection in TD](https://musichackspace.org/product/introduction-to-beat-detection-and-audio-reactive-visuals-in-touchdesigner/)

### OpenCV / Python
- [OpenCV Python Documentation](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
- [Live-Glitch (Real-Time OpenCV Glitch)](https://github.com/makew0rld/live-glitch)
- [Video Editing with Python/OpenCV](https://andersoncanteli.wordpress.com/2020/03/02/video-editing-with-python-opencv/)

### GLSL Shaders
- [Shadertoy](https://www.shadertoy.com/)
- [Glitch Image Effect Shader (Harry Alisavakis)](https://halisavakis.com/my-take-on-shaders-glitch-image-effect/)
- [Three.js GLSL Glitch Effects](https://zenn.dev/er/articles/6c696c5a0ddc41)
- [Rendering Video Effects in GLSL](https://www.asawicki.info/news_1573_rendering_video_special_effects_in_glsl)
- [The Book of Shaders](https://thebookofshaders.com/)
- [ISF (Interactive Shader Format)](https://isf.video/)

### VJ / Live Performance
- [Top 7 VJ Software (VJ Galaxy)](https://vjgalaxy.com/blogs/resources-digital-assets/best-software-to-create-real-time-vj-visuals)
- [VDMX](https://vidvox.net/)
- [Resolume](https://resolume.com/)
