# Datamosh Techniques Deep Dive

> Complete reference for datamoshing: frame manipulation, tools, and workflows.
> Last updated: 2026-02-07

---

## Table of Contents

1. [Video Compression Fundamentals](#video-compression-fundamentals)
2. [Classic Datamosh: I-Frame Removal](#classic-datamosh-i-frame-removal)
3. [Bloom/Melt Effect: P-Frame Duplication](#bloommelt-effect-p-frame-duplication)
4. [Tools: Avidemux](#tools-avidemux)
5. [Tools: FFmpeg GOP Manipulation](#tools-ffmpeg-gop-manipulation)
6. [Python-Based Datamosh](#python-based-datamosh)
7. [Moshpit Command-Line Tool](#moshpit-command-line-tool)
8. [Controlling Datamosh Intensity](#controlling-datamosh-intensity)
9. [Common Artifacts and How to Leverage Them](#common-artifacts-and-how-to-leverage-them)
10. [Integration with FFmpeg Pipeline](#integration-with-ffmpeg-pipeline)
11. [Alternative Techniques](#alternative-techniques)
12. [Resources and Links](#resources-and-links)

---

## Video Compression Fundamentals

### How Video Compression Works

Modern video codecs (H.264, H.265, VP9, AV1) do not store every frame as a complete picture. Instead, they exploit temporal redundancy -- the fact that consecutive frames are usually very similar.

### Frame Types

| Frame Type | Full Name | Description | Data Size |
|------------|-----------|-------------|-----------|
| **I-frame** | Intra-coded frame | Complete, self-contained picture. Can be decoded independently. | Large |
| **P-frame** | Predicted frame | Stores only the **differences** from the previous frame. References backward. | Small |
| **B-frame** | Bi-predictive frame | Stores differences from **both** previous and next frames. References both directions. | Smallest |

### GOP (Group of Pictures)

A GOP is a sequence of frames starting with an I-frame, followed by P-frames and B-frames:

```
Typical GOP structure:
I  P  B  B  P  B  B  P  B  B  I  P  B  B  P ...
^                              ^
|                              |
Keyframe (complete image)      Next keyframe
```

**GOP Size** = number of frames between I-frames. Larger GOP = smaller file but harder to seek/edit.

### IDR Frames (H.264 Specific)

In H.264, I-frames can be either:
- **IDR (Instantaneous Decoding Refresh)**: Forces a clean break. No frame after it can reference anything before it.
- **Non-IDR I-frame**: A complete picture, but subsequent frames might still reference earlier frames.

For datamoshing, you typically work with IDR frames (NAL unit type 5).

### NAL Units (H.264 Stream Structure)

H.264 video is organized into NAL (Network Abstraction Layer) units:

| NAL Type | Meaning |
|----------|---------|
| 1 | Non-IDR slice (P-frame or B-frame data) |
| 5 | IDR slice (I-frame / keyframe data) |
| 6 | SEI (Supplemental Enhancement Info) |
| 7 | SPS (Sequence Parameter Set) |
| 8 | PPS (Picture Parameter Set) |

Datamoshing algorithms parse NAL headers to identify and selectively remove type-5 units (I-frames).

### Why Datamoshing Works

When you remove an I-frame:
1. The decoder has no new reference image
2. P-frames continue applying their motion vectors
3. But they apply to the **wrong** reference image (from the previous scene)
4. Result: motion from the new scene warps pixels from the old scene

---

## Classic Datamosh: I-Frame Removal

### How It Works

I-frame removal is the "transition-style" datamosh. It creates the effect where pixels from a previous scene are morphed by motion vectors from a new scene.

```
Before I-frame removal:
Scene A (I) (P) (P) (P) | Scene B (I) (P) (P) (P)
                           ^
                           I-frame = clean transition

After I-frame removal:
Scene A (I) (P) (P) (P) Scene B (P) (P) (P)
                         ^
                         No I-frame = Scene B's motion applied to Scene A's pixels
```

### Best Practices for I-Frame Removal

1. **Best at scene cuts**: The most dramatic effects happen when removing I-frames at the boundary between two different scenes
2. **Movement matters**: The effect is most visible when the new scene has significant motion (camera movement, subject movement)
3. **Scene similarity**: If both scenes are very similar, the effect will be subtle. Contrasting scenes produce the most dramatic results
4. **Multiple removals**: You can remove I-frames at multiple scene boundaries for a continuous "never-resolving" effect

### Manual Process

1. Identify I-frame positions using FFprobe or Avidemux
2. Re-encode with controlled GOP to minimize I-frames
3. Remove the target I-frame(s)
4. Re-encode the result for playback compatibility

---

## Bloom/Melt Effect: P-Frame Duplication

### How It Works

Instead of removing I-frames, this technique **duplicates P-frames**. The repeated P-frames keep applying the same motion vectors over and over, creating a "melting" or "blooming" effect where the image gradually morphs in one direction.

```
Original:
(I) (P1) (P2) (P3) (P4) (I) ...

After P-frame duplication (P2 repeated):
(I) (P1) (P2) (P2) (P2) (P2) (P2) (P2) (P3) (P4) (I) ...
              ^    repeating the same motion vector
```

### Characteristics

- **Gradual distortion**: Unlike I-frame removal (which is a sudden shift), P-frame duplication creates a slow, organic distortion
- **Direction of melt**: The visual "melts" in the direction of the motion vectors in the duplicated P-frame
- **Duration control**: More copies = longer melt effect
- **Often paired with I-frame removal** for complex pieces

### Best P-Frames to Duplicate

Look for P-frames with:
- Significant motion (camera pans, subject movement)
- Interesting directional movement
- The melt will follow the motion direction captured in that frame

---

## Tools: Avidemux

### Overview

Avidemux is a free, cross-platform video editor commonly used for datamoshing. **Important: Version 2.5.6 works best for datamoshing.** Newer versions (2.7+) require a different workflow.

### Avidemux 2.7.0 Workflow

**Step 1: Import and Re-encode**

1. Open source video in Avidemux 2.7.0
2. Set Video Output to **"Mpeg4 AVC (x264)"**
3. Click **Configure** > **Frames** tab:
   - Maximum Consecutive B-frames: **0**
   - GOP-Size Minimum: **0**
   - GOP-Size Maximum: **999**
4. Keep Audio Output as **Copy**
5. Set Output Format to **Mkv Muxer**
6. Save as a new file (e.g., `reencoded.mkv`)

**Step 2: Open Re-encoded File**

Close and reopen the newly created MKV file.

**Step 3: P-Frame Manipulation (Bloom/Melt)**

1. Use the Navigation toolbar to find P-frames with significant movement
2. The frame type indicator shows I, P, or B for the current frame
3. Navigate frame-by-frame with arrow keys
4. Set **Start Marker** (A button) at a P-frame position
5. Move forward one frame, set **End Marker** (B button)
6. Copy the P-frame (Ctrl+C)
7. Paste it multiple times (Ctrl+V, Ctrl+V, Ctrl+V...)
8. More repetitions = more pronounced bloom/melt effect

**Step 4: I-Frame Removal**

1. Navigate to an I-frame (scene boundary)
2. Set markers around just that I-frame
3. Delete it (removes the clean scene transition)

**Step 5: Export**

1. Reset Start/End markers to encompass entire timeline
2. Set Video Output to **Copy** (do NOT re-encode)
3. Save the file
4. Ignore keyframe warnings (click Yes)
5. Open result in VLC to verify

### Tips for Avidemux

- **Try 3 P-frames at a time** rather than single frames for copy/paste
- **Experiment with different source videos** if results are unpredictable
- **"Bake" the result** in a video editor to improve compatibility
- **Avoid excessive pasting** -- it can cause slowdown and crashes
- Keep the first I-frame in the file (needed for proper video startup)

---

## Tools: FFmpeg GOP Manipulation

### Preparing Video for Datamoshing

Before datamoshing, re-encode with controlled GOP settings:

```bash
# Re-encode with minimal I-frames and no B-frames
ffmpeg -i input.mp4 \
    -c:v libx264 \
    -g 999 \
    -keyint_min 999 \
    -bf 0 \
    -sc_threshold 0 \
    -c:a copy \
    output_prepared.mp4
```

**Parameter Explanation:**

| Parameter | Effect |
|-----------|--------|
| `-g 999` | Maximum GOP size (frames between keyframes). 999 = very few I-frames |
| `-keyint_min 999` | Minimum keyframe interval. Prevents extra I-frames |
| `-bf 0` | No B-frames (simplifies frame structure to I and P only) |
| `-sc_threshold 0` | Disable scene change detection (prevents automatic I-frame insertion at cuts) |

### Analyzing Frame Types

```bash
# List all frame types in a video
ffprobe -v quiet -print_format json -show_entries \
    "frame=coded_picture_number,pict_type" \
    -select_streams v:0 input.mp4

# Simpler output (just frame types)
ffprobe -v quiet -select_streams v:0 \
    -show_entries frame=pict_type \
    -of csv=p=0 input.mp4
```

### Visualizing Motion Vectors

```bash
# Display motion vectors in real-time
ffplay -flags2 +export_mvs input.mp4 \
    -vf codecview=mv=pf+bf+bb

# Save motion vector visualization to file
ffmpeg -flags2 +export_mvs -i input.mp4 \
    -vf codecview=mv=pf+bf+bb \
    -c:v libx264 motion_vectors.mp4
```

### Advanced FFmpeg Settings for Datamosh Source Material

```bash
# Minimal motion estimation (creates more visible artifacts)
ffmpeg -i input.mp4 \
    -c:v libx264 \
    -g 20 \
    -sc_threshold 0 \
    -me_method zero \
    -bf 0 \
    output.mp4

# Force specific keyframe positions
ffmpeg -i input.mp4 \
    -c:v libx264 \
    -force_key_frames "expr:eq(n,0)" \
    -bf 0 \
    -sc_threshold 0 \
    output.mp4
```

### Converting to AVI (Required for Some Tools)

Many datamosh tools require AVI format (simpler container):

```bash
# Convert to AVI with Xvid codec (compatible with most datamosh tools)
ffmpeg -i input.mp4 \
    -c:v mpeg4 \
    -q:v 5 \
    -bf 0 \
    -g 999 \
    output.avi

# Convert to AVI with H.264 (for tools that support it)
ffmpeg -i input.mp4 \
    -c:v libx264 \
    -bf 0 \
    -g 999 \
    -sc_threshold 0 \
    output.avi
```

---

## Python-Based Datamosh

### tomato.py (P-Frame Manipulation)

`tomato.py` allows programmatic manipulation of P-frames in AVI files:

```python
# Basic usage pattern (requires tomato.py script)
# 1. Convert video to AVI
# 2. Use tomato.py to manipulate P-frames
# 3. Convert back to MP4

import subprocess

# Step 1: Prepare AVI
subprocess.run([
    "ffmpeg", "-i", "input.mp4",
    "-c:v", "mpeg4", "-bf", "0", "-g", "999",
    "-q:v", "5", "prepared.avi"
])

# Step 2: Run tomato.py (duplicates P-frames at specified positions)
# python tomato.py prepared.avi output.avi --repeat 5 --frame 30

# Step 3: Convert back
subprocess.run([
    "ffmpeg", "-i", "output.avi",
    "-c:v", "libx264", "-crf", "18",
    "final.mp4"
])
```

### Custom I-Frame Removal in Python

```python
def find_nal_units(data):
    """Find NAL unit boundaries in H.264 bitstream."""
    positions = []
    i = 0
    while i < len(data) - 3:
        # NAL units start with 0x00 0x00 0x01 or 0x00 0x00 0x00 0x01
        if data[i:i+3] == b'\x00\x00\x01':
            positions.append(i)
            i += 3
        elif data[i:i+4] == b'\x00\x00\x00\x01':
            positions.append(i)
            i += 4
        else:
            i += 1
    return positions

def get_nal_type(data, pos):
    """Get the NAL unit type (5 = IDR/I-frame, 1 = non-IDR/P-frame)."""
    # Skip start code
    if data[pos:pos+4] == b'\x00\x00\x00\x01':
        header_byte = data[pos + 4]
    else:
        header_byte = data[pos + 3]
    return header_byte & 0x1F

def remove_iframes(input_path, output_path, keep_first=True):
    """Remove I-frames from an H.264 bitstream.

    Args:
        input_path: Path to input .h264 raw bitstream
        output_path: Path to output .h264 raw bitstream
        keep_first: If True, keep the very first I-frame (required for decoding)
    """
    with open(input_path, "rb") as f:
        data = f.read()

    nal_positions = find_nal_units(data)
    output = bytearray()

    first_idr_found = False

    for i, pos in enumerate(nal_positions):
        # Determine end of this NAL unit
        if i + 1 < len(nal_positions):
            end = nal_positions[i + 1]
        else:
            end = len(data)

        nal_type = get_nal_type(data, pos)
        nal_data = data[pos:end]

        if nal_type == 5:  # IDR frame (I-frame)
            if keep_first and not first_idr_found:
                output.extend(nal_data)
                first_idr_found = True
                print(f"Keeping first I-frame at position {pos}")
            else:
                print(f"Removing I-frame at position {pos}")
                # Skip this NAL unit (don't add to output)
                continue
        else:
            # Keep all non-IDR NAL units (P-frames, B-frames, SPS, PPS, SEI)
            output.extend(nal_data)

    with open(output_path, "wb") as f:
        f.write(output)

    print(f"Done. Removed I-frames from {input_path} -> {output_path}")
```

### AVI-Based Datamosh (Simpler Approach)

AVI files have a simpler structure than MP4, making frame manipulation easier:

```python
import struct

def parse_avi_frames(filepath):
    """Parse AVI file to find video frame locations and types."""
    with open(filepath, "rb") as f:
        data = f.read()

    frames = []
    # Search for "00dc" chunks (video data in AVI)
    # and "01dc" for second video stream
    i = 0
    while i < len(data) - 8:
        chunk_id = data[i:i+4]
        if chunk_id in (b'00dc', b'01dc'):
            chunk_size = struct.unpack_from('<I', data, i + 4)[0]
            chunk_data = data[i+8:i+8+chunk_size]

            # Check if this is an I-frame (first bytes indicate frame type)
            is_iframe = False
            if len(chunk_data) > 4:
                # For MPEG-4 ASP: I-frames start with specific byte patterns
                # For Xvid: check VOP coding type
                if chunk_data[0:3] == b'\x00\x00\x01':
                    vop_type = (chunk_data[4] >> 6) & 0x03
                    is_iframe = (vop_type == 0)

            frames.append({
                'offset': i,
                'size': chunk_size,
                'is_iframe': is_iframe,
                'data': chunk_data
            })
            i += 8 + chunk_size
            # Align to word boundary
            if chunk_size % 2 == 1:
                i += 1
        else:
            i += 1

    return frames

def duplicate_pframe(filepath, output_path, frame_index, num_copies=10):
    """Duplicate a specific P-frame in an AVI file."""
    with open(filepath, "rb") as f:
        data = bytearray(f.read())

    frames = parse_avi_frames(filepath)

    if frame_index >= len(frames):
        print(f"Frame index {frame_index} out of range (max {len(frames)-1})")
        return

    target_frame = frames[frame_index]
    if target_frame['is_iframe']:
        print("Warning: Selected frame is an I-frame, not a P-frame")
        return

    # Get the raw frame data including chunk header
    frame_start = target_frame['offset']
    frame_end = frame_start + 8 + target_frame['size']
    frame_bytes = data[frame_start:frame_end]

    # Insert copies after the target frame
    insert_point = frame_end
    insertion = frame_bytes * num_copies

    output_data = data[:insert_point] + insertion + data[insert_point:]

    with open(output_path, "wb") as f:
        f.write(output_data)

    print(f"Duplicated frame {frame_index} x{num_copies}")
```

### automosh.py Pattern

Several open-source projects provide automated datamoshing:

```python
#!/usr/bin/env python3
"""Automated datamosh pipeline."""

import subprocess
import os
import sys

def automosh(input_video, output_video, effect="iframe_removal"):
    """
    Automated datamoshing pipeline.

    Args:
        input_video: Path to source video
        output_video: Path for datamoshed output
        effect: "iframe_removal" or "pframe_bloom"
    """
    temp_avi = "temp_prepared.avi"
    temp_moshed = "temp_moshed.avi"

    # Step 1: Convert to AVI with controlled encoding
    print("Step 1: Preparing video...")
    subprocess.run([
        "ffmpeg", "-y", "-i", input_video,
        "-c:v", "mpeg4",
        "-bf", "0",        # No B-frames
        "-g", "999",       # Minimal I-frames
        "-q:v", "5",       # Quality level
        "-sc_threshold", "0",  # No scene detection
        temp_avi
    ], check=True)

    # Step 2: Manipulate frames
    print(f"Step 2: Applying {effect}...")
    with open(temp_avi, "rb") as f:
        data = bytearray(f.read())

    if effect == "iframe_removal":
        data = remove_iframes_from_avi(data)
    elif effect == "pframe_bloom":
        data = bloom_pframes_in_avi(data, repeat_count=20)

    with open(temp_moshed, "wb") as f:
        f.write(data)

    # Step 3: Convert back to MP4
    print("Step 3: Converting to final format...")
    subprocess.run([
        "ffmpeg", "-y", "-i", temp_moshed,
        "-c:v", "libx264",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_video
    ], check=True)

    # Cleanup
    os.remove(temp_avi)
    os.remove(temp_moshed)

    print(f"Done! Output: {output_video}")

def remove_iframes_from_avi(data):
    """Remove I-frames from AVI data (keeping the first one)."""
    # Implementation depends on codec used
    # See parse_avi_frames() above
    pass

def bloom_pframes_in_avi(data, repeat_count=20):
    """Duplicate P-frames for bloom/melt effect."""
    # Implementation depends on codec used
    # See duplicate_pframe() above
    pass
```

### Related Python Projects

| Project | Language | URL |
|---------|----------|-----|
| **automosh** | Python | github.com/selftext/video-art |
| **Autodatamosh** | Perl | github.com/grampajoe/Autodatamosh |
| **Datamosh-python** | Python | github.com/amgadani/Datamosh-python |
| **aviglitch** | Ruby | github.com/ucnv/aviglitch |
| **node-aviglitch** | Node.js | github.com/fand/node-aviglitch |
| **moshy** | Ruby | github.com/wayspurrchen/moshy |

---

## Moshpit Command-Line Tool

### Overview

Moshpit is a cross-platform command-line tool for "surgical I-Frame removal." Written in Go, it includes built-in scene cut detection.

### Installation

Download the binary from the GitHub releases page. Requires FFmpeg installed separately.

**Source:** https://github.com/CrushedPixel/moshpit

### Usage

```bash
# Launch moshpit with a video file
moshpit input.mp4

# Interactive commands:
> scenes 0.2          # Detect scene cuts (threshold 0.0-1.0)
                       # Lower threshold = more sensitive
> mosh output.mp4 42  # Remove I-frame at frame 42
> mosh output.mp4 42 87 135  # Remove I-frames at multiple positions
> mosh output.mp4 all  # Remove I-frames at all detected scene boundaries
> exit                 # Quit
```

### How Moshpit Works

1. **Converts** source video to AVI format (for frame manipulation)
2. **Analyzes** frames to detect scene boundaries (configurable threshold)
3. **Removes** I-frames at user-specified positions
4. **Replaces** removed I-frames with the following P-frame (maintains duration)
5. **Bakes** the result back to MP4, preserving the datamosh artifacts

### Scene Detection

The scene detection analyzes frame-to-frame similarity:
- **Low threshold (0.1-0.2)**: Detects subtle scene changes -- good for finding all cuts
- **Medium threshold (0.3-0.5)**: Detects obvious scene changes
- **High threshold (0.7-0.9)**: Only detects dramatic scene changes

---

## Controlling Datamosh Intensity

### Variables That Affect Intensity

| Variable | Effect on Datamosh |
|----------|-------------------|
| **GOP size** | Larger GOP = more P-frames between I-frames = longer melt potential |
| **Motion in source** | More motion = more dramatic distortion |
| **Number of P-frame copies** | More copies = longer bloom/melt duration |
| **Number of removed I-frames** | More removals = longer sections without clean reference |
| **Codec choice** | Different codecs produce different artifact styles |
| **Encoding quality** | Lower quality = more visible compression artifacts |
| **Scene contrast** | Higher contrast between scenes = more dramatic I-frame removal |
| **B-frame presence** | B-frames add complexity; removing them (bf=0) simplifies control |

### Tips for Controlled Datamoshing

1. **Start subtle**: Begin with a single I-frame removal or a few P-frame copies
2. **Use scene detection**: Moshpit's scene detection identifies the best I-frames to remove
3. **Preview frequently**: Small changes can have dramatic visual effects
4. **Control motion estimation**: Using `-me_method zero` in FFmpeg creates more visible artifacts
5. **Layer effects**: Combine I-frame removal with P-frame duplication
6. **Re-encode for stability**: Always "bake" the result through a re-encode for playback compatibility

### Quality vs. Artifact Balance

```bash
# Subtle datamosh (higher quality, fewer artifacts)
ffmpeg -i input.mp4 -c:v libx264 -g 30 -bf 0 -crf 18 output.mp4

# Medium datamosh (balanced)
ffmpeg -i input.mp4 -c:v libx264 -g 120 -bf 0 -crf 23 -sc_threshold 0 output.mp4

# Aggressive datamosh (low quality, maximum artifacts)
ffmpeg -i input.mp4 -c:v libx264 -g 999 -bf 0 -crf 35 -sc_threshold 0 -me_method zero output.mp4
```

---

## Common Artifacts and How to Leverage Them

### Artifact Types

| Artifact | Cause | Visual Effect | Best Use |
|----------|-------|--------------|----------|
| **Motion smearing** | P-frames applying wrong motion vectors | Pixels stretch and blur in movement direction | Dreamlike transitions |
| **Color bleeding** | Incorrect color reference | Colors from one scene leak into another | Psychedelic effects |
| **Block corruption** | Macroblocks referencing wrong data | Rectangular glitch blocks appear | Digital decay aesthetic |
| **Ghosting** | Partial scene overlap | Transparent overlay of two scenes | Layered, ethereal looks |
| **Pixel drift** | Accumulated motion vector errors | Pixels slowly migrate across frame | Organic, liquid motion |
| **Edge artifacts** | Motion compensation errors at boundaries | Sharp geometric distortions at edges | Cyberpunk aesthetic |

### Leveraging Specific Artifacts

**For Music Videos:**
- Use I-frame removal at beat drops for dramatic visual shifts
- Use P-frame bloom during sustained notes or pads
- Time the "resolution" (where a new I-frame appears) to musical phrasing

**For Art Installations:**
- Loop a datamoshed section for continuous visual evolution
- Use very long P-frame duplication for meditative, slowly evolving pieces
- Feed live camera input through real-time datamoshing

**For Social Media Content:**
- Short, punchy I-frame removals at 2-3 second intervals
- Combine with text overlays for contrast
- Use the "resolved" moments (where I-frames appear) for important visual beats

---

## Integration with FFmpeg Pipeline

### Complete Datamosh Pipeline Script

```bash
#!/bin/bash
# datamosh_pipeline.sh - Complete datamoshing workflow

INPUT="$1"
OUTPUT="$2"
GOP_SIZE="${3:-999}"

if [ -z "$INPUT" ] || [ -z "$OUTPUT" ]; then
    echo "Usage: ./datamosh_pipeline.sh input.mp4 output.mp4 [gop_size]"
    exit 1
fi

TEMP_DIR=$(mktemp -d)
PREPARED="${TEMP_DIR}/prepared.avi"
MOSHED="${TEMP_DIR}/moshed.avi"

echo "Step 1: Preparing video with controlled GOP..."
ffmpeg -y -i "$INPUT" \
    -c:v mpeg4 \
    -bf 0 \
    -g "$GOP_SIZE" \
    -q:v 5 \
    -sc_threshold 0 \
    -c:a copy \
    "$PREPARED"

echo "Step 2: Analyzing frame types..."
ffprobe -v quiet -select_streams v:0 \
    -show_entries frame=pict_type \
    -of csv=p=0 "$PREPARED" | head -50

echo "Step 3: Use moshpit or manual tools to manipulate frames..."
echo "  moshpit $PREPARED"
echo "  OR use Avidemux to manually edit frames"

echo "Step 4: After manipulation, convert back:"
echo "  ffmpeg -y -i moshed.avi -c:v libx264 -crf 18 -pix_fmt yuv420p $OUTPUT"

# Cleanup
# rm -rf "$TEMP_DIR"
```

### Useful FFmpeg One-Liners

```bash
# Count frames by type
ffprobe -v quiet -select_streams v:0 \
    -show_entries frame=pict_type \
    -of csv=p=0 input.mp4 | sort | uniq -c

# Extract I-frames only as images
ffmpeg -i input.mp4 -vf "select='eq(pict_type,I)'" -vsync vfr iframes/frame_%04d.png

# Extract a specific frame range
ffmpeg -i input.mp4 -vf "select='between(n,100,200)'" -vsync vfr range/frame_%04d.png

# Create a very long GOP video (datamosh source material)
ffmpeg -i input.mp4 -c:v libx264 -x264-params "keyint=9999:min-keyint=9999:scenecut=0" -bf 0 prepared.mp4

# Re-encode datamoshed file for compatibility
ffmpeg -i moshed.avi -c:v libx264 -crf 18 -pix_fmt yuv420p final.mp4

# Add original audio back to datamoshed video
ffmpeg -i datamoshed_video.mp4 -i original.mp4 \
    -c:v copy -c:a copy -map 0:v -map 1:a \
    -shortest final_with_audio.mp4
```

---

## Alternative Techniques

### Optical Flow Transfer (Non-Destructive)

Instead of corrupting compressed video, extract motion vectors using optical flow and apply them to a static image:

```python
import cv2
import numpy as np

def optical_flow_datamosh(reference_image_path, motion_video_path, output_path):
    """
    Apply motion from a video to a static reference image.
    Non-destructive datamosh effect using optical flow.
    """
    ref_img = cv2.imread(reference_image_path)
    cap = cv2.VideoCapture(motion_video_path)

    fps = cap.get(cv2.CAP_PROP_FPS)
    h, w = ref_img.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    ret, prev_frame = cap.read()
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

    current_image = ref_img.astype(np.float32)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Compute optical flow (Farneback method)
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )

        # Create remap coordinates
        h, w = flow.shape[:2]
        map_x = np.arange(w).reshape(1, -1).repeat(h, axis=0).astype(np.float32)
        map_y = np.arange(h).reshape(-1, 1).repeat(w, axis=1).astype(np.float32)

        map_x += flow[:, :, 0]
        map_y += flow[:, :, 1]

        # Warp the current image using the flow
        warped = cv2.remap(current_image, map_x, map_y, cv2.INTER_LINEAR)
        current_image = warped

        out.write(warped.astype(np.uint8))
        prev_gray = gray

    cap.release()
    out.release()
```

### Audacity Audio-as-Video Method

An unusual technique that treats raw video data as audio:

1. Export video as raw YUV data: `ffmpeg -i input.mp4 -f rawvideo -pix_fmt yuv420p raw.yuv`
2. Import raw.yuv into Audacity as "Raw Data" (unsigned 8-bit)
3. Apply audio effects (echo, reverb, chorus, phaser)
4. Export as raw data
5. Convert back: `ffmpeg -f rawvideo -pix_fmt yuv420p -s WxH -r FPS -i processed.yuv output.mp4`

This produces unique glitch effects because audio processing algorithms interpret pixel data in unexpected ways.

### Real-Time Datamoshing

For live performance, some approaches include:
- **OBS with custom scripts**: Intercept the encoding pipeline
- **TouchDesigner + Feedback**: Simulates datamosh-like effects using feedback loops
- **Custom OpenCV pipeline**: Capture frames, apply optical flow transfer in real-time

---

## Resources and Links

### Tutorials
- [How to Datamosh Videos (datamoshing.com)](http://datamoshing.com/2016/06/26/how-to-datamosh-videos/)
- [Datamoshing Using Avidemux 2.7.0 (Antonio Roberts)](https://www.hellocatfood.com/datamoshing-using-avidemux-2-7-0/)
- [Datamosh 101 (formatc.hr)](https://formatc.hr/datamosh101/)
- [Datamoshing (Yohan Chalier)](https://chalier.fr/blog/datamoshing)
- [Datamoshing Tutorial for PC (Eddy Bergman)](https://www.eddybergman.com/2015/08/data-moshing-tutorial-for-pc-using.html)
- [How to Datamosh Video (Epidemic Sound)](https://www.epidemicsound.com/blog/how-to-datamosh/)

### Tools
- [Moshpit (Go CLI tool)](https://github.com/CrushedPixel/moshpit)
- [Moshy (Ruby datamosh toolkit)](https://github.com/wayspurrchen/moshy)
- [Video Art Scripts (Python)](https://github.com/selftext/video-art)
- [aviglitch (Ruby)](https://github.com/ucnv/aviglitch)
- [node-aviglitch (Node.js)](https://github.com/fand/node-aviglitch)
- [Autodatamosh (Perl)](https://github.com/grampajoe/Autodatamosh)
- [Datamosh-python](https://github.com/amgadani/Datamosh-python)

### Academic / Technical
- [Datamoshing Technique for Video Art Production (Art-Science Journal)](https://www.art-science.org/journal/v13n3/v13n3pp154/artsci-v13n3pp154.pdf)
- [What is Datamoshing (Destroy All Circuits)](https://www.destroyallcircuits.com/blogs/news/what-is-datamoshing-and-some-ramblings)
- [Datamoshing.com](http://datamoshing.com/)

### Video Resources
- [I-Frame Removal Examples (datamoshing.com/type/video)](http://datamoshing.com/type/video/)
- [VideoHelp Forum: Datamosh Discussions](https://forum.videohelp.com/threads/350898-datamosh-all-I-frames-in-video-how-to-get-p-frames)

### Software
- [Avidemux (avidemux.sourceforge.net)](http://avidemux.sourceforge.net/)
- [FFmpeg (ffmpeg.org)](https://ffmpeg.org/)
- [VLC (videolan.org)](https://www.videolan.org/)
