# Media I/O Reference: yt-dlp + imageio + soundfile

> Tools for downloading, reading, and writing audio/video/image media.
> yt-dlp: Command-line audio/video downloader
> imageio 2.37.2: Image and video I/O library
> soundfile 0.13.1: Audio file I/O via libsndfile

---

## Table of Contents

### yt-dlp
1. [Basic Downloads](#basic-downloads)
2. [Format Selection](#format-selection)
3. [Audio Extraction](#audio-extraction)
4. [Quality and Resolution](#quality-and-resolution)
5. [Output Templates](#output-templates)
6. [Playlist Handling](#playlist-handling)
7. [Advanced Options](#advanced-options)
8. [Use Case: Downloading Reference Media](#use-case-downloading-reference-media)

### imageio
9. [Reading Images](#reading-images)
10. [Writing Images](#writing-images)
11. [Reading Videos](#reading-videos)
12. [Writing Videos](#writing-videos)
13. [Video Frame Iteration](#video-frame-iteration)
14. [Format Support](#imageio-format-support)
15. [Use Case: Batch Video Frame Processing for Glitch Art](#use-case-batch-video-frame-processing-for-glitch-art)

### soundfile
16. [Reading Audio](#reading-audio)
17. [Writing Audio](#writing-audio)
18. [File Information](#file-information)
19. [Block-Wise Reading](#block-wise-reading)
20. [SoundFile Class](#soundfile-class)
21. [Supported Formats and Subtypes](#supported-formats-and-subtypes)
22. [Use Case: Audio I/O for Plugin Testing and Analysis](#use-case-audio-io-for-plugin-testing-and-analysis)

---

# yt-dlp

> A feature-rich command-line audio/video downloader.
> Install: `pip install yt-dlp` or `brew install yt-dlp`
> Requires: ffmpeg for merging/conversion (`brew install ffmpeg`)
> Docs: https://github.com/yt-dlp/yt-dlp

## Basic Downloads

```bash
# Download best quality video+audio (default behavior)
yt-dlp "https://www.youtube.com/watch?v=VIDEO_ID"

# Download with verbose output
yt-dlp -v "URL"

# Download and show progress
yt-dlp --progress "URL"

# Limit download speed
yt-dlp --rate-limit 5M "URL"  # 5 MB/s max

# Resume interrupted download
yt-dlp --continue "URL"

# Skip already downloaded files
yt-dlp --download-archive downloaded.txt "URL"
# Records downloaded video IDs in downloaded.txt, skips on re-run
```

## Format Selection

```bash
# List all available formats
yt-dlp -F "URL"
# Shows table: ID, EXT, RESOLUTION, FPS, CODEC, FILESIZE, etc.

# Download best video + best audio (default)
yt-dlp -f "bv*+ba/b" "URL"
# bv* = best video (any), ba = best audio, b = best single file

# Best MP4 video + best M4A audio
yt-dlp -f "bv[ext=mp4]+ba[ext=m4a]" "URL"

# Best video up to 720p + best audio
yt-dlp -f "bv*[height<=720]+ba" "URL"

# Best video up to 1080p, prefer MP4
yt-dlp -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba" "URL"

# Specific format by ID (from -F output)
yt-dlp -f 137+140 "URL"  # Format 137 video + format 140 audio

# Best quality single file (no merge needed)
yt-dlp -f "b" "URL"

# Worst quality (for testing/preview)
yt-dlp -f "wv+wa/w" "URL"
```

### Format Selection Syntax

| Selector | Meaning |
|----------|---------|
| `b` | Best single file |
| `bv` | Best video-only |
| `ba` | Best audio-only |
| `bv*` | Best video (may include audio) |
| `wv` | Worst video |
| `wa` | Worst audio |
| `bv*+ba` | Best video + best audio (merged) |
| `[height<=720]` | Filter: max 720p |
| `[ext=mp4]` | Filter: MP4 format |
| `[fps>30]` | Filter: above 30fps |
| `[filesize<500M]` | Filter: under 500MB |

## Audio Extraction

```bash
# Download best audio and keep original format
yt-dlp -f "ba" "URL"

# Extract audio and convert to MP3
yt-dlp -x --audio-format mp3 "URL"

# Extract audio as high-quality MP3
yt-dlp -x --audio-format mp3 --audio-quality 0 "URL"
# --audio-quality: 0 (best) to 10 (worst) for VBR, or specific kbps

# Extract audio as WAV (uncompressed)
yt-dlp -x --audio-format wav "URL"

# Extract audio as FLAC (lossless)
yt-dlp -x --audio-format flac "URL"

# Extract audio as M4A/AAC
yt-dlp -x --audio-format m4a "URL"

# Extract audio as OGG Vorbis
yt-dlp -x --audio-format vorbis "URL"

# Best audio only (no video), keep original format
yt-dlp -f "bestaudio" "URL"

# Embed thumbnail in audio file
yt-dlp -x --audio-format mp3 --embed-thumbnail "URL"

# Embed metadata in audio file
yt-dlp -x --audio-format mp3 --embed-metadata "URL"

# Full quality audio with all metadata
yt-dlp -x --audio-format mp3 --audio-quality 0 \
  --embed-thumbnail --embed-metadata \
  --add-metadata "URL"
```

### Audio Quality Settings

| Format | Quality Option | Notes |
|--------|---------------|-------|
| MP3 | `--audio-quality 0` | VBR ~245 kbps (V0) |
| MP3 | `--audio-quality 128K` | CBR 128 kbps |
| MP3 | `--audio-quality 320K` | CBR 320 kbps |
| FLAC | N/A | Always lossless |
| WAV | N/A | Always uncompressed |
| M4A | `--audio-quality 0` | Best AAC quality |

## Quality and Resolution

```bash
# Download specific resolution
yt-dlp -f "bv[height=1080]+ba" "URL"     # Exactly 1080p
yt-dlp -f "bv[height<=720]+ba" "URL"     # Up to 720p
yt-dlp -f "bv[height<=480]+ba" "URL"     # Up to 480p

# Download 4K if available
yt-dlp -f "bv[height<=2160]+ba" "URL"

# Prefer specific codec
yt-dlp -f "bv[vcodec^=avc1]+ba[acodec^=mp4a]" "URL"  # H.264 + AAC
yt-dlp -f "bv[vcodec^=vp9]+ba[acodec^=opus]" "URL"    # VP9 + Opus

# Prefer specific FPS
yt-dlp -f "bv[fps>=60]+ba" "URL"         # 60fps or higher
```

## Output Templates

```bash
# Custom filename
yt-dlp -o "%(title)s.%(ext)s" "URL"

# Organized by uploader
yt-dlp -o "%(uploader)s/%(title)s.%(ext)s" "URL"

# With video ID for uniqueness
yt-dlp -o "%(title)s [%(id)s].%(ext)s" "URL"

# To specific directory
yt-dlp -o "~/Downloads/YouTube/%(title)s.%(ext)s" "URL"

# Playlist with numbering
yt-dlp -o "%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s" "PLAYLIST_URL"

# Date-organized
yt-dlp -o "%(upload_date>%Y-%m)s/%(title)s.%(ext)s" "URL"

# Sanitize filename (remove special chars)
yt-dlp -o "%(title).100B.%(ext)s" "URL"  # Limit to 100 bytes
```

### Template Variables

| Variable | Description |
|----------|-------------|
| `%(title)s` | Video title |
| `%(id)s` | Video ID |
| `%(ext)s` | File extension |
| `%(uploader)s` | Channel/uploader name |
| `%(upload_date)s` | Upload date (YYYYMMDD) |
| `%(duration)s` | Duration in seconds |
| `%(playlist)s` | Playlist name |
| `%(playlist_index)s` | Position in playlist |
| `%(resolution)s` | Video resolution |
| `%(fps)s` | Frames per second |

## Playlist Handling

```bash
# Download entire playlist
yt-dlp "PLAYLIST_URL"

# Download specific items from playlist
yt-dlp --playlist-items 1-5 "PLAYLIST_URL"     # First 5 videos
yt-dlp --playlist-items 1,3,5,7 "PLAYLIST_URL"  # Specific items
yt-dlp --playlist-items 3- "PLAYLIST_URL"        # From 3rd onward

# Download playlist in reverse order
yt-dlp --playlist-reverse "PLAYLIST_URL"

# Limit number of downloads
yt-dlp --max-downloads 10 "PLAYLIST_URL"

# Skip playlist, download single video only
yt-dlp --no-playlist "URL"

# Download playlist as audio files
yt-dlp -x --audio-format mp3 --audio-quality 0 \
  -o "%(playlist)s/%(playlist_index)02d - %(title)s.%(ext)s" \
  "PLAYLIST_URL"
```

## Advanced Options

```bash
# Write subtitle files
yt-dlp --write-subs --sub-langs en "URL"
yt-dlp --write-auto-subs --sub-langs en "URL"  # Auto-generated subs

# Embed subtitles in video
yt-dlp --embed-subs --sub-langs en "URL"

# Download thumbnail
yt-dlp --write-thumbnail "URL"
yt-dlp --write-all-thumbnails "URL"

# Write metadata/info JSON
yt-dlp --write-info-json "URL"

# Use cookies (for age-restricted or member content)
yt-dlp --cookies cookies.txt "URL"
yt-dlp --cookies-from-browser chrome "URL"

# Proxy
yt-dlp --proxy socks5://127.0.0.1:1080 "URL"

# Limit download speed
yt-dlp --rate-limit 1M "URL"

# Set output format to specific container
yt-dlp --merge-output-format mkv "URL"
yt-dlp --merge-output-format mp4 "URL"

# Post-processing: convert to specific format
yt-dlp --recode-video mp4 "URL"

# SponsorBlock: skip sponsored segments
yt-dlp --sponsorblock-remove all "URL"

# Configuration file (~/.config/yt-dlp/config)
# Put default options there to avoid typing them every time
```

## Use Case: Downloading Reference Media

```bash
# Download reference track for audio analysis
# Best audio quality, extract as WAV for analysis
yt-dlp -x --audio-format wav \
  -o "~/Development/AudioPlugins/reference_tracks/%(title)s.%(ext)s" \
  "URL"

# Download reference music video for glitch processing
# 1080p MP4 for frame extraction
yt-dlp -f "bv[height<=1080][ext=mp4]+ba[ext=m4a]" \
  --merge-output-format mp4 \
  -o "~/Development/VideoGlitch/source/%(title)s.%(ext)s" \
  "URL"

# Download a batch of reference tracks (from a file)
# Create urls.txt with one URL per line
yt-dlp -x --audio-format wav --audio-quality 0 \
  -o "reference_tracks/%(title)s.%(ext)s" \
  -a urls.txt

# Download tutorial video for offline viewing
yt-dlp -f "bv[height<=720]+ba" \
  --embed-subs --sub-langs en \
  --embed-metadata \
  -o "~/Downloads/Tutorials/%(title)s.%(ext)s" \
  "URL"
```

### Python API (yt-dlp as library)

```python
import yt_dlp

# Download audio programmatically
def download_audio(url, output_dir="downloads"):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info.get('title', 'Unknown')

# Get video info without downloading
def get_info(url):
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title'),
            'duration': info.get('duration'),
            'uploader': info.get('uploader'),
            'formats': len(info.get('formats', [])),
        }

# List available formats
def list_formats(url):
    ydl_opts = {'listformats': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=False)
```

---

# imageio

> Image and video I/O library for Python.
> Install: `pip install imageio` (+ `pip install imageio[ffmpeg]` for video)
> Docs: https://imageio.readthedocs.io/en/stable/

**Always use the v3 API:**
```python
import imageio.v3 as iio
```

## Reading Images

```python
import imageio.v3 as iio
import numpy as np

# Read image from file
img = iio.imread("photo.png")
# Returns: numpy.ndarray
# Shape: (height, width, channels) for color, (height, width) for grayscale
# dtype: typically uint8 (0-255)
print(f"Shape: {img.shape}, dtype: {img.dtype}")

# Read from URL
img = iio.imread("https://example.com/image.png")

# Read from bytes
with open("photo.png", "rb") as f:
    img = iio.imread(f.read())

# Read from BytesIO
from io import BytesIO
img = iio.imread(BytesIO(image_bytes))

# Read from ZIP archive
img = iio.imread("archive.zip/path/to/image.png")

# Read specific frame from multi-frame image (GIF)
frame = iio.imread("animation.gif", index=0)    # First frame
frames = iio.imread("animation.gif", index=None) # All frames as 4D array
# Shape: (n_frames, height, width, channels)

# Read with specific plugin
img = iio.imread("photo.jpg", plugin="pillow")

# Get image metadata
metadata = iio.immeta("photo.png")
# Returns dict: {'shape': (H, W, C), 'dtype': dtype, ...}

# Get image properties
props = iio.improps("photo.png")
# Returns ImageProperties object with shape, dtype, n_images, etc.
```

## Writing Images

```python
import imageio.v3 as iio
import numpy as np

# Write image to file
iio.imwrite("output.png", img_array)
iio.imwrite("output.jpg", img_array)
iio.imwrite("output.bmp", img_array)

# Write to bytes (in memory)
png_bytes = iio.imwrite("<bytes>", img_array, extension=".png")
jpg_bytes = iio.imwrite("<bytes>", img_array, extension=".jpeg")

# Write to BytesIO
from io import BytesIO
buffer = BytesIO()
iio.imwrite(buffer, img_array, plugin="pillow", extension=".png")
png_data = buffer.getvalue()

# Write with quality settings (JPEG)
iio.imwrite("output.jpg", img_array, quality=95)

# Write GIF from multiple frames
frames = [frame1, frame2, frame3]  # list of numpy arrays
iio.imwrite("output.gif", frames, duration=100)  # 100ms per frame
# or
iio.imwrite("output.gif", np.stack(frames), duration=100, loop=0)

# Create image from numpy array
# Grayscale
gray = np.random.randint(0, 255, (480, 640), dtype=np.uint8)
iio.imwrite("gray.png", gray)

# RGB
rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
iio.imwrite("color.png", rgb)

# RGBA (with transparency)
rgba = np.random.randint(0, 255, (480, 640, 4), dtype=np.uint8)
iio.imwrite("transparent.png", rgba)
```

## Reading Videos

```python
import imageio.v3 as iio
import numpy as np

# Read a specific frame by index
frame = iio.imread("video.mp4", index=42, plugin="pyav")
# Returns: numpy.ndarray shape (height, width, 3)

# Read ALL frames into memory (WARNING: large files will use lots of RAM)
all_frames = iio.imread("video.mp4", index=None, plugin="pyav")
# Shape: (n_frames, height, width, 3)
# Only use for short clips!

# Get video metadata
meta = iio.immeta("video.mp4", plugin="pyav")
print(f"FPS: {meta.get('fps', 'unknown')}")
print(f"Duration: {meta.get('duration', 'unknown')}s")

# Get video properties
props = iio.improps("video.mp4", plugin="pyav")
print(f"Shape per frame: {props.shape}")
print(f"Number of frames: {props.n_images}")
```

## Writing Videos

```python
import imageio.v3 as iio
import numpy as np

# Write video using imopen (recommended for large videos)
frames = [np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8) for _ in range(60)]

with iio.imopen("output.mp4", "w", plugin="pyav") as out_file:
    out_file.init_video_stream("libx264", fps=30)
    for frame in frames:
        out_file.write_frame(frame)

# Re-encode a video (transcode)
source = "input.mp4"
dest = "output.mp4"
meta = iio.immeta(source, plugin="pyav")
fps = meta.get("fps", 30)

with iio.imopen(dest, "w", plugin="pyav") as out_file:
    out_file.init_video_stream("libx264", fps=fps)
    for frame in iio.imiter(source, plugin="pyav"):
        out_file.write_frame(frame)

# Write with specific codec settings
with iio.imopen("output.mp4", "w", plugin="pyav") as out_file:
    out_file.init_video_stream("vp9", fps=30)  # VP9 codec
    for frame in frames:
        out_file.write_frame(frame)

# Legacy API (v2 style, still works)
writer = iio.get_writer("output.mp4", fps=30, codec="libx264")
for frame in frames:
    writer.append_data(frame)
writer.close()
```

## Video Frame Iteration

The key pattern for processing large videos without loading everything into memory.

```python
import imageio.v3 as iio
import numpy as np

# Iterate over video frames (memory efficient)
for frame in iio.imiter("video.mp4", plugin="pyav"):
    print(f"Frame shape: {frame.shape}, dtype: {frame.dtype}")
    # Process each frame...

# With frame counter
for idx, frame in enumerate(iio.imiter("video.mp4", plugin="pyav")):
    if idx % 100 == 0:
        print(f"Processing frame {idx}")
    # Process frame...

# Process every Nth frame (skip frames for speed)
for idx, frame in enumerate(iio.imiter("video.mp4", plugin="pyav")):
    if idx % 10 != 0:  # Process every 10th frame
        continue
    processed = some_effect(frame)

# Webcam capture
for idx, frame in enumerate(iio.imiter("<video0>")):
    if idx > 100:
        break
    print(f"Captured frame {idx}: {frame.shape}")

# Screenshot
screenshot = iio.imread("<screen>")
```

## imageio Format Support

### Images

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| PNG | Yes | Yes | Lossless, transparency |
| JPEG | Yes | Yes | Lossy, no transparency |
| BMP | Yes | Yes | Uncompressed |
| GIF | Yes | Yes | Animated, 256 colors |
| TIFF | Yes | Yes | Lossless, multi-page |
| WebP | Yes | Yes | Modern web format |

### Videos (requires imageio-ffmpeg or pyav)

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| MP4 | Yes | Yes | H.264/H.265 |
| AVI | Yes | Yes | Legacy format |
| MOV | Yes | Yes | Apple QuickTime |
| MKV | Yes | Yes | Matroska container |
| WebM | Yes | Yes | VP8/VP9 |
| GIF | Yes | Yes | Animated |

**Install video support:**
```bash
pip install imageio[ffmpeg]    # ffmpeg plugin
pip install imageio[pyav]      # pyav plugin (recommended)
```

## Use Case: Batch Video Frame Processing for Glitch Art

```python
import imageio.v3 as iio
import numpy as np
import os

def extract_frames(video_path, output_dir, every_n=1):
    """Extract frames from video for glitch processing."""
    os.makedirs(output_dir, exist_ok=True)

    meta = iio.immeta(video_path, plugin="pyav")
    print(f"Video FPS: {meta.get('fps', 'unknown')}")

    frame_count = 0
    saved_count = 0
    for frame in iio.imiter(video_path, plugin="pyav"):
        if frame_count % every_n == 0:
            output_path = os.path.join(output_dir, f"frame_{saved_count:06d}.png")
            iio.imwrite(output_path, frame)
            saved_count += 1
        frame_count += 1

    print(f"Extracted {saved_count} frames from {frame_count} total")
    return saved_count

def apply_glitch_effect(frame, effect="pixel_sort"):
    """Apply various glitch effects to a single frame."""
    result = frame.copy()

    if effect == "pixel_sort":
        # Sort pixels by brightness in random rows
        for row in range(0, frame.shape[0], np.random.randint(1, 20)):
            brightness = np.sum(frame[row], axis=1)
            sort_idx = np.argsort(brightness)
            result[row] = frame[row][sort_idx]

    elif effect == "channel_shift":
        # Shift color channels independently
        shift_r = np.random.randint(-20, 20)
        shift_g = np.random.randint(-20, 20)
        result[:, :, 0] = np.roll(frame[:, :, 0], shift_r, axis=1)
        result[:, :, 1] = np.roll(frame[:, :, 1], shift_g, axis=1)

    elif effect == "block_corrupt":
        # Randomly copy blocks to wrong positions
        h, w = frame.shape[:2]
        for _ in range(np.random.randint(5, 30)):
            bh, bw = np.random.randint(10, 100), np.random.randint(10, 200)
            sy, sx = np.random.randint(0, h-bh), np.random.randint(0, w-bw)
            dy, dx = np.random.randint(0, h-bh), np.random.randint(0, w-bw)
            result[dy:dy+bh, dx:dx+bw] = frame[sy:sy+bh, sx:sx+bw]

    elif effect == "data_bend":
        # Treat image data as 1D and shift chunks
        flat = result.reshape(-1)
        start = np.random.randint(0, len(flat) // 2)
        length = np.random.randint(100, 10000)
        shift = np.random.randint(-1000, 1000)
        chunk = flat[start:start+length].copy()
        dest = max(0, min(len(flat)-length, start + shift))
        flat[dest:dest+length] = chunk
        result = flat.reshape(frame.shape)

    return result

def process_video_glitch(input_video, output_video, effect="pixel_sort", intensity=0.3):
    """Apply glitch effect to every frame and reassemble video."""
    meta = iio.immeta(input_video, plugin="pyav")
    fps = meta.get("fps", 30)

    with iio.imopen(output_video, "w", plugin="pyav") as out:
        out.init_video_stream("libx264", fps=fps)
        for idx, frame in enumerate(iio.imiter(input_video, plugin="pyav")):
            if np.random.random() < intensity:
                frame = apply_glitch_effect(frame, effect)
            out.write_frame(frame)
            if idx % 100 == 0:
                print(f"Processed frame {idx}")

    print(f"Glitch video saved to {output_video}")

# Example usage
# extract_frames("music_video.mp4", "frames/", every_n=1)
# process_video_glitch("music_video.mp4", "glitched.mp4", effect="channel_shift", intensity=0.5)
```

### Frame Processing Pipeline

```python
import imageio.v3 as iio
import numpy as np

def frame_pipeline(input_path, output_path, effects_chain):
    """Apply a chain of effects to each video frame.

    Args:
        input_path: Source video file
        output_path: Output video file
        effects_chain: List of (effect_func, probability) tuples
    """
    meta = iio.immeta(input_path, plugin="pyav")
    fps = meta.get("fps", 30)

    with iio.imopen(output_path, "w", plugin="pyav") as out:
        out.init_video_stream("libx264", fps=fps)
        for frame in iio.imiter(input_path, plugin="pyav"):
            for effect_func, prob in effects_chain:
                if np.random.random() < prob:
                    frame = effect_func(frame)
            out.write_frame(frame)

# Define effects
def invert(frame):
    return 255 - frame

def add_noise(frame):
    noise = np.random.randint(-30, 30, frame.shape, dtype=np.int16)
    return np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

def posterize(frame, levels=4):
    factor = 256 // levels
    return (frame // factor * factor).astype(np.uint8)

# Apply pipeline
# frame_pipeline("input.mp4", "output.mp4", [
#     (invert, 0.1),
#     (add_noise, 0.3),
#     (posterize, 0.2),
# ])
```

---

# soundfile

> Audio file I/O via libsndfile. NumPy integration.
> Install: `pip install soundfile`
> Docs: https://python-soundfile.readthedocs.io/

## Reading Audio

```python
import soundfile as sf
import numpy as np

# Basic read (returns float64 by default)
data, samplerate = sf.read("audio.wav")
# data: numpy.ndarray
#   Mono: shape (n_samples,)
#   Stereo: shape (n_samples, n_channels)
# samplerate: int (e.g., 44100)

# Read as specific data type
data, sr = sf.read("audio.wav", dtype='float32')   # 32-bit float [-1.0, 1.0]
data, sr = sf.read("audio.wav", dtype='float64')   # 64-bit float [-1.0, 1.0] (default)
data, sr = sf.read("audio.wav", dtype='int16')      # 16-bit integer [-32768, 32767]
data, sr = sf.read("audio.wav", dtype='int32')      # 32-bit integer

# Read specific portion
data, sr = sf.read("audio.wav", start=44100, stop=88200)
# Reads samples 44100 to 88200 (1 second at 44.1kHz)

# Read specific number of frames
data, sr = sf.read("audio.wav", frames=44100)  # Read first 44100 samples

# Always read as 2D (even mono)
data, sr = sf.read("audio.wav", always_2d=True)
# Mono: shape (n_samples, 1) instead of (n_samples,)

# Read from file-like object
from io import BytesIO
with open("audio.wav", "rb") as f:
    data, sr = sf.read(f)

# Read from BytesIO
data, sr = sf.read(BytesIO(wav_bytes))
```

## Writing Audio

```python
import soundfile as sf
import numpy as np

# Basic write
sf.write("output.wav", data, samplerate=44100)

# Write with specific subtype (bit depth)
sf.write("output.wav", data, 44100, subtype='PCM_16')   # 16-bit WAV
sf.write("output.wav", data, 44100, subtype='PCM_24')   # 24-bit WAV
sf.write("output.wav", data, 44100, subtype='PCM_32')   # 32-bit integer WAV
sf.write("output.wav", data, 44100, subtype='FLOAT')     # 32-bit float WAV
sf.write("output.wav", data, 44100, subtype='DOUBLE')    # 64-bit float WAV

# Write FLAC (lossless compression)
sf.write("output.flac", data, 44100, subtype='PCM_24')

# Write OGG Vorbis
sf.write("output.ogg", data, 44100)

# Write to BytesIO
from io import BytesIO
buffer = BytesIO()
sf.write(buffer, data, 44100, format='WAV', subtype='PCM_16')
wav_bytes = buffer.getvalue()

# Generate and write audio
# Sine wave
sr = 44100
duration = 2.0  # seconds
t = np.linspace(0, duration, int(sr * duration), endpoint=False)
frequency = 440.0
audio = 0.5 * np.sin(2 * np.pi * frequency * t)  # 440 Hz sine at -6dB
sf.write("sine_440.wav", audio.astype(np.float32), sr, subtype='FLOAT')

# Stereo sine (left=440Hz, right=880Hz)
left = 0.5 * np.sin(2 * np.pi * 440 * t)
right = 0.5 * np.sin(2 * np.pi * 880 * t)
stereo = np.column_stack([left, right])
sf.write("stereo_test.wav", stereo.astype(np.float32), sr, subtype='FLOAT')
```

## File Information

```python
import soundfile as sf

# Get file info without reading data
info = sf.info("audio.wav")
print(f"Sample rate: {info.samplerate}")       # e.g., 44100
print(f"Channels: {info.channels}")             # e.g., 2
print(f"Frames: {info.frames}")                 # Total sample frames
print(f"Duration: {info.duration:.2f}s")        # Duration in seconds
print(f"Format: {info.format}")                 # e.g., 'WAV'
print(f"Subtype: {info.subtype}")               # e.g., 'PCM_16'
print(f"Subtype info: {info.subtype_info}")     # e.g., 'Signed 16 bit PCM'

# Check available formats
print(sf.available_formats())
# {'AIFF': 'AIFF (Apple/SGI)', 'AU': 'AU (Sun/NeXT)', 'AVR': 'AVR (Audio Visual Research)',
#  'CAF': 'CAF (Apple Core Audio File)', 'FLAC': 'FLAC (Free Lossless Audio Codec)',
#  'HTK': 'HTK (HMM Tool Kit)', ...}

# Check available subtypes
print(sf.available_subtypes())
# {'PCM_S8': 'Signed 8 bit PCM', 'PCM_16': 'Signed 16 bit PCM',
#  'PCM_24': 'Signed 24 bit PCM', 'PCM_32': 'Signed 32 bit PCM',
#  'PCM_U8': 'Unsigned 8 bit PCM', 'FLOAT': '32 bit float',
#  'DOUBLE': '64 bit float', ...}

# Check available subtypes for a specific format
print(sf.available_subtypes('FLAC'))
# {'PCM_S8': '...', 'PCM_16': '...', 'PCM_24': '...'}
```

## Block-Wise Reading

For processing large audio files without loading everything into memory.

```python
import soundfile as sf
import numpy as np

# Read in blocks (generator)
for block in sf.blocks("large_file.wav", blocksize=4096):
    # block: numpy.ndarray shape (4096, n_channels) or (4096,) for mono
    rms = np.sqrt(np.mean(block**2))
    print(f"Block RMS: {rms:.6f}")

# Read in overlapping blocks
for block in sf.blocks("large_file.wav", blocksize=4096, overlap=2048):
    # 50% overlap between blocks
    process(block)

# Read with dtype
for block in sf.blocks("large_file.wav", blocksize=4096, dtype='float32'):
    process(block)

# Read blocks from specific position
for block in sf.blocks("large_file.wav", blocksize=4096, start=44100):
    process(block)

# Process large file efficiently
def process_large_file(input_path, output_path, effect_func, blocksize=8192):
    """Apply an effect function to a large file in chunks."""
    info = sf.info(input_path)

    with sf.SoundFile(input_path, 'r') as infile:
        with sf.SoundFile(output_path, 'w',
                          samplerate=info.samplerate,
                          channels=info.channels,
                          subtype=info.subtype) as outfile:
            while infile.tell() < infile.frames:
                data = infile.read(blocksize)
                processed = effect_func(data)
                outfile.write(processed)

# Example: apply gain
def apply_gain(data, gain_db=6.0):
    gain_linear = 10**(gain_db / 20.0)
    return np.clip(data * gain_linear, -1.0, 1.0)

# process_large_file("input.wav", "output.wav", lambda d: apply_gain(d, 3.0))
```

## SoundFile Class

For more control over reading and writing, use the SoundFile class directly.

```python
import soundfile as sf
import numpy as np

# Read mode
with sf.SoundFile("audio.wav", "r") as f:
    print(f"Sample rate: {f.samplerate}")
    print(f"Channels: {f.channels}")
    print(f"Frames: {f.frames}")
    print(f"Format: {f.format}")
    print(f"Subtype: {f.subtype}")

    # Read chunks
    chunk1 = f.read(1024)   # Read 1024 frames
    chunk2 = f.read(1024)   # Read next 1024 frames

    # Seek
    f.seek(0)               # Back to start
    f.seek(44100)           # Jump to 1 second mark
    position = f.tell()     # Current position

    # Read remaining
    remaining = f.read()

# Write mode
with sf.SoundFile("output.wav", "w",
                   samplerate=44100,
                   channels=2,
                   subtype='PCM_24') as f:
    # Write chunks
    f.write(chunk1)
    f.write(chunk2)
    f.write(chunk3)

# Read-write mode (modify existing file)
with sf.SoundFile("audio.wav", "r+") as f:
    data = f.read()
    f.seek(0)
    f.write(data * 0.5)  # Halve the volume

# Append mode (not supported by all formats)
# WAV supports it; others may not
```

## Supported Formats and Subtypes

### Formats

| Format | Extension | Lossless | Notes |
|--------|-----------|----------|-------|
| WAV | .wav | Yes | Universal, uncompressed by default |
| FLAC | .flac | Yes | Compressed lossless, ~60% WAV size |
| OGG | .ogg | No | Vorbis codec, good quality/size |
| AIFF | .aiff | Yes | Apple format, like WAV |
| CAF | .caf | Varies | Apple Core Audio, flexible |
| RAW | .raw | Yes | No header, must specify params |
| MAT5 | .mat | Yes | MATLAB format |
| W64 | .w64 | Yes | Extended WAV (>4GB files) |

### Subtypes (Bit Depth / Encoding)

| Subtype | Bits | Type | Range | Use Case |
|---------|------|------|-------|----------|
| `PCM_S8` | 8 | Integer | [-128, 127] | Low quality, tiny files |
| `PCM_16` | 16 | Integer | [-32768, 32767] | CD quality standard |
| `PCM_24` | 24 | Integer | [-8388608, 8388607] | Professional audio standard |
| `PCM_32` | 32 | Integer | [-2^31, 2^31-1] | Rarely used |
| `FLOAT` | 32 | Float | [-1.0, 1.0]* | DAW internal format |
| `DOUBLE` | 64 | Float | [-1.0, 1.0]* | Maximum precision |

*Float formats can exceed [-1.0, 1.0] without clipping during processing.

### Choosing the Right Format

| Scenario | Format | Subtype |
|----------|--------|---------|
| Plugin test files | WAV | FLOAT (32-bit) |
| Final master | WAV | PCM_24 |
| CD distribution | WAV | PCM_16 |
| Archive/backup | FLAC | PCM_24 |
| Web streaming | OGG | (auto) |
| Analysis intermediate | WAV | FLOAT |

## Use Case: Audio I/O for Plugin Testing and Analysis

### Generate Test Signals

```python
import soundfile as sf
import numpy as np

def generate_test_signals(output_dir="test_signals", sr=44100):
    """Generate a comprehensive set of test signals for plugin testing."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    # 1. Sine waves at key frequencies
    for freq in [50, 100, 440, 1000, 5000, 10000, 15000]:
        signal = 0.5 * np.sin(2 * np.pi * freq * t)
        sf.write(f"{output_dir}/sine_{freq}hz.wav", signal.astype(np.float32), sr,
                 subtype='FLOAT')

    # 2. White noise
    noise = np.random.randn(int(sr * duration)).astype(np.float32) * 0.3
    sf.write(f"{output_dir}/white_noise.wav", noise, sr, subtype='FLOAT')

    # 3. Pink noise (1/f spectrum)
    # Approximate pink noise using filtered white noise
    from scipy.signal import sosfilt, butter
    white = np.random.randn(int(sr * duration))
    sos = butter(1, 20, btype='high', fs=sr, output='sos')
    pink = sosfilt(sos, white)
    pink = (pink / np.max(np.abs(pink)) * 0.3).astype(np.float32)
    sf.write(f"{output_dir}/pink_noise.wav", pink, sr, subtype='FLOAT')

    # 4. Impulse
    impulse = np.zeros(int(sr * 1.0), dtype=np.float32)
    impulse[int(0.1 * sr)] = 1.0
    sf.write(f"{output_dir}/impulse.wav", impulse, sr, subtype='FLOAT')

    # 5. Sweep (logarithmic chirp 20Hz-20kHz)
    f0, f1 = 20, 20000
    sweep = 0.5 * np.sin(2 * np.pi * f0 * duration / np.log(f1/f0) *
                          (np.exp(t / duration * np.log(f1/f0)) - 1))
    sf.write(f"{output_dir}/log_sweep.wav", sweep.astype(np.float32), sr,
             subtype='FLOAT')

    # 6. Square wave (for clipping/saturation testing)
    square = 0.5 * np.sign(np.sin(2 * np.pi * 440 * t))
    sf.write(f"{output_dir}/square_440hz.wav", square.astype(np.float32), sr,
             subtype='FLOAT')

    # 7. Stereo test (left=440Hz, right=880Hz)
    left = 0.5 * np.sin(2 * np.pi * 440 * t)
    right = 0.5 * np.sin(2 * np.pi * 880 * t)
    stereo = np.column_stack([left, right]).astype(np.float32)
    sf.write(f"{output_dir}/stereo_test.wav", stereo, sr, subtype='FLOAT')

    # 8. Dynamic test (quiet to loud)
    dynamic = np.zeros_like(t, dtype=np.float32)
    segment_len = len(t) // 8
    for i, db in enumerate([-60, -48, -36, -24, -12, -6, -3, 0]):
        gain = 10**(db / 20.0) * 0.99
        start = i * segment_len
        end = start + segment_len
        dynamic[start:end] = gain * np.sin(2 * np.pi * 1000 * t[start:end])
    sf.write(f"{output_dir}/dynamic_range.wav", dynamic, sr, subtype='FLOAT')

    print(f"Generated test signals in {output_dir}/")

# generate_test_signals()
```

### A/B Comparison Tool

```python
import soundfile as sf
import numpy as np

def compare_audio_files(file_a, file_b):
    """Compare two audio files for A/B testing plugin output."""
    data_a, sr_a = sf.read(file_a, dtype='float64')
    data_b, sr_b = sf.read(file_b, dtype='float64')

    info_a = sf.info(file_a)
    info_b = sf.info(file_b)

    print(f"File A: {file_a}")
    print(f"  SR: {sr_a}, Channels: {info_a.channels}, "
          f"Duration: {info_a.duration:.2f}s, Subtype: {info_a.subtype}")

    print(f"File B: {file_b}")
    print(f"  SR: {sr_b}, Channels: {info_b.channels}, "
          f"Duration: {info_b.duration:.2f}s, Subtype: {info_b.subtype}")

    # Ensure same length for comparison
    min_len = min(len(data_a), len(data_b))
    a = data_a[:min_len]
    b = data_b[:min_len]

    # Make both 2D
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    if b.ndim == 1:
        b = b.reshape(-1, 1)

    # Compute difference
    diff = a - b

    # Stats
    rms_a = np.sqrt(np.mean(a**2))
    rms_b = np.sqrt(np.mean(b**2))
    rms_diff = np.sqrt(np.mean(diff**2))
    peak_diff = np.max(np.abs(diff))
    correlation = np.corrcoef(a.flatten(), b.flatten())[0, 1]

    print(f"\nComparison:")
    print(f"  RMS A: {20*np.log10(rms_a+1e-10):.1f} dBFS")
    print(f"  RMS B: {20*np.log10(rms_b+1e-10):.1f} dBFS")
    print(f"  RMS Difference: {20*np.log10(rms_diff+1e-10):.1f} dBFS")
    print(f"  Peak Difference: {20*np.log10(peak_diff+1e-10):.1f} dBFS")
    print(f"  Correlation: {correlation:.6f}")
    print(f"  Files are {'identical' if peak_diff < 1e-10 else 'different'}")

    # Save difference signal
    diff_path = file_a.replace('.wav', '_diff.wav')
    sf.write(diff_path, diff.astype(np.float32), sr_a, subtype='FLOAT')
    print(f"  Difference saved to: {diff_path}")

    return {
        'rms_diff_db': 20*np.log10(rms_diff+1e-10),
        'peak_diff_db': 20*np.log10(peak_diff+1e-10),
        'correlation': correlation,
    }

# compare_audio_files("dry.wav", "processed.wav")
```

### Batch Format Conversion

```python
import soundfile as sf
import os

def convert_audio_batch(input_dir, output_dir, target_format='WAV',
                         target_subtype='PCM_24', target_sr=None):
    """Convert a batch of audio files to a target format."""
    os.makedirs(output_dir, exist_ok=True)

    supported_ext = {'.wav', '.flac', '.ogg', '.aiff', '.aif'}

    for filename in sorted(os.listdir(input_dir)):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in supported_ext:
            continue

        input_path = os.path.join(input_dir, filename)
        name = os.path.splitext(filename)[0]

        format_ext = {'WAV': '.wav', 'FLAC': '.flac', 'OGG': '.ogg', 'AIFF': '.aiff'}
        output_ext = format_ext.get(target_format, '.wav')
        output_path = os.path.join(output_dir, f"{name}{output_ext}")

        try:
            data, sr = sf.read(input_path, dtype='float64')

            # Resample if needed
            if target_sr and sr != target_sr:
                from scipy.signal import resample
                num_samples = int(len(data) * target_sr / sr)
                data = resample(data, num_samples)
                sr = target_sr

            sf.write(output_path, data, sr,
                     format=target_format, subtype=target_subtype)
            print(f"Converted: {filename} -> {output_ext} ({target_subtype})")

        except Exception as e:
            print(f"Failed: {filename} - {e}")

# Convert all to 24-bit WAV at 48kHz
# convert_audio_batch("raw/", "converted/", 'WAV', 'PCM_24', 48000)

# Convert all to FLAC for archival
# convert_audio_batch("masters/", "archive/", 'FLAC', 'PCM_24')
```

---

## Integration Patterns

### soundfile + librosa

```python
import soundfile as sf
import librosa

# soundfile for I/O, librosa for analysis
data, sr = sf.read("audio.wav")  # Native sample rate
mfcc = librosa.feature.mfcc(y=data, sr=sr)

# librosa for processing, soundfile for output
y, sr = librosa.load("audio.wav", sr=None)
y_stretched = librosa.effects.time_stretch(y, rate=1.5)
sf.write("stretched.wav", y_stretched, sr, subtype='FLOAT')
```

### soundfile + scipy.signal

```python
import soundfile as sf
from scipy.signal import butter, sosfilt

# Read, filter, write
data, sr = sf.read("audio.wav", dtype='float32')
sos = butter(4, 1000, btype='low', fs=sr, output='sos')
filtered = sosfilt(sos, data, axis=0)
sf.write("filtered.wav", filtered, sr, subtype='FLOAT')
```

### imageio + soundfile (video + audio)

```python
import imageio.v3 as iio
import soundfile as sf

# Extract frames from video for visual analysis while
# analyzing the audio track separately
# (Use ffmpeg to separate audio from video first)

# Split with ffmpeg:
# ffmpeg -i video.mp4 -vn -acodec pcm_s24le audio.wav
# ffmpeg -i video.mp4 -an frames/frame_%06d.png

# Then analyze both:
audio, sr = sf.read("audio.wav")
for idx, frame in enumerate(iio.imiter("video.mp4", plugin="pyav")):
    # Correlate visual frame with audio at same timestamp
    timestamp = idx / 30.0  # Assuming 30fps
    audio_sample = int(timestamp * sr)
    # ...
```
