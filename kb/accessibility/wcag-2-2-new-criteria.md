---
title: "WCAG 2.2: All 9 New Success Criteria Explained"
source: "W3C WAI + AllAccessible"
url: "https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/"
date: "2023-10-05"
tags:
  - accessibility
  - wcag
  - wcag-2-2
  - standards
  - compliance
  - don-norman
  - art-director
---

# WCAG 2.2: All 9 New Success Criteria Explained

WCAG 2.2 was published as a W3C Recommendation on October 5, 2023, introducing 9 additional success criteria beyond WCAG 2.1. One criterion was removed: 4.1.1 Parsing is now obsolete.

## Level A Criteria (3 total)

### 3.2.6 Consistent Help -- Level A

**Requirement:** Help mechanisms appearing on multiple pages must occur in the same relative order to other content unless the user initiates a change.

**Help types covered:**
- Human contact details
- Human contact mechanisms
- Self-help options
- Fully automated contact mechanisms

**Why:** Users with cognitive disabilities locate assistance more easily when positioned consistently.

### 3.3.7 Redundant Entry -- Level A

**Requirement:** Information requested multiple times within the same process must be auto-populated or selectable by users.

**Exceptions:** Re-entry is essential, required for security, or previously entered data is no longer valid.

**Why:** Users with cognitive disabilities struggle to recall previously entered information.

### 3.3.9 Accessible Authentication (Enhanced) -- Level AAA (listed here for grouping)

**Requirement:** Authentication cannot require object recognition or identification of user-supplied images/media unless alternatives exist.

## Level AA Criteria (6 total) -- The Legal Compliance Standard

### 2.4.11 Focus Not Obscured (Minimum) -- Level AA

**Requirement:** Ensure keyboard-focused components remain at least partially visible and are not entirely hidden by author-created content.

**Why:** People unable to use mice depend on seeing where keyboard focus is positioned. Sticky headers, cookie banners, and floating menus can hide focused elements.

### 2.5.7 Dragging Movements -- Level AA

**Requirement:** Provide single-pointer alternatives for any drag-dependent functionality, unless dragging is essential or user-agent-determined.

**Why:** Users with hand tremors or motor control limitations cannot reliably perform drag operations.

### 2.5.8 Target Size (Minimum) -- Level AA

**Requirement:** Pointer targets must be at least 24x24 CSS pixels, or undersized targets must have adequate spacing so non-overlapping 24-pixel circles fit around each.

**Exceptions:** Inline targets constrained by line-height, user-agent-controlled sizes, equivalent controls on the same page, or essential presentations.

**Why:** People with physical impairments require adequate target spacing to avoid accidental clicks.

### 3.3.8 Accessible Authentication (Minimum) -- Level AA

**Requirement:** Authentication processes cannot require cognitive function tests (memorizing passwords, solving puzzles, transcribing codes) unless alternatives are provided.

**Acceptable alternatives:**
- Non-cognitive authentication methods
- Mechanisms assisting with cognitive tests
- Object recognition tasks
- Recognition of user-provided content

**Why:** Cognitive disabilities prevent successful completion of memory-based or puzzle-solving authentication.

## Level AAA Criteria (2 total)

### 2.4.12 Focus Not Obscured (Enhanced) -- Level AAA

**Requirement:** Ensure keyboard-focused components are fully visible with no parts hidden by author-created content. Stricter than the AA version.

### 2.4.13 Focus Appearance -- Level AAA

**Requirement:** Focus indicators must be at least as large as a 2 CSS pixel perimeter around the unfocused component and maintain a 3:1 contrast ratio between focused and unfocused states.

**Why:** Many users, including older adults, struggle to detect small visual changes.

## Implementation Priority

**Phase 1 (Weeks 1-2):** Target size requirements, redundant entry prevention, consistent help placement

**Phase 2 (Weeks 3-4):** Accessible authentication, dragging movement alternatives

**Phase 3 (Weeks 5-6):** Focus obscuring fixes, focus visibility enhancements

**Phase 4 (Future):** AAA-level criteria for specialized contexts

## Legal Context

- U.S. courts increasingly cite WCAG 2.2 in ADA lawsuits (4,605 filed in 2024)
- EU Accessibility Act (effective June 2025) enforces compliance with potential penalties reaching 100,000 EUR or 4% annual revenue
- Section 508 updates expected by 2026
- Automated tools detect only ~40% of issues -- manual testing required
