# Jacob Collier Harmony & Music Theory Reference

> Comprehensive reference for encoding Jacob Collier's harmonic concepts into
> algorithmic music composition systems. Covers negative harmony, microtonal
> modulation, Super-Ultra-Hyper-Mega-Meta scales, reharmonization, audience
> harmony, polytonality, harmonic gravity, and production philosophy.
>
> **Sources:** Web research from interviews, masterclasses, academic analyses,
> music theory blogs, and code implementations. February 2026.

---

## Table of Contents

1. [Negative Harmony (Ernst Levy / Collier)](#1-negative-harmony)
2. [The Five Levels of Harmony](#2-the-five-levels-of-harmony)
3. [Super-Ultra-Hyper-Mega-Meta Scales](#3-super-ultra-hyper-mega-meta-scales)
4. [Microtonal Harmony & Just Intonation](#4-microtonal-harmony--just-intonation)
5. [The Four Magical Chords](#5-the-four-magical-chords)
6. [Reharmonization Techniques](#6-reharmonization-techniques)
7. [Circle of Fifths: Brighten & Darken](#7-circle-of-fifths-brighten--darken)
8. [Harmonic Gravity](#8-harmonic-gravity)
9. [Audience-Driven Harmony](#9-audience-driven-harmony)
10. [Polytonality & Polytonal Voice Leading](#10-polytonality--polytonal-voice-leading)
11. [Rhythm & Polyrhythm](#11-rhythm--polyrhythm)
12. [Production & Arrangement Philosophy](#12-production--arrangement-philosophy)
13. [The Harmonizer Instrument](#13-the-harmonizer-instrument)
14. [Ernst Levy's Polarity Theory (Deep Dive)](#14-ernst-levys-polarity-theory)
15. [Steve Coleman's Symmetrical Movement](#15-steve-colemans-symmetrical-movement)
16. [George Russell's Lydian Chromatic Concept](#16-george-russells-lydian-chromatic-concept)
17. [Esoteric Concepts & Philosophy](#17-esoteric-concepts--philosophy)
18. [Algorithmic Implementation Reference](#18-algorithmic-implementation-reference)
19. [Key Arrangements & Analysis](#19-key-arrangements--analysis)
20. [Sources & Further Reading](#20-sources--further-reading)

---

## 1. Negative Harmony

### Origin

Ernst Levy (1895-1981), Swiss musicologist/composer/pianist, developed the concept
in his book *A Theory of Harmony* (published posthumously, 1985). Levy did NOT use
the term "negative harmony" himself. Jacob Collier popularized the concept in a
2017 interview with June Lee, causing Levy's out-of-print book to spike in sales.

Steve Coleman (M-BASE) independently developed practical applications of Levy's
ideas in his Symmetrical Movement Concept (1978), predating Collier by decades.

### Core Concept

Every note and chord in a key has a "negative" mirror counterpart. The reflection
occurs around an axis positioned exactly halfway between the tonic and the dominant
(perfect 5th above). This axis preserves "tonal gravity" -- the mirrored chords
carry equivalent emotional weight, tension, and resolution tendency.

### The Axis

For any key with tonic T:
- Axis sits between T and T+7 semitones (the P5)
- In practice: the axis is at T + 3.5 semitones (between the b3 and natural 3)

```
Key of C:
Axis = between Eb and E (3.5 semitones above C)

Visualization on circle of fifths:
Draw a line from the tonic through the center to the tritone.
Notes on either side of this line are mirror pairs.
```

### Complete Note Mapping (Key of C)

```
Original  ->  Negative
C         ->  G
C#/Db     ->  F#/Gb
D         ->  F
D#/Eb     ->  E
E         ->  Eb
F         ->  D
F#/Gb     ->  C#/Db
G         ->  C
G#/Ab     ->  B
A         ->  Bb
A#/Bb     ->  A
B         ->  Ab
```

**Pattern:** Each pair sums to 7 (the number of semitones in a P5).
- C(0) + G(7) = 7
- D(2) + F(5) = 7
- E(4) + Eb(3) = 7
- etc.

### Algorithmic Formula

```python
def negative_harmony_note(note_midi, tonic_midi):
    """
    Reflect a MIDI note around the negative harmony axis.

    The axis is at tonic + 3.5 semitones.
    For note N in key T: negative(N) = T + 7 - (N - T) = 2*T + 7 - N
    Simplified: negative(N) = (2 * tonic + 7 - note) % 12
    """
    note_class = note_midi % 12
    tonic_class = tonic_midi % 12
    negative_class = (2 * tonic_class + 7 - note_class) % 12
    # Preserve octave of original note
    octave = note_midi // 12
    return octave * 12 + negative_class

def negative_harmony_chord(chord_notes, tonic_midi):
    """Transform an entire chord via negative harmony."""
    return [negative_harmony_note(n, tonic_midi) for n in chord_notes]
```

### Chord Type Transformations

When you apply negative harmony, chord qualities transform predictably:

```
Original       ->  Negative
Major          ->  minor
minor          ->  Major
Major 7th      ->  minor(b6)  [or minor add b13]
minor 7th      ->  Major 6th
Dominant 7th   ->  minor 6th
minor 6th      ->  Dominant 7th
augmented      ->  augmented  (self-inverse)
diminished     ->  diminished (self-inverse)
```

### Diatonic Chord Mapping (Key of C)

```
I   (C major)   ->  i    (C minor)     [Cm]
ii  (D minor)   ->  bVII (Bb major)    [Bb]
iii (E minor)   ->  bVI  (Ab major)    [Ab]
IV  (F major)   ->  v    (G minor)     [Gm]  -- note: NOT the dominant
V   (G major)   ->  iv   (F minor)     [Fm]
vi  (A minor)   ->  bIII (Eb major)    [Eb]
vii (B dim)     ->  i dim variant
```

### Cadence Transformations

```
Original:   V7 -> I     (G7 -> C)      "Perfect cadence"
Negative:   iv6 -> i    (Fm6 -> Cm)    "Plagal-flavored cadence"

Original:   ii7 -> V7 -> I    (Dm7 -> G7 -> Cmaj7)
Negative:   Bb6 -> Fm6 -> Cm(b6)
```

Key insight from Collier: negative harmony converts **perfect cadences
into plagal-sounding cadences** while preserving equivalent tonal gravity.
"Converting perfect to plagal."

### Mode Brightness Inversion

Negative harmony inverts the brightness spectrum of modes:

```
Brightest                          Darkest
Lydian     <---mirror--->  Locrian
Ionian     <---mirror--->  Phrygian
Mixolydian <---mirror--->  Aeolian
Dorian     <---mirror--->  Dorian (SELF-INVERSE: the axis of symmetry)
```

**Algorithm:** If Lydian ascends W-W-W-H-W-W-H, reflecting those intervals
from top-down produces H-W-W-H-W-W-W = Locrian.

Dorian is the only mode that maps to itself because its interval pattern
is palindromic: W-H-W-W-W-H-W.

```python
MODE_BRIGHTNESS = ['lydian', 'ionian', 'mixolydian', 'dorian',
                   'aeolian', 'phrygian', 'locrian']

def negative_mode(mode_name):
    """Return the negative harmony mirror of a mode."""
    idx = MODE_BRIGHTNESS.index(mode_name.lower())
    mirror_idx = len(MODE_BRIGHTNESS) - 1 - idx
    return MODE_BRIGHTNESS[mirror_idx]
```

---

## 2. The Five Levels of Harmony

From Collier's WIRED video "Musician Explains One Concept in 5 Levels of
Difficulty" (with Herbie Hancock). This is Collier's taxonomy of harmonic
understanding.

### Level 1: Feeling (Child)

- Harmony = "when people sing together, and it sounds nice"
- A melody alone feels "lonely"; adding harmony transforms it emotionally
- **Algorithmic encoding:** Binary -- harmony present/absent changes emotional state

### Level 2: Triadic Harmony (Teen)

- Major triads = "happy and bright"
- Minor triads = "darker, more somber"
- Chord progressions create narrative: tension -> release
- **Algorithmic encoding:** Map chord quality to valence (major=+1, minor=-1)

### Level 3: Circle of Fifths (College Student)

- The circle of fifths as "a guide to the emotional landscape of music"
- Moving clockwise = brighter
- Moving counter-clockwise = darker
- Demonstrates reharmonization of "Amazing Grace" with altered harmonies
- **Algorithmic encoding:** Distance on circle of fifths = brightness delta

### Level 4: Harmonic Series & Reharmonization (Professional)

- Overtone series and undertone series as natural foundation
- "Every melody note can work with every bass note"
- Reharmonization = rearranging notes to create "a new harmonic landscape"
- There are NO wrong notes -- only context
- **Algorithmic encoding:** Any melody-bass pair is valid; the art is voice leading

### Level 5: Choice & Expression (Herbie Hancock)

- The paradox: unlimited harmonic options require intentional selection
- Life experiences and emotions guide harmonic decisions
- Music as "an extension of one's feelings and perspectives"
- **Algorithmic encoding:** Harmonic choice = probability weighted by emotional target

---

## 3. Super-Ultra-Hyper-Mega-Meta Scales

### Concept

Collier's idea for a theoretically infinite scale. It chains consecutive Lydian
tetrachords built on ascending 5ths, creating a scale that continuously wraps
around the bright side of the circle of fifths.

### Connection to George Russell

George Russell's Lydian Chromatic Concept (1953) posited the Lydian mode as the
"true" consonant scale (because it perfectly stacks ascending 5ths from its root).
Collier extends this by not stopping at one octave.

### Construction Algorithm

```python
def super_ultra_hyper_mega_meta_lydian(root_midi, num_tetrachords=4):
    """
    Generate the Super-Ultra-Hyper-Mega-Meta Lydian scale.

    Each Lydian tetrachord (W-W-W pattern, 3 whole steps) resolves
    into the next one, built a perfect 5th higher.

    Lydian tetrachord intervals: [0, 2, 4, 6] (in semitones)
    Each new tetrachord starts a P5 (7 semitones) above the previous root.
    """
    notes = []
    current_root = root_midi

    for i in range(num_tetrachords):
        tetrachord = [current_root + interval for interval in [0, 2, 4, 6]]
        notes.extend(tetrachord)
        current_root += 7  # Move up a perfect 5th

    return notes

# Example: Starting on C4 (MIDI 60)
# Tetrachord 1 (C Lydian):  C  D  E  F#
# Tetrachord 2 (G Lydian):  G  A  B  C#
# Tetrachord 3 (D Lydian):  D  E  F# G#
# Tetrachord 4 (A Lydian):  A  B  C# D#
# ... continues through all 12 keys and beyond
```

### Properties

- After 12 tetrachords, you cycle through all 12 chromatic notes
- Despite being chromatic in aggregate, it maintains a continuous Lydian flavor
- It doesn't sound chromatic or atonal because each segment has clear tonal pull
- The scale is theoretically infinite (wraps around the circle of fifths)

### Locrian Variant (Super-Ultra-Hyper-Mega-Meta Locrian)

The mirror image: chain Locrian tetrachords descending in 5ths (or ascending
in 4ths). This produces the darkest possible continuous scale.

```python
def super_ultra_hyper_mega_meta_locrian(root_midi, num_tetrachords=4):
    """The dark mirror: consecutive Locrian tetrachords descending in 5ths."""
    notes = []
    current_root = root_midi

    for i in range(num_tetrachords):
        # Locrian tetrachord: H-W-W pattern = [0, 1, 3, 5]
        tetrachord = [current_root + interval for interval in [0, 1, 3, 5]]
        notes.extend(tetrachord)
        current_root -= 7  # Move DOWN a perfect 5th (= up a P4)

    return notes
```

### Mixolydian Variant

An ascending chain through Mixolydian tetrachords, creating a middle-brightness
continuous scale.

---

## 4. Microtonal Harmony & Just Intonation

### Collier's Microtonal Approach

Collier regularly ventures into notes between the 12 standard pitches of equal
temperament. He doesn't treat microtonality as "out of tune" -- he treats it as
an expanded palette.

### Equal Temperament vs. Just Intonation

```
12-TET (Equal Temperament):
- All semitones are exactly 100 cents
- Mathematically: each semitone = 2^(1/12) frequency ratio
- Compromise: NO interval is acoustically "pure" except the octave
- All keys sound the same (symmetry)

Just Intonation:
- Intervals based on simple frequency ratios
- Major 3rd = 5:4 (386 cents, vs 400 in 12-TET = 14 cents flat)
- Perfect 5th = 3:2 (702 cents, vs 700 in 12-TET = 2 cents sharp)
- Minor 7th = 7:4 (969 cents, vs 1000 in 12-TET = 31 cents flat!)
- Result: individual chords sound more "pure" and resonant
- Trade-off: you can't modulate freely (each key needs retuning)
```

### The Exploitable Gap

Collier exploits the gap between these systems. A just-intonation dominant 7th
chord (C-E-G-Bb with ratios 4:5:6:7) sounds shimmery and resonant because
all overtones align. The 12-TET version sounds "duller" because overtones clash.

```python
# Frequency ratios for just intonation intervals
JUST_RATIOS = {
    'unison':     1/1,       # 0 cents
    'minor_2nd':  16/15,     # 112 cents
    'major_2nd':  9/8,       # 204 cents
    'minor_3rd':  6/5,       # 316 cents
    'major_3rd':  5/4,       # 386 cents
    'perfect_4th': 4/3,      # 498 cents
    'tritone':    45/32,     # 590 cents
    'perfect_5th': 3/2,      # 702 cents
    'minor_6th':  8/5,       # 814 cents
    'major_6th':  5/3,       # 884 cents
    'minor_7th':  9/5,       # 1018 cents (or 7/4 = 969 cents for septimal)
    'major_7th':  15/8,      # 1088 cents
    'octave':     2/1,       # 1200 cents
}

# Equal temperament comparison
def equal_temperament_cents(semitones):
    return semitones * 100

def just_intonation_cents(ratio):
    import math
    return 1200 * math.log2(ratio)

def cent_difference(interval_name):
    """How many cents off is 12-TET from just intonation?"""
    just_cents = just_intonation_cents(JUST_RATIOS[interval_name])
    # Find nearest 12-TET semitone
    nearest_semitone = round(just_cents / 100)
    tet_cents = nearest_semitone * 100
    return tet_cents - just_cents
```

### Quarter-Tone Keys

Collier modulates to keys that don't exist on a piano:
- **G half-sharp major**: halfway between G and G# (G + 50 cents)
- **B half-flat major**: halfway between Bb and B (B - 50 cents)
- **D half-sharp major**: used in Moon River arrangement

These keys are reached through careful voice leading where each successive
chord is tuned slightly sharp (in just intonation), accumulating until the
tonal center has shifted by a quarter tone.

```python
def quarter_tone_frequency(base_freq, quarter_tones_sharp=1):
    """
    Calculate frequency for quarter-tone-shifted pitch.
    One quarter tone = 50 cents = 2^(1/24) ratio.
    """
    import math
    return base_freq * (2 ** (quarter_tones_sharp / 24))

# G half-sharp: G4 = 392 Hz
# G half-sharp 4 = 392 * 2^(1/24) = ~403.5 Hz
# (Compare: G# = 415.3 Hz)
```

---

## 5. The Four Magical Chords

### Context

In "In the Bleak Midwinter," Collier modulates from E major to G half-sharp
major using four ascending chords. This is his most famous microtonal moment.

### How It Works

1. Each chord is voiced in **just intonation** (pure ratios)
2. Each successive chord shares a common tone with the previous chord
3. Each chord is **slightly sharper overall** than the one before
4. The listener perceives continuity (common tone) not drift (sharpening)
5. After four chords, the tonal center has shifted by ~50 cents (a quarter tone)

### The Mechanism (Algorithmic Description)

```python
def four_magical_chords_principle():
    """
    The principle behind Collier's microtonal modulation.

    In 12-TET, a major 3rd = 400 cents.
    In just intonation, a major 3rd = 386 cents (5:4 ratio).

    Difference = 14 cents per major 3rd.

    If you chain just-intonation major 3rds upward:
    C -> E (386c) -> G# (772c) -> C (1158c)

    In 12-TET: C -> E (400c) -> G# (800c) -> C (1200c)

    The just version arrives 42 cents FLAT of the octave after
    3 major 3rds. This is the "syntonic comma drift."

    Collier REVERSES this: by singing in just intonation where
    each chord sounds perfectly in tune LOCALLY, he accumulates
    a small upward drift with each chord transition.

    After ~3.5 such transitions, you've drifted up ~50 cents
    (one quarter tone), arriving at G half-sharp.
    """
    pass

# The syntonic comma: 81/80 = 21.5 cents
# This is the difference between four just P5ths and two octaves + a just M3rd
# Collier uses accumulated comma drift as a FEATURE, not a bug

SYNTONIC_COMMA = 81/80  # ~21.5 cents
DIESIS = 128/125        # ~41.1 cents (3 just major 3rds vs octave)
```

### Collier's Own Words

> "Having been unable to find a key centre that held enough power for the
> final verse, I forged a careful bridge from equal temperament into the
> microtonal realm, unearthing the majesty of G Half-Sharp Major."

---

## 6. Reharmonization Techniques

### Core Philosophy

Collier treats harmony as "the way a melody feels" -- a way of "injecting
melody with emotion." His reharmonizations:

1. **Preserve the original melody** (always recognizable)
2. **Subvert harmonic expectations** systematically
3. **Progress from simple to complex** across an arrangement
4. **Use voice leading as the connective tissue** between any chords

### "Every Note Works with Every Bass Note"

Collier's principle: there are no wrong notes, only inadequate voice leading.
Any melody note can be paired with any bass note if you:
- Choose appropriate inner voices
- Use smooth voice leading (minimal motion between chords)
- Create a harmonic context that justifies the combination

```python
def reharmonize_melody_note(melody_note, target_bass, key):
    """
    Given a melody note and a desired bass note, find inner voices
    that create a coherent chord.

    Strategy: The melody and bass define the outer voices.
    Fill inner voices by:
    1. Identify the interval between bass and melody
    2. Choose a chord quality that contains both notes
    3. Fill remaining chord tones with smooth voice leading
    """
    interval = (melody_note - target_bass) % 12

    # Map intervals to possible chord interpretations
    # (bass_note, melody_note_function, possible_chord_types)
    INTERVAL_CHORDS = {
        0:  ['unison/octave', 'maj', 'min', 'dim', 'aug', 'sus4', 'sus2'],
        1:  ['b9 chord', 'maj7#11'],
        2:  ['9 chord', 'add9', 'sus2'],
        3:  ['minor chord (melody=b3)', '#9 chord', 'min/maj7'],
        4:  ['major chord (melody=3)', 'dom7#5'],
        5:  ['sus4', '11 chord', 'major (melody=4/11)'],
        6:  ['#11 chord', 'b5 chord', 'lydian dom'],
        7:  ['power chord (melody=5)', 'any quality'],
        8:  ['minor 6th (melody=b6)', '#5 chord', 'aug'],
        9:  ['6th chord (melody=6)', '13 chord'],
        10: ['dom7 (melody=b7)', 'min7'],
        11: ['maj7 (melody=7)', 'min/maj7'],
    }

    return INTERVAL_CHORDS.get(interval, [])
```

### Reharmonization Density Levels

Collier progressively increases harmonic density across an arrangement:

```
Level 1: Diatonic triads (I, IV, V, vi)
Level 2: Add 7ths and sus chords
Level 3: Secondary dominants and borrowed chords
Level 4: Tritone substitutions and chromatic mediants
Level 5: Negative harmony substitutions
Level 6: Chromatic bass lines with upper-structure triads
Level 7: Microtonal voice leading and quarter-tone modulations
Level 8: Full polytonal layering
```

### Chromatic Mediant Movement

A favorite Collier device: moving chord roots by major or minor 3rds
while maintaining a common tone.

```python
def chromatic_mediant_options(root, quality='major'):
    """
    Return chromatic mediant destinations from a given chord.
    Chromatic mediants share exactly one common tone.
    """
    mediants = {
        'upper_major':  (root + 4, 'major'),   # up major 3rd, same quality
        'upper_minor':  (root + 3, 'major'),   # up minor 3rd, same quality
        'lower_major':  (root - 4, 'major'),   # down major 3rd
        'lower_minor':  (root - 3, 'major'),   # down minor 3rd
        'upper_major_m': (root + 4, 'minor'),  # up major 3rd, mode change
        'upper_minor_m': (root + 3, 'minor'),  # up minor 3rd, mode change
        'lower_major_m': (root - 4, 'minor'),
        'lower_minor_m': (root - 3, 'minor'),
    }
    return mediants
```

---

## 7. Circle of Fifths: Brighten & Darken

### Collier's Framework

Collier uses the circle of fifths as a **brightness axis**:
- **Clockwise motion (ascending 5ths)** = brighter, more "major"
- **Counter-clockwise motion (ascending 4ths/descending 5ths)** = darker, more "minor"

### "Fifths Are Major, Fourths Are Minor"

Collier's controversial claim: stack ascending 5ths from any root and you get
a major sonority. Stack ascending 4ths and you get minor.

```
Ascending 5ths from C: C G D A E = C6/9 chord (major pentatonic)
Ascending 4ths from C: C F Bb Eb Ab = Cm7(11)(b13) (minor quality)
```

```python
def brightness_from_fifths(root, num_fifths=5, direction='clockwise'):
    """
    Generate a chord by stacking perfect 5ths.

    Clockwise (ascending 5ths) = increasingly bright/major.
    Counter-clockwise (ascending 4ths) = increasingly dark/minor.
    """
    notes = [root]
    current = root
    interval = 7 if direction == 'clockwise' else 5  # P5 up or P4 up

    for _ in range(num_fifths - 1):
        current = (current + interval) % 12
        notes.append(current)

    return sorted(set(notes))

# brightness_from_fifths(0, 5, 'clockwise')  -> [0, 2, 4, 7, 9] = C major pentatonic
# brightness_from_fifths(0, 5, 'counter')    -> [0, 3, 5, 8, 10] = C minor pentatonic
```

### Brightness Score

```python
def harmonic_brightness(chord_notes, key_center):
    """
    Calculate a brightness score based on position on circle of fifths.

    Notes on the sharp/clockwise side of the key = bright.
    Notes on the flat/counter-clockwise side = dark.

    Score: sum of fifths-distance for each note.
    Positive = bright, Negative = dark.
    """
    FIFTHS_ORDER = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]
    key_pos = FIFTHS_ORDER.index(key_center % 12)

    score = 0
    for note in chord_notes:
        note_pos = FIFTHS_ORDER.index(note % 12)
        # Distance on circle of fifths (signed)
        dist = note_pos - key_pos
        if dist > 6:
            dist -= 12
        if dist < -6:
            dist += 12
        score += dist

    return score / len(chord_notes)  # Normalize by chord size
```

---

## 8. Harmonic Gravity

### Concept

Collier (via Levy and Coleman) describes "tonal gravity" as the pull that notes
and chords exert toward resolution. Two types:

**Telluric Gravity** (Levy/Coleman's term): Traditional tonal gravity based on
the overtone series. The dominant pulls toward the tonic. This is the "pull of
the earth" -- the natural acoustic tendency of sound.

**Absolute Conception** (Levy/Coleman): Gravity based on geometric centers of
symmetry. Negative harmony operates in this space. Chords have gravity not
because of acoustic overtones but because of their position relative to an
axis of symmetry.

### Gravity in Negative Harmony

When Collier says negative harmony preserves "equivalent tonal gravity," he means:
- A mirrored chord has the same STRENGTH of pull as the original
- But the DIRECTION of pull is inverted (perfect -> plagal)
- The emotional weight is maintained while the color changes

```python
def tonal_gravity(chord_notes, tonic):
    """
    Estimate tonal gravity (strength of pull toward tonic).

    Based on:
    1. Presence of leading tone (semitone below tonic) = strong pull
    2. Presence of tritone (between 4th and 7th degrees) = tension
    3. Proximity of chord tones to tonic on circle of 5ths
    """
    gravity = 0.0
    tonic_class = tonic % 12

    for note in chord_notes:
        nc = note % 12
        interval = (nc - tonic_class) % 12

        # Leading tone (semitone below tonic)
        if interval == 11:
            gravity += 3.0
        # Supertonic (whole step above tonic)
        elif interval == 2:
            gravity += 1.0
        # Dominant (P5 above tonic)
        elif interval == 7:
            gravity += 2.0
        # Subdominant (P4 above tonic)
        elif interval == 5:
            gravity += 1.5
        # Tritone
        elif interval == 6:
            gravity += 2.5

    return gravity
```

### Melodic Gravity

Notes at the top of a melodic arc have potential energy; descending motion
releases it. Collier often builds melodic phrases that ascend in tension
and descend in resolution.

---

## 9. Audience-Driven Harmony

### The Technique

Collier conducts audiences of thousands into singing three-part (or more)
complex harmonies using only hand gestures, body language, and eye contact.

### How It Works

1. **Section division**: Split audience into 3+ groups (left, center, right)
2. **Pitch cueing**: Collier sings or plays the starting note for each section
   (he has perfect pitch, so he can cue any note instantly)
3. **Hand-height = pitch**: Higher hand position = higher pitch. He "draws"
   the melody line in the air
4. **Finger spread = dynamics**: Wide fingers = louder, closed = softer
5. **Eye contact = section activation**: Looking at a section means "your turn"
6. **Modulation by gesture**: He gradually shifts hand positions to modulate
   the audience's notes

### Theory Behind It

- Audiences naturally tend toward **consonant intervals** (3rds, 5ths, octaves)
- Collier exploits this by starting with simple intervals and gradually
  increasing complexity
- The "instrument" improves each night as Collier refines his conducting language
- He's managed audiences of 100,000+ people (virtual, 31 cities)

### Native Instruments Collaboration

Collier partnered with Native Instruments to create the free "Audience Choir"
plugin, which samples actual audience singing from his Djesse World Tour,
recorded with Shure KSM44A microphones.

### Algorithmic Encoding

```python
def audience_harmony_model(melody_note, num_parts=3, complexity=0.5):
    """
    Model audience-driven harmony.

    At low complexity (0): audiences sing octaves and unisons.
    At medium complexity (0.5): audiences add 3rds and 5ths.
    At high complexity (1.0): audiences can manage 7ths and extensions.

    The key constraint: each part moves by step or stays put.
    Large leaps cause audiences to lose pitch.
    """
    intervals = {
        0.0: [0, 0, 0],                    # Unisons
        0.2: [0, 7, 12],                   # Root, 5th, octave
        0.4: [0, 4, 7],                    # Major triad
        0.5: [0, 3, 7],                    # Minor triad
        0.6: [0, 4, 7, 10],               # Dom7
        0.8: [0, 4, 7, 11],               # Maj7
        1.0: [0, 4, 7, 11, 14],           # Maj9
    }

    # Find closest complexity level
    closest = min(intervals.keys(), key=lambda x: abs(x - complexity))
    selected = intervals[closest][:num_parts]

    return [melody_note + i for i in selected]
```

---

## 10. Polytonality & Polytonal Voice Leading

### Collier's Approach

Collier moves between key centers using:

1. **Common-tone modulation**: One note stays fixed while harmony shifts around it
2. **Chromatic mediant modulation**: Root moves by major or minor 3rd
3. **Microtonal drift**: Accumulated just-intonation comma drift (see Section 5)
4. **Cross-terrain modulation**: Collier's term for modulating between tuning systems

### Polytonal Layering

In his dense arrangements, different layers may occupy different key centers:
- Bass line in one key
- Inner harmony in a related key
- Melody in a third key
- Counter-melody in a fourth key

### Voice Leading Rules

Collier's voice leading principles (derived from analysis):

```python
VOICE_LEADING_RULES = {
    'max_semitone_motion': 2,       # Prefer stepwise or common-tone motion
    'contrary_motion_preferred': True,  # Outer voices move in opposite directions
    'avoid_parallel_5ths': True,     # Unless deliberate (parallel planing)
    'common_tone_retention': True,   # Keep shared notes in same voice
    'bass_can_leap': True,           # Bass voice has more freedom
    'chromatic_voice_leading': True, # Chromatic half-steps connect anything
}

def smooth_voice_leading(chord_a, chord_b):
    """
    Find the voicing of chord_b that minimizes total voice movement
    from chord_a. Uses the Hungarian algorithm for optimal assignment.
    """
    import itertools

    if len(chord_a) != len(chord_b):
        # Pad shorter chord with None
        pass

    min_cost = float('inf')
    best_voicing = None

    for perm in itertools.permutations(chord_b):
        cost = sum(abs(a - b) for a, b in zip(chord_a, perm))
        if cost < min_cost:
            min_cost = cost
            best_voicing = list(perm)

    return best_voicing, min_cost
```

---

## 11. Rhythm & Polyrhythm

### Collier's Rhythmic Philosophy

- Time signatures are fluid, not fixed
- Polyrhythms are stacked: 2 against 3 against 4 against 5 against 6
  (he practices this with one hand: pinky=2, ring=3, middle=4, index=5, thumb=6)
- Sudden time signature changes are a feature, not a disruption
- Groove is paramount -- complexity serves the groove, never the reverse

### Polyrhythm Stacking

```python
def polyrhythm_grid(subdivisions, total_beats=1, resolution=120):
    """
    Generate a polyrhythmic grid for multiple simultaneous subdivisions.

    subdivisions: list like [2, 3, 5] for 2-against-3-against-5
    resolution: ticks per beat
    """
    grid = {}
    for sub in subdivisions:
        ticks_per_hit = (total_beats * resolution) // sub
        grid[sub] = [i * ticks_per_hit for i in range(sub)]

    return grid

# polyrhythm_grid([2, 3, 5], 1, 120)
# {2: [0, 60], 3: [0, 40, 80], 5: [0, 24, 48, 72, 96]}
```

### Rhythmic Reharmonization

Collier reshapes rhythmic distributions of chords -- spreading the same harmonic
content across different metric positions to change the feel without changing
the notes.

---

## 12. Production & Arrangement Philosophy

### "Maximalism in the Name of Minimalism"

Collier uses maximum resources to tell a story. His Logic Pro sessions routinely
exceed 300 tracks. But the GOAL is simplicity of emotional communication.

### Djesse Album Arc

```
Vol. 1: Large acoustic space. Orchestras, choirs, massive brush strokes.
        Bright, wide, cinematic. (Collaborators: Metropole Orkest)

Vol. 2: Smaller acoustic space. Folk, African music, acoustic instruments.
        Warm, intimate, earthy. (Collaborators: Lianne La Havas, Dodie)

Vol. 3: Negative space. Middle of the night. Deep funk, strange weirdness.
        Dark, electronic, experimental. (Collaborators: Tori Kelly, Daniel Caesar)

Vol. 4: Culmination. All worlds combined. Spatial audio (Dolby Atmos).
        Full spectrum. 316-track arrangements. (Collaborators: John Legend, Yebba)
```

### Arrangement Techniques

1. **Vocal pyramids**: Build chords as arpeggios, adding one voice at a time
   from bottom to top, creating a sense of harmonic revelation
2. **Horizontal over vertical**: Melody-driven harmony. Each voice is a
   melody first, and the harmony emerges from the interplay
3. **Density curves**: Arrangements follow a density arc:
   sparse -> building -> dense -> climax -> sparse
4. **Textural contrast**: Acoustic vs. electronic, solo vs. ensemble,
   intimate vs. epic -- always in service of the emotional arc

### Spatial Audio

Djesse Vol. 4 was mixed in Dolby Atmos at Wingbeats Recording Studio.
Collier uses spatial positioning as another harmonic dimension --
different voices/instruments occupy different positions in 3D space.

---

## 13. The Harmonizer Instrument

### What It Is

A custom hardware/software instrument built by Ben Bloomberg (MIT Media Lab)
that allows Collier to sing one note and produce up to 12 simultaneous
harmonized voices in real time.

### How It Works

1. Collier sings into a microphone
2. A vocoder-style engine analyzes the vocal input
3. MIDI input from a keyboard specifies the target pitches
4. The engine resynthesizes the voice at each target pitch
5. Result: one-person choir with Collier's vocal timbre on every note

### Technical Details

- Uses modified TC Helicon hardware (PCB extracted and rebuilt)
- Custom code + off-the-shelf plugins glued together
- Features: three infinite sustains, sub-bass treatment, pitch shifts,
  "sparkly effects"
- The harmonizer "doesn't know about chords or keys" -- it's purely
  pitch-based, requiring manual keyboard input

### Algorithmic Model

```python
def harmonizer_model(input_pitch, target_pitches, formant_preserve=True):
    """
    Model of a vocal harmonizer.

    input_pitch: the sung note (MIDI)
    target_pitches: list of desired output pitches (MIDI)
    formant_preserve: if True, shift pitch without changing vowel quality
    """
    outputs = []
    for target in target_pitches:
        shift_semitones = target - input_pitch
        outputs.append({
            'pitch': target,
            'shift': shift_semitones,
            'formant_shift': 0 if formant_preserve else shift_semitones,
            'source_pitch': input_pitch,
        })
    return outputs
```

---

## 14. Ernst Levy's Polarity Theory

### The Core Idea

Levy proposed that harmony is bipolar: every tonal relationship has a
positive (overtone-based) and negative (undertone-based) manifestation.

### Overtone vs. Undertone Series

```
Overtone series from C: C  C  G  C  E  G  Bb  C  D  E  F#  G
(Harmonics:              1  2  3  4  5  6   7  8  9  10  11  12)
-> Produces: MAJOR triad (C-E-G) naturally

Undertone series from C: C  C  F  C  Ab  F  D  C  Bb  Ab  Gb  F
(Subharmonics:           1  2  3  4   5  6  7  8   9  10  11  12)
-> Produces: MINOR triad (F-Ab-C) naturally
```

### Polarity Pairs

```
Interval          Positive (up)    Negative (down)
Perfect 5th:      C -> G           C -> F
Major 3rd:        C -> E           C -> Ab
Major 2nd:        C -> D           C -> Bb

Levy calls:
- Upward P5 = "Dominant" direction
- Downward P5 = "Anti-dominant" direction
- Upward M3 = "Determinant" (brightening)
- Downward M3 = "Anti-determinant" (darkening)
```

### Generator Concept

Every note generates two triads:
- **Positive triad** (major): built upward from the generator
  - C generates C major: C-E-G
- **Negative triad** (minor): built downward from the generator
  - C generates F minor: F-Ab-C (C is the 5th, read downward)

```python
def levy_polarity_triads(generator_midi):
    """
    Generate both polarity triads from a generator note (Levy's system).

    Positive (major): generator is root, build up
    Negative (minor): generator is 5th, build down
    """
    g = generator_midi % 12

    positive = [g, (g + 4) % 12, (g + 7) % 12]         # Major triad
    negative = [(g - 7) % 12, (g - 3) % 12, g]          # Minor triad (root is P5 below)

    return {
        'positive': positive,   # e.g., C -> C major [C, E, G]
        'negative': negative,   # e.g., C -> F minor [F, Ab, C]
    }
```

---

## 15. Steve Coleman's Symmetrical Movement

### Connection

Steve Coleman independently developed Levy's ideas into practical improvisation
tools (1978). He called it the "Symmetrical Movement Concept."

### Key Principles

1. **Axis tone**: A central pitch around which melodic motion expands and
   contracts equally in both directions
2. **Equal expansion**: If you move up by interval X, you also move down by X
3. **Telluric adaptation**: Bending the symmetrical lines to fit conventional
   tonal harmony when needed
4. **Cells**: Small melodic units that can be symmetrically transformed

### Relation to Negative Harmony

Coleman's system is melodic (horizontal); Collier/Levy's is harmonic (vertical).
But the underlying mathematics is the same: reflection around an axis.

```python
def symmetrical_expansion(axis_note, intervals):
    """
    Generate a symmetrical melody around an axis note.

    For each interval, produce both the upper and lower notes.
    """
    melody = [axis_note]
    for interval in intervals:
        melody.append(axis_note + interval)   # Expand up
        melody.append(axis_note - interval)   # Expand down
    return sorted(melody)

# symmetrical_expansion(60, [2, 4, 7])
# -> [53, 56, 58, 60, 62, 64, 67]
```

---

## 16. George Russell's Lydian Chromatic Concept

### Why It Matters

Russell (1953) proposed that the Lydian mode -- not the major scale -- is the
"true" consonant scale. Reason: stacking 6 ascending perfect 5ths from any
note produces the Lydian scale.

```
C -> G -> D -> A -> E -> B -> F# = C Lydian
(All natural notes of C major EXCEPT F -> F#)
```

### Connection to Collier

Collier's circle-of-fifths brightness concept and his Super-Ultra-Hyper-Mega-Meta
Lydian scale are direct extensions of Russell's thinking.

### Tonal Gravity (Russell's Version)

Russell ranked scales by their "tonal gravity" -- how strongly they pull
toward a tonal center:

```
Strongest gravity:  Lydian (most consonant with the overtone series)
                    Lydian Augmented
                    Lydian Dominant
                    Lydian b7
                    Auxiliary Diminished
                    Auxiliary Augmented
Weakest gravity:    Auxiliary Diminished Blues (most chromatic)
```

```python
RUSSELL_TONAL_ORDER = [
    ('lydian',              [0, 2, 4, 6, 7, 9, 11]),
    ('lydian_augmented',    [0, 2, 4, 6, 8, 9, 11]),
    ('lydian_dominant',     [0, 2, 4, 6, 7, 9, 10]),
    ('lydian_b7',           [0, 2, 4, 6, 7, 9, 10]),  # same as above
    ('aux_diminished',      [0, 1, 3, 4, 6, 7, 9, 10]),
    ('aux_augmented',       [0, 2, 4, 6, 8, 10]),
    ('aux_dim_blues',       [0, 2, 3, 5, 6, 8, 9, 11]),
]
```

---

## 17. Esoteric Concepts & Philosophy

### "There Are No Wrong Notes"

Collier's foundational belief: ANY combination of pitches can be made to work
with sufficient voice leading skill. Dissonance is not error -- it's unrealized
consonance awaiting resolution.

### Harmony as Emotion Injection

"Harmony is the way a melody feels." Harmonic choices don't illustrate theory --
they express emotion. The theory is a map; the emotion is the territory.

### Music as Natural Pattern

Collier sees music as encoded in nature: overtone series, Fibonacci spirals
in rhythm, golden ratio in phrase lengths. His approach is to discover patterns
rather than invent them.

### Decisions Based on Feelings

"A lot of the decisions that may feel quite technical are basically based in
feelings." Despite his vast theoretical knowledge, Collier claims intuition
guides final choices. The theory serves as vocabulary; the sentence comes
from the heart.

### Performing Theory

Academic analysis describes Collier as "performing theory" -- his music doesn't
just USE theory, it DEMONSTRATES theory. Each performance is simultaneously
music and meta-music (music about music).

### Analytic Listening

Collier's teaching encourages "analytic listening" -- making contingent and
ambiguous musical features explicit without sacrificing emotional flow. He
makes the implicit explicit.

---

## 18. Algorithmic Implementation Reference

### Complete Negative Harmony Transformer

```python
class NegativeHarmonyTransformer:
    """
    Full implementation of negative harmony transformation.

    Supports:
    - Single note reflection
    - Chord reflection
    - Mode reflection
    - Cadence transformation
    - Melody inversion with key preservation
    """

    NOTE_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F',
                  'F#', 'G', 'Ab', 'A', 'Bb', 'B']

    def __init__(self, tonic=0):
        """
        tonic: MIDI note class (0=C, 1=C#, ..., 11=B)
        """
        self.tonic = tonic % 12
        self.axis = self.tonic + 3.5  # Between b3 and natural 3

    def reflect_note(self, note):
        """Reflect a single note around the axis."""
        note_class = note % 12
        reflected = (2 * self.tonic + 7 - note_class) % 12
        octave = note // 12
        return octave * 12 + reflected

    def reflect_chord(self, chord_notes):
        """Reflect all notes in a chord."""
        return [self.reflect_note(n) for n in chord_notes]

    def reflect_scale(self, scale_degrees):
        """Reflect a scale (given as semitone offsets from tonic)."""
        return sorted([(self.tonic + 7 - d) % 12 for d in scale_degrees])

    def get_mapping_table(self):
        """Return complete note-to-note mapping."""
        mapping = {}
        for i in range(12):
            original = (self.tonic + i) % 12
            reflected = (2 * self.tonic + 7 - original) % 12
            mapping[self.NOTE_NAMES[original]] = self.NOTE_NAMES[reflected]
        return mapping

    def transform_chord_quality(self, quality):
        """Transform chord quality under negative harmony."""
        QUALITY_MAP = {
            'major':     'minor',
            'minor':     'major',
            'major7':    'minor_b6',
            'minor7':    'major6',
            'dominant7': 'minor6',
            'minor6':    'dominant7',
            'augmented': 'augmented',
            'diminished':'diminished',
            'sus4':      'sus2',
            'sus2':      'sus4',
        }
        return QUALITY_MAP.get(quality, quality)


class MicrotonalModulator:
    """
    Implement Collier-style microtonal modulation.
    """

    def __init__(self, start_freq=440.0):
        self.current_freq = start_freq
        self.current_cents_offset = 0

    def just_intonation_chord(self, root_freq, chord_type='major7'):
        """Build a chord in just intonation from a root frequency."""
        JUST_INTERVALS = {
            'major':  [1, 5/4, 3/2],
            'minor':  [1, 6/5, 3/2],
            'major7': [1, 5/4, 3/2, 15/8],
            'dom7':   [1, 5/4, 3/2, 7/4],
            'minor7': [1, 6/5, 3/2, 9/5],
        }
        ratios = JUST_INTERVALS.get(chord_type, [1])
        return [root_freq * r for r in ratios]

    def comma_drift_step(self, chord_root_freq, interval_ratio):
        """
        Calculate the comma drift when chaining just intervals.

        Returns: (new_root_freq, cents_drift_from_12tet)
        """
        import math
        new_freq = chord_root_freq * interval_ratio
        # What 12-TET would expect
        nearest_semitone = round(12 * math.log2(interval_ratio))
        expected_freq = chord_root_freq * (2 ** (nearest_semitone / 12))
        # Drift in cents
        drift = 1200 * math.log2(new_freq / expected_freq)
        return new_freq, drift

    def four_magical_chords(self, start_freq):
        """
        Simulate the four magical chords modulation.

        Chain just-intonation intervals that accumulate ~50 cents of drift,
        arriving at a quarter-tone-shifted key center.
        """
        import math
        chords = []
        current = start_freq
        total_drift = 0

        # Each step: move by a just major 3rd (5/4 ratio)
        # 12-TET M3 = 400 cents, Just M3 = 386 cents
        # Each step drifts ~14 cents sharp
        for i in range(4):
            chord = self.just_intonation_chord(current, 'major7')
            chords.append({
                'root_freq': current,
                'chord_freqs': chord,
                'total_drift_cents': total_drift,
            })
            current = current * (5/4)
            drift = 1200 * math.log2(5/4) - 400
            total_drift += abs(drift)

        return chords


class BrightnessEngine:
    """
    Calculate and manipulate harmonic brightness using
    Collier's circle-of-fifths framework.
    """

    # Circle of fifths order (by fifths from C)
    FIFTHS = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]

    def brightness_score(self, notes, tonic=0):
        """
        Score the brightness of a set of notes relative to a tonic.
        Positive = bright (sharp side), Negative = dark (flat side).
        """
        tonic_pos = self.FIFTHS.index(tonic)
        score = 0
        for note in notes:
            note_pos = self.FIFTHS.index(note % 12)
            dist = note_pos - tonic_pos
            if dist > 6: dist -= 12
            if dist < -6: dist += 12
            score += dist
        return score / max(len(notes), 1)

    def brighten(self, chord_notes, tonic, steps=1):
        """
        Brighten a chord by moving notes clockwise on circle of fifths.
        """
        result = []
        for note in chord_notes:
            pos = self.FIFTHS.index(note % 12)
            new_pos = (pos + steps) % 12
            result.append(self.FIFTHS[new_pos])
        return result

    def darken(self, chord_notes, tonic, steps=1):
        """
        Darken a chord by moving notes counter-clockwise on circle of fifths.
        """
        return self.brighten(chord_notes, tonic, -steps)
```

---

## 19. Key Arrangements & Analysis

### "In the Bleak Midwinter"

- Starts in E major
- Modulates to G half-sharp major (quarter-tone key) via four magical chords
- Uses just-intonation comma drift to reach the microtonal destination
- Won Grammy for Best Arrangement, Instrumental or A Cappella (2013)

### "Moon River"

- 8 different keys/pitch centers throughout the arrangement
- Starts in Bb, modulates to Db (3:48), D (4:34), then D half-sharp (5:42)
- 144 different singers each contribute one note ("moon") in the 1.5-minute intro
- Microtonal inflections throughout, including notes a major 7th above the tune
- Uses descending chromatic inner voice sequences
- Won Grammy for Best Arrangement (2020)

### "Bridge Over Troubled Water" (Djesse Vol. 4)

- 316 tracks in the Logic Pro session
- Purely a cappella arrangement (all human voice)
- Features John Legend, Tori Kelly, and Yebba
- Won Grammy 2025 (Collier's 7th total)

### "The Christmas Song"

- A cappella arrangement with "hundreds of Colliers"
- Vocal pyramids: chords built as ascending arpeggios
- High dominant pedals bookend the track
- Modulates to non-standard keys (B half-flat major reported)

### Djesse Series (50 songs, 4 volumes, 2018-2024)

- Features 24+ collaborating artists and ensembles
- Each volume represents a different "world" (see Section 12)
- Vol. 4 mixed in Dolby Atmos spatial audio
- Culmination of all Collier's harmonic ideas in one project

---

## 20. Sources & Further Reading

### Primary Interviews & Videos

- [WIRED: Jacob Collier Explains Harmony in 5 Levels of Difficulty](https://markmoshermusic.com/2018/07/15/musician-explains-one-concept-in-5-levels-of-difficulty-ft-jacob-collier-herbie-hancock/)
- [June Lee Music Theory Interview with Jacob Collier (Parts 1 & 2)](http://www.robbyburns.com/blog/music-theory-interview-jacob-collier)
- [NPR: Jacob Collier on Djesse Vol. 3](https://www.npr.org/2020/08/15/902713663/jacob-collier-on-creating-the-negative-space-of-djesse-vol-3)
- [NPR: Jacob Collier on the Djesse Project](https://www.npr.org/2024/02/29/1234996309/jacob-collier-on-the-four-album-project-djesse)
- [imusic-school: Jacob Collier Masterclass on Harmony and Rhythm](https://www.imusic-school.com/en/music-theory/lessons/jacob-collier-masterclass/)
- [MIT Visiting Artist: Jacob Collier Infuses Technology with Humanity](https://arts.mit.edu/jazz-prodigy-jacob-collier-infuses-technology-humanity-mit/)

### Academic & Analytical

- [Ethan Hein: Jacob Collier's Four Magical Chords](https://www.ethanhein.com/wp/2019/jacob-colliers-four-magical-chords/)
- [Jamie Xu: Jacob Collier, The Master of Microtones (Medium)](https://jamiesxu.medium.com/jacob-collier-the-master-of-microtones-e0680fb1589a)
- [Stanford Daily: The Brilliance of Collier's Christmas Song Arrangement](https://stanforddaily.com/2020/11/29/the-brilliance-of-jacob-colliers-the-christmas-song-arrangement/)
- [Handling Ideas: Performing Theory in Jacob Collier's Music](https://handlingideas.blog/2019/11/05/performing-theory-imagination-in-jacob-colliers-music/)
- [ETSU Honors Thesis: Negative Harmony Experiments](https://dc.etsu.edu/cgi/viewcontent.cgi?article=1614&context=honors)
- [Tom Rocks Maths: Negative Harmony, Maths and Jacob Collier (PDF)](https://tomrocksmaths.com/wp-content/uploads/2024/08/tom-rocks-isaac-teng-isaac-teng.pdf)

### Negative Harmony Technical

- [Dan Tepfer: Negative Harmony, A Primer](https://dantepfer.com/blog/?p=368)
- [Sinewave Lab: Negative Harmony Explained Simply](https://sinewavelab.com/negative-harmony-explained-simply/)
- [Michael Fluegel: Short Facts about Negative Harmony](https://www.michaelfluegel.de/negative-harmony.html)
- [Opus Science Collective: The Harmonic Upside Down](https://www.opussciencecollective.com/post/the-harmonic-upside-down-negative-harmony)
- [Jazzmodes: Negative Harmony Part 3, The Levy Legacy](https://jazzmodes.wordpress.com/2017/09/20/negative-harmony-part-3-the-levy-legacy/)
- [Rafael Calsaverini: Negative Harmony Inverts Brightness of Modes](https://rcalsaverini.github.io/blog/negative-harmony-inverts-brightness-modes/)
- [Beyond Music Theory: Cadences and Negative Harmony](https://www.beyondmusictheory.org/cadences-and-negative-harmony/)

### Code Implementations

- [Jack Rusher: Negative Harmony Triad Transformations (Clojure)](https://gist.github.com/jackrusher/efc96f061b401d19b4b4de133be9daf9)
- [Jonathan Tetelepta: Finding Negative Harmony Using Python (Medium)](https://medium.com/@jonathan_tetelepta/finding-negative-harmony-using-python-ace83e4a476a)
- [Luke McCraig: NegativeHarmonizer (Python MIDI tool)](https://github.com/lukemcraig/NegativeHarmonizer)
- [Forrest Balman: Negative Harmony Calculator](https://forrestbalman.github.io/negative-harmony-calculator/)
- [Mathigatti: Real-time Harmonizer (Python, inspired by Collier)](https://github.com/mathigatti/harmonizer)

### Books

- Ernst Levy, *A Theory of Harmony* (SUNY Press, 1985)
- George Russell, *Lydian Chromatic Concept of Tonal Organization* (1953)
- [Steve Coleman: Symmetrical Movement Concept (M-BASE essay)](http://m-base.com/essays/symmetrical-movement-concept/)

### Collier's Tools & Collaborations

- [Native Instruments: Jacob Collier Audience Choir (Free Plugin)](https://www.native-instruments.com/en/products/komplete/vocal/jacob-collier-audience-choir/)
- [FloVoice: How Was Jacob Collier's Harmonizer Built?](https://www.flovoice.com/articles/6001397-how-was-jacob-colliers-harmonizer-built)
- [MusicRadar: Bridge Over Troubled Water Logic Session (316 tracks)](https://www.musicradar.com/news/jacob-collier-bridge-over-troubled-water-logic-pro-session)

### Super-Ultra-Hyper-Mega-Meta Scales

- [Jazz Improviser: Super-Ultra-Hyper-Mega-Meta Modes/Scales](https://jazzimproviser.com/super-ultra-hyper-mega-meta-modes-scales-jacon-collier-extending-lydian-and-locrian-modes-mixolydian-mode/)
- [NamuWiki: Super-Ultra-Hyper-Mega-Meta Lydian](https://en.namu.wiki/w/Super-Ultra-Hyper-Mega-Meta%20Lydian)

### General

- [Jacob Collier Wikipedia](https://en.wikipedia.org/wiki/Jacob_Collier)
- [Quora: What's So Special About Jacob Collier's Music Theory?](https://www.quora.com/What-s-so-special-about-Jacob-Collier-s-music-theory)
- [Modulation of the Day: Moon River Analysis](https://modulationoftheday.home.blog/2019/06/14/jacob-collier-moon-river/)
- [Modulation of the Day: In the Bleak Midwinter Analysis](https://modulationoftheday.home.blog/2022/12/09/jacob-collier-in-the-bleak-midwinter/)

---

## Quick Reference Card

### Negative Harmony Formula
```
negative(note) = (2 * tonic + 7 - note) % 12
```

### Brightness Direction
```
Clockwise on Circle of 5ths  = BRIGHTER (Lydian direction)
Counter-clockwise             = DARKER   (Locrian direction)
```

### Mode Mirrors
```
Lydian <-> Locrian | Ionian <-> Phrygian | Mixolydian <-> Aeolian | Dorian <-> Dorian
```

### Chord Quality Mirrors
```
Major <-> minor | Maj7 <-> min(b6) | min7 <-> Maj6 | Dom7 <-> min6 | aug <-> aug | dim <-> dim
```

### Quarter Tone
```
50 cents = 2^(1/24) frequency ratio
```

### Syntonic Comma
```
81/80 = ~21.5 cents (drift per just-intonation P5 cycle vs 12-TET)
```

### Diesis
```
128/125 = ~41.1 cents (drift from 3 stacked just M3rds vs octave)
```
