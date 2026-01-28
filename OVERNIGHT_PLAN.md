# JARVIS Fab Lab - 40-Step Overnight Improvement Plan

## Research Summary: Making iPhone Scans Look Better

### The Problem
iPhone Polycam scans capture geometry well but look rough:
- Noisy mesh with bumpy surfaces
- No realistic lighting/reflections
- Flat colors, no PBR materials
- No ambient occlusion or shadows

### The Solution: GPU-Style Rendering Pipeline

**Three.js can render scans to near-photorealistic quality using:**

1. **PBR Materials** (`MeshPhysicalMaterial`) - Realistic light interaction
   - Roughness, metalness, clearcoat, sheen
   - Makes white plastic look like actual white plastic

2. **HDRI Environment Maps** - Realistic reflections & lighting
   - Single HDR image replaces all lights
   - Creates natural reflections on surfaces
   - Studio lighting feel

3. **Post-Processing Effects** (EffectComposer)
   - **Bloom** - Glow on bright surfaces
   - **SSAO** - Ambient occlusion for depth
   - **Tone Mapping** - ACES filmic for realistic HDR
   - **Vignette** - Subtle darkening at edges

4. **Mesh Enhancement** (Server-side with MeshLib/trimesh)
   - Laplacian smoothing to reduce scan noise
   - Decimation to optimize performance
   - Normal recalculation for smooth shading

### Competitive Edge
- OctoPrint/Mainsail: Show models in flat wireframe
- Bambu Studio: Basic gray preview
- **JARVIS**: PBR studio-quality rendering with HDRI

---

## The 40 Steps

### SECTION A: 3D Rendering Engine Upgrade (Steps 1-10)

#### Step 1: Upgrade Three.js to r163+
- Current: r128 (old)
- Target: r163+ for `MeshPhysicalMaterial`, better PBR
- Update all CDN links in `web/index.html`
- Migrate from legacy `THREE.XxxLoader` to ES module imports

#### Step 2: Add HDRI Environment Map
- Download a free studio HDRI from [Poly Haven](https://polyhaven.com/hdris)
- Use `RGBELoader` to load `.hdr` file
- Set `scene.environment` for global PBR reflections
- Add `scene.background` option (solid color or HDRI)

#### Step 3: Upgrade to PBR Materials for Scans
- Replace `MeshPhongMaterial` with `MeshPhysicalMaterial`
- Configure: `roughness: 0.4, metalness: 0.0, clearcoat: 0.3`
- Add material presets: Plastic, Metal, Rubber, Wood, Carbon Fiber

#### Step 4: Add Post-Processing Pipeline
- Add `EffectComposer` + `RenderPass`
- Add `UnrealBloomPass` for subtle glow on edges
- Add ACES filmic tone mapping
- Add subtle vignette effect

#### Step 5: Add Ambient Occlusion (SSAO)
- Add `SSAOPass` for realistic shadow in crevices
- Configure radius and intensity
- Makes scans look dramatically more realistic

#### Step 6: Add Ground Plane with Contact Shadow
- Semi-transparent ground plane
- Contact shadow beneath model
- Reflection on ground (slight)

#### Step 7: Add Environment Presets
- "Studio" - Clean white HDRI
- "Workshop" - Warm workshop lighting
- "Outdoor" - Natural daylight
- "JARVIS" - Cyan tech aesthetic (current default)
- Dropdown selector in UI

#### Step 8: Smooth Shading for Scans
- Auto-detect if mesh has sharp normals
- Apply `geometry.computeVertexNormals()` for smooth look
- Add toggle: Flat shading vs Smooth shading

#### Step 9: Add Model Rotation Controls
- Auto-rotate toggle (current)
- Manual rotation buttons (X/Y/Z)
- Reset view button
- Zoom-to-fit button
- Wireframe toggle

#### Step 10: Add Screenshot/Export Button
- Capture viewport as PNG
- Download rendered image
- Include JARVIS overlay option
- Share button (copy image to clipboard)

---

### SECTION B: Dashboard Visual Overhaul (Steps 11-20)

#### Step 11: Add Live Temperature Charts
- Add Chart.js CDN
- Create temperature chart area below viewport
- Nozzle temp line (orange)
- Bed temp line (cyan)
- Target temp dashed lines (green)
- 60-second rolling window

#### Step 12: Add Print Progress Ring
- Circular progress indicator
- Percentage in center
- Animated fill
- ETA countdown timer
- Layer counter (current/total)

#### Step 13: Add File Upload (Drag & Drop)
- Drag STL/OBJ/GLB onto viewport
- Upload to server `/scans/imported/`
- Auto-refresh scan library
- File size validation
- Progress bar during upload

#### Step 14: Add Model Info Panel
- Dimensions (L x W x H in mm)
- Volume calculation
- Surface area
- Bounding box visualization
- Toggle model info overlay

#### Step 15: Add Print Cost Estimator
- Material weight from volume
- Cost per gram setting
- Electricity cost estimate
- Time-based pricing option
- Total cost display

#### Step 16: Improve JARVIS Boot Animation
- Add typing effect for log messages
- Arc reactor loading spinner
- System check sequence
- Sound toggle for boot SFX
- Skip button

#### Step 17: Add Keyboard Shortcuts
- `Space` - Toggle auto-rotate
- `F` - Zoom to fit
- `W` - Toggle wireframe
- `S` - Screenshot
- `1-4` - Switch tabs
- `?` - Show shortcut help

#### Step 18: Add Dark/Light Theme Toggle
- Dark mode (current JARVIS theme)
- Light mode for daytime use
- Auto-detect system preference
- Smooth transition animation

#### Step 19: Add Notification Toasts
- Slide-in notifications from top-right
- Types: success, warning, error, info
- Auto-dismiss after 5 seconds
- Click to dismiss
- Stack multiple notifications

#### Step 20: Add Responsive Mobile Layout
- Collapse side panels to tabs
- Touch-friendly controls
- Pinch-to-zoom on viewport
- Swipe between panels
- Bottom navigation bar

---

### SECTION C: Printer-Ready Backend (Steps 21-30)

#### Step 21: Add Bambu Printer Connection Config
- Settings page/modal
- Printer IP address input
- Access code input
- Serial number input
- Connection test button
- Save to config file

#### Step 22: Install `bambulabs-api` Package
- `pip install bambulabs-api`
- Create `src/printer/bambu.py` abstraction
- Connect via MQTT
- Get real-time status
- Handle connection/disconnection

#### Step 23: Real Printer Status Integration
- Replace simulated data with real MQTT data
- Temperature readings (nozzle, bed, chamber)
- Print progress percentage
- Current filename
- Remaining time
- Speed/fan status

#### Step 24: Camera Feed from Printer
- Support JPEG frame streaming (A1/P1 series)
- Support RTSP (X1 series)
- Display in viewport (picture-in-picture)
- Snapshot button
- Full-screen toggle

#### Step 25: Send G-code Commands
- Command input in console
- Send to printer via MQTT
- Common commands as buttons:
  - Home All
  - Set Temp
  - Pause/Resume
  - Emergency Stop (already in UI)

#### Step 26: File Manager
- Browse printer SD card / internal storage
- Upload .3mf files to printer
- Delete files from printer
- File size and date info
- Start print from file list

#### Step 27: Add SQLite Database
- Store print history
- Store scan metadata
- Store user preferences
- Store alert history
- Auto-create tables on first run

#### Step 28: Print History Logging
- Log every print start/end
- Success/failure status
- Material used
- Time taken
- Cost calculated
- Thumbnail reference

#### Step 29: WebSocket Real-time Updates
- Replace polling with WebSocket
- Push temperature updates
- Push print progress
- Push alert notifications
- Reconnect on disconnect

#### Step 30: API Documentation
- Add `/api/docs` endpoint
- Auto-generate from route decorators
- Include request/response examples
- Interactive testing UI

---

### SECTION D: Scan Enhancement Pipeline (Steps 31-36)

#### Step 31: Server-side Mesh Processing
- Install `trimesh` Python package
- Add `/api/mesh/smooth` endpoint
- Laplacian smoothing with configurable iterations
- Preserve volume while reducing noise

#### Step 32: Mesh Decimation Endpoint
- Add `/api/mesh/decimate` endpoint
- Reduce triangle count by percentage
- Quality-bounded decimation (QEM)
- Return optimized mesh file

#### Step 33: Auto-Fix Mesh Issues
- Add `/api/mesh/repair` endpoint
- Fill holes in scan mesh
- Remove degenerate triangles
- Make mesh watertight for printing
- Remove internal faces

#### Step 34: Normal Recalculation
- Recalculate vertex normals server-side
- Consistent face orientation
- Smooth normal angles (configurable)
- Return enhanced mesh

#### Step 35: Mesh Analysis Report
- Add `/api/mesh/analyze` endpoint
- Watertight check
- Triangle quality histogram
- Overhang detection
- Thin wall detection
- Printability score (0-100)

#### Step 36: Batch Processing
- Process all scans on import
- Auto-smooth, auto-repair
- Generate LOD versions (high/med/low)
- Cache processed versions

---

### SECTION E: UX Polish & Features (Steps 37-40)

#### Step 37: Add Material Preset Library
- PLA profiles with realistic colors
- PETG profiles (slight transparency)
- ABS profiles
- TPU profiles (flexible appearance)
- Custom material creator

#### Step 38: Add Scan Comparison Mode
- Side-by-side viewport
- Before/after enhancement
- Overlay diff view
- Toggle between versions

#### Step 39: Multi-Language Support
- English (default)
- Spanish
- Japanese
- German
- Language selector in settings

#### Step 40: Add Onboarding Tour
- First-time user guide
- Highlight key features
- Step-by-step walkthrough
- Skip option
- Don't show again checkbox

---

## Implementation Priority (Tonight)

### Must Do (High Impact, Standalone)
| Step | Feature | Why |
|------|---------|-----|
| 1 | Upgrade Three.js | Foundation for everything |
| 2 | HDRI Environment Map | Biggest visual upgrade |
| 3 | PBR Materials | Makes scans look real |
| 4 | Post-Processing | Bloom + tone mapping |
| 5 | SSAO | Depth and realism |
| 11 | Temperature Charts | Core monitoring feature |
| 13 | File Upload | Essential for adding scans |
| 17 | Keyboard Shortcuts | Quick UX win |
| 19 | Toast Notifications | Better feedback |
| 27 | SQLite Database | Data persistence |

### Should Do (Medium Impact)
| Step | Feature | Why |
|------|---------|-----|
| 6 | Ground Shadow | Visual polish |
| 7 | Environment Presets | User choice |
| 8 | Smooth Shading | Better scan display |
| 9 | Rotation Controls | Better interaction |
| 10 | Screenshot Button | Share renders |
| 12 | Progress Ring | Print monitoring |
| 14 | Model Info | Useful data |
| 15 | Cost Estimator | Practical feature |

### Nice to Have (Lower Priority Tonight)
| Step | Feature | Why |
|------|---------|-----|
| 16 | Boot Animation | Polish |
| 18 | Light Theme | Accessibility |
| 20 | Mobile Layout | Future-proof |
| 31-36 | Mesh Processing | Requires trimesh |
| 37-40 | UX Polish | Can wait |

---

## Technical Dependencies

```
pip install trimesh numpy scipy bambulabs-api aiosqlite chart.js
```

### CDN Dependencies (Frontend)
```html
<!-- Three.js r163+ -->
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.163.0/examples/jsm/"
  }
}
</script>

<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>

<!-- HDRI -->
<!-- Download from https://polyhaven.com/a/studio_small_08 -->
```

---

## Success Criteria

After tonight's work:
1. iPhone scans render with studio-quality PBR lighting
2. HDRI reflections make models look like product renders
3. Post-processing gives cinematic feel
4. Temperature charts show live data
5. Files can be dragged onto viewport
6. Keyboard shortcuts work
7. Toast notifications provide feedback
8. Database stores history
9. Ready to plug in real Bambu printer

---

## Sources

### Scan Enhancement
- [Polycam](https://poly.cam/) - iPhone 3D scanning
- [MeshLab](https://www.meshlab.net/) - Open source mesh processing
- [MeshLib](https://meshlib.io/) - Mesh smoothing/decimation library

### Rendering
- [Three.js HDRI Examples](https://threejs.org/examples/webgl_materials_envmaps_hdr.html)
- [pmndrs postprocessing](https://github.com/pmndrs/postprocessing) - Effect composer
- [Poly Haven HDRIs](https://polyhaven.com/hdris) - Free environment maps

### Printer Integration
- [bambulabs-api](https://pypi.org/project/bambulabs-api/) - Python Bambu MQTT
- [bambu-lab-cloud-api](https://github.com/coelacant1/Bambu-Lab-Cloud-API) - Full API
- [Bambu Integration Wiki](https://wiki.bambulab.com/en/software/third-party-integration)

### Competitive Analysis
- [OctoPrint](https://octoprint.org) - 300+ plugins
- [Mainsail](https://docs.mainsail.xyz) - Modern Klipper UI
- [Obico](https://www.obico.io) - AI failure detection
- [Meshy AI](https://www.meshy.ai) - Text to 3D

---

*Created: January 2026*
