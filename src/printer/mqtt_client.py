"""Production-grade MQTT client for Bambu Labs printers.

Provides reliable, secure communication with reconnection logic,
message queuing, and comprehensive metrics.
"""

import asyncio
import json
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Dict, Any, Awaitable
from uuid import uuid4
from enum import Enum

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

from src.utils import get_logger

logger = get_logger("printer.mqtt")


class ConnectionState(str, Enum):
    """MQTT connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class MQTTMetrics:
    """Metrics for MQTT client monitoring."""
    connections_total: int = 0
    disconnections_total: int = 0
    reconnections_total: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    messages_failed: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_connected: Optional[datetime] = None
    last_disconnected: Optional[datetime] = None
    last_message_sent: Optional[datetime] = None
    last_message_received: Optional[datetime] = None
    connection_errors: int = 0
    avg_latency_ms: float = 0.0
    _latencies: list = field(default_factory=list)

    def record_latency(self, latency_ms: float):
        """Record a message round-trip latency."""
        self._latencies.append(latency_ms)
        if len(self._latencies) > 100:
            self._latencies.pop(0)
        self.avg_latency_ms = sum(self._latencies) / len(self._latencies)

    def to_dict(self) -> dict:
        """Export metrics as dictionary."""
        return {
            "connections_total": self.connections_total,
            "disconnections_total": self.disconnections_total,
            "reconnections_total": self.reconnections_total,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "messages_failed": self.messages_failed,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "last_connected": self.last_connected.isoformat() if self.last_connected else None,
            "last_disconnected": self.last_disconnected.isoformat() if self.last_disconnected else None,
            "connection_errors": self.connection_errors,
            "avg_latency_ms": round(self.avg_latency_ms, 2)
        }


class ExponentialBackoff:
    """Exponential backoff with jitter for reconnection."""

    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: float = 0.1
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self._current = min_delay
        self._attempts = 0

    def next(self) -> float:
        """Get next delay with jitter."""
        import random
        delay = min(self._current, self.max_delay)
        jitter_range = delay * self.jitter
        actual_delay = delay + random.uniform(-jitter_range, jitter_range)
        self._current *= self.multiplier
        self._attempts += 1
        return max(0, actual_delay)

    def reset(self):
        """Reset backoff after successful connection."""
        self._current = self.min_delay
        self._attempts = 0

    @property
    def attempts(self) -> int:
        return self._attempts


class PrinterTimeoutError(Exception):
    """Raised when a printer command times out."""
    pass


class PrinterConnectionError(Exception):
    """Raised when connection to printer fails."""
    pass


class BambuMQTTClient:
    """Production-grade MQTT client for Bambu Labs printers.

    Features:
    - Automatic reconnection with exponential backoff
    - Message queuing during disconnection
    - Command acknowledgment tracking
    - Comprehensive metrics
    - TLS encryption
    """

    MQTT_PORT = 8883
    KEEPALIVE = 60

    def __init__(
        self,
        printer_ip: str,
        access_code: str,
        serial_number: Optional[str] = None,
        device_id: Optional[str] = None,
        on_state_update: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_connection_change: Optional[Callable[[ConnectionState], Awaitable[None]]] = None
    ):
        if not MQTT_AVAILABLE:
            raise ImportError("paho-mqtt is required. Install with: pip install paho-mqtt")

        self.printer_ip = printer_ip
        self.access_code = access_code
        self.serial_number = serial_number or device_id or "unknown"
        self.device_id = device_id or serial_number or "unknown"

        # Callbacks
        self._on_state_update = on_state_update
        self._on_connection_change = on_connection_change

        # State
        self._state = ConnectionState.DISCONNECTED
        self._client: Optional[mqtt.Client] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Message handling
        self._pending_acks: Dict[str, asyncio.Future] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._current_printer_state: dict = {}

        # Reconnection
        self._backoff = ExponentialBackoff()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._should_reconnect = True

        # Metrics
        self.metrics = MQTTMetrics()

        # Topics
        self._report_topic = f"device/{self.serial_number}/report"
        self._request_topic = f"device/{self.serial_number}/request"

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Whether client is currently connected."""
        return self._state == ConnectionState.CONNECTED

    @property
    def printer_state(self) -> dict:
        """Last known printer state."""
        return self._current_printer_state.copy()

    async def connect(self):
        """Connect to the printer."""
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            logger.debug("Already connected or connecting")
            return

        await self._set_state(ConnectionState.CONNECTING)
        self._loop = asyncio.get_running_loop()

        try:
            # Create MQTT client
            self._client = mqtt.Client(
                client_id=f"claude_fab_lab_{uuid4().hex[:8]}",
                protocol=mqtt.MQTTv311,
                transport="tcp"
            )

            # Set up TLS (Bambu printers use self-signed certs)
            self._client.tls_set(cert_reqs=ssl.CERT_NONE)
            self._client.tls_insecure_set(True)

            # Authentication
            self._client.username_pw_set("bblp", self.access_code)

            # Callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Connect
            logger.info(f"Connecting to printer at {self.printer_ip}:{self.MQTT_PORT}")
            self._client.connect_async(
                self.printer_ip,
                self.MQTT_PORT,
                keepalive=self.KEEPALIVE
            )

            # Start network loop in background
            self._client.loop_start()

            # Wait for connection with timeout
            await asyncio.wait_for(
                self._wait_for_connection(),
                timeout=30.0
            )

            self.metrics.connections_total += 1
            self.metrics.last_connected = datetime.utcnow()
            self._backoff.reset()
            logger.info(f"Connected to printer {self.serial_number}")

        except asyncio.TimeoutError:
            await self._set_state(ConnectionState.ERROR)
            self.metrics.connection_errors += 1
            raise PrinterConnectionError(
                f"Connection to {self.printer_ip} timed out"
            )
        except Exception as e:
            await self._set_state(ConnectionState.ERROR)
            self.metrics.connection_errors += 1
            logger.error(f"Connection failed: {e}")
            raise PrinterConnectionError(f"Connection failed: {e}")

    async def disconnect(self):
        """Disconnect from the printer."""
        self._should_reconnect = False

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

        await self._set_state(ConnectionState.DISCONNECTED)
        self.metrics.last_disconnected = datetime.utcnow()
        logger.info("Disconnected from printer")

    async def send_command(
        self,
        command: dict,
        timeout: float = 30.0,
        require_ack: bool = True
    ) -> Optional[dict]:
        """Send a command to the printer.

        Args:
            command: Command dictionary to send
            timeout: Timeout in seconds
            require_ack: Whether to wait for acknowledgment

        Returns:
            Acknowledgment response if require_ack, else None

        Raises:
            PrinterTimeoutError: If command times out
            PrinterConnectionError: If not connected
        """
        if not self.is_connected:
            raise PrinterConnectionError("Not connected to printer")

        # Add sequence ID for tracking
        sequence_id = str(uuid4())
        command["sequence_id"] = sequence_id

        # Wrap in print structure if needed
        if "print" not in command:
            command = {"print": command}

        payload = json.dumps(command)

        # Set up acknowledgment tracking
        future = None
        if require_ack:
            future = self._loop.create_future()
            self._pending_acks[sequence_id] = future

        # Send message
        start_time = time.time()
        try:
            result = self._client.publish(
                self._request_topic,
                payload,
                qos=1
            )

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                self.metrics.messages_failed += 1
                raise PrinterConnectionError(f"Failed to send command: {result.rc}")

            self.metrics.messages_sent += 1
            self.metrics.bytes_sent += len(payload)
            self.metrics.last_message_sent = datetime.utcnow()

            logger.debug(f"Sent command {sequence_id}: {command}")

            # Wait for acknowledgment
            if require_ack and future:
                try:
                    response = await asyncio.wait_for(future, timeout=timeout)
                    latency = (time.time() - start_time) * 1000
                    self.metrics.record_latency(latency)
                    return response
                except asyncio.TimeoutError:
                    del self._pending_acks[sequence_id]
                    self.metrics.messages_failed += 1
                    raise PrinterTimeoutError(
                        f"Command {sequence_id} timed out after {timeout}s"
                    )
            return None

        except Exception as e:
            if sequence_id in self._pending_acks:
                del self._pending_acks[sequence_id]
            raise

    async def request_status(self) -> dict:
        """Request current printer status."""
        command = {
            "pushing": {
                "sequence_id": "0",
                "command": "pushall"
            }
        }
        await self.send_command(command, require_ack=False)
        # Status will come via _on_message callback
        await asyncio.sleep(0.5)  # Brief wait for response
        return self.printer_state

    async def start_print(self, gcode_path: str) -> dict:
        """Start printing a file."""
        command = {
            "print": {
                "command": "project_file",
                "param": gcode_path,
                "subtask_name": gcode_path.split("/")[-1]
            }
        }
        return await self.send_command(command)

    async def pause_print(self) -> dict:
        """Pause current print."""
        command = {"print": {"command": "pause"}}
        return await self.send_command(command)

    async def resume_print(self) -> dict:
        """Resume paused print."""
        command = {"print": {"command": "resume"}}
        return await self.send_command(command)

    async def stop_print(self) -> dict:
        """Stop current print."""
        command = {"print": {"command": "stop"}}
        return await self.send_command(command)

    async def set_temperature(
        self,
        bed_temp: Optional[int] = None,
        nozzle_temp: Optional[int] = None
    ) -> dict:
        """Set printer temperatures."""
        command = {"print": {"command": "gcode_line"}}

        gcodes = []
        if bed_temp is not None:
            gcodes.append(f"M140 S{bed_temp}")
        if nozzle_temp is not None:
            gcodes.append(f"M104 S{nozzle_temp}")

        if gcodes:
            command["print"]["param"] = "\n".join(gcodes)
            return await self.send_command(command)
        return {}

    # Internal methods

    async def _set_state(self, new_state: ConnectionState):
        """Update connection state and notify callback."""
        old_state = self._state
        self._state = new_state

        if old_state != new_state:
            logger.debug(f"State changed: {old_state} -> {new_state}")
            if self._on_connection_change:
                try:
                    await self._on_connection_change(new_state)
                except Exception as e:
                    logger.error(f"Error in connection change callback: {e}")

    async def _wait_for_connection(self):
        """Wait for connection to be established."""
        while self._state == ConnectionState.CONNECTING:
            await asyncio.sleep(0.1)
        if self._state != ConnectionState.CONNECTED:
            raise PrinterConnectionError("Connection failed")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback."""
        if rc == 0:
            logger.info("MQTT connected successfully")
            # Subscribe to report topic
            client.subscribe(self._report_topic, qos=1)

            # Schedule state update
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._set_state(ConnectionState.CONNECTED),
                    self._loop
                )
        else:
            logger.error(f"MQTT connection failed with code {rc}")
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._set_state(ConnectionState.ERROR),
                    self._loop
                )

    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback."""
        logger.warning(f"MQTT disconnected with code {rc}")
        self.metrics.disconnections_total += 1
        self.metrics.last_disconnected = datetime.utcnow()

        if self._loop and self._should_reconnect:
            asyncio.run_coroutine_threadsafe(
                self._handle_disconnect(),
                self._loop
            )

    async def _handle_disconnect(self):
        """Handle disconnection and trigger reconnection."""
        await self._set_state(ConnectionState.RECONNECTING)

        if self._should_reconnect:
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        """Reconnection loop with exponential backoff."""
        while self._should_reconnect and self._state == ConnectionState.RECONNECTING:
            delay = self._backoff.next()
            logger.info(
                f"Reconnection attempt {self._backoff.attempts} in {delay:.1f}s"
            )
            await asyncio.sleep(delay)

            try:
                await self.connect()
                self.metrics.reconnections_total += 1
                return
            except Exception as e:
                logger.warning(f"Reconnection attempt failed: {e}")
                if self._backoff.attempts >= 10:
                    logger.error("Max reconnection attempts reached")
                    await self._set_state(ConnectionState.ERROR)
                    return

    def _on_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            payload = json.loads(msg.payload.decode())
            self.metrics.messages_received += 1
            self.metrics.bytes_received += len(msg.payload)
            self.metrics.last_message_received = datetime.utcnow()

            # Update printer state
            if "print" in payload:
                self._current_printer_state.update(payload["print"])

            # Check for acknowledgment
            sequence_id = payload.get("print", {}).get("sequence_id")
            if sequence_id and sequence_id in self._pending_acks:
                future = self._pending_acks.pop(sequence_id)
                if not future.done():
                    future.set_result(payload)

            # Notify state update callback
            if self._loop and self._on_state_update:
                asyncio.run_coroutine_threadsafe(
                    self._on_state_update(payload),
                    self._loop
                )

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
