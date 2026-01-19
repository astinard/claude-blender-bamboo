"""Remote monitoring dashboard for Claude Fab Lab.

Provides a web-based dashboard for monitoring 3D prints remotely.
Features:
- Live camera feed
- Temperature graphs
- Print progress
- Push notifications
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any
from uuid import uuid4

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("jarvis.dashboard")


class PrintStatus(str, Enum):
    """Status of print job."""
    IDLE = "idle"
    PREPARING = "preparing"
    PRINTING = "printing"
    PAUSED = "paused"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TemperatureData:
    """Temperature reading."""
    timestamp: str
    nozzle_current: float
    nozzle_target: float
    bed_current: float
    bed_target: float
    chamber_current: Optional[float] = None
    chamber_target: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "nozzle": {
                "current": self.nozzle_current,
                "target": self.nozzle_target,
            },
            "bed": {
                "current": self.bed_current,
                "target": self.bed_target,
            },
            "chamber": {
                "current": self.chamber_current,
                "target": self.chamber_target,
            } if self.chamber_current is not None else None,
        }


@dataclass
class PrintProgress:
    """Current print progress."""
    print_id: str
    file_name: str
    status: PrintStatus
    progress_percent: float
    layer_current: int
    layer_total: int
    time_elapsed_seconds: int
    time_remaining_seconds: int
    filament_used_mm: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "print_id": self.print_id,
            "file_name": self.file_name,
            "status": self.status.value,
            "progress_percent": self.progress_percent,
            "layer_current": self.layer_current,
            "layer_total": self.layer_total,
            "time_elapsed": self.time_elapsed_seconds,
            "time_remaining": self.time_remaining_seconds,
            "filament_used_mm": self.filament_used_mm,
        }


@dataclass
class DashboardConfig:
    """Dashboard configuration."""
    host: str = "0.0.0.0"
    port: int = 9880
    enable_notifications: bool = True
    enable_camera: bool = True
    camera_fps: int = 10
    history_length: int = 100  # Number of temperature readings to keep
    update_interval_seconds: float = 1.0


@dataclass
class PrinterState:
    """Current state of the printer."""
    connected: bool = False
    status: PrintStatus = PrintStatus.IDLE
    progress: Optional[PrintProgress] = None
    temperatures: List[TemperatureData] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    last_update: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "connected": self.connected,
            "status": self.status.value,
            "progress": self.progress.to_dict() if self.progress else None,
            "temperatures": [t.to_dict() for t in self.temperatures[-20:]],  # Last 20
            "alerts": self.alerts[-10:],  # Last 10 alerts
            "last_update": self.last_update,
        }


class Dashboard:
    """
    Web-based monitoring dashboard.

    Provides real-time monitoring of 3D prints via web interface.
    """

    def __init__(self, config: Optional[DashboardConfig] = None):
        """
        Initialize dashboard.

        Args:
            config: Dashboard configuration
        """
        self.config = config or DashboardConfig()
        self._state = PrinterState()
        self._websockets: List[web.WebSocketResponse] = []
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        self._notification_callbacks: List[Callable[[str, str], None]] = []

        # Get web directory
        self._web_dir = Path(__file__).parent.parent.parent / "web"

    @property
    def is_running(self) -> bool:
        """Check if dashboard is running."""
        return self._running

    @property
    def state(self) -> PrinterState:
        """Get current printer state."""
        return self._state

    @property
    def url(self) -> str:
        """Get dashboard URL."""
        host = "localhost" if self.config.host == "0.0.0.0" else self.config.host
        return f"http://{host}:{self.config.port}"

    def update_status(self, status: PrintStatus) -> None:
        """Update print status."""
        self._state.status = status
        self._state.last_update = datetime.now().isoformat()
        self._schedule_broadcast()

    def update_progress(self, progress: PrintProgress) -> None:
        """Update print progress."""
        self._state.progress = progress
        self._state.status = progress.status
        self._state.last_update = datetime.now().isoformat()
        self._schedule_broadcast()

    def add_temperature(self, temp: TemperatureData) -> None:
        """Add temperature reading."""
        self._state.temperatures.append(temp)
        # Keep only last N readings
        if len(self._state.temperatures) > self.config.history_length:
            self._state.temperatures = self._state.temperatures[-self.config.history_length:]
        self._state.last_update = datetime.now().isoformat()

    def add_alert(self, alert_type: str, message: str, severity: str = "info") -> None:
        """Add an alert."""
        alert = {
            "id": str(uuid4())[:8],
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
        }
        self._state.alerts.append(alert)
        self._state.last_update = datetime.now().isoformat()

        # Notify callbacks
        for callback in self._notification_callbacks:
            try:
                callback(alert_type, message)
            except Exception as e:
                logger.error(f"Notification callback error: {e}")

        self._schedule_broadcast()

    def _schedule_broadcast(self) -> None:
        """Schedule a broadcast if running in async context."""
        if self._running:
            try:
                asyncio.create_task(self._broadcast_state())
            except RuntimeError:
                # No event loop running, skip broadcast
                pass

    def clear_alerts(self) -> int:
        """Clear all alerts."""
        count = len(self._state.alerts)
        self._state.alerts.clear()
        return count

    def register_notification_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for notifications."""
        self._notification_callbacks.append(callback)

    async def start(self) -> bool:
        """
        Start the dashboard server.

        Returns:
            True if started successfully
        """
        if not HAS_AIOHTTP:
            logger.error("aiohttp not installed. Run: pip install aiohttp")
            return False

        if self._running:
            return True

        try:
            self._app = web.Application()
            self._setup_routes()

            self._runner = web.AppRunner(self._app)
            await self._runner.setup()

            site = web.TCPSite(self._runner, self.config.host, self.config.port)
            await site.start()

            self._running = True
            self._state.connected = True
            self._state.last_update = datetime.now().isoformat()

            # Start update task
            self._update_task = asyncio.create_task(self._update_loop())

            logger.info(f"Dashboard started at {self.url}")
            return True

        except Exception as e:
            logger.error(f"Failed to start dashboard: {e}")
            return False

    async def stop(self) -> None:
        """Stop the dashboard server."""
        self._running = False

        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None

        # Close websockets
        for ws in self._websockets:
            await ws.close()
        self._websockets.clear()

        if self._runner:
            await self._runner.cleanup()
            self._runner = None

        self._app = None
        self._state.connected = False

        logger.info("Dashboard stopped")

    def _setup_routes(self) -> None:
        """Set up web routes."""
        self._app.router.add_get("/", self._handle_index)
        self._app.router.add_get("/api/status", self._handle_status)
        self._app.router.add_get("/api/temperatures", self._handle_temperatures)
        self._app.router.add_get("/api/alerts", self._handle_alerts)
        self._app.router.add_post("/api/alerts/clear", self._handle_clear_alerts)
        self._app.router.add_get("/ws", self._handle_websocket)

        # Static files
        if self._web_dir.exists():
            self._app.router.add_static("/static", self._web_dir)

    async def _handle_index(self, request: web.Request) -> web.Response:
        """Handle index page."""
        # Try to serve JARVIS dashboard if it exists
        jarvis_index = self._web_dir / "index.html"
        if jarvis_index.exists():
            html = jarvis_index.read_text()
            return web.Response(text=html, content_type="text/html")
        # Fall back to embedded dashboard
        html = self._generate_dashboard_html()
        return web.Response(text=html, content_type="text/html")

    async def _handle_status(self, request: web.Request) -> web.Response:
        """Handle status API."""
        return web.json_response(self._state.to_dict())

    async def _handle_temperatures(self, request: web.Request) -> web.Response:
        """Handle temperatures API."""
        temps = [t.to_dict() for t in self._state.temperatures]
        return web.json_response({"temperatures": temps})

    async def _handle_alerts(self, request: web.Request) -> web.Response:
        """Handle alerts API."""
        return web.json_response({"alerts": self._state.alerts})

    async def _handle_clear_alerts(self, request: web.Request) -> web.Response:
        """Handle clear alerts API."""
        count = self.clear_alerts()
        return web.json_response({"cleared": count})

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle websocket connection."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._websockets.append(ws)
        logger.info(f"WebSocket client connected ({len(self._websockets)} total)")

        # Send initial state
        await ws.send_json({"type": "state", "data": self._state.to_dict()})

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    # Handle incoming messages
                    data = json.loads(msg.data)
                    await self._handle_ws_message(ws, data)
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            self._websockets.remove(ws)
            logger.info(f"WebSocket client disconnected ({len(self._websockets)} total)")

        return ws

    async def _handle_ws_message(self, ws: web.WebSocketResponse, data: dict) -> None:
        """Handle incoming websocket message."""
        msg_type = data.get("type")

        if msg_type == "ping":
            await ws.send_json({"type": "pong"})
        elif msg_type == "subscribe":
            # Client subscribing to updates
            await ws.send_json({"type": "subscribed"})

    async def _broadcast_state(self) -> None:
        """Broadcast state to all connected clients."""
        if not self._websockets:
            return

        message = {"type": "state", "data": self._state.to_dict()}

        for ws in list(self._websockets):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

    async def _update_loop(self) -> None:
        """Periodic update loop."""
        while self._running:
            try:
                # Generate mock temperature data for demo
                temp = TemperatureData(
                    timestamp=datetime.now().isoformat(),
                    nozzle_current=200.0 + (time.time() % 10) * 0.1,
                    nozzle_target=200.0,
                    bed_current=60.0 + (time.time() % 5) * 0.1,
                    bed_target=60.0,
                )
                self.add_temperature(temp)

                await asyncio.sleep(self.config.update_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(1)

    def _generate_dashboard_html(self) -> str:
        """Generate dashboard HTML."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Fab Lab - Dashboard</title>
    <style>
        :root {
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --text-primary: #eaeaea;
            --text-secondary: #a0a0a0;
            --accent: #e94560;
            --success: #2ecc71;
            --warning: #f39c12;
            --danger: #e74c3c;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }

        .header {
            background: var(--bg-secondary);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--bg-card);
        }

        .header h1 {
            font-size: 1.5rem;
            font-weight: 600;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--danger);
        }

        .status-dot.connected {
            background: var(--success);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }

        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
        }

        .card h2 {
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .progress-section {
            grid-column: 1 / -1;
        }

        .progress-bar {
            height: 20px;
            background: var(--bg-secondary);
            border-radius: 10px;
            overflow: hidden;
            margin: 1rem 0;
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent), #ff6b6b);
            border-radius: 10px;
            transition: width 0.3s ease;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .stat-item {
            text-align: center;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 600;
            color: var(--accent);
        }

        .stat-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }

        .temp-display {
            display: flex;
            justify-content: space-around;
            text-align: center;
        }

        .temp-item .current {
            font-size: 2.5rem;
            font-weight: 600;
        }

        .temp-item .target {
            font-size: 0.9rem;
            color: var(--text-secondary);
        }

        .temp-item .label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
        }

        .alert-list {
            max-height: 300px;
            overflow-y: auto;
        }

        .alert-item {
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            border-radius: 8px;
            background: var(--bg-secondary);
            border-left: 4px solid var(--text-secondary);
        }

        .alert-item.warning {
            border-color: var(--warning);
        }

        .alert-item.critical {
            border-color: var(--danger);
        }

        .alert-item .time {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .no-alerts {
            color: var(--text-secondary);
            text-align: center;
            padding: 2rem;
        }

        #camera-feed {
            width: 100%;
            aspect-ratio: 16/9;
            background: var(--bg-secondary);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-secondary);
        }
    </style>
</head>
<body>
    <header class="header">
        <h1>Claude Fab Lab Dashboard</h1>
        <div class="status-indicator">
            <span class="status-dot" id="connection-status"></span>
            <span id="status-text">Connecting...</span>
        </div>
    </header>

    <div class="container">
        <div class="card progress-section">
            <h2>Print Progress</h2>
            <div id="print-status">No active print</div>
            <div class="progress-bar">
                <div class="progress-bar-fill" id="progress-fill" style="width: 0%"></div>
            </div>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value" id="progress-percent">0%</div>
                    <div class="stat-label">Progress</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="layer-info">0/0</div>
                    <div class="stat-label">Layer</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="time-elapsed">--:--</div>
                    <div class="stat-label">Elapsed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="time-remaining">--:--</div>
                    <div class="stat-label">Remaining</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Temperatures</h2>
            <div class="temp-display">
                <div class="temp-item">
                    <div class="current" id="nozzle-temp">--</div>
                    <div class="target">Target: <span id="nozzle-target">--</span></div>
                    <div class="label">Nozzle</div>
                </div>
                <div class="temp-item">
                    <div class="current" id="bed-temp">--</div>
                    <div class="target">Target: <span id="bed-target">--</span></div>
                    <div class="label">Bed</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Camera Feed</h2>
            <div id="camera-feed">Camera not available</div>
        </div>

        <div class="card">
            <h2>Alerts</h2>
            <div class="alert-list" id="alert-list">
                <div class="no-alerts">No alerts</div>
            </div>
        </div>
    </div>

    <script>
        const ws = new WebSocket('ws://' + window.location.host + '/ws');
        const connectionStatus = document.getElementById('connection-status');
        const statusText = document.getElementById('status-text');

        ws.onopen = function() {
            connectionStatus.classList.add('connected');
            statusText.textContent = 'Connected';
        };

        ws.onclose = function() {
            connectionStatus.classList.remove('connected');
            statusText.textContent = 'Disconnected';
        };

        ws.onmessage = function(event) {
            const message = JSON.parse(event.data);
            if (message.type === 'state') {
                updateDashboard(message.data);
            }
        };

        function updateDashboard(state) {
            // Update progress
            if (state.progress) {
                const p = state.progress;
                document.getElementById('print-status').textContent = p.file_name + ' - ' + p.status;
                document.getElementById('progress-fill').style.width = p.progress_percent + '%';
                document.getElementById('progress-percent').textContent = p.progress_percent.toFixed(1) + '%';
                document.getElementById('layer-info').textContent = p.layer_current + '/' + p.layer_total;
                document.getElementById('time-elapsed').textContent = formatTime(p.time_elapsed);
                document.getElementById('time-remaining').textContent = formatTime(p.time_remaining);
            }

            // Update temperatures
            if (state.temperatures && state.temperatures.length > 0) {
                const temp = state.temperatures[state.temperatures.length - 1];
                document.getElementById('nozzle-temp').textContent = temp.nozzle.current.toFixed(0) + String.fromCharCode(176);
                document.getElementById('nozzle-target').textContent = temp.nozzle.target + String.fromCharCode(176);
                document.getElementById('bed-temp').textContent = temp.bed.current.toFixed(0) + String.fromCharCode(176);
                document.getElementById('bed-target').textContent = temp.bed.target + String.fromCharCode(176);
            }

            // Update alerts using safe DOM methods
            const alertList = document.getElementById('alert-list');
            // Clear existing content safely
            while (alertList.firstChild) {
                alertList.removeChild(alertList.firstChild);
            }

            if (state.alerts && state.alerts.length > 0) {
                state.alerts.forEach(function(a) {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert-item ' + a.severity;

                    const msgDiv = document.createElement('div');
                    msgDiv.textContent = a.message;
                    alertDiv.appendChild(msgDiv);

                    const timeDiv = document.createElement('div');
                    timeDiv.className = 'time';
                    timeDiv.textContent = new Date(a.timestamp).toLocaleTimeString();
                    alertDiv.appendChild(timeDiv);

                    alertList.appendChild(alertDiv);
                });
            } else {
                const noAlerts = document.createElement('div');
                noAlerts.className = 'no-alerts';
                noAlerts.textContent = 'No alerts';
                alertList.appendChild(noAlerts);
            }
        }

        function formatTime(seconds) {
            if (seconds == null) return '--:--';
            const h = Math.floor(seconds / 3600);
            const m = Math.floor((seconds % 3600) / 60);
            const s = seconds % 60;
            if (h > 0) {
                return h + ':' + m.toString().padStart(2, '0') + ':' + s.toString().padStart(2, '0');
            }
            return m + ':' + s.toString().padStart(2, '0');
        }

        // Ping to keep connection alive
        setInterval(function() {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'ping'}));
            }
        }, 30000);
    </script>
</body>
</html>"""


def create_dashboard(
    host: str = "0.0.0.0",
    port: int = 9880,
    enable_notifications: bool = True,
) -> Dashboard:
    """
    Create a dashboard instance.

    Args:
        host: Host to bind to
        port: Port to bind to
        enable_notifications: Enable push notifications

    Returns:
        Dashboard instance
    """
    config = DashboardConfig(
        host=host,
        port=port,
        enable_notifications=enable_notifications,
    )
    return Dashboard(config)
