# FFmpeg Filters Reference for Glitch Art

> Curated from [FFmpeg Filters Documentation](https://ffmpeg.org/ffmpeg-filters.html)
> Focus: Filters most useful for glitch art, datamoshing, and creative video destruction.

---

## Table of Contents

1. [displacement / displace](#1-displace)
2. [blend / tblend](#2-blend--tblend)
3. [chromakey](#3-chromakey)
4. [colorchannelmixer](#4-colorchannelmixer)
5. [curves](#5-curves)
6. [edgedetect](#6-edgedetect)
7. [eq](#7-eq)
8. [noise](#8-noise)
9. [random](#9-random)
10. [setpts](#10-setpts)
11. [shufflepixels](#11-shufflepixels)
12. [swaprect](#12-swaprect)
13. [tile](#13-tile)
14. [tmix](#14-tmix)
15. [xfade](#15-xfade)
16. [Bonus Glitch Filters](#16-bonus-glitch-filters)

---

## 1. displace

**What it does:** Displaces pixels in the input video using displacement maps from two additional video inputs. Creates warping, melting, and spatial distortion effects.

**Syntax:**
```
[input][xmap][ymap]displace
```

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `edge` | int | smear | Edge behavior: `blank`, `smear`, `wrap`, `mirror` |

**Glitch Art Usage:**
- Feed noise video as displacement map for organic warping
- Use edge-detected version of same video for self-distortion
- Animate displacement intensity over time for "melting" effect

**Examples:**
```bash
# Self-displacement using edge detection as map
ffmpeg -i input.mp4 -i xmap.mp4 -i ymap.mp4 -filter_complex "[0][1][2]displace" output.mp4

# Generate noise map and use as displacement
ffmpeg -f lavfi -i "nullsrc=s=1920x1080:d=10,geq=random(1)*255:128:128" -pix_fmt yuv420p noise_map.mp4
ffmpeg -i input.mp4 -i noise_map.mp4 -i noise_map.mp4 -filter_complex "[0][1][2]displace=edge=wrap" warped.mp4
```

---

## 2. blend / tblend

**What it does:** `blend` combines two video inputs pixel-by-pixel. `tblend` blends consecutive frames of a single video (temporal blend). Essential for ghosting, feedback, and overlay effects.

**Syntax:**
```
# Two-input spatial blend
[input1][input2]blend=all_mode=MODE:all_opacity=VALUE

# Single-input temporal blend
tblend=all_mode=MODE
```

**Blend Modes (glitch-relevant):**

| Mode | Effect | Glitch Use |
|------|--------|------------|
| `addition` | Add pixel values | Blown-out, overexposed |
| `difference` | Absolute difference | Motion trails, edge highlight |
| `exclusion` | Soft exclusion | Dreamy overlay |
| `multiply` | Darken blend | Shadow emphasis |
| `screen` | Lighten blend | Glow effect |
| `lighten` | Keep brighter pixel | Ghosting trails |
| `darken` | Keep darker pixel | Shadow bleeding |
| `average` | Mean of both | Smooth ghost overlay |
| `phoenix` | min-max blend | Psychedelic inversion |
| `negation` | Negate difference | Color shift artifacts |
| `xor` | XOR pixel values | Digital noise pattern |

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `c0_mode`...`c3_mode` | string | normal | Blend mode per channel (Y/U/V or R/G/B/A) |
| `c0_opacity`...`c3_opacity` | float | 1 | Opacity per channel (0.0-1.0) |
| `all_mode` | string | normal | Apply mode to all channels |
| `all_opacity` | float | 1 | Apply opacity to all channels |

**Examples:**
```bash
# Temporal ghosting (blend consecutive frames)
ffmpeg -i input.mp4 -vf "tblend=all_mode=average" ghost.mp4

# Difference-based motion trails
ffmpeg -i input.mp4 -vf "tblend=all_mode=difference" trails.mp4

# XOR noise pattern between frames
ffmpeg -i input.mp4 -vf "tblend=all_mode=xor" xor_glitch.mp4

# Phoenix blend for psychedelic effect
ffmpeg -i input.mp4 -vf "tblend=all_mode=phoenix" phoenix.mp4

# Blend two videos with different modes per channel
ffmpeg -i vid1.mp4 -i vid2.mp4 -filter_complex "[0][1]blend=c0_mode=lighten:c1_mode=difference:c2_mode=xor" output.mp4
```

---

## 3. chromakey

**What it does:** Removes a specific color from the video, making it transparent. Useful for compositing and creative keying of non-standard colors.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `color` | color | black | Color to key out (hex, name, or RGB) |
| `similarity` | float | 0.01 | How close colors must match (0.01-1.0) |
| `blend` | float | 0 | Edge softness (0-1) |
| `yuv` | bool | 0 | Process in YUV colorspace instead of RGB |

**Glitch Art Usage:**
- Key out skin tones to create body-horror voids
- Key out dominant scene colors for disorienting gaps
- Chain with noise to fill keyed areas with static

**Examples:**
```bash
# Remove green for glitch compositing
ffmpeg -i input.mp4 -vf "chromakey=color=green:similarity=0.15:blend=0.1" keyed.mp4

# Key out black areas and fill with noise
ffmpeg -i input.mp4 -vf "chromakey=color=black:similarity=0.3" keyed.mp4

# Key out specific hex color
ffmpeg -i input.mp4 -vf "chromakey=color=0xFF0000:similarity=0.2" keyed.mp4
```

---

## 4. colorchannelmixer

**What it does:** Remaps color channels through a 4x4 matrix multiplication. Each output channel is a weighted sum of all input channels. The most powerful color manipulation filter for glitch art.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `rr` | float | 1 | Red contribution to Red output |
| `rg` | float | 0 | Green contribution to Red output |
| `rb` | float | 0 | Blue contribution to Red output |
| `ra` | float | 0 | Alpha contribution to Red output |
| `gr` | float | 0 | Red contribution to Green output |
| `gg` | float | 1 | Green contribution to Green output |
| `gb` | float | 0 | Blue contribution to Green output |
| `ga` | float | 0 | Alpha contribution to Green output |
| `br` | float | 0 | Red contribution to Blue output |
| `bg` | float | 0 | Green contribution to Blue output |
| `bb` | float | 1 | Blue contribution to Blue output |
| `ba` | float | 0 | Alpha contribution to Blue output |

**Glitch Art Recipes:**

```bash
# Swap Red and Blue channels (alien color shift)
ffmpeg -i input.mp4 -vf "colorchannelmixer=rr=0:rb=1:bb=0:br=1" swapped.mp4

# Remove green channel entirely
ffmpeg -i input.mp4 -vf "colorchannelmixer=gg=0" no_green.mp4

# Mix all channels equally (desaturated + color bleed)
ffmpeg -i input.mp4 -vf "colorchannelmixer=rr=0.3:rg=0.4:rb=0.3:gr=0.3:gg=0.4:gb=0.3:br=0.3:bg=0.4:bb=0.3" flat.mp4

# Invert colors via channel mixing
ffmpeg -i input.mp4 -vf "colorchannelmixer=rr=-1:rg=0:rb=0:gr=0:gg=-1:gb=0:br=0:bg=0:bb=-1" inverted.mp4

# Sepia-like through channel bleed
ffmpeg -i input.mp4 -vf "colorchannelmixer=rr=0.393:rg=0.769:rb=0.189:gr=0.349:gg=0.686:gb=0.168:br=0.272:bg=0.534:bb=0.131" sepia.mp4
```

---

## 5. curves

**What it does:** Applies tone curve adjustments to video, similar to Photoshop curves. Supports presets and custom point-based curves per channel.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `preset` | string | none | `color_negative`, `cross_process`, `darker`, `increase_contrast`, `lighter`, `linear_contrast`, `medium_contrast`, `negative`, `strong_contrast`, `vintage` |
| `master` | string | - | Master curve as point pairs (e.g., `0/0 0.5/0.8 1/1`) |
| `red` | string | - | Red channel curve |
| `green` | string | - | Green channel curve |
| `blue` | string | - | Blue channel curve |
| `all` | string | - | Apply same curve to all channels |
| `psfile` | string | - | Load from Adobe Photoshop .acv curve file |

**Glitch Art Recipes:**

```bash
# Cross-process look (film processing error aesthetic)
ffmpeg -i input.mp4 -vf "curves=preset=cross_process" cross.mp4

# Color negative
ffmpeg -i input.mp4 -vf "curves=preset=color_negative" negative.mp4

# Extreme contrast crush (posterize-like)
ffmpeg -i input.mp4 -vf "curves=all='0/0 0.1/0 0.5/1 0.9/1 1/1'" crushed.mp4

# Solarization curve
ffmpeg -i input.mp4 -vf "curves=all='0/0 0.25/1 0.5/0 0.75/1 1/0'" solar.mp4

# Split-channel chaos
ffmpeg -i input.mp4 -vf "curves=red='0/1 1/0':green='0/0 0.5/1 1/0':blue='0/0.5 1/0.5'" chaos.mp4
```

---

## 6. edgedetect

**What it does:** Detects and renders edges in the video. Multiple algorithms available. Essential for creating sketch/wireframe looks and as masks for other effects.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | wires | `wires` (white on black), `colormix` (edges + color), `canny` (Canny detector) |
| `high` | float | 0.196078 | High threshold for edge detection |
| `low` | float | 0.078431 | Low threshold for edge detection |
| `planes` | flags | all | Which planes to filter |

**Examples:**
```bash
# Standard edge detection (sketch look)
ffmpeg -i input.mp4 -vf "edgedetect=low=0.1:high=0.4" edges.mp4

# Color-mixed edges (edges overlaid on original colors)
ffmpeg -i input.mp4 -vf "edgedetect=mode=colormix:high=0.1" color_edges.mp4

# High-sensitivity edge detection (noisy, glitchy)
ffmpeg -i input.mp4 -vf "edgedetect=low=0.01:high=0.05" noisy_edges.mp4

# Use as displacement mask (pipe to blend)
ffmpeg -i input.mp4 -filter_complex "[0]edgedetect=low=0.1:high=0.3[edges];[0][edges]blend=all_mode=addition" edge_glitch.mp4
```

---

## 7. eq

**What it does:** Adjusts brightness, contrast, saturation, and gamma. Basic but essential for pushing values to extremes for glitch effects.

**Parameters:**

| Param | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `contrast` | float | 1.0 | -1000 to 1000 | Contrast multiplier |
| `brightness` | float | 0.0 | -1.0 to 1.0 | Brightness offset |
| `saturation` | float | 1.0 | 0.0 to 3.0 | Color saturation |
| `gamma` | float | 1.0 | 0.1 to 10.0 | Overall gamma correction |
| `gamma_r` | float | 1.0 | 0.1 to 10.0 | Red gamma |
| `gamma_g` | float | 1.0 | 0.1 to 10.0 | Green gamma |
| `gamma_b` | float | 1.0 | 0.1 to 10.0 | Blue gamma |

**Examples:**
```bash
# Blown-out overexposure
ffmpeg -i input.mp4 -vf "eq=brightness=0.4:contrast=3:saturation=2" blown.mp4

# Deep crushed blacks
ffmpeg -i input.mp4 -vf "eq=brightness=-0.3:contrast=2:gamma=0.3" crushed.mp4

# Per-channel gamma shift (color cast glitch)
ffmpeg -i input.mp4 -vf "eq=gamma_r=0.5:gamma_g=1.5:gamma_b=2.0" gamma_shift.mp4

# Desaturated + high contrast (surveillance camera look)
ffmpeg -i input.mp4 -vf "eq=saturation=0.1:contrast=2:brightness=-0.1" surveillance.mp4
```

---

## 8. noise

**What it does:** Adds synthetic noise to the video. Supports uniform and temporal noise. Essential for VHS, film grain, and static effects.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `all_seed` / `c0_seed`...`c3_seed` | int | 123457 | Random seed |
| `all_strength` / `c0_strength`...`c3_strength` | int | 0 | Noise intensity (0-100) |
| `all_flags` / `c0_flags`...`c3_flags` | flags | 0 | Noise type flags |

**Noise Flags:**
- `a` - averaged temporal noise (smoother)
- `p` - mix random noise with semi-regular pattern
- `t` - temporal noise (different each frame)
- `u` - uniform distribution (vs. gaussian default)

**Examples:**
```bash
# Film grain
ffmpeg -i input.mp4 -vf "noise=alls=20:allf=t" grain.mp4

# Heavy VHS static
ffmpeg -i input.mp4 -vf "noise=alls=60:allf=t+u" static.mp4

# Noise only on luma (leave color clean)
ffmpeg -i input.mp4 -vf "noise=c0s=40:c0f=t" luma_noise.mp4

# Patterned noise (semi-regular interference)
ffmpeg -i input.mp4 -vf "noise=alls=30:allf=t+p" pattern_noise.mp4
```

---

## 9. random

**What it does:** Randomly reorders video frames within a buffer. Creates temporal glitch, stutter, and non-linear playback.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | int | 30 | Buffer size (number of frames to shuffle among) |
| `seed` | int | -1 | Random seed (-1 = auto) |

**Examples:**
```bash
# Mild frame shuffle (subtle temporal glitch)
ffmpeg -i input.mp4 -vf "random=frames=5" mild_shuffle.mp4

# Aggressive frame chaos
ffmpeg -i input.mp4 -vf "random=frames=60" chaos.mp4

# Deterministic shuffle (reproducible)
ffmpeg -i input.mp4 -vf "random=frames=15:seed=42" deterministic.mp4
```

---

## 10. setpts

**What it does:** Modifies presentation timestamps. Essential for speed ramping, freezing, time-stretching, and temporal manipulation.

**Expression Variables:**

| Variable | Description |
|----------|-------------|
| `N` | Frame count (starting from 0) |
| `PTS` | Current presentation timestamp |
| `PREV_INPTS` | Previous input PTS |
| `PREV_OUTPTS` | Previous output PTS |
| `STARTPTS` | First frame PTS |
| `T` | Time in seconds |
| `TB` | Timebase |

**Examples:**
```bash
# 2x speed
ffmpeg -i input.mp4 -vf "setpts=0.5*PTS" fast.mp4

# Half speed (slow motion)
ffmpeg -i input.mp4 -vf "setpts=2.0*PTS" slow.mp4

# Freeze at frame 100 (hold frame)
ffmpeg -i input.mp4 -vf "setpts=if(gte(N\,100)\,100*TB\,PTS)" freeze.mp4

# Progressive slowdown (tape stop effect)
ffmpeg -i input.mp4 -vf "setpts=PTS*(1+0.01*N)" tape_stop.mp4

# Random speed variation
ffmpeg -i input.mp4 -vf "setpts=PTS+random(0)*0.1" jitter.mp4

# Reset timestamps (fix after other manipulations)
ffmpeg -i input.mp4 -vf "setpts=PTS-STARTPTS" reset.mp4
```

---

## 11. shufflepixels

**What it does:** Randomly rearranges pixels or pixel blocks within each frame. Pure spatial glitch.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `direction` | int | 0 | `0` = forward, `1` = inverse |
| `mode` | int | 0 | `0` = horizontal, `1` = vertical, `2` = block |
| `width` | int | 10 | Block width for shuffling |
| `height` | int | 10 | Block height for shuffling |
| `seed` | int | -1 | Random seed |

**Examples:**
```bash
# Horizontal pixel shuffle
ffmpeg -i input.mp4 -vf "shufflepixels=mode=0:width=20:seed=42" h_shuffle.mp4

# Block shuffle (mosaic glitch)
ffmpeg -i input.mp4 -vf "shufflepixels=mode=2:width=30:height=30:seed=42" block_glitch.mp4

# Fine pixel scatter
ffmpeg -i input.mp4 -vf "shufflepixels=mode=2:width=2:height=2" scatter.mp4
```

---

## 12. swaprect

**What it does:** Swaps two rectangular regions within the frame. Creates cut-and-paste displacement glitch.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `w` | string | - | Rectangle width (supports expressions) |
| `h` | string | - | Rectangle height (supports expressions) |
| `x1` | string | - | First rectangle X position |
| `y1` | string | - | First rectangle Y position |
| `x2` | string | - | Second rectangle X position |
| `y2` | string | - | Second rectangle Y position |

**Examples:**
```bash
# Swap top-left and bottom-right quadrants
ffmpeg -i input.mp4 -vf "swaprect=w=iw/2:h=ih/2:x1=0:y1=0:x2=iw/2:y2=ih/2" swapped.mp4

# Random rectangle swap (animated expression)
ffmpeg -i input.mp4 -vf "swaprect=w=100:h=100:x1=mod(n*17\,iw-100):y1=mod(n*31\,ih-100):x2=mod(n*23\,iw-100):y2=mod(n*41\,ih-100)" random_swap.mp4
```

---

## 13. tile

**What it does:** Arranges input frames into a grid layout. Useful for creating contact sheets, kaleidoscope effects, and tiled glitch patterns.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `layout` | string | 6x5 | Grid dimensions (COLSxROWS) |
| `nb_frames` | int | 0 | Frames per tile (0 = auto) |
| `margin` | int | 0 | Margin between tiles (pixels) |
| `padding` | int | 0 | Border padding (pixels) |
| `color` | color | black | Background/padding color |
| `overlap` | int | 0 | Number of frames to overlap |
| `init_padding` | int | 0 | Initial padding frames |

**Examples:**
```bash
# 4x4 grid of frames (contact sheet)
ffmpeg -i input.mp4 -vf "tile=4x4" tiled.mp4

# Kaleidoscope-like tiling with overlap
ffmpeg -i input.mp4 -vf "scale=480:270,tile=4x4:overlap=12" kaleidoscope.mp4

# Single-row filmstrip
ffmpeg -i input.mp4 -vf "scale=192:108,tile=10x1" filmstrip.mp4
```

---

## 14. tmix

**What it does:** Temporally mixes consecutive frames using weighted averaging. Creates motion blur, ghosting, and temporal smearing.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | int | 3 | Number of frames to mix (1-128) |
| `weights` | string | 1 1 1 | Weight per frame (space-separated) |
| `scale` | float | 0 | Output divisor (0 = auto sum of weights) |

**Examples:**
```bash
# Light motion blur (3-frame average)
ffmpeg -i input.mp4 -vf "tmix=frames=3:weights='1 1 1'" blur.mp4

# Heavy ghosting (10 frames, decaying)
ffmpeg -i input.mp4 -vf "tmix=frames=10:weights='1 2 3 4 5 5 4 3 2 1'" ghost.mp4

# Echo trail (weighted toward current frame)
ffmpeg -i input.mp4 -vf "tmix=frames=5:weights='10 4 2 1 1'" echo.mp4

# Extreme temporal smear (30 frames)
ffmpeg -i input.mp4 -vf "tmix=frames=30" extreme_smear.mp4

# Difference-weighted (emphasize movement)
ffmpeg -i input.mp4 -vf "tmix=frames=3:weights='1 -2 1'" movement.mp4
```

---

## 15. xfade

**What it does:** Creates transitions between two video clips. Includes many built-in transition effects useful for glitch aesthetics.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `transition` | string | fade | Transition effect (see list below) |
| `duration` | float | 1 | Transition duration in seconds |
| `offset` | float | 0 | Start time of transition |
| `expr` | string | - | Custom transition expression |

**Glitch-Relevant Transitions:**
- `fade`, `dissolve` - Standard fades
- `pixelize` - Pixelation transition
- `diagtl`, `diagtr`, `diagbl`, `diagbr` - Diagonal wipes
- `hlslice`, `hrslice`, `vuslice`, `vdslice` - Slice transitions
- `horzopen`, `horzclose`, `vertopen`, `vertclose` - Split reveals
- `squeezeh`, `squeezev` - Squeeze transitions
- `zoomin` - Zoom transition
- `wipetl`, `wipetr`, `wipebl`, `wipebr` - Directional wipes

**Examples:**
```bash
# Pixelation transition between two clips
ffmpeg -i clip1.mp4 -i clip2.mp4 -filter_complex "xfade=transition=pixelize:duration=2:offset=3" output.mp4

# Slice transition
ffmpeg -i clip1.mp4 -i clip2.mp4 -filter_complex "xfade=transition=hlslice:duration=1:offset=4" output.mp4
```

---

## 16. Bonus Glitch Filters

### rgbashift (RGB Split / Chromatic Aberration)
```bash
# Horizontal RGB split
ffmpeg -i input.mp4 -vf "rgbashift=rh=5:bh=-5:rv=3:bv=-3" rgb_split.mp4

# Extreme RGB split
ffmpeg -i input.mp4 -vf "rgbashift=rh=20:bh=-20:gh=10" extreme_split.mp4
```

### hue (Color Rotation)
```bash
# Constant hue shift
ffmpeg -i input.mp4 -vf "hue=h=90" hue90.mp4

# Animated hue rotation (rainbow cycle)
ffmpeg -i input.mp4 -vf "hue=H=2*PI*t/5" rainbow.mp4

# Desaturated hue shift
ffmpeg -i input.mp4 -vf "hue=h=180:s=0.5" desat_shift.mp4
```

### geq (Generic Equation Filter)
```bash
# Pixel value based on position (gradient glitch)
ffmpeg -i input.mp4 -vf "geq=r='X*Y*0.001':g='(X+Y)*0.5':b='255-X'" geq_glitch.mp4

# Self-referencing pixel shift
ffmpeg -i input.mp4 -vf "geq=lum='lum(X+10\,Y+10)':cb='cb(X\,Y)':cr='cr(X\,Y)'" shifted.mp4
```

### lagfun (Temporal Lag)
```bash
# Glow trails from bright pixels
ffmpeg -i input.mp4 -vf "lagfun=decay=0.95" glow_trails.mp4

# Heavy persistence
ffmpeg -i input.mp4 -vf "lagfun=decay=0.99" heavy_persist.mp4
```

### negate
```bash
# Simple color inversion
ffmpeg -i input.mp4 -vf "negate" inverted.mp4
```

### transpose (Rotation for Directional Effects)
```bash
# Rotate 90 degrees (for vertical pixel sorting approximation)
ffmpeg -i input.mp4 -vf "transpose=1" rotated.mp4
```

---

## Filter Chaining Quick Reference

Combine filters with commas for complex effects:

```bash
# VHS look: noise + color shift + blur
ffmpeg -i input.mp4 -vf "noise=alls=25:allf=t,rgbashift=rh=3:bh=-3,eq=saturation=1.3:contrast=1.2" vhs.mp4

# Broken TV: edge detect + color channel swap + noise
ffmpeg -i input.mp4 -vf "edgedetect=mode=colormix:high=0.05,colorchannelmixer=rr=0:rb=1:bb=0:br=1,noise=alls=15:allf=t" broken_tv.mp4

# Dream sequence: tmix + hue rotation + eq
ffmpeg -i input.mp4 -vf "tmix=frames=5:weights='5 3 2 1 1',hue=H=0.5*PI*t/10,eq=brightness=0.1:saturation=0.7" dream.mp4

# Progressive destruction: expressions with frame number
ffmpeg -i input.mp4 -vf "noise=c0s='min(100\,N/3)':c0f=t,eq=contrast='1+N*0.01'" progressive.mp4
```
