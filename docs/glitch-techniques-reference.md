# Glitch Art Techniques Reference

> Compiled from web research on datamoshing, pixel sorting, and glitch art tools.
> Sources linked throughout.

---

## Table of Contents

1. [Datamoshing](#1-datamoshing)
2. [Pixel Sorting](#2-pixel-sorting)
3. [Byte-Level Corruption (Databending)](#3-byte-level-corruption-databending)
4. [Optical Flow Transfer](#4-optical-flow-transfer)
5. [JPEG/PNG Corruption](#5-jpegpng-corruption)
6. [Open Source Glitch Tools](#6-open-source-glitch-tools)

---

## 1. Datamoshing

Datamoshing exploits video compression by removing or manipulating keyframes (I-frames), causing the decoder to apply motion vectors from new footage to pixels from old footage.

### How Video Compression Works (The Basis)

| Frame Type | Name | Contains | Dependency |
|------------|------|----------|------------|
| **I-frame** | Intra-coded | Complete image | None (self-contained) |
| **P-frame** | Predicted | Differences from previous frame | Previous I or P frame |
| **B-frame** | Bi-predictive | Differences from previous AND next | Previous + next frames |

When you remove an I-frame, subsequent P-frames try to reference a frame that no longer exists. The decoder uses whatever was last successfully decoded, causing motion vectors from new content to warp old pixels.

### Two Main Datamosh Effects

| Effect | Method | Result |
|--------|--------|--------|
| **Bloom / Glide** | Remove I-frames between two clips | Motion from clip B applies to pixels of clip A. Pixels "melt" and flow. |
| **Melt / Repeat** | Duplicate P-frames | Same motion applied repeatedly, causing pixels to smear in one direction |

### Method 1: FFmpeg Datamosh Prep

```bash
# Step 1: Encode with minimal I-frames, no B-frames
ffmpeg -i input.mp4 -c:v libx264 -g 999999 -keyint_min 999999 -bf 0 -sc_threshold 0 -crf 18 datamosh_prep.mp4

# Step 2: View frame types (verify I-frame placement)
ffprobe -v quiet -print_format json -show_entries "frame=pict_type,coded_picture_number" -select_streams v:0 datamosh_prep.mp4

# Step 3: Visualize motion vectors
ffplay -flags2 +export_mvs datamosh_prep.mp4 -vf codecview=mv=pf+bf+bb
```

Key FFmpeg flags for datamosh prep:

| Flag | Value | Purpose |
|------|-------|---------|
| `-g` | 999999 | Max GOP size (keyframe interval) |
| `-keyint_min` | 999999 | Min keyframe interval |
| `-bf` | 0 | Disable B-frames |
| `-sc_threshold` | 0 | Disable scene change detection (prevents auto I-frames) |

### Method 2: AviGlitch (Ruby)

[AviGlitch](https://ucnv.github.io/aviglitch/) is a Ruby library for manipulating AVI files at the frame level.

```bash
# Install
gem install aviglitch

# Built-in datamosh command
datamosh input.avi -o moshed.avi
```

**Prep for AviGlitch:**
```bash
# Convert to AVI with MPEG-4, no B-frames
ffmpeg -i input.mp4 -c:v mpeg4 -g 300 -bf 0 -q:v 3 -an ready.avi
```

**Ruby script for selective I-frame removal:**
```ruby
require 'aviglitch'

a = AviGlitch.open('input.avi')
# Remove all keyframes except the first
first = true
a.frames.each do |f|
  if f.is_keyframe?
    if first
      first = false
    else
      f.data = nil  # Remove this I-frame
    end
  end
end
a.output('moshed.avi')
```

### Method 3: moshy (CLI tool)

[moshy](https://github.com/wayspurrchen/moshy) / [GlitchTools/moshy](https://github.com/GlitchTools/moshy) -- command-line datamoshing toolkit.

```bash
# Install
gem install moshy

# Prep video (converts to moshable AVI)
moshy -m prep -i input.mp4 -o prepped.avi

# Bloom mosh (remove I-frames)
moshy -m isplit -i prepped.avi -o moshed.avi

# Duplicate P-frames for melt effect
moshy -m ppulse -i prepped.avi -o melted.avi --count 30
```

### Method 4: python-moshion

[python-moshion](https://github.com/rjmoggach/python-moshion) -- Python wrapper around FFmpeg for datamoshing image sequences.

### Method 5: ffmosher

[ffmosher](https://github.com/davFaithid/ffmosher) -- Direct datamoshing with FFmpeg.

### Method 6: moshpit

[moshpit](https://github.com/CrushedPixel/moshpit) -- Cross-platform command-line datamosh tool. Powerful and modern.

### I-Frame Removal via Avidemux

Manual GUI method:
1. Open video in Avidemux
2. Set Video Output to "MPEG-4 ASP (Xvid)"
3. Configure: Max I-frame interval = high value, B-frames = 0
4. Navigate frame-by-frame, identify I-frames
5. Delete I-frames manually
6. Save/export

### Timestamp Fix

After removing I-frames, timestamps can become corrupted causing stuttering:
```bash
# Reset timestamps after datamosh
ffmpeg -i moshed.avi -vf "setpts=PTS-STARTPTS" -c:v libx264 -crf 18 fixed.mp4

# Or with -fflags +genpts
ffmpeg -fflags +genpts -i moshed.avi -c:v libx264 -crf 18 fixed.mp4
```

---

## 2. Pixel Sorting

Pixel sorting selectively reorders pixels within rows or columns based on a property (lightness, hue, saturation). Popularized by artist Kim Asendorf.

### How It Works

1. **Define intervals** -- Split each row/column into segments where sorting should occur
2. **Sort pixels** within each interval by a chosen property
3. Unsorted regions (outside intervals) remain unchanged

### Python Implementation: pixelsort

[pixelsort](https://github.com/satyarth/pixelsort) -- the most complete Python implementation.

```bash
# Install
pip install pixelsort
```

**Python API:**
```python
from pixelsort import pixelsort
from PIL import Image

img = Image.open("input.jpg")
result = pixelsort(img)
result.save("sorted.png")
```

**CLI Usage:**
```bash
# Default (threshold intervals, lightness sort)
python3 -m pixelsort input.jpg -o sorted.png

# Sort by hue with edge detection intervals
python3 -m pixelsort input.jpg -i edges -s hue -o sorted.png

# Random intervals with custom width
python3 -m pixelsort input.jpg -i random -c 20 -o sorted.png

# Vertical sorting (90-degree angle)
python3 -m pixelsort input.jpg -a 90 -o sorted.png

# With mask (only sort masked region)
python3 -m pixelsort input.jpg -m mask.png -i random -c 20 -o sorted.png

# Diagonal sorting
python3 -m pixelsort input.jpg -a 45 -o sorted.png
```

**Sorting Functions:**

| Function | Flag | Description |
|----------|------|-------------|
| `lightness` | `-s lightness` | HSL lightness (default) |
| `hue` | `-s hue` | Color hue angle |
| `saturation` | `-s saturation` | Color intensity |
| `intensity` | `-s intensity` | Sum of RGB values |
| `minimum` | `-s minimum` | Min of R, G, B values |

**Interval Functions:**

| Function | Flag | Description |
|----------|------|-------------|
| `threshold` | `-i threshold` | Lightness between `-t` (lower) and `-u` (upper) thresholds |
| `edges` | `-i edges` | Edge detection defines interval boundaries |
| `random` | `-i random` | Random interval widths (scale with `-c`) |
| `waves` | `-i waves` | Uniform-width wave intervals |
| `file` | `-i file` | B&W image defines sorting regions (white = sort) |
| `file-edges` | `-i file-edges` | Edge detection on external image |
| `none` | `-i none` | Sort entire rows/columns |

**Key Parameters:**

| Param | Flag | Default | Description |
|-------|------|---------|-------------|
| Lower threshold | `-t` | 0.25 | Minimum lightness for threshold intervals |
| Upper threshold | `-u` | 0.8 | Maximum lightness for threshold intervals |
| Characteristic length | `-c` | 50 | Width scale for random/wave intervals |
| Angle | `-a` | 0 | Sorting direction in degrees |
| Randomness | `-r` | 0 | Percentage of intervals to skip (0-100) |
| Mask | `-m` | none | B&W mask image |

### Pixel Sorting for Video

Apply pixel sorting frame-by-frame:
```bash
# 1. Extract frames
ffmpeg -i input.mp4 frames/frame_%04d.png

# 2. Sort each frame (bash loop)
for f in frames/frame_*.png; do
    python3 -m pixelsort "$f" -i edges -s lightness -o "sorted_$f"
done

# 3. Reassemble
ffmpeg -framerate 30 -i sorted_frames/frame_%04d.png -c:v libx264 -crf 18 sorted_video.mp4
```

**Python batch processing:**
```python
from pixelsort import pixelsort
from PIL import Image
import glob

for path in sorted(glob.glob("frames/frame_*.png")):
    img = Image.open(path)
    result = pixelsort(img, interval_function="edges", sorting_function="lightness")
    result.save(path.replace("frames/", "sorted_frames/"))
```

### Other Pixel Sorting Tools

- [rkargon/pixelsorter](https://github.com/rkargon/pixelsorter) -- Alternative Python implementation
- [a-gratton/PixelSort](https://github.com/a-gratton/PixelSort) -- Pillow-based, uses Radix-LSD sorting with multiprocessing
- [DavidMcLaughlin208/PixelSorting](https://github.com/DavidMcLaughlin208/PixelSorting) -- C++ with OpenFrameworks, GPU-accelerated, real-time video support

---

## 3. Byte-Level Corruption (Databending)

Treating non-audio files as audio data, or directly editing file bytes.

### Audacity Databending

```bash
# 1. Export video as raw pixel data
ffmpeg -i input.mp4 -f rawvideo -pix_fmt yuv420p raw.yuv

# 2. Import raw.yuv into Audacity:
#    File > Import > Raw Data
#    Encoding: Unsigned 8-bit
#    Byte order: No endianness
#    Channels: 1 (Mono)
#    Sample rate: 48000

# 3. Apply audio effects:
#    - Echo (creates visual repetition)
#    - Reverb (creates ghosting/smearing)
#    - Phaser (creates banding patterns)
#    - Paulstretch (extreme time-stretch creates abstract textures)
#    - Wahwah (creates color oscillation)

# 4. Export as raw data (Header: RAW, Encoding: Unsigned 8-bit)

# 5. Convert back
ffmpeg -f rawvideo -pix_fmt yuv420p -s 1920x1080 -r 30 -i processed.yuv \
       -c:v libx264 -preset ultrafast -crf 18 result.mp4
```

**Warning:** Corrupting the first few bytes of a YUV file will likely make it unreadable. Apply effects to the middle/end sections.

### Hex Editor Corruption

Open any video file in a hex editor and modify bytes:
- Change values in the middle of the file (avoid headers)
- Search for patterns and replace systematically
- Works best on MJPEG, MPEG-4, and uncompressed formats

### Python Byte Corruption

```python
import random

def corrupt_file(input_path, output_path, corruption_rate=0.001, skip_header=1000):
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())

    # Skip header bytes to avoid breaking the container
    for i in range(skip_header, len(data)):
        if random.random() < corruption_rate:
            data[i] = random.randint(0, 255)

    with open(output_path, 'wb') as f:
        f.write(data)

corrupt_file("input.avi", "corrupted.avi", corruption_rate=0.0005)
```

---

## 4. Optical Flow Transfer

An alternative to destructive datamoshing that uses motion estimation to create similar effects non-destructively.

### Concept

1. Calculate optical flow between consecutive frames (how pixels move)
2. Apply those motion vectors to a different image or video
3. Creates the "pixel bleeding" look without actually corrupting files

### Python Implementation (OpenCV)

```python
import cv2
import numpy as np

def optical_flow_transfer(source_video, reference_image, output_path):
    cap = cv2.VideoCapture(source_video)
    ref = cv2.imread(reference_image)

    ret, prev_frame = cap.read()
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    h, w = ref.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, 30.0, (w, h))

    current_image = ref.copy().astype(np.float32)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Calculate optical flow (Farneback method)
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )

        # Create remap coordinates
        h, w = flow.shape[:2]
        map_x = np.float32(np.tile(np.arange(w), (h, 1))) + flow[:, :, 0]
        map_y = np.float32(np.tile(np.arange(h).reshape(-1, 1), (1, w))) + flow[:, :, 1]

        # Apply flow to current image
        current_image = cv2.remap(
            current_image, map_x, map_y,
            cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )

        out.write(current_image.astype(np.uint8))
        prev_gray = gray

    cap.release()
    out.release()
```

---

## 5. JPEG/PNG Corruption

### JPEG Glitching

JPEG files use blocks of 8x8 pixels. Corrupting different sections produces different effects:

```python
import random

def glitch_jpeg(input_path, output_path, num_glitches=10):
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())

    # Find JPEG data section (after headers)
    # SOS marker = 0xFF 0xDA
    sos_pos = data.find(b'\xff\xda')
    if sos_pos == -1:
        return

    # Only corrupt data after SOS (scan data, not headers)
    start = sos_pos + 10  # Skip SOS header
    end = len(data) - 2   # Skip EOI marker

    for _ in range(num_glitches):
        pos = random.randint(start, end)
        data[pos] = random.randint(0, 255)

    with open(output_path, 'wb') as f:
        f.write(data)
```

### PNG Channel Manipulation

```python
from PIL import Image
import numpy as np

def channel_shift(input_path, output_path, shift_x=10, shift_y=5):
    img = Image.open(input_path)
    arr = np.array(img)

    # Shift red channel
    arr[:, :, 0] = np.roll(arr[:, :, 0], shift_x, axis=1)
    # Shift blue channel
    arr[:, :, 2] = np.roll(arr[:, :, 2], -shift_x, axis=1)
    arr[:, :, 2] = np.roll(arr[:, :, 2], shift_y, axis=0)

    Image.fromarray(arr).save(output_path)
```

### Browser-Based Tools

- [Image Glitch Tool](https://snorpey.github.io/jpg-glitch/) -- drag-and-drop JPEG glitching in browser
- [Photomosh](https://photomosh.com/) -- comprehensive browser-based glitch effects

---

## 6. Open Source Glitch Tools

### Video Glitch Tools

| Tool | Language | Type | Link |
|------|----------|------|------|
| **AviGlitch** | Ruby | Datamosh library | [ucnv/aviglitch](https://ucnv.github.io/aviglitch/) |
| **moshy** | Ruby | Datamosh CLI toolkit | [GlitchTools/moshy](https://github.com/GlitchTools/moshy) |
| **moshpit** | Go | Cross-platform datamosh | [CrushedPixel/moshpit](https://github.com/CrushedPixel/moshpit) |
| **ffmosher** | Python | FFmpeg datamosh | [davFaithid/ffmosher](https://github.com/davFaithid/ffmosher) |
| **python-moshion** | Python | Image sequence datamosh | [rjmoggach/python-moshion](https://github.com/rjmoggach/python-moshion) |
| **FaceGlitch** | Processing | Real-time face glitch | [recyclism/faceglitch](http://www.recyclism.com/faceglitch.html) |

### Image Glitch Tools

| Tool | Language | Type | Link |
|------|----------|------|------|
| **pixelsort** | Python | Pixel sorting | [satyarth/pixelsort](https://github.com/satyarth/pixelsort) |
| **Image Glitch Tool** | JavaScript | JPEG glitching (web) | [snorpey/jpg-glitch](https://snorpey.github.io/jpg-glitch/) |
| **Photomosh** | Web app | Multi-effect glitch | [photomosh.com](https://photomosh.com/) |

### Video Editors with Glitch Support

| Tool | Cost | Platform | Notes |
|------|------|----------|-------|
| **Shotcut** | Free/OSS | Win/Mac/Linux | Open source, plugin support |
| **Avidemux** | Free/OSS | Win/Mac/Linux | Manual I-frame deletion |
| **FFmpeg** | Free/OSS | All | CLI, most powerful |

### Curated Resource Lists

- [Glitch Art Resources](https://github.com/Open-Source-Dream-Collective/Glitch-Art-Resources) -- Curated collection
- [Glitch Arts Resources](https://github.com/osromusic/Glitch-Arts-Resources) -- Another curated list
- [datamoshing.com](http://datamoshing.com/) -- Tutorials and community
