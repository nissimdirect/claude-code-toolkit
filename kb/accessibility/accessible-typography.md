---
title: "Accessible Fonts and Typography Guidelines"
source: "Section508.gov + WebAIM"
url: "https://www.section508.gov/develop/fonts-typography/"
date: "2026-02-09"
tags:
  - accessibility
  - typography
  - fonts
  - readability
  - wcag
  - art-director
  - don-norman
---

# Accessible Fonts and Typography Guidelines

## Definition of Accessible Fonts

An accessible font is "a typeface designed for easy reading by a diverse audience, including individuals with visual impairments such as low vision or reading disability such as dyslexia."

## Why Sans Serif for Digital

For people with low vision, serifs "significantly degrade legibility." Since digital content is screen-based rather than print, sans serif fonts are particularly important for body text. Serif fonts may be used for headings or emphasis.

## Font Size Recommendations

| Context | Recommended Size |
|---------|------------------|
| Body text (websites/documents) | 11-12 pt or 15-16 px |
| Email text | 10-11 pt or 13-15 px |
| Minimum when user cannot adjust | 16 pt (3/16 inch) |

**Never go below 16px for body text** -- this is the minimum for comfortable reading.

## WCAG Text Spacing Requirements (SC 1.4.12 -- Level AA)

Content must not lose functionality when users adjust these properties:

- **Line height**: at least 1.5x the font size
- **Paragraph spacing**: at least 2x the font size
- **Letter spacing**: at least 0.12x the font size
- **Word spacing**: at least 0.16x the font size

## How We Read

Readers don't process individual characters. Instead, eyes scan patterns of 6-9 characters at a time, converting them to meaning almost instantaneously. Barriers to this process require slower, character-by-character analysis.

## Key Typography Principles for Accessibility

### 1. Use Simple, Familiar Fonts

"Simple, familiar typefaces are easiest to parse and read because the mind already has or can quickly generate a model for the shapes and patterns of text." No single typeface works best for all users -- prioritize simplicity and familiarity.

### 2. Reduce Character Complexity

Complex, decorative typefaces slow comprehension, especially in extended text passages. Simpler character shapes allow faster mental analysis.

### 3. Eliminate Character Ambiguity

Similar-looking characters (like capital I, lowercase l, and numeral 1) create confusion. Select typefaces with clear visual distinctions between potentially confusing glyphs.

### 4. Limit Typeface Variety

Each new typeface requires cognitive mapping effort. "Each time you encounter a new typeface, font, or font variation, your mind must build a map or model." Use one typeface for headings and another for body text -- not multiple variations throughout.

### 5. Optimize Spacing and Weight

Adequate letter and word spacing improves clarity. Font weight (thickness) also affects readability. Ensure letters and words don't appear cramped.

### 6. Maintain Proper Contrast

Text needs sufficient brightness difference from background. Black on white provides standard contrast, though dark grey on white reduces eye fatigue. Excessive contrast may create visual artifacts affecting dyslexic readers.

### 7. Avoid Small Font Sizes

While WCAG lacks minimum font size requirements, larger text improves readability. Use relative units (percentages, ems, rems) rather than absolute measurements (pixels, points) for better flexibility.

## Implementation: Use Relative Units

Use flexible units like `em` or `rem` instead of fixed pixel values. This allows content to scale proportionally when users adjust spacing:

- **`em`**: relative to the parent element
- **`rem`**: relative to the root (`<html>`) element

## Text Styling Caution

Avoid extensive use of entirely bold, italicized, capitalized, or unusual text styling. "Each new variation requires some orientation by the user," slowing comprehension.

## Real Text vs. Text in Images

Real text rendered as characters offers significant advantages:

- Users can customize spacing, font, color, and size
- Text remains searchable and copyable
- Scales without loss of quality
- Works across devices and bandwidth conditions

WCAG guidelines state: "If the same visual presentation can be made using text alone, an image is not used to present that text."

## Additional WCAG Success Criteria

- **1.4.3 Contrast**: Text must have a contrast ratio of at least 4.5:1
- **1.4.4 Resize Text**: Users must resize text to at least 200% without loss of content or functionality
- **1.4.5 Images of Text**: Use actual text rather than images of text whenever possible
- **1.4.10 Reflow**: Content should not require horizontal scrolling when magnified

## Testing

The **Text Spacing Bookmarklet** allows developers to test compliance by automatically applying WCAG spacing recommendations to websites, revealing potential layout issues. Manual testing is equally important -- automated tools should complement human review.
