# Initial Prompt for Claude Code

Copy everything below the line and paste it into your new Claude Code session:

---

I want to build an automated pipeline that connects Claude Code to Blender for 3D modeling and Bamboo Labs 3D printers for fabrication. Here's what I need:

## Project Goal
Create an AI-assisted 3D design and print workflow where I can describe objects in natural language, have them modeled in Blender, and sent to my Bamboo Labs printer.

## Key Components to Integrate

### 1. Blender MCP Server
- Repository: https://github.com/ahujasid/blender-mcp
- Enables natural language control of Blender
- Can create/modify 3D objects, apply materials, export files

### 2. Bamboo Labs Printer Control
- Use `bambulabs-api` Python package for MQTT communication
- Printers support: A1, A1 Mini, P1S, X1 Carbon
- Need to connect via LAN Mode or Developer Mode
- MQTT endpoint: `<printer-ip>:8883`

### 3. Slicing
- Use OrcaSlicer CLI or Bambu Studio
- Accept .stl or .3mf from Blender
- Output .gcode.3mf for printer

## What I Need You To Do

1. **Set up the development environment**
   - Create a Python virtual environment
   - Install required packages: `bambulabs-api`, `blender-mcp`, any MCP dependencies
   - Set up configuration files

2. **Create the integration code**
   - Python scripts to connect all components
   - Blender headless automation scripts
   - Printer communication module

3. **Build example workflows**
   - Simple object creation (cube, cylinder)
   - Export to STL/3MF
   - Send to printer and start print

4. **Set up MCP server configuration**
   - Configure Blender MCP
   - Optionally configure 3D printer MCP server

## Technical Details

**File formats:** .blend → .stl/.3mf → .gcode.3mf → printer

**Blender headless mode:**
```bash
blender --background --python script.py
```

**Bamboo MQTT connection:**
```python
from bambulabs_api import Printer
printer = Printer(ip="PRINTER_IP", access_code="ACCESS_CODE", serial="SERIAL")
```

**Printer ports needed:**
- 8883 (MQTT/TLS)
- 990 (FTPS)
- 10001-10512 (control)

## My Setup
- macOS (Darwin)
- Blender 4.x (or will install)
- Bamboo Labs printer (or evaluating purchase)
- Python 3.10+

Please start by:
1. Creating the project structure
2. Setting up a virtual environment
3. Creating a requirements.txt
4. Building the core integration modules

Let me know if you need my printer IP/access code or if I should set anything up manually first.
