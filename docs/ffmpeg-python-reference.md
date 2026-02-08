# ffmpeg-python Wrapper Reference

> **Package:** ffmpeg-python 0.2.0
> **Import:** `import ffmpeg`
> **Purpose:** Pythonic wrapper for FFmpeg with complex filter graph support
> **Dependencies:** FFmpeg must be installed and in PATH (`brew install ffmpeg`)
> **PyPI:** `pip install ffmpeg-python` (NOT `ffmpeg` or `python-ffmpeg`)
> **GitHub:** https://github.com/kkroening/ffmpeg-python
> **API Docs:** https://kkroening.github.io/ffmpeg-python/

---

## Table of Contents

1. [Core Concepts](#1-core-concepts)
2. [Input and Output](#2-input-and-output)
3. [Video Filters](#3-video-filters)
4. [Custom Filters](#4-custom-filters)
5. [Complex Filter Graphs](#5-complex-filter-graphs)
6. [Audio/Video Stream Selection](#6-audiovideo-stream-selection)
7. [Probing File Info](#7-probing-file-info)
8. [Running Commands](#8-running-commands)
9. [Integration with NumPy/PIL](#9-integration-with-numpypil)
10. [Common Recipes](#10-common-recipes)
11. [Error Handling](#11-error-handling)
12. [vs. subprocess FFmpeg](#12-comparison-with-subprocess-ffmpeg-calls)

---

## 1. Core Concepts

ffmpeg-python builds a **stream graph** that represents the FFmpeg filter pipeline. No processing happens until you call `.run()`. The graph is constructed using either a **functional** or **fluent** API style.

### Functional Style

```python
import ffmpeg

stream = ffmpeg.input('input.mp4')
stream = ffmpeg.hflip(stream)
stream = ffmpeg.output(stream, 'output.mp4')
ffmpeg.run(stream)
```

### Fluent Style (Recommended)

```python
import ffmpeg

(
    ffmpeg
    .input('input.mp4')
    .hflip()
    .output('output.mp4')
    .run()
)
```

Both styles produce identical FFmpeg commands. Mix and match as needed.

---

## 2. Input and Output

### ffmpeg.input()

```python
ffmpeg.input(filename, **kwargs)
```

Defines an input file (maps to FFmpeg `-i` option). Accepts arbitrary kwargs passed to FFmpeg.

```python
# Basic file input
stream = ffmpeg.input('video.mp4')

# With options
stream = ffmpeg.input('video.mp4', ss=10, t=20)  # Start at 10s, duration 20s
stream = ffmpeg.input('video.mp4', r=30)          # Force input framerate

# From stdin (pipe)
stream = ffmpeg.input('pipe:', format='rawvideo', pix_fmt='rgb24',
                       s='640x480', framerate=30)

# From webcam (macOS)
stream = ffmpeg.input('0', format='avfoundation', framerate=30,
                       video_size='1280x720')

# From URL/stream
stream = ffmpeg.input('rtsp://camera.example.com/stream')
stream = ffmpeg.input('https://example.com/video.mp4')

# Image sequence (glob pattern)
stream = ffmpeg.input('frames/frame_%04d.png', framerate=24)
```

### ffmpeg.output()

```python
ffmpeg.output(*streams_and_filename, **kwargs)
```

Specifies the output file. The last positional argument is the filename.

```python
# Basic output
stream = ffmpeg.input('input.mp4').output('output.mp4')

# With codec and quality settings
stream = (
    ffmpeg
    .input('input.mp4')
    .output('output.mp4',
            vcodec='libx264',      # Video codec
            acodec='aac',          # Audio codec
            video_bitrate='5000k', # Maps to -b:v
            audio_bitrate='192k',  # Maps to -b:a
            crf=18,                # Quality (0-51, lower = better)
            preset='medium',       # Encoding speed
            pix_fmt='yuv420p',     # Pixel format (for compatibility)
            movflags='faststart',  # Web streaming optimization
            )
)

# To stdout (pipe)
stream = ffmpeg.input('input.mp4').output('pipe:', format='rawvideo', pix_fmt='rgb24')

# Multiple outputs
out1 = ffmpeg.input('input.mp4').output('out1.mp4')
out2 = ffmpeg.input('input.mp4').output('out2.webm')
ffmpeg.merge_outputs(out1, out2).run()
```

### Special Parameter Names

FFmpeg options with colons (like `-b:v`, `-qscale:v`) use dict unpacking:

```python
(
    ffmpeg
    .input('in.mp4')
    .output('out.mp4', **{'qscale:v': 3, 'b:a': '192k'})
    .run()
)
```

### Overwrite Output

```python
# Add -y flag to overwrite without prompting
(
    ffmpeg
    .input('input.mp4')
    .output('output.mp4')
    .overwrite_output()
    .run()
)
```

---

## 3. Video Filters

### Built-in Filter Methods

```python
import ffmpeg

stream = ffmpeg.input('input.mp4')

# Horizontal flip
stream = stream.hflip()

# Vertical flip
stream = stream.vflip()

# Crop
stream = stream.crop(x=100, y=50, width=640, height=480)
# Also accepts FFmpeg expressions:
stream = stream.crop('in_w-2*10', 'in_h-2*20')

# Drawbox
stream = stream.drawbox(x=50, y=50, width=120, height=120,
                         color='red', thickness=5)

# Drawtext
stream = stream.drawtext(text='Hello World', x=10, y=10,
                          fontsize=24, fontcolor='white',
                          fontfile='/path/to/font.ttf')

# Overlay
main = ffmpeg.input('main.mp4')
overlay = ffmpeg.input('overlay.png')
stream = ffmpeg.overlay(main, overlay, x=10, y=10)

# Hue adjustment
stream = stream.hue(h=90, s=2)  # h=hue degrees, s=saturation multiplier

# Color channel mixing
stream = stream.colorchannelmixer()

# Zoom and pan
stream = stream.zoompan(z='min(zoom+0.001,1.5)', d=300,
                         x='iw/2-(iw/zoom/2)', y='ih/2-(ih/zoom/2)',
                         s='1920x1080')

# Set presentation timestamps (speed control)
stream = stream.setpts('0.5*PTS')   # 2x speed
stream = stream.setpts('2.0*PTS')   # 0.5x speed

# Trim
stream = stream.trim(start=5, end=15)
stream = stream.trim(start_frame=100, end_frame=500)

# Concatenation
clip1 = ffmpeg.input('a.mp4').trim(start=0, end=5).setpts('PTS-STARTPTS')
clip2 = ffmpeg.input('b.mp4').trim(start=0, end=5).setpts('PTS-STARTPTS')
joined = ffmpeg.concat(clip1, clip2)
```

---

## 4. Custom Filters

### filter() / filter_()

For any FFmpeg filter not directly wrapped:

```python
# Generic filter application
stream = ffmpeg.input('input.mp4')
stream = ffmpeg.filter(stream, 'fps', fps=25, round='up')
stream = ffmpeg.output(stream, 'output.mp4')

# Fluent style (use filter_ to avoid conflict with Python's built-in filter)
stream = (
    ffmpeg
    .input('input.mp4')
    .filter_('fps', fps=25, round='up')
    .output('output.mp4')
)
```

### Useful FFmpeg Filters via filter_()

```python
# Scale/resize
stream = stream.filter_('scale', 1280, 720)
stream = stream.filter_('scale', 'iw/2', 'ih/2')  # Half size

# Deinterlace
stream = stream.filter_('yadif')

# Denoise
stream = stream.filter_('hqdn3d')

# Deflicker
stream = stream.filter_('deflicker', mode='pm', size=10)

# Color balance
stream = stream.filter_('eq', brightness=0.1, contrast=1.2, saturation=1.5)

# Blur
stream = stream.filter_('boxblur', luma_radius=5, luma_power=2)

# Sharpen
stream = stream.filter_('unsharp', luma_msize_x=5, luma_msize_y=5, luma_amount=1.5)

# Fade
stream = stream.filter_('fade', type='in', start_time=0, duration=2)
stream = stream.filter_('fade', type='out', start_time=8, duration=2)

# Rotate (radians, or use degrees with *PI/180)
stream = stream.filter_('rotate', angle='45*PI/180')

# Reverse
stream = stream.filter_('reverse')

# Chromakey (green screen)
stream = stream.filter_('chromakey', color='0x00FF00', similarity=0.3, blend=0.1)

# LUT (lookup table for color grading)
stream = stream.filter_('lut', r='val*1.2', g='val*0.8', b='val*1.1')

# Noise
stream = stream.filter_('noise', alls=20, allf='t')

# Glitch-like: datascope (visualize data)
stream = stream.filter_('datascope', size='1920x1080', x=0, y=0, mode=0)

# Pixel format conversion
stream = stream.filter_('format', pix_fmts='yuv420p')
```

### Multiple Input Filters

```python
# Overlay with positioning
main = ffmpeg.input('main.mp4')
logo = ffmpeg.input('logo.png')
stream = ffmpeg.filter([main, logo], 'overlay', 10, 10)
stream = ffmpeg.output(stream, 'output.mp4')
```

### Multiple Output Filters

```python
# Split a stream into multiple
split = (
    ffmpeg
    .input('input.mp4')
    .filter_multi_output('split')  # Creates 2 outputs by default
)

# Use split streams
normal = split[0]
reversed_stream = split[1].filter_('reverse')
joined = ffmpeg.concat(normal, reversed_stream)
```

---

## 5. Complex Filter Graphs

### Trim, Concat, Overlay

```python
import ffmpeg

in_file = ffmpeg.input('input.mp4')
overlay_file = ffmpeg.input('overlay.png')

(
    ffmpeg
    .concat(
        in_file.trim(start_frame=10, end_frame=20).setpts('PTS-STARTPTS'),
        in_file.trim(start_frame=30, end_frame=40).setpts('PTS-STARTPTS'),
    )
    .overlay(overlay_file.hflip())
    .drawbox(50, 50, 120, 120, color='red', thickness=5)
    .output('out.mp4')
    .run()
)
```

### Audio + Video Processing

```python
input_file = ffmpeg.input('input.mp4')

# Split into audio and video streams
video = input_file.video
audio = input_file.audio

# Process video
video = video.hflip()

# Process audio
audio = audio.filter_('volume', volume=0.5)

# Recombine
output = ffmpeg.output(video, audio, 'output.mp4')
output.run()
```

### Multiple Inputs with Timing

```python
# Concatenate video files with audio
clip1 = ffmpeg.input('clip1.mp4')
clip2 = ffmpeg.input('clip2.mp4')

# v=1, a=1 means 1 video stream and 1 audio stream per segment
joined = ffmpeg.concat(clip1, clip2, v=1, a=1)
joined.output('combined.mp4').run()
```

### Picture-in-Picture

```python
main = ffmpeg.input('main.mp4')
pip_stream = ffmpeg.input('small.mp4').filter_('scale', 320, 240)

(
    ffmpeg
    .overlay(main, pip_stream, x='main_w-overlay_w-10', y=10)
    .output('pip_output.mp4')
    .run()
)
```

---

## 6. Audio/Video Stream Selection

Some filters only work on video and drop audio. Use `.audio` and `.video` to separate streams.

```python
input_file = ffmpeg.input('input.mp4')

# Select video stream only
video = input_file.video      # Shorthand for input_file['v']

# Select audio stream only
audio = input_file.audio      # Shorthand for input_file['a']

# Process video while keeping audio intact
video = input_file.video.hflip()
audio = input_file.audio

# Re-merge
ffmpeg.output(video, audio, 'output.mp4').run()
```

---

## 7. Probing File Info

### ffmpeg.probe()

```python
probe = ffmpeg.probe('video.mp4')

# Get video stream info
video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
width = int(video_info['width'])
height = int(video_info['height'])
duration = float(video_info.get('duration', probe['format']['duration']))
fps_str = video_info['r_frame_rate']  # e.g., '30/1'
num, den = fps_str.split('/')
fps = int(num) / int(den)

print(f"Resolution: {width}x{height}")
print(f"Duration: {duration}s")
print(f"FPS: {fps}")
print(f"Codec: {video_info['codec_name']}")

# Get audio stream info
audio_info = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
if audio_info:
    print(f"Audio codec: {audio_info['codec_name']}")
    print(f"Sample rate: {audio_info['sample_rate']}")
    print(f"Channels: {audio_info['channels']}")

# Additional probe options
probe = ffmpeg.probe('video.mp4', cmd='ffprobe')  # Custom ffprobe path
```

---

## 8. Running Commands

### run() - Execute and Wait

```python
# Basic run
ffmpeg.input('in.mp4').output('out.mp4').run()

# Capture output
out, err = (
    ffmpeg
    .input('in.mp4')
    .output('out.mp4')
    .run(capture_stdout=True, capture_stderr=True)
)

# Quiet mode (suppress ffmpeg output)
ffmpeg.input('in.mp4').output('out.mp4').run(quiet=True)

# Overwrite output without prompting
ffmpeg.input('in.mp4').output('out.mp4').run(overwrite_output=True)

# Custom ffmpeg binary
ffmpeg.input('in.mp4').output('out.mp4').run(cmd='/usr/local/bin/ffmpeg')
```

### run_async() - Execute Asynchronously

```python
# Returns subprocess.Popen object
process = (
    ffmpeg
    .input('in.mp4')
    .output('pipe:', format='rawvideo', pix_fmt='rgb24')
    .run_async(pipe_stdout=True)
)

# Read frames from pipe
while True:
    in_bytes = process.stdout.read(width * height * 3)
    if not in_bytes:
        break
    frame = np.frombuffer(in_bytes, np.uint8).reshape([height, width, 3])
    # Process frame...

process.wait()
```

### compile() - Get Command Without Running

```python
# Returns list of command-line arguments (includes 'ffmpeg')
cmd = ffmpeg.input('in.mp4').hflip().output('out.mp4').compile()
print(' '.join(cmd))
# Output: ffmpeg -i in.mp4 -filter_complex [0]hflip[s0] -map [s0] out.mp4
```

### get_args() - Get Arguments Only

```python
# Returns list without the 'ffmpeg' prefix
args = ffmpeg.input('in.mp4').hflip().output('out.mp4').get_args()
print(args)
```

---

## 9. Integration with NumPy/PIL

### Read Frames as NumPy Arrays

```python
import ffmpeg
import numpy as np

# Get video info first
probe = ffmpeg.probe('input.mp4')
video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
width = int(video_info['width'])
height = int(video_info['height'])

# Read all frames into pipe
out, _ = (
    ffmpeg
    .input('input.mp4')
    .output('pipe:', format='rawvideo', pix_fmt='rgb24')
    .run(capture_stdout=True, quiet=True)
)

# Convert to numpy array
video = np.frombuffer(out, np.uint8).reshape([-1, height, width, 3])
print(f"Total frames: {video.shape[0]}")
print(f"Frame shape: {video.shape[1:]}")
```

### Write NumPy Arrays to Video

```python
import ffmpeg
import numpy as np

height, width = 480, 640
fps = 30

# Create writer process
process = (
    ffmpeg
    .input('pipe:', format='rawvideo', pix_fmt='rgb24',
           s=f'{width}x{height}', framerate=fps)
    .output('output.mp4', vcodec='libx264', pix_fmt='yuv420p', crf=18)
    .overwrite_output()
    .run_async(pipe_stdin=True)
)

# Write frames
for i in range(300):  # 10 seconds at 30fps
    frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    process.stdin.write(frame.tobytes())

process.stdin.close()
process.wait()
```

### Frame-by-Frame Processing Pipeline

```python
import ffmpeg
import numpy as np

input_file = 'input.mp4'
output_file = 'output.mp4'

# Probe
probe = ffmpeg.probe(input_file)
video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
width = int(video_info['width'])
height = int(video_info['height'])

# Reader process
reader = (
    ffmpeg
    .input(input_file)
    .output('pipe:', format='rawvideo', pix_fmt='rgb24')
    .run_async(pipe_stdout=True, quiet=True)
)

# Writer process
writer = (
    ffmpeg
    .input('pipe:', format='rawvideo', pix_fmt='rgb24',
           s=f'{width}x{height}', framerate=30)
    .output(output_file, vcodec='libx264', pix_fmt='yuv420p')
    .overwrite_output()
    .run_async(pipe_stdin=True, quiet=True)
)

# Process frame by frame
while True:
    in_bytes = reader.stdout.read(width * height * 3)
    if not in_bytes:
        break

    frame = np.frombuffer(in_bytes, np.uint8).reshape([height, width, 3])

    # === YOUR PROCESSING HERE ===
    processed = 255 - frame  # Example: invert colors

    writer.stdin.write(processed.tobytes())

reader.stdout.close()
writer.stdin.close()
reader.wait()
writer.wait()
```

### With PIL/Pillow

```python
import ffmpeg
import numpy as np
from PIL import Image

# Read a single frame as PIL Image
out, _ = (
    ffmpeg
    .input('input.mp4', ss=5)  # Seek to 5 seconds
    .filter_('select', 'gte(n,0)')
    .output('pipe:', vframes=1, format='image2', vcodec='png')
    .run(capture_stdout=True, quiet=True)
)

image = Image.open(io.BytesIO(out))
```

---

## 10. Common Recipes

### Trim a Video

```python
(
    ffmpeg
    .input('input.mp4', ss=10, t=30)  # Start at 10s, 30s duration
    .output('trimmed.mp4', codec='copy')  # Stream copy = no re-encoding
    .run()
)
```

### Extract Audio

```python
(
    ffmpeg
    .input('video.mp4')
    .output('audio.mp3', acodec='libmp3lame', audio_bitrate='320k')
    .run()
)

# As WAV
(
    ffmpeg
    .input('video.mp4')
    .output('audio.wav', acodec='pcm_s16le', ar=44100)
    .run()
)
```

### Generate Thumbnail

```python
(
    ffmpeg
    .input('video.mp4', ss=5)
    .filter_('scale', 320, -1)
    .output('thumb.png', vframes=1)
    .run()
)
```

### Concatenate Videos (Same Format)

```python
# Using concat demuxer (fastest, no re-encoding)
# First create a file list
with open('filelist.txt', 'w') as f:
    f.write("file 'clip1.mp4'\n")
    f.write("file 'clip2.mp4'\n")
    f.write("file 'clip3.mp4'\n")

(
    ffmpeg
    .input('filelist.txt', f='concat', safe=0)
    .output('combined.mp4', codec='copy')
    .run()
)

# Using concat filter (re-encodes, handles different formats)
clip1 = ffmpeg.input('clip1.mp4')
clip2 = ffmpeg.input('clip2.mp4')
ffmpeg.concat(clip1, clip2, v=1, a=1).output('combined.mp4').run()
```

### Add Watermark/Overlay

```python
main = ffmpeg.input('video.mp4')
logo = ffmpeg.input('watermark.png')

(
    ffmpeg
    .overlay(main, logo, x='main_w-overlay_w-10', y='main_h-overlay_h-10')
    .output('watermarked.mp4')
    .run()
)
```

### Convert Format

```python
# MP4 to WebM
(
    ffmpeg
    .input('input.mp4')
    .output('output.webm', vcodec='libvpx-vp9', acodec='libopus',
            crf=30, **{'b:v': '0'})
    .run()
)

# Video to GIF
(
    ffmpeg
    .input('input.mp4', ss=0, t=5)
    .filter_('fps', fps=15)
    .filter_('scale', 480, -1, flags='lanczos')
    .output('output.gif')
    .run()
)
```

### Apply Color Grading

```python
(
    ffmpeg
    .input('input.mp4')
    .filter_('eq', brightness=0.06, contrast=1.2, saturation=1.3, gamma=1.1)
    .filter_('unsharp', luma_msize_x=5, luma_msize_y=5, luma_amount=0.5)
    .output('graded.mp4')
    .run()
)
```

### Speed Change

```python
# 2x speed (video + audio)
input_file = ffmpeg.input('input.mp4')
video = input_file.video.setpts('0.5*PTS')
audio = input_file.audio.filter_('atempo', 2.0)
ffmpeg.output(video, audio, 'fast.mp4').run()

# 0.5x speed (slow motion)
input_file = ffmpeg.input('input.mp4')
video = input_file.video.setpts('2.0*PTS')
audio = input_file.audio.filter_('atempo', 0.5)
ffmpeg.output(video, audio, 'slow.mp4').run()
```

### Extract Frames as Images

```python
(
    ffmpeg
    .input('input.mp4')
    .filter_('fps', fps=1)  # 1 frame per second
    .output('frames/frame_%04d.png')
    .run()
)
```

### Assemble Images into Video

```python
(
    ffmpeg
    .input('frames/frame_%04d.png', framerate=24)
    .filter_('deflicker', mode='pm', size=10)
    .filter_('scale', 1920, 1080)
    .output('assembled.mp4', vcodec='libx264', crf=18, pix_fmt='yuv420p')
    .run()
)
```

---

## 11. Error Handling

```python
import ffmpeg

try:
    (
        ffmpeg
        .input('nonexistent.mp4')
        .output('out.mp4')
        .run(capture_stderr=True)
    )
except ffmpeg.Error as e:
    print('FFmpeg error:')
    print(e.stderr.decode())
except FileNotFoundError:
    print('FFmpeg binary not found. Install with: brew install ffmpeg')
```

---

## 12. Comparison with subprocess FFmpeg Calls

### When to Use ffmpeg-python

- Complex filter graphs with multiple inputs/outputs
- Building dynamic pipelines in code
- When you need to read/write frames via pipes (numpy integration)
- Readable, maintainable code

### When to Use subprocess

- Simple one-off commands
- Using very new FFmpeg features not yet wrapped
- When you need full control over the command

### subprocess Equivalent

```python
import subprocess

# ffmpeg-python:
ffmpeg.input('in.mp4').hflip().output('out.mp4').run()

# subprocess equivalent:
subprocess.run([
    'ffmpeg', '-i', 'in.mp4',
    '-vf', 'hflip',
    'out.mp4', '-y'
], check=True)
```

### Hybrid Approach

```python
# Use ffmpeg-python to build the command, run with subprocess
import ffmpeg
import subprocess

cmd = (
    ffmpeg
    .input('in.mp4')
    .filter_('eq', brightness=0.1)
    .output('out.mp4')
    .compile()
)

print(f"Running: {' '.join(cmd)}")
subprocess.run(cmd, check=True)
```
