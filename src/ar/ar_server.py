"""AR preview server for serving USDZ files.

Provides a local web server that:
- Serves USDZ files for AR Quick Look
- Generates HTML preview pages
- Creates QR codes for easy mobile access
"""

import asyncio
import socket
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("ar.ar_server")


@dataclass
class ARSession:
    """An AR preview session."""
    session_id: str
    model_path: str
    usdz_path: Optional[str] = None
    preview_url: Optional[str] = None
    qr_code_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    accessed_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "model_path": self.model_path,
            "usdz_path": self.usdz_path,
            "preview_url": self.preview_url,
            "qr_code_path": self.qr_code_path,
            "created_at": self.created_at,
            "accessed_count": self.accessed_count,
        }


class ARServer:
    """
    Local server for AR preview.

    Serves USDZ files and generates QR codes for iPhone AR viewing.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 9880):
        """
        Initialize AR server.

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self._sessions: Dict[str, ARSession] = {}
        self._running = False
        self._server = None

        settings = get_settings()
        self._output_dir = Path(settings.output_dir) / "ar"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _get_local_ip(self) -> str:
        """Get the local IP address for LAN access."""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @property
    def base_url(self) -> str:
        """Get the base URL for the server."""
        ip = self._get_local_ip()
        return f"http://{ip}:{self.port}"

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    async def create_session(
        self,
        model_path: str,
        export_usdz: bool = True,
        generate_qr: bool = True,
    ) -> ARSession:
        """
        Create a new AR preview session.

        Args:
            model_path: Path to the 3D model
            export_usdz: Whether to export to USDZ
            generate_qr: Whether to generate QR code

        Returns:
            AR session with URLs and QR code
        """
        from src.ar.usdz_exporter import USDZExporter, ExportStatus
        from src.ar.qr_generator import QRGenerator

        session_id = str(uuid4())[:8]
        session = ARSession(
            session_id=session_id,
            model_path=model_path,
        )

        # Export to USDZ if needed
        if export_usdz:
            input_path = Path(model_path)
            usdz_path = self._output_dir / f"{input_path.stem}_{session_id}.usdz"

            exporter = USDZExporter()
            result = await exporter.export(model_path, str(usdz_path))

            if result.status == ExportStatus.COMPLETED:
                session.usdz_path = result.output_path
            else:
                logger.error(f"USDZ export failed: {result.error_message}")

        # Generate preview URL
        if session.usdz_path:
            session.preview_url = f"{self.base_url}/ar/{session_id}"

        # Generate QR code
        if generate_qr and session.preview_url:
            qr_gen = QRGenerator()
            qr_path = qr_gen.generate(session.preview_url)
            session.qr_code_path = qr_path

        self._sessions[session_id] = session
        logger.info(f"Created AR session: {session_id}")

        return session

    def get_session(self, session_id: str) -> Optional[ARSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[ARSession]:
        """List all sessions."""
        return list(self._sessions.values())

    async def start(self) -> None:
        """Start the AR server."""
        try:
            from aiohttp import web
        except ImportError:
            logger.error("aiohttp not installed. Install with: pip install aiohttp")
            return

        app = web.Application()

        # Add routes
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/ar/{session_id}", self._handle_ar_preview)
        app.router.add_get("/ar/{session_id}/model.usdz", self._handle_usdz)
        app.router.add_get("/qr/{session_id}", self._handle_qr)
        app.router.add_get("/api/sessions", self._handle_api_sessions)

        # Start server
        runner = web.AppRunner(app)
        await runner.setup()

        self._server = web.TCPSite(runner, self.host, self.port)
        await self._server.start()

        self._running = True
        logger.info(f"AR server started at {self.base_url}")

    async def stop(self) -> None:
        """Stop the AR server."""
        if self._server:
            await self._server.stop()
            self._server = None

        self._running = False
        logger.info("AR server stopped")

    async def _handle_index(self, request) -> 'web.Response':
        """Handle index page request."""
        from aiohttp import web

        html = self._generate_index_html()
        return web.Response(text=html, content_type="text/html")

    async def _handle_ar_preview(self, request) -> 'web.Response':
        """Handle AR preview page request."""
        from aiohttp import web

        session_id = request.match_info["session_id"]
        session = self._sessions.get(session_id)

        if not session:
            return web.Response(text="Session not found", status=404)

        session.accessed_count += 1

        html = self._generate_ar_html(session)
        return web.Response(text=html, content_type="text/html")

    async def _handle_usdz(self, request) -> 'web.Response':
        """Handle USDZ file request."""
        from aiohttp import web

        session_id = request.match_info["session_id"]
        session = self._sessions.get(session_id)

        if not session or not session.usdz_path:
            return web.Response(text="Model not found", status=404)

        usdz_path = Path(session.usdz_path)
        if not usdz_path.exists():
            return web.Response(text="Model file not found", status=404)

        session.accessed_count += 1

        return web.FileResponse(
            usdz_path,
            headers={
                "Content-Type": "model/vnd.usdz+zip",
                "Content-Disposition": f'inline; filename="{usdz_path.name}"',
            },
        )

    async def _handle_qr(self, request) -> 'web.Response':
        """Handle QR code image request."""
        from aiohttp import web

        session_id = request.match_info["session_id"]
        session = self._sessions.get(session_id)

        if not session or not session.qr_code_path:
            return web.Response(text="QR code not found", status=404)

        qr_path = Path(session.qr_code_path)
        if not qr_path.exists():
            return web.Response(text="QR file not found", status=404)

        return web.FileResponse(qr_path, content_type="image/png")

    async def _handle_api_sessions(self, request) -> 'web.Response':
        """Handle API sessions list request."""
        from aiohttp import web
        import json

        sessions = [s.to_dict() for s in self._sessions.values()]
        return web.Response(
            text=json.dumps(sessions, indent=2),
            content_type="application/json",
        )

    def _generate_index_html(self) -> str:
        """Generate index page HTML."""
        sessions_html = ""
        for session in self._sessions.values():
            sessions_html += f"""
            <div class="session">
                <h3>{Path(session.model_path).name}</h3>
                <p>Session: {session.session_id}</p>
                <a href="/ar/{session.session_id}">View AR Preview</a>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Claude Fab Lab - AR Preview</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
        }}
        .session {{
            background: white;
            padding: 20px;
            margin: 10px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .session h3 {{
            margin-top: 0;
        }}
        .session a {{
            display: inline-block;
            padding: 10px 20px;
            background: #007aff;
            color: white;
            text-decoration: none;
            border-radius: 6px;
        }}
        .empty {{
            text-align: center;
            color: #666;
            padding: 40px;
        }}
    </style>
</head>
<body>
    <h1>Claude Fab Lab - AR Preview</h1>
    <p>Available AR preview sessions:</p>
    {sessions_html if sessions_html else '<div class="empty">No sessions available</div>'}
</body>
</html>"""

    def _generate_ar_html(self, session: ARSession) -> str:
        """Generate AR preview page HTML."""
        model_name = Path(session.model_path).name
        usdz_url = f"/ar/{session.session_id}/model.usdz"
        qr_url = f"/qr/{session.session_id}" if session.qr_code_path else ""

        qr_section = ""
        if qr_url:
            qr_section = f"""
            <div class="qr-section">
                <h2>Scan with iPhone</h2>
                <img src="{qr_url}" alt="QR Code" class="qr-code">
                <p>Point your iPhone camera at this QR code to view in AR</p>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AR Preview - {model_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            text-align: center;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            font-size: 24px;
        }}
        .model-name {{
            color: #666;
            margin-bottom: 30px;
        }}
        .ar-button {{
            display: inline-block;
            padding: 15px 30px;
            background: #007aff;
            color: white;
            text-decoration: none;
            border-radius: 10px;
            font-size: 18px;
            margin: 20px 0;
        }}
        .ar-button:active {{
            background: #0056b3;
        }}
        .qr-section {{
            margin-top: 40px;
            padding: 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .qr-code {{
            width: 200px;
            height: 200px;
            margin: 20px auto;
            display: block;
        }}
        .instructions {{
            margin-top: 30px;
            padding: 20px;
            background: white;
            border-radius: 12px;
            text-align: left;
        }}
        .instructions h3 {{
            margin-top: 0;
        }}
        .instructions ol {{
            padding-left: 20px;
        }}
        .instructions li {{
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <h1>AR Preview</h1>
    <p class="model-name">{model_name}</p>

    <!-- AR Quick Look link (works on iOS Safari) -->
    <a rel="ar" href="{usdz_url}" class="ar-button">
        View in AR
        <img style="display:none" src="">
    </a>

    {qr_section}

    <div class="instructions">
        <h3>How to use</h3>
        <ol>
            <li><strong>On iPhone/iPad:</strong> Tap "View in AR" to see the model in your space</li>
            <li><strong>On desktop:</strong> Scan the QR code with your iPhone camera</li>
            <li>Move your device to place the model in your environment</li>
            <li>Pinch to resize, drag to move</li>
        </ol>
    </div>
</body>
</html>"""


async def serve_ar_preview(
    model_path: str,
    port: int = 8080,
    open_browser: bool = True,
) -> ARSession:
    """
    Convenience function to serve an AR preview.

    Args:
        model_path: Path to the 3D model
        port: Port to serve on
        open_browser: Whether to open the browser

    Returns:
        AR session with preview URL
    """
    server = ARServer(port=port)

    # Create session
    session = await server.create_session(model_path)

    # Start server
    await server.start()

    # Open browser if requested
    if open_browser and session.preview_url:
        import webbrowser
        webbrowser.open(session.preview_url)

    logger.info(f"AR preview available at: {session.preview_url}")
    if session.qr_code_path:
        logger.info(f"QR code saved to: {session.qr_code_path}")

    return session
