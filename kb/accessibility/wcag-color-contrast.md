---
title: "Contrast and Color Accessibility: WCAG 2 Requirements"
source: "WebAIM"
url: "https://webaim.org/articles/contrast/"
date: "2026-02-09"
tags:
  - accessibility
  - color-contrast
  - wcag
  - visual-design
  - art-director
  - don-norman
---

# Contrast and Color Accessibility: WCAG 2 Requirements

## Introduction

Contrast and color use are essential for accessibility, ensuring all users -- particularly those with visual disabilities -- can perceive page content.

## Defining Colors

Colors can be defined through multiple formats:

- **RGB**: `rgb(97, 97, 255)` -- values 0-255 for red, green, blue
- **Hexadecimal**: `#6161FF` -- six-character format commonly used in webpages
- **HSL**: `hsl(240, 100%, 69%)` -- hue, saturation, and lightness more closely match human perception

**Alpha (opacity)** ranges from 0 (transparent) to 1 (opaque) and affects contrast ratios.

## WCAG 2 Contrast Ratio

Contrast measures perceived brightness difference between two colors, expressed as a ratio from 1:1 to 21:1. Examples on white backgrounds:

- Pure red (#FF0000): 4:1
- Pure green (#00FF00): 1.4:1
- Pure blue (#0000FF): 8.6:1

**Important**: Swapping text and background colors preserves the same contrast ratio.

## Success Criterion 1.4.3: Contrast (Minimum) -- Level AA

### Primary Requirements

"The visual presentation of text and images of text has a contrast ratio of at least 4.5:1," with exceptions for:

**Large Text**: 3:1 ratio for text 18pt+ or 14pt+ bold (approximately 24px or 18.67px)

**Incidental Text**: No requirement for:
- Inactive UI components
- Pure decoration
- Hidden text
- Text within images not essential to understanding

**Logotypes**: Brand names and logos exempt from requirements

### Images of Text

Contrast requirements apply to text within graphics. Text effects like outlines or halos can impact perceived contrast when measured.

### Special Considerations

**Gradients, backgrounds, and transparency**: Test areas with lowest contrast; WCAG provides no specific guidance.

**Interactive states**: Text in hover, focus, or active states must meet the same 4.5:1 ratio independently.

## Success Criterion 1.4.6: Contrast (Enhanced) -- Level AAA

More stringent requirements: 7:1 for normal text, 4.5:1 for large text. Level AA conformance (1.4.3) remains standard practice.

## Success Criterion 1.4.11: Non-text Contrast -- Level AA

Applies to visual elements beyond text, requiring 3:1 contrast "against adjacent color(s)."

### User Interface Components

All interactive controls need 3:1 contrast, including all states (hover, focus, active). **Exception**: Default browser styles are exempt from requirements.

**Example**: Custom checkboxes, buttons, and form inputs must maintain 3:1 contrast in all states.

### Graphical Objects

Graphics must have 3:1 contrast when "required to understand the content," except:
- When a textual alternative provides the information
- When presentation style is essential (heat maps, photos, logos)

## Success Criterion 1.4.1: Use of Color -- Level A

"Color is not used as the only visual means of conveying information, indicating an action, prompting a response, or distinguishing a visual element."

### Applications

**Forms**: Required fields and errors need additional indicators -- icons, text labels, or borders -- beyond color alone.

**Links**: When removing underlines, links need:
1. 3:1 contrast with body text
2. Visual cue (not color change) on focus/hover
3. 4.5:1 contrast with background

Meeting all three simultaneously can prove challenging.

## Key Takeaways

- Minimum 4.5:1 contrast required for standard text; cannot round up
- Large text requires only 3:1
- Non-text elements need 3:1 against adjacent colors
- Color alone cannot convey critical information
- All interactive states require consistent contrast ratios
- Test comprehensively across backgrounds and states
