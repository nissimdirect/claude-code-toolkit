---
title: "Target Sizes and Touch Targets: Complete Accessibility Guide"
source: "TetraLogical + AllAccessible"
url: "https://tetralogical.com/blog/2022/12/20/foundations-target-size/"
date: "2022-12-20"
tags:
  - accessibility
  - touch-targets
  - target-size
  - wcag
  - interaction-design
  - mobile
  - art-director
  - don-norman
---

# Target Sizes and Touch Targets: Complete Accessibility Guide

## What Are Target Sizes?

A target size represents "the area that can be activated in order to interact with an element." For people with dexterity challenges, motor control difficulties, or those using alternative input devices, adequate target sizing is essential for usable web experiences.

The average adult finger pad measures approximately 10mm (44 CSS pixels at standard density).

## WCAG Requirements

### WCAG 2.1 -- SC 2.5.5 Target Size (AAA Level)
Target sizes must be no smaller than **44x44 pixels** for all pointer inputs (mouse, stylus, touch).

### WCAG 2.2 -- SC 2.5.8 Target Size Minimum (AA Level)
The new criterion introduces more flexibility:
- **Absolute minimum**: 24x24 CSS pixels
- **Spacing exception**: Undersized targets may pass if they have sufficient spacing (non-overlapping 24-pixel diameter circles around each target)
- Focuses on preventing accidental activation of adjacent targets

**Exceptions to 2.5.8:**
- Inline targets constrained by line-height (e.g., links within paragraphs)
- User-agent-controlled sizes (browser default controls)
- Equivalent controls available elsewhere on the same page
- Essential presentations where size is critical to information conveyed

## Industry Platform Standards

| Platform | Minimum Target Size | Notes |
|----------|-------------------|-------|
| **Apple (iOS/macOS)** | 44x44 points | "Minimum tappable area for all controls" |
| **Google Material Design** | 48x48 dp | Standard touch target |
| **Google Design for Driving** | 76x76 dp | For divided-attention contexts |
| **WCAG 2.1 (AAA)** | 44x44 CSS px | Strict requirement |
| **WCAG 2.2 (AA)** | 24x24 CSS px | With spacing allowances |

## Spacing Best Practices

### Why Spacing Matters
- Prevents accidental activation of neighboring controls
- Allows for imprecise targeting (tremors, moving vehicle, one-handed use)
- The BBC's "exclusion zones" concept demonstrates effective tap target separation

### Key Principles
- **Padding increases effective target size** without enlarging the visible icon
- Use CSS padding rather than margin for larger touch areas
- Maintain visual relationships between related controls -- excessive spacing weakens perceived connections
- Consider the context: driving, walking, or moving users need larger targets and more spacing

## Implementation Tips

### During Design
- Use design tools (Figma, Sketch) to verify dimensions and spacing
- Hold Alt/Option to measure spacing between elements
- Design for the smallest comfortable target first, then ensure desktop is adequate

### During Development
- Inspect elements using browser developer tools
- Account for padding and spacing when calculating actual target size
- Document target sizes and spacing in design systems
- Use `min-width` and `min-height` in CSS to enforce minimums

### Common Pitfalls
- Icon buttons with no padding (visual icon is 16px but needs 44px touch area)
- Close buttons in modals and banners (often too small)
- Navigation links too close together on mobile
- Form checkboxes and radio buttons at default browser size
- Inline links within dense text

## Testing

- Verify dimensions in browser DevTools
- Test on actual mobile devices (not just simulators)
- Test with users who have motor impairments
- Check all interactive states (expanded menus, dropdowns, overlays)
- Consistently apply target sizes across all components and pages

## Key Recommendation

Aim for **44x44 pixels** as the practical minimum for all interactive elements, even though WCAG 2.2 AA allows 24x24. The larger target size provides a better experience for everyone, especially mobile users, older adults, and people with motor disabilities.
