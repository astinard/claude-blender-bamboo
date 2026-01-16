"""
Bamboo Labs printer connection module.

Provides MQTT-based communication with Bamboo Labs printers.
Supports both real printers and mock connections for testing.
"""

import json
import ssl
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Any
import threading

try:
    from bambulabs_api import Printer as BambuPrinter
    BAMBULABS_API_AVAILABLE = True
except ImportError:
    BAMBULABS_API_AVAILABLE = False
    BambuPrinter = None

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None


class PrinterState(Enum):
    """Printer status states."""
    UNKNOWN = "unknown"
    IDLE = "idle"
    PRINTING = "printing"
    PAUSED = "paused"
    ERROR = "error"
    OFFLINE = "offline"
    PREPARING = "preparing"
    FINISHED = "finished"


@dataclass
class PrinterStatus:
    """Current status of the printer."""
    state: PrinterState = PrinterState.UNKNOWN
    progress: float = 0.0  # 0-100
    remaining_time: int = 0  # seconds
    bed_temp: float = 0.0
    bed_temp_target: float = 0.0
    nozzle_temp: float = 0.0
    nozzle_temp_target: float = 0.0
    current_file: str = ""
    layer_current: int = 0
    layer_total: int = 0
    speed_level: int = 100
    fan_speed: int = 0
    error_message: str = ""
    raw_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "state": self.state.value,
            "progress": self.progress,
            "remaining_time": self.remaining_time,
            "bed_temp": self.bed_temp,
            "bed_temp_target": self.bed_temp_target,
            "nozzle_temp": self.nozzle_temp,
            "nozzle_temp_target": self.nozzle_temp_target,
            "current_file": self.current_file,
            "layer_current": self.layer_current,
            "layer_total": self.layer_total,
            "speed_level": self.speed_level,
            "fan_speed": self.fan_speed,
            "error_message": self.error_message,
        }


class BambooConnection:
    """
    Connection manager for Bamboo Labs printers.

    Uses MQTT protocol for real-time communication.
    """

    MQTT_PORT = 8883
    MQTT_USERNAME = "bblp"

    def __init__(
        self,
        ip: str,
        access_code: str,
        serial: str,
        use_mock: bool = False
    ):
        """
        Initialize printer connection.

        Args:
            ip: Printer IP address
            access_code: Printer access code
            serial: Printer serial number
            use_mock: Use mock connection for testing
        """
        self.ip = ip
        self.access_code = access_code
        self.serial = serial
        self.use_mock = use_mock

        self._connected = False
        self._status = PrinterStatus()
        self._callbacks: List[Callable[[PrinterStatus], None]] = []
        self._client: Optional[Any] = None
        self._lock = threading.Lock()

        if use_mock:
            self._setup_mock()
        elif BAMBULABS_API_AVAILABLE:
            self._setup_bambulabs_api()
        elif MQTT_AVAILABLE:
            self._setup_mqtt()
        else:
            raise RuntimeError(
                "No MQTT library available. Install bambulabs-api or paho-mqtt."
            )

    def _setup_mock(self):
        """Set up mock connection for testing."""
        self._status = PrinterStatus(
            state=PrinterState.IDLE,
            bed_temp=25.0,
            nozzle_temp=25.0
        )

    def _setup_bambulabs_api(self):
        """Set up connection using bambulabs_api package."""
        self._client = BambuPrinter(
            ip=self.ip,
            access_code=self.access_code,
            serial=self.serial
        )

    def _setup_mqtt(self):
        """Set up raw MQTT connection."""
        self._client = mqtt.Client(
            client_id=f"claude-blender-{self.serial[:8]}",
            protocol=mqtt.MQTTv311
        )
        self._client.username_pw_set(self.MQTT_USERNAME, self.access_code)

        # SSL context for secure connection
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self._client.tls_set_context(ssl_context)

        self._client.on_connect = self._on_mqtt_connect
        self._client.on_message = self._on_mqtt_message
        self._client.on_disconnect = self._on_mqtt_disconnect

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connect callback."""
        if rc == 0:
            self._connected = True
            # Subscribe to printer status topic
            topic = f"device/{self.serial}/report"
            client.subscribe(topic)
        else:
            self._connected = False

    def _on_mqtt_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            payload = json.loads(msg.payload.decode())
            self._parse_status(payload)
        except Exception as e:
            print(f"Error parsing MQTT message: {e}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback."""
        self._connected = False

    def _parse_status(self, data: Dict):
        """Parse status data from MQTT message."""
        with self._lock:
            self._status.raw_data = data

            if "print" in data:
                print_data = data["print"]

                # State
                state_str = print_data.get("gcode_state", "").lower()
                state_map = {
                    "idle": PrinterState.IDLE,
                    "running": PrinterState.PRINTING,
                    "pause": PrinterState.PAUSED,
                    "finish": PrinterState.FINISHED,
                    "failed": PrinterState.ERROR,
                    "prepare": PrinterState.PREPARING,
                }
                self._status.state = state_map.get(state_str, PrinterState.UNKNOWN)

                # Progress
                self._status.progress = print_data.get("mc_percent", 0)
                self._status.remaining_time = print_data.get("mc_remaining_time", 0) * 60

                # Temperatures
                self._status.bed_temp = print_data.get("bed_temper", 0)
                self._status.bed_temp_target = print_data.get("bed_target_temper", 0)
                self._status.nozzle_temp = print_data.get("nozzle_temper", 0)
                self._status.nozzle_temp_target = print_data.get("nozzle_target_temper", 0)

                # Layer info
                self._status.layer_current = print_data.get("layer_num", 0)
                self._status.layer_total = print_data.get("total_layer_num", 0)

                # Speed
                self._status.speed_level = print_data.get("spd_lvl", 100)

                # File
                self._status.current_file = print_data.get("gcode_file", "")

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(self._status)
                except Exception as e:
                    print(f"Callback error: {e}")

    def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to the printer.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        if self.use_mock:
            self._connected = True
            return True

        if BAMBULABS_API_AVAILABLE and isinstance(self._client, BambuPrinter):
            try:
                self._client.connect()
                self._connected = True
                return True
            except Exception as e:
                print(f"Connection error: {e}")
                return False

        if MQTT_AVAILABLE and self._client:
            try:
                self._client.connect(self.ip, self.MQTT_PORT, keepalive=60)
                self._client.loop_start()

                # Wait for connection
                start = time.time()
                while not self._connected and time.time() - start < timeout:
                    time.sleep(0.1)

                return self._connected
            except Exception as e:
                print(f"MQTT connection error: {e}")
                return False

        return False

    def disconnect(self):
        """Disconnect from printer."""
        if self.use_mock:
            self._connected = False
            return

        if BAMBULABS_API_AVAILABLE and isinstance(self._client, BambuPrinter):
            try:
                self._client.disconnect()
            except:
                pass

        if MQTT_AVAILABLE and self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except:
                pass

        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to printer."""
        return self._connected

    @property
    def status(self) -> PrinterStatus:
        """Get current printer status."""
        with self._lock:
            return self._status

    def add_status_callback(self, callback: Callable[[PrinterStatus], None]):
        """Add callback for status updates."""
        self._callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[PrinterStatus], None]):
        """Remove status callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def refresh_status(self) -> PrinterStatus:
        """
        Request fresh status from printer.

        Returns:
            Current printer status
        """
        if self.use_mock:
            return self._status

        if BAMBULABS_API_AVAILABLE and isinstance(self._client, BambuPrinter):
            try:
                # Request status push
                self._client.refresh()
                time.sleep(0.5)  # Wait for response
            except:
                pass

        return self._status

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
