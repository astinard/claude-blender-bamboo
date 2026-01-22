# JARVIS Fab Lab - Product Roadmap

## Competitive Analysis

### Direct Competitors

| Product | Strengths | Weaknesses | Pricing |
|---------|-----------|------------|---------|
| **[OctoPrint](https://octoprint.org)** | 300+ plugins, massive community, works with any printer | Heavy, dated UI, requires Raspberry Pi | Free |
| **[Mainsail](https://docs.mainsail.xyz)** | Modern Vue.js UI, 3D G-code preview, beautiful temp graphs | Klipper-only, limited plugins | Free |
| **[Fluidd](https://docs.fluidd.xyz)** | Clean UI, mobile-friendly, fast | Klipper-only, less customizable | Free |
| **[Obico](https://www.obico.io)** | AI failure detection (1M+ hours trained), remote access | $4-12/mo for full features | Freemium |
| **[OctoEverywhere](https://octoeverywhere.com)** | Free AI detection, works with Bambu | Requires cloud connection | Freemium |
| **[Bambu Handy](https://apps.apple.com/us/app/bambu-handy/id1625671285)** | Native Bambu integration, timelapse, LiDAR on X1C | Bambu-only, limited AI on A1/P1 | Free |

### AI 3D Generation Competitors

| Product | Speed | Quality | Export Formats | Pricing |
|---------|-------|---------|----------------|---------|
| **[Meshy AI](https://www.meshy.ai)** | ~2 min | High (PBR textures) | STL, OBJ, FBX, GLTF | $20/mo Pro |
| **[Tripo AI](https://www.tripo3d.ai)** | ~30 sec | Good (clean topology) | STL, OBJ, FBX | $10/mo |
| **[OpenAI Shap-E](https://github.com/openai/shap-e)** | Fast | Medium | OBJ, STL | Free (self-host) |

### Our Differentiators
1. **Iron Man JARVIS aesthetic** - Unique, memorable UI
2. **Blender integration** - Professional 3D editing pipeline
3. **Voice control** - Hands-free operation
4. **All-in-one** - Generation + Monitoring + Analytics in one platform
5. **Open source** - Customizable, self-hosted

---

## Roadmap Overview

| Phase | Focus | Features | Timeline |
|-------|-------|----------|----------|
| **P0** | Foundation | Core dashboard, 3D viewer, basic monitoring | Week 1-2 |
| **P1** | Monitoring | Live temps, camera, alerts, print queue | Week 3-4 |
| **P2** | Intelligence | AI failure detection, voice control, analytics | Week 5-7 |
| **P3** | Generation | Text-to-3D, AR preview, advanced features | Week 8-10 |

---

## P0: Foundation (5 Features)

### P0.1 - Dashboard Core UI
**Status:** Complete
**Description:** Iron Man JARVIS-style dashboard with dark theme, cyan glow effects, Orbitron font, and responsive grid layout.

**Acceptance Criteria:**
- [x] Header with logo, status indicators, real-time clock
- [x] Left panel with tabs (Status, AMS, Scans, Queue)
- [x] Center viewport with 3D model display
- [x] Right panel with action buttons
- [x] Bottom console for logs and commands
- [x] Mobile-responsive layout

---

### P0.2 - 3D Model Viewer
**Status:** Complete
**Description:** Three.js-powered 3D viewport with orbit controls, auto-rotation, and model loading.

**Acceptance Criteria:**
- [x] Load STL files with default cyan material
- [x] Load OBJ files with MTL materials (colors)
- [x] Load GLB/GLTF files with embedded textures
- [x] Orbit controls (rotate, zoom, pan)
- [x] Auto-rotation with toggle
- [x] Grid helper and proper lighting
- [x] Vertex/face count display

---

### P0.3 - Scan Library
**Status:** Complete
**Description:** Browse and load 3D scans from the library panel.

**Acceptance Criteria:**
- [x] List available scans with thumbnails
- [x] Display file format, size, date
- [x] Click to load into viewport
- [x] Support OBJ, STL, GLB formats
- [x] API endpoint for scan listing

---

### P0.4 - Printer Status Panel
**Status:** Complete
**Description:** Real-time printer status display with simulated data.

**Acceptance Criteria:**
- [x] Bed temperature display
- [x] Nozzle temperature display
- [x] Chamber temperature display
- [x] Print speed percentage
- [x] Status indicator (Idle/Printing/Paused/Error)
- [x] WebSocket updates every 1 second

---

### P0.5 - Console & Command Input
**Status:** Complete
**Description:** JARVIS-style console for logs and text commands.

**Acceptance Criteria:**
- [x] Scrollable log output with timestamps
- [x] Different log levels (info, warning, error, jarvis)
- [x] Text input for commands
- [x] Execute button
- [x] Clear console function

---

## P1: Monitoring (5 Features)

### P1.1 - Live Temperature Graphs
**Status:** Pending
**Priority:** High
**Description:** Real-time temperature charts using Chart.js with historical data.

**Acceptance Criteria:**
- [ ] Line chart showing last 60 data points
- [ ] Nozzle temp (current vs target)
- [ ] Bed temp (current vs target)
- [ ] Chamber temp (if available)
- [ ] Smooth animations on update
- [ ] Hover tooltips with exact values
- [ ] Toggle individual lines on/off

**Technical:**
```javascript
// Chart.js config
const tempChart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: timestamps,
    datasets: [
      { label: 'Nozzle', borderColor: '#ff6b35' },
      { label: 'Bed', borderColor: '#00d4ff' },
      { label: 'Target', borderColor: '#00ff88', borderDash: [5,5] }
    ]
  }
});
```

---

### P1.2 - Camera Feed Integration
**Status:** Pending
**Priority:** High
**Description:** Live camera feed with snapshot and timelapse support.

**Acceptance Criteria:**
- [ ] MJPEG stream display in viewport
- [ ] Snapshot capture button
- [ ] Picture-in-picture mode
- [ ] Full-screen toggle
- [ ] Fallback placeholder when no camera
- [ ] FPS indicator

**Technical:**
- Use `bambu-connect` library for Bambu camera
- Support generic MJPEG streams
- Store snapshots in `/captures/` directory

---

### P1.3 - Print Queue Manager
**Status:** Pending
**Priority:** High
**Description:** Manage multiple print jobs with drag-and-drop reordering.

**Acceptance Criteria:**
- [ ] Add files to queue (drag & drop)
- [ ] Reorder jobs via drag
- [ ] Set priority (Low/Normal/High/Urgent)
- [ ] Estimated time per job
- [ ] Total queue time calculation
- [ ] Start/Pause/Cancel queue
- [ ] Job dependencies (print A before B)
- [ ] Persist queue to SQLite

**UI Elements:**
```
QUEUE (3 jobs - 4h 23m total)
┌─────────────────────────────────┐
│ 1. ▶ benchy.3mf     [HIGH]  45m │
│ 2.   bracket.stl    [NORM]  2h  │
│ 3.   clip.stl       [LOW]   1h  │
└─────────────────────────────────┘
[START QUEUE] [PAUSE] [CLEAR]
```

---

### P1.4 - Alert System
**Status:** Pending
**Priority:** Medium
**Description:** Push notifications and in-app alerts for print events.

**Acceptance Criteria:**
- [ ] In-app toast notifications
- [ ] Browser push notifications (with permission)
- [ ] Alert types: Info, Warning, Error, Success
- [ ] Alert sounds (toggle)
- [ ] Alert history panel
- [ ] Dismiss/snooze options
- [ ] Email notifications (optional)

**Alert Events:**
- Print started/completed/failed
- Temperature deviation (>5°C from target)
- Filament runout
- Print paused
- AI failure detected

---

### P1.5 - AMS Material Manager
**Status:** Pending
**Priority:** Medium
**Description:** Visual AMS slot management with color/material tracking.

**Acceptance Criteria:**
- [ ] 4-slot visual representation
- [ ] Color picker for each slot
- [ ] Material type selector (PLA, PETG, ABS, etc.)
- [ ] Remaining percentage estimate
- [ ] Drag material to model parts
- [ ] Humidity indicator
- [ ] Dry box reminder

**UI Mockup:**
```
AMS SLOTS
┌──────┬──────┬──────┬──────┐
│  1   │  2   │  3   │  4   │
│ ███  │ ███  │ ███  │ ░░░  │
│ PLA  │ PETG │ PLA  │EMPTY │
│ 78%  │ 45%  │ 92%  │  -   │
│ Red  │White │Black │  -   │
└──────┴──────┴──────┴──────┘
```

---

## P2: Intelligence (5 Features)

### P2.1 - AI Failure Detection
**Status:** Pending
**Priority:** Critical
**Description:** Real-time print failure detection using computer vision.

**Acceptance Criteria:**
- [ ] Detect spaghetti/stringing
- [ ] Detect layer shifting
- [ ] Detect bed adhesion failure
- [ ] Detect nozzle clogs (under-extrusion)
- [ ] Confidence score display
- [ ] Auto-pause on high-confidence failure
- [ ] Manual override option
- [ ] Training data collection (opt-in)

**Technical Options:**
1. **Bambu H2D native** - Built-in NPU (X1C/P2S only)
2. **Obico self-hosted** - Docker container, proven model
3. **Custom model** - Train on collected data

**Implementation:**
```python
# Using Obico's model
from obico import FailureDetector

detector = FailureDetector()
frame = camera.capture()
result = detector.analyze(frame)

if result.confidence > 0.85:
    printer.pause()
    alert("Spaghetti detected!")
```

---

### P2.2 - Voice Control (Full)
**Status:** Partial
**Priority:** High
**Description:** Complete voice command system with wake word.

**Acceptance Criteria:**
- [ ] Wake word: "Hey JARVIS"
- [ ] Browser speech recognition
- [ ] Command parsing with NLP
- [ ] Voice feedback (TTS)
- [ ] Visual feedback (waveform)
- [ ] Commands: generate, print, pause, status, change color
- [ ] Multi-language support

**Voice Commands:**
```
"Hey JARVIS, generate a phone stand"
"Hey JARVIS, what's the print status?"
"Hey JARVIS, make the sole blue"
"Hey JARVIS, start the print queue"
"Hey JARVIS, pause the printer"
"Hey JARVIS, show temperature graph"
```

---

### P2.3 - Print Analytics Dashboard
**Status:** Pending
**Priority:** Medium
**Description:** Historical analytics and insights.

**Acceptance Criteria:**
- [ ] Success/failure rate (pie chart)
- [ ] Material usage over time (bar chart)
- [ ] Print time trends (line chart)
- [ ] Cost tracking ($)
- [ ] Most printed models
- [ ] Printer utilization %
- [ ] Export reports (PDF/CSV)
- [ ] Date range selector

**Metrics Tracked:**
- Total prints, successful, failed
- Total print hours
- Filament used (g/m)
- Cost per print
- Average print time
- Failure reasons

---

### P2.4 - Smart Print Settings
**Status:** Pending
**Priority:** Medium
**Description:** AI-recommended print settings based on model geometry.

**Acceptance Criteria:**
- [ ] Analyze model for overhangs
- [ ] Recommend support placement
- [ ] Suggest optimal orientation
- [ ] Layer height recommendation
- [ ] Infill percentage suggestion
- [ ] Material compatibility check
- [ ] Time vs quality slider
- [ ] One-click apply settings

---

### P2.5 - Maintenance Tracker
**Status:** Pending
**Priority:** Low
**Description:** Track and predict maintenance needs.

**Acceptance Criteria:**
- [ ] Nozzle wear estimation (hours/material)
- [ ] Belt tension reminder
- [ ] Lubrication schedule
- [ ] Filter replacement tracking
- [ ] Maintenance log history
- [ ] Push reminder notifications
- [ ] Parts inventory

---

## P3: Generation (5 Features)

### P3.1 - Text-to-3D Generation
**Status:** Pending
**Priority:** Critical
**Description:** Generate 3D models from text prompts using AI.

**Acceptance Criteria:**
- [ ] Text input with prompt suggestions
- [ ] Provider selection (Meshy/Tripo)
- [ ] Style presets (Realistic, Cartoon, Low-poly)
- [ ] Generation progress indicator
- [ ] Preview before adding to library
- [ ] Regenerate with variations
- [ ] Edit prompt and retry
- [ ] Auto-save to library

**UI Flow:**
```
1. User types: "a dragon phone stand"
2. Click [GENERATE]
3. Show progress: "Generating... 45%"
4. Display 4 variations
5. User selects best one
6. [ADD TO LIBRARY] or [REGENERATE]
```

**API Integration:**
```python
# Meshy API
response = meshy.generate(
    prompt="a dragon phone stand",
    style="realistic",
    format="stl"
)
model_url = response.model_url
```

---

### P3.2 - Image-to-3D Generation
**Status:** Pending
**Priority:** High
**Description:** Generate 3D models from uploaded images.

**Acceptance Criteria:**
- [ ] Drag & drop image upload
- [ ] Multi-view image support
- [ ] Background removal
- [ ] Preview reconstruction
- [ ] Mesh cleanup options
- [ ] Texture extraction

---

### P3.3 - AR Preview
**Status:** Pending
**Priority:** High
**Description:** Preview models in augmented reality on iPhone.

**Acceptance Criteria:**
- [ ] Export to USDZ format
- [ ] Generate QR code
- [ ] One-click "View in AR"
- [ ] Scale indicator in AR
- [ ] Share AR link

**Technical:**
```python
# Export to USDZ for iOS AR
from pxr import Usd, UsdGeom
stage = Usd.Stage.CreateNew('model.usdz')
# ... add geometry
stage.Save()

# Generate QR
qr = qrcode.make(f"https://jarvis.local/ar/{model_id}.usdz")
```

---

### P3.4 - Real-time Color Editor
**Status:** Pending
**Priority:** Medium
**Description:** Edit model colors/materials in real-time.

**Acceptance Criteria:**
- [ ] Click to select model part
- [ ] Color picker popup
- [ ] Material presets (Matte, Glossy, Metallic)
- [ ] Save color configuration
- [ ] Apply to AMS slots
- [ ] Export modified model
- [ ] Undo/redo support

---

### P3.5 - Timelapse Generator
**Status:** Pending
**Priority:** Low
**Description:** Automatic timelapse recording and export.

**Acceptance Criteria:**
- [ ] Auto-start on print begin
- [ ] Configurable interval (1-60 sec)
- [ ] MP4/GIF export
- [ ] Add JARVIS overlay (progress bar, temps)
- [ ] Speed control (2x-32x)
- [ ] Auto-share option
- [ ] Storage management

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────┐
│                   JARVIS Frontend                    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Dashboard│ │3D Viewer│ │ Charts  │ │  Voice  │   │
│  │  (HTML) │ │(Three.js│ │(Chart.js│ │  (Web   │   │
│  │         │ │)        │ │)        │ │  Speech)│   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
│       └──────────┬┴──────────┬┴───────────┘        │
│                  │ WebSocket │                      │
└──────────────────┼───────────┼──────────────────────┘
                   │           │
┌──────────────────┼───────────┼──────────────────────┐
│                  │  Backend  │                       │
│  ┌───────────────▼───────────▼───────────────────┐  │
│  │              FastAPI / aiohttp                 │  │
│  └───────────────────────────────────────────────┘  │
│       │           │           │           │         │
│  ┌────▼───┐ ┌─────▼────┐ ┌────▼────┐ ┌────▼────┐   │
│  │ Bambu  │ │   AI     │ │ SQLite  │ │  Meshy  │   │
│  │Connect │ │ Detector │ │   DB    │ │   API   │   │
│  └────────┘ └──────────┘ └─────────┘ └─────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Success Metrics

| Metric | P0 Target | P3 Target |
|--------|-----------|-----------|
| Page Load Time | <2s | <2s |
| 3D Model Load | <3s | <3s |
| AI Generation | N/A | <60s |
| Failure Detection | N/A | >90% accuracy |
| Voice Recognition | N/A | >95% accuracy |
| User Satisfaction | N/A | >4.5/5 |

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Meshy API rate limits | High | Local caching, queue system |
| Camera stream latency | Medium | Frame buffering, WebRTC |
| Large model files | Medium | Decimation, LOD system |
| Browser compatibility | Low | Feature detection, fallbacks |
| Bambu API changes | Medium | Abstraction layer |

---

## Resources

### Competitive Products
- [OctoPrint](https://octoprint.org) - Open source printer control
- [Mainsail](https://docs.mainsail.xyz) - Modern Klipper interface
- [Obico](https://www.obico.io) - AI failure detection
- [Bambu Handy](https://apps.apple.com/us/app/bambu-handy/id1625671285) - Official Bambu app

### AI Generation
- [Meshy AI](https://www.meshy.ai) - Text/Image to 3D
- [Tripo AI](https://www.tripo3d.ai) - Fast 3D generation

### UI/UX References
- [Dashboard Design Principles 2025](https://medium.com/@allclonescript/20-best-dashboard-ui-ux-design-principles-you-need-in-2025-30b661f2f795)
- [3D Printing Dashboard on Dribbble](https://dribbble.com/shots/21395995-3D-printing-platform-app-design-ui-ux-dashboard)

---

*Last Updated: January 2026*
*Version: 1.0*
