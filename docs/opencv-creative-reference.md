# OpenCV Creative Video Processing Reference

> **Package:** opencv-python 4.13.0
> **Import:** `import cv2 as cv` (or `import cv2`)
> **Purpose:** Computer vision, image/video processing, creative visual effects
> **Dependency:** numpy (always used together)

---

## Table of Contents

1. [Video Capture and Frame-by-Frame Processing](#1-video-capture-and-frame-by-frame-processing)
2. [Color Space Conversions](#2-color-space-conversions)
3. [Image Transformations](#3-image-transformations)
4. [Edge Detection](#4-edge-detection)
5. [Morphological Operations](#5-morphological-operations)
6. [Blending and Compositing](#6-blending-and-compositing)
7. [Contour Detection and Manipulation](#7-contour-detection-and-manipulation)
8. [Optical Flow for Motion Effects](#8-optical-flow-for-motion-based-effects)
9. [Feature Detection for Creative Uses](#9-feature-detection-for-creative-uses)
10. [Image Filtering](#10-image-filtering)
11. [Thresholding](#11-thresholding)
12. [Real-Time Video Processing Pipeline](#12-real-time-video-processing-pipeline)
13. [NumPy Pixel Manipulation](#13-numpy-pixel-manipulation)
14. [Creative Glitch Techniques](#14-creative-glitch-art-techniques)

---

## 1. Video Capture and Frame-by-Frame Processing

### VideoCapture - Reading Video

```python
import cv2 as cv
import numpy as np

# From file
cap = cv.VideoCapture('input.mp4')

# From webcam (0 = default camera)
cap = cv.VideoCapture(0)

# Check if opened successfully
if not cap.isOpened():
    print("Cannot open video source")
    exit()
```

### Reading Frames

```python
while True:
    ret, frame = cap.read()  # ret = bool, frame = numpy array (H, W, 3) BGR
    if not ret:
        print("End of video or can't receive frame")
        break

    # Process frame here...
    processed = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

    cv.imshow('output', processed)
    if cv.waitKey(1) == ord('q'):
        break

cap.release()
cv.destroyAllWindows()
```

### Video Properties

```python
# Get properties
width  = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))   # e.g. 1920
height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))  # e.g. 1080
fps    = cap.get(cv.CAP_PROP_FPS)                 # e.g. 30.0
total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
current_frame = int(cap.get(cv.CAP_PROP_POS_FRAMES))

# Set properties
cap.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv.CAP_PROP_POS_FRAMES, 100)  # Seek to frame 100
```

### VideoWriter - Saving Video

```python
# Define codec and create VideoWriter
fourcc = cv.VideoWriter_fourcc(*'XVID')  # or 'MJPG', 'X264', 'mp4v'
out = cv.VideoWriter('output.avi', fourcc, 30.0, (640, 480))
# Parameters: filename, fourcc, fps, (width, height)

# Write frames in a loop
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    frame = cv.flip(frame, 0)  # Example: flip vertically
    out.write(frame)

cap.release()
out.release()
```

### FourCC Codec Reference

| Codec | Extension | Notes |
|-------|-----------|-------|
| `XVID` | .avi | Widely supported, good quality |
| `MJPG` | .avi | Large files, fast encoding |
| `X264` | .mkv | Smallest files, best compression |
| `mp4v` | .mp4 | Standard MP4 codec |
| `DIVX` | .avi | Windows standard |
| `avc1` | .mp4 | H.264 on macOS |

### Display Functions

```python
cv.imshow('Window Name', frame)      # Show frame in window
key = cv.waitKey(1)                   # Wait 1ms, returns key code (-1 if none)
key = cv.waitKey(25)                  # 25ms = ~40fps playback
cv.destroyAllWindows()                # Close all windows
cv.destroyWindow('Window Name')       # Close specific window
```

---

## 2. Color Space Conversions

### cv.cvtColor() - The Core Conversion Function

```python
# Syntax
dst = cv.cvtColor(src, code)
```

### Common Conversions

```python
# BGR to Grayscale
gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

# BGR to HSV (Hue-Saturation-Value)
hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

# BGR to LAB (Lightness-A-B perceptual color)
lab = cv.cvtColor(frame, cv.COLOR_BGR2LAB)

# BGR to RGB (for matplotlib/PIL compatibility)
rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

# BGR to HLS (Hue-Lightness-Saturation)
hls = cv.cvtColor(frame, cv.COLOR_BGR2HLS)

# BGR to YCrCb (luminance + chrominance)
ycrcb = cv.cvtColor(frame, cv.COLOR_BGR2YCrCb)

# BGR to LUV
luv = cv.cvtColor(frame, cv.COLOR_BGR2Luv)

# Grayscale to BGR
bgr = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)

# HSV back to BGR
bgr = cv.cvtColor(hsv, cv.COLOR_HSV2BGR)
```

### HSV Ranges in OpenCV

| Channel | Range | Notes |
|---------|-------|-------|
| Hue | 0-179 | Different from standard 0-360! |
| Saturation | 0-255 | 0 = gray, 255 = fully saturated |
| Value | 0-255 | 0 = black, 255 = brightest |

### Color Isolation with HSV

```python
# Convert to HSV
hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

# Define range for blue color
lower_blue = np.array([110, 50, 50])
upper_blue = np.array([130, 255, 255])

# Create mask
mask = cv.inRange(hsv, lower_blue, upper_blue)

# Apply mask to original
result = cv.bitwise_and(frame, frame, mask=mask)
```

### Finding HSV Values for Any Color

```python
# Convert a BGR color to HSV
green_bgr = np.uint8([[[0, 255, 0]]])
green_hsv = cv.cvtColor(green_bgr, cv.COLOR_BGR2HSV)
print(green_hsv)  # [[[60 255 255]]]
# Use hue +/- 10 for range: [50, 100, 100] to [70, 255, 255]
```

### List All Available Conversions

```python
flags = [i for i in dir(cv) if i.startswith('COLOR_')]
print(len(flags))  # 200+ conversion flags
```

---

## 3. Image Transformations

### Resize

```python
# By scale factor
resized = cv.resize(frame, None, fx=0.5, fy=0.5, interpolation=cv.INTER_LINEAR)

# By exact dimensions
resized = cv.resize(frame, (640, 480), interpolation=cv.INTER_CUBIC)

# Interpolation methods:
# cv.INTER_NEAREST  - fastest, pixelated (good for glitch art)
# cv.INTER_LINEAR   - default, bilinear
# cv.INTER_AREA     - best for shrinking
# cv.INTER_CUBIC    - better quality, slower
# cv.INTER_LANCZOS4 - highest quality, slowest
```

### Translation (Shifting)

```python
rows, cols = frame.shape[:2]
# Shift 100px right, 50px down
M = np.float32([[1, 0, 100], [0, 1, 50]])
shifted = cv.warpAffine(frame, M, (cols, rows))
```

### Rotation

```python
rows, cols = frame.shape[:2]
# Rotate 45 degrees around center, scale 1.0
center = ((cols - 1) / 2.0, (rows - 1) / 2.0)
M = cv.getRotationMatrix2D(center, 45, 1.0)
# Parameters: center, angle (degrees, counterclockwise), scale
rotated = cv.warpAffine(frame, M, (cols, rows))
```

### Affine Transformation (Skew/Shear)

```python
rows, cols, ch = frame.shape

# Define 3 source points and 3 destination points
pts1 = np.float32([[50, 50], [200, 50], [50, 200]])
pts2 = np.float32([[10, 100], [200, 50], [100, 250]])

M = cv.getAffineTransform(pts1, pts2)
dst = cv.warpAffine(frame, M, (cols, rows))
```

### Perspective Transformation

```python
rows, cols, ch = frame.shape

# 4 source points -> 4 destination points
pts1 = np.float32([[56, 65], [368, 52], [28, 387], [389, 390]])
pts2 = np.float32([[0, 0], [300, 0], [0, 300], [300, 300]])

M = cv.getPerspectiveTransform(pts1, pts2)
dst = cv.warpPerspective(frame, M, (300, 300))
```

### Remap (Pixel Displacement)

```python
# remap() relocates pixels according to map arrays
# dst(x,y) = src(map_x(x,y), map_y(x,y))

rows, cols = frame.shape[:2]

# Create coordinate maps
map_x = np.zeros((rows, cols), dtype=np.float32)
map_y = np.zeros((rows, cols), dtype=np.float32)

# Example: Horizontal flip via remap
for i in range(rows):
    for j in range(cols):
        map_x[i, j] = cols - j
        map_y[i, j] = i

# Faster with meshgrid
map_y, map_x = np.mgrid[0:rows, 0:cols].astype(np.float32)

# Ripple/wave effect
map_x_wave = map_x + 20 * np.sin(2 * np.pi * map_y / 128)
map_y_wave = map_y + 20 * np.cos(2 * np.pi * map_x / 128)

remapped = cv.remap(frame, map_x_wave, map_y_wave, cv.INTER_LINEAR)
```

### Flip

```python
flipped_v = cv.flip(frame, 0)    # Vertical flip
flipped_h = cv.flip(frame, 1)    # Horizontal flip
flipped_both = cv.flip(frame, -1) # Both axes
```

---

## 4. Edge Detection

### Canny Edge Detection

```python
# Signature: cv.Canny(image, threshold1, threshold2, apertureSize=3, L2gradient=False)
edges = cv.Canny(frame, 100, 200)

# With custom parameters
edges = cv.Canny(frame, 50, 150, apertureSize=3, L2gradient=True)

# Recommended: blur first to reduce noise
blurred = cv.GaussianBlur(gray, (5, 5), 0)
edges = cv.Canny(blurred, 50, 150)
```

**Parameters:**
- `threshold1` (minVal): Below this = not an edge
- `threshold2` (maxVal): Above this = definite edge
- Between thresholds: edge only if connected to a definite edge
- `apertureSize`: Sobel kernel size (3, 5, or 7)
- `L2gradient`: True = more accurate gradient magnitude

### Sobel Edge Detection

```python
# Horizontal edges
sobel_x = cv.Sobel(gray, cv.CV_64F, 1, 0, ksize=5)
# Vertical edges
sobel_y = cv.Sobel(gray, cv.CV_64F, 0, 1, ksize=5)
# Combined
sobel_combined = cv.magnitude(sobel_x, sobel_y)

# Convert to uint8 for display
abs_sobel_x = cv.convertScaleAbs(sobel_x)
abs_sobel_y = cv.convertScaleAbs(sobel_y)
combined = cv.addWeighted(abs_sobel_x, 0.5, abs_sobel_y, 0.5, 0)
```

### Laplacian Edge Detection

```python
laplacian = cv.Laplacian(gray, cv.CV_64F)
laplacian_abs = cv.convertScaleAbs(laplacian)
```

### Scharr Filter (More Accurate than Sobel)

```python
scharr_x = cv.Scharr(gray, cv.CV_64F, 1, 0)
scharr_y = cv.Scharr(gray, cv.CV_64F, 0, 1)
```

---

## 5. Morphological Operations

### Kernel Creation

```python
# Simple rectangular kernel
kernel = np.ones((5, 5), np.uint8)

# Structured kernels
rect_kernel = cv.getStructuringElement(cv.MORPH_RECT, (5, 5))
ellipse_kernel = cv.getStructuringElement(cv.MORPH_ELLIPSE, (5, 5))
cross_kernel = cv.getStructuringElement(cv.MORPH_CROSS, (5, 5))
```

### Basic Operations

```python
# Erosion - shrinks white regions, removes small noise
erosion = cv.erode(img, kernel, iterations=1)

# Dilation - grows white regions, fills small holes
dilation = cv.dilate(img, kernel, iterations=1)
```

### Advanced Morphological Operations

```python
# Opening (erosion then dilation) - removes noise
opening = cv.morphologyEx(img, cv.MORPH_OPEN, kernel)

# Closing (dilation then erosion) - fills small holes
closing = cv.morphologyEx(img, cv.MORPH_CLOSE, kernel)

# Gradient (dilation minus erosion) - object outlines
gradient = cv.morphologyEx(img, cv.MORPH_GRADIENT, kernel)

# Top Hat (original minus opening) - bright spots on dark background
tophat = cv.morphologyEx(img, cv.MORPH_TOPHAT, kernel)

# Black Hat (closing minus original) - dark spots on bright background
blackhat = cv.morphologyEx(img, cv.MORPH_BLACKHAT, kernel)
```

---

## 6. Blending and Compositing

### addWeighted - Alpha Blending

```python
# dst = src1 * alpha + src2 * beta + gamma
# Both images must be same size
blended = cv.addWeighted(img1, 0.7, img2, 0.3, 0)
# Parameters: img1, alpha, img2, beta, gamma
# alpha + beta should = 1.0 for natural look
```

### Bitwise Operations

```python
# AND - keeps pixels where both are non-zero
result = cv.bitwise_and(img1, img2)
result = cv.bitwise_and(img1, img2, mask=mask)

# OR - keeps pixels where either is non-zero
result = cv.bitwise_or(img1, img2)

# XOR - keeps pixels where exactly one is non-zero
result = cv.bitwise_xor(img1, img2)

# NOT - inverts all pixels
result = cv.bitwise_not(img)
```

### Direct Addition and Subtraction

```python
# Saturated addition (clips at 255)
result = cv.add(img1, img2)

# Saturated subtraction (clips at 0)
result = cv.subtract(img1, img2)

# Absolute difference
result = cv.absdiff(img1, img2)
```

### ROI-Based Compositing (Logo Overlay)

```python
# Place a logo on an image using masking
logo = cv.imread('logo.png')
rows, cols, _ = logo.shape

# Define ROI on target image
roi = img[0:rows, 0:cols]

# Create mask from logo
logo_gray = cv.cvtColor(logo, cv.COLOR_BGR2GRAY)
_, mask = cv.threshold(logo_gray, 10, 255, cv.THRESH_BINARY)
mask_inv = cv.bitwise_not(mask)

# Black-out the logo area in ROI
bg = cv.bitwise_and(roi, roi, mask=mask_inv)
# Take only logo region from logo image
fg = cv.bitwise_and(logo, logo, mask=mask)

# Combine
combined = cv.add(bg, fg)
img[0:rows, 0:cols] = combined
```

---

## 7. Contour Detection and Manipulation

### Finding Contours

```python
# Convert to grayscale and threshold first
gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
ret, thresh = cv.threshold(gray, 127, 255, 0)

# Find contours
contours, hierarchy = cv.findContours(thresh, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
# Returns: list of contours (numpy arrays), hierarchy array
```

### Retrieval Modes

| Mode | Description |
|------|-------------|
| `cv.RETR_EXTERNAL` | Only outermost contours |
| `cv.RETR_LIST` | All contours, no hierarchy |
| `cv.RETR_CCOMP` | Two-level hierarchy |
| `cv.RETR_TREE` | Full hierarchy tree |

### Approximation Methods

| Method | Description |
|--------|-------------|
| `cv.CHAIN_APPROX_NONE` | All boundary points stored |
| `cv.CHAIN_APPROX_SIMPLE` | Compressed (e.g., rectangle = 4 points instead of hundreds) |

### Drawing Contours

```python
# Draw ALL contours (index -1) in green, thickness 3
cv.drawContours(frame, contours, -1, (0, 255, 0), 3)

# Draw specific contour (index 3)
cv.drawContours(frame, contours, 3, (0, 255, 0), 3)

# Fill contours (thickness = -1)
cv.drawContours(frame, contours, -1, (0, 255, 0), -1)
```

### Contour Properties

```python
for cnt in contours:
    # Area
    area = cv.contourArea(cnt)

    # Perimeter (True = closed contour)
    perimeter = cv.arcLength(cnt, True)

    # Bounding rectangle
    x, y, w, h = cv.boundingRect(cnt)

    # Minimum enclosing circle
    (cx, cy), radius = cv.minEnclosingCircle(cnt)

    # Fit ellipse (needs >= 5 points)
    if len(cnt) >= 5:
        ellipse = cv.fitEllipse(cnt)

    # Approximate polygon
    epsilon = 0.01 * cv.arcLength(cnt, True)
    approx = cv.approxPolyDP(cnt, epsilon, True)

    # Convex hull
    hull = cv.convexHull(cnt)

    # Moments (centroid, etc.)
    M = cv.moments(cnt)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
```

---

## 8. Optical Flow for Motion-Based Effects

### Lucas-Kanade Sparse Optical Flow

Tracks specific feature points between frames. Good for motion trails and tracking effects.

```python
import cv2 as cv
import numpy as np

cap = cv.VideoCapture('video.mp4')

# Parameters for Shi-Tomasi corner detection
feature_params = dict(
    maxCorners=100,
    qualityLevel=0.3,
    minDistance=7,
    blockSize=7
)

# Parameters for Lucas-Kanade optical flow
lk_params = dict(
    winSize=(15, 15),
    maxLevel=2,
    criteria=(cv.TERM_CRITERIA_EPS | cv.TERM_CRITERIA_COUNT, 10, 0.03)
)

# Read first frame and find corners
ret, old_frame = cap.read()
old_gray = cv.cvtColor(old_frame, cv.COLOR_BGR2GRAY)
p0 = cv.goodFeaturesToTrack(old_gray, mask=None, **feature_params)

# Create mask for drawing trails
mask = np.zeros_like(old_frame)
color = np.random.randint(0, 255, (100, 3))

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

    # Calculate optical flow
    p1, st, err = cv.calcOpticalFlowPyrLK(old_gray, frame_gray, p0, None, **lk_params)

    # Select good points
    if p1 is not None:
        good_new = p1[st == 1]
        good_old = p0[st == 1]

    # Draw motion trails
    for i, (new, old) in enumerate(zip(good_new, good_old)):
        a, b = new.ravel()
        c, d = old.ravel()
        mask = cv.line(mask, (int(a), int(b)), (int(c), int(d)), color[i].tolist(), 2)
        frame = cv.circle(frame, (int(a), int(b)), 5, color[i].tolist(), -1)

    img = cv.add(frame, mask)
    cv.imshow('Optical Flow', img)
    if cv.waitKey(30) & 0xff == 27:
        break

    old_gray = frame_gray.copy()
    p0 = good_new.reshape(-1, 1, 2)

cv.destroyAllWindows()
```

### Farneback Dense Optical Flow

Computes flow for every pixel. Perfect for motion-based glitch effects, displacement, and visualizations.

```python
cap = cv.VideoCapture('video.mp4')
ret, frame1 = cap.read()
prvs = cv.cvtColor(frame1, cv.COLOR_BGR2GRAY)
hsv = np.zeros_like(frame1)
hsv[..., 1] = 255  # Full saturation

while True:
    ret, frame2 = cap.read()
    if not ret:
        break

    next_gray = cv.cvtColor(frame2, cv.COLOR_BGR2GRAY)

    # Calculate dense optical flow
    flow = cv.calcOpticalFlowFarneback(
        prvs, next_gray, None,
        pyr_scale=0.5,   # Pyramid scale (<1, 0.5 = halve each level)
        levels=3,         # Number of pyramid levels
        winsize=15,       # Averaging window size
        iterations=3,     # Iterations at each level
        poly_n=5,         # Neighborhood size for polynomial expansion
        poly_sigma=1.2,   # Gaussian std for polynomial expansion
        flags=0
    )

    # Convert flow to polar coordinates for visualization
    mag, ang = cv.cartToPolar(flow[..., 0], flow[..., 1])
    hsv[..., 0] = ang * 180 / np.pi / 2       # Hue = direction
    hsv[..., 2] = cv.normalize(mag, None, 0, 255, cv.NORM_MINMAX)  # Value = magnitude
    bgr = cv.cvtColor(hsv.astype(np.uint8), cv.COLOR_HSV2BGR)

    cv.imshow('Dense Optical Flow', bgr)
    if cv.waitKey(30) & 0xff == 27:
        break

    prvs = next_gray

cv.destroyAllWindows()
```

**Farneback Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pyr_scale` | 0.5 | Image scale for pyramid (<1.0) |
| `levels` | 3 | Number of pyramid levels |
| `winsize` | 15 | Averaging window size |
| `iterations` | 3 | Iterations per pyramid level |
| `poly_n` | 5 | Neighborhood for polynomial expansion (5 or 7) |
| `poly_sigma` | 1.2 | Gaussian std for smoothing (1.1 for poly_n=5, 1.5 for poly_n=7) |

---

## 9. Feature Detection for Creative Uses

### ORB (Oriented FAST and Rotated BRIEF)

Fast, free alternative to SIFT. Good for finding interesting points in frames.

```python
import cv2 as cv
import numpy as np

img = cv.imread('image.jpg', cv.IMREAD_GRAYSCALE)

# Create ORB detector
orb = cv.ORB_create(nFeatures=500)  # Max 500 keypoints

# Detect keypoints
kp = orb.detect(img, None)

# Compute descriptors
kp, des = orb.compute(img, kp)

# Draw keypoints
img_kp = cv.drawKeypoints(img, kp, None, color=(0, 255, 0), flags=0)
```

**ORB_create Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `nFeatures` | 500 | Max features to retain |
| `scaleFactor` | 1.2 | Pyramid decimation ratio |
| `nlevels` | 8 | Number of pyramid levels |
| `edgeThreshold` | 31 | Border size for features |
| `scoreType` | HARRIS_SCORE | HARRIS_SCORE or FAST_SCORE |
| `WTA_K` | 2 | Points producing each BRIEF element |

### SIFT (Scale-Invariant Feature Transform)

More robust than ORB, but slower.

```python
sift = cv.SIFT_create()
kp, des = sift.detectAndCompute(gray, None)
img_sift = cv.drawKeypoints(gray, kp, img, flags=cv.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
```

### Feature Matching Between Frames

```python
# BFMatcher for ORB (Hamming distance)
bf = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=True)
matches = bf.match(des1, des2)
matches = sorted(matches, key=lambda x: x.distance)
result = cv.drawMatches(img1, kp1, img2, kp2, matches[:20], None, flags=2)

# FLANN matcher for SIFT (L2 distance)
FLANN_INDEX_KDTREE = 1
index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
search_params = dict(checks=50)
flann = cv.FlannBasedMatcher(index_params, search_params)
matches = flann.knnMatch(des1, des2, k=2)
```

---

## 10. Image Filtering

### Blur/Smoothing

```python
# Box blur (uniform averaging)
blur = cv.blur(frame, (5, 5))

# Gaussian blur (weighted, most common)
gaussian = cv.GaussianBlur(frame, (5, 5), 0)
# Kernel size must be positive and odd

# Median blur (good for salt-and-pepper noise)
median = cv.medianBlur(frame, 5)  # kernel size as single int

# Bilateral filter (smooths while keeping edges sharp)
bilateral = cv.bilateralFilter(frame, d=9, sigmaColor=75, sigmaSpace=75)
```

### Custom Kernel Convolution

```python
# Create custom kernel
kernel = np.ones((5, 5), np.float32) / 25  # averaging

# Sharpen kernel
sharpen = np.array([
    [0, -1, 0],
    [-1, 5, -1],
    [0, -1, 0]
])

# Emboss kernel
emboss = np.array([
    [-2, -1, 0],
    [-1, 1, 1],
    [0, 1, 2]
])

# Apply
result = cv.filter2D(frame, -1, kernel)
```

---

## 11. Thresholding

### Simple Thresholding

```python
# Returns: threshold value used, thresholded image
ret, thresh = cv.threshold(gray, 127, 255, cv.THRESH_BINARY)

# Types:
# cv.THRESH_BINARY      - above threshold = maxval, below = 0
# cv.THRESH_BINARY_INV  - above = 0, below = maxval
# cv.THRESH_TRUNC       - above = threshold, below = unchanged
# cv.THRESH_TOZERO      - above = unchanged, below = 0
# cv.THRESH_TOZERO_INV  - above = 0, below = unchanged
```

### Adaptive Thresholding

```python
# Handles varying illumination
adaptive_mean = cv.adaptiveThreshold(
    gray, 255,
    cv.ADAPTIVE_THRESH_MEAN_C,     # or GAUSSIAN_C
    cv.THRESH_BINARY,
    blockSize=11,                   # Neighborhood size (odd)
    C=2                             # Constant subtracted from mean
)
```

### Otsu's Binarization (Automatic Threshold)

```python
# Automatically finds optimal threshold
blur = cv.GaussianBlur(gray, (5, 5), 0)
ret, otsu = cv.threshold(blur, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)
print(f"Otsu's threshold: {ret}")
```

---

## 12. Real-Time Video Processing Pipeline

### Standard Pattern

```python
import cv2 as cv
import numpy as np

def process_frame(frame):
    """Apply your effect to a single frame."""
    # Example: edge detection + color overlay
    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    edges = cv.Canny(gray, 50, 150)
    edges_bgr = cv.cvtColor(edges, cv.COLOR_GRAY2BGR)
    result = cv.addWeighted(frame, 0.7, edges_bgr, 0.3, 0)
    return result

def main():
    cap = cv.VideoCapture('input.mp4')
    if not cap.isOpened():
        print("Error opening video")
        return

    fps = cap.get(cv.CAP_PROP_FPS)
    width = int(cap.get(cv.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv.VideoWriter_fourcc(*'mp4v')
    out = cv.VideoWriter('output.mp4', fourcc, fps, (width, height))

    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        processed = process_frame(frame)
        out.write(processed)
        frame_count += 1

        if frame_count % 100 == 0:
            print(f"Processed {frame_count} frames...")

    cap.release()
    out.release()
    print(f"Done! {frame_count} frames processed.")

if __name__ == '__main__':
    main()
```

### With Frame Index for Time-Based Effects

```python
def process_frame_with_index(frame, index, total_frames):
    """Effect that changes based on position in video."""
    progress = index / total_frames  # 0.0 to 1.0

    # Example: increasing blur over time
    blur_amount = int(1 + progress * 20) | 1  # must be odd
    result = cv.GaussianBlur(frame, (blur_amount, blur_amount), 0)
    return result

cap = cv.VideoCapture('input.mp4')
total = int(cap.get(cv.CAP_PROP_FRAME_COUNT))

idx = 0
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    processed = process_frame_with_index(frame, idx, total)
    # ... write frame
    idx += 1
```

---

## 13. NumPy Pixel Manipulation

### Direct Pixel Access

```python
# Frame shape: (height, width, 3) for BGR, dtype=uint8
# Access pixel at (y=100, x=200)
pixel = frame[100, 200]           # [B, G, R] array
blue = frame[100, 200, 0]         # Blue channel
green = frame[100, 200, 1]        # Green channel
red = frame[100, 200, 2]          # Red channel

# Set pixel
frame[100, 200] = [255, 0, 0]    # Set to blue
```

### Region of Interest (ROI)

```python
# Slice a region
roi = frame[100:300, 200:400]     # rows 100-300, cols 200-400

# Copy ROI to another location
frame[0:200, 0:200] = frame[100:300, 200:400]
```

### Channel Manipulation

```python
# Split channels
b, g, r = cv.split(frame)

# Merge channels (swap channels for color effects)
swapped = cv.merge([r, g, b])   # Swap red and blue
green_only = cv.merge([np.zeros_like(b), g, np.zeros_like(r)])

# Channel shifting (glitch effect)
shifted = frame.copy()
shifted[:, 10:, 2] = frame[:, :-10, 2]  # Shift red channel right by 10px
```

### Arithmetic Operations

```python
# Add constant brightness
bright = np.clip(frame.astype(np.int16) + 50, 0, 255).astype(np.uint8)

# Multiply contrast
contrast = np.clip(frame.astype(np.float32) * 1.5, 0, 255).astype(np.uint8)

# Invert
inverted = 255 - frame

# Gamma correction
gamma = 2.0
lut = np.array([((i / 255.0) ** (1.0 / gamma)) * 255
                for i in range(256)]).astype(np.uint8)
corrected = cv.LUT(frame, lut)
```

### Random Noise

```python
# Gaussian noise
noise = np.random.normal(0, 25, frame.shape).astype(np.int16)
noisy = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

# Salt and pepper noise
s_vs_p = 0.5
amount = 0.01
noisy = frame.copy()
# Salt
num_salt = int(amount * frame.size * s_vs_p)
coords = [np.random.randint(0, i - 1, num_salt) for i in frame.shape[:2]]
noisy[coords[0], coords[1]] = 255
# Pepper
num_pepper = int(amount * frame.size * (1 - s_vs_p))
coords = [np.random.randint(0, i - 1, num_pepper) for i in frame.shape[:2]]
noisy[coords[0], coords[1]] = 0
```

---

## 14. Creative Glitch Art Techniques

### Channel Displacement

```python
def channel_shift(frame, shift_r=(5, 0), shift_g=(0, 0), shift_b=(-5, 0)):
    """Shift RGB channels independently for chromatic aberration."""
    b, g, r = cv.split(frame)
    rows, cols = frame.shape[:2]

    M_r = np.float32([[1, 0, shift_r[0]], [0, 1, shift_r[1]]])
    M_g = np.float32([[1, 0, shift_g[0]], [0, 1, shift_g[1]]])
    M_b = np.float32([[1, 0, shift_b[0]], [0, 1, shift_b[1]]])

    r = cv.warpAffine(r, M_r, (cols, rows))
    g = cv.warpAffine(g, M_g, (cols, rows))
    b = cv.warpAffine(b, M_b, (cols, rows))

    return cv.merge([b, g, r])
```

### Scan Line Effect

```python
def scanlines(frame, gap=2, opacity=0.5):
    """Add horizontal scan lines."""
    result = frame.copy()
    result[::gap, :] = (result[::gap, :] * opacity).astype(np.uint8)
    return result
```

### Pixel Sorting

```python
def pixel_sort_row(frame, threshold=100):
    """Sort pixels in each row by brightness above threshold."""
    result = frame.copy()
    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

    for y in range(frame.shape[0]):
        mask = gray[y] > threshold
        indices = np.where(mask)[0]
        if len(indices) > 1:
            pixels = frame[y, indices]
            brightness = np.sum(pixels, axis=1)
            sorted_idx = np.argsort(brightness)
            result[y, indices] = pixels[sorted_idx]

    return result
```

### Wave Distortion via Remap

```python
def wave_distort(frame, amplitude=10, frequency=0.05, phase=0):
    """Apply sine wave distortion."""
    rows, cols = frame.shape[:2]
    map_y, map_x = np.mgrid[0:rows, 0:cols].astype(np.float32)

    map_x += amplitude * np.sin(2 * np.pi * map_y * frequency + phase)
    return cv.remap(frame, map_x, map_y, cv.INTER_LINEAR, borderMode=cv.BORDER_REFLECT)
```

### Block Glitch

```python
def block_glitch(frame, num_blocks=5, max_shift=30):
    """Randomly shift rectangular blocks."""
    result = frame.copy()
    h, w = frame.shape[:2]

    for _ in range(num_blocks):
        y1 = np.random.randint(0, h - 20)
        block_h = np.random.randint(10, 50)
        y2 = min(y1 + block_h, h)

        shift = np.random.randint(-max_shift, max_shift)
        block = frame[y1:y2, :].copy()

        if shift > 0:
            result[y1:y2, shift:] = block[:, :w - shift]
        elif shift < 0:
            result[y1:y2, :w + shift] = block[:, -shift:]

    return result
```

### Posterize

```python
def posterize(frame, levels=4):
    """Reduce color levels for poster effect."""
    div = 256 // levels
    return (frame // div * div + div // 2).astype(np.uint8)
```

### Datamosh Simulation (Frame Blending)

```python
def datamosh_blend(frame_current, frame_previous, alpha=0.7):
    """Simulate datamosh by blending with previous frame."""
    return cv.addWeighted(frame_current, alpha, frame_previous, 1 - alpha, 0)
```

### Motion-Based Displacement

```python
def motion_displace(frame, prev_gray, curr_gray, scale=2.0):
    """Use optical flow to displace pixels (motion-reactive glitch)."""
    flow = cv.calcOpticalFlowFarneback(prev_gray, curr_gray, None,
                                        0.5, 3, 15, 3, 5, 1.2, 0)
    h, w = frame.shape[:2]
    map_y, map_x = np.mgrid[0:h, 0:w].astype(np.float32)

    map_x += flow[..., 0] * scale
    map_y += flow[..., 1] * scale

    return cv.remap(frame, map_x, map_y, cv.INTER_LINEAR)
```

---

## Quick Reference: Common Constants

| Constant | Value | Use |
|----------|-------|-----|
| `cv.COLOR_BGR2GRAY` | 6 | Color conversion |
| `cv.COLOR_BGR2HSV` | 40 | Color conversion |
| `cv.COLOR_BGR2RGB` | 4 | For matplotlib |
| `cv.INTER_NEAREST` | 0 | Pixelated resize |
| `cv.INTER_LINEAR` | 1 | Default resize |
| `cv.INTER_CUBIC` | 2 | High quality resize |
| `cv.BORDER_REFLECT` | 2 | Border handling |
| `cv.BORDER_WRAP` | 3 | Border wrapping |
| `cv.NORM_MINMAX` | 32 | Normalize range |

---

## Performance Tips

1. **Resize before processing** - Downscale large videos for faster iteration
2. **Use numpy operations** instead of per-pixel Python loops
3. **Pre-allocate arrays** with `np.zeros_like()` or `np.empty()`
4. **Use `.astype()` wisely** - Avoid unnecessary type conversions
5. **Process grayscale** when color is not needed (3x fewer channels)
6. **Use `cv.UMat()`** for GPU acceleration (transparent API)
