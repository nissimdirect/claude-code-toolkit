# ASCII Art Generator — Tool Reference

> **File:** `~/Development/tools/ascii_art.py`
> **Version:** 1.0
> **Deps:** Python 3, Pillow
> **Lines:** ~550

---

## What It Does

Converts images to ASCII art and renders text as large banners. Standalone CLI tool (also integrated into Entropic as `asciiart` and `brailleart` effects).

**Techniques sourced from:**
- [vietnh1009/ASCII-generator](https://github.com/vietnh1009/ASCII-generator) (8K stars) — color image output, cell averaging
- [TheZoraiz/ascii-image-converter](https://github.com/TheZoraiz/ascii-image-converter) (3K stars) — braille mode, Floyd-Steinberg dithering
- [joelibaceta/video-to-ascii](https://github.com/joelibaceta/video-to-ascii) (1.8K stars) — ITU-R BT.709 luminance, ANSI color mapping
- [stong/gradscii-art](https://github.com/stong/gradscii-art) — gradient descent optimization (referenced, not used)
- [JuliaPoo/AsciiArtist](https://github.com/JuliaPoo/AsciiArtist) — CNN edge detection approach (referenced)

---

## CLI Usage

```bash
# Image to ASCII
python3 ascii_art.py image photo.jpg [options]

# Text banner
python3 ascii_art.py text "HELLO" [options]

# Show demo
python3 ascii_art.py demo
```

### Image Options

| Flag | Default | Description |
|------|---------|-------------|
| `--width N` | 80 | Output width in characters |
| `--charset` | basic | `basic` (10), `dense` (69), `block` (5 Unicode), `braille` (256 patterns) |
| `--invert` | off | Swap light/dark (for dark terminal backgrounds) |
| `--color` | off | ANSI 24-bit truecolor output |
| `--dither` | off | Floyd-Steinberg error diffusion |
| `--edge` | off | Sobel edge detection overlay |
| `--html` | off | Output as color HTML (implies --color) |
| `--output FILE` | stdout | Save to file instead of printing |

### Text Options

| Flag | Default | Description |
|------|---------|-------------|
| `--char C` | # | Fill character for banner |
| `--output FILE` | stdout | Save to file |

---

## Character Sets

| Name | Chars | Use Case |
|------|-------|----------|
| `basic` | 10 (` .:-=+*#%@`) | Clean, readable, general purpose |
| `dense` | 69 (full ASCII ramp) | Maximum detail, fine gradation |
| `block` | 5 (` ░▒▓█`) | Bold Unicode blocks, graphic look |
| `braille` | 256 (U+2800–U+28FF) | 2x4 dot grid per char = **4x resolution** |

---

## Examples

```bash
# Basic conversion
python3 ascii_art.py image photo.jpg --width 80

# High-detail color (great in iTerm2 / Warp)
python3 ascii_art.py image photo.jpg --charset dense --color --width 120

# Braille mode (highest resolution)
python3 ascii_art.py image photo.jpg --charset braille --width 100

# Edge-detected + dithered block art
python3 ascii_art.py image photo.jpg --edge --dither --charset block

# Shareable HTML (open in browser)
python3 ascii_art.py image photo.jpg --html --output art.html && open art.html

# Album art preview
python3 ascii_art.py text "GONE MISSIN" --char @

# Save braille to file
python3 ascii_art.py image photo.jpg --charset braille --output art.txt
```

---

## Technical Details

### Luminance (ITU-R BT.709)
```
L = 0.2126*R + 0.7152*G + 0.0722*B
```
Green contributes most to perceived brightness. This matches how the human eye works.

### Braille Encoding
Each braille character is a 2-column × 4-row dot grid. 8 dots = 8 bits = 256 possible patterns (U+2800 to U+28FF).

```
Dot positions:    Bit values:
[1] [4]           0x01  0x08
[2] [5]           0x02  0x10
[3] [6]           0x04  0x20
[7] [8]           0x40  0x80
```

### Floyd-Steinberg Dithering
Error diffusion distributes quantization error to neighboring pixels:
```
         pixel    7/16 →
  3/16 ↙  5/16 ↓  1/16 ↘
```

### Sobel Edge Detection
3x3 convolution kernels for horizontal and vertical gradients. Combined magnitude emphasizes outlines, making shapes recognizable even at low ASCII resolution.

---

## Entropic Integration

The same algorithms power two Entropic effects:

| Entropic Effect | What It Does |
|----------------|-------------|
| `asciiart` | Frame → ASCII chars → rendered back as image |
| `brailleart` | Frame → braille unicode → rendered back as image |

**Package:** `ascii-art` (6 recipes)
- `terminal-mono` — White on black, basic charset
- `matrix-rain` — Green phosphor, dense charset + scanlines
- `amber-crt` — Amber terminal, block charset + noise
- `braille-hires` — 4x resolution braille, dithered
- `edge-ascii` — Sobel edge overlay, dense charset
- `nuclear-ascii` — Inverted braille + scanlines + noise

```bash
python3 entropic_packages.py apply myproject --package ascii-art --recipe matrix-rain
```

---

## Text Banner Font

Built-in 5-line bitmap font covering: A-Z, 0-9, space, `! ? . , - ' : / # & ( )`

No external font files needed.

```
#   # ##### #     #      ###
#   # #     #     #     #   #
##### ###   #     #     #   #
#   # #     #     #     #   #
#   # ##### ##### #####  ###
```
