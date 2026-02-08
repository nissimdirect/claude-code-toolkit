# FFmpeg Codecs & Formats Guide for Glitch Art

> Curated from [FFmpeg Codecs Documentation](https://ffmpeg.org/ffmpeg-codecs.html)
> Focus: Codecs that matter for glitch art preservation, datamoshing, and creative encoding.

---

## Why Codecs Matter for Glitch Art

Codec choice determines whether your glitch effects survive encoding:

- **Lossy codecs** (H.264, MPEG-4) add their own compression artifacts -- sometimes desirable, sometimes destructive
- **Lossless codecs** (FFV1, HuffYUV, rawvideo) preserve exact pixel values -- use for intermediate processing
- **I-frame control** is critical for datamoshing -- you need codecs that let you manipulate keyframe placement

**Rule of thumb:** Edit in lossless, export in lossy for delivery.

---

## Codec Comparison Table

| Codec | Lossless? | I-Frame Control | File Size | Speed | Best For |
|-------|-----------|-----------------|-----------|-------|----------|
| **rawvideo** | Yes | N/A | Enormous | Instant | Byte-level corruption |
| **FFV1** | Yes | N/A | Large | Fast | Intermediate storage |
| **HuffYUV** | Yes | N/A | Large | Fast | Legacy lossless |
| **libx264** | Optional | Full | Small-Med | Medium | Datamosh + delivery |
| **ProRes** | Near | N/A | Large | Fast | Mac/Final Cut workflows |
| **MJPEG** | No | Every frame | Large | Fast | Frame-by-frame editing |
| **mpeg2video** | No | Full | Medium | Fast | Classic datamosh |
| **mpeg4** | No | Full | Small-Med | Fast | AVI datamosh (Xvid) |

---

## 1. rawvideo -- Raw Uncompressed

**What it is:** Zero compression. Every pixel stored as-is. The largest files but zero encoding artifacts.

**Why for glitch art:**
- **Byte-level corruption**: Import raw YUV into Audacity as audio, apply effects, re-export
- **No compression interference**: What you write is exactly what you get
- **Databending**: Direct hex editing produces predictable results

**Key Parameters:**

| Param | Description |
|-------|-------------|
| `pixel_format` | Pixel layout (yuv420p, rgb24, rgba, etc.) |
| `video_size` | Frame dimensions (must match exactly) |
| `framerate` | Playback rate |

**Commands:**
```bash
# Export to raw YUV (for Audacity databending)
ffmpeg -i input.mp4 -f rawvideo -pix_fmt yuv420p output.yuv

# Import raw YUV back to video
ffmpeg -f rawvideo -pix_fmt yuv420p -s 1920x1080 -r 30 -i output.yuv -c:v libx264 -crf 18 result.mp4

# Export to raw RGB
ffmpeg -i input.mp4 -f rawvideo -pix_fmt rgb24 output.rgb

# Calculate file size: width * height * bytes_per_pixel * frames
# 1920x1080 YUV420p at 30fps = ~93 MB/second
```

**Audacity Databending Workflow:**
```bash
# 1. Export video as raw YUV
ffmpeg -i input.mp4 -f rawvideo -pix_fmt yuv420p raw.yuv

# 2. Open raw.yuv in Audacity:
#    File > Import > Raw Data
#    Encoding: Unsigned 8-bit
#    Channels: 1 (Mono)
#    Sample rate: 48000 (arbitrary, but remember it)

# 3. Apply audio effects (echo, reverb, phaser, etc.)
# 4. Export as raw data (no header)

# 5. Convert back to video
ffmpeg -f rawvideo -pix_fmt yuv420p -s 1920x1080 -r 30 -i processed.yuv -c:v libx264 -crf 18 glitched.mp4
```

---

## 2. FFV1 -- Lossless Archival

**What it is:** Open-source lossless video codec. Excellent compression ratio for a lossless codec. Used by archives and museums.

**Why for glitch art:**
- Best lossless option for intermediate storage during multi-step glitch processing
- Preserves exact pixel values between processing stages
- Smaller files than rawvideo while remaining lossless

**Key Parameters:**

| Param | Value | Description |
|-------|-------|-------------|
| `coder` | `0` (rice), `1` (range_def), `2` (range_tab) | Entropy coder selection |
| `context` | `0` (small), `1` (big) | Context model size |
| `slicecrc` | `-1` (auto), `0` (off), `1` (on) | CRC checking per slice |

**Commands:**
```bash
# Encode lossless intermediate
ffmpeg -i input.mp4 -c:v ffv1 -level 3 -coder 1 -context 1 -slicecrc 1 lossless.mkv

# Use as intermediate format in pipeline
ffmpeg -i input.mp4 -vf "noise=alls=30:allf=t" -c:v ffv1 step1.mkv
ffmpeg -i step1.mkv -vf "rgbashift=rh=5:bh=-5" -c:v ffv1 step2.mkv
ffmpeg -i step2.mkv -c:v libx264 -crf 18 final.mp4
```

---

## 3. HuffYUV -- Lossless Legacy

**What it is:** Huffman-coded YUV lossless codec. Fast encoding/decoding, widely compatible.

**Why for glitch art:**
- Fast encode/decode for real-time preview workflows
- Good compatibility with older tools (VirtualDub, AviSynth)
- AVI container support (important for AviGlitch tools)

**Commands:**
```bash
# Encode lossless HuffYUV in AVI container
ffmpeg -i input.mp4 -c:v huffyuv lossless.avi

# HuffYUV in AVI for AviGlitch compatibility
ffmpeg -i input.mp4 -c:v huffyuv -an datamosh_ready.avi
```

---

## 4. libx264 (H.264) -- The Datamosh Codec

**What it is:** The most common video codec. H.264/AVC. The primary codec for datamoshing because of its I/P/B frame structure.

**Why for glitch art:**
- **Datamoshing**: Remove I-frames to create motion-bleed effects
- **GOP control**: Fine-grained keyframe placement
- **CRF quality**: Scale from lossless (0) to intentionally degraded (51)
- **Universal playback**: Works everywhere

**Critical Parameters for Glitch Art:**

| Param | Type | Description |
|-------|------|-------------|
| `-g N` | int | GOP size (keyframe interval). Higher = fewer I-frames = more mosh-able |
| `-keyint_min N` | int | Minimum keyframe interval |
| `-bf N` | int | Max B-frames (set to 0 for datamosh prep) |
| `-sc_threshold N` | int | Scene change detection threshold (0 = disable) |
| `-crf N` | int | Quality (0=lossless, 23=default, 51=worst) |
| `-preset` | string | Speed/quality tradeoff (ultrafast to veryslow) |
| `-tune` | string | Optimization target (film, animation, grain, etc.) |
| `-x264opts` | string | Advanced x264 options |

**Datamosh Prep Commands:**
```bash
# Prepare video for datamoshing (minimal I-frames, no B-frames)
ffmpeg -i input.mp4 -c:v libx264 -g 999999 -keyint_min 999999 -bf 0 -sc_threshold 0 -crf 18 datamosh_prep.mp4

# Force I-frame only (every frame is a keyframe -- anti-datamosh for clean editing)
ffmpeg -i input.mp4 -c:v libx264 -g 1 -crf 18 all_iframes.mp4

# Intentionally degraded quality (lo-fi aesthetic)
ffmpeg -i input.mp4 -c:v libx264 -crf 45 -preset ultrafast degraded.mp4

# Lossless H.264
ffmpeg -i input.mp4 -c:v libx264 -crf 0 -preset veryslow lossless.mp4

# Preserve grain (don't let encoder smooth out glitch artifacts)
ffmpeg -i glitched.mp4 -c:v libx264 -crf 18 -tune grain -preset slow final.mp4
```

**Understanding GOP for Datamosh:**
```
GOP = Group of Pictures

I-frame: Full image (reference)
P-frame: Predicted from previous frame (motion vectors + residual)
B-frame: Bi-directional prediction

Normal GOP: I P P P P I P P P P I ...
Datamosh prep: I P P P P P P P P P P P P ... (one I-frame, all P after)

When you remove I-frames:
- P-frames reference a frame that no longer exists
- Decoder uses whatever was last decoded as reference
- Motion vectors from new video apply to old video's pixels
- Result: "pixel bleeding" / "motion transfer" datamosh effect
```

---

## 5. ProRes -- Mac/Professional Workflow

**What it is:** Apple's intermediate codec. Near-lossless at high profiles. Native to Final Cut Pro and Logic workflows.

**Why for glitch art:**
- High quality intermediate for Mac-based workflows
- Works natively in Final Cut Pro, Motion, Logic Pro
- Good for final delivery to galleries/installations

**Profiles:**

| Profile | Quality | Use Case |
|---------|---------|----------|
| `proxy` | Low | Offline editing |
| `lt` | Medium | Standard editing |
| `standard` | High | Finishing |
| `hq` | Very High | Master delivery |
| `4444` | Near-lossless + alpha | Compositing with transparency |
| `4444xq` | Highest | Archive master |

**Commands:**
```bash
# ProRes HQ for portfolio delivery
ffmpeg -i input.mp4 -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le output.mov

# ProRes 4444 with alpha channel (for overlays)
ffmpeg -i input.mp4 -c:v prores_ks -profile:v 4 -pix_fmt yuva444p10le output.mov
```

---

## 6. MJPEG -- Frame-Independent

**What it is:** Motion JPEG. Each frame is an independent JPEG image. No inter-frame compression.

**Why for glitch art:**
- Every frame is independently decodable
- Corrupt one frame without affecting others
- Easy to extract, manipulate, re-insert individual frames
- No I/P/B frame complexity

**Commands:**
```bash
# Encode as MJPEG (high quality)
ffmpeg -i input.mp4 -c:v mjpeg -q:v 2 mjpeg_output.avi

# Low quality MJPEG (intentional JPEG artifacts)
ffmpeg -i input.mp4 -c:v mjpeg -q:v 20 jpeggy.avi

# Individual JPEG corruption workflow
ffmpeg -i input.mp4 -c:v mjpeg -q:v 3 frames/frame_%04d.jpg
# (corrupt individual JPEGs with hex editor or Python)
ffmpeg -framerate 30 -i frames/frame_%04d.jpg -c:v libx264 -crf 18 result.mp4
```

---

## 7. mpeg2video -- Classic Datamosh

**What it is:** MPEG-2 codec. Older but simpler I/P/B frame structure. Used in DVDs.

**Why for glitch art:**
- Simpler frame structure than H.264 -- easier to parse and manipulate
- Classic datamosh aesthetic (more blocky, less smooth than H.264)
- Well-understood by AviGlitch and older mosh tools

**Key Parameters:**

| Param | Description |
|-------|-------------|
| `-g N` | GOP size (keyframe interval) |
| `-bf N` | Max B-frames |
| `-qmin` / `-qmax` | Quantizer range |
| `-b:v` | Target bitrate |

**Commands:**
```bash
# MPEG-2 for datamosh prep
ffmpeg -i input.mp4 -c:v mpeg2video -g 500 -bf 0 -q:v 2 mosh_prep.mpg

# Low bitrate MPEG-2 (heavy blocking artifacts)
ffmpeg -i input.mp4 -c:v mpeg2video -b:v 500k blocky.mpg
```

---

## 8. mpeg4 (Xvid/DivX) -- AVI Datamosh Standard

**What it is:** MPEG-4 Part 2 (not H.264). The classic format for AviGlitch datamoshing. Usually in AVI container.

**Why for glitch art:**
- **THE** format for AviGlitch and moshy tools
- Simple AVI container is easy to parse at byte level
- B-frame control via `-bf 0`
- Well-documented datamosh workflow

**Key Parameters:**

| Param | Description |
|-------|-------------|
| `-g N` | GOP size |
| `-bf N` | Max B-frames (0 for datamosh) |
| `-b:v` | Target bitrate |
| `-qmin` / `-qmax` | Quantizer range |

**Commands:**
```bash
# Prepare for AviGlitch (MPEG-4 ASP in AVI, no B-frames)
ffmpeg -i input.mp4 -c:v mpeg4 -g 300 -bf 0 -q:v 3 -an datamosh_ready.avi

# Xvid-compatible output
ffmpeg -i input.mp4 -c:v mpeg4 -vtag xvid -g 300 -bf 0 -q:v 3 xvid_output.avi

# Low quality (intentional macro-blocking)
ffmpeg -i input.mp4 -c:v mpeg4 -b:v 200k -bf 0 macroblocked.avi
```

---

## Workflow Decision: Which Codec When?

```
What are you doing?
|
├── Datamoshing?
│   ├── Using AviGlitch/moshy → mpeg4 in AVI container
│   ├── Using FFmpeg directly → libx264 with high -g
│   └── Classic blocky mosh → mpeg2video
|
├── Frame-by-frame processing (Python/PIL)?
│   ├── Need lossless → ffv1 in MKV or rawvideo
│   ├── Need speed → huffyuv in AVI
│   └── Want JPEG artifacts → mjpeg
|
├── Byte-level corruption (hex/Audacity)?
│   └── rawvideo (YUV or RGB)
|
├── Multi-step pipeline?
│   └── ffv1 between steps, libx264 for final
|
├── Delivery (portfolio/social)?
│   ├── Web/social → libx264 (CRF 18-23)
│   ├── Mac/Final Cut → prores_ks
│   └── Intentional lo-fi → libx264 (CRF 35+)
|
└── Archival master?
    └── ffv1 level 3 in MKV
```

---

## Encoding Speed Reference

| Preset (libx264) | Speed | Quality | Use Case |
|-------------------|-------|---------|----------|
| `ultrafast` | Fastest | Lowest | Quick previews |
| `veryfast` | Very fast | Low | Drafts |
| `fast` | Fast | Medium | Working copies |
| `medium` | Default | Good | General use |
| `slow` | Slow | Very good | Final render |
| `veryslow` | Slowest | Best | Archive/portfolio |

```bash
# Quick preview of glitch effect
ffmpeg -i glitched_frames/%04d.png -c:v libx264 -preset ultrafast -crf 23 preview.mp4

# Final portfolio render
ffmpeg -i glitched_frames/%04d.png -c:v libx264 -preset veryslow -crf 18 -tune grain final.mp4
```
