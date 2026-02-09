#!/usr/bin/env python3
"""ASCII Art Generator — Convert images and text to ASCII art.

Features inspired by: vietnh1009/ASCII-generator (8K stars), TheZoraiz/ascii-image-converter (3K),
joelibaceta/video-to-ascii (1.8K), stong/gradscii-art, JuliaPoo/AsciiArtist.

Usage:
    python3 ascii_art.py image photo.jpg [--width 80] [--charset basic] [--invert] [--color] [--dither] [--edge] [--output file.txt]
    python3 ascii_art.py text "HELLO" [--char #] [--output file.txt]
    python3 ascii_art.py demo
"""

import argparse
import html as html_module
import sys
from pathlib import Path

try:
    from PIL import Image, ImageFilter
    Image.MAX_IMAGE_PIXELS = 178_956_970  # ~13400x13400, Pillow default guard
except ImportError:
    Image = None

# Allowed image extensions
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}

# Width bounds
MAX_WIDTH = 500

# ---------------------------------------------------------------------------
# Character sets (ordered darkest → lightest for white backgrounds)
# ---------------------------------------------------------------------------
CHARSETS = {
    # 69 chars — fine gradation for detailed images
    "dense": " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    # 10 chars — clean, readable
    "basic": " .:-=+*#%@",
    # 5 chars — Unicode block elements
    "block": " ░▒▓█",
    # Braille — 256 patterns via 2×4 dot grid (U+2800–U+28FF)
    # Handled specially in image_to_ascii(); this is just for the charset list
    "braille": "braille",
}

# Braille dot bit positions: each char is a 2-wide × 4-tall grid
# Left column bits: 0x01, 0x02, 0x04, 0x40
# Right column bits: 0x08, 0x10, 0x20, 0x80
BRAILLE_DOTS = [
    [0x01, 0x08],
    [0x02, 0x10],
    [0x04, 0x20],
    [0x40, 0x80],
]

# ---------------------------------------------------------------------------
# Embedded 5-line bitmap font  (each char is a list of 5 strings, same width)
# ---------------------------------------------------------------------------
FONT = {
    "A": [" ### ", "#   #", "#####", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#### ", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", " ####"],
    "D": ["#### ", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "###  ", "#    ", "#####"],
    "F": ["#####", "#    ", "###  ", "#    ", "#    "],
    "G": [" ####", "#    ", "# ###", "#   #", " ####"],
    "H": ["#   #", "#   #", "#####", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["#####", "    #", "    #", "#   #", " ### "],
    "K": ["#   #", "#  # ", "###  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#### ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
    "S": [" ####", "#    ", " ### ", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "# # #", "## ##", "#   #"],
    "X": ["#   #", " # # ", "  #  ", " # # ", "#   #"],
    "Y": ["#   #", " # # ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "   # ", "  #  ", " #   ", "#####"],
    "0": [" ### ", "#  ##", "# # #", "##  #", " ### "],
    "1": [" ##  ", "# #  ", "  #  ", "  #  ", "#####"],
    "2": [" ### ", "#   #", "  ## ", " #   ", "#####"],
    "3": [" ### ", "#   #", "  ## ", "#   #", " ### "],
    "4": ["#   #", "#   #", "#####", "    #", "    #"],
    "5": ["#####", "#    ", "#### ", "    #", "#### "],
    "6": [" ### ", "#    ", "#### ", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", "  #  "],
    "8": [" ### ", "#   #", " ### ", "#   #", " ### "],
    "9": [" ### ", "#   #", " ####", "    #", " ### "],
    " ": ["     ", "     ", "     ", "     ", "     "],
    "!": ["  #  ", "  #  ", "  #  ", "     ", "  #  "],
    "?": [" ### ", "#   #", "  ## ", "     ", "  #  "],
    ".": ["     ", "     ", "     ", "     ", "  #  "],
    ",": ["     ", "     ", "     ", "  #  ", " #   "],
    "-": ["     ", "     ", "#####", "     ", "     "],
    "'": ["  #  ", "  #  ", "     ", "     ", "     "],
    ":": ["     ", "  #  ", "     ", "  #  ", "     "],
    "/": ["    #", "   # ", "  #  ", " #   ", "#    "],
    "#": [" # # ", "#####", " # # ", "#####", " # # "],
    "&": [" ##  ", "#  # ", " ### ", "#  # ", " ## #"],
    "(": ["  #  ", " #   ", " #   ", " #   ", "  #  "],
    ")": ["  #  ", "   # ", "   # ", "   # ", "  #  "],
}


# ---------------------------------------------------------------------------
# Luminance — perceptual brightness (ITU-R BT.709)
# From video-to-ascii: green contributes most, blue least
# ---------------------------------------------------------------------------
def luminance(r, g, b):
    """Perceptual brightness from RGB (0-255)."""
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ---------------------------------------------------------------------------
# ANSI 256-color escape codes (from video-to-ascii)
# ---------------------------------------------------------------------------
def rgb_to_ansi256(r, g, b):
    """Convert RGB (0-255) to ANSI 256-color index."""
    r, g, b = int(r), int(g), int(b)
    # Grayscale ramp (24 shades)
    if r == g == b:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return int(round((r - 8) / 247 * 24)) + 232
    # 6×6×6 color cube
    r_idx = int(round(r / 255 * 5))
    g_idx = int(round(g / 255 * 5))
    b_idx = int(round(b / 255 * 5))
    return 16 + 36 * r_idx + 6 * g_idx + b_idx


def colorize_char(char, r, g, b):
    """Wrap a character in ANSI 256-color foreground escape code."""
    return f"\x1b[38;5;{rgb_to_ansi256(r, g, b)}m{char}\x1b[0m"


def colorize_char_truecolor(char, r, g, b):
    """Wrap a character in 24-bit truecolor foreground escape code."""
    return f"\x1b[38;2;{int(r)};{int(g)};{int(b)}m{char}\x1b[0m"


# ---------------------------------------------------------------------------
# Floyd-Steinberg dithering (from ascii-image-converter approach)
# ---------------------------------------------------------------------------
def floyd_steinberg_dither(img_array, levels):
    """Apply Floyd-Steinberg error diffusion dithering in-place.

    Args:
        img_array: 2D numpy-like list of floats (0-255)
        levels: number of quantization levels
    Returns:
        Dithered 2D array
    """
    height = len(img_array)
    width = len(img_array[0]) if height > 0 else 0
    step = 255 / (levels - 1) if levels > 1 else 255

    for y in range(height):
        for x in range(width):
            old_val = img_array[y][x]
            new_val = round(old_val / step) * step
            new_val = max(0, min(255, new_val))
            error = old_val - new_val
            img_array[y][x] = new_val

            if x + 1 < width:
                img_array[y][x + 1] += error * 7 / 16
            if y + 1 < height:
                if x - 1 >= 0:
                    img_array[y + 1][x - 1] += error * 3 / 16
                img_array[y + 1][x] += error * 5 / 16
                if x + 1 < width:
                    img_array[y + 1][x + 1] += error * 1 / 16

    return img_array


# ---------------------------------------------------------------------------
# Edge detection (Sobel operator — no numpy/scipy required)
# Inspired by pic2ascii and AsciiArtist
# ---------------------------------------------------------------------------
def sobel_edge_detect(pixels, width, height):
    """Simple Sobel edge detection on grayscale pixel grid.

    Returns edge magnitude array (0-255).
    """
    edges = [[0] * width for _ in range(height)]
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            # Sobel kernels
            gx = (
                -pixels[y - 1][x - 1] + pixels[y - 1][x + 1]
                - 2 * pixels[y][x - 1] + 2 * pixels[y][x + 1]
                - pixels[y + 1][x - 1] + pixels[y + 1][x + 1]
            )
            gy = (
                -pixels[y - 1][x - 1] - 2 * pixels[y - 1][x] - pixels[y - 1][x + 1]
                + pixels[y + 1][x - 1] + 2 * pixels[y + 1][x] + pixels[y + 1][x + 1]
            )
            mag = min(255, int((gx ** 2 + gy ** 2) ** 0.5))
            edges[y][x] = mag
    return edges


# ---------------------------------------------------------------------------
# Braille rendering (from ascii-image-converter approach)
# Each braille char encodes a 2×4 pixel block → 4× effective resolution
# ---------------------------------------------------------------------------
def image_to_braille(img, width, threshold=128, invert=False, dither=False):
    """Convert grayscale PIL image to braille unicode art."""
    # Each braille char covers 2 pixels wide × 4 pixels tall
    char_cols = width
    img_width = char_cols * 2
    aspect_ratio = img.height / img.width
    img_height_pixels = int(img_width * aspect_ratio)
    # Round up to multiple of 4 for clean braille rows
    char_rows = (img_height_pixels + 3) // 4
    img_height = char_rows * 4

    img = img.resize((img_width, img_height))
    img = img.convert("L")

    # Get pixel data as 2D array
    pixels = []
    for y in range(img_height):
        row = []
        for x in range(img_width):
            row.append(float(img.getpixel((x, y))))
        pixels.append(row)

    if dither:
        pixels = floyd_steinberg_dither(pixels, 2)

    lines = []
    for row in range(char_rows):
        line = ""
        for col in range(char_cols):
            bits = 0
            for dy in range(4):
                for dx in range(2):
                    py = row * 4 + dy
                    px = col * 2 + dx
                    if py < img_height and px < img_width:
                        pixel_on = pixels[py][px] > threshold
                        if invert:
                            pixel_on = not pixel_on
                        if pixel_on:
                            bits |= BRAILLE_DOTS[dy][dx]
            line += chr(0x2800 + bits)
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core image-to-ASCII conversion
# ---------------------------------------------------------------------------
def image_to_ascii(path, width=80, charset="basic", invert=False,
                   color=False, dither=False, edge=False, html=False):
    """Convert an image file to ASCII art string.

    Techniques borrowed from:
    - vietnh1009/ASCII-generator: color image output, cell averaging
    - video-to-ascii: proper luminance, ANSI color, saturation
    - ascii-image-converter: braille mode, dithering
    - pic2ascii: edge detection
    """
    if Image is None:
        return "Error: Pillow is not installed. Run: pip3 install Pillow"

    # Validate width bounds
    width = max(10, min(width, MAX_WIDTH))

    img_path = Path(path)
    if not img_path.exists():
        return f"Error: File not found: {path}"

    # Validate file extension
    if img_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return f"Error: Unsupported file type: {img_path.suffix}. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"

    try:
        img = Image.open(img_path).convert("RGBA")
        # Composite onto white background to handle transparency
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg.convert("RGB")
    except Exception as e:
        return f"Error: Could not open image: {e}"

    # --- Braille mode (special path — binary dots, not brightness chars) ---
    if charset == "braille":
        gray = img.convert("L")
        return image_to_braille(gray, width, invert=invert, dither=dither)

    chars = CHARSETS.get(charset, CHARSETS["basic"])
    if invert:
        chars = chars[::-1]

    # Resize with aspect ratio correction
    aspect_ratio = img.height / img.width
    new_height = int(width * aspect_ratio * 0.55)
    if new_height < 1:
        new_height = 1
    img = img.resize((width, new_height), Image.LANCZOS)

    # Keep RGB copy for color mode
    rgb_img = img.copy()

    # Convert to grayscale using proper luminance
    gray = img.convert("L")

    # Get pixel data as 2D arrays
    gray_pixels = []
    for y in range(new_height):
        row = []
        for x in range(width):
            row.append(float(gray.getpixel((x, y))))
        gray_pixels.append(row)

    # --- Edge detection overlay ---
    if edge:
        edges = sobel_edge_detect(gray_pixels, width, new_height)
        # Blend: boost brightness where edges are strong
        for y in range(new_height):
            for x in range(width):
                edge_strength = edges[y][x] / 255
                # Mix: darken at edges (make them more visible in ASCII)
                gray_pixels[y][x] = gray_pixels[y][x] * (1 - edge_strength * 0.7)

    # --- Floyd-Steinberg dithering ---
    if dither:
        gray_pixels = floyd_steinberg_dither(gray_pixels, len(chars))

    # --- Map pixels to characters ---
    num_chars = len(chars)
    lines = []

    if html:
        lines.append('<pre style="font-family:monospace;font-size:8px;line-height:1.0;letter-spacing:0px;background:#000;color:#fff;display:inline-block;padding:8px;">')

    for y in range(new_height):
        row_parts = []
        for x in range(width):
            brightness = max(0, min(255, gray_pixels[y][x]))
            char_index = int(brightness / 256 * num_chars)
            char_index = min(char_index, num_chars - 1)
            ch = chars[char_index]

            if color or html:
                r, g, b = rgb_img.getpixel((x, y))
                if html:
                    safe_ch = html_module.escape(ch)
                    row_parts.append(f'<span style="color:rgb({r},{g},{b})">{safe_ch}</span>')
                else:
                    row_parts.append(colorize_char_truecolor(ch, r, g, b))
            else:
                row_parts.append(ch)

        lines.append("".join(row_parts))

    if html:
        lines.append("</pre>")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Text banner
# ---------------------------------------------------------------------------
def text_to_banner(text, char="#"):
    """Render text as a large ASCII banner using the embedded bitmap font."""
    text = text.upper()
    rows = ["", "", "", "", ""]

    for i, c in enumerate(text):
        glyph = FONT.get(c)
        if glyph is None:
            glyph = FONT.get("?", ["?????"] * 5)

        for row_idx in range(5):
            if i > 0:
                rows[row_idx] += " "
            line = glyph[row_idx]
            if char != "#":
                line = line.replace("#", char)
            rows[row_idx] += line

    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def demo():
    """Show examples of all features."""
    print("=" * 65)
    print("  ASCII Art Generator — Demo")
    print("  Inspired by: ASCII-generator, ascii-image-converter,")
    print("  video-to-ascii, gradscii-art, AsciiArtist")
    print("=" * 65)

    print("\n--- Text Banners ---\n")
    print(text_to_banner("HELLO"))
    print()
    print(text_to_banner("WORLD", char="*"))

    print("\n--- Character Sets ---\n")
    for name in ["dense", "basic", "block"]:
        chars = CHARSETS[name]
        count = len(chars) if name != "braille" else 256
        print(f"  {name:8s} ({count:3d} chars): {chars}")
    print(f"  {'braille':8s} (256 patterns): Unicode 2×4 dot grid (U+2800–U+28FF)")

    print("\n--- Gradients ---\n")
    for name in ["basic", "dense", "block"]:
        chars = CHARSETS[name]
        bar = ""
        for i in range(60):
            idx = min(int(i / 60 * len(chars)), len(chars) - 1)
            bar += chars[idx]
        print(f"  {name:6s}: {bar}")

    # Braille gradient demo
    braille_bar = ""
    for i in range(60):
        # Fill proportional dots in a single-row braille char
        fill = i / 60
        bits = 0
        for dot_idx, bit_val in enumerate([0x01, 0x08, 0x02, 0x10, 0x04, 0x20, 0x40, 0x80]):
            if dot_idx / 8 < fill:
                bits |= bit_val
        braille_bar += chr(0x2800 + bits)
    print(f"  {'braille':6s}: {braille_bar}")

    print("\n--- New Features ---\n")
    print("  --color     ANSI 24-bit truecolor output (terminal)")
    print("  --dither    Floyd-Steinberg error diffusion")
    print("  --edge      Sobel edge detection overlay")
    print("  --html      Color HTML output (shareable)")
    print("  braille     2×4 dot grid charset (4× resolution)")

    print("\n--- Usage Examples ---\n")
    print("  # Basic")
    print("  python3 ascii_art.py image photo.jpg --width 80")
    print()
    print("  # High detail with color")
    print("  python3 ascii_art.py image photo.jpg --charset dense --color")
    print()
    print("  # Braille mode (highest resolution)")
    print("  python3 ascii_art.py image photo.jpg --charset braille --width 100")
    print()
    print("  # Edge-detected + dithered")
    print("  python3 ascii_art.py image photo.jpg --edge --dither --charset block")
    print()
    print("  # Color HTML export (open in browser)")
    print("  python3 ascii_art.py image photo.jpg --color --html --output art.html")
    print()
    print("  # Text banners")
    print("  python3 ascii_art.py text \"GONE MISSIN\" --char @")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="ASCII Art Generator — images & text to ASCII/braille/color art."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- image subcommand ---
    img_parser = subparsers.add_parser("image", help="Convert an image to ASCII art")
    img_parser.add_argument("path", help="Path to image file")
    img_parser.add_argument(
        "--width", type=int, default=80,
        help="Output width in characters (default: 80, max: 500)",
    )
    img_parser.add_argument(
        "--charset", choices=["dense", "basic", "block", "braille"], default="basic",
        help="Character set: dense (69 chars), basic (10), block (5 Unicode), braille (2×4 dots)",
    )
    img_parser.add_argument(
        "--invert", action="store_true",
        help="Invert brightness (for dark terminal backgrounds)",
    )
    img_parser.add_argument(
        "--color", action="store_true",
        help="ANSI 24-bit truecolor output",
    )
    img_parser.add_argument(
        "--dither", action="store_true",
        help="Floyd-Steinberg error diffusion dithering",
    )
    img_parser.add_argument(
        "--edge", action="store_true",
        help="Sobel edge detection overlay (emphasizes outlines)",
    )
    img_parser.add_argument(
        "--html", action="store_true",
        help="Output as color HTML (implies --color)",
    )
    img_parser.add_argument("--output", help="Save output to file instead of stdout")

    # --- text subcommand ---
    txt_parser = subparsers.add_parser("text", help="Render text as ASCII banner")
    txt_parser.add_argument("text", help="Text to render")
    txt_parser.add_argument(
        "--char", default="#",
        help="Character to use for the banner (default: #)",
    )
    txt_parser.add_argument("--output", help="Save output to file instead of stdout")

    # --- demo subcommand ---
    subparsers.add_parser("demo", help="Show demo of all features")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "demo":
        demo()
        return

    if args.command == "image":
        if args.html:
            args.color = True
        result = image_to_ascii(
            args.path,
            width=args.width,
            charset=args.charset,
            invert=args.invert,
            color=args.color,
            dither=args.dither,
            edge=args.edge,
            html=args.html,
        )
        if result.startswith("Error:"):
            print(result, file=sys.stderr)
            sys.exit(1)

    elif args.command == "text":
        result = text_to_banner(args.text, char=args.char)

    # Output handling
    if hasattr(args, "output") and args.output:
        out_path = Path(args.output).resolve()
        # Block writing to system directories
        blocked_prefixes = ("/etc", "/usr", "/bin", "/sbin", "/var", "/System", "/Library")
        if any(str(out_path).startswith(p) for p in blocked_prefixes):
            print(f"Error: Cannot write to system directory: {out_path}", file=sys.stderr)
            sys.exit(1)
        out_path.write_text(result + "\n")
        print(f"Saved to {out_path}")
    else:
        print(result)


if __name__ == "__main__":
    main()
