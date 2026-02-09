---
title: "APCA: Accessible Perceptual Contrast Algorithm (Future of WCAG 3)"
source: "Myndex / APCA Documentation"
url: "https://git.apcacontrast.com/documentation/APCA_in_a_Nutshell.html"
date: "2026-02-09"
tags:
  - accessibility
  - color-contrast
  - apca
  - wcag-3
  - dark-mode
  - perceptual
  - art-director
  - don-norman
---

# APCA: Accessible Perceptual Contrast Algorithm

## Overview

APCA is the candidate contrast method for future WCAG 3 standards. It is a perceptually-based contrast calculation method designed specifically for readable text and content on self-illuminated RGB displays. It forms part of the S-Luv Accessible Color Appearance Model (SACAM).

## Core Concept: Lightness Contrast (Lc)

APCA generates a lightness/darkness contrast value that "represents the same perceived readability contrast" regardless of color darkness levels. This differs fundamentally from WCAG 2.x, which "overstates contrast for dark colors to the point that 4.5:1 can be functionally unreadable when one of the colors in a pair is near black."

The algorithm produces Lc values ranging from 0 to 105+, with perceptually uniform scaling -- doubling or halving the value corresponds to doubling or halving perceived contrast.

## Why APCA Over WCAG 2.x Ratios?

- WCAG 2 overstates contrast for dark colors -- 4.5:1 can be functionally unreadable near black
- WCAG 2 contrast cannot reliably guide "dark mode" design
- APCA asks "How readable is this text for a human viewer?" instead of "Do these two colors meet a fixed ratio?"
- Traditional WCAG 2.x relies on static luminance ratios that assume the eye responds linearly to light -- but human vision does not work that way
- We perceive contrast differently depending on polarity, surrounding brightness, color saturation, and typographic detail

## Lc Value Thresholds and Use Cases

APCA employs a sliding scale approach rather than binary pass/fail scoring:

| Lc Value | Use Case | Minimum Font Requirements |
|----------|----------|--------------------------|
| **Lc 90** | Body text, fluent reading | 18px/weight 300, 14px/weight 400 |
| **Lc 75** | Body text columns | 24px/300, 18px/400, 16px/500, 14px/700 |
| **Lc 60** | Content text (non-body) | 48px/200, 36px/300, 24px/400, 21px/500, 18px/600, 16px/700 |
| **Lc 45** | Headlines, large text | 36px normal weight or 24px bold |
| **Lc 30** | "Spot readable" text, icons | Placeholder text, disabled elements, pictograms with fine details |
| **Lc 15** | Non-semantic elements | Dividers, outlines; treat below this as "invisible" for many users |

## Font Sizing Notes

- Measurements assume x-height ratio of 0.52
- "px" refers to CSS reference pixels (1.278 arc minutes of visual angle)
- Font weights are standardized against Helvetica/Arial
- Different fonts require adjustment: Times New Roman's 0.45 x-height ratio necessitates ~16% size increase
- Font weights should be compared directly -- Raleway 400 approximates Helvetica 300

## Key Differences from WCAG 2

| Aspect | WCAG 2.x | APCA |
|--------|----------|------|
| Measurement | Static luminance ratios | Perceptual lightness contrast |
| Dark mode | Cannot guide dark mode design | Accurate for dark backgrounds |
| Scoring | Binary pass/fail | Ranges tied to use cases |
| User model | Assumes linear eye response | Models actual human perception |
| Flexibility | One size fits all | Font weight/size lookup tables |

## Dark Mode Guidance

APCA highlights that dark mode and light mode should not be treated as simple inversions of each other:
- Avoid highly saturated or extremely bright text on near-black backgrounds
- Softer off-white text, reduced saturation, and slightly elevated background tones help prevent halation and eye strain
- Even if it "passes" legacy ratios, extreme contrast in dark mode causes readability problems

## Implementation Levels

The APCA Readability Criterion offers optional Silver and Gold levels:
- **Silver**: Basic lookup tables for font weight/size vs. Lc value
- **Gold**: Greater design precision and flexibility

## Resources

- [APCA Calculator](https://apcacontrast.com) -- real-time font size and weight testing
- [ARC Guidelines](https://readtech.org/ARC/) -- Inclusive Reading Technologies
- [GitHub: Myndex/SAPC-APCA](https://github.com/Myndex/SAPC-APCA) -- source code and documentation
