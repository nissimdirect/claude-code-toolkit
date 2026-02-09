---
title: "Text Spacing and WCAG 1.4.12: Complete Implementation Guide"
source: "The A11Y Collective"
url: "https://www.a11y-collective.com/blog/text-spacing-wcag/"
date: "2026-02-09"
tags:
  - accessibility
  - typography
  - text-spacing
  - wcag
  - css
  - don-norman
  - art-director
---

# Text Spacing and WCAG 1.4.12: Complete Implementation Guide

## Overview

Text spacing is a critical but often overlooked aspect of web accessibility. Poor spacing makes content difficult to read and understand, especially for users with low vision, dyslexia, or cognitive disabilities.

## Three Categories of Text Spacing

1. **Line spacing (line-height)** -- vertical distance between text lines
2. **Letter spacing (letter-spacing)** -- proximity of individual characters
3. **Word spacing (word-spacing)** -- separation between words

## WCAG 1.4.12 Text Spacing -- Level AA

Content must not lose functionality or information when users override these spacing properties:

| Property | Minimum Value | CSS Property | Example (16px base) |
|----------|--------------|--------------|---------------------|
| Line height | 1.5x font size | `line-height` | 24px |
| Paragraph spacing | 2x font size | `margin-bottom` | 32px |
| Letter spacing | 0.12x font size | `letter-spacing` | 1.92px |
| Word spacing | 0.16x font size | `word-spacing` | 2.56px |

**Key point:** The criterion does not require you to SET these values. It requires that content does not break when users OVERRIDE to these values.

## Implementation Best Practices

### Use Relative Units

Use flexible units like `em` or `rem` instead of fixed pixel values:

```css
/* Good - scales proportionally */
body {
  font-size: 1rem;         /* 16px base */
  line-height: 1.5;        /* 1.5x font size */
  letter-spacing: 0.12em;  /* 0.12x font size */
  word-spacing: 0.16em;    /* 0.16x font size */
}

p + p {
  margin-top: 2em;         /* 2x font size */
}

/* Bad - fixed values that don't scale */
body {
  font-size: 16px;
  line-height: 24px;
  letter-spacing: 2px;
}
```

- **`em`**: relative to the parent element's font size
- **`rem`**: relative to the root (`<html>`) element's font size

### Avoid Fixed-Height Containers

Do not use fixed heights on text containers. When users increase spacing, text expands and can overflow fixed containers, causing:
- Text overlapping other content
- Text being clipped/hidden by `overflow: hidden`
- Buttons and navigation items breaking layout

```css
/* Bad */
.card { height: 200px; overflow: hidden; }

/* Good */
.card { min-height: 200px; }
```

### Common Issues When Spacing Adjusts

Watch for these problems when testing with adjusted spacing:
- Buttons disappearing or shifting position
- Navigation menus covering content
- Text breaking containers and overlapping
- Reduced contrast making text unreadable
- Form labels separating from their inputs

## Connection to Other WCAG Criteria

- **SC 1.4.4 Resize Text** -- Content must support 200% text zoom without loss of functionality
- **SC 1.4.10 Reflow** -- Content must reflow without horizontal scrolling at 400% zoom (320px viewport)
- Implementing flexible spacing supports both of these criteria naturally

## Testing Methods

### Text Spacing Bookmarklet
A JavaScript bookmarklet that automatically applies WCAG 1.4.12 minimum spacing values to any website. Drag it to your bookmarks bar, then click on any page to test.

The bookmarklet applies:
```css
* {
  line-height: 1.5 !important;
  letter-spacing: 0.12em !important;
  word-spacing: 0.16em !important;
}
p {
  margin-bottom: 2em !important;
}
```

### Manual Testing Process
1. Apply the bookmarklet or manually set CSS overrides
2. Check all pages for content loss or overlap
3. Verify all interactive elements remain functional
4. Test on different viewport sizes
5. Check form fields, buttons, and navigation

### Automated Testing
Automated tools can detect fixed heights and overflow:hidden, but manual review is essential to catch visual issues computers might miss.

## Design System Recommendations

When building a design system:
- Define spacing tokens using relative units
- Test all components with WCAG spacing overrides
- Document minimum container sizes
- Use CSS Grid or Flexbox for layouts that accommodate text expansion
- Never clip text content with overflow:hidden on text containers
