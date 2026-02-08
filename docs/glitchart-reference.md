# GlitchArt Library Reference

> **Package:** GlitchArt 1.0.0
> **Import:** `import glitchart`
> **Purpose:** Apply glitch effects to images and videos by corrupting JPEG data at the byte level
> **Author:** Dan Tes (delivrance)
> **License:** MIT
> **GitHub:** https://github.com/delivrance/glitchart
> **PyPI:** https://pypi.org/project/GlitchArt/
> **Dependencies:** Pillow (auto-installed), ffmpeg + ffprobe (required for video, must be in PATH)
> **Install:** `pip3 install glitchart`

---

## Table of Contents

1. [How It Works](#1-how-it-works)
2. [Image Functions](#2-image-functions)
3. [Video Function](#3-video-function)
4. [Async Variants](#4-async-variants)
5. [Parameters Reference](#5-parameters-reference)
6. [Usage Examples](#6-usage-examples)
7. [Integration with Other Tools](#7-integration-with-other-tools)
8. [Tips and Creative Techniques](#8-tips-and-creative-techniques)
9. [Limitations and Workarounds](#9-limitations-and-workarounds)

---

## 1. How It Works

GlitchArt creates glitch effects by **corrupting random bytes within JPEG scan data**. The corruption targets only the image data segment (between the SOS/Start of Scan and EOI/End of Image markers), avoiding the JPEG header to prevent total file corruption. This produces the characteristic "glitch art" visual distortions: color bleeding, shifted blocks, displaced rows, and data artifacts.

**Process for images:**
1. If the input is PNG or WebP, it is first converted to JPEG internally
2. Random bytes within the JPEG scan data are selected
3. Those bytes are replaced with different random values
4. The corrupted JPEG is saved
5. If the original was PNG/WebP, it is converted back to the original format

**Process for video (MP4):**
1. Frames are extracted from the video using ffmpeg
2. Each frame is individually glitched as a JPEG
3. Frames are re-assembled into a video at the original framerate using ffmpeg

---

## 2. Image Functions

### glitchart.jpeg()

Glitch a JPEG file by corrupting random bytes in the scan data.

```python
glitchart.jpeg(
    photo: str,
    seed: int = None,
    min_amount: int = 1,
    max_amount: int = 10,
    inplace: bool = False
) -> str
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `photo` | str | required | Path to the JPEG file to glitch |
| `seed` | int | None (random) | PRNG seed. Same seed + same file = identical result |
| `min_amount` | int | 1 | Minimum bytes to corrupt. Negative values become 0 |
| `max_amount` | int | 10 | Maximum bytes to corrupt. Negative values become 1 |
| `inplace` | bool | False | If True, overwrites original file |

**Returns:** Absolute path to the glitched image (str).

**Output naming:** If `inplace=False`, creates `filename_glitch.jpg` in the current working directory.

```python
import glitchart

# Basic usage
result = glitchart.jpeg("photo.jpg")
print(result)  # /absolute/path/to/photo_glitch.jpg

# Reproducible glitch
result = glitchart.jpeg("photo.jpg", seed=42)

# Heavy glitch
result = glitchart.jpeg("photo.jpg", min_amount=20, max_amount=50)

# Subtle glitch
result = glitchart.jpeg("photo.jpg", min_amount=1, max_amount=2)

# Overwrite original
result = glitchart.jpeg("photo.jpg", inplace=True)
```

### glitchart.png()

Glitch a PNG file. Internally converts to JPEG, applies glitch, converts back to PNG.

```python
glitchart.png(
    photo: str,
    seed: int = None,
    min_amount: int = 1,
    max_amount: int = 10,
    inplace: bool = False
) -> str
```

Same parameters as `jpeg()`. Output: `filename_glitch.png`

```python
result = glitchart.png("artwork.png")
result = glitchart.png("artwork.png", seed=42, max_amount=20)
```

### glitchart.webp()

Glitch a WebP file. Internally converts to JPEG, applies glitch, converts back to WebP.

```python
glitchart.webp(
    photo: str,
    seed: int = None,
    min_amount: int = 1,
    max_amount: int = 10,
    inplace: bool = False
) -> str
```

Same parameters as `jpeg()`. Output: `filename_glitch.webp`

```python
result = glitchart.webp("image.webp")
```

---

## 3. Video Function

### glitchart.mp4()

Glitch an MP4 video. Extracts frames with ffmpeg, glitches each frame individually, reassembles.

```python
glitchart.mp4(
    video: str,
    seed: int = None,
    min_amount: int = 0,
    max_amount: int = 3,
    inplace: bool = False
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `video` | str | required | Path to the MP4 file |
| `seed` | int | None | Base seed (each frame gets seed + frame_number) |
| `min_amount` | int | 0 | Minimum bytes to corrupt per frame |
| `max_amount` | int | 3 | Maximum bytes to corrupt per frame |
| `inplace` | bool | False | If True, overwrites original file |

**Note:** Default corruption amounts are LOWER for video (0-3) compared to images (1-10) because even small corruption per frame creates noticeable effects at 24-30fps.

```python
import glitchart

# Basic video glitch
glitchart.mp4("music_video.mp4")

# Heavy glitch
glitchart.mp4("input.mp4", min_amount=5, max_amount=15)

# Reproducible
glitchart.mp4("input.mp4", seed=42)

# Subtle (some frames won't be corrupted due to min_amount=0)
glitchart.mp4("input.mp4", min_amount=0, max_amount=1)
```

**Requirements for video:**
- `ffmpeg` must be in PATH
- `ffprobe` must be in PATH
- Sufficient disk space for extracted frames (temporary)

---

## 4. Async Variants

All functions have async versions for use with `asyncio`:

```python
import asyncio
import glitchart

async def main():
    result = await glitchart.jpeg_async("photo.jpg", seed=42)
    print(f"Glitched: {result}")

    result = await glitchart.png_async("artwork.png", max_amount=20)

    result = await glitchart.webp_async("image.webp")

    await glitchart.mp4_async("video.mp4", seed=100, max_amount=5)

asyncio.run(main())
```

**Available async functions:**
- `glitchart.jpeg_async()` - Same params as `jpeg()`
- `glitchart.png_async()` - Same params as `png()`
- `glitchart.webp_async()` - Same params as `webp()`
- `glitchart.mp4_async()` - Same params as `mp4()`

---

## 5. Parameters Reference

### Amount vs. Visual Impact

| min_amount | max_amount | Visual Effect |
|------------|------------|---------------|
| 0 | 1 | Very subtle, occasional minor artifact |
| 1 | 3 | Light glitch, small color shifts |
| 1 | 10 | **Default for images.** Moderate glitch |
| 5 | 20 | Heavy glitch, significant distortion |
| 10 | 50 | Extreme, may be barely recognizable |
| 50+ | 100+ | Potentially unreadable |

### Seed Behavior

- `seed=None` (default): Random result each time
- `seed=<int>`: Deterministic. Same seed + same file = same output
- For video: Each frame uses `seed + frame_index`, creating varied but reproducible results

### Edge Cases

- If `min_amount < 0`, it becomes 0
- If `max_amount < 0`, it becomes 1
- If `min_amount > max_amount`, then `max_amount = min_amount`
- The actual corruption count is randomly chosen within `[min_amount, max_amount]`

---

## 6. Usage Examples

### Single Image Glitch

```python
import glitchart

# The simplest usage
glitchart.jpeg("starrynight.jpg")
# Creates: starrynight_glitch.jpg in current directory
```

### Batch Processing

```python
import glitchart
import glob

for img in glob.glob("photos/*.jpg"):
    glitchart.jpeg(img, max_amount=15)
    print(f"Glitched: {img}")
```

### Multiple Glitch Intensities

```python
import glitchart

source = "portrait.jpg"
for intensity in [2, 5, 10, 20, 50]:
    result = glitchart.jpeg(source, seed=42, min_amount=1, max_amount=intensity)
    # Note: all outputs go to same filename since source is the same.
    # Use shutil.copy to save different versions
    import shutil
    shutil.copy(result, f"portrait_glitch_{intensity}.jpg")
```

### Iterative Glitching (Compound Effect)

```python
import glitchart
import shutil

source = "original.jpg"
current = source

for i in range(5):
    result = glitchart.jpeg(current, max_amount=3)
    current = result
    shutil.copy(result, f"iteration_{i+1}.jpg")

# Each iteration compounds the glitch effect
```

---

## 7. Integration with Other Tools

### With OpenCV

```python
import glitchart
import cv2

# Glitch an image, then load with OpenCV for further processing
result_path = glitchart.jpeg("input.jpg", max_amount=15)
glitched = cv2.imread(result_path)

# Apply additional OpenCV effects
edges = cv2.Canny(glitched, 50, 150)
combined = cv2.addWeighted(glitched, 0.7,
                            cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR), 0.3, 0)
cv2.imwrite("glitch_edges.jpg", combined)
```

### With PIL/Pillow

```python
import glitchart
from PIL import Image, ImageEnhance

# Glitch, then enhance
result_path = glitchart.jpeg("photo.jpg", seed=42)
img = Image.open(result_path)

# Increase contrast of glitched image
enhancer = ImageEnhance.Contrast(img)
enhanced = enhancer.enhance(2.0)
enhanced.save("glitch_enhanced.jpg")
```

### With MoviePy

```python
import glitchart
from moviepy import VideoFileClip, ImageSequenceClip
import os
import glob

# Method 1: Glitch entire video at once
glitchart.mp4("input.mp4", max_amount=5)

# Method 2: Extract frames with MoviePy, glitch selectively, reassemble
clip = VideoFileClip("input.mp4")
clip.write_images_sequence("frames/frame%04d.jpg", fps=clip.fps)

# Glitch every other frame for a strobing effect
frame_files = sorted(glob.glob("frames/frame*.jpg"))
for i, f in enumerate(frame_files):
    if i % 2 == 0:
        glitchart.jpeg(f, inplace=True, max_amount=10)

# Reassemble
result = ImageSequenceClip("frames/", fps=clip.fps)
result.write_videofile("glitched_strobe.mp4")
```

### With ffmpeg-python

```python
import ffmpeg
import glitchart
import os
import glob

# Extract frames
os.makedirs('temp_frames', exist_ok=True)
(
    ffmpeg
    .input('input.mp4')
    .output('temp_frames/frame_%04d.jpg', start_number=0)
    .run(quiet=True)
)

# Glitch each frame
for f in sorted(glob.glob('temp_frames/frame_*.jpg')):
    glitchart.jpeg(f, inplace=True, min_amount=1, max_amount=8)

# Reassemble
probe = ffmpeg.probe('input.mp4')
video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
fps = eval(video_info['r_frame_rate'])

(
    ffmpeg
    .input('temp_frames/frame_%04d.jpg', framerate=fps)
    .output('glitched_output.mp4', vcodec='libx264', pix_fmt='yuv420p', crf=18)
    .overwrite_output()
    .run(quiet=True)
)
```

---

## 8. Tips and Creative Techniques

### Controlling the Aesthetic

1. **Low amounts (1-3):** Subtle color shifts, small artifacts. Good for "lived-in" or "analog" feel.
2. **Medium amounts (5-15):** Classic glitch art. Visible distortion while image remains recognizable.
3. **High amounts (20-50):** Extreme distortion. Best for abstract art or transitional moments in video.
4. **Iterative glitching:** Run the same image through multiple passes for compound degradation.

### Seed as Creative Control

- Use the same seed across a series of images for a cohesive visual style
- For video, the seed creates a deterministic pattern of glitches that can be replicated
- Try sequential seeds (42, 43, 44...) across a series for consistent but varied results

### Video Tips

- **Lower amounts for video** (0-5) - each frame's glitch accumulates visually
- **High amounts on video** can produce "datamosh-like" effects
- **Selective frame glitching** (every Nth frame) creates a strobing/stuttering effect
- **Combine with speed changes** - slow-mo glitched footage can look particularly interesting

### Workflow Recommendations

1. **Always work on copies** - Use `inplace=False` (default) until you are satisfied
2. **Test with a single frame first** before processing an entire video
3. **Try different seeds** with the same settings to find the best aesthetic result
4. **Combine with other effects** - Glitch first, then apply color grading, edge detection, etc.

---

## 9. Limitations and Workarounds

### Supported Formats

| Format | Input | Output | Notes |
|--------|-------|--------|-------|
| JPEG | Direct | Direct | Native format for glitching |
| PNG | Via conversion | Via conversion | Converted to JPEG internally, then back |
| WebP | Via conversion | Via conversion | Converted to JPEG internally, then back |
| MP4 | Via frame extraction | Via reassembly | Requires ffmpeg + ffprobe |

### Not Supported

- **GIF:** Convert to MP4 first, glitch, convert back
- **MOV, AVI, WebM:** Convert to MP4 first using ffmpeg
- **RAW image formats:** Convert to JPEG/PNG first
- **Audio:** No audio processing (video audio track is preserved through ffmpeg)

### Workaround for Unsupported Formats

```python
import subprocess

# Convert MOV to MP4, glitch, convert back
subprocess.run(['ffmpeg', '-i', 'input.mov', 'temp.mp4', '-y'], check=True)
glitchart.mp4('temp.mp4', max_amount=5)
subprocess.run(['ffmpeg', '-i', 'temp_glitch.mp4', 'output.mov', '-y'], check=True)
```

### Known Behaviors

- Output files are created in the **current working directory**, not alongside the source file
- PNG/WebP quality may differ slightly due to JPEG intermediate conversion (lossy step)
- Very small images may not have enough JPEG scan data to corrupt effectively
- Processing time for video depends on frame count and resolution (CPU-bound)

---

## API Quick Reference

```python
import glitchart

# Images
glitchart.jpeg(photo, seed=None, min_amount=1, max_amount=10, inplace=False) -> str
glitchart.png(photo, seed=None, min_amount=1, max_amount=10, inplace=False) -> str
glitchart.webp(photo, seed=None, min_amount=1, max_amount=10, inplace=False) -> str

# Video
glitchart.mp4(video, seed=None, min_amount=0, max_amount=3, inplace=False)

# Async variants
await glitchart.jpeg_async(photo, seed=None, min_amount=1, max_amount=10, inplace=False)
await glitchart.png_async(photo, seed=None, min_amount=1, max_amount=10, inplace=False)
await glitchart.webp_async(photo, seed=None, min_amount=1, max_amount=10, inplace=False)
await glitchart.mp4_async(video, seed=None, min_amount=0, max_amount=3, inplace=False)
```
