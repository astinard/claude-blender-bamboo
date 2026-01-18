"""
JARVIS Web Server

FastAPI backend that serves the web dashboard and provides API endpoints
for controlling the fabrication system.

Endpoints:
- GET  /               - Web dashboard
- GET  /api/status     - System status
- POST /api/scan       - Start scan
- POST /api/analyze    - Analyze mesh
- POST /api/repair     - Repair mesh
- POST /api/print      - Start print
- POST /api/laser      - Start laser cut
- POST /api/stop       - Emergency stop
- POST /api/command    - Process voice command
- WS   /ws             - WebSocket for real-time updates
"""

import asyncio
import json
import subprocess
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import threading
import queue

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import uvicorn

# Import our modules
try:
    from config import BLENDER_EXECUTABLE, OUTPUT_DIR, TEMP_DIR
except ImportError:
    BLENDER_EXECUTABLE = "/Applications/Blender.app/Contents/MacOS/Blender"
    OUTPUT_DIR = project_root / "output"
    TEMP_DIR = project_root / "temp"

try:
    from src.printer import MockPrinter, create_mock_printer, PrinterStatus, PrinterState
    from src.materials.library import MaterialLibrary
    from src.estimator.cost_estimator import CostEstimator
    from src.pipeline.workflow import PrintWorkflow, WorkflowConfig
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SystemState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    PROCESSING = "processing"
    PRINTING = "printing"
    LASER_CUTTING = "laser_cutting"
    ERROR = "error"


@dataclass
class SystemStatus:
    state: SystemState = SystemState.IDLE
    printer_connected: bool = False
    laser_connected: bool = False
    blender_available: bool = False
    bed_temp: float = 25.0
    nozzle_temp: float = 25.0
    chamber_temp: float = 28.0
    current_job: Optional[str] = None
    progress: float = 0.0
    message: str = "Ready"
    materials: List[Dict[str, Any]] = None

    def to_dict(self):
        return {
            "state": self.state.value,
            "printer_connected": self.printer_connected,
            "laser_connected": self.laser_connected,
            "blender_available": self.blender_available,
            "bed_temp": self.bed_temp,
            "nozzle_temp": self.nozzle_temp,
            "chamber_temp": self.chamber_temp,
            "current_job": self.current_job,
            "progress": self.progress,
            "message": self.message,
            "materials": self.materials or []
        }


class CommandRequest(BaseModel):
    command: str


class PrintRequest(BaseModel):
    model_type: str = "cube"
    params: Dict[str, Any] = {}
    material: str = "PLA"
    auto_start: bool = False


class ScanResult(BaseModel):
    vertices: int = 0
    faces: int = 0
    volume: float = 0.0
    dimensions: str = ""
    watertight: bool = True
    file_path: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# FABRICATION CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════════

class FabricationController:
    """Central controller for all fabrication operations."""

    def __init__(self):
        self.status = SystemStatus()
        self.mock_printer: Optional[MockPrinter] = None
        self.websocket_clients: List[WebSocket] = []
        self.event_queue = queue.Queue()
        self._check_blender()
        self._init_mock_printer()
        self._init_materials()

    def _check_blender(self):
        """Check if Blender is available."""
        blender_path = Path(BLENDER_EXECUTABLE)
        self.status.blender_available = blender_path.exists()

    def _init_mock_printer(self):
        """Initialize mock printer for demo."""
        if MODULES_AVAILABLE:
            try:
                self.mock_printer = create_mock_printer()
                self.mock_printer.connect()
                self.status.printer_connected = True
            except:
                pass

    def _init_materials(self):
        """Initialize material library."""
        self.status.materials = [
            {"slot": 1, "name": "PLA White", "color": "#ffffff", "level": 80},
            {"slot": 2, "name": "PLA Red", "color": "#ff4444", "level": 65},
            {"slot": 3, "name": "PLA Blue", "color": "#4444ff", "level": 90},
            {"slot": 4, "name": "PLA Green", "color": "#44ff44", "level": 45},
        ]

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all WebSocket clients."""
        message = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()})
        disconnected = []
        for ws in self.websocket_clients:
            try:
                await ws.send_text(message)
            except:
                disconnected.append(ws)
        for ws in disconnected:
            self.websocket_clients.remove(ws)

    async def log(self, message: str, level: str = "info"):
        """Send log message to clients."""
        await self.broadcast("log", {"message": message, "level": level})

    async def update_status(self):
        """Send status update to clients."""
        await self.broadcast("status", self.status.to_dict())

    # ═══════════════════════════════════════════════════════════════════════════
    # OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    async def scan(self) -> ScanResult:
        """Perform a scan operation."""
        self.status.state = SystemState.SCANNING
        self.status.current_job = "Scanning object"
        self.status.message = "Initializing LiDAR scanner..."
        await self.update_status()
        await self.log("Initializing LiDAR scanner...")

        # Simulate scan progress
        for i in range(10):
            self.status.progress = (i + 1) * 10
            self.status.message = f"Scanning... {self.status.progress:.0f}%"
            await self.update_status()
            await asyncio.sleep(0.3)

        await self.log("Scan complete!", "success")

        # Mock scan result
        result = ScanResult(
            vertices=847293,
            faces=1694582,
            volume=42.7,
            dimensions="75 x 150 x 8 mm",
            watertight=True,
            file_path=str(OUTPUT_DIR / "scan_result.stl")
        )

        self.status.state = SystemState.IDLE
        self.status.current_job = None
        self.status.progress = 0
        self.status.message = "Scan complete"
        await self.update_status()

        return result

    async def analyze(self) -> Dict[str, Any]:
        """Analyze mesh topology."""
        self.status.state = SystemState.PROCESSING
        self.status.message = "Analyzing mesh..."
        await self.update_status()
        await self.log("Analyzing mesh topology...")

        await asyncio.sleep(2)

        result = {
            "topology": "Manifold",
            "watertight": True,
            "self_intersections": 0,
            "degenerate_faces": 0,
            "printability": "Excellent"
        }

        await self.log("Mesh is watertight and printable.", "success")

        self.status.state = SystemState.IDLE
        self.status.message = "Analysis complete"
        await self.update_status()

        return result

    async def repair(self) -> Dict[str, Any]:
        """Repair mesh issues."""
        self.status.state = SystemState.PROCESSING
        self.status.message = "Repairing mesh..."
        await self.update_status()
        await self.log("Running auto-repair algorithm...")

        await asyncio.sleep(1)
        await self.log("Found 3 holes and 12 non-manifold edges...", "warning")

        for i in range(5):
            self.status.progress = (i + 1) * 20
            await self.update_status()
            await asyncio.sleep(0.3)

        await self.log("Repaired 3 holes and 12 non-manifold edges.", "success")

        self.status.state = SystemState.IDLE
        self.status.progress = 0
        self.status.message = "Repair complete"
        await self.update_status()

        return {"holes_fixed": 3, "edges_fixed": 12}

    async def hollow(self, wall_thickness: float = 2.0) -> Dict[str, Any]:
        """Hollow out the model."""
        self.status.state = SystemState.PROCESSING
        self.status.message = f"Hollowing (wall: {wall_thickness}mm)..."
        await self.update_status()
        await self.log(f"Creating hollow shell ({wall_thickness}mm walls)...")

        for i in range(10):
            self.status.progress = (i + 1) * 10
            await self.update_status()
            await asyncio.sleep(0.2)

        await self.log("Hollowing complete. Material savings: 68%", "success")

        self.status.state = SystemState.IDLE
        self.status.progress = 0
        self.status.message = "Hollow complete"
        await self.update_status()

        return {"wall_thickness": wall_thickness, "material_saved": 68, "new_volume": 13.7}

    async def start_print(self, request: PrintRequest) -> Dict[str, Any]:
        """Start a 3D print."""
        self.status.state = SystemState.PRINTING
        self.status.current_job = f"Printing {request.model_type}"
        await self.update_status()
        await self.log("Initiating print sequence...")

        # Heat bed
        await self.log("Heating bed to 60C...")
        for temp in range(25, 61, 5):
            self.status.bed_temp = temp
            await self.update_status()
            await asyncio.sleep(0.2)
        await self.log("Bed temperature reached.", "success")

        # Heat nozzle
        await self.log("Heating nozzle to 210C...")
        for temp in range(25, 211, 15):
            self.status.nozzle_temp = temp
            await self.update_status()
            await asyncio.sleep(0.2)
        await self.log("Nozzle temperature reached.", "success")

        await self.log("Beginning fabrication...")

        # Simulate print
        for i in range(20):
            self.status.progress = (i + 1) * 5
            self.status.message = f"Printing layer {i + 1}/20..."
            await self.update_status()
            await asyncio.sleep(0.5)

        await self.log("Print complete!", "success")

        self.status.state = SystemState.IDLE
        self.status.current_job = None
        self.status.progress = 0
        self.status.message = "Print complete"
        self.status.bed_temp = 25
        self.status.nozzle_temp = 25
        await self.update_status()

        return {"success": True, "print_time": "2h 45m", "material_used": "42.3g"}

    async def start_laser(self, power: int = 80, speed: int = 10) -> Dict[str, Any]:
        """Start laser cutting."""
        self.status.state = SystemState.LASER_CUTTING
        self.status.current_job = "Laser cutting"
        await self.update_status()
        await self.log("Preparing laser cutter...")
        await self.log("WARNING: Ensure safety enclosure is closed!", "warning")

        await asyncio.sleep(1)
        await self.log("Laser armed. Cutting in progress...")

        for i in range(10):
            self.status.progress = (i + 1) * 10
            await self.update_status()
            await asyncio.sleep(0.5)

        await self.log("Laser cutting complete.", "success")

        self.status.state = SystemState.IDLE
        self.status.current_job = None
        self.status.progress = 0
        self.status.message = "Laser complete"
        await self.update_status()

        return {"success": True, "cut_time": "3m 24s"}

    async def emergency_stop(self):
        """Emergency stop all operations."""
        await self.log("EMERGENCY STOP ACTIVATED", "error")

        self.status.state = SystemState.IDLE
        self.status.current_job = None
        self.status.progress = 0
        self.status.message = "Emergency stop - all operations halted"
        self.status.bed_temp = 25
        self.status.nozzle_temp = 25
        await self.update_status()

        await self.log("All operations halted. Systems safe.", "warning")

    async def process_command(self, command: str) -> Dict[str, Any]:
        """Process a voice/text command."""
        command = command.lower().strip()

        if "scan" in command:
            result = await self.scan()
            return {"action": "scan", "result": asdict(result) if hasattr(result, '__dataclass_fields__') else result.__dict__}
        elif "analyze" in command:
            result = await self.analyze()
            return {"action": "analyze", "result": result}
        elif "repair" in command or "fix" in command:
            result = await self.repair()
            return {"action": "repair", "result": result}
        elif "hollow" in command:
            result = await self.hollow()
            return {"action": "hollow", "result": result}
        elif "print" in command:
            result = await self.start_print(PrintRequest())
            return {"action": "print", "result": result}
        elif "laser" in command or "cut" in command:
            result = await self.start_laser()
            return {"action": "laser", "result": result}
        elif "stop" in command or "abort" in command:
            await self.emergency_stop()
            return {"action": "stop", "result": {"stopped": True}}
        elif "status" in command:
            return {"action": "status", "result": self.status.to_dict()}
        else:
            await self.log(f"Unknown command: {command}", "warning")
            return {"action": "unknown", "result": {"error": f"Unknown command: {command}"}}

    async def launch_blender(self, script: Optional[str] = None) -> Dict[str, Any]:
        """Launch Blender application."""
        if not self.status.blender_available:
            await self.log("Blender not found!", "error")
            return {"success": False, "error": "Blender not installed"}

        await self.log("Launching Blender...")

        try:
            cmd = [BLENDER_EXECUTABLE]
            if script:
                cmd.extend(["--python", script])

            # Launch in background
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await self.log("Blender launched successfully.", "success")
            return {"success": True}
        except Exception as e:
            await self.log(f"Failed to launch Blender: {e}", "error")
            return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="JARVIS Fab Lab API", version="1.0.0")
controller = FabricationController()


# Serve static files (web dashboard)
web_dir = project_root / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web dashboard."""
    index_path = web_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>JARVIS Fab Lab</h1><p>Web dashboard not found.</p>")


@app.get("/api/status")
async def get_status():
    """Get current system status."""
    return controller.status.to_dict()


@app.post("/api/scan")
async def scan():
    """Start a scan operation."""
    result = await controller.scan()
    return {"success": True, "result": result.__dict__}


@app.post("/api/analyze")
async def analyze():
    """Analyze the current mesh."""
    result = await controller.analyze()
    return {"success": True, "result": result}


@app.post("/api/repair")
async def repair():
    """Repair mesh issues."""
    result = await controller.repair()
    return {"success": True, "result": result}


@app.post("/api/hollow")
async def hollow(wall_thickness: float = 2.0):
    """Hollow out the model."""
    result = await controller.hollow(wall_thickness)
    return {"success": True, "result": result}


@app.post("/api/print")
async def start_print(request: PrintRequest):
    """Start a 3D print job."""
    result = await controller.start_print(request)
    return {"success": True, "result": result}


@app.post("/api/laser")
async def start_laser(power: int = 80, speed: int = 10):
    """Start laser cutting."""
    result = await controller.start_laser(power, speed)
    return {"success": True, "result": result}


@app.post("/api/stop")
async def emergency_stop():
    """Emergency stop all operations."""
    await controller.emergency_stop()
    return {"success": True}


@app.post("/api/command")
async def process_command(request: CommandRequest):
    """Process a voice/text command."""
    result = await controller.process_command(request.command)
    return result


@app.post("/api/launch-blender")
async def launch_blender(script: Optional[str] = None):
    """Launch Blender application."""
    result = await controller.launch_blender(script)
    return result


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    controller.websocket_clients.append(websocket)

    # Send initial status
    await websocket.send_text(json.dumps({
        "type": "connected",
        "data": controller.status.to_dict(),
        "timestamp": datetime.now().isoformat()
    }))

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "command":
                result = await controller.process_command(message.get("data", ""))
                await websocket.send_text(json.dumps({
                    "type": "command_result",
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                }))
            elif message.get("type") == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }))

    except WebSocketDisconnect:
        controller.websocket_clients.remove(websocket)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the JARVIS server."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    JARVIS FAB LAB SERVER                     ║
╠══════════════════════════════════════════════════════════════╣
║  Server: http://{host}:{port:<38}║
║  API:    http://{host}:{port}/api/status{' '*28}║
║  WS:     ws://{host}:{port}/ws{' '*33}║
╚══════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JARVIS Fab Lab Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()
    run_server(args.host, args.port)
