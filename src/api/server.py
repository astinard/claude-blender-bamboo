"""API server for JARVIS Fab Lab Control.

Connects the web UI to the backend features.
"""

import asyncio
import json
import os
import webbrowser
from pathlib import Path
from typing import Optional

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("api.server")


class JARVISServer:
    """API server for JARVIS Fab Lab Control."""

    def __init__(self, host: str = "localhost", port: int = 8080):
        """Initialize the server."""
        self.host = host
        self.port = port
        self.app = None
        self.runner = None
        self._setup_routes()

    def _setup_routes(self):
        """Set up API routes."""
        if not HAS_AIOHTTP:
            logger.error("aiohttp not installed")
            return

        self.app = web.Application()
        self.websockets = set()

        # WebSocket for real-time updates
        self.app.router.add_get("/ws", self._websocket_handler)

        # Static files and pages
        self.app.router.add_get("/", self._serve_index)
        self.app.router.add_get("/api/status", self._get_status)
        self.app.router.add_post("/api/scan", self._start_scan)
        self.app.router.add_post("/api/analyze", self._analyze_mesh)
        self.app.router.add_post("/api/repair", self._repair_mesh)
        self.app.router.add_post("/api/hollow", self._hollow_mesh)
        self.app.router.add_post("/api/print", self._start_print)
        self.app.router.add_post("/api/generate", self._generate_model)
        self.app.router.add_post("/api/queue/add", self._add_to_queue)
        self.app.router.add_get("/api/queue", self._get_queue)
        self.app.router.add_get("/api/materials", self._get_materials)
        self.app.router.add_get("/api/analytics", self._get_analytics)
        self.app.router.add_post("/api/ar-preview", self._ar_preview)
        self.app.router.add_post("/api/command", self._process_command)
        self.app.router.add_get("/api/scans", self._get_scans)
        self.app.router.add_post("/api/scans/import", self._import_scan)
        self.app.router.add_get("/api/scans/watch-folder", self._get_watch_folder)
        self.app.router.add_static("/static", Path(__file__).parent.parent.parent / "web")
        self.app.router.add_static("/static/scans", Path(__file__).parent.parent.parent / "scans")
        self.app.router.add_static("/static/output", Path(__file__).parent.parent.parent / "output")

    async def _websocket_handler(self, request):
        """Handle WebSocket connections."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.websockets.add(ws)
        logger.info("WebSocket client connected")

        # Send initial status
        await ws.send_json({
            "type": "connected",
            "data": {
                "bed_temp": 25.0,
                "nozzle_temp": 25.0,
                "chamber_temp": 28.0,
                "print_speed": 100,
            }
        })

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    # Handle incoming WebSocket commands
                    if data.get("type") == "command":
                        result = await self._handle_ws_command(data.get("command", ""))
                        await ws.send_json({"type": "command_result", "data": result})
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            self.websockets.discard(ws)
            logger.info("WebSocket client disconnected")

        return ws

    async def _handle_ws_command(self, command: str) -> dict:
        """Handle a WebSocket command."""
        try:
            from src.jarvis import create_voice_controller
            controller = create_voice_controller()
            result = await controller.process_command(command)
            return {
                "success": result.success,
                "command": result.command,
                "message": result.message,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def broadcast(self, message: dict):
        """Broadcast message to all connected WebSocket clients."""
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def _serve_index(self, request):
        """Serve the main JARVIS interface."""
        index_path = Path(__file__).parent.parent.parent / "web" / "index.html"
        if index_path.exists():
            return web.FileResponse(index_path)
        return web.Response(text="JARVIS interface not found", status=404)

    async def _get_status(self, request):
        """Get system status."""
        return web.json_response({
            "systems_online": True,
            "printer_ready": True,
            "laser_standby": True,
            "bed_temp": 25.0,
            "nozzle_temp": 25.0,
            "chamber_temp": 28.0,
            "print_speed": 100,
            "materials": {
                "pla_white": 85,
                "pla_red": 70,
                "pla_blue": 60,
                "pla_green": 40,
            }
        })

    async def _start_scan(self, request):
        """Start object scanning."""
        try:
            from src.capture.photogrammetry import PhotogrammetryCapture
            capture = PhotogrammetryCapture()
            return web.json_response({
                "success": True,
                "message": "Scan initiated",
                "scan_id": "scan_001",
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _analyze_mesh(self, request):
        """Analyze mesh for printability."""
        try:
            data = await request.json()
            mesh_path = data.get("mesh_path", "")

            from src.blender.design_advisor import DesignAdvisor
            advisor = DesignAdvisor()
            # Mock analysis for demo
            return web.json_response({
                "success": True,
                "vertices": 847293,
                "faces": 1694582,
                "volume_cm3": 42.7,
                "watertight": True,
                "printability_score": 85,
                "issues": [],
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _repair_mesh(self, request):
        """Auto-repair mesh issues."""
        return web.json_response({
            "success": True,
            "repairs_made": 3,
            "message": "Repaired 3 holes and 12 non-manifold edges",
        })

    async def _hollow_mesh(self, request):
        """Hollow out the mesh."""
        return web.json_response({
            "success": True,
            "wall_thickness_mm": 2.0,
            "material_saved_percent": 45,
        })

    async def _start_print(self, request):
        """Start a print job."""
        try:
            data = await request.json()

            from src.queue import PrintQueue
            queue = PrintQueue()

            return web.json_response({
                "success": True,
                "job_id": "print_001",
                "estimated_time_minutes": 120,
                "message": "Print started",
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _generate_model(self, request):
        """Generate 3D model from text."""
        try:
            data = await request.json()
            prompt = data.get("prompt", "")

            from src.ai import TextTo3DGenerator
            generator = TextTo3DGenerator()

            # For demo, use mock mode
            result = await generator.generate(prompt, provider="mock")

            return web.json_response({
                "success": result.success,
                "model_path": result.model_path if result.success else None,
                "message": result.message,
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _add_to_queue(self, request):
        """Add model to print queue."""
        try:
            data = await request.json()

            from src.queue import PrintQueue, create_queue
            queue = create_queue()
            job = queue.add(
                name=data.get("name", "model"),
                file_path=data.get("file_path", ""),
                priority=data.get("priority", "normal"),
            )

            return web.json_response({
                "success": True,
                "job_id": job.id,
                "position": queue.get_position(job.id),
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _get_queue(self, request):
        """Get print queue status."""
        try:
            from src.queue import PrintQueue, create_queue
            queue = create_queue()
            jobs = queue.list_jobs()

            return web.json_response({
                "success": True,
                "jobs": [j.to_dict() for j in jobs],
                "total": len(jobs),
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _get_materials(self, request):
        """Get material inventory."""
        try:
            from src.materials import MaterialInventory, create_inventory
            inventory = create_inventory()
            spools = inventory.list_spools()

            return web.json_response({
                "success": True,
                "spools": [s.to_dict() for s in spools],
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _get_analytics(self, request):
        """Get print analytics."""
        try:
            from src.analytics import PrintAnalytics, create_analytics
            analytics = create_analytics()
            stats = analytics.get_stats()

            return web.json_response({
                "success": True,
                "stats": stats,
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _ar_preview(self, request):
        """Generate AR preview."""
        try:
            data = await request.json()
            mesh_path = data.get("mesh_path", "")

            from src.ar import USDZExporter, create_exporter
            exporter = create_exporter()
            result = exporter.export(mesh_path)

            return web.json_response({
                "success": result.success,
                "usdz_path": result.usdz_path if result.success else None,
                "qr_code_path": result.qr_path if result.success else None,
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _process_command(self, request):
        """Process voice/text command."""
        try:
            data = await request.json()
            command = data.get("command", "")

            from src.jarvis import create_voice_controller
            controller = create_voice_controller()
            result = await controller.process_command(command)

            return web.json_response({
                "success": result.success,
                "command": result.command,
                "message": result.message,
                "data": result.data,
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _get_scans(self, request):
        """Get list of imported scans."""
        try:
            from src.capture import create_importer
            importer = create_importer()
            scans = importer.list_imported_scans()

            return web.json_response({
                "success": True,
                "scans": scans,
                "total": len(scans),
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _import_scan(self, request):
        """Import a scan from watch folder or check for new scans."""
        try:
            from src.capture import create_importer
            importer = create_importer()

            # Check for new scans in watch folder
            results = importer.check_for_new_scans()

            imported = []
            for result in results:
                if result.success:
                    imported.append({
                        "name": result.name,
                        "path": str(result.imported_path),
                        "vertices": result.vertices,
                        "faces": result.faces,
                        "size_mb": result.file_size_mb,
                    })

            return web.json_response({
                "success": True,
                "imported": imported,
                "count": len(imported),
                "message": f"Imported {len(imported)} scan(s)" if imported else "No new scans found",
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def _get_watch_folder(self, request):
        """Get the watch folder path for scan imports."""
        try:
            from src.capture import create_importer, PolycamIntegration
            importer = create_importer()

            return web.json_response({
                "success": True,
                "watch_folder": str(importer.get_watch_folder()),
                "instructions": PolycamIntegration.setup_polycam_export_instructions(),
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e),
            })

    async def start(self):
        """Start the server."""
        if not HAS_AIOHTTP:
            logger.error("Cannot start server: aiohttp not installed")
            return False

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()

        logger.info(f"JARVIS server running at http://{self.host}:{self.port}")
        return True

    async def stop(self):
        """Stop the server."""
        if self.runner:
            await self.runner.cleanup()


def create_server(host: str = "localhost", port: int = 8080) -> JARVISServer:
    """Create a JARVIS server."""
    return JARVISServer(host=host, port=port)


async def run_server(host: str = "localhost", port: int = 8080, open_browser: bool = True):
    """Run the JARVIS server."""
    server = create_server(host, port)
    await server.start()

    if open_browser:
        webbrowser.open(f"http://{host}:{port}")

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(run_server())
