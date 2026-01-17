"""
JARVIS Display System

Futuristic terminal UI with animations, ASCII art, and sci-fi visuals.
"""

import sys
import time
import threading
import math
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    BLINK = "\033[5m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"


# Jarvis color scheme (cyan/blue sci-fi aesthetic)
JARVIS_PRIMARY = Colors.BRIGHT_CYAN
JARVIS_SECONDARY = Colors.CYAN
JARVIS_ACCENT = Colors.BRIGHT_BLUE
JARVIS_SUCCESS = Colors.BRIGHT_GREEN
JARVIS_WARNING = Colors.BRIGHT_YELLOW
JARVIS_ERROR = Colors.BRIGHT_RED
JARVIS_DIM = Colors.BRIGHT_BLACK


# ASCII Art banners
JARVIS_BANNER = f"""{JARVIS_PRIMARY}
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
{JARVIS_DIM}    Just A Rather Very Intelligent System{Colors.RESET}
"""

FAB_LAB_BANNER = f"""{JARVIS_PRIMARY}
███████╗ █████╗ ██████╗     ██╗      █████╗ ██████╗
██╔════╝██╔══██╗██╔══██╗    ██║     ██╔══██╗██╔══██╗
█████╗  ███████║██████╔╝    ██║     ███████║██████╔╝
██╔══╝  ██╔══██║██╔══██╗    ██║     ██╔══██║██╔══██╗
██║     ██║  ██║██████╔╝    ███████╗██║  ██║██████╔╝
╚═╝     ╚═╝  ╚═╝╚═════╝     ╚══════╝╚═╝  ╚═╝╚═════╝
{JARVIS_DIM}        Personal Fabrication System v2.0{Colors.RESET}
"""

PRINTER_ASCII = f"""{JARVIS_SECONDARY}
    ╔══════════════════════════╗
    ║  {JARVIS_PRIMARY}BAMBU LAB H2D{JARVIS_SECONDARY}           ║
    ╠══════════════════════════╣
    ║  ┌────────────────────┐  ║
    ║  │{JARVIS_DIM}░░░░░░░░░░░░░░░░░░░░{JARVIS_SECONDARY}│  ║
    ║  │{JARVIS_DIM}░░░░░░░░░░░░░░░░░░░░{JARVIS_SECONDARY}│  ║
    ║  │{JARVIS_DIM}░░░░░░░░░░░░░░░░░░░░{JARVIS_SECONDARY}│  ║
    ║  └────────────────────┘  ║
    ║  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  ║
    ╚══════════════════════════╝{Colors.RESET}
"""

SCAN_ASCII = f"""{JARVIS_SECONDARY}
       {JARVIS_PRIMARY}◉{JARVIS_SECONDARY}
      ╱│╲
     ╱ │ ╲
    ╱  │  ╲      {JARVIS_DIM}LiDAR SCANNING{JARVIS_SECONDARY}
   ╱   │   ╲
  ╱    │    ╲
 ▔▔▔▔▔▔▔▔▔▔▔▔
   ┌─────┐
   │ {JARVIS_ACCENT}◯◯◯{JARVIS_SECONDARY} │
   │ {JARVIS_ACCENT}◯◯◯{JARVIS_SECONDARY} │
   └─────┘{Colors.RESET}
"""


class AnimationFrame:
    """Single frame of an animation."""
    def __init__(self, content: str, duration: float = 0.1):
        self.content = content
        self.duration = duration


class JarvisDisplay:
    """
    Futuristic terminal display system.
    """

    def __init__(self):
        self._animation_thread: Optional[threading.Thread] = None
        self._stop_animation = threading.Event()
        self._spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._progress_chars = "▏▎▍▌▋▊▉█"

    def clear(self):
        """Clear the terminal."""
        print("\033[2J\033[H", end="")

    def move_cursor(self, row: int, col: int):
        """Move cursor to position."""
        print(f"\033[{row};{col}H", end="")

    def hide_cursor(self):
        """Hide the cursor."""
        print("\033[?25l", end="")

    def show_cursor(self):
        """Show the cursor."""
        print("\033[?25h", end="")

    def banner(self, style: str = "jarvis"):
        """Display a banner."""
        if style == "jarvis":
            print(JARVIS_BANNER)
        elif style == "fablab":
            print(FAB_LAB_BANNER)
        elif style == "printer":
            print(PRINTER_ASCII)
        elif style == "scan":
            print(SCAN_ASCII)

    def header(self, text: str):
        """Display a header."""
        width = 60
        line = "═" * width
        print(f"\n{JARVIS_PRIMARY}╔{line}╗")
        print(f"║{JARVIS_ACCENT}{text.center(width)}{JARVIS_PRIMARY}║")
        print(f"╚{line}╝{Colors.RESET}\n")

    def subheader(self, text: str):
        """Display a subheader."""
        print(f"\n{JARVIS_SECONDARY}▸ {text}{Colors.RESET}")

    def status(self, label: str, value: str, status: str = "ok"):
        """Display a status line."""
        colors = {
            "ok": JARVIS_SUCCESS,
            "warning": JARVIS_WARNING,
            "error": JARVIS_ERROR,
            "info": JARVIS_ACCENT,
            "dim": JARVIS_DIM,
        }
        color = colors.get(status, JARVIS_ACCENT)
        dot = "●" if status == "ok" else "○" if status == "dim" else "◉"
        print(f"  {color}{dot}{Colors.RESET} {JARVIS_DIM}{label}:{Colors.RESET} {color}{value}{Colors.RESET}")

    def info(self, text: str):
        """Display info text."""
        print(f"  {JARVIS_DIM}ℹ {text}{Colors.RESET}")

    def success(self, text: str):
        """Display success message."""
        print(f"  {JARVIS_SUCCESS}✓ {text}{Colors.RESET}")

    def warning(self, text: str):
        """Display warning message."""
        print(f"  {JARVIS_WARNING}⚠ {text}{Colors.RESET}")

    def error(self, text: str):
        """Display error message."""
        print(f"  {JARVIS_ERROR}✗ {text}{Colors.RESET}")

    def progress_bar(self, progress: float, width: int = 40, label: str = ""):
        """
        Display a progress bar.

        Args:
            progress: Progress value 0.0 to 1.0
            width: Width of the bar
            label: Optional label
        """
        filled = int(width * progress)
        empty = width - filled

        # Gradient effect
        bar = ""
        for i in range(filled):
            intensity = i / width
            if intensity < 0.5:
                bar += f"{JARVIS_SECONDARY}█"
            else:
                bar += f"{JARVIS_PRIMARY}█"

        bar += f"{JARVIS_DIM}{'░' * empty}{Colors.RESET}"

        percent = f"{progress * 100:5.1f}%"

        if label:
            print(f"\r  {JARVIS_DIM}{label}{Colors.RESET} [{bar}] {JARVIS_ACCENT}{percent}{Colors.RESET}", end="")
        else:
            print(f"\r  [{bar}] {JARVIS_ACCENT}{percent}{Colors.RESET}", end="")

    def spinner_start(self, message: str = "Processing"):
        """Start a spinner animation."""
        self._stop_animation.clear()
        self._animation_thread = threading.Thread(
            target=self._spinner_loop,
            args=(message,),
            daemon=True
        )
        self._animation_thread.start()

    def spinner_stop(self, final_message: str = ""):
        """Stop the spinner animation."""
        self._stop_animation.set()
        if self._animation_thread:
            self._animation_thread.join(timeout=1)
        print(f"\r{' ' * 60}\r", end="")  # Clear line
        if final_message:
            self.success(final_message)

    def _spinner_loop(self, message: str):
        """Spinner animation loop."""
        i = 0
        while not self._stop_animation.is_set():
            char = self._spinner_chars[i % len(self._spinner_chars)]
            print(f"\r  {JARVIS_PRIMARY}{char}{Colors.RESET} {JARVIS_DIM}{message}...{Colors.RESET}", end="")
            sys.stdout.flush()
            i += 1
            time.sleep(0.1)

    def animated_text(self, text: str, delay: float = 0.03):
        """Print text with typewriter animation."""
        for char in text:
            print(f"{JARVIS_ACCENT}{char}{Colors.RESET}", end="")
            sys.stdout.flush()
            time.sleep(delay)
        print()

    def hologram_box(self, lines: List[str], title: str = ""):
        """Display a holographic-style box."""
        max_width = max(len(line) for line in lines) if lines else 20
        if title:
            max_width = max(max_width, len(title) + 4)

        width = max_width + 4

        # Top border with corners
        print(f"{JARVIS_PRIMARY}┌{'─' * width}┐{Colors.RESET}")

        # Title if provided
        if title:
            print(f"{JARVIS_PRIMARY}│{Colors.RESET} {JARVIS_ACCENT}{title.center(width - 2)}{Colors.RESET} {JARVIS_PRIMARY}│{Colors.RESET}")
            print(f"{JARVIS_PRIMARY}├{'─' * width}┤{Colors.RESET}")

        # Content
        for line in lines:
            padded = line.ljust(width - 2)
            print(f"{JARVIS_PRIMARY}│{Colors.RESET} {padded} {JARVIS_PRIMARY}│{Colors.RESET}")

        # Bottom border
        print(f"{JARVIS_PRIMARY}└{'─' * width}┘{Colors.RESET}")

    def data_table(self, data: Dict[str, Any], title: str = ""):
        """Display data in a formatted table."""
        if not data:
            return

        max_key = max(len(str(k)) for k in data.keys())
        max_val = max(len(str(v)) for v in data.values())
        width = max_key + max_val + 7

        print(f"\n{JARVIS_PRIMARY}┌{'─' * width}┐{Colors.RESET}")
        if title:
            print(f"{JARVIS_PRIMARY}│{Colors.RESET} {JARVIS_ACCENT}{title.center(width - 2)}{Colors.RESET} {JARVIS_PRIMARY}│{Colors.RESET}")
            print(f"{JARVIS_PRIMARY}├{'─' * width}┤{Colors.RESET}")

        for key, value in data.items():
            key_str = str(key).ljust(max_key)
            val_str = str(value).rjust(max_val)
            print(f"{JARVIS_PRIMARY}│{Colors.RESET} {JARVIS_DIM}{key_str}{Colors.RESET} : {JARVIS_ACCENT}{val_str}{Colors.RESET} {JARVIS_PRIMARY}│{Colors.RESET}")

        print(f"{JARVIS_PRIMARY}└{'─' * width}┘{Colors.RESET}")

    def wave_animation(self, duration: float = 2.0, message: str = ""):
        """Display a wave animation."""
        width = 40
        start_time = time.time()

        self.hide_cursor()
        try:
            while time.time() - start_time < duration:
                t = time.time() * 4
                wave = ""
                for i in range(width):
                    y = math.sin(t + i * 0.3) * 0.5 + 0.5
                    if y > 0.8:
                        wave += f"{JARVIS_PRIMARY}█"
                    elif y > 0.6:
                        wave += f"{JARVIS_SECONDARY}▓"
                    elif y > 0.4:
                        wave += f"{JARVIS_ACCENT}▒"
                    elif y > 0.2:
                        wave += f"{JARVIS_DIM}░"
                    else:
                        wave += " "

                print(f"\r  {wave}{Colors.RESET} {JARVIS_DIM}{message}{Colors.RESET}", end="")
                sys.stdout.flush()
                time.sleep(0.05)
        finally:
            self.show_cursor()
            print()

    def scanning_animation(self, duration: float = 3.0):
        """Display a scanning animation."""
        frames = [
            "◐", "◓", "◑", "◒"
        ]
        width = 30
        start_time = time.time()
        i = 0

        self.hide_cursor()
        try:
            while time.time() - start_time < duration:
                frame = frames[i % len(frames)]
                progress = (time.time() - start_time) / duration

                # Scanning beam
                beam_pos = int((math.sin(time.time() * 3) + 1) / 2 * width)
                beam = " " * beam_pos + f"{JARVIS_PRIMARY}║{Colors.RESET}" + " " * (width - beam_pos - 1)

                print(f"\r  {JARVIS_ACCENT}{frame}{Colors.RESET} Scanning [{beam}] {progress * 100:5.1f}%", end="")
                sys.stdout.flush()
                i += 1
                time.sleep(0.1)
        finally:
            self.show_cursor()
            print(f"\r  {JARVIS_SUCCESS}✓{Colors.RESET} Scan complete!{' ' * 30}")

    def fabrication_animation(self, layers: int = 10, duration: float = 5.0):
        """Display a fabrication/printing animation."""
        self.hide_cursor()
        try:
            for layer in range(layers):
                progress = (layer + 1) / layers
                time.sleep(duration / layers)

                # Build up visualization
                print(f"\r  Layer {layer + 1}/{layers} ", end="")

                bar_width = 30
                filled = int(bar_width * progress)
                bar = f"{JARVIS_PRIMARY}{'█' * filled}{JARVIS_DIM}{'░' * (bar_width - filled)}{Colors.RESET}"
                print(f"[{bar}] {progress * 100:5.1f}%", end="")

                # Layer visualization
                layer_vis = f" {JARVIS_SECONDARY}{'▓' * (layer + 1)}{Colors.RESET}"
                print(layer_vis, end="")

                sys.stdout.flush()
        finally:
            self.show_cursor()
            print(f"\n  {JARVIS_SUCCESS}✓ Fabrication complete!{Colors.RESET}")


# Convenience functions

_display: Optional[JarvisDisplay] = None

def get_display() -> JarvisDisplay:
    """Get the default display instance."""
    global _display
    if _display is None:
        _display = JarvisDisplay()
    return _display

def show_banner(style: str = "jarvis"):
    """Show a banner."""
    get_display().banner(style)

def show_status(label: str, value: str, status: str = "ok"):
    """Show a status line."""
    get_display().status(label, value, status)


# Demo
if __name__ == "__main__":
    display = JarvisDisplay()

    display.clear()
    display.banner("jarvis")

    time.sleep(0.5)

    display.header("SYSTEM STATUS")

    display.status("Power Systems", "Online", "ok")
    display.status("Fabrication Unit", "Standby", "ok")
    display.status("LiDAR Scanner", "Ready", "ok")
    display.status("Material Bay", "4/4 slots loaded", "ok")
    display.status("Network", "Connected", "ok")

    time.sleep(0.5)

    display.header("SCANNING OBJECT")
    display.scanning_animation(duration=2.0)

    display.header("MESH ANALYSIS")
    display.data_table({
        "Vertices": "847,293",
        "Faces": "1,694,582",
        "Volume": "42.7 cm³",
        "Dimensions": "75 × 150 × 8 mm",
        "Watertight": "Yes",
        "Printable": "Yes",
    }, title="SCAN RESULTS")

    time.sleep(0.5)

    display.header("FABRICATION")
    display.fabrication_animation(layers=10, duration=3.0)

    display.banner("printer")

    print(f"\n{JARVIS_SUCCESS}  All systems nominal.{Colors.RESET}\n")
