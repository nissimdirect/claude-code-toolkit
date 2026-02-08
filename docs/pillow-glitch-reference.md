# Pillow / PIL Glitch Art Reference

> Comprehensive reference for image manipulation and glitch art techniques using Python's Pillow library.
> Last updated: 2026-02-07

---

## Table of Contents

1. [Image Manipulation Fundamentals](#image-manipulation-fundamentals)
2. [Channel Operations](#channel-operations)
3. [Pixel Sorting Implementation](#pixel-sorting-implementation)
4. [Data Bending Techniques](#data-bending-techniques)
5. [Blend Modes Implementation](#blend-modes-implementation)
6. [Noise Generation](#noise-generation)
7. [Color Space Manipulation](#color-space-manipulation)
8. [Batch Processing for Video Frames](#batch-processing-for-video-frames)
9. [Performance Optimization with NumPy](#performance-optimization-with-numpy)
10. [Complete Glitch Art Recipes](#complete-glitch-art-recipes)

---

## Image Manipulation Fundamentals

### Opening and Creating Images

```python
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw, ImageChops

# Open an image
img = Image.open("input.png")

# Create a new image
img = Image.new("RGB", (800, 600), color=(0, 0, 0))

# Get image properties
width, height = img.size
mode = img.mode          # "RGB", "RGBA", "L", etc.
bands = img.getbands()   # ("R", "G", "B") for RGB
```

### Image Modes

| Mode | Description | Channels | Use Case |
|------|-------------|----------|----------|
| `1` | Binary (black/white) | 1 | Masks, thresholding |
| `L` | Grayscale | 1 | Luminance operations |
| `P` | Palette/indexed color | 1 | GIFs, limited color |
| `RGB` | True color | 3 | Standard color images |
| `RGBA` | True color + alpha | 4 | Transparency support |
| `CMYK` | Print colors | 4 | Print production |
| `HSV` | Hue/Saturation/Value | 3 | Color manipulation |
| `LAB` | CIE L*a*b* | 3 | Perceptual color work |

### Pixel Access (getpixel / putpixel)

```python
# Read a single pixel
pixel = img.getpixel((x, y))  # Returns tuple: (R, G, B) or (R, G, B, A)

# Write a single pixel
img.putpixel((x, y), (255, 0, 0))  # Set to red

# WARNING: getpixel/putpixel are SLOW for bulk operations
# Use img.load() for faster access:
pixels = img.load()
for y in range(height):
    for x in range(width):
        r, g, b = pixels[x, y]
        pixels[x, y] = (b, r, g)  # Channel swap
```

### Pixel Data Access (getdata)

```python
# Get all pixel data as a flat sequence
data = list(img.getdata())  # List of (R, G, B) tuples

# Modify and put back
new_data = [(255 - r, 255 - g, 255 - b) for r, g, b in data]
img.putdata(new_data)
```

### Point Transformations

```python
# Apply a function to every pixel value in every channel
inverted = img.point(lambda x: 255 - x)

# Threshold (posterize-like effect)
threshold = img.point(lambda x: 255 if x > 128 else 0)

# Gamma correction
gamma = 2.2
corrected = img.point(lambda x: int(255 * (x / 255) ** (1 / gamma)))

# Apply lookup table (256-entry list, one per possible byte value)
lut = [min(255, int(i * 1.5)) for i in range(256)]
brightened = img.point(lut * 3)  # Multiply by 3 for RGB (one lut per channel)
```

### Filters

```python
from PIL import ImageFilter

# Predefined filters
blurred = img.filter(ImageFilter.BLUR)
sharpened = img.filter(ImageFilter.SHARPEN)
smoothed = img.filter(ImageFilter.SMOOTH)
edges = img.filter(ImageFilter.FIND_EDGES)
enhanced_edges = img.filter(ImageFilter.EDGE_ENHANCE)
embossed = img.filter(ImageFilter.EMBOSS)

# Configurable filters
box_blur = img.filter(ImageFilter.BoxBlur(radius=5))
gauss_blur = img.filter(ImageFilter.GaussianBlur(radius=3))
eroded = img.filter(ImageFilter.MinFilter(3))     # Erosion (removes white pixels)
dilated = img.filter(ImageFilter.MaxFilter(3))     # Dilation (adds white pixels)
median = img.filter(ImageFilter.MedianFilter(3))   # Noise reduction

# Custom kernel
kernel = ImageFilter.Kernel(
    size=(3, 3),
    kernel=[0, -1, 0, -1, 5, -1, 0, -1, 0],  # Sharpen
    scale=1,
    offset=0
)
custom = img.filter(kernel)
```

---

## Channel Operations

### Split and Merge

```python
# Split into individual channels
r, g, b = img.split()  # Each is a mode "L" image

# For RGBA:
r, g, b, a = img.split()

# Merge channels back
merged = Image.merge("RGB", (r, g, b))

# Channel swap (glitch effect)
swapped = Image.merge("RGB", (b, r, g))  # Shift R->G, G->B, B->R

# Isolate a single channel (zero out others)
zeroed = r.point(lambda _: 0)
red_only = Image.merge("RGB", (r, zeroed, zeroed))
green_only = Image.merge("RGB", (zeroed, g, zeroed))
blue_only = Image.merge("RGB", (zeroed, zeroed, b))
```

### Channel Offset (Chromatic Aberration / RGB Shift)

```python
from PIL import ImageChops

def chromatic_aberration(img, offset_x=10, offset_y=0):
    """Offset color channels to create chromatic aberration glitch effect."""
    r, g, b = img.split()

    # Offset red channel left, blue channel right
    r = ImageChops.offset(r, -offset_x, -offset_y)
    b = ImageChops.offset(b, offset_x, offset_y)

    return Image.merge("RGB", (r, g, b))

# Varying offsets create different intensities
mild = chromatic_aberration(img, 5, 0)
extreme = chromatic_aberration(img, 30, 10)
```

### Channel Math with ImageChops

```python
from PIL import ImageChops

# Add two images (clipped at 255)
added = ImageChops.add(img1, img2, scale=1, offset=0)

# Subtract
subtracted = ImageChops.subtract(img1, img2)

# Multiply (darken blend)
multiplied = ImageChops.multiply(img1, img2)

# Screen (lighten blend)
screened = ImageChops.screen(img1, img2)

# Difference (absolute difference per pixel)
diff = ImageChops.difference(img1, img2)

# Invert
inverted = ImageChops.invert(img)

# Offset (wrap pixels around edges)
shifted = ImageChops.offset(img, xoffset=50, yoffset=20)
```

---

## Pixel Sorting Implementation

### What is Pixel Sorting?

Pixel sorting selectively orders pixels in rows or columns of an image based on criteria like luminosity, hue, or saturation. The image is divided into "intervals" and pixels within each interval are sorted. Popularized by artist Kim Asendorf.

### Basic Pixel Sort (by Lightness)

```python
from PIL import Image
import colorsys

def get_lightness(pixel):
    """Convert RGB pixel to lightness value (0-255)."""
    r, g, b = pixel[0] / 255, pixel[1] / 255, pixel[2] / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return int(l * 255)

def pixel_sort_row(row, lower_threshold=50, upper_threshold=200):
    """Sort pixels in a row that fall between threshold values."""
    intervals = []
    current_interval = []

    for pixel in row:
        lightness = get_lightness(pixel)
        if lower_threshold < lightness < upper_threshold:
            current_interval.append(pixel)
        else:
            if current_interval:
                current_interval.sort(key=lambda p: get_lightness(p))
                intervals.extend(current_interval)
                current_interval = []
            intervals.append(pixel)

    if current_interval:
        current_interval.sort(key=lambda p: get_lightness(p))
        intervals.extend(current_interval)

    return intervals

def pixel_sort(img, lower=50, upper=200):
    """Apply pixel sorting to an entire image."""
    width, height = img.size
    pixels = img.load()
    sorted_img = img.copy()
    sorted_pixels = sorted_img.load()

    for y in range(height):
        row = [pixels[x, y] for x in range(width)]
        sorted_row = pixel_sort_row(row, lower, upper)
        for x, pixel in enumerate(sorted_row):
            sorted_pixels[x, y] = pixel

    return sorted_img
```

### Sorting Modes

```python
import colorsys

def sort_by_hue(pixel):
    r, g, b = pixel[0] / 255, pixel[1] / 255, pixel[2] / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h

def sort_by_saturation(pixel):
    r, g, b = pixel[0] / 255, pixel[1] / 255, pixel[2] / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return s

def sort_by_intensity(pixel):
    return pixel[0] + pixel[1] + pixel[2]

def sort_by_minimum(pixel):
    return min(pixel[0], pixel[1], pixel[2])

# Usage:
# current_interval.sort(key=sort_by_hue)
```

### Interval Functions

```python
import random
from PIL import ImageFilter

def threshold_interval(row, lower=64, upper=224):
    """Create intervals between brightness thresholds."""
    intervals = []
    current = []
    for pixel in row:
        lightness = get_lightness(pixel)
        if lower < lightness < upper:
            current.append(pixel)
        else:
            if current:
                intervals.append(current)
                current = []
            intervals.append([pixel])
    if current:
        intervals.append(current)
    return intervals

def random_interval(row, avg_length=50):
    """Create random-width intervals."""
    intervals = []
    i = 0
    while i < len(row):
        length = max(1, int(random.gauss(avg_length, avg_length / 3)))
        intervals.append(row[i:i + length])
        i += length
    return intervals

def edge_interval(img, y, edge_threshold=100):
    """Use edge detection to define sorting boundaries."""
    edges = img.filter(ImageFilter.FIND_EDGES).convert("L")
    edge_pixels = edges.load()
    width = img.size[0]

    intervals = []
    current = []
    pixels = img.load()

    for x in range(width):
        if edge_pixels[x, y] > edge_threshold:
            if current:
                intervals.append(current)
                current = []
            intervals.append([(pixels[x, y])])
        else:
            current.append(pixels[x, y])

    if current:
        intervals.append(current)
    return intervals
```

### Using the pixelsort Package

```bash
pip install pixelsort
```

```python
# Command line usage
# python3 -m pixelsort input.png -o output.png -i threshold -t 0.25 -u 0.8 -s lightness

# Python API
from pixelsort import pixelsort
from PIL import Image

img = Image.open("input.png")
sorted_img = pixelsort(
    img,
    interval_function="threshold",  # threshold, edges, random, waves, none
    sorting_function="lightness",   # lightness, hue, saturation, intensity, minimum
    lower_threshold=0.25,           # 0.0 - 1.0
    upper_threshold=0.8,
    angle=0,                        # degrees (0 = horizontal)
    randomness=0,                   # 0-100, percentage chance to skip sorting
    char_length=50,                 # for waves/random interval length
)
sorted_img.save("output.png")
```

### Vertical Pixel Sorting

```python
def pixel_sort_vertical(img, lower=50, upper=200):
    """Sort pixels vertically (column-by-column)."""
    # Rotate 90 degrees, sort horizontally, rotate back
    rotated = img.rotate(90, expand=True)
    sorted_rotated = pixel_sort(rotated, lower, upper)
    return sorted_rotated.rotate(-90, expand=True)
```

---

## Data Bending Techniques

### What is Data Bending?

Data bending manipulates the raw bytes of an image file to produce glitch artifacts. The key is modifying pixel data without destroying the file header.

### BMP Data Bending (Safest Format)

BMP files have a simple structure with a 1:1 mapping between bytes and pixels:

```
File Structure:
- Header (54 bytes typically) -- DO NOT MODIFY
  - Magic bytes: 42 4D (identifies BMP format)
  - File size: 4 bytes
  - Reserved: 4 bytes
  - Pixel data offset: 4 bytes
  - DIB header: 40 bytes (dimensions, color depth, compression)
- Pixel data (rest of file) -- SAFE TO MODIFY
  - Color format: BGR (not RGB), 3 bytes per pixel
  - Row order: Bottom-to-top
  - Row padding: Each row must be a multiple of 4 bytes
```

```python
def data_bend_bmp(input_path, output_path, offset=54, intensity=10):
    """Data bend a BMP file by modifying raw bytes after the header."""
    with open(input_path, "rb") as f:
        data = bytearray(f.read())

    header = data[:offset]  # Preserve header
    body = data[offset:]    # Modify pixel data

    import random
    for i in range(0, len(body), intensity):
        idx = random.randint(0, len(body) - 1)
        body[idx] = random.randint(0, 255)

    with open(output_path, "wb") as f:
        f.write(header + body)
```

### JPEG Data Bending

JPEG is more fragile due to compression, but produces dramatic glitch effects:

```python
def data_bend_jpeg(input_path, output_path, num_replacements=5):
    """Data bend a JPEG by replacing bytes in the compressed data.

    IMPORTANT: Avoid the first ~200 bytes (header/quantization tables)
    and the last 2 bytes (FFD9 end marker).
    """
    with open(input_path, "rb") as f:
        data = bytearray(f.read())

    safe_start = 200  # Skip past header
    safe_end = len(data) - 2  # Preserve end marker

    import random
    for _ in range(num_replacements):
        pos = random.randint(safe_start, safe_end)
        # Find and replace specific byte sequences
        find_byte = random.randint(0, 255)
        replace_byte = random.randint(0, 255)
        if data[pos] == find_byte:
            data[pos] = replace_byte

    with open(output_path, "wb") as f:
        f.write(data)
```

### Raw Byte Manipulation with Pillow

```python
from PIL import Image
import io

def glitch_via_bytes(img, num_glitches=20, format="JPEG", quality=85):
    """Convert image to bytes, corrupt them, and read back."""
    # Save to bytes buffer
    buf = io.BytesIO()
    img.save(buf, format=format, quality=quality)
    raw = bytearray(buf.getvalue())

    # Skip header region
    header_size = 200 if format == "JPEG" else 54
    data_region = raw[header_size:-2] if format == "JPEG" else raw[header_size:]

    import random
    for _ in range(num_glitches):
        pos = random.randint(0, len(data_region) - 1)
        data_region[pos] = random.randint(0, 255)

    # Reassemble
    if format == "JPEG":
        raw[header_size:-2] = data_region
    else:
        raw[header_size:] = data_region

    # Try to read back
    try:
        return Image.open(io.BytesIO(bytes(raw)))
    except Exception:
        return img  # Return original if corruption was too severe
```

### Word Replacement in Raw Data

```python
def word_replace_glitch(input_path, output_path, find_bytes, replace_bytes):
    """Find and replace byte sequences in image data."""
    with open(input_path, "rb") as f:
        data = f.read()

    data = data.replace(find_bytes, replace_bytes)

    with open(output_path, "wb") as f:
        f.write(data)

# Example: Replace all occurrences of 0xFF00 with 0x00FF
word_replace_glitch("input.jpg", "output.jpg", b"\xff\x00", b"\x00\xff")
```

---

## Blend Modes Implementation

### Basic Blend Modes with Pillow

```python
from PIL import Image, ImageChops
import numpy as np

def blend_multiply(base, blend):
    """Multiply blend mode: darkens image."""
    return ImageChops.multiply(base, blend)

def blend_screen(base, blend):
    """Screen blend mode: lightens image."""
    return ImageChops.screen(base, blend)

def blend_difference(base, blend):
    """Difference blend mode: absolute difference."""
    return ImageChops.difference(base, blend)

def blend_add(base, blend):
    """Additive blend mode."""
    return ImageChops.add(base, blend)

def blend_subtract(base, blend):
    """Subtractive blend mode."""
    return ImageChops.subtract(base, blend)
```

### Advanced Blend Modes with NumPy

```python
import numpy as np
from PIL import Image

def to_float(img):
    return np.array(img).astype(np.float64) / 255.0

def to_image(arr):
    return Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8))

def blend_overlay(base_img, blend_img):
    """Overlay: combines Multiply and Screen."""
    base = to_float(base_img)
    blend = to_float(blend_img)
    mask = base < 0.5
    result = np.where(mask, 2 * base * blend, 1 - 2 * (1 - base) * (1 - blend))
    return to_image(result)

def blend_soft_light(base_img, blend_img):
    """Soft Light: subtle contrast adjustment."""
    base = to_float(base_img)
    blend = to_float(blend_img)
    result = np.where(
        blend < 0.5,
        base - (1 - 2 * blend) * base * (1 - base),
        base + (2 * blend - 1) * (np.sqrt(base) - base)
    )
    return to_image(result)

def blend_hard_light(base_img, blend_img):
    """Hard Light: strong contrast adjustment."""
    base = to_float(base_img)
    blend = to_float(blend_img)
    mask = blend < 0.5
    result = np.where(mask, 2 * base * blend, 1 - 2 * (1 - base) * (1 - blend))
    return to_image(result)

def blend_color_dodge(base_img, blend_img):
    """Color Dodge: extreme lightening."""
    base = to_float(base_img)
    blend = to_float(blend_img)
    result = np.where(blend >= 1.0, 1.0, np.minimum(1.0, base / (1 - blend + 1e-7)))
    return to_image(result)

def blend_color_burn(base_img, blend_img):
    """Color Burn: extreme darkening."""
    base = to_float(base_img)
    blend = to_float(blend_img)
    result = np.where(blend <= 0.0, 0.0, np.maximum(0.0, 1 - (1 - base) / (blend + 1e-7)))
    return to_image(result)
```

### Opacity/Alpha Blending

```python
def blend_with_opacity(base_img, blend_img, opacity=0.5):
    """Blend two images with adjustable opacity."""
    return Image.blend(base_img, blend_img, alpha=opacity)

def composite_with_mask(base_img, overlay_img, mask_img):
    """Composite using a grayscale mask."""
    return Image.composite(overlay_img, base_img, mask_img)
```

---

## Noise Generation

### Random Noise

```python
import numpy as np
from PIL import Image

def generate_noise(width, height, scale=1.0, seed=None):
    """Generate random noise image."""
    if seed is not None:
        np.random.seed(seed)
    noise = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    return Image.fromarray(noise)

def generate_smooth_noise(width, height, octaves=4, persistence=0.5):
    """Generate smooth noise using multiple octaves."""
    result = np.zeros((height, width))
    amplitude = 1.0
    frequency = 1.0

    for _ in range(octaves):
        small_w = max(2, int(width * frequency / width))
        small_h = max(2, int(height * frequency / height))
        noise = np.random.rand(small_h, small_w)

        noise_img = Image.fromarray((noise * 255).astype(np.uint8), mode="L")
        noise_img = noise_img.resize((width, height), Image.BILINEAR)
        noise_scaled = np.array(noise_img) / 255.0

        result += noise_scaled * amplitude
        amplitude *= persistence
        frequency *= 2

    result = ((result - result.min()) / (result.max() - result.min()) * 255).astype(np.uint8)
    return Image.fromarray(result, mode="L")
```

### Scanline Noise

```python
def add_scanlines(img, line_spacing=2, line_opacity=0.3):
    """Add horizontal scanlines for a CRT/VHS effect."""
    arr = np.array(img).astype(np.float64)
    for y in range(0, arr.shape[0], line_spacing):
        arr[y] = arr[y] * (1.0 - line_opacity)
    return Image.fromarray(arr.astype(np.uint8))
```

### Salt and Pepper Noise

```python
def salt_and_pepper(img, amount=0.02):
    """Add salt and pepper noise for a damaged sensor look."""
    arr = np.array(img)
    total_pixels = arr.shape[0] * arr.shape[1]

    num_salt = int(total_pixels * amount / 2)
    coords = [np.random.randint(0, i, num_salt) for i in arr.shape[:2]]
    arr[coords[0], coords[1]] = 255

    num_pepper = int(total_pixels * amount / 2)
    coords = [np.random.randint(0, i, num_pepper) for i in arr.shape[:2]]
    arr[coords[0], coords[1]] = 0

    return Image.fromarray(arr)
```

### Block Corruption Noise

```python
def block_corruption(img, num_blocks=10, block_size_range=(20, 80)):
    """Add randomly placed corrupted blocks."""
    arr = np.array(img)
    h, w = arr.shape[:2]

    for _ in range(num_blocks):
        bw = np.random.randint(*block_size_range)
        bh = np.random.randint(*block_size_range)
        x = np.random.randint(0, max(1, w - bw))
        y = np.random.randint(0, max(1, h - bh))

        effect = np.random.choice(["shift", "noise", "repeat", "invert"])

        if effect == "shift":
            shift = np.random.randint(-50, 50)
            src_x = max(0, min(w - bw, x + shift))
            arr[y:y+bh, x:x+bw] = arr[y:y+bh, src_x:src_x+bw]
        elif effect == "noise":
            arr[y:y+bh, x:x+bw] = np.random.randint(0, 256, (bh, bw, 3), dtype=np.uint8)
        elif effect == "repeat":
            arr[y:y+bh, x:x+bw] = arr[y:y+1, x:x+bw]
        elif effect == "invert":
            arr[y:y+bh, x:x+bw] = 255 - arr[y:y+bh, x:x+bw]

    return Image.fromarray(arr)
```

---

## Color Space Manipulation

### RGB to HSV and Back

```python
from PIL import Image
import colorsys

def shift_hue(img, degrees=30):
    """Shift all hues by a given number of degrees."""
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y][:3]
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            h = (h + degrees / 360) % 1.0
            r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
            pixels[x, y] = (int(r2 * 255), int(g2 * 255), int(b2 * 255))

    return img

# FASTER version using Pillow's HSV mode:
def shift_hue_fast(img, degrees=30):
    """Fast hue shift using HSV conversion."""
    hsv = img.convert("HSV")
    h, s, v = hsv.split()
    h = h.point(lambda x: (x + int(degrees * 255 / 360)) % 256)
    return Image.merge("HSV", (h, s, v)).convert("RGB")
```

### Posterization

```python
def posterize(img, levels=4):
    """Reduce color levels for a posterized look."""
    factor = 256 / levels
    return img.point(lambda x: int(x / factor) * int(factor))
```

### Color Channel Isolation and Manipulation

```python
def isolate_color_range(img, hue_min=0, hue_max=30, desaturate_rest=True):
    """Isolate a specific color range, desaturate everything else."""
    arr = np.array(img)
    hsv = np.array(img.convert("HSV"))

    hue = hsv[:, :, 0]
    hue_scaled = hue * 360 / 255

    mask = (hue_scaled >= hue_min) & (hue_scaled <= hue_max)

    if desaturate_rest:
        gray = np.array(img.convert("L"))
        gray_rgb = np.stack([gray, gray, gray], axis=2)
        result = np.where(mask[:, :, np.newaxis], arr, gray_rgb)
        return Image.fromarray(result.astype(np.uint8))

    return Image.fromarray(arr * mask[:, :, np.newaxis].astype(np.uint8))
```

### LAB Color Space

```python
def enhance_via_lab(img, l_factor=1.2, a_factor=1.0, b_factor=1.5):
    """Manipulate LAB channels for perceptually-aware color changes."""
    lab = img.convert("LAB")
    l, a, b = lab.split()

    l = l.point(lambda x: min(255, int(x * l_factor)))
    a = a.point(lambda x: min(255, max(0, int(128 + (x - 128) * a_factor))))
    b = b.point(lambda x: min(255, max(0, int(128 + (x - 128) * b_factor))))

    return Image.merge("LAB", (l, a, b)).convert("RGB")
```

---

## Batch Processing for Video Frames

### Extract Frames with FFmpeg

```bash
# Extract all frames as PNG
ffmpeg -i input.mp4 frames/frame_%04d.png

# Extract at specific framerate
ffmpeg -i input.mp4 -vf fps=30 frames/frame_%04d.png

# Extract specific time range
ffmpeg -i input.mp4 -ss 00:00:05 -t 00:00:10 -vf fps=30 frames/frame_%04d.png
```

### Process Frames in Python

```python
import os
from PIL import Image
from pathlib import Path

def process_frames(input_dir, output_dir, effect_fn, **kwargs):
    """Apply an effect function to all frames in a directory."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    frames = sorted([
        f for f in os.listdir(input_dir)
        if f.endswith((".png", ".jpg", ".bmp"))
    ])

    total = len(frames)
    for i, frame_name in enumerate(frames):
        img = Image.open(os.path.join(input_dir, frame_name))
        processed = effect_fn(img, **kwargs)
        processed.save(os.path.join(output_dir, frame_name))

        if (i + 1) % 100 == 0:
            print(f"Processed {i + 1}/{total} frames")

    print(f"Done. {total} frames processed.")
```

### Reassemble Video with FFmpeg

```bash
# Basic reassembly
ffmpeg -framerate 30 -i output/frame_%04d.png -c:v libx264 -pix_fmt yuv420p result.mp4

# With original audio
ffmpeg -framerate 30 -i output/frame_%04d.png -i original.mp4 \
    -c:v libx264 -c:a copy -map 0:v -map 1:a -pix_fmt yuv420p result.mp4

# High quality (CRF 18 = near lossless)
ffmpeg -framerate 30 -i output/frame_%04d.png -c:v libx264 -crf 18 -pix_fmt yuv420p result.mp4
```

### Progressive Effects (Intensity Changes Over Time)

```python
def process_frames_progressive(input_dir, output_dir, effect_fn, start_kwargs, end_kwargs):
    """Apply effect with parameters that change over the duration."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    frames = sorted([f for f in os.listdir(input_dir) if f.endswith(".png")])
    total = len(frames)

    for i, frame_name in enumerate(frames):
        t = i / max(1, total - 1)  # 0.0 to 1.0 over duration

        kwargs = {}
        for key in start_kwargs:
            start_val = start_kwargs[key]
            end_val = end_kwargs.get(key, start_val)
            kwargs[key] = start_val + (end_val - start_val) * t

        img = Image.open(os.path.join(input_dir, frame_name))
        processed = effect_fn(img, **kwargs)
        processed.save(os.path.join(output_dir, frame_name))
```

---

## Performance Optimization with NumPy

### Why NumPy?

Pillow's pixel-by-pixel operations (getpixel, putpixel, img.load()) are slow because they operate in Python. NumPy operates on entire arrays in C, offering 10-100x speedups.

### Converting Between Pillow and NumPy

```python
import numpy as np
from PIL import Image

# Pillow -> NumPy
arr = np.array(img)           # Shape: (height, width, 3) for RGB
arr = np.asarray(img)         # Read-only version (slightly faster)

# NumPy -> Pillow
img = Image.fromarray(arr)
img = Image.fromarray(arr.astype(np.uint8))  # Ensure correct dtype
```

### Fast Glitch Operations with NumPy

```python
def fast_channel_shift(img, r_shift=0, g_shift=0, b_shift=0):
    """Fast RGB channel offset using NumPy roll."""
    arr = np.array(img)
    result = np.empty_like(arr)
    result[:, :, 0] = np.roll(arr[:, :, 0], r_shift, axis=1)
    result[:, :, 1] = np.roll(arr[:, :, 1], g_shift, axis=1)
    result[:, :, 2] = np.roll(arr[:, :, 2], b_shift, axis=1)
    return Image.fromarray(result)

def fast_row_shift(img, max_shift=20):
    """Randomly shift each row horizontally (corrupted data look)."""
    arr = np.array(img)
    for y in range(arr.shape[0]):
        shift = np.random.randint(-max_shift, max_shift)
        arr[y] = np.roll(arr[y], shift, axis=0)
    return Image.fromarray(arr)

def fast_invert_bands(img, band_height=10):
    """Invert alternating horizontal bands."""
    arr = np.array(img).astype(np.float64)
    for y in range(0, arr.shape[0], band_height * 2):
        arr[y:y+band_height] = 255 - arr[y:y+band_height]
    return Image.fromarray(arr.astype(np.uint8))

def fast_pixel_sort_numpy(img, threshold_low=50, threshold_high=200):
    """NumPy-accelerated pixel sorting."""
    arr = np.array(img)
    lightness = np.mean(arr, axis=2)

    for y in range(arr.shape[0]):
        row = arr[y]
        l = lightness[y]
        mask = (l > threshold_low) & (l < threshold_high)

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
                sorted_indices = np.argsort(sort_key)
                arr[y, s:e] = segment[sorted_indices]

    return Image.fromarray(arr)
```

### Memory-Efficient Batch Processing

```python
def process_frames_efficient(input_dir, output_dir, effect_fn):
    """Process frames with memory efficiency."""
    frames = sorted(Path(input_dir).glob("*.png"))

    for frame_path in frames:
        img = Image.open(frame_path)
        result = effect_fn(img)
        result.save(Path(output_dir) / frame_path.name)

        img.close()
        result.close()
```

---

## Complete Glitch Art Recipes

### VHS Effect

```python
def vhs_effect(img, scanline_opacity=0.15, chromatic_offset=8, noise_amount=0.01):
    """Complete VHS degradation effect."""
    result = chromatic_aberration(img, offset_x=chromatic_offset, offset_y=1)
    result = add_scanlines(result, line_spacing=2, line_opacity=scanline_opacity)
    result = salt_and_pepper(result, amount=noise_amount)
    result = result.filter(ImageFilter.GaussianBlur(radius=0.5))
    enhancer = ImageEnhance.Color(result)
    result = enhancer.enhance(0.8)
    return result
```

### Digital Corruption

```python
def digital_corruption(img, intensity=5):
    """Simulate digital file corruption."""
    result = block_corruption(img, num_blocks=intensity * 3)
    result = fast_row_shift(result, max_shift=intensity * 5)
    result = fast_channel_shift(result, r_shift=intensity * 2, b_shift=-intensity * 2)
    return result
```

### Sorted Glitch Portrait

```python
def sorted_glitch_portrait(img, sort_strength=0.5):
    """Pixel sorting effect optimized for portraits."""
    lower = int(50 * (1 - sort_strength))
    upper = int(200 + 55 * sort_strength)
    result = pixel_sort(img, lower=lower, upper=upper)
    result = chromatic_aberration(result, offset_x=3)
    enhancer = ImageEnhance.Contrast(result)
    result = enhancer.enhance(1.2)
    return result
```

---

## Resources and Links

### Official Documentation
- [Pillow Documentation](https://pillow.readthedocs.io/en/stable/)
- [Pillow Tutorial](https://pillow.readthedocs.io/en/stable/handbook/tutorial.html)
- [Image Processing with Pillow (Real Python)](https://realpython.com/image-processing-with-the-python-pillow-library/)

### Pixel Sorting Tools
- [pixelsort (Python package)](https://github.com/satyarth/pixelsort)
- [Pixelort (GUI application)](https://github.com/Akascape/Pixelort)
- [Pixel Sorting Explained (satyarth.me)](https://satyarth.me/articles/pixel-sorting/)
- [Pixel Sorting in Python (Level Up Coding)](https://levelup.gitconnected.com/pixel-sorting-in-python-62337c078118)

### Glitch Art Libraries
- [pyglitch (data bending library)](https://github.com/giofusco/pyglitch)
- [GlitchTools pixelsort](https://github.com/GlitchTools/pixelsort)
- [Glitch Art GitHub Topics](https://github.com/topics/glitch-art?l=python)

### Data Bending
- [Databending 101: BMP](https://nickbriz.com/databending101/bmp.html)
- [Glitch Art and Image Processing with Python](https://chezsoi.org/lucas/blog/glitch-art-and-image-processing-with-python.html)

### Image Processing with NumPy
- [NumPy Image Processing (Scientific Python)](https://lectures.scientific-python.org/advanced/image_processing/index.html)
- [NumPy and Images (PythonInformer)](https://www.pythoninformer.com/python-libraries/numpy/numpy-and-images/)
