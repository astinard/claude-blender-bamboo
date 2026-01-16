# Claude Code + Blender + Bamboo Labs 3D Printer Integration

## Project Overview
Automated pipeline connecting Claude Code AI to Blender 3D modeling and Bamboo Labs printers for AI-assisted 3D design and fabrication.

---

## Quick Start Command

```bash
cd ~/projects/claude-blender-bamboo-2026-01-14 && claude --dangerously-skip-permissions
```

**Note:** The `--dangerously-skip-permissions` flag bypasses all permission prompts. Only use on trusted networks/containers.

---

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Claude Code   │────▶│  Blender MCP    │────▶│  OrcaSlicer     │────▶│  Bamboo Labs    │
│   (Orchestrator)│     │  (3D Modeling)  │     │  (Slicing)      │     │  Printer (MQTT) │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │                       │
         │                       ▼                       ▼                       ▼
         │              .blend → .stl/.3mf        .gcode/.3mf           Physical Print
         │
         └──────────────────── Natural Language Commands ────────────────────────▶
```

---

## Component Breakdown

### 1. Blender Integration

**Blender MCP Server** - Enables Claude to control Blender via natural language:
- Repository: https://github.com/ahujasid/blender-mcp
- Website: https://blender-mcp.com/

**Capabilities:**
- Create, modify, delete 3D objects
- Apply materials and textures
- Adjust camera, lighting, scene properties
- Export to STL/3MF formats
- Run arbitrary Python scripts in Blender

**Headless Mode:**
```bash
blender myscene.blend --background --python myscript.py
```

**Key Python API:**
- `bpy` - Main Blender Python module
- `bpy.context` - Current state (active object, scene, mode)
- `bpy.ops` - Operators for actions
- `bpy.data` - Access to data blocks

**3D Print Toolbox** (built-in addon):
- Mesh analysis (volume, surface area)
- Geometry checking ("Make Manifold")
- Quick export to STL

**3MF Export** (requires addon):
- https://github.com/Ghostkeeper/Blender3mfFormat
- Supports full 3MF Core Specification v1.2.3

---

### 2. Bamboo Labs Printer Integration

**Supported Printers:**
- A1, A1 Mini
- P1S
- X1 Carbon (X1C)
- X1E (coming Q3 2025)
- H2D (coming Q4 2025)

**Connectivity Options:**

| Mode | Description | Best For |
|------|-------------|----------|
| **Cloud Mode** | Internet-connected, Bambu Cloud | Remote monitoring |
| **LAN Mode** | Local network only | Privacy, speed |
| **Developer Mode** | Full MQTT/FTP access, no auth | Automation |

**Enable Developer Mode:**
1. Tap Settings on printer touchscreen
2. Scroll to page 3 → LAN Only Mode → Enable
3. Enable Developer Mode toggle
4. Accept disclaimer

**MQTT Protocol (Key for Automation):**
- Endpoint: `<printer-ip>:8883` (TLS)
- Username: `bblp`
- Password: Found on printer (or in Bambu Handy app)

**Python Libraries:**

1. **bambulabs-api** (Recommended)
   ```bash
   pip install bambulabs-api
   ```
   - Documentation: https://bambutools.github.io/bambulabs_api/

2. **bambu-connect**
   ```bash
   pip install bambu-connect
   ```
   - Features: Status monitoring, send print jobs, camera feed, G-code execution

3. **bambu-lab-cloud-api**
   ```bash
   pip install bambu-lab-cloud-api
   ```
   - Full Cloud + MQTT + FTP support

**File Formats Accepted:**
- .3mf (preferred - native support)
- .stl
- .gcode
- .stp/.step
- .amf
- .obj

---

### 3. Slicing Integration

**OrcaSlicer CLI** (Recommended):
- Repository: https://github.com/SoftFever/OrcaSlicer
- Supports: Bambu, Prusa, Voron, Creality, etc.

**Bambu/OrcaSlicer MCP Agent:**
- https://lobehub.com/mcp/sharonxu-bambu-mcp-agent
- Analyze .3mf files, compare profiles, recommend settings

**Bambu Connect URL Scheme** (for file import):
```
bambu-connect://import-file?path=/tmp/model.gcode.3mf&name=MyModel&version=1.0.0
```

---

### 4. MCP Servers to Install

**Blender MCP:**
```bash
# Install via pip
pip install blender-mcp

# Or clone repository
git clone https://github.com/ahujasid/blender-mcp.git
```

**3D Printer MCP Server** (Universal):
```bash
npm install -g mcp-3d-printer-server
```
- Repository: https://github.com/DMontgomery40/mcp-3D-printer-server
- Supports: Bambu Labs, OctoPrint, Klipper, Prusa Connect

**Bambu-Specific MCP:**
- https://github.com/Shockedrope/bambu-mcp-server

---

## Implementation Phases

### Phase 1: Environment Setup
- [ ] Install Blender 4.2 LTS (or 4.4)
- [ ] Install OrcaSlicer or Bambu Studio
- [ ] Install Python dependencies
- [ ] Configure MCP servers
- [ ] Set up Bamboo Labs printer in Developer/LAN mode

### Phase 2: Blender Automation
- [ ] Test Blender headless mode
- [ ] Install Blender MCP server
- [ ] Create test Python scripts for modeling
- [ ] Test STL/3MF export pipeline

### Phase 3: Printer Connection
- [ ] Get printer IP and access code
- [ ] Test MQTT connection with bambulabs-api
- [ ] Verify file upload via FTP
- [ ] Test print job initiation

### Phase 4: End-to-End Pipeline
- [ ] Create workflow: prompt → model → export → slice → print
- [ ] Test with simple objects (cube, cylinder)
- [ ] Add error handling and status monitoring
- [ ] Document full workflow

### Phase 5: Advanced Features
- [ ] Real-time print monitoring
- [ ] Camera feed integration
- [ ] Multi-printer farm support
- [ ] Custom slicer profiles per model type

---

## Example Workflow

```python
# Example: AI-Assisted 3D Print Pipeline

# 1. Claude receives natural language request
# "Create a phone stand with 60 degree angle and print it"

# 2. Blender MCP creates model
# - Generate mesh via Python scripting
# - Apply materials if needed
# - Run mesh analysis (watertight check)

# 3. Export to 3MF
# blender --background --python export_3mf.py

# 4. Slice with OrcaSlicer
# orcaslicer --slice model.3mf --preset "0.20mm Standard" --output model.gcode.3mf

# 5. Send to Printer via MQTT
from bambulabs_api import Printer

printer = Printer(
    ip="192.168.1.100",
    access_code="12345678",
    serial="01S00C123456789"
)

printer.connect()
printer.upload_file("model.gcode.3mf")
printer.start_print("model.gcode.3mf")
```

---

## Network Requirements

| Port | Protocol | Purpose |
|------|----------|---------|
| 8883 | MQTT/TLS | Printer control |
| 990 | FTPS | File upload |
| 10001-10512 | TCP | Control commands |
| 5888-5889 | TCP | Additional services |

---

## Security Notes

1. **Developer Mode** disables authentication - use only on trusted networks
2. **LAN Mode** is more secure than Developer Mode
3. Consider Docker containers for isolation
4. MQTT password is device-specific (don't share publicly)

---

## Resources

### Official Documentation
- [Blender Python API](https://docs.blender.org/api/current/)
- [Bambu Lab Third-Party Integration](https://wiki.bambulab.com/en/software/third-party-integration)
- [Bambu Lab LAN Mode Guide](https://wiki.bambulab.com/en/knowledge-sharing/enable-lan-mode)

### MCP Servers
- [Blender MCP](https://github.com/ahujasid/blender-mcp)
- [3D Printer MCP Server](https://github.com/DMontgomery40/mcp-3D-printer-server)
- [Bambu MCP Server](https://github.com/Shockedrope/bambu-mcp-server)

### Python Libraries
- [bambulabs-api](https://pypi.org/project/bambulabs-api/)
- [bambu-connect](https://pypi.org/project/bambu-connect/)
- [BambuLabs API Docs](https://bambutools.github.io/bambulabs_api/)

### Additional
- [OrcaSlicer](https://github.com/SoftFever/OrcaSlicer)
- [Blender 3MF Addon](https://github.com/Ghostkeeper/Blender3mfFormat)
- [Model Context Protocol](https://modelcontextprotocol.io/)
