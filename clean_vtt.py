#!/usr/bin/env python3
"""Clean VTT subtitle files into readable transcript text.

Removes timestamps, duplicate lines, and formatting tags.
Outputs clean paragraph text suitable for markdown articles.
"""

import re
import sys
from pathlib import Path


def clean_vtt(vtt_path: Path) -> str:
    """Convert VTT subtitle file to clean text."""
    text = vtt_path.read_text(encoding="utf-8")

    lines = []
    seen = set()

    for line in text.split("\n"):
        # Skip VTT headers, timestamps, and sequence numbers
        if line.startswith("WEBVTT"):
            continue
        if line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.match(r"^\d+$", line.strip()):
            continue
        if "-->" in line:
            continue
        if "align:start" in line or "position:" in line:
            continue

        # Remove inline timestamp tags like <00:00:15.420><c>
        cleaned = re.sub(r"<[^>]+>", "", line).strip()

        if not cleaned or cleaned in seen:
            continue

        # Skip [Music], [Applause] etc.
        if re.match(r"^\[.*\]$", cleaned):
            continue

        seen.add(cleaned)
        lines.append(cleaned)

    # Join into paragraphs (group by sentence endings)
    text = " ".join(lines)
    # Clean up multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Add paragraph breaks at natural points (roughly every 3-4 sentences)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    paragraphs = []
    current = []
    for i, sent in enumerate(sentences):
        current.append(sent)
        if len(current) >= 4 or i == len(sentences) - 1:
            paragraphs.append(" ".join(current))
            current = []

    return "\n\n".join(paragraphs)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 clean_vtt.py <vtt_file_or_directory>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if path.is_file():
        print(clean_vtt(path))
    elif path.is_dir():
        for vtt in sorted(path.glob("*.vtt")):
            output = vtt.with_suffix(".txt")
            cleaned = clean_vtt(vtt)
            output.write_text(cleaned, encoding="utf-8")
            words = len(cleaned.split())
            print(f"  {vtt.name} -> {output.name} ({words} words)")
    else:
        print(f"Not found: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
