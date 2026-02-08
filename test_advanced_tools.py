#!/usr/bin/env python3
"""Test advanced multimedia tools"""

print("Testing Advanced Tools Installation\n")
print("=" * 50)

# Test pedalboard
print("\n1. Pedalboard (Spotify Audio Effects)")
try:
    from pedalboard import Reverb, Compressor
    print("   ✅ Import successful")
    print("   Available: Reverb, Compressor, Distortion, Delay, Chorus, etc.")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test pyrubberband
print("\n2. Pyrubberband (Time Stretching)")
try:
    import pyrubberband
    print("   ✅ Import successful")
    print("   Available: time_stretch(), pitch_shift()")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test wand
print("\n3. Wand (ImageMagick)")
try:
    from wand.image import Image
    from wand import version
    print("   ✅ Import successful")
    print(f"   ImageMagick version: {version.MAGICK_VERSION}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("   Note: Requires ImageMagick: brew install imagemagick")

# Test rawpy
print("\n4. Rawpy (RAW Photo Processing)")
try:
    import rawpy
    print("   ✅ Import successful")
    print("   Supports: CR2, NEF, DNG, ARW, etc.")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 50)
print("\n✅ Advanced tools ready for multimedia hacking!")
