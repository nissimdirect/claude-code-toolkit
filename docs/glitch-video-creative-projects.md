# Glitch Video Creative Projects - Inspiration Library

> A curated collection of real-world creative projects using OpenCV, MoviePy, PIL/Pillow,
> FFmpeg, datamoshing, and pixel sorting. Each entry is chosen for creative inspiration,
> not just technical reference. All projects use tools from our installed stack.

---

## Table of Contents

1. [Creative Glitch Art Projects on GitHub](#1-creative-glitch-art-projects-on-github)
2. [OpenCV Creative Coding Projects](#2-opencv-creative-coding-projects)
3. [FFmpeg Creative Pipelines](#3-ffmpeg-creative-pipelines)
4. [PIL/Pillow Pixel Art and Corruption](#4-pilpillow-pixel-art-and-corruption)
5. [MoviePy Creative Projects](#5-moviepy-creative-projects)
6. [Cross-Modal Audio-Video Projects](#6-cross-modal-audio-video-projects)
7. [Datamosh-Specific Resources](#7-datamosh-specific-resources)
8. [Generative Art with Python](#8-generative-art-with-python)

---

## 1. Creative Glitch Art Projects on GitHub

### Datamosher-Pro
- **URL:** https://github.com/Akascape/Datamosher-Pro
- **Stack:** Python, FFmpeg, OpenCV, Tkinter
- **What:** A GUI-based automatic datamoshing application with 30+ built-in glitch effects, including bloom, classic datamosh, echo, fake motion, glitch shift, ghost, inversion, pulse, and many more. All effects are inspired by tomato.py, pymosh, and FFglitch.
- **Why It's Cool:** The most comprehensive single-tool datamosh suite available. Each effect is a self-contained Python function that manipulates raw frame data. The sheer variety of effects (30+) means you can chain them for totally unique looks.
- **Key Technique:** P-frame duplication, I-frame removal, and frame buffer manipulation using numpy arrays and FFmpeg subprocess calls. Effects like "Rise" and "Sink" shift motion vectors to create directional melting.
- **Our Use:** Study the individual effect functions as templates for building our own custom effects. The architecture of one-effect-per-function is clean and extensible.

---

### Crasher
- **URL:** https://github.com/witch-software/crasher
- **Stack:** Python, PIL/Pillow
- **What:** An open-source application for creating glitch art. Provides byte-level corruption of image files with controllable intensity and region targeting.
- **Why It's Cool:** Focuses on raw byte manipulation rather than pixel-level operations. This produces artifacts that look like actual data corruption (the JPEG smearing, BMP header destruction aesthetic) rather than filter-processed effects.
- **Key Technique:** Direct binary file manipulation -- reading image files as byte arrays, randomly replacing bytes within controlled regions, then re-interpreting the corrupted data as images. Different file formats produce dramatically different artifacts.
- **Our Use:** Combine with our PIL pipeline. Corrupt individual video frames as PNG/BMP, then reassemble. The byte corruption approach gives results that pixel-level filters cannot replicate.

---

### GlitchGen
- **URL:** https://github.com/sas152ana/GlitchGen
- **Stack:** Python, PIL/Pillow, numpy
- **What:** A procedural generator for glitch art, digital chaos, and datamoshing effects. Offers a layered, non-destructive workflow allowing you to compose, mutate, and refine your digital art.
- **Why It's Cool:** The non-destructive layered workflow is a game-changer. Instead of destructively modifying an image, you stack mutations and can adjust any layer independently. Think Photoshop adjustment layers, but for glitch effects.
- **Key Technique:** Effect stacking with compositing. Each glitch operation is stored as a mutation layer. The final image is computed by compositing all layers, allowing you to reorder, disable, or re-parameterize any effect without starting over.
- **Our Use:** Adopt the layered/compositing architecture for our video glitch pipeline. This would let us non-destructively stack pixel sort + byte corruption + color shift and tweak each independently.

---

### glitch-this
- **URL:** https://github.com/TotallyNotChase/glitch-this
- **Stack:** Python, PIL/Pillow, numpy
- **What:** A commandline tool and Python library to glitchify images and make GIFs. Features 100 gradually different levels of glitching intensity, scan lines for retro CRT effects, and color offset (RGB channel displacement).
- **Why It's Cool:** 1.8k stars on GitHub. Was #1 on r/python, r/programming, r/broken_gifs, and r/glitch_art. The 100-level intensity gradient means you can animate a "glitch amount" parameter smoothly over time for video.
- **Key Technique:** JPEG chunk manipulation. The algorithm corrupts JPEG data at the byte level by manipulating the scan data within JPEG files. It also applies RGB channel offset (shifting red, green, blue channels by different pixel amounts) and scan line overlay.
- **Our Use:** Install via `pip install glitch-this`. Use the library API to process individual video frames with varying intensity levels. Animate the glitch_amount parameter from 1 to 10 over a music drop for a building-chaos effect.

---

### glitch-tool (tobloef)
- **URL:** https://github.com/tobloef/glitch-tool
- **Stack:** Python (minimal dependencies)
- **What:** A simple, focused tool for messing up files to create glitch art. Supports byte replacement, insertion, and deletion with configurable probability and range.
- **Why It's Cool:** Intentionally minimalist. No GUI, no framework, just pure file corruption with precise control. This is the "scalpel" approach to glitch art where you control exactly how much damage to inflict.
- **Key Technique:** Probabilistic byte manipulation. Each byte in the file has a configurable probability of being modified. You can set replacement ranges (which byte values to swap in), skip regions (protect file headers), and control the chaos/order balance.
- **Our Use:** Use as a preprocessing step. Run on raw video frame files before reassembly. The probability-based approach pairs well with audio-reactive control (louder audio = higher corruption probability).

---

### image-glitchsort (P33ry)
- **URL:** https://github.com/P33ry/image-glitchsort
- **Stack:** OpenCV, Python
- **What:** Image manipulation combining pixel sorting with Canny edge detection. Uses OpenCV's edge detection to define sorting regions, so glitch effects follow the natural contours of the image.
- **Why It's Cool:** Bridges the gap between pixel sorting and computer vision. Instead of sorting arbitrary rows, it uses edge detection to define intelligent regions. Faces melt along jawlines, buildings collapse along architectural lines.
- **Key Technique:** Canny edge detection as a pixel sort mask. OpenCV's Canny filter identifies edges, then pixel sorting is applied only to regions between detected edges. This creates "intelligent" glitch effects that respect the image content.
- **Our Use:** Directly applicable. Use OpenCV edge detection on video frames, then apply pixel sorting within detected contour regions. The result looks intentional rather than random.

---

### PixelSorter (h43lb1t0)
- **URL:** https://github.com/h43lb1t0/PixelSorter
- **Stack:** Python, PIL/Pillow, OpenCV, YOLOv8
- **What:** Advanced pixel sorting application that can sort by brightness, hue, or saturation. The standout feature: it uses YOLOv8 object segmentation to isolate specific objects for sorting.
- **Why It's Cool:** AI-guided pixel sorting. You can tell it "only pixel sort the person" or "only sort the background" using YOLO segmentation masks. This is bleeding-edge creative tech -- using ML models as artistic masking tools.
- **Key Technique:** YOLOv8 segmentation mask as a pixel sort region selector. The model segments the image into objects, and you choose which segments to sort. The mask defines where sorting happens, preserving everything else.
- **Our Use:** Install YOLO weights and use this approach for music video effects. Sort only the performer while keeping the background clean, or vice versa. This is the future of targeted glitch effects.

---

### Pixelort (Akascape)
- **URL:** https://github.com/Akascape/Pixelort
- **Stack:** Python, customtkinter, PIL/Pillow
- **What:** An advanced pixel sorting application with a polished GUI built with customtkinter. Supports sorting by luminosity, hue, or saturation with real-time preview and extensive parameter control.
- **Why It's Cool:** The GUI makes pixel sorting accessible for rapid experimentation. You can see results instantly and dial in parameters before committing to batch processing video frames.
- **Key Technique:** Threshold-based interval detection. Instead of sorting entire rows, it identifies intervals of pixels that meet brightness/hue/saturation thresholds, then sorts only within those intervals. The threshold parameters control how much of the image gets affected.
- **Our Use:** Study the threshold interval logic for our automated pipeline. The ability to define "only sort pixels between brightness X and Y" gives precise control over which parts of an image get the glitch treatment.

---

### pixelsort (satyarth)
- **URL:** https://github.com/satyarth/pixelsort
- **Stack:** Python, PIL/Pillow
- **What:** The original popular Python pixel sorting library. Sorts pixels in rows/columns based on lightness thresholds. Can sort at any angle, not just horizontal/vertical.
- **Why It's Cool:** The foundational pixel sort library that inspired most others. Clean, hackable code. The angle parameter allows diagonal sorting which produces unique flowing effects that horizontal-only tools cannot create.
- **Key Technique:** Lightness-threshold interval sorting with angular rotation. The image is rotated by the specified angle, sorted horizontally, then rotated back. Intervals are defined by lightness thresholds -- only pixels between upper and lower lightness values are sorted.
- **Our Use:** Install via `pip install pixelsort`. Use the Python API for batch frame processing. Animate the angle parameter across frames for a sweeping, rotating pixel sort effect.

---

## 2. OpenCV Creative Coding Projects

### Generative-OpenCV (zradlicz)
- **URL:** https://github.com/zradlicz/Generative-OpenCV
- **Stack:** OpenCV, Python, numpy
- **What:** A collection of generative art experiments using OpenCV as a drawing canvas. Includes particle systems, flow fields, and procedural patterns all rendered through OpenCV's drawing primitives.
- **Why It's Cool:** Proves OpenCV is not just for computer vision -- it is a full creative coding canvas. The drawing primitives (circles, lines, polygons) combined with numpy array manipulation create surprisingly beautiful generative art.
- **Key Technique:** Using OpenCV's drawing functions (cv2.circle, cv2.line, cv2.polylines) on blank numpy arrays to create generative patterns. Particle systems where each particle leaves a trail, creating organic flowing images.
- **Our Use:** Use OpenCV as our primary rendering engine instead of PIL for effects that need real-time preview. OpenCV's imshow provides instant visual feedback during development.

---

### OpenCV Optical Flow Visualization (technique)
- **URL:** https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html
- **Stack:** OpenCV, numpy
- **What:** Dense optical flow (Farneback method) computes motion vectors for every pixel between frames. When visualized as color (hue = direction, saturation = magnitude), it creates psychedelic motion maps.
- **Why It's Cool:** Turns invisible motion into visible art. A person walking becomes a flowing river of color. A dancer becomes a kaleidoscope. The motion itself becomes the subject, not the person creating it.
- **Key Technique:** `cv2.calcOpticalFlowFarneback()` returns a 2-channel array of motion vectors. Convert to polar coordinates (magnitude, angle), map angle to hue, magnitude to value in HSV color space, then convert to BGR for display. The result is a real-time motion painting.
- **Our Use:** Layer optical flow visualization over original video at partial opacity. Use the motion magnitude to drive other effects (more motion = more glitch). Feed optical flow data into pixel sort intensity.

---

### OpenCV Edge Detection Art (technique)
- **URL:** https://docs.opencv.org/4.x/da/d22/tutorial_py_canny.html
- **Stack:** OpenCV, numpy
- **What:** Canny edge detection, Laplacian, and Sobel filters extract line art from any video. Combined with morphological operations (dilate, erode), you can create hand-drawn animation effects.
- **Why It's Cool:** Turns any video into what looks like pencil sketches, ink drawings, or rotoscoped animation. Apply adaptive thresholding after edge detection for a graphic novel look. Chain with color quantization for full cel-shaded animation.
- **Key Technique:** Pipeline: Gaussian blur -> Canny edge detection -> dilate to thicken lines -> bitwise_not for white lines on black. For the "cartoon" look: bilateral filter (preserves edges while smoothing) -> color quantization -> edge overlay.
- **Our Use:** Process music video footage to create a "hand-drawn" version. Layer edge-detected footage over the original with blend modes. Use edge maps as masks for selective glitch effects.

---

### OpenCV Morphological Art (technique)
- **URL:** https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html
- **Stack:** OpenCV, numpy
- **What:** Morphological operations (erosion, dilation, opening, closing, gradient, top hat, black hat) with custom structuring elements create organic, cellular visual effects when applied creatively.
- **Key Technique:** Use unusual structuring elements (crosses, diamonds, large ellipses) with iterative morphological operations. Apply morphological gradient (dilation minus erosion) for glowing edge effects. Chain opening and closing with different kernel sizes for cellular/organic textures.
- **Why It's Cool:** These operations are computationally cheap (real-time on video) and produce effects that look biological -- like cell division, crystal growth, or coral patterns.
- **Our Use:** Apply morphological operations to video frames for organic-feeling distortion. Use the morphological gradient as a glow/outline effect. Animate kernel size over time for evolving textures.

---

### OpenCV Color Space Manipulation Art (technique)
- **URL:** https://docs.opencv.org/4.x/df/d9d/tutorial_py_colorspaces.html
- **Stack:** OpenCV, numpy
- **What:** Convert between color spaces (BGR, HSV, LAB, YCrCb) and manipulate individual channels for surreal color effects. Swap channels between color spaces, rotate hue, isolate chrominance.
- **Why It's Cool:** Working in HSV lets you rotate hue independently (psychedelic color cycling). Working in LAB lets you manipulate perceptual lightness separately from color. YCrCb separation creates glitchy color bleeding.
- **Key Technique:** Convert to HSV, add a value to the H channel (modulo 180), convert back. This rotates all colors around the color wheel. Animate the rotation value for smooth color cycling. For glitch: swap the Cr and Cb channels in YCrCb space for eerie color inversion that differs from simple RGB inversion.
- **Our Use:** Audio-reactive hue rotation: map bass frequency amplitude to hue shift amount. Louder bass = more hue rotation. Combine with other glitch effects for layered results.

---

### OpenCV Face/Body Tracking for Generative Art (technique)
- **URL:** https://docs.opencv.org/4.x/d2/d99/tutorial_js_face_detection.html
- **Stack:** OpenCV, numpy (Haar cascades or MediaPipe)
- **What:** Use face detection (Haar cascades) or body pose estimation (MediaPipe) to drive generative visual effects anchored to detected body parts.
- **Why It's Cool:** The performer's body becomes the controller. Raise a hand, and particles explode from that point. Turn your head, and the glitch follows your gaze. This is how interactive art installations work.
- **Key Technique:** Detect face/body landmarks with cv2.CascadeClassifier or MediaPipe. Use landmark positions as coordinates for drawing, particle emission points, or distortion centers. Apply radial distortion (bulge/pinch) centered on detected face position.
- **Our Use:** Track the performer in music video footage. Apply targeted effects to face region only (face melting, pixel sorting around the head). Use hand positions to define regions of glitch intensity.

---

## 3. FFmpeg Creative Pipelines

### FFmpeg Artschool (AMIA Open Source)
- **URL:** https://github.com/amiaopensource/ffmpeg-artschool
- **Scripts:** https://amiaopensource.github.io/ffmpeg-artschool/scripts.html
- **Stack:** FFmpeg, Bash
- **What:** A comprehensive collection of Bash scripts wrapping creative FFmpeg filter chains. Includes: audioviz, bitplane, blend, chromakey, colorizer, corruptor, echo, lagfun, life, lumakey, pseudocolor, rainbow-trail, tblend_glitch, and many more.
- **Why It's Cool:** The single best educational resource for creative FFmpeg. Every script is documented, includes preview mode (-p flag), and outputs ProRes HQ. The "corruptor" and "tblend_glitch" scripts are particularly relevant for glitch art.
- **Key Technique:** Filter chain composition. Scripts demonstrate how to chain multiple FFmpeg filters with semicolons and commas. Example: `tblend` (temporal blending between frames) creates ghost/echo/trail effects. `lagfun` creates frame-accumulation decay effects.
- **Our Use:** Run these scripts directly on our video files. Study the filter chains and adapt them into our Python pipeline using subprocess calls to FFmpeg. The "audioviz" script shows how to create audio-reactive visuals purely in FFmpeg.

---

### NeuroWinter's FFmpeg Glitch Cheatsheet
- **URL:** https://gist.github.com/NeuroWinter/e557bfc555118ed68df88e8e51f03177
- **Stack:** FFmpeg
- **What:** A concise collection of FFmpeg commands specifically for creating glitch art effects. Covers displacement maps, datamoshing via FFmpeg, blend modes, and feedback effects.
- **Why It's Cool:** No-dependency glitch art. Every effect is a single FFmpeg command. No Python, no libraries, just FFmpeg and a terminal. Perfect for rapid prototyping and batch processing.
- **Key Technique:** Key commands include: using `-bsf:v noise` for bitstream-level corruption, `tblend` with various blend modes for temporal smearing, and the displacement map filter `displace` for warping video using another video as the displacement source.
- **Our Use:** Bookmark this gist. Use these commands as the FFmpeg subprocess calls in our Python pipeline. The displacement map technique is especially powerful -- use audio waveform visualizations as displacement sources to create audio-reactive warping.

---

### FFmpeg Displacement Map Experiments
- **URL:** https://abissusvoide.wordpress.com/2018/05/23/ffmpeg-displacement-map-experiments/
- **Additional:** https://www.glitch.cool/vaeprism/ffmpeg-displacement-maps/
- **Stack:** FFmpeg
- **What:** Detailed experiments using FFmpeg's `displace` filter to warp video using displacement maps. A displacement map is any image/video whose pixel values are interpreted as X/Y offset instructions for the source video.
- **Why It's Cool:** Displacement maps turn any image into a distortion instruction. Use a noise texture for organic warping, a gradient for lens effects, or another video for cross-source contamination. The results look like physical analog video corruption.
- **Key Technique:** `ffmpeg -i input.mp4 -i dispmap.mp4 -filter_complex "[0][1][1]displace" output.mp4`. The displacement map's red channel controls horizontal displacement, green controls vertical. Scale the map values to control intensity.
- **Our Use:** Generate displacement maps from audio (waveform visualization as displacement source). Use Perlin noise textures as displacement maps for organic warping. Use optical flow output as displacement for motion-guided distortion.

---

### Kaspar's FFmpeg Glitch Generators
- **URL:** https://www.kaspar.wtf/blog/glitch-patterns-using-ffmpeg-generators
- **Stack:** FFmpeg
- **What:** Using FFmpeg's built-in signal generators (mandelbrot, life, testsrc, color) as raw material for glitch patterns. These generators create synthetic video that can be blended with real footage.
- **Why It's Cool:** FFmpeg can generate its own video from mathematical formulas. The mandelbrot generator creates infinitely zoomable fractal footage. The life generator runs Conway's Game of Life. Blend these with real video for mathematical overlays.
- **Key Technique:** `ffmpeg -f lavfi -i mandelbrot=s=1920x1080 -t 10 mandelbrot.mp4` generates 10 seconds of Mandelbrot fractal zoom. Use `blend` filter to composite this over real video. The `cellauto` filter generates cellular automata patterns.
- **Our Use:** Generate synthetic textures and blend them with music video footage. Use cellular automata patterns as displacement maps. Layer Mandelbrot zooms at low opacity for a mathematical undercurrent.

---

### FFmpeg Feedback Loop Techniques
- **URL:** https://amiaopensource.github.io/ffmpeg-artschool/scripts.html (lagfun, echo, blend scripts)
- **Stack:** FFmpeg
- **What:** Creating video feedback effects using temporal blend modes. The `lagfun` filter accumulates frames with decay, creating ghostly trails. The `tblend` filter blends consecutive frames using various mathematical blend modes (difference, multiply, screen, etc.).
- **Why It's Cool:** Video feedback is one of the oldest video art techniques (Nam June Paik, 1960s). These FFmpeg commands recreate analog feedback digitally. The `difference` blend mode between frames creates edge-detection-like effects that pulse with motion.
- **Key Technique:** `ffmpeg -i input.mp4 -vf "lagfun=decay=0.95" output.mp4` creates ghostly trails where brighter values persist longer. `tblend=all_mode=difference` shows only what changed between frames. Chain these for recursive feedback.
- **Our Use:** Apply lagfun to music video footage for ethereal trailing effects. Use tblend=difference to create pulsing edge effects that react to movement. Stack multiple temporal effects for dense layered feedback.

---

### osromusic/ffmpeg-experiments
- **URL:** https://github.com/osromusic/ffmpeg-experiments
- **Stack:** FFmpeg, Bash
- **What:** A collection of scripts and FFmpeg commands used to create video glitch art, from a musician's perspective. Includes commands for glitch generation, artifact creation, and creative encoding tricks.
- **Why It's Cool:** Created by a musician for musicians. The effects are designed with music video aesthetics in mind, not just abstract art. The workflow is practical: input a clip, get a glitched result, drop it in your video editor.
- **Key Technique:** Multi-pass encoding with intentionally wrong parameters. Encoding at extremely low bitrates, wrong frame rates, or mismatched codecs creates authentic compression artifacts. Re-encoding an already compressed video amplifies existing artifacts.
- **Our Use:** Study the musician's workflow. These are the exact kind of quick-and-dirty commands needed for music video production. Integrate the best commands into our Python pipeline.

---

### FFmpeg Audio-Reactive Video Generation (technique)
- **URL:** https://amiaopensource.github.io/ffmpeg-artschool/scripts.html (audioviz script)
- **Stack:** FFmpeg
- **What:** FFmpeg's `showcqt` (constant-Q transform), `showfreqs`, `showspectrum`, and `avectorscope` filters generate real-time audio visualizations that can be blended with video or used as displacement maps.
- **Why It's Cool:** Pure FFmpeg, no Python needed. The audio visualization becomes a filter you can composite with any video. Use the audio spectrum as a displacement map and the video literally bends to the music.
- **Key Technique:** `ffmpeg -i audio.mp3 -i video.mp4 -filter_complex "[0:a]showcqt=s=1920x1080[viz];[1:v][viz]blend=all_mode=screen" output.mp4`. This generates a constant-Q spectrum from the audio and screen-blends it with the video.
- **Our Use:** Use showcqt output as a displacement map for our video. The audio literally deforms the video. This is a zero-code audio-reactive pipeline that can be called from Python via subprocess.

---

## 4. PIL/Pillow Pixel Art and Corruption

### Python-Pillow-Scripts (mthaier)
- **URL:** https://github.com/mthaier/Python-Pillow-Scripts
- **Stack:** Python, PIL/Pillow
- **What:** A collection of experimental filters and generative art scripts built entirely with PIL/Pillow. Includes custom convolution kernels, color manipulation effects, and procedural texture generators.
- **Why It's Cool:** Demonstrates how far you can push PIL beyond its intended use. Custom convolution kernels create effects that standard filters cannot. The experimental approach produces genuinely original visual effects.
- **Key Technique:** Custom ImageFilter.Kernel definitions with unusual kernel matrices. For example: asymmetric kernels that emphasize directional features, oversized kernels (7x7, 9x9) for dramatic blur/sharpen effects, and negative-value kernels for emboss/edge effects.
- **Our Use:** Create a library of custom convolution kernels tuned for glitch aesthetics. Apply different kernels to different regions of the frame based on audio analysis. Animate kernel values over time.

---

### GenerativeArtWithPIL
- **URL:** https://github.com/GrowingUnderTheTree/GenerativeArtWithPIL
- **Stack:** Python, PIL/Pillow, random
- **What:** Generative art system that creates abstract compositions using only PIL's drawing primitives (lines, rectangles, ellipses, polygons) with randomized parameters.
- **Why It's Cool:** Shows that compelling generative art does not require complex math. Simple geometric primitives with randomized colors, positions, and sizes create surprisingly rich compositions. The constraint of using only PIL forces creative solutions.
- **Key Technique:** Layered random geometry. Draw hundreds of semi-transparent shapes (using RGBA with low alpha) on top of each other. The accumulation of transparency creates depth and complexity from simple elements.
- **Our Use:** Generate abstract backgrounds or overlay textures for video frames. Use audio features to control the randomization parameters (beat = burst of shapes, sustained notes = flowing lines).

---

### Kaleidoscope Generator (onojk)
- **URL:** https://github.com/onojk/kaleidoscope-generator
- **Stack:** Python, PIL/Pillow
- **What:** Generates kaleidoscopic mandalas from source images using mirrored triangle tiling, layered symmetry, and high-density grid generation at custom scales.
- **Why It's Cool:** Takes any photo and transforms it into intricate mandala patterns. The symmetry operations (reflection, rotation, tiling) create mesmerizing complexity from simple source material. Multiple tiling algorithms produce distinct mandala styles.
- **Key Technique:** Triangle extraction from source image, then mirroring and rotating to create N-fold symmetry. The source triangle is reflected across multiple axes, then rotated N times around a center point. Grid generation tiles the resulting mandala at configurable density.
- **Our Use:** Process music video frames into kaleidoscopic versions. Animate the number of symmetry folds over time. Use different source regions of the video as the triangle source for each frame.

---

### PIL Channel Splitting and Recombination (technique)
- **URL:** Built into PIL/Pillow
- **Stack:** Python, PIL/Pillow
- **What:** Split an image into R, G, B (or C, M, Y, K) channels, manipulate each independently, then recombine. Offset channels spatially for chromatic aberration. Swap channels between different images for color contamination.
- **Why It's Cool:** Channel displacement (shifting R, G, B by different pixel amounts) is the signature look of digital glitch art. It simulates the way analog video signals corrupt -- each color channel drifts independently.
- **Key Technique:** `r, g, b = img.split()` then `ImageChops.offset(r, 10, 5)` to shift the red channel 10px right and 5px down. Recombine with `Image.merge('RGB', (r_shifted, g, b_shifted))`. Vary offset amounts per frame for animated chromatic aberration.
- **Our Use:** Core glitch technique. Apply audio-reactive channel displacement -- bass hits cause red channel to jump, treble causes blue to shift. Animate offsets over time for a drifting, unstable look.

---

### PIL Image Corruption via BytesIO (technique)
- **URL:** Built into PIL/Pillow + io.BytesIO
- **Stack:** Python, PIL/Pillow, io
- **What:** Save an image to a BytesIO buffer in JPEG format (with controlled quality), corrupt bytes in the buffer, then re-open the corrupted JPEG. The JPEG decoder attempts to reconstruct the image from corrupted data, producing authentic compression artifacts.
- **Why It's Cool:** This produces real JPEG glitch artifacts -- the colored blocks, smeared regions, and shifted scanlines that happen when JPEG data is corrupted. No filter can replicate this because it exploits the actual JPEG decoding algorithm.
- **Key Technique:** `buf = io.BytesIO(); img.save(buf, 'JPEG', quality=X); data = bytearray(buf.getvalue()); data[random_offset] = random_byte; corrupted = Image.open(io.BytesIO(bytes(data)))`. Skip the first ~600 bytes (JPEG header) to avoid destroying the file entirely.
- **Our Use:** Apply to video frames with varying corruption intensity. Lower JPEG quality before corruption amplifies artifacts. Map corruption amount to audio amplitude for audio-reactive JPEG destruction.

---

### PIL Procedural Texture Generation (technique)
- **URL:** Built into PIL/Pillow + numpy
- **Stack:** Python, PIL/Pillow, numpy
- **What:** Generate textures procedurally using numpy arrays -- noise, gradients, patterns, cellular automata -- then convert to PIL Images for compositing with video frames.
- **Why It's Cool:** You can generate infinite unique textures without any source material. Plasma effects, wood grain, marble, clouds -- all from mathematical functions applied to coordinate arrays.
- **Key Technique:** Create a numpy array of coordinates, apply mathematical functions (sin, cos, noise), map to color values, convert to PIL Image. For plasma: `np.sin(x/16.0) * 128 + np.sin(y/8.0) * 128`. For interference patterns: `np.sin(np.sqrt(x**2 + y**2))`.
- **Our Use:** Generate procedural textures and use them as: overlay layers, displacement maps, alpha masks for selective glitch effects, or standalone generative backgrounds.

---

## 5. MoviePy Creative Projects

### MoviePy (Zulko)
- **URL:** https://github.com/Zulko/moviepy
- **Stack:** Python, FFmpeg, numpy, ImageIO
- **What:** The core video editing library for Python. Cuts, concatenations, title insertions, compositing, and custom effects. Every frame is a numpy array, making it a bridge between all our other tools.
- **Why It's Cool:** MoviePy is the glue that connects PIL, OpenCV, and FFmpeg in Python. Any function that takes a numpy array (frame) and returns a numpy array can be used as a video effect. This means every OpenCV filter, every PIL operation, every numpy manipulation becomes a MoviePy effect.
- **Key Technique:** Custom effects via `fl_image`: `clip.fl_image(my_effect_function)` where `my_effect_function(frame) -> frame`. The function receives and returns numpy arrays. Chain multiple effects: `clip.fl_image(glitch).fl_image(pixelsort).fl_image(color_shift)`.
- **Our Use:** MoviePy is our pipeline orchestrator. Read video with MoviePy, apply our custom effect functions (which internally use OpenCV/PIL/numpy), then write the result. Use `CompositeVideoClip` for layering multiple processed versions.

---

### Jale the Black Cat (cinematic short with MoviePy)
- **URL:** https://github.com/mikbalyilmaz/-Jaletheblackcat
- **Stack:** Python, MoviePy
- **What:** A 37-second cinematic short film built entirely in code with MoviePy. Layers voices, sound effects, and background music with dynamic on-screen text, transitions, and intro-style captions.
- **Why It's Cool:** Proves you can make a complete, emotionally resonant short film entirely in Python. No video editor. The text animations, audio layering, and smooth transitions are all programmatic.
- **Key Technique:** Multi-track audio compositing with `CompositeAudioClip` and multi-layer video compositing with `CompositeVideoClip`. Text animation using `TextClip` with position functions that change over time. Crossfade transitions between scenes.
- **Our Use:** Study the audio/video synchronization approach. Use the text animation techniques for lyric overlays in music videos. The multi-track audio compositing is directly useful for mixing stems with video.

---

### MoviePy Audio-Reactive Effects (technique)
- **URL:** https://zulko.github.io/moviepy/ (core docs)
- **Stack:** Python, MoviePy, librosa, numpy
- **What:** Extract audio features (amplitude, frequency, beat) from the soundtrack, then use those features to drive visual parameters in MoviePy effect functions.
- **Why It's Cool:** The video literally dances to the music. Every bass hit can trigger a visual event. The connection between sound and image is mathematical and precise.
- **Key Technique:** Extract audio with `clip.audio.to_soundarray()`, analyze with librosa (onset detection, beat tracking, spectral features), then use the analysis data inside `fl_image` or `fl` effect functions: `def effect(get_frame, t): frame = get_frame(t); amplitude = audio_features[int(t * sr)]; return apply_glitch(frame, intensity=amplitude)`.
- **Our Use:** This is the core architecture for audio-reactive music videos. Build effect functions that accept intensity parameters, then drive those parameters from librosa analysis. Every effect we build should accept audio-driven parameters.

---

### MoviePy Green Screen / Compositing (technique)
- **URL:** https://zulko.github.io/moviepy/ (masking and compositing)
- **Stack:** Python, MoviePy, numpy
- **What:** Chroma keying (green screen removal), alpha compositing, and mask-based layer blending in MoviePy. Create masks from color ranges, luminance thresholds, or arbitrary numpy arrays.
- **Why It's Cool:** Enables the classic music video trick of placing performers in impossible environments. But more creatively: use glitch-processed footage as the background layer, with clean performer footage composited on top. Or invert it: clean background, glitched performer.
- **Key Technique:** `clip.fx(vfx.mask_color, color=[0, 255, 0], thr=100, s=5)` for green screen. For arbitrary masks: create a mask clip from numpy arrays and use `clip.set_mask(mask_clip)`. Layer with `CompositeVideoClip([background, masked_foreground])`.
- **Our Use:** Composite clean and glitched versions of the same footage. Use body segmentation masks (from OpenCV/MediaPipe) to selectively glitch the performer or the environment. Layer multiple processing passes.

---

## 6. Cross-Modal Audio-Video Projects

### sync-break-ultimate (glasilus)
- **URL:** https://github.com/glasilus/sync-break-ultimate
- **Stack:** Python, librosa, OpenCV, Tkinter
- **What:** Automated video synthesis and rhythmic editing tool specializing in Breakcore and IDM aesthetics. Features scene detection, configurable beat thresholds, and a full suite of glitched visual effects including datamosh simulation.
- **Why It's Cool:** Purpose-built for electronic music video creation. The beat detection drives scene cuts, effect intensity, and glitch timing. It understands that electronic music has specific rhythmic structures that should drive the visuals.
- **Key Technique:** Librosa onset detection and beat tracking control video editing decisions. When a beat is detected above a configurable threshold, the tool applies a visual effect (glitch, cut, datamosh simulation). Scene detection identifies natural cut points in source footage.
- **Our Use:** Directly relevant to our music video workflow. Study the beat-to-visual mapping architecture. Adapt the scene detection + beat sync approach for our own pipeline. The breakcore aesthetic aligns with glitch art sensibilities.

---

### audio-reactive-video-engine (vicsao)
- **URL:** https://github.com/vicsao/audio-reactive-video-engine
- **Stack:** Python, librosa, OpenCV
- **What:** An automated pipeline for generating 1080p music visualization videos. Analyzes audio features and generates reactive visuals rendered through OpenCV.
- **Why It's Cool:** A complete, working pipeline from audio file to finished 1080p video. No manual intervention. Feed it a song, get a visualization video. This is the architecture we want to build on top of.
- **Key Technique:** Full pipeline: librosa audio analysis (spectral features, beats, onsets) -> feature mapping to visual parameters -> OpenCV frame rendering -> video output. Each audio feature controls a specific visual attribute (frequency bands map to colors, amplitude maps to shape size, etc.).
- **Our Use:** Study and extend this pipeline. Replace the basic visualizations with our glitch effects while keeping the audio analysis and pipeline architecture. This is the skeleton we build our music video system on.

---

### Art-with-Python (AemieJ)
- **URL:** https://github.com/AemieJ/art-with-python
- **Stack:** Python, PIL/Pillow, numpy, audio libraries
- **What:** Pixel sorting implementation combined with sonification -- converting pixel colors to musical octaves to produce sounds from image data.
- **Why It's Cool:** Bidirectional audio-visual translation. Not just visuals from audio, but audio from visuals. Each pixel's color maps to a musical note, so an image becomes a composition. Pixel sort the image and the melody changes.
- **Key Technique:** Map pixel brightness/hue to musical frequency. Scan the image row by row, converting each pixel to a note at the corresponding frequency. The result is a musical composition derived from the image data. Pixel sorting the image rearranges the melody.
- **Our Use:** Create sonification of our glitch art. Generate audio from video frames, creating a complete audio-visual feedback loop: video -> audio -> drives new glitch effects -> new video.

---

### Hydra (Live Coding Visuals)
- **URL:** https://hydra.ojack.xyz/
- **Source:** https://github.com/hydra-synth/hydra
- **Stack:** JavaScript/WebGL (browser-based)
- **What:** A live-codeable video synth and coding environment. Inspired by analog modular synthesis -- chain transformations together like patching cables. Multiple framebuffers for feedback, modulation, and compositing.
- **Why It's Cool:** The fastest way to prototype visual effects. Type code, see results instantly. The modular synthesis metaphor (oscillators, modulators, feedback) translates directly to how audio people think about signal processing.
- **Key Technique:** Functional composition: `osc(10, 0.1, 1.5).rotate(0, 0.1).kaleid(4).out()` creates a rotating kaleidoscopic oscillator pattern. Audio input: `a.show()` then use `a.fft[0]` (bass), `a.fft[1]` (mids), `a.fft[2]` (treble) to drive any parameter.
- **Our Use:** Use Hydra for rapid prototyping of effect ideas in the browser before implementing in Python. The modular patching metaphor informs our Python pipeline architecture. Consider capturing Hydra output and combining with Python-processed footage.

---

### awesome-livecoding (TOPLAP)
- **URL:** https://github.com/toplap/awesome-livecoding
- **Stack:** Multi-language reference
- **What:** Comprehensive list of all live coding tools, languages, and environments for visuals and audio. Includes Python-compatible tools like Improviz, FoxDot, and more.
- **Why It's Cool:** A gateway to the entire live coding community. Discovers tools and techniques you would never find otherwise. The intersection of performance, code, and visuals.
- **Key Technique:** The live coding philosophy itself: write code in real-time as performance. Error is embraced, imperfection is aesthetic, the process is the art.
- **Our Use:** Reference for finding Python-compatible live visual tools. Explore FoxDot for live coded audio that drives our visual pipeline. Consider building a simple live coding interface for our glitch tools.

---

### Python Sonification (technique)
- **URL:** Technique using librosa + numpy + PIL
- **Stack:** Python, librosa, numpy, PIL/Pillow
- **What:** Converting image data to audio (sonification) and audio data to images (visualization). Each pixel row becomes a frequency spectrum, each column becomes a time step. Play the image as sound.
- **Why It's Cool:** Spectrograms are reversible. If you draw an image that looks like a spectrogram and convert it to audio, the audio will have that image embedded in its spectrogram. Artists have hidden images in music using this technique (Aphex Twin's "Windowlicker").
- **Key Technique:** Create a 2D numpy array representing frequency (rows) x time (columns). Set pixel values to amplitude. Use `librosa.griffinlim()` or inverse STFT to convert the 2D array to audio waveform. The image literally becomes sound.
- **Our Use:** Create visual-to-audio feedback: glitch an image, sonify it, use the resulting audio to drive new glitch effects. Or: embed hidden images in our music that only appear when viewed as spectrograms.

---

## 7. Datamosh-Specific Resources

### tomato.py (itsKaspar)
- **URL:** https://github.com/itsKaspar/tomato
- **Stack:** Python, numpy, struct
- **What:** The foundational AVI index breaker. Reorders frames inside the MOVI tag of AVI files by directly manipulating the binary structure. Uses numpy, struct, and itertools for byte-level file manipulation.
- **Why It's Cool:** This is where modern Python datamoshing started. The script operates at the container level, not the codec level, which means it manipulates the AVI file structure directly. This produces genuinely broken video rather than simulated glitch.
- **Key Technique:** Parse the AVI RIFF structure to locate the MOVI chunk, identify I-frames and P-frames by their chunk headers (00dc for video), then reorder, remove, or duplicate frames at the binary level. The AVI index is recalculated after manipulation.
- **Our Use:** Study the AVI binary format manipulation. The technique of working at the container level (rather than decoding/re-encoding) produces artifacts that are impossible to simulate. Extend to other container formats.

---

### Datamosh-Den (g-l-i-t-c-h-o-r-s-e)
- **URL:** https://github.com/g-l-i-t-c-h-o-r-s-e/Datamosh-Den
- **Stack:** Python, FFmpeg, MEncoder, Tkinter
- **What:** A GUI combining FFmpeg, MEncoder, and tomato.py into a unified datamosh workflow. Provides a visual interface for the three-tool datamosh pipeline.
- **Why It's Cool:** Solves the biggest pain point of datamoshing: the multi-tool workflow. Instead of manually running tomato.py, then FFmpeg, then MEncoder, everything is orchestrated through one interface.
- **Key Technique:** The three-phase datamosh pipeline: (1) FFmpeg converts source to AVI with specific codec settings, (2) tomato.py manipulates the AVI frame structure, (3) MEncoder or FFmpeg re-encodes the corrupted AVI to a playable format.
- **Our Use:** Understand the complete datamosh pipeline. The three-phase approach (prepare -> corrupt -> re-encode) is the canonical datamosh workflow. Automate this pipeline in our Python tools.

---

### datamosh-gui (willbearfruits)
- **URL:** https://github.com/willbearfruits/datamosh-gui
- **Stack:** Python, Tkinter, FFmpeg
- **What:** Professional-grade GUI for datamoshing with real-time preview and hardware-accelerated effects. Supports appending multiple video clips for complex datamosh sequences.
- **Why It's Cool:** Real-time preview of datamosh effects. You can see the result before committing to a full render. Hardware acceleration means smooth previewing even on complex effects. Multi-clip support enables transition datamoshing (where one scene melts into another).
- **Key Technique:** FFmpeg subprocess streaming for real-time preview. Instead of rendering to file, FFmpeg outputs to stdout pipe, which is read frame-by-frame and displayed in the GUI. I-frame removal and P-frame duplication with live feedback.
- **Our Use:** Study the real-time preview architecture. The FFmpeg-to-pipe-to-display pattern is exactly what we need for interactive development of our effects. The multi-clip approach enables music-video-style transition effects.

---

### H.264 Datamosh Web Tool (Artsen)
- **URL:** https://github.com/Artsen/H.264-Datamosh-Web-Tool
- **Stack:** Python, Flask, FFmpeg
- **What:** A web-based tool for H.264 datamoshing. Upload two video clips, the tool extracts and manipulates raw H.264 streams, concatenates them with I-frame removal, producing the classic datamosh transition effect.
- **Why It's Cool:** Works with H.264 (the modern codec) rather than AVI/MPEG-4 Part 2. This matters because most modern footage is H.264. The web interface makes it shareable. The two-clip concatenation is specifically designed for transition datamoshing.
- **Key Technique:** Extract raw H.264 bitstream with `ffmpeg -i input.mp4 -vcodec copy -an -bsf:v h264_mp4toannexb raw.h264`. Remove IDR frames (I-frames in H.264) from the second clip. Concatenate the bitstreams. The decoder applies the second clip's motion data to the first clip's image data.
- **Our Use:** Modern datamoshing for modern codecs. This technique works with footage straight from phones and cameras (which record H.264). The H.264 bitstream manipulation approach is more relevant than the legacy AVI approach.

---

### pydatamosh (Alexandrsv)
- **URL:** https://github.com/Alexandrsv/pydatamosh
- **Stack:** Python 3, FFmpeg
- **What:** A script that makes datamoshing with Python fun and easy. Handles the full pipeline from input video to datamoshed output with simple command-line options.
- **Why It's Cool:** Minimal friction. One command, one output. The script handles all the intermediate format conversion, frame manipulation, and re-encoding automatically.
- **Key Technique:** Automated pipeline: input video -> FFmpeg conversion to manipulable format -> I-frame identification and removal -> P-frame duplication -> FFmpeg re-encoding to output. All managed through subprocess calls.
- **Our Use:** Use as the quick-and-dirty datamosh tool when we just need a fast result. Study the automated pipeline for integration into our larger system.

---

### python-moshion (rjmoggach)
- **URL:** https://github.com/rjmoggach/python-moshion
- **Stack:** Python, FFmpeg
- **What:** A command-line wrapper to FFmpeg specifically designed for datamoshing two image sequences. Operates on frame sequences rather than video files, giving fine-grained control over which frames get moshed.
- **Why It's Cool:** Works with image sequences, which is how professional video pipelines often operate. This means you can datamosh specific frame ranges, leave others clean, and have frame-accurate control over where the mosh begins and ends.
- **Key Technique:** Frame sequence workflow: extract frames -> select source and target frame ranges -> apply datamosh between selected ranges -> reassemble. This gives frame-level precision that video-file-based tools lack.
- **Our Use:** Use for precision datamoshing in music videos. Datamosh only during the chorus, keep verses clean. Frame-sequence approach integrates with our OpenCV/PIL frame processing pipeline.

---

### FFglitch
- **URL:** https://ffglitch.org/
- **Stack:** C (FFmpeg fork), JavaScript/Python scripting
- **What:** A multimedia bitstream editor based on FFmpeg that allows precise editing of compressed video at the bitstream level. Features native JavaScript and Python 3 scripting for automated glitching. Provides direct access to motion vectors, quantization parameters, and macroblock types.
- **Why It's Cool:** The most powerful video glitch tool in existence. It does not simulate glitch -- it creates real encoding artifacts by modifying the actual bitstream data. Motion vector editing lets you redirect where the decoder looks for predicted data, creating surreal motion effects.
- **Key Technique:** `glitch_frame` function in JavaScript/Python is called for each frame. You can modify motion vectors (`mv` array), quantization matrices, macroblock types, and DCT coefficients. Setting `mv_delta_flag` forces motion vectors to be written even when there is no motion.
- **Our Use:** The ultimate datamosh tool. Use Python scripting to create audio-reactive motion vector manipulation. Map audio features to motion vector modifications: bass = downward vectors, treble = horizontal scatter. This creates effects that no other tool can produce.

---

### FF-Dissolve-Glitch (Akascape)
- **URL:** https://github.com/Akascape/FF-Dissolve-Glitch
- **Stack:** Python, FFmpeg, customtkinter
- **What:** A GUI tool that uses FFmpeg's motion interpolation (minterpolate) filter with intentionally wrong parameters to create dissolve-glitch effects. Based on Antonio Roberts's technique.
- **Why It's Cool:** Exploits FFmpeg's motion interpolation in ways it was never intended. When minterpolate tries to create intermediate frames between very different scenes, it produces beautiful, organic morphing artifacts. It is datamoshing through interpolation rather than frame removal.
- **Key Technique:** `ffmpeg -i input.mp4 -vf "minterpolate=mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" output.mp4`. The motion interpolation algorithm tries to find correspondences between frames that do not logically correspond, creating surreal morphing effects.
- **Our Use:** Quick morphing/dissolve glitch effects with a single FFmpeg command. Use on transitions between scenes in music videos. The minterpolate approach is computationally expensive but produces unique results.

---

## 8. Generative Art with Python

### awesome-creative-coding (terkelg)
- **URL:** https://github.com/terkelg/awesome-creative-coding
- **Stack:** Multi-language reference (strong Python section)
- **What:** The definitive curated list of creative coding resources. Covers frameworks, libraries, tutorials, books, and inspiration across all languages. Includes a dedicated Python section with links to py5, Processing Python mode, and creative coding notebooks.
- **Why It's Cool:** The single most comprehensive index of creative coding resources on the internet. If a tool, technique, or community exists in creative coding, it is listed here. Updated regularly by the community.
- **Key Technique:** Reference resource -- the technique here is knowing where to look. When stuck on a creative coding problem, search this list first.
- **Our Use:** Bookmark and reference regularly. When we need a new technique or tool, check here before building from scratch. The Python sections are directly relevant.

---

### encre (MichailSemoglou)
- **URL:** https://github.com/MichailSemoglou/encre
- **Stack:** Python, py5, Processing Python Mode, OpenCV
- **What:** A creative coding course with 17 lessons and a 5-day advanced workshop. Covers generative art, computer vision, interactive visuals, particles, flow fields, face detection, ML art, and installation art. Built on py5.
- **Why It's Cool:** A complete curriculum for creative coding in Python. Covers the exact intersection we care about: generative art + computer vision + interactivity. The flow fields and particle systems lessons are directly applicable to music video effects.
- **Key Technique:** Flow fields (vector fields that guide particle movement), particle systems with physics, face detection driving generative visuals, ML-based art generation. All implemented in Python with py5 and OpenCV.
- **Our Use:** Work through the lessons to learn flow fields and particle systems. These techniques create organic, fluid motion that pairs beautifully with music. Adapt the face detection + generative visuals for music video performer effects.

---

### noise library (caseman)
- **URL:** https://github.com/caseman/noise
- **PyPI:** https://pypi.org/project/noise/
- **Stack:** Python (C extension)
- **What:** Native-code implementation of Perlin "improved" noise and Perlin simplex noise for Python. Fast, well-optimized, supports 2D, 3D, and 4D noise.
- **Why It's Cool:** Perlin noise is the foundation of natural-looking procedural generation. Clouds, terrain, fire, water, organic textures -- all built on noise functions. The 3D version means you can generate 2D noise that evolves smoothly over time (the third dimension is time).
- **Key Technique:** `noise.pnoise2(x/scale, y/scale, octaves=6, persistence=0.5, lacunarity=2.0)` generates 2D Perlin noise at position (x,y). For animation: `noise.pnoise3(x/scale, y/scale, t/scale)` where t is time. The noise value smoothly varies, creating organic flowing patterns.
- **Our Use:** Generate displacement maps that evolve over time. Use noise values to drive glitch parameters (noise > 0.5 = apply pixel sort, else leave clean). Create flowing, organic distortion fields.

---

### pythonperlin (timpyrkov)
- **URL:** https://github.com/timpyrkov/pythonperlin
- **Stack:** Python, numpy
- **What:** Comprehensive noise generator supporting Perlin and Worley noise in N dimensions. Features seamless tiling, domain warping, octaves, and 2D/3D surface grid generation.
- **Why It's Cool:** Worley noise (cellular noise) creates patterns that look like cracked earth, cell structures, or stained glass. Domain warping feeds noise into itself, creating impossibly organic swirling patterns. Seamless tiling means noise textures loop without visible seams.
- **Key Technique:** Domain warping: `noise(x + noise(x, y), y + noise(x, y))`. Feeding noise coordinates through another noise function creates recursive distortion. The result looks like fluid dynamics or geological formations.
- **Our Use:** Domain-warped noise as displacement maps for video frames. The recursive distortion creates organic warping effects that evolve smoothly. Seamless tiling means looping background textures for music videos.

---

### perlin-numpy (pvigier)
- **URL:** https://github.com/pvigier/perlin-numpy
- **Stack:** Python, numpy
- **What:** A fast and simple Perlin noise generator using only numpy. Generates 2D Perlin noise arrays efficiently using vectorized numpy operations.
- **Why It's Cool:** Zero dependencies beyond numpy. Extremely fast because all operations are vectorized. The output is a raw numpy array, which plugs directly into our OpenCV/PIL/MoviePy pipeline without conversion.
- **Key Technique:** Vectorized gradient computation using numpy broadcasting. Instead of computing noise value-by-value, the entire noise field is computed in a single vectorized operation. This makes it fast enough for real-time video frame generation.
- **Our Use:** Fast noise generation for per-frame displacement maps. Because it outputs numpy arrays directly, integrate with `cv2.remap()` for real-time video distortion driven by animated noise fields.

---

### Generative_Art (Ishasharmax)
- **URL:** https://github.com/Ishasharmax/Generative_Art
- **Stack:** Python, Processing, p5.js, PIL
- **What:** A gallery of generative art with source code, spanning multiple techniques: 10-print patterns, fronkonstin technique, Perlin noise fields, and more. Cross-platform implementations in Python, JavaScript, and R.
- **Why It's Cool:** Each piece comes with the code that created it and an explanation of the technique. This is a cookbook of generative art recipes. The variety of techniques (from simple 10-print to complex noise fields) shows the range of what is possible.
- **Key Technique:** The "fronkonstin" technique: parametric equations with random variation to create flowing, organic line art. The 10-print technique: random selection of / and \ characters to create maze-like patterns (the simplest possible generative art).
- **Our Use:** Implement these techniques in Python and use as video overlays. The 10-print pattern makes a great glitch-style texture. Perlin noise fields create organic flow patterns that pair well with music.

---

### fractalartmaker (asweigart)
- **URL:** https://github.com/asweigart/fractalartmaker
- **Stack:** Python, turtle graphics
- **What:** A module for creating fractal art using Python's built-in turtle module. Generates L-system fractals (Sierpinski triangle, Koch snowflake, dragon curve, plant-like branching structures) with customizable parameters.
- **Why It's Cool:** L-systems generate infinitely complex branching structures from simple rules. Change one rule and get a completely different organic pattern. The turtle graphics approach means each fractal is drawn stroke-by-stroke, which can be animated.
- **Key Technique:** L-system string rewriting: start with an axiom (e.g., "F"), apply production rules (e.g., "F" -> "F+F-F-F+F") for N iterations, then interpret the resulting string as turtle movement commands (F=forward, +=turn left, -=turn right).
- **Our Use:** Render L-system fractals to PIL images and use as overlay textures. Animate the iteration count (complexity) over time. Use different L-system rules for different sections of a music video.

---

### Turtle-Fractals (tk744)
- **URL:** https://github.com/tk744/Turtle-Fractals
- **Stack:** Python, turtle graphics
- **What:** A 2D Lindenmayer system fractal generator. Parses L-system grammars and renders them using turtle graphics. Supports custom axioms, production rules, and rendering parameters.
- **Why It's Cool:** Clean implementation of L-system parsing that can be extended with custom rules. The separation of grammar definition from rendering means you can plug in any L-system rule set and get instant visual output.
- **Key Technique:** Grammar-based generation: define an alphabet of symbols, a set of production rules, and an interpretation mapping (which symbol means which turtle action). The grammar evolves the string, the interpretation draws it.
- **Our Use:** Generate unique branching patterns for each song section. Map musical parameters to L-system rules (tempo = branching angle, key = color palette). Render to numpy array for compositing with video frames.

---

### Introduction to Generative Art in Python Using Perlin Noise (tutorial)
- **URL:** https://www.gmschroeder.com/blog/intro_pyart1.html
- **Stack:** Python, PIL/Pillow, noise, numpy
- **What:** A detailed tutorial on creating generative art using Perlin noise in Python. Covers noise generation, color mapping, flow field construction, and particle system animation.
- **Why It's Cool:** Step-by-step tutorial that builds from basic noise to complete flow field visualizations. The flow field technique (using noise values as angles to guide particle movement) creates the signature look of generative art.
- **Key Technique:** Flow fields: generate a 2D grid of Perlin noise values, interpret each value as an angle. Place particles on the grid. Each particle moves in the direction indicated by the noise value at its position. The particles trace organic, flowing paths.
- **Our Use:** Implement flow fields and overlay on video frames. Particles trace paths that respond to the underlying noise field. Animate the noise field over time for evolving flow patterns. Use video brightness as an additional influence on particle direction.

---

## Quick Reference: Techniques by Category

### For Music Videos
| Technique | Tool | Difficulty |
|-----------|------|-----------|
| Beat-synced glitch cuts | librosa + MoviePy | Medium |
| Audio-reactive pixel sort | librosa + pixelsort | Medium |
| Channel displacement on bass hits | PIL + librosa | Easy |
| Datamosh transitions between scenes | FFmpeg/tomato.py | Hard |
| Face-tracked effects | OpenCV/MediaPipe + MoviePy | Medium |
| Audio-driven displacement maps | FFmpeg showcqt + displace | Medium |

### For Abstract Visuals
| Technique | Tool | Difficulty |
|-----------|------|-----------|
| Perlin noise flow fields | noise + PIL/OpenCV | Medium |
| L-system fractal overlays | fractalartmaker + PIL | Easy |
| Cellular automata patterns | FFmpeg cellauto / numpy | Medium |
| Domain-warped noise textures | pythonperlin + OpenCV | Medium |
| Optical flow visualization | OpenCV | Easy |

### For Maximum Chaos
| Technique | Tool | Difficulty |
|-----------|------|-----------|
| Byte-level JPEG corruption | PIL + BytesIO | Easy |
| Motion vector manipulation | FFglitch | Hard |
| Raw bitstream corruption | FFmpeg -bsf:v noise | Easy |
| Multi-pass re-encoding degradation | FFmpeg | Easy |
| Binary file corruption | crasher/glitch-tool | Easy |

---

## Pipeline Architecture

Based on studying all these projects, here is the recommended pipeline for our glitch video system:

```
Audio Input (WAV/MP3)
    |
    v
[librosa] Audio Analysis
    |-- Beat detection
    |-- Onset detection
    |-- Spectral features (bass, mid, treble energy)
    |-- Amplitude envelope
    |
    v
Feature Timeline (numpy arrays of audio features over time)
    |
    v
[MoviePy] Frame-by-frame Processing
    |
    +---> [OpenCV] Computer Vision Effects
    |       |-- Edge detection masks
    |       |-- Optical flow visualization
    |       |-- Face/body tracking
    |       |-- Color space manipulation
    |       |-- Morphological operations
    |
    +---> [PIL/Pillow] Image Corruption
    |       |-- Channel displacement
    |       |-- JPEG byte corruption
    |       |-- Pixel sorting (via pixelsort lib)
    |       |-- Kaleidoscope/symmetry
    |
    +---> [numpy] Generative Overlays
    |       |-- Perlin noise displacement maps
    |       |-- Flow field particles
    |       |-- Procedural textures
    |       |-- L-system fractals
    |
    +---> [FFmpeg subprocess] Heavy Effects
    |       |-- Datamoshing (I-frame removal)
    |       |-- Displacement map warping
    |       |-- Temporal blending (lagfun, tblend)
    |       |-- Motion interpolation glitch
    |
    v
[MoviePy] Compositing & Output
    |-- Layer compositing (clean + glitch versions)
    |-- Audio re-attachment
    |-- Final render to MP4
```

---

## Next Steps

1. **Install missing libraries:** `pip install pixelsort glitch-this noise` (add to our venv)
2. **Clone key repos for study:**
   - `git clone https://github.com/Akascape/Datamosher-Pro` (study effect functions)
   - `git clone https://github.com/amiaopensource/ffmpeg-artschool` (FFmpeg scripts)
   - `git clone https://github.com/glasilus/sync-break-ultimate` (audio-reactive architecture)
3. **Build a prototype pipeline** using the architecture above, starting with librosa analysis + MoviePy frame processing + one effect (channel displacement)
4. **Experiment with FFglitch** for motion vector manipulation -- this is the most unique technique in the collection
5. **Study the flow field tutorial** at gmschroeder.com for generative overlay techniques
