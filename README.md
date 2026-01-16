# Blender + Bamboo Labs 3D Printer Integration

Automated pipeline connecting Blender 3D modeling to Bamboo Labs 3D printers for AI-assisted design and fabrication.

## Features

- **Blender Automation**: Create 3D models programmatically with Python
- **iOS LiDAR Scanning**: Process scans from Polycam, 3D Scanner App, and more
- **Case/Mount Generation**: Auto-generate protective cases, stands, and mounts from scans
- **Printer Communication**: MQTT-based control of Bamboo Labs printers
- **Full Pipeline**: Model creation → Validation → Upload → Print → Monitor
- **CLI Interface**: Command-line tool for all operations
- **Mock Printer**: Test without hardware

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd claude-blender-bamboo-2026-01-14

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Requirements

- Python 3.10+
- Blender 4.x (for model creation)
- Bamboo Labs printer (or use mock for testing)

### Basic Usage

```bash
# Create a cube model (requires Blender)
python -m src.pipeline.cli create cube --size 25 --output my_cube

# Check printer status (mock)
python -m src.pipeline.cli status --mock

# Upload and print (mock)
python -m src.pipeline.cli print output/cube.stl --mock --start --monitor

# Full workflow (mock)
python -m src.pipeline.cli workflow sphere --radius 15 --mock --auto-print
```

### With Real Printer

```bash
# Set environment variables (or use command-line args)
export BAMBOO_PRINTER_IP="192.168.1.100"
export BAMBOO_ACCESS_CODE="your_access_code"
export BAMBOO_SERIAL="your_serial_number"

# Check printer status
python -m src.pipeline.cli status

# Print a file
python -m src.pipeline.cli print model.stl --start --monitor
```

## Project Structure

```
claude-blender-bamboo-2026-01-14/
├── src/
│   ├── blender/              # Blender automation
│   │   ├── primitives.py     # Shape generators
│   │   ├── exporter.py       # STL/OBJ export
│   │   ├── mesh_utils.py     # Mesh validation
│   │   ├── runner.py         # Headless CLI
│   │   ├── scan_processor.py # LiDAR scan import/repair
│   │   ├── case_generator.py # Case/mount/stand generation
│   │   └── scan_runner.py    # Headless scan processing
│   ├── printer/              # Bamboo Labs communication
│   │   ├── connection.py     # MQTT connection
│   │   ├── commands.py       # Print commands
│   │   ├── file_transfer.py  # FTP upload
│   │   └── mock.py           # Mock printer
│   └── pipeline/             # Orchestration
│       ├── workflow.py       # Full pipeline
│       └── cli.py            # CLI interface
├── tests/                    # Test suite
├── config/                   # Configuration
│   └── settings.py           # Settings and defaults
├── output/                   # Generated models
└── requirements.txt
```

## CLI Commands

### `create` - Create a 3D model

```bash
python -m src.pipeline.cli create <shape> [options]

Shapes: cube, cylinder, sphere, cone, torus

Options:
  --size FLOAT       Size in mm (for cube)
  --radius FLOAT     Radius in mm
  --height FLOAT     Height in mm
  --format FORMAT    Export format (stl, obj, ply)
  --output NAME      Output filename
```

### `print` - Print a file

```bash
python -m src.pipeline.cli print <file> [options]

Options:
  --start            Immediately start print
  --monitor          Monitor print progress
  --mock             Use mock printer
  --printer-ip IP    Printer IP address
  --access-code CODE Printer access code
```

### `status` - Check printer status

```bash
python -m src.pipeline.cli status [options]

Options:
  --mock             Use mock printer
  --printer-ip IP    Printer IP address
```

### `workflow` - Run full pipeline

```bash
python -m src.pipeline.cli workflow <shape> [options]

Options:
  --auto-print       Start print automatically
  --monitor          Monitor print progress
  --mock             Use mock printer
  (plus all create options)
```

### `scan` - Process LiDAR scans

Process 3D scans from iOS LiDAR apps (Polycam, 3D Scanner App, KIRI Engine, Scaniverse, Heges).

```bash
# Analyze a scan
python -m src.pipeline.cli scan analyze phone_scan.stl

# Repair mesh issues (holes, non-manifold edges)
python -m src.pipeline.cli scan repair phone_scan.stl --output repaired.stl --smooth 2

# Scale to real dimensions
python -m src.pipeline.cli scan scale phone_scan.stl --target-width 150 --output scaled.stl

# Reduce polygon count
python -m src.pipeline.cli scan decimate phone_scan.stl --ratio 0.5 --output decimated.stl

# Make hollow (save material)
python -m src.pipeline.cli scan hollow phone_scan.stl --wall-thickness 2.0 --output hollow.stl

# Generate protective case
python -m src.pipeline.cli scan case phone_scan.stl --case-type full_case --output case.stl

# Generate wall mount
python -m src.pipeline.cli scan mount controller.stl --output wall_mount.stl

# Generate angled stand
python -m src.pipeline.cli scan stand tablet.stl --angle 60 --output stand.stl

# Generate cradle holder
python -m src.pipeline.cli scan cradle phone_scan.stl --output cradle.stl
```

#### Scan Options

| Option | Description |
|--------|-------------|
| `--output, -o` | Output file path |
| `--format` | Export format (stl, obj, ply) |
| `--wall-thickness` | Wall thickness in mm |
| `--clearance` | Clearance gap for fit (mm) |
| `--case-type` | Case type (full_case, bumper, cradle, sleeve) |
| `--angle` | Stand angle in degrees |
| `--smooth` | Smoothing iterations |
| `--target-width/height/depth` | Target dimensions for scaling |
| `--target-faces` | Target face count for decimation |
| `--ratio` | Decimation ratio (0.5 = half) |

## iOS LiDAR Workflow

### Supported Apps

| App | Export Format | Best For |
|-----|--------------|----------|
| **Polycam** | STL, OBJ, PLY | High-quality scans, textures |
| **3D Scanner App** | STL, OBJ | Quick scans, sharing |
| **KIRI Engine** | STL, OBJ | Room scanning |
| **Scaniverse** | STL, OBJ | Object scanning |
| **Heges** | STL, OBJ | Detailed models |

### Workflow Example

1. **Scan object** with iOS app (Polycam recommended)
2. **Export as STL/OBJ** and transfer to Mac (AirDrop, iCloud, email)
3. **Process scan**:
   ```bash
   # Analyze scan quality
   python -m src.pipeline.cli scan analyze my_phone.stl

   # Repair any issues
   python -m src.pipeline.cli scan repair my_phone.stl --output repaired.stl

   # Generate case
   python -m src.pipeline.cli scan case repaired.stl --case-type full_case --output phone_case.stl
   ```
4. **Print case**:
   ```bash
   python -m src.pipeline.cli print output/phone_case.stl --mock --start --monitor
   ```

### Case Types

| Type | Description |
|------|-------------|
| `full_case` | Wraps entire object with opening |
| `bumper` | Protects edges only |
| `cradle` | Holds object from below |
| `sleeve` | Slides over object |
| `mount` | Wall/desk mount with screw holes |
| `stand` | Angled display stand |

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `BAMBOO_PRINTER_IP` | Printer IP address |
| `BAMBOO_ACCESS_CODE` | Printer access code |
| `BAMBOO_SERIAL` | Printer serial number |
| `BLENDER_PATH` | Path to Blender executable |

### Local Settings

Create `config/settings_local.py` to override defaults:

```python
PRINTER_IP = "192.168.1.100"
PRINTER_ACCESS_CODE = "your_code"
PRINTER_SERIAL = "your_serial"
```

## Python API

### Create Models

```python
from src.pipeline.workflow import PrintWorkflow, WorkflowConfig

config = WorkflowConfig(
    model_type="cube",
    model_params={"size": 25},
    use_mock_printer=True
)

workflow = PrintWorkflow(config)
result = workflow.create_model()
print(f"Created: {result.output_path}")
```

### Control Printer

```python
from src.printer import BambooConnection, PrinterCommands

conn = BambooConnection(
    ip="192.168.1.100",
    access_code="your_code",
    serial="your_serial"
)

if conn.connect():
    commands = PrinterCommands(conn)

    # Check status
    print(conn.status)

    # Start print
    commands.start_print("model.3mf")

    conn.disconnect()
```

### Use Mock Printer

```python
from src.printer import create_mock_printer

printer = create_mock_printer()
printer.connect()

# Upload and print
printer.upload_file("test.stl", 1024)
printer.start_print("test.stl")

# Monitor
while printer.status.progress < 100:
    print(f"Progress: {printer.status.progress}%")
    time.sleep(1)

printer.disconnect()
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_printer.py -v

# Run with coverage
pytest tests/ --cov=src
```

## Supported Printers

- Bamboo Labs A1
- Bamboo Labs A1 Mini
- Bamboo Labs P1S
- Bamboo Labs X1 Carbon

### Printer Setup

1. Enable **LAN Mode** or **Developer Mode** on printer
2. Note printer IP address (Settings → Network)
3. Note access code (Settings → Network or Bambu Handy app)
4. Configure in environment or settings file

## Network Requirements

| Port | Protocol | Purpose |
|------|----------|---------|
| 8883 | MQTT/TLS | Printer control |
| 990 | FTPS | File upload |

## License

MIT License - see LICENSE file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests/ -v`
4. Submit pull request

## Credits

Built with Claude Code by Anthropic.
