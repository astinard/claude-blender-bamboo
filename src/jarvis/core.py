"""
JARVIS Core - Main AI Assistant Interface

The central hub that combines voice, display, and fab lab capabilities
into a cohesive sci-fi experience.
"""

import time
import threading
import re
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from .voice import JarvisVoice, VoiceConfig, SpeechRecognizer
from .display import JarvisDisplay, JARVIS_PRIMARY, JARVIS_ACCENT, JARVIS_SUCCESS, Colors
from .sounds import JarvisSounds, SoundConfig, SoundType


class JarvisState(Enum):
    """Jarvis operational states."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SCANNING = "scanning"
    FABRICATING = "fabricating"
    ERROR = "error"


@dataclass
class FabricationJob:
    """A fabrication job."""
    name: str
    job_type: str  # "print", "laser_cut", "laser_engrave"
    status: str
    progress: float = 0.0
    eta_seconds: float = 0.0
    details: Dict[str, Any] = None


class Jarvis:
    """
    JARVIS - Just A Rather Very Intelligent System

    The main interface for the Fab Lab, combining voice interaction,
    visual displays, and fabrication control.

    Usage:
        jarvis = Jarvis()
        jarvis.boot()
        jarvis.command("scan this object")
        jarvis.command("print it")
    """

    def __init__(
        self,
        voice_enabled: bool = True,
        voice_config: Optional[VoiceConfig] = None,
        sounds_enabled: bool = True,
        sounds_config: Optional[SoundConfig] = None,
    ):
        self.voice = JarvisVoice(voice_config) if voice_enabled else None
        self.sounds = JarvisSounds(sounds_config) if sounds_enabled else None
        self.display = JarvisDisplay()
        self.recognizer = SpeechRecognizer(wake_word="jarvis")

        self.state = JarvisState.INITIALIZING
        self._commands: Dict[str, Callable] = {}
        self._current_job: Optional[FabricationJob] = None

        # Register built-in commands
        self._register_commands()

    def _register_commands(self):
        """Register voice/text commands."""
        self._commands = {
            # Scanning
            r"scan|capture|photograph": self._cmd_scan,
            r"analyze|check|inspect": self._cmd_analyze,

            # Modeling
            r"repair|fix|heal": self._cmd_repair,
            r"scale|resize|make.*(bigger|smaller)": self._cmd_scale,
            r"hollow|shell": self._cmd_hollow,

            # Fabrication
            r"print|fabricate|make": self._cmd_print,
            r"cut|laser.?cut": self._cmd_laser_cut,
            r"engrave|etch": self._cmd_engrave,

            # Control
            r"status|how.*(going|doing)|progress": self._cmd_status,
            r"stop|cancel|abort": self._cmd_stop,
            r"pause|hold": self._cmd_pause,
            r"resume|continue": self._cmd_resume,

            # Info
            r"estimate|cost|how much": self._cmd_estimate,
            r"material|filament": self._cmd_materials,

            # System
            r"help|what can you do": self._cmd_help,
            r"goodbye|bye|shutdown|exit": self._cmd_shutdown,
        }

    def boot(self, skip_animation: bool = False):
        """
        Boot up JARVIS with full sci-fi startup sequence.
        """
        self.display.clear()
        self.display.hide_cursor()

        try:
            if not skip_animation:
                # Power up sound
                if self.sounds:
                    self.sounds.play(SoundType.POWER_UP, block=True)

                # Startup animation
                self.display.animated_text("Initializing JARVIS...", delay=0.02)
                time.sleep(0.3)

            self.display.banner("jarvis")

            if not skip_animation:
                # Boot sound sequence
                if self.sounds:
                    self.sounds.play(SoundType.BOOT, block=True)
                time.sleep(0.3)

            if not skip_animation:
                # System checks
                self.display.subheader("Running System Diagnostics")
                time.sleep(0.2)

                checks = [
                    ("Core Systems", "Online"),
                    ("Voice Module", "Active" if self.voice else "Disabled"),
                    ("Sound Engine", "Active" if self.sounds else "Disabled"),
                    ("Display Engine", "Active"),
                    ("Fabrication Link", "Standing By"),
                    ("Material Database", "Loaded"),
                    ("Neural Network", "Ready"),
                ]

                for label, value in checks:
                    time.sleep(0.15)
                    if self.sounds:
                        self.sounds.click()
                    self.display.status(label, value, "ok")

                time.sleep(0.3)

            # Ready sound
            if self.sounds:
                self.sounds.play(SoundType.READY, block=True)

            # Speak greeting
            if self.voice:
                self.voice.speak_greeting()

            self.state = JarvisState.IDLE

            # Start ambient sound
            if self.sounds:
                self.sounds.start_ambient()

            self.display.header("READY FOR COMMAND")
            self.display.info("Say 'Jarvis' followed by a command, or type below")
            self.display.info("Type 'help' for available commands")
            print()

        finally:
            self.display.show_cursor()

    def say(self, text: str, also_print: bool = True):
        """Speak and optionally print text."""
        if also_print:
            self.display.animated_text(f"JARVIS: {text}", delay=0.01)
        if self.voice:
            self.voice.speak(text)

    def command(self, text: str) -> bool:
        """
        Process a text command.

        Returns True if command was recognized.
        """
        text = text.lower().strip()

        if not text:
            return False

        # Find matching command
        for pattern, handler in self._commands.items():
            if re.search(pattern, text, re.IGNORECASE):
                self.state = JarvisState.PROCESSING
                if self.sounds:
                    self.sounds.confirm()
                if self.voice:
                    self.voice.speak_confirmation()
                try:
                    handler(text)
                except Exception as e:
                    if self.sounds:
                        self.sounds.error()
                    self.say(f"I encountered an error: {str(e)}")
                    self.state = JarvisState.ERROR
                    return False
                self.state = JarvisState.IDLE
                return True

        # Unknown command
        if self.sounds:
            self.sounds.warning()
        self.say("I'm not sure what you mean. Say 'help' for available commands.")
        return False

    def interactive(self):
        """
        Run interactive command loop.
        """
        print(f"\n{JARVIS_PRIMARY}╔══════════════════════════════════════════════════════════╗")
        print(f"║  Type commands below. Type 'quit' to exit.               ║")
        print(f"╚══════════════════════════════════════════════════════════╝{Colors.RESET}\n")

        while True:
            try:
                user_input = input(f"{JARVIS_ACCENT}You:{Colors.RESET} ").strip()

                if user_input.lower() in ("quit", "exit", "bye", "goodbye"):
                    self.shutdown()
                    break

                if user_input:
                    self.command(user_input)
                    print()

            except KeyboardInterrupt:
                print()
                self.shutdown()
                break
            except EOFError:
                break

    def listen_loop(self):
        """
        Start continuous voice listening (requires speech_recognition).
        """
        if not self.recognizer.available:
            self.say("Speech recognition is not available. Please install speech_recognition and pyaudio.")
            return

        def handle_command(cmd: str):
            self.command(cmd)

        self.recognizer.on_command(handle_command)
        self.say("Voice control activated. Say 'Jarvis' followed by a command.")
        self.recognizer.start_continuous()

    # ═══════════════════════════════════════════════════════════════════
    # COMMAND HANDLERS
    # ═══════════════════════════════════════════════════════════════════

    def _cmd_scan(self, text: str):
        """Handle scan command."""
        self.state = JarvisState.SCANNING
        self.display.header("INITIATING SCAN")

        # Scan start sound
        if self.sounds:
            self.sounds.play(SoundType.SCAN_START)

        self.say("Preparing LiDAR scanner. Please position the object.")
        time.sleep(1)

        self.display.banner("scan")
        self.say("Scanning in progress. Hold steady.")

        # Play scan loop sound during animation
        if self.sounds:
            self.sounds.play(SoundType.SCAN_LOOP)

        self.display.scanning_animation(duration=3.0)

        # Scan complete sound
        if self.sounds:
            self.sounds.play(SoundType.SCAN_COMPLETE, block=True)

        self.say("Scan complete. Processing mesh data.")

        # Simulated results
        self.display.data_table({
            "Vertices": "847,293",
            "Faces": "1,694,582",
            "Volume": "42.7 cm³",
            "Dimensions": "75 × 150 × 8 mm",
            "Watertight": "Yes",
        }, title="SCAN RESULTS")

        if self.sounds:
            self.sounds.success()
        self.say("Object captured successfully. Mesh is clean and printable.")

    def _cmd_analyze(self, text: str):
        """Handle analyze command."""
        self.display.header("ANALYZING MESH")

        if self.sounds:
            self.sounds.processing()

        self.display.spinner_start("Running mesh analysis")
        time.sleep(2)
        self.display.spinner_stop("Analysis complete")

        self.display.data_table({
            "Topology": "Manifold",
            "Watertight": "Yes",
            "Self-intersections": "None",
            "Degenerate faces": "0",
            "Printability": "Excellent",
        }, title="MESH ANALYSIS")

        if self.sounds:
            self.sounds.success()
        self.say("The mesh is in excellent condition. Ready for fabrication.")

    def _cmd_repair(self, text: str):
        """Handle repair command."""
        self.display.header("MESH REPAIR")

        self.say("Analyzing mesh for defects.")

        if self.sounds:
            self.sounds.processing()

        self.display.spinner_start("Scanning for issues")
        time.sleep(1.5)
        self.display.spinner_stop()

        if self.sounds:
            self.sounds.warning()
        self.display.status("Holes found", "3", "warning")
        self.display.status("Non-manifold edges", "12", "warning")

        self.say("Found 3 holes and 12 non-manifold edges. Initiating repair.")

        for i in range(5):
            self.display.progress_bar((i + 1) / 5, label="Repairing")
            if self.sounds:
                self.sounds.click()
            time.sleep(0.3)
        print()

        if self.sounds:
            self.sounds.success()
        self.display.success("Mesh repaired successfully")
        self.say("All issues have been resolved. Mesh is now printable.")

    def _cmd_scale(self, text: str):
        """Handle scale command."""
        # Parse scale factor from command
        factor = 1.0
        if "bigger" in text or "larger" in text:
            factor = 1.5
        elif "smaller" in text:
            factor = 0.75

        # Look for specific number
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:x|times|percent|%)', text)
        if match:
            num = float(match.group(1))
            if "percent" in text or "%" in text:
                factor = num / 100
            else:
                factor = num

        self.display.header("SCALING OBJECT")
        self.say(f"Scaling object by factor of {factor:.1f}x")

        self.display.spinner_start("Applying transformation")
        time.sleep(1)
        self.display.spinner_stop("Scale applied")

        self.display.data_table({
            "Scale Factor": f"{factor:.2f}x",
            "New Volume": f"{42.7 * factor**3:.1f} cm³",
            "New Dimensions": f"{int(75*factor)} × {int(150*factor)} × {int(8*factor)} mm",
        }, title="SCALED OBJECT")

        self.say("Object scaled successfully.")

    def _cmd_hollow(self, text: str):
        """Handle hollow command."""
        self.display.header("HOLLOWING OBJECT")
        self.say("Creating hollow shell with 2 millimeter wall thickness.")

        for i in range(10):
            self.display.progress_bar((i + 1) / 10, label="Hollowing")
            time.sleep(0.2)
        print()

        self.display.success("Hollowing complete")
        self.display.data_table({
            "Wall Thickness": "2.0 mm",
            "Material Saved": "68%",
            "New Volume": "13.7 cm³",
            "Estimated Weight": "17.0 g",
        })

        self.say("Object hollowed. You'll save 68 percent on material.")

    def _cmd_print(self, text: str):
        """Handle print command."""
        self.state = JarvisState.FABRICATING
        self.display.header("INITIATING 3D PRINT")

        # Print start sound
        if self.sounds:
            self.sounds.play(SoundType.PRINT_START)

        self.say("Preparing fabrication sequence.")

        # Simulated print preview
        self.display.data_table({
            "Material": "PLA (White)",
            "Layer Height": "0.2 mm",
            "Infill": "20%",
            "Estimated Time": "2h 45m",
            "Filament Usage": "42.3 g",
            "Cost": "$1.06",
        }, title="PRINT PREVIEW")

        time.sleep(1)
        self.say("Heating bed to 60 degrees. Nozzle to 210 degrees.")

        # Temperature animation with sounds
        for temp in range(25, 61, 5):
            self.display.progress_bar(temp / 60, label=f"Bed: {temp}°C")
            time.sleep(0.1)
        print()
        if self.sounds:
            self.sounds.click()
        self.display.success("Bed temperature reached")

        for temp in range(25, 211, 20):
            self.display.progress_bar(temp / 210, label=f"Nozzle: {temp}°C")
            time.sleep(0.1)
        print()
        if self.sounds:
            self.sounds.click()
        self.display.success("Nozzle temperature reached")

        self.say("Temperatures stable. Beginning fabrication.")

        # Print simulation with layer sounds
        if self.sounds:
            self.sounds.processing()
        self.display.fabrication_animation(layers=15, duration=5.0)

        # Print complete sound
        if self.sounds:
            self.sounds.play(SoundType.PRINT_COMPLETE, block=True)

        self.display.banner("printer")
        self.say("Fabrication complete. Your object is ready.")

    def _cmd_laser_cut(self, text: str):
        """Handle laser cut command."""
        self.state = JarvisState.FABRICATING
        self.display.header("LASER CUTTING")

        self.say("Preparing laser cutter. Please ensure safety enclosure is closed.")

        self.display.data_table({
            "Material": "Plywood 3mm",
            "Power": "80%",
            "Speed": "10 mm/s",
            "Passes": "1",
            "Estimated Time": "3m 24s",
        }, title="CUT PARAMETERS")

        time.sleep(1)
        self.say("Laser armed. Cutting in progress.")

        self.display.wave_animation(duration=3.0, message="Cutting")

        self.display.success("Laser cutting complete")
        self.say("Cutting operation finished. Allow material to cool before handling.")

    def _cmd_engrave(self, text: str):
        """Handle engrave command."""
        self.display.header("LASER ENGRAVING")

        self.say("Preparing laser engraver.")

        self.display.data_table({
            "Material": "Plywood 3mm",
            "Power": "30%",
            "Speed": "100 mm/s",
            "Line Spacing": "0.1 mm",
            "Estimated Time": "8m 15s",
        }, title="ENGRAVE PARAMETERS")

        self.say("Engraving in progress.")

        self.display.wave_animation(duration=4.0, message="Engraving")

        self.display.success("Engraving complete")
        self.say("Engraving finished. Beautiful detail achieved.")

    def _cmd_status(self, text: str):
        """Handle status command."""
        self.display.header("SYSTEM STATUS")

        if self._current_job:
            self.display.data_table({
                "Job": self._current_job.name,
                "Type": self._current_job.job_type,
                "Progress": f"{self._current_job.progress * 100:.1f}%",
                "ETA": f"{self._current_job.eta_seconds / 60:.0f} min",
            }, title="CURRENT JOB")
        else:
            self.display.status("Current Job", "None", "dim")

        self.display.status("Printer", "Idle", "ok")
        self.display.status("Laser", "Standby", "ok")
        self.display.status("Bed Temp", "25°C", "dim")
        self.display.status("Nozzle Temp", "25°C", "dim")
        self.display.status("Filament", "4/4 slots loaded", "ok")

        self.say("All systems nominal. Standing by for commands.")

    def _cmd_stop(self, text: str):
        """Handle stop command."""
        if self.state == JarvisState.FABRICATING:
            self.display.warning("EMERGENCY STOP")
            self.say("Aborting fabrication. Please wait.")
            self.state = JarvisState.IDLE
            self._current_job = None
            time.sleep(1)
            self.display.success("Operation stopped safely")
            self.say("Fabrication aborted. Systems safe.")
        else:
            self.say("No active operation to stop.")

    def _cmd_pause(self, text: str):
        """Handle pause command."""
        if self.state == JarvisState.FABRICATING:
            self.say("Pausing operation.")
            self.display.warning("Operation paused")
        else:
            self.say("No active operation to pause.")

    def _cmd_resume(self, text: str):
        """Handle resume command."""
        self.say("Resuming operation.")
        self.display.success("Operation resumed")

    def _cmd_estimate(self, text: str):
        """Handle estimate/cost command."""
        self.display.header("COST ESTIMATE")

        self.display.data_table({
            "Material": "PLA (42.3g)",
            "Material Cost": "$1.06",
            "Machine Time": "2h 45m",
            "Machine Cost": "$1.38",
            "Energy": "$0.05",
            "─────────────": "───────",
            "TOTAL": "$2.49",
        }, title="PRINT ESTIMATE")

        self.say("Estimated total cost is $2.49 for this print.")

    def _cmd_materials(self, text: str):
        """Handle materials command."""
        self.display.header("MATERIAL BAY STATUS")

        slots = [
            ("Slot 1", "PLA White", "~800g"),
            ("Slot 2", "PLA Red", "~650g"),
            ("Slot 3", "PLA Blue", "~900g"),
            ("Slot 4", "PETG Clear", "~750g"),
        ]

        for slot, material, remaining in slots:
            self.display.status(slot, f"{material} ({remaining})", "ok")

        self.say("All material slots loaded and ready.")

    def _cmd_help(self, text: str):
        """Handle help command."""
        self.display.header("AVAILABLE COMMANDS")

        commands = [
            ("scan / capture", "Scan an object with LiDAR"),
            ("analyze / inspect", "Analyze mesh quality"),
            ("repair / fix", "Auto-repair mesh issues"),
            ("scale / resize", "Scale object size"),
            ("hollow / shell", "Make object hollow"),
            ("print / fabricate", "Start 3D printing"),
            ("cut / laser cut", "Laser cut material"),
            ("engrave / etch", "Laser engrave design"),
            ("status", "Check system status"),
            ("estimate / cost", "Get cost estimate"),
            ("materials", "Check material bay"),
            ("stop / abort", "Emergency stop"),
            ("goodbye / exit", "Shutdown Jarvis"),
        ]

        self.display.hologram_box(
            [f"{cmd:20} │ {desc}" for cmd, desc in commands],
            title="VOICE COMMANDS"
        )

        self.say("These are the commands I understand. How may I assist you?")

    def _cmd_shutdown(self, text: str):
        """Handle shutdown command."""
        self.shutdown()

    def shutdown(self):
        """Shutdown JARVIS gracefully."""
        self.display.header("SHUTTING DOWN")

        # Stop ambient sound
        if self.sounds:
            self.sounds.stop_ambient()

        self.say("Powering down systems. Goodbye.")

        # Power down sound
        if self.sounds:
            self.sounds.play(SoundType.POWER_DOWN, block=True)

        if self.voice:
            self.voice.wait()
            self.voice.stop()

        if self.sounds:
            self.sounds.stop()

        time.sleep(0.5)
        self.display.info("JARVIS offline")
        print()


# Main entry point
def main():
    """Run JARVIS in interactive mode."""
    jarvis = Jarvis(voice_enabled=True)
    jarvis.boot()
    jarvis.interactive()


if __name__ == "__main__":
    main()
