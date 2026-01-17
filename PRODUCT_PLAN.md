# Claude Code Fab Lab - Product Requirements Document

**Version:** 1.1
**Date:** January 2026
**Status:** P0-P2 Implementation Complete

### Implementation Progress
| Priority | Features | Completed | Status |
|----------|----------|-----------|--------|
| **P0** | Core Foundation | 8/8 | ✅ 100% |
| **P1** | Multi-Color & Materials | 7/7 | ✅ 100% |
| **P2** | Laser Cutting | 8/8 | ✅ 100% |
| **P3** | Advanced Features | 0/10 | 📋 0% |

---

## Executive Summary

Build an AI-powered personal fabrication system that transforms natural language into physical products. Users scan objects with iPhone LiDAR, iterate on designs through conversation with Claude Code, and manufacture using Bambu Lab's H2D printer with 3D printing, multi-color AMS, and laser cutting capabilities.

**Vision:** "Jarvis for manufacturing" - speak and make things.

**Investment:** ~$4,000 USD (Bambu Lab H2D 40W Laser Full Combo)

---

## Table of Contents

1. [Hardware Specification](#1-hardware-specification)
2. [System Architecture](#2-system-architecture)
3. [Priority Breakdown (P0-P3)](#3-priority-breakdown)
4. [Detailed Module Specifications](#4-detailed-module-specifications)
5. [Technical Implementation](#5-technical-implementation)
6. [Risk Assessment](#6-risk-assessment)
7. [Timeline](#7-timeline)
8. [Success Metrics](#8-success-metrics)

---

## 1. Hardware Specification

### Recommended Printer: Bambu Lab H2D 40W Laser Full Combo

**Price:** $3,499 USD
**Availability:** Pre-order, shipping end of April 2025

| Specification | Value |
|---------------|-------|
| **Build Volume** | 325 × 320 × 325 mm³ (single nozzle) |
| | 300 × 320 × 325 mm³ (dual nozzle) |
| **Print Speed** | Up to 600 mm/s |
| **Acceleration** | 20,000 mm/s² |
| **Nozzle Temp** | Up to 350°C |
| **Heated Chamber** | 65°C (enables advanced materials) |
| **Extruders** | IDEX (Independent Dual Extruder) |
| **Auto Calibration** | X/Y offset, bed leveling, vibration compensation |

#### Multi-Color Capability (AMS)
- Supports up to **4 AMS 2 Pro** + **8 AMS HT** = 12 units
- Maximum **24 filament slots** / **25 colors per print**
- Automatic filament switching mid-print
- Material types: PLA, PETG, TPU, ABS, ASA, PA, PC, CF/GF reinforced

#### Laser Module (40W)
| Specification | Value |
|---------------|-------|
| Wavelength | 455nm (blue semiconductor) |
| Max Cut Thickness | 15mm basswood |
| Max Engrave Speed | 1000 mm/s |
| Processing Area | 310 × 250 mm |
| Processing Height | 265 mm |

**Supported Materials:**
- **Cutting:** Wood (up to 15mm), leather, dark acrylic, rubber
- **Engraving:** Metal (aluminum, stainless steel, copper), stone, wood, leather

#### Safety Features
- Enclosed chamber with safety windows
- No goggles required during operation
- Integrated air assist pump
- Vision-based alignment system

### Scanning Hardware: iPhone with LiDAR

**Compatible Devices:**
- iPhone 12 Pro / Pro Max and newer
- iPhone 13 Pro / Pro Max and newer
- iPhone 14 Pro / Pro Max and newer
- iPhone 15 Pro / Pro Max and newer
- iPad Pro (2020 and newer)

**Scanning Apps (Free):**

| App | Cost | Export Formats | Notes |
|-----|------|----------------|-------|
| **Scaniverse** | Free | OBJ, FBX, STL, USDZ | By Niantic, best free option |
| **3D Scanner App** | Free | OBJ, STL, USDZ, 3MF | Native 3MF support |
| **Polycam** | Freemium | STL, OBJ (Pro only) | Best UX, exports require Pro |
| **KIRI Engine** | Freemium | Multiple | Great photogrammetry AI |

**Recommended:** Scaniverse or 3D Scanner App (both 100% free with STL export)

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLAUDE CODE FAB LAB                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │     CAPTURE     │    │     DESIGN      │    │   MANUFACTURE   │         │
│  │                 │    │                 │    │                 │         │
│  │ src/capture/    │───▶│ src/blender/    │───▶│ src/output/     │         │
│  │                 │    │                 │    │                 │         │
│  │ • lidar_import  │    │ • addon         │    │ • print_3d      │         │
│  │ • photogrammetry│    │ • nl_commands   │    │ • laser_cut     │         │
│  │ • mesh_repair   │    │ • materials     │    │ • multi_color   │         │
│  │ • format_convert│    │ • vertex_colors │    │ • export_3mf    │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│           │                      │                      │                   │
│           ▼                      ▼                      ▼                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         KNOWLEDGE LAYER                              │  │
│  │                         src/knowledge/                               │  │
│  │                                                                      │  │
│  │  • materials.py      - Material properties, constraints, colors     │  │
│  │  • machines.py       - Printer profiles, laser settings, limits     │  │
│  │  • constraints.py    - Wall thickness, overhangs, tolerances        │  │
│  │  • presets.py        - Common configurations, defaults              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    NATURAL LANGUAGE ENGINE                           │  │
│  │                    src/nl/                                           │  │
│  │                                                                      │  │
│  │  • command_parser.py   - Parse user intent                          │  │
│  │  • context_manager.py  - Track conversation state                   │  │
│  │  • action_router.py    - Route to appropriate module                │  │
│  │  • response_builder.py - Format responses with context              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      PRINTER INTERFACE                               │  │
│  │                      src/printer/                                    │  │
│  │                                                                      │  │
│  │  • mqtt_client.py      - Real-time printer communication            │  │
│  │  • ftp_upload.py       - File transfer to printer                   │  │
│  │  • ams_manager.py      - Multi-color filament mapping               │  │
│  │  • status_monitor.py   - Print progress, temperatures               │  │
│  │  • laser_control.py    - Laser module commands                      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Voice/Text
      │
      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Claude    │────▶│   Blender   │────▶│   Printer   │
│   Code      │     │   (Visual)  │     │   (H2D)     │
└─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │
      │  NL Commands      │  3MF/SVG/DXF     │  MQTT/FTP
      │                   │                   │
      ▼                   ▼                   ▼
 "make it red"    [Blender Window]      [Physical Part]
```

---

## 3. Priority Breakdown

### P0: Core Foundation (Must Have)
**Goal:** End-to-end workflow from scan to print

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| P0.1 | iPhone LiDAR Import | Load STL/OBJ from iPhone scan apps | ✅ Done |
| P0.2 | Blender Integration | Persistent session, visual feedback | ✅ Done |
| P0.3 | Natural Language Commands | Basic transformations (scale, rotate, height) | ✅ Done |
| P0.4 | Iterative Design | Modify same object without reloading | ✅ Done |
| P0.5 | STL Export | Export for single-color printing | ✅ Done |
| P0.6 | Mock Printer | Test workflow without hardware | ✅ Done |
| P0.7 | Real Printer Connection | MQTT/FTP to Bambu Lab printer | ✅ Done |
| P0.8 | Basic Print Job | Upload and start single-color print | ✅ Done |

### P1: Multi-Color & Materials (Should Have)
**Goal:** Full color and material control

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| P1.1 | Material Library | PLA, PETG, TPU, ABS properties | ✅ Done |
| P1.2 | Color Assignment | "Paint the top red" → vertex colors | ✅ Done |
| P1.3 | Material Assignment | "Make the grip rubber" → material per region | ✅ Done |
| P1.4 | Region Selection | "Select the handle" → geometry picking | ✅ Done |
| P1.5 | 3MF Export | Multi-color/material export | ✅ Done |
| P1.6 | AMS Integration | Map colors to filament slots | ✅ Done |
| P1.7 | Print Preview | Show AMS mapping before print | 🔨 To Build |

### P2: Laser Cutting (Nice to Have)
**Goal:** 2D fabrication from 3D models

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| P2.1 | Cross-Section Tool | Slice 3D model at any Z height | ✅ Done |
| P2.2 | 2D Projection | Top/front/side view to 2D | ✅ Done |
| P2.3 | SVG Export | Vector paths for laser | ✅ Done |
| P2.4 | DXF Export | AutoCAD-compatible paths | ✅ Done |
| P2.5 | Material Presets | Wood, acrylic, leather power/speed | ✅ Done |
| P2.6 | Laser Job Control | Send to H2D laser module | ✅ Done |
| P2.7 | Engrave vs Cut | Differentiate operations | ✅ Done |
| P2.8 | Path Optimization | Minimize travel, reduce time | ✅ Done |

### P3: Advanced Features (Future)
**Goal:** Professional-grade capabilities

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| P3.1 | Photogrammetry | Photos → 3D via Meshroom | 📋 Planned |
| P3.2 | Auto Mesh Repair | Fix holes, noise, non-manifold | ✅ Done |
| P3.3 | Texture Capture | Scan with color/texture | 📋 Planned |
| P3.4 | Parametric Edits | "Make all holes 2mm bigger" | ✅ Done |
| P3.5 | Design Suggestions | "This overhang may fail" warnings | 📋 Planned |
| P3.6 | Print Queue | Batch multiple jobs | 📋 Planned |
| P3.7 | Version History | Track all design iterations | 📋 Planned |
| P3.8 | Voice Control | Hands-free operation | 📋 Planned |
| P3.9 | Remote Monitoring | Camera feed, notifications | 📋 Planned |
| P3.10 | Cost Estimation | Material usage, time, cost | ✅ Done |

---

## 4. Detailed Module Specifications

### 4.1 Capture Module (`src/capture/`)

#### 4.1.1 LiDAR Import (`lidar_import.py`)
```python
class LiDARImporter:
    """Import and process iPhone LiDAR scans."""

    supported_formats = ['.stl', '.obj', '.ply', '.usdz', '.3mf']

    def import_scan(self, filepath: str) -> Mesh:
        """Import scan file and return processed mesh."""

    def auto_orient(self, mesh: Mesh) -> Mesh:
        """Auto-orient mesh (flat side down)."""

    def center_origin(self, mesh: Mesh) -> Mesh:
        """Center mesh and place on ground plane."""

    def estimate_scale(self, mesh: Mesh) -> float:
        """Estimate real-world scale from scan metadata."""
```

#### 4.1.2 Mesh Repair (`mesh_repair.py`)
```python
class MeshRepair:
    """Automatic mesh repair for 3D scans."""

    def fill_holes(self, mesh: Mesh, max_hole_size: float = 10.0) -> Mesh:
        """Fill holes up to specified diameter."""

    def remove_noise(self, mesh: Mesh, threshold: float = 0.5) -> Mesh:
        """Remove isolated vertices and small components."""

    def make_manifold(self, mesh: Mesh) -> Mesh:
        """Ensure mesh is watertight for printing."""

    def smooth(self, mesh: Mesh, iterations: int = 2) -> Mesh:
        """Smooth mesh to reduce scan noise."""

    def decimate(self, mesh: Mesh, target_faces: int = 100000) -> Mesh:
        """Reduce polygon count while preserving shape."""
```

**Dependencies:**
- `pymeshfix` - Hole filling and manifold repair
- `pymeshlab` - Comprehensive mesh processing
- `trimesh` - Mesh manipulation

#### 4.1.3 Photogrammetry (`photogrammetry.py`) [P3]
```python
class PhotogrammetryPipeline:
    """Convert photos to 3D model using Meshroom."""

    def __init__(self, meshroom_path: str = None):
        """Initialize with Meshroom installation path."""

    def process_images(self, image_folder: str, output_path: str) -> Mesh:
        """Run full photogrammetry pipeline on images."""

    def get_progress(self) -> dict:
        """Return current processing progress."""
```

**Dependencies:**
- Meshroom (AliceVision) - Open source photogrammetry
- NVIDIA GPU with CUDA 3.0+ (for full speed)

---

### 4.2 Blender Module (`src/blender/`)

#### 4.2.1 Interactive Addon (`interactive_addon.py`) [Enhanced]

**New Commands to Add:**

```python
# Material/Color Commands
'set_color': {
    'params': {'region': str, 'color': str},
    'example': "paint the top red"
}

'set_material': {
    'params': {'region': str, 'material': str},
    'example': "make the handle rubber"
}

'select_region': {
    'params': {'description': str},
    'example': "select the top half"
}

# Laser Commands
'cross_section': {
    'params': {'z_height': float, 'export_svg': bool},
    'example': "cut a cross section at 10mm"
}

'project_2d': {
    'params': {'direction': str, 'export_format': str},
    'example': "project from top to SVG"
}

# Advanced Commands
'boolean_union': {
    'params': {},
    'example': "merge all objects"
}

'boolean_difference': {
    'params': {'tool_object': str},
    'example': "cut out the cylinder"
}

'mirror': {
    'params': {'axis': str},
    'example': "mirror on X axis"
}

'array': {
    'params': {'count': int, 'offset': tuple},
    'example': "make 4 copies spaced 50mm apart"
}
```

#### 4.2.2 Vertex Colors (`vertex_colors.py`)
```python
class VertexColorManager:
    """Manage per-face colors for multi-color printing."""

    def paint_region(self, obj, region_selector: str, color: tuple) -> None:
        """Paint faces matching selector with color.

        region_selector examples:
        - "top" → faces with normal.z > 0.7
        - "bottom" → faces with normal.z < -0.7
        - "front" → faces with normal.y > 0.7
        - "z > 50mm" → faces above z=50
        - "selected" → currently selected faces
        """

    def get_color_regions(self, obj) -> dict:
        """Return dict of colors and their face counts."""

    def export_color_map(self, obj) -> dict:
        """Export color mapping for 3MF."""
```

#### 4.2.3 Material Assignment (`material_assign.py`)
```python
class MaterialAssigner:
    """Assign materials to mesh regions."""

    def assign_material(self, obj, region_selector: str, material_name: str) -> None:
        """Assign material from library to region."""

    def create_material_slots(self, obj, materials: list) -> None:
        """Create material slots for multi-material export."""

    def get_material_map(self, obj) -> dict:
        """Return mapping of materials to faces."""
```

---

### 4.3 Materials Module (`src/materials/`)

#### 4.3.1 Material Library (`library.py`)
```python
from dataclasses import dataclass
from enum import Enum

class MaterialType(Enum):
    FILAMENT = "filament"
    SHEET = "sheet"

class MaterialProperty(Enum):
    RIGID = "rigid"
    FLEXIBLE = "flexible"
    HEAT_RESISTANT = "heat_resistant"
    FOOD_SAFE = "food_safe"
    UV_RESISTANT = "uv_resistant"

@dataclass
class FilamentMaterial:
    name: str
    type: MaterialType = MaterialType.FILAMENT
    nozzle_temp: int = 210
    bed_temp: int = 60
    chamber_temp: int = 0
    properties: list[MaterialProperty] = None
    colors: list[str] = None
    density: float = 1.24  # g/cm³
    cost_per_kg: float = 25.0

    # Printing constraints
    min_layer_height: float = 0.08
    max_layer_height: float = 0.28
    min_wall_thickness: float = 0.8
    max_overhang_angle: float = 45
    supports_required_angle: float = 60

@dataclass
class SheetMaterial:
    name: str
    type: MaterialType = MaterialType.SHEET
    thickness: float = 3.0  # mm

    # Laser settings
    cut_power: int = 70  # percentage
    cut_speed: int = 10  # mm/s
    engrave_power: int = 30
    engrave_speed: int = 100
    passes: int = 1

    # Properties
    can_cut: bool = True
    can_engrave: bool = True

MATERIAL_LIBRARY = {
    # Filaments
    'pla': FilamentMaterial(
        name='PLA',
        nozzle_temp=210,
        bed_temp=60,
        properties=[MaterialProperty.RIGID],
        colors=['white', 'black', 'red', 'blue', 'green', 'yellow', 'orange', 'purple'],
        cost_per_kg=25.0,
    ),
    'petg': FilamentMaterial(
        name='PETG',
        nozzle_temp=240,
        bed_temp=70,
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT],
        colors=['clear', 'white', 'black', 'blue'],
        cost_per_kg=30.0,
        max_overhang_angle=40,
    ),
    'tpu': FilamentMaterial(
        name='TPU',
        nozzle_temp=220,
        bed_temp=50,
        properties=[MaterialProperty.FLEXIBLE],
        colors=['white', 'black', 'clear'],
        cost_per_kg=40.0,
        min_wall_thickness=1.2,
    ),
    'abs': FilamentMaterial(
        name='ABS',
        nozzle_temp=250,
        bed_temp=100,
        chamber_temp=45,
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT],
        colors=['white', 'black', 'red', 'blue'],
        cost_per_kg=28.0,
    ),
    'pa': FilamentMaterial(
        name='Nylon/PA',
        nozzle_temp=280,
        bed_temp=85,
        chamber_temp=55,
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT],
        colors=['natural', 'black'],
        cost_per_kg=50.0,
    ),
    'pc': FilamentMaterial(
        name='Polycarbonate',
        nozzle_temp=300,
        bed_temp=110,
        chamber_temp=60,
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT],
        colors=['clear', 'black'],
        cost_per_kg=55.0,
    ),

    # Sheet materials for laser
    'wood_3mm': SheetMaterial(
        name='Plywood 3mm',
        thickness=3.0,
        cut_power=70,
        cut_speed=10,
        engrave_power=25,
        engrave_speed=150,
    ),
    'wood_5mm': SheetMaterial(
        name='Plywood 5mm',
        thickness=5.0,
        cut_power=85,
        cut_speed=6,
        engrave_power=25,
        engrave_speed=150,
    ),
    'wood_10mm': SheetMaterial(
        name='Plywood 10mm',
        thickness=10.0,
        cut_power=100,
        cut_speed=3,
        passes=2,
        engrave_power=30,
        engrave_speed=120,
    ),
    'acrylic_dark_3mm': SheetMaterial(
        name='Dark Acrylic 3mm',
        thickness=3.0,
        cut_power=80,
        cut_speed=8,
        engrave_power=20,
        engrave_speed=200,
    ),
    'leather_2mm': SheetMaterial(
        name='Leather 2mm',
        thickness=2.0,
        cut_power=50,
        cut_speed=15,
        engrave_power=15,
        engrave_speed=250,
    ),
}
```

#### 4.3.2 Natural Language Material Mapping (`nl_materials.py`)
```python
# Natural language to material mapping
MATERIAL_ALIASES = {
    # Filaments
    'plastic': 'pla',
    'rubber': 'tpu',
    'flexible': 'tpu',
    'bendy': 'tpu',
    'soft': 'tpu',
    'hard': 'pla',
    'strong': 'petg',
    'heat resistant': 'petg',
    'nylon': 'pa',
    'tough': 'pa',

    # Sheet materials
    'wood': 'wood_3mm',
    'plywood': 'wood_3mm',
    'thin wood': 'wood_3mm',
    'thick wood': 'wood_10mm',
    'acrylic': 'acrylic_dark_3mm',
    'leather': 'leather_2mm',
}

COLOR_ALIASES = {
    'red': (1.0, 0.0, 0.0, 1.0),
    'green': (0.0, 1.0, 0.0, 1.0),
    'blue': (0.0, 0.0, 1.0, 1.0),
    'yellow': (1.0, 1.0, 0.0, 1.0),
    'orange': (1.0, 0.5, 0.0, 1.0),
    'purple': (0.5, 0.0, 1.0, 1.0),
    'pink': (1.0, 0.5, 0.8, 1.0),
    'white': (1.0, 1.0, 1.0, 1.0),
    'black': (0.0, 0.0, 0.0, 1.0),
    'gray': (0.5, 0.5, 0.5, 1.0),
    'grey': (0.5, 0.5, 0.5, 1.0),
    'brown': (0.6, 0.3, 0.0, 1.0),
    'gold': (1.0, 0.84, 0.0, 1.0),
    'silver': (0.75, 0.75, 0.75, 1.0),
}
```

---

### 4.4 Export Module (`src/export/`)

#### 4.4.1 3MF Exporter (`threemf.py`)
```python
class ThreeMFExporter:
    """Export to 3MF format for multi-color/material printing."""

    def export(self,
               objects: list,
               output_path: str,
               materials: dict = None,
               colors: dict = None,
               print_settings: dict = None) -> str:
        """
        Export objects to 3MF with full material/color support.

        Args:
            objects: List of Blender objects
            output_path: Output file path
            materials: {face_index: material_name} mapping
            colors: {face_index: (r, g, b, a)} mapping
            print_settings: Slicer settings to embed

        Returns:
            Path to exported file
        """

    def _build_model_xml(self, objects, materials, colors) -> str:
        """Build 3MF model XML structure."""

    def _build_material_xml(self, materials) -> str:
        """Build material definitions."""

    def _embed_thumbnail(self, objects) -> bytes:
        """Generate and embed thumbnail image."""
```

#### 4.4.2 SVG/DXF Exporter (`vector_export.py`)
```python
class VectorExporter:
    """Export 2D paths for laser cutting."""

    def cross_section(self, obj, z_height: float) -> list:
        """Get 2D contours at specified Z height."""

    def project_outline(self, obj, direction: str = 'top') -> list:
        """Project object silhouette to 2D."""

    def export_svg(self, contours: list, output_path: str,
                   stroke_color: str = 'black',
                   stroke_width: float = 0.1) -> str:
        """Export contours to SVG."""

    def export_dxf(self, contours: list, output_path: str) -> str:
        """Export contours to DXF."""

    def optimize_paths(self, contours: list) -> list:
        """Optimize path order to minimize laser travel."""
```

---

### 4.5 Printer Module (`src/printer/`)

#### 4.5.1 Bambu Connection (`bamboo_connection.py`)
```python
import paho.mqtt.client as mqtt
from ftplib import FTP_TLS

class BambuPrinter:
    """Real Bambu Lab printer connection."""

    def __init__(self, ip: str, access_code: str, serial: str):
        self.ip = ip
        self.access_code = access_code
        self.serial = serial
        self.mqtt_client = None
        self.status = PrinterStatus()

    def connect(self) -> bool:
        """Connect via MQTT (port 8883, TLS)."""
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.tls_set()
        self.mqtt_client.username_pw_set(
            f"bblp",
            self.access_code
        )
        self.mqtt_client.connect(self.ip, 8883)
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.subscribe(f"device/{self.serial}/report")
        self.mqtt_client.loop_start()
        return True

    def upload_file(self, local_path: str, remote_name: str = None) -> bool:
        """Upload file via FTP/FTPS."""
        ftp = FTP_TLS()
        ftp.connect(self.ip, 990)
        ftp.login("bblp", self.access_code)
        ftp.prot_p()

        remote_name = remote_name or Path(local_path).name
        with open(local_path, 'rb') as f:
            ftp.storbinary(f'STOR /cache/{remote_name}', f)
        ftp.quit()
        return True

    def start_print(self, filename: str,
                    plate_number: int = 1,
                    ams_mapping: dict = None) -> bool:
        """Start print job with optional AMS mapping."""
        cmd = {
            "print": {
                "command": "project_file",
                "param": f"/cache/{filename}",
                "subtask_name": filename,
                "plate_number": plate_number,
            }
        }
        if ams_mapping:
            cmd["print"]["ams_mapping"] = ams_mapping

        self._send_command(cmd)
        return True

    def get_status(self) -> PrinterStatus:
        """Get current printer status."""
        return self.status

    def pause(self) -> bool:
        """Pause current print."""
        self._send_command({"print": {"command": "pause"}})
        return True

    def resume(self) -> bool:
        """Resume paused print."""
        self._send_command({"print": {"command": "resume"}})
        return True

    def stop(self) -> bool:
        """Stop current print."""
        self._send_command({"print": {"command": "stop"}})
        return True
```

#### 4.5.2 AMS Manager (`ams_manager.py`)
```python
@dataclass
class AMSSlot:
    slot_id: int
    material: str
    color: str
    remaining_percent: float

class AMSManager:
    """Manage Automatic Material System."""

    def __init__(self, printer: BambuPrinter):
        self.printer = printer
        self.slots: list[AMSSlot] = []

    def get_slots(self) -> list[AMSSlot]:
        """Get current AMS slot configuration."""

    def suggest_mapping(self, required_colors: list[str]) -> dict:
        """
        Suggest optimal AMS mapping for required colors.

        Returns: {color_name: slot_id} mapping
        """

    def validate_mapping(self, mapping: dict) -> tuple[bool, str]:
        """Validate that mapping is achievable with current AMS."""
```

#### 4.5.3 Laser Control (`laser_control.py`)
```python
class LaserController:
    """Control H2D laser module."""

    def __init__(self, printer: BambuPrinter):
        self.printer = printer

    def set_mode(self, mode: str) -> bool:
        """Set laser mode: 'cut', 'engrave', or 'off'."""

    def set_power(self, power: int) -> bool:
        """Set laser power (0-100%)."""

    def set_speed(self, speed: int) -> bool:
        """Set movement speed (mm/s)."""

    def start_job(self, svg_path: str, material: str) -> bool:
        """Start laser job with material-appropriate settings."""
        settings = MATERIAL_LIBRARY[material]
        # Apply settings and start

    def preview_job(self, svg_path: str) -> dict:
        """Preview job without firing laser."""
```

---

### 4.6 Natural Language Module (`src/nl/`)

#### 4.6.1 Command Parser (`command_parser.py`)
```python
class CommandParser:
    """Parse natural language into structured commands."""

    # Pattern definitions
    PATTERNS = {
        # Geometry
        r'(?:make|set)\s+(?:it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|inch|inches|in)?\s*(taller|shorter|wider|narrower|deeper)':
            lambda m: {'action': 'resize', 'value': float(m.group(1)), 'unit': m.group(2), 'direction': m.group(3)},

        r'(?:rotate|turn|tilt)\s+(?:it\s+)?(\d+(?:\.\d+)?)\s*(?:degrees?)?\s*(?:on\s+)?(?:the\s+)?([xyz])?\s*(?:axis)?':
            lambda m: {'action': 'rotate', 'angle': float(m.group(1)), 'axis': m.group(2) or 'z'},

        r'(?:scale|resize)\s+(?:it\s+)?(?:by\s+)?(\d+(?:\.\d+)?)\s*(?:x|times)?':
            lambda m: {'action': 'scale', 'factor': float(m.group(1))},

        # Colors
        r'(?:paint|color|make)\s+(?:the\s+)?(top|bottom|front|back|left|right|all|everything)\s+(red|blue|green|yellow|orange|purple|white|black|gray|pink)':
            lambda m: {'action': 'set_color', 'region': m.group(1), 'color': m.group(2)},

        # Materials
        r'(?:make|set)\s+(?:the\s+)?(top|bottom|handle|grip|body|base)\s+(?:to\s+)?(?:be\s+)?(rubber|flexible|plastic|hard|soft|strong)':
            lambda m: {'action': 'set_material', 'region': m.group(1), 'material': m.group(2)},

        # Laser
        r'(?:cut|laser\s+cut)\s+(?:this\s+)?(?:from\s+)?(wood|plywood|acrylic|leather)':
            lambda m: {'action': 'laser_prepare', 'material': m.group(1), 'operation': 'cut'},

        r'(?:engrave|etch)\s+(?:on|into)\s+(wood|metal|leather|acrylic)':
            lambda m: {'action': 'laser_prepare', 'material': m.group(1), 'operation': 'engrave'},

        # Printing
        r'(?:print|make)\s+(?:it|this)\s+(?:in\s+)?(blue|red|green|yellow|white|black|multi-?color)':
            lambda m: {'action': 'print', 'color': m.group(1)},

        r'(?:use|put)\s+(blue|red|green|yellow|white|black)\s+(?:in\s+)?(?:slot\s+)?(\d)':
            lambda m: {'action': 'ams_map', 'color': m.group(1), 'slot': int(m.group(2))},
    }

    def parse(self, text: str) -> dict:
        """Parse natural language command into structured action."""
        text = text.lower().strip()

        for pattern, handler in self.PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                return handler(match)

        return {'action': 'unknown', 'raw_text': text}
```

---

## 5. Technical Implementation

### 5.1 Dependencies

```toml
# pyproject.toml
[project]
name = "claude-fab-lab"
version = "1.0.0"
requires-python = ">=3.10"

dependencies = [
    # Core
    "numpy>=1.24.0",
    "trimesh>=4.0.0",

    # Mesh Processing
    "pymeshfix>=0.16.0",
    "pymeshlab>=2023.12",

    # Printer Communication
    "bambulabs-api>=2.6.0",
    "paho-mqtt>=2.0.0",

    # Export
    "svgwrite>=1.4.3",
    "ezdxf>=1.1.0",

    # Utilities
    "Pillow>=10.0.0",
    "watchdog>=4.0.0",
]

[project.optional-dependencies]
photogrammetry = [
    "meshroom",  # Requires separate installation
]
```

### 5.2 File Structure

```
claude-blender-bamboo/
├── src/
│   ├── __init__.py
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── lidar_import.py
│   │   ├── mesh_repair.py
│   │   └── photogrammetry.py
│   ├── blender/
│   │   ├── __init__.py
│   │   ├── interactive_addon.py  # Enhanced
│   │   ├── command_interpreter.py  # Enhanced
│   │   ├── design.py
│   │   ├── vertex_colors.py  # NEW
│   │   └── material_assign.py  # NEW
│   ├── materials/
│   │   ├── __init__.py
│   │   ├── library.py  # NEW
│   │   └── nl_materials.py  # NEW
│   ├── export/
│   │   ├── __init__.py
│   │   ├── threemf.py  # NEW
│   │   └── vector_export.py  # NEW
│   ├── printer/
│   │   ├── __init__.py
│   │   ├── bamboo_connection.py  # NEW (real printer)
│   │   ├── mock.py
│   │   ├── ams_manager.py  # NEW
│   │   └── laser_control.py  # NEW
│   ├── nl/
│   │   ├── __init__.py
│   │   ├── command_parser.py  # Enhanced
│   │   └── context_manager.py  # NEW
│   └── knowledge/
│       ├── __init__.py
│       ├── constraints.py  # NEW
│       └── presets.py  # NEW
├── tests/
│   ├── test_capture.py
│   ├── test_blender.py
│   ├── test_materials.py
│   ├── test_export.py
│   ├── test_printer.py
│   └── test_nl.py
├── test_scans/
│   ├── phone_mockup.stl
│   └── tablet_mockup.stl
├── output/
├── PRODUCT_PLAN.md
├── README.md
└── pyproject.toml
```

---

## 6. Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Bambu API changes | Medium | High | Use abstraction layer, monitor updates |
| 3MF color export issues | Medium | Medium | Extensive testing, fallback to multi-file |
| Laser safety | Low | Critical | Rely on H2D built-in safety, no bypass |
| Large scan files (>100MB) | Medium | Medium | Implement decimation, progress feedback |
| Blender API changes | Low | Medium | Pin Blender version, test on updates |

### Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Print failures | Medium | Low | Preview validation, material warnings |
| Material waste | Medium | Low | Cost estimation before print |
| Learning curve | High | Medium | Progressive disclosure, help system |

### Dependencies

| Dependency | Risk Level | Alternative |
|------------|------------|-------------|
| Bambu Lab ecosystem | Medium | Generic G-code export |
| Blender | Low | None (core to vision) |
| iPhone LiDAR | Low | Photogrammetry fallback |
| Python bambulabs-api | Medium | Direct MQTT implementation |

---

## 7. Timeline

### Phase 1: P0 Completion (Week 1-2)
- [ ] Day 1-2: Real printer connection (MQTT)
- [ ] Day 3-4: File upload (FTP)
- [ ] Day 5-6: Basic print job control
- [ ] Day 7-8: End-to-end test with real hardware
- [ ] Day 9-10: Bug fixes, documentation

### Phase 2: P1 Multi-Color (Week 3-5)
- [ ] Week 3: Material library, color system
- [ ] Week 4: Vertex color painting, region selection
- [ ] Week 5: 3MF export, AMS integration

### Phase 3: P2 Laser (Week 6-8)
- [ ] Week 6: Cross-section tool, 2D projection
- [ ] Week 7: SVG/DXF export, material presets
- [ ] Week 8: Laser job control, testing

### Phase 4: P3 Advanced (Ongoing)
- [ ] Photogrammetry pipeline
- [ ] Auto mesh repair
- [ ] Design suggestions
- [ ] Voice control integration

---

## 8. Success Metrics

### User Experience Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Scan to print time | < 15 min | Time from scan import to print start |
| Command success rate | > 90% | NL commands correctly interpreted |
| Iteration speed | < 30 sec | Time between design changes |
| Learning time | < 1 hour | Time to complete first successful print |

### Technical Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Blender session stability | > 4 hours | Time without crash/disconnect |
| Print success rate | > 95% | Prints completed without failure |
| File export accuracy | 100% | 3MF files load correctly in Bambu Studio |
| API response time | < 500ms | Command to visual feedback |

### Business Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Material waste | < 10% | Failed prints + supports vs successful |
| Time savings vs manual CAD | > 80% | Compared to traditional workflow |
| Features used | > 50% | Users engaging with multi-color/laser |

---

## Appendix A: Research Sources

### Hardware
- [Bambu Lab H2D Official Page](https://us.store.bambulab.com/products/h2d)
- [H2D Technical Specifications](https://bambulab.com/en/h2d/tech-specs)
- [Bambu Lab Laser Materials Guide](https://wiki.bambulab.com/en/laser/material/types-and-examples-intro)

### API & Integration
- [Bambu Lab Third-Party Integration Wiki](https://wiki.bambulab.com/en/software/third-party-integration)
- [bambulabs-api PyPI Package](https://pypi.org/project/bambulabs-api/)
- [Bambu Lab Cloud API GitHub](https://github.com/coelacant1/Bambu-Lab-Cloud-API)
- [Bambu Studio Command Line Usage](https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage)

### File Formats
- [3MF Compatibility in Bambu Studio](https://wiki.bambulab.com/en/software/bambu-studio/3mf-compatibility)
- [Multi-Color Printing Guide](https://wiki.bambulab.com/en/software/bambu-studio/multi-color-printing)

### Mesh Processing
- [PyMeshFix GitHub](https://github.com/pyvista/pymeshfix)
- [MeshLib SDK](https://meshlib.io/)
- [PyMeshLab](https://www.meshlab.net/)

### Scanning
- [Scaniverse App](https://apps.apple.com/us/app/scaniverse-3d-scanner/id1541433223)
- [3D Scanner App Comparison](https://beforesandafters.com/2024/07/02/comparing-the-top-5-3d-scanner-apps/)
- [Meshroom Photogrammetry](https://github.com/alicevision/Meshroom)

### Blender
- [Blender Python API - BMesh](https://docs.blender.org/api/current/bmesh.html)
- [Blender Vertex Colors Tutorial](https://surf-visualization.github.io/blender-course/advanced/python_scripting/3_geometry_colors_and_materials/)
- [Flatterer SVG Export Addon](https://stuvel.eu/software/flatterer/)

---

## Appendix B: Example Conversations

### Basic Workflow
```
User: Load my scan from Downloads
Claude: [Loads STL, shows in Blender]
        Loaded: phone_case_scan.stl (125 x 65 x 12 mm)

User: Make it 2 inches taller
Claude: [Modifies height]
        Height changed to 62.8mm (2.47 inches)

User: Rotate it 15 degrees
Claude: [Rotates]
        Rotated 15° around Z axis

User: Print it
Claude: [Exports STL, uploads to printer]
        Print started on Bambu H2D
        Estimated time: 45 minutes
        Material: PLA (slot 1)
```

### Multi-Color Workflow
```
User: Paint the top red and the bottom blue
Claude: [Applies vertex colors]
        Applied red to top faces (234 faces)
        Applied blue to bottom faces (198 faces)

User: What colors do I have loaded?
Claude: AMS Status:
        Slot 1: White PLA (85%)
        Slot 2: Black PLA (62%)
        Slot 3: Red PLA (90%)
        Slot 4: Blue PETG (45%)

        Your design needs: red, blue
        Suggested mapping: red→slot 3, blue→slot 4

User: Print it multi-color
Claude: [Exports 3MF with colors, uploads]
        Multi-color print started
        Using slots 3 (red) and 4 (blue)
        Estimated time: 1h 15m
```

### Laser Workflow
```
User: I want to cut this shape from 3mm plywood
Claude: [Generates 2D projection]
        Created top-view projection
        Outline size: 125 x 65 mm

        Material: 3mm Plywood
        Laser power: 70%
        Speed: 10 mm/s
        Estimated cut time: 3 minutes

User: Cut it
Claude: [Exports SVG, sends to laser]
        Laser job started
        Please ensure plywood is positioned on bed
        Safety enclosure active
```

---

*Document Version: 1.0*
*Last Updated: January 2026*
*Status: Ready for Execution*
