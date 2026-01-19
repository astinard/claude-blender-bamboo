"""Voice control module for JARVIS integration.

Provides voice command recognition and processing for hands-free
control of the 3D printing workflow.

Note: Requires speech_recognition library for actual voice input.
Falls back to text commands when not available.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import subprocess
import webbrowser

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("jarvis.voice_control")


def _launch_dashboard(params: dict, context: dict = None) -> dict:
    """Handler to launch the JARVIS Fab Lab Control dashboard."""
    import os
    from pathlib import Path

    # Look for JARVIS dashboard in multiple locations
    possible_paths = [
        Path.home() / "projects" / "claude-blender-bamboo-2026-01-14" / "web" / "index.html",
        Path.home() / "projects" / "claude-blender-bamboo" / "web" / "index.html",
        Path(__file__).parent.parent.parent / "web" / "index.html",
    ]

    dashboard_path = None
    for path in possible_paths:
        if path.exists():
            dashboard_path = path
            break

    if dashboard_path:
        url = f"file://{dashboard_path}"
        try:
            webbrowser.open(url)
            return {
                "action": "dashboard_opened",
                "url": url,
                "message": f"JARVIS dashboard opened",
            }
        except Exception as e:
            return {
                "action": "dashboard_error",
                "error": str(e),
                "message": f"Could not open dashboard: {e}",
            }
    else:
        # Fall back to localhost server
        url = "http://localhost:9880"
        try:
            webbrowser.open(url)
            return {
                "action": "dashboard_opened",
                "url": url,
                "message": f"Dashboard opened at {url}",
            }
        except Exception as e:
            return {
                "action": "dashboard_error",
                "error": str(e),
                "message": f"Could not open dashboard: {e}",
            }


class CommandCategory(str, Enum):
    """Voice command categories."""
    GENERATION = "generation"  # AI model generation
    QUEUE = "queue"  # Print queue management
    MONITORING = "monitoring"  # Print monitoring
    ANALYTICS = "analytics"  # Analytics and reports
    MATERIALS = "materials"  # Material inventory
    MAINTENANCE = "maintenance"  # Maintenance tasks
    AR = "ar"  # AR preview
    SYSTEM = "system"  # System commands


@dataclass
class VoiceCommand:
    """A recognized voice command."""
    name: str
    category: CommandCategory
    patterns: List[str]  # Regex patterns to match
    description: str
    handler: Optional[Callable] = None
    parameters: List[str] = field(default_factory=list)

    def matches(self, text: str) -> Tuple[bool, Dict[str, str]]:
        """
        Check if text matches this command.

        Args:
            text: Input text to match

        Returns:
            Tuple of (matched, extracted_params)
        """
        text_lower = text.lower().strip()

        for pattern in self.patterns:
            match = re.match(pattern, text_lower)
            if match:
                return True, match.groupdict()

        return False, {}


@dataclass
class CommandResult:
    """Result of executing a voice command."""
    command: str
    success: bool
    message: str
    data: Optional[dict] = None
    executed_at: str = field(default_factory=lambda: datetime.now().isoformat())


class VoiceController:
    """
    Voice command controller for JARVIS.

    Supports both voice recognition (when available) and
    text command input for testing/fallback.
    """

    def __init__(self, wake_word: str = "jarvis"):
        """
        Initialize voice controller.

        Args:
            wake_word: Word to trigger listening (e.g., "jarvis", "hey jarvis")
        """
        self.wake_word = wake_word.lower()
        self._commands: Dict[str, VoiceCommand] = {}
        self._listening = False
        self._speech_available = False
        self._command_history: List[CommandResult] = []

        # Check for speech recognition
        self._check_speech_available()

        # Register default commands
        self._register_default_commands()

    def _check_speech_available(self) -> None:
        """Check if speech recognition is available."""
        try:
            import speech_recognition
            self._speech_available = True
            logger.info("Speech recognition available")
        except ImportError:
            logger.warning("speech_recognition not installed, using text input only")
            self._speech_available = False

    def _register_default_commands(self) -> None:
        """Register all default voice commands."""
        # Generation commands (exclude "report" to avoid conflict with generate_report)
        self.register_command(VoiceCommand(
            name="generate_model",
            category=CommandCategory.GENERATION,
            patterns=[
                r"generate (?:a |an )?(?P<description>(?!.*\breport$).+)",
                r"create (?:a |an )?(?P<description>(?!.*\breport$).+)",
                r"make (?:me )?(?:a |an )?(?P<description>(?!.*\breport$).+)",
            ],
            description="Generate a 3D model from description",
            parameters=["description"],
        ))

        # Queue commands
        self.register_command(VoiceCommand(
            name="start_queue",
            category=CommandCategory.QUEUE,
            patterns=[
                r"start (?:the )?(?:print )?queue",
                r"begin printing",
                r"start printing",
            ],
            description="Start processing the print queue",
        ))

        self.register_command(VoiceCommand(
            name="pause_queue",
            category=CommandCategory.QUEUE,
            patterns=[
                r"pause (?:the )?(?:print )?queue",
                r"pause printing",
                r"hold (?:the )?queue",
            ],
            description="Pause the print queue",
        ))

        self.register_command(VoiceCommand(
            name="show_queue",
            category=CommandCategory.QUEUE,
            patterns=[
                r"show (?:the )?(?:print )?queue",
                r"list (?:the )?queue",
                r"what(?:'s| is) in (?:the )?queue",
            ],
            description="Show current print queue",
        ))

        self.register_command(VoiceCommand(
            name="add_to_queue",
            category=CommandCategory.QUEUE,
            patterns=[
                r"add (?P<file>.+) to (?:the )?queue",
                r"queue (?P<file>.+)",
            ],
            description="Add a file to the print queue",
            parameters=["file"],
        ))

        # Monitoring commands
        self.register_command(VoiceCommand(
            name="print_status",
            category=CommandCategory.MONITORING,
            patterns=[
                r"(?:what(?:'s| is) the )?print(?:er)? status",
                r"how(?:'s| is) the print(?:er)?",
                r"check print(?:er)? status",
            ],
            description="Get current print status",
        ))

        self.register_command(VoiceCommand(
            name="start_monitoring",
            category=CommandCategory.MONITORING,
            patterns=[
                r"start monitoring",
                r"enable monitoring",
                r"watch (?:the )?print(?:er)?",
            ],
            description="Start print monitoring",
        ))

        self.register_command(VoiceCommand(
            name="stop_monitoring",
            category=CommandCategory.MONITORING,
            patterns=[
                r"stop monitoring",
                r"disable monitoring",
            ],
            description="Stop print monitoring",
        ))

        self.register_command(VoiceCommand(
            name="take_snapshot",
            category=CommandCategory.MONITORING,
            patterns=[
                r"take (?:a )?snapshot",
                r"capture (?:a )?(?:snapshot|image|photo)",
            ],
            description="Capture a camera snapshot",
        ))

        self.register_command(VoiceCommand(
            name="show_dashboard",
            category=CommandCategory.MONITORING,
            patterns=[
                r"(?:show|open|start|launch) (?:the )?(?:jarvis )?dashboard",
                r"dashboard",
                r"open (?:the )?(?:jarvis|monitoring)",
                r"show (?:the )?(?:monitoring|jarvis) (?:dashboard|screen|panel)?",
                r"jarvis",
            ],
            description="Open the JARVIS Fab Lab dashboard",
            handler=_launch_dashboard,
        ))

        # Analytics commands
        self.register_command(VoiceCommand(
            name="show_analytics",
            category=CommandCategory.ANALYTICS,
            patterns=[
                r"show (?:me )?(?:the )?analytics",
                r"print(?:ing)? statistics",
                r"show (?:me )?(?:the )?stats",
            ],
            description="Show printing analytics",
        ))

        self.register_command(VoiceCommand(
            name="generate_report",
            category=CommandCategory.ANALYTICS,
            patterns=[
                r"generate (?:a )?(?P<report_type>weekly|monthly|daily)? ?report",
                r"create (?:a )?(?P<report_type>weekly|monthly|daily)? ?report",
            ],
            description="Generate an analytics report",
            parameters=["report_type"],
        ))

        # Materials commands
        self.register_command(VoiceCommand(
            name="check_materials",
            category=CommandCategory.MATERIALS,
            patterns=[
                r"check (?:the )?(?:material|filament) (?:inventory|levels?|stock)",
                r"how much (?:material|filament) (?:do (?:i|we) have|is left)",
                r"(?:material|filament) status",
            ],
            description="Check material inventory levels",
        ))

        self.register_command(VoiceCommand(
            name="low_stock_alerts",
            category=CommandCategory.MATERIALS,
            patterns=[
                r"(?:any )?low stock(?:alerts)?",
                r"what(?:'s| is) running low",
            ],
            description="Show low stock alerts",
        ))

        # Maintenance commands
        self.register_command(VoiceCommand(
            name="maintenance_status",
            category=CommandCategory.MAINTENANCE,
            patterns=[
                r"maintenance status",
                r"check maintenance",
                r"what maintenance is (?:due|needed)",
            ],
            description="Show maintenance status",
        ))

        self.register_command(VoiceCommand(
            name="record_maintenance",
            category=CommandCategory.MAINTENANCE,
            patterns=[
                r"record maintenance (?:on |for )?(?P<component>.+)",
                r"(?:i |we )?(?:did|performed) maintenance (?:on |for )?(?P<component>.+)",
            ],
            description="Record a maintenance task",
            parameters=["component"],
        ))

        # AR commands
        self.register_command(VoiceCommand(
            name="ar_preview",
            category=CommandCategory.AR,
            patterns=[
                r"(?:show )?ar preview",
                r"preview in ar",
                r"start ar (?:preview)?",
            ],
            description="Start AR preview",
        ))

        # System commands
        self.register_command(VoiceCommand(
            name="system_status",
            category=CommandCategory.SYSTEM,
            patterns=[
                r"system status",
                r"status report",
                r"how(?:'s| is) everything",
            ],
            description="Show overall system status",
        ))

        self.register_command(VoiceCommand(
            name="help",
            category=CommandCategory.SYSTEM,
            patterns=[
                r"help",
                r"what can you do",
                r"list commands",
                r"available commands",
            ],
            description="Show available commands",
        ))

        self.register_command(VoiceCommand(
            name="stop_listening",
            category=CommandCategory.SYSTEM,
            patterns=[
                r"stop listening",
                r"go to sleep",
                r"(?:good)?bye",
            ],
            description="Stop voice listening",
        ))

    def register_command(self, command: VoiceCommand) -> None:
        """Register a voice command."""
        self._commands[command.name] = command
        logger.debug(f"Registered command: {command.name}")

    def unregister_command(self, name: str) -> bool:
        """Unregister a voice command."""
        if name in self._commands:
            del self._commands[name]
            return True
        return False

    def get_commands(self, category: Optional[CommandCategory] = None) -> List[VoiceCommand]:
        """Get all registered commands, optionally filtered by category."""
        if category:
            return [c for c in self._commands.values() if c.category == category]
        return list(self._commands.values())

    def parse_command(self, text: str) -> Tuple[Optional[VoiceCommand], Dict[str, str]]:
        """
        Parse text to find matching command.

        Args:
            text: Input text

        Returns:
            Tuple of (command, parameters) or (None, {}) if no match
        """
        # Remove wake word if present
        text_lower = text.lower().strip()
        for wake in [f"hey {self.wake_word}", self.wake_word]:
            if text_lower.startswith(wake):
                text_lower = text_lower[len(wake):].strip()
                text = text[len(wake):].strip()
                # Remove leading punctuation (comma, colon, etc.)
                if text_lower and text_lower[0] in ',.:;!':
                    text_lower = text_lower[1:].strip()
                    text = text[1:].strip() if text else text
                break

        # Remove common prefixes
        for prefix in ["please ", "can you ", "could you ", "would you "]:
            if text_lower.startswith(prefix):
                text_lower = text_lower[len(prefix):]
                text = text[len(prefix):]

        # Try to match each command
        for command in self._commands.values():
            matched, params = command.matches(text_lower)
            if matched:
                logger.info(f"Matched command: {command.name} with params: {params}")
                return command, params

        return None, {}

    async def process_command(
        self,
        text: str,
        context: Optional[dict] = None,
    ) -> CommandResult:
        """
        Process a text command.

        Args:
            text: Command text
            context: Optional context dictionary

        Returns:
            Command execution result
        """
        command, params = self.parse_command(text)

        if not command:
            result = CommandResult(
                command=text,
                success=False,
                message=f"Unknown command: {text}",
            )
            self._command_history.append(result)
            return result

        # Execute command handler if available
        if command.handler:
            try:
                if asyncio.iscoroutinefunction(command.handler):
                    data = await command.handler(params, context)
                else:
                    data = command.handler(params, context)

                result = CommandResult(
                    command=command.name,
                    success=True,
                    message=f"Executed: {command.description}",
                    data=data,
                )
            except Exception as e:
                result = CommandResult(
                    command=command.name,
                    success=False,
                    message=f"Error executing {command.name}: {e}",
                )
        else:
            # No handler, return command info
            result = CommandResult(
                command=command.name,
                success=True,
                message=f"Recognized: {command.description}",
                data={"params": params, "category": command.category.value},
            )

        self._command_history.append(result)
        return result

    async def listen(self, timeout: float = 5.0) -> Optional[str]:
        """
        Listen for voice input.

        Args:
            timeout: Listening timeout in seconds

        Returns:
            Recognized text or None
        """
        if not self._speech_available:
            logger.warning("Speech recognition not available")
            return None

        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()

            with sr.Microphone() as source:
                logger.info("Listening...")
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=timeout)

            try:
                text = recognizer.recognize_google(audio)
                logger.info(f"Recognized: {text}")
                return text
            except sr.UnknownValueError:
                logger.debug("Could not understand audio")
                return None
            except sr.RequestError as e:
                logger.error(f"Speech recognition error: {e}")
                return None

        except Exception as e:
            logger.error(f"Listen error: {e}")
            return None

    async def start_continuous_listening(self) -> None:
        """Start continuous voice listening mode."""
        if not self._speech_available:
            logger.error("Speech recognition not available for continuous listening")
            return

        self._listening = True
        logger.info(f"Continuous listening started (wake word: {self.wake_word})")

        while self._listening:
            text = await self.listen(timeout=10.0)

            if text:
                # Check for wake word
                text_lower = text.lower()
                if self.wake_word in text_lower or f"hey {self.wake_word}" in text_lower:
                    result = await self.process_command(text)

                    # Check for stop command
                    if result.command == "stop_listening":
                        self._listening = False
                        break

            await asyncio.sleep(0.1)

        logger.info("Continuous listening stopped")

    def stop_listening(self) -> None:
        """Stop continuous listening."""
        self._listening = False

    @property
    def is_listening(self) -> bool:
        """Check if currently listening."""
        return self._listening

    def get_command_history(self, limit: int = 20) -> List[CommandResult]:
        """Get recent command history."""
        return self._command_history[-limit:]

    def get_help_text(self) -> str:
        """Get help text for all commands."""
        lines = ["Available voice commands:", ""]

        for category in CommandCategory:
            commands = self.get_commands(category)
            if commands:
                lines.append(f"[{category.value.upper()}]")
                for cmd in commands:
                    lines.append(f"  - {cmd.description}")
                lines.append("")

        return "\n".join(lines)


# Convenience function
def create_voice_controller(wake_word: str = "jarvis") -> VoiceController:
    """Create a voice controller with default configuration."""
    return VoiceController(wake_word=wake_word)
