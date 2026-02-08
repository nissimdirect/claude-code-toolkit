# Real-Time Video Processing Libraries and Tools

> Reference guide for creative coding tools for real-time video processing, visual synthesis, and inter-app video routing.
> Covers: TouchDesigner, Processing/p5.js, Hydra, cables.gl, Syphon/Spout, vvvv
> Last updated: 2026-02-07

---

## Table of Contents

1. [Overview and Comparison](#overview-and-comparison)
2. [TouchDesigner](#touchdesigner)
3. [Processing and p5.js](#processing-and-p5js)
4. [Hydra Visual Synth](#hydra-visual-synth)
5. [cables.gl](#cablesgl)
6. [Syphon and Spout](#syphon-and-spout)
7. [vvvv](#vvvv)
8. [Additional Tools](#additional-tools)
9. [Inter-App Routing Workflows](#inter-app-routing-workflows)
10. [Resources](#resources)

---

## Overview and Comparison

### Tool Comparison Matrix

| Tool | Type | Platform | Language | Real-Time | Free? | Best For |
|------|------|----------|----------|-----------|-------|----------|
| **TouchDesigner** | Node-based visual | Win/macOS | Python | Yes | Free (non-commercial) | Installations, VJ, interactive |
| **Processing** | Code-based | Cross-platform | Java | Yes | Yes (open-source) | Generative art, learning |
| **p5.js** | Code-based (web) | Browser | JavaScript | Yes | Yes (open-source) | Web art, sketches, education |
| **Hydra** | Live coding (web) | Browser | JavaScript | Yes | Yes (open-source) | Live visuals, performance |
| **cables.gl** | Node-based (web) | Browser | JavaScript | Yes | Yes (free tier) | WebGL, interactive web |
| **Syphon** | Video routing | macOS only | N/A | Yes | Yes (open-source) | Inter-app video sharing |
| **Spout** | Video routing | Windows only | N/A | Yes | Yes (open-source) | Inter-app video sharing |
| **vvvv** | Node-based visual | Win (primarily) | Visual/.NET | Yes | Free (non-commercial) | Installations, data viz, show control |

### Choosing a Tool

| If you want to... | Use |
|-------------------|-----|
| Build interactive installations | TouchDesigner or vvvv |
| Create web-based visual art | p5.js, Hydra, or cables.gl |
| Live code visuals for performance | Hydra |
| Learn creative coding from scratch | p5.js (lowest barrier) |
| Create glitch/datamosh video effects | FFmpeg + Python (scripted) |
| Route video between apps on macOS | Syphon |
| Build complex data-driven visuals | TouchDesigner or vvvv |
| Create visual programming for web | cables.gl |

---

## TouchDesigner

### Overview

**TouchDesigner** is a node-based visual programming environment for real-time interactive media. Developed by **Derivative** (Toronto, Canada).

- **URL**: [derivative.ca](https://derivative.ca/)
- **Platform**: Windows and macOS
- **Current Version**: TouchDesigner 2024.x+
- **Pricing**: Free (non-commercial), $600/year (commercial), $2,200/year (pro)

### Key Features

- **Node-based workflow**: Visual programming with operators (TOPs, CHOPs, SOPs, DATs, MATs, COMPs)
- **Real-time rendering**: GPU-accelerated video processing and 3D rendering
- **Python scripting**: Full Python integration for automation and logic
- **Multi-protocol support**: MIDI, OSC, DMX, Art-Net, serial, WebSocket, HTTP
- **Hardware integration**: Kinect, Leap Motion, webcams, projectors, LED panels
- **Audio reactive**: CHOP operators for audio analysis and visualization

### Python Integration

TouchDesigner uses a **custom Python build** with access to standard Python libraries plus TD-specific modules.

- **Documentation**: [docs.derivative.ca/Python](https://docs.derivative.ca/Python)
- **Tutorial**: [derivative.ca/UserGuide/Introduction_to_Python_Tutorial](https://derivative.ca/UserGuide/Introduction_to_Python_Tutorial)
- **Examples**: 100+ working Python examples included (Help > Python Examples)

#### Key Python Capabilities

```python
# Access operators
op('moviefilein1').par.file = '/path/to/video.mp4'

# Set parameters
op('transform1').par.tx = 0.5

# React to events
def onValueChange(channel, sampleIndex, val, prev):
    op('text1').par.text = f"Value: {val}"

# Execute scripts on timeline
def onFrameStart(frame):
    # Called every frame
    pass

# Network communication
import socket
# OSC, UDP, TCP available

# Access external Python libraries
import numpy as np
import cv2  # OpenCV for computer vision
```

#### Common Python Patterns

| Pattern | Use Case |
|---------|----------|
| **Callbacks** | React to parameter changes, MIDI input, OSC messages |
| **Timers** | Schedule events, create sequencers |
| **File I/O** | Load/save data, process CSV, read JSON |
| **Network** | Communicate with other software via OSC/UDP/WebSocket |
| **Extensions** | Create custom operator behavior |
| **NumPy integration** | Fast array operations for video/audio processing |

### Operator Types

| Type | Code | Purpose | Example |
|------|------|---------|---------|
| **Texture** | TOP | 2D image/video processing | Movie File In, Composite, Blur |
| **Channel** | CHOP | Audio/signal processing | Audio In, LFO, Math |
| **Surface** | SOP | 3D geometry | Sphere, Grid, Transform |
| **Data** | DAT | Tables/text/scripts | Table, Execute, Python |
| **Material** | MAT | Shading/materials | Phong, PBR, GLSL |
| **Component** | COMP | Containers/UI/3D scenes | Container, Camera, Light |

### Learning Resources

- [TouchDesigner Tutorial for Beginners (2025)](https://stevezafeiriou.com/touchdesigner-tutorial-for-beginners/) -- Steve Zafeiriou
- [Python in TouchDesigner](https://matthewragan.com/teaching-resources/touchdesigner/python-in-touchdesigner/) -- Matthew Ragan
- [TouchDesigner Python Cheat Sheet](https://interactiveimmersive.io/blog/python/python-cheat-sheet-for-touchdesigner-developers/) -- Interactive & Immersive HQ
- [TouchDesigner Python Tricks](https://interactiveimmersive.io/blog/python/touchdesigner-python-tricks/)
- [TouchDesigner Curriculum](https://learn.derivative.ca/) -- Official learning platform
- [TouchDesigner and Python (CCIA)](https://rvirmoors.github.io/ccia/touchdesigner-and-python) -- Academic course

### Relevance for Glitch Video

TouchDesigner can be used for:
- Real-time glitch effects (feedback loops, pixel sorting, data bending)
- Audio-reactive video manipulation
- Live performance visuals
- Installation art with sensor input
- Output via Syphon/Spout to other apps

---

## Processing and p5.js

### Processing

**Processing** is a flexible software sketchbook and language for learning to code within the context of the visual arts.

- **URL**: [processing.org](https://processing.org/)
- **Language**: Java-based (with Python mode available)
- **Platform**: Windows, macOS, Linux
- **License**: Open-source (LGPL)
- **Created**: 2001 by Casey Reas and Ben Fry (MIT Media Lab)

#### Key Features

- **Sketch-based workflow**: Write code, run immediately
- **2D and 3D graphics**: Built-in drawing primitives, OpenGL support
- **Video library**: Capture and process video in real-time
- **Sound library**: Audio input/output, analysis, synthesis
- **Extensive library ecosystem**: 200+ contributed libraries
- **Education focused**: Designed for artists and designers learning to code

#### Video Processing in Processing

```java
import processing.video.*;
Capture cam;

void setup() {
  size(640, 480);
  cam = new Capture(this, 640, 480);
  cam.start();
}

void draw() {
  if (cam.available()) {
    cam.read();
  }
  // Apply glitch effect
  cam.loadPixels();
  for (int i = 0; i < cam.pixels.length; i++) {
    if (random(1) > 0.99) {
      cam.pixels[i] = cam.pixels[int(random(cam.pixels.length))];
    }
  }
  cam.updatePixels();
  image(cam, 0, 0);
}
```

### p5.js

**p5.js** is the JavaScript port of Processing, running entirely in the browser.

- **URL**: [p5js.org](https://p5js.org/)
- **Language**: JavaScript
- **Platform**: Any modern browser
- **License**: Open-source (LGPL)
- **Editor**: [editor.p5js.org](https://editor.p5js.org/) (online, free)

#### Key Features

- **Browser-based**: No installation required
- **Canvas API**: 2D and WebGL 3D rendering
- **Webcam access**: Real-time video capture in browser
- **Sound library**: p5.sound for audio visualization
- **DOM manipulation**: Create interactive HTML elements
- **Shareable**: Embed in websites, share links to sketches

#### Video Processing in p5.js

```javascript
let cam;

function setup() {
  createCanvas(640, 480);
  cam = createCapture(VIDEO);
  cam.hide();
}

function draw() {
  cam.loadPixels();
  // Pixel sort effect
  for (let y = 0; y < cam.height; y++) {
    let row = [];
    for (let x = 0; x < cam.width; x++) {
      let i = (y * cam.width + x) * 4;
      row.push({
        r: cam.pixels[i],
        g: cam.pixels[i+1],
        b: cam.pixels[i+2],
        brightness: cam.pixels[i] + cam.pixels[i+1] + cam.pixels[i+2]
      });
    }
    row.sort((a, b) => a.brightness - b.brightness);
    // Write sorted pixels back...
  }
  cam.updatePixels();
  image(cam, 0, 0);
}
```

#### p5.js Libraries for Video Art

| Library | Purpose | URL |
|---------|---------|-----|
| **p5.sound** | Audio visualization, FFT, amplitude | Built-in |
| **ml5.js** | Machine learning (pose detection, style transfer) | [ml5js.org](https://ml5js.org/) |
| **p5.capture** | Export video/GIF from sketches | npm |
| **p5.grain** | Film grain and analog effects | npm |

---

## Hydra Visual Synth

### Overview

**Hydra** is a live-codeable video synth and coding environment that runs entirely in the browser. Created by **Olivia Jack**.

- **URL**: [hydra.ojack.xyz](https://hydra.ojack.xyz/)
- **Editor**: [hydra.ojack.xyz](https://hydra.ojack.xyz/) (open in browser to start)
- **Source**: [github.com/hydra-synth/hydra](https://github.com/hydra-synth/hydra)
- **License**: Open-source (AGPL)
- **Documentation**: [hydra.ojack.xyz/docs/](https://hydra.ojack.xyz/docs/)

### Key Features

- **Browser-based**: No installation required
- **Live coding**: Modify code while visuals run in real-time
- **Analog synth metaphor**: Patch functions together like modular synthesizer cables
- **WebGL rendering**: GPU-accelerated visual processing
- **Networked**: Collaborative live coding (multiple browsers)
- **Multiple framebuffers**: Mix, composite, and feedback between video streams
- **Audio reactive**: Use microphone input to drive visuals

### Syntax Overview

Hydra uses a **chainable function syntax** inspired by analog modular synthesis:

```javascript
// Basic oscillator
osc(10, 0.1, 0.8).out()

// Kaleidoscope effect
osc(10, 0.1).kaleid(4).out()

// Feedback loop (glitch-like)
src(o0).scale(1.01).rotate(0.01).blend(osc(10), 0.5).out()

// Audio reactive
a.setBins(4)
osc(60, 0.1, 1.5)
  .modulate(noise(3), () => a.fft[0] * 2)
  .out()

// Color manipulation
osc(20, 0.01, 1)
  .color(1, 0.5, 0.3)
  .saturate(2)
  .contrast(1.5)
  .out()

// Multiple outputs
osc(10).out(o0)       // Output 0
noise(3).out(o1)      // Output 1
src(o0).blend(src(o1)).out(o2)  // Blend
render(o2)            // Display output 2
```

### Function Categories

| Category | Functions | Purpose |
|----------|-----------|---------|
| **Source** | `osc()`, `noise()`, `voronoi()`, `shape()`, `gradient()` | Generate base patterns |
| **Color** | `color()`, `saturate()`, `contrast()`, `brightness()`, `invert()` | Modify colors |
| **Geometry** | `rotate()`, `scale()`, `kaleid()`, `pixelate()`, `repeat()` | Transform geometry |
| **Blend** | `blend()`, `add()`, `mult()`, `diff()`, `mask()` | Combine sources |
| **Modulate** | `modulate()`, `modulateScale()`, `modulateRotate()` | Use one source to modify another |

### Learning Resources

- [Getting Started Guide](https://hydra.ojack.xyz/docs/docs/learning/getting-started/)
- [Hydra Tutorial - Beginners Guide (CLIP)](https://www.clipsoundandmusic.uk/hydra-tutorial-a-beginners-guide-to-live-coding-visuals/)
- [Live Coding Visuals with Hydra (Medium)](https://medium.com/@royce.taylor789/hydra-b944ae889a61)
- [Workshop: Livecoding Visuals with Hydra (CreativeApplications)](https://www.creativeapplications.net/member-submissions/workshop-livecoding-visuals-with-hydra/)

### Why Hydra for Glitch Art

- **Feedback loops** naturally create glitch-like visual artifacts
- **Modulation** creates unpredictable, organic transformations
- **Real-time**: Perfect for live performance and experimentation
- **Zero setup**: Open browser, start coding
- **Screencast output**: Record browser window for video art

---

## cables.gl

### Overview

**cables.gl** is a browser-based visual programming tool for creating interactive real-time graphics and WebGL content.

- **URL**: [cables.gl](https://cables.gl/)
- **Developer**: undev (creative studio for interactive graphics)
- **Platform**: Browser-based
- **Pricing**: Free (basic), paid plans for teams/commercial

### Key Features

- **Node-based visual programming**: Connect operators with virtual cables
- **WebGL rendering**: Hardware-accelerated 3D and 2D graphics
- **Real-time**: Instant preview of all changes
- **Operators**: Mathematical functions, shapes, materials, post-processing effects
- **Export**: Publish interactive content to web pages
- **Audio reactive**: Analyze audio for visualization

### Operator Categories

| Category | Purpose |
|----------|---------|
| **Math** | Mathematical functions, trigonometry, interpolation |
| **Shapes** | 3D primitives, custom geometry |
| **Materials** | Shaders, textures, PBR materials |
| **Post-Processing** | Blur, bloom, color grading, glitch effects |
| **Audio** | FFT analysis, audio input, beat detection |
| **Data** | JSON, arrays, strings, user input |
| **Animation** | Timelines, easing, sequencing |

### Limitations

- **No Syphon/Spout support**: Cannot directly share textures with other apps (browser limitation)
- **Workaround**: Use screen capture software (OBS) to route cables.gl output to other apps
- **Performance**: Limited by browser WebGL capabilities vs native applications

### Use Cases

- Interactive web art and installations
- Data visualizations
- Audio-reactive web experiences
- Product configurators and 3D viewers
- Generative art for websites

---

## Syphon and Spout

### Syphon (macOS)

**Syphon** is an open-source technology for macOS that enables real-time sharing of video frames between applications via GPU texture sharing.

- **URL**: [syphon.github.io](http://syphon.github.io/)
- **Source**: [github.com/Syphon](https://github.com/Syphon)
- **Platform**: macOS only
- **License**: Open-source (BSD)

#### How It Works

```
+-------------------+     Syphon     +-------------------+
| Application A     |  (GPU shared   | Application B     |
| (e.g., Processing)|  texture)      | (e.g., VDMX)     |
|                   |                |                   |
| Syphon Server     |--------------->| Syphon Client     |
| (sends frames)    |  Zero-copy     | (receives frames) |
+-------------------+  GPU transfer  +-------------------+
```

- **Zero-copy**: Frames are shared via GPU texture, not copied through CPU
- **Low latency**: Near-instantaneous frame sharing
- **Multiple clients**: One server can feed many clients simultaneously
- **No compression**: Full-quality texture sharing

#### Compatible Applications (macOS)

| Application | Syphon Support | Type |
|-------------|---------------|------|
| **VDMX** | Server + Client | VJ software |
| **Resolume** | Server + Client | VJ software |
| **Processing** | Server (via library) | Creative coding |
| **TouchDesigner** | Server + Client | Visual programming |
| **Max/MSP** | Server + Client | Visual/audio programming |
| **MadMapper** | Client | Projection mapping |
| **OBS** | Client (via plugin) | Screen recording/streaming |
| **Isadora** | Server + Client | Interactive media |

#### Syphon Tools

- **Syphon Recorder**: Record any Syphon output to video file
- **Simple Server/Client**: Basic test utilities
- **Syphon Virtual Webcam**: Make any Syphon source appear as a webcam
  - [CDM: Syphon Virtual Webcam](https://cdm.link/2020/07/free-syphon-virtual-webcam/)

### Spout (Windows)

**Spout** is the Windows equivalent of Syphon -- real-time video sharing between applications.

- **URL**: [leadedge.github.io](https://leadedge.github.io/)
- **Platform**: Windows only
- **Technology**: DirectX texture sharing
- **License**: Open-source (BSD)

#### Compatible Applications

Same general ecosystem as Syphon but on Windows:
- Resolume, TouchDesigner, Processing, Max/MSP, OBS, etc.

### Cross-Platform Alternatives

| Solution | How It Works |
|----------|-------------|
| **NDI** (NewTek) | Network-based video sharing (cross-platform, cross-machine) |
| **Virtual Webcam** | Route video as virtual camera input (OBS Virtual Camera) |
| **Screen Capture** | Capture window/region (OBS, screencapture APIs) |

---

## vvvv

### Overview

**vvvv** is a visual live-programming environment for .NET with a special focus on real-time video synthesis, interactive media, and large-scale installations.

- **URL**: [vvvv.org](https://vvvv.org/)
- **Documentation**: [thegraybook.vvvv.org](https://thegraybook.vvvv.org/)
- **Platform**: Primarily Windows (.NET/DirectX), some macOS/Linux support via .NET
- **Pricing**: Free (non-commercial), ~$500+ (commercial license)
- **History**: Created 2002 at meso.design, independent since 2006

### Key Features

- **Visual live programming**: Modify program while it runs, background compilation
- **High performance**: Compiled .NET code, as fast as C#
- **.NET ecosystem**: Access to all .NET libraries
- **Protocol support**: OSC, MIDI, UDP, TCP, Redis, DMX, Art-Net, Firmata, ZMQ, MQTT, WebSocket, HTTP
- **Hardware support**: Color/depth cameras, serial port, various sensors
- **GPU rendering**: DirectX-based real-time graphics

### Applications

vvvv is used for:
- **Generative design** and procedural graphics
- **Interaction design** with sensors and cameras
- **Data visualization** (large-scale, real-time)
- **Computer vision** applications
- **VR** experiences
- **Show control** and stage lighting
- **Physical computing** and hardware integration
- **Machine learning** integration
- **Media servers** for live events

### vvvv vs TouchDesigner

| Feature | vvvv | TouchDesigner |
|---------|------|---------------|
| **Platform** | Windows (primarily) | Windows + macOS |
| **Language** | Visual + C# | Visual + Python |
| **Performance** | .NET compiled (very fast) | GPU-accelerated |
| **Community** | European-centric, smaller | Global, larger |
| **Learning Curve** | Steeper | Moderate |
| **Commercial Use** | ~$500/year license | $600/year license |
| **Best For** | Large installations, data viz | Interactive installations, VJ |

### Learning Resources

- [Introduction for Creative Coders](https://thegraybook.vvvv.org/reference/getting-started/cc/introduction-for-creative-coders.html) -- Official guide
- [The Gray Book](https://thegraybook.vvvv.org/) -- Complete vvvv documentation
- [The Node Institute](https://thenodeinstitute.org/about-vvvv/) -- vvvv education platform

---

## Additional Tools

### VDMX (macOS)

- **URL**: [vidvox.net](https://vidvox.net/)
- **Purpose**: VJ software for real-time video mixing and effects
- **Syphon**: Full Syphon server + client support
- **Features**: Layer-based mixing, MIDI/OSC control, GLSL shaders
- **Pricing**: $199-$349

### Resolume (Cross-Platform)

- **URL**: [resolume.com](https://resolume.com/)
- **Purpose**: Professional VJ and media server software
- **Syphon/Spout**: Full support on respective platforms
  - [Resolume Syphon/Spout Guide](https://resolume.com/support/en/syphonspout)
- **Features**: Real-time effects, LED mapping, DMX output
- **Pricing**: $299-$799

### OBS Studio (Cross-Platform)

- **URL**: [obsproject.com](https://obsproject.com/)
- **Purpose**: Open-source streaming and recording
- **Integration**: Syphon client (macOS), Spout client (Windows) via plugins
- **Use Case**: Record/stream output from any visual tool
- **Price**: Free (open-source)

### Max/MSP + Jitter (Cross-Platform)

- **URL**: [cycling74.com](https://cycling74.com/)
- **Purpose**: Visual programming for audio and video
- **Jitter**: Real-time video processing engine
- **Integration**: Syphon/Spout, MIDI, OSC, serial
- **Pricing**: $9.99/month or $399 perpetual

### Visor VJ

- **URL**: [visor.live](https://www.visor.live/)
- **Purpose**: Web-based VJ software
- **Features**: Real-time visual mixing in the browser
- **Integration**: MIDI controller support

---

## Inter-App Routing Workflows

### macOS Workflow: Audio-Reactive Glitch Video

```
Audio Source (DAW/Ableton)
    |
    | (Soundflower / BlackHole / Loopback)
    v
TouchDesigner (audio analysis → video effects)
    |
    | (Syphon)
    v
VDMX or Resolume (mixing, additional effects)
    |
    | (Syphon)
    v
OBS (recording / streaming)
```

### Browser-Based Workflow: Live Coding Performance

```
Hydra (live coded visuals)
    |
    | (browser window capture)
    v
OBS (compositing, recording, streaming)
    +
p5.js sketch (additional layer)
    |
    | (browser window capture)
    v
OBS (layer compositing)
```

### Workflow: Glitch Video Pipeline

```
Source Video
    |
    | (FFmpeg: extract frames)
    v
Python/PIL (pixel manipulation, datamosh, corruption)
    |
    | (FFmpeg: reassemble)
    v
TouchDesigner (real-time effects, feedback)
    |
    | (Syphon)
    v
VDMX (live mixing)
    |
    v
OBS (final output / recording)
```

---

## Resources

### Creative Coding Communities

- [Creative Applications Network](https://www.creativeapplications.net/) -- Showcase of creative tech projects
- [OpenProcessing](https://openprocessing.org/) -- p5.js/Processing sketch sharing
- [Shadertoy](https://www.shadertoy.com/) -- GLSL shader community
- [Are.na](https://www.are.na/) -- Creative research and collection platform

### Learning Platforms

- [The Coding Train](https://thecodingtrain.com/) -- p5.js and Processing tutorials (YouTube)
- [Creative Coding with Patt Vira](https://www.youtube.com/@pattvira) -- Creative coding tutorials
- [Interactive & Immersive HQ](https://interactiveimmersive.io/) -- TouchDesigner education
- [The Node Institute](https://thenodeinstitute.org/) -- vvvv education

### Tools Reference

- [awesome-creative-coding](https://github.com/terkelg/awesome-creative-coding) -- Curated list
- [awesome-musicdsp](https://github.com/olilarkin/awesome-musicdsp) -- Audio/music DSP resources
- [VJ Galaxy](https://vjgalaxy.com/) -- VJ tools and resources

### Books

- **"Generative Design"** -- Hartmut Bohnacker et al. (Processing/p5.js)
- **"The Nature of Code"** -- Daniel Shiffman (Processing/p5.js)
- **"Code as Creative Medium"** -- Golan Levin and Tega Brain
- **"Programming Interactivity"** -- Joshua Noble
