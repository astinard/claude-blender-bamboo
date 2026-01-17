"""
Real Bambu Lab Printer Connection.

This module provides direct communication with Bambu Lab printers
via MQTT protocol and FTP file transfer.

Supports:
- X1 Carbon, P1S, P1P, A1, A1 Mini, H2D, H2S
- AMS (Automatic Material System) control
- Real-time status monitoring
- File upload and print job management
- Laser module control (H2D/H2S)

Usage:
    from src.printer.bambu_real import BambuRealPrinter

    printer = BambuRealPrinter(
        ip="192.168.1.100",
        access_code="12345678",
        serial="00M00A000000000"
    )
    printer.connect()
    printer.upload_file("model.3mf")
    printer.start_print("model.3mf")
"""

import json
import ssl
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from ftplib import FTP_TLS
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

import paho.mqtt.client as mqtt


class PrinterState(Enum):
    """Printer state enumeration."""
    OFFLINE = "offline"
    IDLE = "idle"
    PREPARING = "preparing"
    PRINTING = "printing"
    PAUSED = "paused"
    FINISHED = "finished"
    ERROR = "error"
    UNKNOWN = "unknown"


class PrintStage(Enum):
    """Print stage enumeration."""
    IDLE = 0
    PRINTING = 1
    AUTO_BED_LEVELING = 2
    HEATBED_PREHEATING = 3
    SWEEPING_XY_MECH_MODE = 4
    CHANGING_FILAMENT = 5
    M400_PAUSE = 6
    PAUSED_USER = 7
    PAUSED_FILAMENT_RUNOUT = 8
    HEATING_HOTEND = 9
    CALIBRATING_EXTRUSION = 10
    SCANNING_BED_SURFACE = 11
    INSPECTING_FIRST_LAYER = 12
    IDENTIFYING_BUILD_PLATE_TYPE = 13
    CALIBRATING_MICRO_LIDAR = 14
    HOMING_TOOLHEAD = 15
    CLEANING_NOZZLE_TIP = 16
    CHECKING_EXTRUDER_TEMP = 17
    PAUSED_USER_GCODE = 18
    PAUSED_FRONT_COVER_FALLING = 19
    CALIBRATING_LIDAR = 20
    CALIBRATING_EXTRUSION_FLOW = 21
    PAUSED_NOZZLE_TEMP_MALFUNCTION = 22
    PAUSED_HEAT_BED_TEMP_MALFUNCTION = 23


@dataclass
class AMSSlotInfo:
    """Information about a single AMS filament slot."""
    slot_id: int  # 0-3 within AMS unit
    ams_id: int   # AMS unit ID (0-3)
    material: str = ""
    color: str = ""  # Hex color code
    remaining_percent: float = 0.0
    is_loaded: bool = False

    @property
    def global_slot_id(self) -> int:
        """Get global slot ID (0-15 for 4 AMS units)."""
        return self.ams_id * 4 + self.slot_id


@dataclass
class AMSStatus:
    """Status of all AMS units."""
    units: List[List[AMSSlotInfo]] = field(default_factory=list)
    current_slot: int = -1
    humidity: float = 0.0

    def get_slot(self, global_id: int) -> Optional[AMSSlotInfo]:
        """Get slot by global ID."""
        ams_id = global_id // 4
        slot_id = global_id % 4
        if ams_id < len(self.units) and slot_id < len(self.units[ams_id]):
            return self.units[ams_id][slot_id]
        return None

    def get_all_slots(self) -> List[AMSSlotInfo]:
        """Get all slots as flat list."""
        return [slot for unit in self.units for slot in unit]


@dataclass
class PrinterStatus:
    """Complete printer status."""
    state: PrinterState = PrinterState.OFFLINE
    print_stage: PrintStage = PrintStage.IDLE

    # Temperatures
    bed_temp: float = 0.0
    bed_temp_target: float = 0.0
    nozzle_temp: float = 0.0
    nozzle_temp_target: float = 0.0
    chamber_temp: float = 0.0

    # Print progress
    progress: int = 0
    layer_current: int = 0
    layer_total: int = 0
    remaining_time: int = 0  # minutes
    current_file: str = ""
    subtask_name: str = ""

    # Speeds
    print_speed: int = 100  # percentage
    cooling_fan_speed: int = 0
    aux_fan_speed: int = 0
    chamber_fan_speed: int = 0

    # AMS
    ams: AMSStatus = field(default_factory=AMSStatus)

    # Errors
    error_code: int = 0
    error_message: str = ""

    # System
    wifi_signal: int = 0
    light_state: str = "off"

    # Timestamps
    last_update: float = 0.0


@dataclass
class PrintResult:
    """Result of a print operation."""
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class BambuRealPrinter:
    """
    Real Bambu Lab printer connection.

    Communicates via MQTT for control and FTP for file transfer.
    """

    MQTT_PORT = 8883
    FTP_PORT = 990

    def __init__(self, ip: str, access_code: str, serial: str):
        """
        Initialize printer connection.

        Args:
            ip: Printer IP address on local network
            access_code: 8-digit access code from printer screen
            serial: Printer serial number (for MQTT topics)
        """
        self.ip = ip
        self.access_code = access_code
        self.serial = serial

        self._mqtt_client: Optional[mqtt.Client] = None
        self._connected = False
        self._status = PrinterStatus()
        self._callbacks: List[Callable[[PrinterStatus], None]] = []
        self._message_lock = threading.Lock()
        self._request_id = 0

    def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to printer via MQTT.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        try:
            # Create MQTT client
            self._mqtt_client = mqtt.Client(
                client_id=f"claude_fab_lab_{int(time.time())}",
                protocol=mqtt.MQTTv311,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )

            # Configure TLS
            self._mqtt_client.tls_set(
                cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLS
            )
            self._mqtt_client.tls_insecure_set(True)

            # Set credentials
            self._mqtt_client.username_pw_set("bblp", self.access_code)

            # Set callbacks
            self._mqtt_client.on_connect = self._on_connect
            self._mqtt_client.on_message = self._on_message
            self._mqtt_client.on_disconnect = self._on_disconnect

            # Connect
            self._mqtt_client.connect(self.ip, self.MQTT_PORT, keepalive=60)
            self._mqtt_client.loop_start()

            # Wait for connection
            start_time = time.time()
            while not self._connected and time.time() - start_time < timeout:
                time.sleep(0.1)

            if self._connected:
                # Subscribe to printer reports
                topic = f"device/{self.serial}/report"
                self._mqtt_client.subscribe(topic)

                # Request initial status
                self._request_push_all()

            return self._connected

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from printer."""
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()
            self._mqtt_client = None
        self._connected = False
        self._status.state = PrinterState.OFFLINE

    @property
    def is_connected(self) -> bool:
        """Check if connected to printer."""
        return self._connected

    @property
    def status(self) -> PrinterStatus:
        """Get current printer status."""
        return self._status

    def add_status_callback(self, callback: Callable[[PrinterStatus], None]):
        """Add callback for status updates."""
        self._callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[PrinterStatus], None]):
        """Remove status callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    # ==================== File Operations ====================

    def upload_file(self, local_path: str, remote_name: str = None) -> PrintResult:
        """
        Upload file to printer via FTPS.

        Args:
            local_path: Path to local file
            remote_name: Name on printer (defaults to local filename)

        Returns:
            PrintResult with success status
        """
        local_path = Path(local_path)
        if not local_path.exists():
            return PrintResult(False, f"File not found: {local_path}")

        remote_name = remote_name or local_path.name

        try:
            # Connect via FTPS
            ftp = FTP_TLS()
            ftp.connect(self.ip, self.FTP_PORT, timeout=30)
            ftp.login("bblp", self.access_code)
            ftp.prot_p()  # Enable data encryption

            # Upload to cache directory
            file_size = local_path.stat().st_size
            with open(local_path, 'rb') as f:
                ftp.storbinary(f'STOR /cache/{remote_name}', f)

            ftp.quit()

            return PrintResult(
                True,
                f"Uploaded {remote_name} ({file_size / 1024 / 1024:.1f} MB)",
                {"remote_path": f"/cache/{remote_name}", "size": file_size}
            )

        except Exception as e:
            return PrintResult(False, f"Upload failed: {e}")

    def list_files(self) -> PrintResult:
        """List files on printer."""
        try:
            ftp = FTP_TLS()
            ftp.connect(self.ip, self.FTP_PORT, timeout=10)
            ftp.login("bblp", self.access_code)
            ftp.prot_p()

            files = []
            ftp.cwd('/cache')
            ftp.retrlines('LIST', lambda x: files.append(x))

            ftp.quit()

            return PrintResult(True, "File list retrieved", {"files": files})

        except Exception as e:
            return PrintResult(False, f"Failed to list files: {e}")

    def delete_file(self, filename: str) -> PrintResult:
        """Delete file from printer."""
        try:
            ftp = FTP_TLS()
            ftp.connect(self.ip, self.FTP_PORT, timeout=10)
            ftp.login("bblp", self.access_code)
            ftp.prot_p()

            ftp.delete(f'/cache/{filename}')
            ftp.quit()

            return PrintResult(True, f"Deleted {filename}")

        except Exception as e:
            return PrintResult(False, f"Failed to delete: {e}")

    # ==================== Print Control ====================

    def start_print(self, filename: str,
                    plate_number: int = 1,
                    ams_mapping: List[int] = None,
                    use_ams: bool = True,
                    timelapse: bool = False,
                    bed_leveling: bool = True,
                    flow_calibration: bool = False,
                    vibration_calibration: bool = False) -> PrintResult:
        """
        Start printing a file.

        Args:
            filename: Name of file on printer (in /cache/)
            plate_number: Plate number in 3MF file (1-indexed)
            ams_mapping: List mapping filament indices to AMS slots
            use_ams: Whether to use AMS
            timelapse: Enable timelapse recording
            bed_leveling: Enable auto bed leveling
            flow_calibration: Enable flow calibration
            vibration_calibration: Enable vibration calibration

        Returns:
            PrintResult with success status
        """
        if not self._connected:
            return PrintResult(False, "Not connected to printer")

        # Build print command
        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "project_file",
                "param": f"Metadata/plate_{plate_number}.gcode",
                "subtask_name": filename,
                "url": f"file:///cache/{filename}",
                "timelapse": timelapse,
                "bed_leveling": bed_leveling,
                "flow_cali": flow_calibration,
                "vibration_cali": vibration_calibration,
                "layer_inspect": False,
                "use_ams": use_ams,
            }
        }

        # Add AMS mapping if provided
        if ams_mapping:
            cmd["print"]["ams_mapping"] = ams_mapping

        self._send_command(cmd)

        return PrintResult(True, f"Print started: {filename}")

    def pause_print(self) -> PrintResult:
        """Pause current print."""
        if not self._connected:
            return PrintResult(False, "Not connected")

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "pause"
            }
        }
        self._send_command(cmd)
        return PrintResult(True, "Print paused")

    def resume_print(self) -> PrintResult:
        """Resume paused print."""
        if not self._connected:
            return PrintResult(False, "Not connected")

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "resume"
            }
        }
        self._send_command(cmd)
        return PrintResult(True, "Print resumed")

    def stop_print(self) -> PrintResult:
        """Stop current print."""
        if not self._connected:
            return PrintResult(False, "Not connected")

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "stop"
            }
        }
        self._send_command(cmd)
        return PrintResult(True, "Print stopped")

    # ==================== Temperature Control ====================

    def set_bed_temperature(self, temp: int) -> PrintResult:
        """Set bed temperature."""
        if not self._connected:
            return PrintResult(False, "Not connected")

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "gcode_line",
                "param": f"M140 S{temp}"
            }
        }
        self._send_command(cmd)
        return PrintResult(True, f"Bed temperature set to {temp}°C")

    def set_nozzle_temperature(self, temp: int) -> PrintResult:
        """Set nozzle temperature."""
        if not self._connected:
            return PrintResult(False, "Not connected")

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "gcode_line",
                "param": f"M104 S{temp}"
            }
        }
        self._send_command(cmd)
        return PrintResult(True, f"Nozzle temperature set to {temp}°C")

    # ==================== Speed & Fan Control ====================

    def set_print_speed(self, speed_percent: int) -> PrintResult:
        """Set print speed (50-200%)."""
        if not 50 <= speed_percent <= 200:
            return PrintResult(False, "Speed must be 50-200%")

        if not self._connected:
            return PrintResult(False, "Not connected")

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "print_speed",
                "param": str(speed_percent)
            }
        }
        self._send_command(cmd)
        return PrintResult(True, f"Print speed set to {speed_percent}%")

    def set_fan_speed(self, fan: str, speed_percent: int) -> PrintResult:
        """Set fan speed (0-100%)."""
        if not 0 <= speed_percent <= 100:
            return PrintResult(False, "Speed must be 0-100%")

        fan_map = {
            "part": "P1",  # Part cooling fan
            "aux": "P2",   # Auxiliary fan
            "chamber": "P3"  # Chamber fan
        }

        if fan not in fan_map:
            return PrintResult(False, f"Unknown fan: {fan}")

        if not self._connected:
            return PrintResult(False, "Not connected")

        speed_255 = int(speed_percent * 255 / 100)
        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "gcode_line",
                "param": f"M106 {fan_map[fan]} S{speed_255}"
            }
        }
        self._send_command(cmd)
        return PrintResult(True, f"{fan} fan set to {speed_percent}%")

    # ==================== Light Control ====================

    def set_light(self, on: bool) -> PrintResult:
        """Turn chamber light on/off."""
        if not self._connected:
            return PrintResult(False, "Not connected")

        cmd = {
            "system": {
                "sequence_id": str(self._next_request_id()),
                "command": "ledctrl",
                "led_node": "chamber_light",
                "led_mode": "on" if on else "off"
            }
        }
        self._send_command(cmd)
        return PrintResult(True, f"Light {'on' if on else 'off'}")

    # ==================== AMS Control ====================

    def get_ams_status(self) -> AMSStatus:
        """Get current AMS status."""
        return self._status.ams

    def ams_filament_change(self, target_slot: int) -> PrintResult:
        """
        Change to specified AMS slot.

        Args:
            target_slot: Global slot ID (0-15 for 4 AMS units)
        """
        if not self._connected:
            return PrintResult(False, "Not connected")

        ams_id = target_slot // 4
        slot_id = target_slot % 4

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "ams_change_filament",
                "target": target_slot,
                "curr_temp": int(self._status.nozzle_temp),
                "tar_temp": 220  # Default, should be material-specific
            }
        }
        self._send_command(cmd)
        return PrintResult(True, f"Changing to AMS slot {target_slot}")

    # ==================== G-code ====================

    def send_gcode(self, gcode: str) -> PrintResult:
        """Send raw G-code command."""
        if not self._connected:
            return PrintResult(False, "Not connected")

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "gcode_line",
                "param": gcode
            }
        }
        self._send_command(cmd)
        return PrintResult(True, f"Sent: {gcode}")

    # ==================== Calibration ====================

    def run_calibration(self,
                        bed_leveling: bool = True,
                        vibration: bool = False,
                        motor_noise: bool = False) -> PrintResult:
        """Run calibration routines."""
        if not self._connected:
            return PrintResult(False, "Not connected")

        options = []
        if bed_leveling:
            options.append("bed_leveling")
        if vibration:
            options.append("vibration")
        if motor_noise:
            options.append("motor_noise")

        if not options:
            return PrintResult(False, "No calibration options selected")

        cmd = {
            "print": {
                "sequence_id": str(self._next_request_id()),
                "command": "calibration",
                "option": options[0] if len(options) == 1 else options
            }
        }
        self._send_command(cmd)
        return PrintResult(True, f"Calibration started: {', '.join(options)}")

    # ==================== Internal Methods ====================

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback."""
        if reason_code == 0:
            self._connected = True
            self._status.state = PrinterState.IDLE
        else:
            self._connected = False

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """MQTT disconnection callback."""
        self._connected = False
        self._status.state = PrinterState.OFFLINE

    def _on_message(self, client, userdata, message):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(message.payload.decode())
            self._parse_status(payload)

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(self._status)
                except Exception as e:
                    print(f"Callback error: {e}")

        except Exception as e:
            print(f"Message parse error: {e}")

    def _parse_status(self, data: dict):
        """Parse status from MQTT message."""
        with self._message_lock:
            self._status.last_update = time.time()

            if "print" in data:
                p = data["print"]

                # State
                if "gcode_state" in p:
                    state_map = {
                        "IDLE": PrinterState.IDLE,
                        "PREPARE": PrinterState.PREPARING,
                        "RUNNING": PrinterState.PRINTING,
                        "PAUSE": PrinterState.PAUSED,
                        "FINISH": PrinterState.FINISHED,
                        "FAILED": PrinterState.ERROR,
                    }
                    self._status.state = state_map.get(
                        p["gcode_state"], PrinterState.UNKNOWN
                    )

                # Temperatures
                if "bed_temper" in p:
                    self._status.bed_temp = float(p["bed_temper"])
                if "bed_target_temper" in p:
                    self._status.bed_temp_target = float(p["bed_target_temper"])
                if "nozzle_temper" in p:
                    self._status.nozzle_temp = float(p["nozzle_temper"])
                if "nozzle_target_temper" in p:
                    self._status.nozzle_temp_target = float(p["nozzle_target_temper"])
                if "chamber_temper" in p:
                    self._status.chamber_temp = float(p["chamber_temper"])

                # Progress
                if "mc_percent" in p:
                    self._status.progress = int(p["mc_percent"])
                if "layer_num" in p:
                    self._status.layer_current = int(p["layer_num"])
                if "total_layer_num" in p:
                    self._status.layer_total = int(p["total_layer_num"])
                if "mc_remaining_time" in p:
                    self._status.remaining_time = int(p["mc_remaining_time"])
                if "gcode_file" in p:
                    self._status.current_file = p["gcode_file"]
                if "subtask_name" in p:
                    self._status.subtask_name = p["subtask_name"]

                # Fans
                if "cooling_fan_speed" in p:
                    self._status.cooling_fan_speed = int(p["cooling_fan_speed"])
                if "big_fan1_speed" in p:
                    self._status.aux_fan_speed = int(p["big_fan1_speed"])
                if "big_fan2_speed" in p:
                    self._status.chamber_fan_speed = int(p["big_fan2_speed"])

                # Speed
                if "spd_lvl" in p:
                    speed_map = {1: 50, 2: 100, 3: 125, 4: 150}
                    self._status.print_speed = speed_map.get(int(p["spd_lvl"]), 100)

                # Errors
                if "print_error" in p:
                    self._status.error_code = int(p["print_error"])
                if "fail_reason" in p:
                    self._status.error_message = p["fail_reason"]

                # AMS
                if "ams" in p:
                    self._parse_ams_status(p["ams"])

            if "system" in data:
                s = data["system"]
                if "wifi_signal" in s:
                    self._status.wifi_signal = int(s["wifi_signal"])
                if "led_mode" in s:
                    self._status.light_state = s["led_mode"]

    def _parse_ams_status(self, ams_data: dict):
        """Parse AMS status from message."""
        if "ams" not in ams_data:
            return

        units = []
        for ams_unit in ams_data["ams"]:
            ams_id = int(ams_unit.get("id", 0))
            slots = []

            for tray in ams_unit.get("tray", []):
                slot_id = int(tray.get("id", 0))
                slots.append(AMSSlotInfo(
                    slot_id=slot_id,
                    ams_id=ams_id,
                    material=tray.get("tray_type", ""),
                    color=tray.get("tray_color", ""),
                    remaining_percent=float(tray.get("remain", 0)),
                    is_loaded=tray.get("tray_type", "") != ""
                ))

            units.append(slots)

        self._status.ams.units = units

        if "tray_now" in ams_data:
            self._status.ams.current_slot = int(ams_data["tray_now"])
        if "ams_humidity" in ams_data:
            self._status.ams.humidity = float(ams_data["ams_humidity"])

    def _send_command(self, cmd: dict):
        """Send command via MQTT."""
        if not self._mqtt_client or not self._connected:
            return

        topic = f"device/{self.serial}/request"
        payload = json.dumps(cmd)
        self._mqtt_client.publish(topic, payload)

    def _request_push_all(self):
        """Request full status update."""
        cmd = {
            "pushing": {
                "sequence_id": str(self._next_request_id()),
                "command": "pushall"
            }
        }
        self._send_command(cmd)

    def _next_request_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id


def create_real_printer(ip: str, access_code: str, serial: str) -> BambuRealPrinter:
    """Factory function to create a real printer connection."""
    return BambuRealPrinter(ip, access_code, serial)


# Convenience functions for quick testing
def discover_printers() -> List[str]:
    """
    Discover Bambu Lab printers on local network.

    Note: Requires network scanning which may need elevated privileges.
    Returns list of IP addresses.
    """
    # This is a placeholder - real implementation would use
    # mDNS/Bonjour discovery or network scanning
    print("Printer discovery not yet implemented.")
    print("Please manually provide printer IP, access code, and serial number.")
    return []


if __name__ == "__main__":
    # Test connection (requires real printer details)
    import sys

    if len(sys.argv) < 4:
        print("Usage: python bambu_real.py <IP> <ACCESS_CODE> <SERIAL>")
        print("Example: python bambu_real.py 192.168.1.100 12345678 00M00A000000000")
        sys.exit(1)

    ip, access_code, serial = sys.argv[1:4]

    printer = BambuRealPrinter(ip, access_code, serial)

    print(f"Connecting to {ip}...")
    if printer.connect(timeout=10):
        print("Connected!")
        print(f"Status: {printer.status.state.value}")
        print(f"Bed: {printer.status.bed_temp}°C")
        print(f"Nozzle: {printer.status.nozzle_temp}°C")

        # Wait for status updates
        time.sleep(5)

        print(f"\nUpdated status:")
        print(f"Progress: {printer.status.progress}%")

        printer.disconnect()
    else:
        print("Failed to connect")
