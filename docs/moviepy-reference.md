# MoviePy Video Editing Reference

> **Package:** moviepy 2.2.1
> **Import:** `from moviepy import *` or import specific classes
> **Purpose:** High-level video editing, compositing, effects, and rendering
> **Dependencies:** ffmpeg (must be in PATH), numpy, Pillow, proglog
> **Note:** MoviePy v2.0+ has breaking changes from v1.x. This doc covers the v2.x API.

---

## Table of Contents

1. [Clip Types and Loading](#1-clip-types-and-loading)
2. [Clip Modification and Effects](#2-clip-modification-and-effects)
3. [Built-in Video Effects (vfx)](#3-built-in-video-effects-vfx)
4. [Built-in Audio Effects (afx)](#4-built-in-audio-effects-afx)
5. [Custom Effects and Transforms](#5-custom-effects-and-transforms)
6. [Compositing and Combining Clips](#6-compositing-and-combining-clips)
7. [Audio Handling](#7-audio-handling)
8. [Rendering and Output](#8-rendering-and-output)
9. [Text and Titling](#9-text-and-titling)
10. [Time Formats and Utilities](#10-time-formats-and-utilities)
11. [Performance Tips](#11-performance-tips)
12. [v2.x API Changes from v1.x](#12-v2x-api-changes-from-v1x)

---

## 1. Clip Types and Loading

### VideoFileClip - Load a Video File

```python
from moviepy import VideoFileClip

clip = VideoFileClip("input.mp4")

# Properties
print(clip.duration)       # Duration in seconds
print(clip.fps)            # Frames per second
print(clip.size)           # (width, height) tuple
print(clip.w, clip.h)      # Width and height individually

# Trim on load
clip = VideoFileClip("input.mp4").subclipped(0.5, 10)  # 0.5s to 10s
```

### ImageClip - Static Image as Video

```python
from moviepy import ImageClip

# From file
clip = ImageClip("photo.png")

# From numpy array (H x W x 3, uint8)
import numpy as np
array = np.zeros((480, 640, 3), dtype=np.uint8)
array[:, :, 0] = 255  # All red
clip = ImageClip(array)

# Must set duration for rendering
clip = clip.with_duration(5)  # 5 seconds
```

### ColorClip - Solid Color

```python
from moviepy import ColorClip

# (width, height), (R, G, B)
background = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=10)
red_bg = ColorClip(size=(640, 480), color=(255, 0, 0), duration=5)
```

### TextClip - Text Rendering

```python
from moviepy import TextClip

txt = TextClip(
    font="./path/to/font.ttf",    # Required: path to TTF font file
    text="Hello World!",
    font_size=70,
    color="#FFFFFF",                # Text color
    bg_color="transparent",        # Background color
    stroke_color="black",          # Outline color
    stroke_width=2,                # Outline width
    duration=3
)
```

### ImageSequenceClip - From Image Sequence

```python
from moviepy import ImageSequenceClip

# From list of file paths
clip = ImageSequenceClip(["frame001.png", "frame002.png", "frame003.png"], fps=24)

# From directory (reads all images in order)
clip = ImageSequenceClip("./frames_directory/", fps=30)

# With custom durations per image
clip = ImageSequenceClip(
    ["img1.jpg", "img2.jpg", "img3.jpg"],
    durations=[1.5, 2.0, 1.0]  # seconds each
)
```

### VideoClip - Custom Frame Function

```python
from moviepy import VideoClip
import numpy as np

def make_frame(t):
    """Return HxWx3 numpy array for time t."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    x = int(t * 100) % 640
    frame[:, x:x+10, :] = 255  # Moving white bar
    return frame

clip = VideoClip(make_frame, duration=5)
clip.write_videofile("custom.mp4", fps=24)
```

### DataVideoClip - From Dataset

```python
from moviepy import DataVideoClip

data = list(range(100))  # Your dataset

def data_to_frame(d):
    """Convert a data point to a frame array."""
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[:, :d*2, 1] = 255  # Green bar growing with data
    return frame

clip = DataVideoClip(data=data, data_to_frame=data_to_frame, fps=10)
```

### AudioFileClip - Load Audio

```python
from moviepy import AudioFileClip

audio = AudioFileClip("music.mp3")
audio = AudioFileClip("video.mp4")  # Extract audio from video
```

### AudioClip - Custom Audio

```python
from moviepy import AudioClip
import numpy as np

def make_audio(t):
    """Return audio sample(s) at time t."""
    return np.sin(440 * 2 * np.pi * t)  # 440Hz sine wave

audio = AudioClip(frame_function=make_audio, duration=3, fps=44100)
```

### Resource Management

```python
# Context manager (recommended for memory management)
with VideoFileClip("input.mp4") as clip:
    clip.subclipped(0, 5).write_videofile("output.mp4")
# Automatically calls clip.close()

# Manual close
clip = VideoFileClip("input.mp4")
# ... process ...
clip.close()
```

---

## 2. Clip Modification and Effects

### Core Principle: Out-of-Place Modification

MoviePy never modifies clips in place. All operations return a NEW modified copy.

```python
# WRONG - discards the result
clip.with_volume_scaled(0.5)

# RIGHT - assign the result
clip = clip.with_volume_scaled(0.5)
```

### with_* Methods (Property Modification)

```python
# Set duration
clip = clip.with_duration(10)

# Set start time (for compositing)
clip = clip.with_start(2.5)

# Set end time
clip = clip.with_end(8.0)

# Set FPS
clip = clip.with_fps(30)

# Remove audio
clip = clip.without_audio()

# Replace audio
clip = clip.with_audio(audio_clip)

# Set volume
clip = clip.with_volume_scaled(0.5)  # 50% volume

# Set mask
clip = clip.with_mask(mask_clip)

# Set position (for compositing)
clip = clip.with_position(("center", "center"))
clip = clip.with_position((100, 50))  # (left, top) in pixels
clip = clip.with_position((0.5, 0.5), relative=True)  # relative to parent
clip = clip.with_position(lambda t: (100 + t * 30, 50))  # animated position
```

### Shortcut Methods

```python
# Trim/cut
clip = clip.subclipped(start_time, end_time)
clip = clip.subclipped(1, 5)        # 1s to 5s
clip = clip.subclipped(1, -1)       # 1s to 1s before end

# Cut out a section
clip = clip.with_section_cut_out(3, 5)  # Remove 3s-5s

# Resize
clip = clip.resized(width=640)          # Resize by width
clip = clip.resized(height=480)         # Resize by height
clip = clip.resized((640, 480))         # Exact size
clip = clip.resized(0.5)               # Half size

# Crop
clip = clip.cropped(x1=100, y1=50, x2=500, y2=400)

# Rotate
clip = clip.rotated(90)               # 90 degrees counterclockwise
```

### Applying Effects

```python
from moviepy import vfx, afx

# Single effect
clip = clip.with_effects([vfx.MultiplySpeed(2)])

# Multiple effects at once
clip = clip.with_effects([
    vfx.Resize(width=640),
    vfx.MultiplySpeed(1.5),
    vfx.FadeIn(1),
    vfx.FadeOut(1),
    afx.MultiplyVolume(0.8)
])
```

---

## 3. Built-in Video Effects (vfx)

### All Available Video Effects

```python
from moviepy import vfx
```

| Effect | Constructor | Description |
|--------|-------------|-------------|
| **AccelDecel** | `AccelDecel(new_duration=None)` | Accelerates then decelerates playback. Good for GIFs. |
| **BlackAndWhite** | `BlackAndWhite(RGB=None)` | Desaturates to black and white. Optional RGB weights. |
| **Blink** | `Blink(duration_on, duration_off)` | Makes clip blink on/off. |
| **Crop** | `Crop(x1=None, y1=None, x2=None, y2=None, width=None, height=None, x_center=None, y_center=None)` | Crops to rectangular region. |
| **CrossFadeIn** | `CrossFadeIn(duration)` | Progressive opacity fade-in (for compositing). |
| **CrossFadeOut** | `CrossFadeOut(duration)` | Progressive opacity fade-out (for compositing). |
| **EvenSize** | `EvenSize()` | Crops 1px if needed to make dimensions even (required by some codecs). |
| **FadeIn** | `FadeIn(duration, initial_color=None)` | Fade in from a color (default black). |
| **FadeOut** | `FadeOut(duration, final_color=None)` | Fade out to a color (default black). |
| **Freeze** | `Freeze(t=None, freeze_duration=None, total_duration=None, padding_end=0)` | Freezes frame at time t. |
| **FreezeRegion** | `FreezeRegion(t=None, region=None, outside_region=None, mask=None)` | Freezes part of frame while rest plays. |
| **GammaCorrection** | `GammaCorrection(gamma)` | Gamma correction (>1 = brighter, <1 = darker). |
| **HeadBlur** | `HeadBlur(fx, fy, radius, intensity=None)` | Blurs a moving circular region (face blur). |
| **InvertColors** | `InvertColors()` | Inverts all colors (negative). |
| **Loop** | `Loop(n=None, duration=None)` | Loops clip n times or for duration seconds. |
| **LumContrast** | `LumContrast(lum=0, contrast=0, contrast_threshold=127)` | Luminosity and contrast adjustment. |
| **MakeLoopable** | `MakeLoopable(overlap_duration)` | Cross-fades end into beginning for seamless loop. |
| **Margin** | `Margin(margin_size=None, left=0, right=0, top=0, bottom=0, color=(0,0,0), opacity=1.0)` | Adds colored margin/border around frame. |
| **MaskColor** | `MaskColor(color=None, threshold=None, stiffness=None)` | Creates transparency where clip matches color (chroma key). |
| **MasksAnd** | `MasksAnd(other_clip)` | Logical AND between two mask clips (minimum). |
| **MasksOr** | `MasksOr(other_clip)` | Logical OR between two mask clips (maximum). |
| **MirrorX** | `MirrorX()` | Horizontal flip. |
| **MirrorY** | `MirrorY()` | Vertical flip. |
| **MultiplyColor** | `MultiplyColor(factor)` | Multiply all pixel values by factor. |
| **MultiplySpeed** | `MultiplySpeed(factor)` | Change playback speed (2 = 2x faster, 0.5 = half speed). |
| **Painting** | `Painting(saturation=1.4, black=0.006)` | Oil painting effect. |
| **Resize** | `Resize(new_size=None, height=None, width=None, apply_to_mask=True)` | Resize clip. |
| **Rotate** | `Rotate(angle, unit='deg', resample='bicubic', expand=True, bg_color=(0,0,0))` | Rotate by angle. Supports animated angle via function. |
| **Scroll** | `Scroll(w=None, h=None, x_speed=0, y_speed=0, x_start=0, y_start=0, apply_to='mask')` | Scrolling window effect. |
| **SlideIn** | `SlideIn(duration, side)` | Clip slides in from 'left', 'right', 'top', or 'bottom'. |
| **SlideOut** | `SlideOut(duration, side)` | Clip slides out to 'left', 'right', 'top', or 'bottom'. |
| **SuperSample** | `SuperSample(d, n_frames)` | Anti-aliased frame by averaging n_frames over d seconds. |
| **TimeMirror** | `TimeMirror()` | Plays clip backwards (reverses time). |
| **TimeSymmetrize** | `TimeSymmetrize()` | Plays forward then backward. |

### Usage Examples

```python
from moviepy import VideoFileClip, vfx

clip = VideoFileClip("input.mp4")

# Speed up 2x
fast = clip.with_effects([vfx.MultiplySpeed(2)])

# Fade in and out
faded = clip.with_effects([vfx.FadeIn(1), vfx.FadeOut(1)])

# Black and white + invert
artsy = clip.with_effects([vfx.BlackAndWhite(), vfx.InvertColors()])

# Loop 3 times
looped = clip.with_effects([vfx.Loop(n=3)])

# Make seamlessly loopable
loopable = clip.with_effects([vfx.MakeLoopable(0.5)])

# Play backwards
reversed_clip = clip.with_effects([vfx.TimeMirror()])

# Forward then backward
boomerang = clip.with_effects([vfx.TimeSymmetrize()])

# Rotate animation (spinning)
spinning = clip.with_effects([vfx.Rotate(lambda t: 360 * t / clip.duration)])

# Painting effect
painted = clip.with_effects([vfx.Painting(saturation=1.6, black=0.01)])

# Freeze a moment
frozen = clip.with_effects([vfx.Freeze(t=2, freeze_duration=3)])
```

---

## 4. Built-in Audio Effects (afx)

```python
from moviepy import afx
```

| Effect | Constructor | Description |
|--------|-------------|-------------|
| **AudioDelay** | `AudioDelay(offset, decay=1, n_repeats=8)` | Echo/delay effect. Repeats audio at intervals with decay. |
| **AudioFadeIn** | `AudioFadeIn(duration)` | Gradual audio fade-in at clip start. |
| **AudioFadeOut** | `AudioFadeOut(duration)` | Gradual audio fade-out at clip end. |
| **AudioLoop** | `AudioLoop(n_loops=None, duration=None)` | Loop audio n times or for duration. |
| **AudioNormalize** | `AudioNormalize()` | Normalize volume to 0dB peak. |
| **MultiplyStereoVolume** | `MultiplyStereoVolume(left=1, right=1)` | Independent left/right channel volume. |
| **MultiplyVolume** | `MultiplyVolume(factor)` | Multiply volume by factor (0.5 = half, 2 = double). |

### Audio Effects Examples

```python
from moviepy import VideoFileClip, afx

clip = VideoFileClip("input.mp4")

# Fade audio in and out
clip = clip.with_effects([afx.AudioFadeIn(2), afx.AudioFadeOut(2)])

# Echo effect
clip = clip.with_effects([afx.AudioDelay(offset=0.3, decay=0.6, n_repeats=4)])

# Normalize audio
clip = clip.with_effects([afx.AudioNormalize()])

# Pan left
clip = clip.with_effects([afx.MultiplyStereoVolume(left=1, right=0)])

# Reduce volume
clip = clip.with_effects([afx.MultiplyVolume(0.3)])
```

---

## 5. Custom Effects and Transforms

### image_transform() - Modify Frames

Process each frame as a numpy array. The callback receives (H, W, 3) uint8 array.

```python
# Invert colors
clip = clip.image_transform(lambda img: 255 - img)

# Swap color channels
def swap_channels(image):
    return image[:, :, [2, 1, 0]]  # BGR swap (if working with OpenCV frames)
clip = clip.image_transform(swap_channels)

# Pixelate effect
def pixelate(image, block_size=10):
    h, w = image.shape[:2]
    small = cv.resize(image, (w // block_size, h // block_size),
                      interpolation=cv.INTER_NEAREST)
    return cv.resize(small, (w, h), interpolation=cv.INTER_NEAREST)
clip = clip.image_transform(lambda img: pixelate(img, 8))
```

### time_transform() - Warp Playback Time

```python
# 3x speed (same as MultiplySpeed(3))
clip = clip.time_transform(lambda t: t * 3)

# Slow motion (half speed)
clip = clip.time_transform(lambda t: t / 2)

# Bounce/ping-pong
duration = clip.duration
clip = clip.time_transform(lambda t: duration - abs(t - duration))

# Stutter effect (repeat every 0.5s)
clip = clip.time_transform(lambda t: (t % 0.5))
```

### transform() - Combined Time + Frame Access

```python
# Scrolling crop effect
def scroll(get_frame, t):
    frame = get_frame(t)
    y = int(t * 50)  # Scroll 50px per second
    return frame[y:y + 360, :]

scrolled = clip.transform(scroll)

# Frame echo (mix current with past frame)
def frame_echo(get_frame, t, delay=0.1, mix=0.5):
    current = get_frame(t).astype(float)
    past = get_frame(max(0, t - delay)).astype(float)
    return (current * (1 - mix) + past * mix).astype('uint8')

echoed = clip.transform(frame_echo)
```

---

## 6. Compositing and Combining Clips

### concatenate_videoclips - Sequential Playback

```python
from moviepy import VideoFileClip, concatenate_videoclips

clip1 = VideoFileClip("part1.mp4")
clip2 = VideoFileClip("part2.mp4")
clip3 = VideoFileClip("part3.mp4")

# Simple concatenation
final = concatenate_videoclips([clip1, clip2, clip3])

# With transitions (method="compose" allows different sizes)
final = concatenate_videoclips([clip1, clip2, clip3], method="compose")

# With padding between clips
final = concatenate_videoclips([clip1, clip2], padding=-1)  # 1s overlap
```

### CompositeVideoClip - Layered Composition

```python
from moviepy import CompositeVideoClip, VideoFileClip, ColorClip

background = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=10)
video1 = VideoFileClip("clip1.mp4").resized(width=640)
video2 = VideoFileClip("clip2.mp4").resized(width=640)

# Stack clips (drawn in order, last on top)
final = CompositeVideoClip([
    background,
    video1.with_position((50, 50)),
    video2.with_position((700, 50))
])
```

### Positioning

```python
# Pixel coordinates (left, top)
clip = clip.with_position((100, 200))

# Named positions
clip = clip.with_position("center")
clip = clip.with_position(("center", "bottom"))
clip = clip.with_position(("right", "top"))

# Relative (0-1 range)
clip = clip.with_position((0.5, 0.5), relative=True)

# Animated position (function of time)
clip = clip.with_position(lambda t: (100 + t * 50, 200))
clip = clip.with_position(lambda t: ("center", 50 + t * 30))
```

### Timing Control

```python
# Set when clip starts playing (in composite timeline)
clip1 = clip1.with_start(0)
clip2 = clip2.with_start(3)    # Start at 3 seconds
clip3 = clip3.with_start(clip2.end)  # Start after clip2

# Set explicit end
clip = clip.with_end(10)

# Set duration
clip = clip.with_duration(5)
```

### clips_array - Grid Layout

```python
from moviepy import clips_array, VideoFileClip

clip1 = VideoFileClip("a.mp4").resized(width=480)
clip2 = VideoFileClip("b.mp4").resized(width=480)
clip3 = VideoFileClip("c.mp4").resized(width=480)
clip4 = VideoFileClip("d.mp4").resized(width=480)

# 2x2 grid
final = clips_array([
    [clip1, clip2],
    [clip3, clip4]
])
```

### Transitions

```python
from moviepy import vfx

clip1 = VideoFileClip("a.mp4").with_duration(5)
clip2 = VideoFileClip("b.mp4").with_effects([vfx.CrossFadeIn(1)])

# Overlap the crossfade
clip2 = clip2.with_start(clip1.end - 1)

final = CompositeVideoClip([clip1, clip2])
```

---

## 7. Audio Handling

### Loading Audio

```python
from moviepy import AudioFileClip, VideoFileClip

# From audio file
audio = AudioFileClip("song.mp3")
audio = AudioFileClip("sound.wav")

# From video file (extract audio track)
audio = AudioFileClip("video.mp4")

# Or get audio from a video clip
clip = VideoFileClip("video.mp4")
audio = clip.audio
```

### Attaching Audio to Video

```python
from moviepy import VideoFileClip, AudioFileClip

video = VideoFileClip("silent_video.mp4")
music = AudioFileClip("background.mp3")

# Set audio (trims audio to video duration automatically)
final = video.with_audio(music)

# Remove audio
silent = video.without_audio()
```

### Audio Volume

```python
from moviepy import afx

# Constant volume change
clip = clip.with_effects([afx.MultiplyVolume(0.5)])

# Stereo control
clip = clip.with_effects([afx.MultiplyStereoVolume(left=1, right=0.3)])

# Using with_volume_scaled shortcut
clip = clip.with_volume_scaled(0.5)
```

### Mixing Multiple Audio Tracks

```python
from moviepy import CompositeAudioClip, AudioFileClip

voice = AudioFileClip("voice.wav")
music = AudioFileClip("music.mp3").with_effects([afx.MultiplyVolume(0.3)])
sfx = AudioFileClip("explosion.wav").with_start(5)

mixed = CompositeAudioClip([voice, music, sfx])

# Concatenate audio
from moviepy import concatenate_audioclips
combined = concatenate_audioclips([audio1, audio2, audio3])
```

---

## 8. Rendering and Output

### write_videofile - Main Output Method

```python
clip.write_videofile("output.mp4")

# Full parameter control
clip.write_videofile(
    "output.mp4",
    fps=24,                        # Frames per second
    codec="libx264",               # Video codec
    audio_codec="aac",             # Audio codec
    bitrate="5000k",               # Video bitrate
    audio_bitrate="192k",          # Audio bitrate
    preset="medium",               # Encoding speed preset
    threads=4,                     # Parallel threads
    ffmpeg_params=["-crf", "18"],  # Custom ffmpeg flags
    logger="bar"                   # Progress display ("bar" or None)
)
```

### Common Codec/Format Combinations

| Extension | Video Codec | Audio Codec | Notes |
|-----------|-------------|-------------|-------|
| `.mp4` | `libx264` | `aac` | Most compatible |
| `.webm` | `libvpx-vp9` | `libvorbis` | Web-optimized |
| `.ogv` | `libtheora` | `libvorbis` | Open format |
| `.avi` | `mpeg4` | `libmp3lame` | Legacy |

### Encoding Presets (libx264)

| Preset | Speed | File Size |
|--------|-------|-----------|
| `ultrafast` | Fastest | Largest |
| `fast` | Fast | Large |
| `medium` | Balanced | Medium |
| `slow` | Slow | Small |
| `veryslow` | Slowest | Smallest |

### Other Output Methods

```python
# Write audio only
clip.audio.write_audiofile("output.mp3")
clip.audio.write_audiofile("output.wav", fps=44100)

# Write GIF
clip.write_gif("output.gif", fps=15)

# Write image sequence
clip.write_images_sequence("frames/frame%04d.png", fps=24)

# Save single frame
clip.save_frame("thumbnail.png", t=1.5)  # Frame at 1.5 seconds
```

### Important: Duration Must Be Set

```python
# Clips without inherent duration (ImageClip, ColorClip, etc.)
# MUST have duration set before writing
clip = ImageClip("photo.png").with_duration(5)
clip.write_videofile("slideshow.mp4", fps=24)
```

---

## 9. Text and Titling

### Basic Text

```python
from moviepy import TextClip, CompositeVideoClip, ColorClip

txt = TextClip(
    font="./Arial.ttf",           # Path to .ttf font file (REQUIRED in v2)
    text="Hello World",
    font_size=70,
    color="white",
    duration=3
)

# Centered on background
bg = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=3)
final = CompositeVideoClip([bg, txt.with_position("center")])
```

### Styled Text

```python
txt = TextClip(
    font="./Bold.ttf",
    text="GLITCH ART",
    font_size=100,
    color="#FF0000",
    bg_color="transparent",
    stroke_color="white",
    stroke_width=3,
    duration=5
)
```

### Animated Text

```python
# Scrolling text
txt = TextClip(font="./font.ttf", text="Credits...", font_size=40,
               color="white", duration=10)
txt = txt.with_position(lambda t: ("center", 1080 - t * 100))

# Fade in text
from moviepy import vfx
txt = txt.with_effects([vfx.FadeIn(1), vfx.FadeOut(1)])
```

### Title Card Pattern

```python
from moviepy import TextClip, ColorClip, CompositeVideoClip, vfx

def make_title_card(text, duration=3, font_path="./font.ttf"):
    bg = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=duration)

    title = TextClip(
        font=font_path,
        text=text,
        font_size=80,
        color="white",
        duration=duration
    ).with_position("center")

    card = CompositeVideoClip([bg, title])
    card = card.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])
    return card
```

---

## 10. Time Formats and Utilities

### Accepted Time Formats

MoviePy accepts time in multiple formats:

```python
# Float seconds
clip.subclipped(1.5, 10.0)

# Tuple (minutes, seconds) or (hours, minutes, seconds)
clip.subclipped((0, 30), (1, 15))     # 0:30 to 1:15
clip.subclipped((0, 0, 30), (0, 1, 15))  # Same

# String
clip.subclipped('00:00:30', '00:01:15')
clip.subclipped('00:00:30.50', '00:01:15.75')

# Negative (from end)
clip.subclipped(0, -2)   # From start to 2 seconds before end
```

### Useful Clip Properties

```python
clip.duration      # Total duration in seconds
clip.start         # Start time (in composite context)
clip.end           # End time (in composite context)
clip.fps           # Frames per second
clip.size          # (width, height)
clip.w             # Width
clip.h             # Height
clip.aspect_ratio  # Width/height ratio
```

---

## 11. Performance Tips

1. **Effects are lazy** - Only the first frame is computed immediately. Other frames render on demand during `write_videofile()`.

2. **Use `preset="ultrafast"`** for test renders, `"medium"` or `"slow"` for final output.

3. **Lower FPS for previews** - Use `fps=12` for quick checks.

4. **Close clips** when done - Use context managers or call `clip.close()`.

5. **Resize early** - Apply `Resize` before other effects to process fewer pixels.

6. **Set `logger=None`** to suppress progress bar (slightly faster for batch processing).

7. **Use `threads`** parameter for parallel encoding.

8. **Avoid unnecessary copies** - Chain operations rather than creating intermediate clips.

---

## 12. v2.x API Changes from v1.x

### Key Breaking Changes

| v1.x (Old) | v2.x (New) | Notes |
|-------------|------------|-------|
| `clip.subclip(t1, t2)` | `clip.subclipped(t1, t2)` | Past tense naming |
| `clip.set_duration(d)` | `clip.with_duration(d)` | `with_` prefix |
| `clip.set_start(t)` | `clip.with_start(t)` | `with_` prefix |
| `clip.set_position(p)` | `clip.with_position(p)` | `with_` prefix |
| `clip.set_audio(a)` | `clip.with_audio(a)` | `with_` prefix |
| `clip.resize(s)` | `clip.resized(s)` | Past tense |
| `clip.crop(...)` | `clip.cropped(...)` | Past tense |
| `clip.rotate(a)` | `clip.rotated(a)` | Past tense |
| `clip.fx(vfx.effect)` | `clip.with_effects([effect()])` | Effects are instantiated objects |
| `clip.fl_image(func)` | `clip.image_transform(func)` | Renamed |
| `clip.fl_time(func)` | `clip.time_transform(func)` | Renamed |
| `clip.fl(func)` | `clip.transform(func)` | Renamed |
| `vfx.speedx(factor)` | `vfx.MultiplySpeed(factor)` | PascalCase class |
| `vfx.resize(s)` | `vfx.Resize(s)` | PascalCase class |
| `vfx.fadein(d)` | `vfx.FadeIn(d)` | PascalCase class |
| `vfx.time_mirror` | `vfx.TimeMirror()` | PascalCase class |
| `TextClip("text", fontsize=50)` | `TextClip(font="path.ttf", text="text", font_size=50)` | Font path required, param renamed |

### Import Changes

```python
# v1.x
from moviepy.editor import *

# v2.x
from moviepy import *
# or specific imports:
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip
from moviepy import vfx, afx
```
