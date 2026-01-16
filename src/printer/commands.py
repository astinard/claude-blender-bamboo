"""
Bamboo Labs printer commands.

Provides high-level commands for controlling the printer:
- Start/stop/pause prints
- Temperature control
- Speed adjustments
- Light control
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

try:
    from bambulabs_api import Printer as BambuPrinter
    BAMBULABS_API_AVAILABLE = True
except ImportError:
    BAMBULABS_API_AVAILABLE = False
    BambuPrinter = None

from .connection import BambooConnection, PrinterState


class SpeedLevel(Enum):
    """Print speed levels."""
    SILENT = 1
    NORMAL = 2
    SPORT = 3
    LUDICROUS = 4


class LightMode(Enum):
    """Chamber light modes."""
    OFF = "off"
    ON = "on"
    FLASHING = "flashing"


@dataclass
class PrintResult:
    """Result of a print command."""
    success: bool
    message: str
    data: Optional[Dict] = None


class PrinterCommands:
    """
    High-level command interface for Bamboo Labs printers.
    """

    def __init__(self, connection: BambooConnection):
        """
        Initialize commands with a printer connection.

        Args:
            connection: Active printer connection
        """
        self.conn = connection
        self._sequence_id = 0

    def _next_sequence_id(self) -> str:
        """Get next sequence ID for commands."""
        self._sequence_id += 1
        return str(self._sequence_id)

    def _send_command(self, command: Dict) -> PrintResult:
        """
        Send a command to the printer.

        Args:
            command: Command dictionary

        Returns:
            PrintResult with success status
        """
        if self.conn.use_mock:
            return PrintResult(
                success=True,
                message="Mock command sent",
                data=command
            )

        if not self.conn.is_connected:
            return PrintResult(
                success=False,
                message="Not connected to printer"
            )

        try:
            if BAMBULABS_API_AVAILABLE and hasattr(self.conn._client, 'send_command'):
                self.conn._client.send_command(command)
                return PrintResult(success=True, message="Command sent")

            # Raw MQTT
            if hasattr(self.conn, '_client') and self.conn._client:
                topic = f"device/{self.conn.serial}/request"
                payload = json.dumps(command)
                self.conn._client.publish(topic, payload)
                return PrintResult(success=True, message="Command sent via MQTT")

            return PrintResult(
                success=False,
                message="No valid client to send command"
            )

        except Exception as e:
            return PrintResult(
                success=False,
                message=f"Command failed: {str(e)}"
            )

    def start_print(self, filename: str, plate_number: int = 1) -> PrintResult:
        """
        Start a print job.

        Args:
            filename: Name of the file to print (must already be on printer/SD)
            plate_number: AMS plate number (1-4)

        Returns:
            PrintResult
        """
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "project_file",
                "param": f"Metadata/plate_{plate_number}.gcode",
                "project_id": "0",
                "profile_id": "0",
                "task_id": "0",
                "subtask_id": "0",
                "subtask_name": filename,
            }
        }
        return self._send_command(command)

    def pause_print(self) -> PrintResult:
        """Pause the current print."""
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "pause"
            }
        }
        return self._send_command(command)

    def resume_print(self) -> PrintResult:
        """Resume a paused print."""
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "resume"
            }
        }
        return self._send_command(command)

    def stop_print(self) -> PrintResult:
        """Stop/cancel the current print."""
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "stop"
            }
        }
        return self._send_command(command)

    def set_bed_temperature(self, temp: int) -> PrintResult:
        """
        Set bed temperature.

        Args:
            temp: Target temperature in Celsius (0 to turn off)
        """
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "gcode_line",
                "param": f"M140 S{temp}"
            }
        }
        return self._send_command(command)

    def set_nozzle_temperature(self, temp: int) -> PrintResult:
        """
        Set nozzle temperature.

        Args:
            temp: Target temperature in Celsius (0 to turn off)
        """
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "gcode_line",
                "param": f"M104 S{temp}"
            }
        }
        return self._send_command(command)

    def send_gcode(self, gcode: str) -> PrintResult:
        """
        Send raw G-code command.

        Args:
            gcode: G-code line to execute
        """
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "gcode_line",
                "param": gcode
            }
        }
        return self._send_command(command)

    def home_axes(self, x: bool = True, y: bool = True, z: bool = True) -> PrintResult:
        """
        Home specified axes.

        Args:
            x: Home X axis
            y: Home Y axis
            z: Home Z axis
        """
        axes = ""
        if x:
            axes += "X"
        if y:
            axes += "Y"
        if z:
            axes += "Z"

        if not axes:
            axes = ""  # Home all if none specified

        return self.send_gcode(f"G28 {axes}".strip())

    def set_speed_level(self, level: SpeedLevel) -> PrintResult:
        """
        Set print speed level.

        Args:
            level: SpeedLevel enum value
        """
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "print_speed",
                "param": str(level.value)
            }
        }
        return self._send_command(command)

    def set_chamber_light(self, mode: LightMode) -> PrintResult:
        """
        Control chamber light.

        Args:
            mode: LightMode enum value
        """
        command = {
            "system": {
                "sequence_id": self._next_sequence_id(),
                "command": "ledctrl",
                "led_node": "chamber_light",
                "led_mode": mode.value,
                "led_on_time": 500,
                "led_off_time": 500,
                "loop_times": 0,
                "interval_time": 0
            }
        }
        return self._send_command(command)

    def set_part_fan(self, speed: int) -> PrintResult:
        """
        Set part cooling fan speed.

        Args:
            speed: Fan speed 0-255 (0 = off, 255 = full)
        """
        speed = max(0, min(255, speed))
        return self.send_gcode(f"M106 S{speed}")

    def turn_off_fans(self) -> PrintResult:
        """Turn off all fans."""
        return self.send_gcode("M107")

    def move_to(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        speed: int = 3000
    ) -> PrintResult:
        """
        Move print head to specified position.

        Args:
            x: X position (mm)
            y: Y position (mm)
            z: Z position (mm)
            speed: Movement speed (mm/min)
        """
        parts = ["G1"]

        if x is not None:
            parts.append(f"X{x}")
        if y is not None:
            parts.append(f"Y{y}")
        if z is not None:
            parts.append(f"Z{z}")

        parts.append(f"F{speed}")

        return self.send_gcode(" ".join(parts))

    def emergency_stop(self) -> PrintResult:
        """Emergency stop - immediately halt all motion."""
        return self.send_gcode("M112")

    def get_printer_info(self) -> PrintResult:
        """Request printer information."""
        command = {
            "info": {
                "sequence_id": self._next_sequence_id(),
                "command": "get_version"
            }
        }
        return self._send_command(command)

    def calibrate_bed(self) -> PrintResult:
        """Start bed leveling calibration."""
        command = {
            "print": {
                "sequence_id": self._next_sequence_id(),
                "command": "calibration"
            }
        }
        return self._send_command(command)

    def is_ready_to_print(self) -> bool:
        """Check if printer is ready to start a new print."""
        status = self.conn.status
        return status.state in (PrinterState.IDLE, PrinterState.FINISHED)

    def wait_for_idle(self, timeout: float = 300, poll_interval: float = 5) -> bool:
        """
        Wait for printer to become idle.

        Args:
            timeout: Maximum wait time in seconds
            poll_interval: Time between status checks

        Returns:
            True if printer became idle, False if timeout
        """
        import time
        start = time.time()

        while time.time() - start < timeout:
            self.conn.refresh_status()
            if self.conn.status.state == PrinterState.IDLE:
                return True
            time.sleep(poll_interval)

        return False
