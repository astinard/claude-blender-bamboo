"""Tests for voice control module."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from src.jarvis.voice_control import (
    VoiceController,
    VoiceCommand,
    CommandCategory,
    CommandResult,
    create_voice_controller,
)


class TestCommandCategory:
    """Tests for CommandCategory enum."""

    def test_category_values(self):
        """Test category values."""
        assert CommandCategory.GENERATION.value == "generation"
        assert CommandCategory.QUEUE.value == "queue"
        assert CommandCategory.MONITORING.value == "monitoring"
        assert CommandCategory.ANALYTICS.value == "analytics"
        assert CommandCategory.MATERIALS.value == "materials"
        assert CommandCategory.MAINTENANCE.value == "maintenance"
        assert CommandCategory.AR.value == "ar"
        assert CommandCategory.SYSTEM.value == "system"


class TestVoiceCommand:
    """Tests for VoiceCommand dataclass."""

    def test_create_command(self):
        """Test creating a voice command."""
        cmd = VoiceCommand(
            name="test_command",
            category=CommandCategory.SYSTEM,
            patterns=[r"test (?P<value>.+)"],
            description="A test command",
            parameters=["value"],
        )

        assert cmd.name == "test_command"
        assert cmd.category == CommandCategory.SYSTEM
        assert len(cmd.patterns) == 1
        assert cmd.parameters == ["value"]

    def test_matches_simple_pattern(self):
        """Test matching a simple pattern."""
        cmd = VoiceCommand(
            name="help",
            category=CommandCategory.SYSTEM,
            patterns=[r"help", r"what can you do"],
            description="Show help",
        )

        matched, params = cmd.matches("help")
        assert matched is True
        assert params == {}

        matched, params = cmd.matches("what can you do")
        assert matched is True
        assert params == {}

    def test_matches_with_parameters(self):
        """Test matching with named parameters."""
        cmd = VoiceCommand(
            name="generate",
            category=CommandCategory.GENERATION,
            patterns=[r"generate (?:a |an )?(?P<description>.+)"],
            description="Generate a model",
            parameters=["description"],
        )

        matched, params = cmd.matches("generate a dragon")
        assert matched is True
        assert params["description"] == "dragon"

        matched, params = cmd.matches("generate phone case")
        assert matched is True
        assert params["description"] == "phone case"

    def test_matches_case_insensitive(self):
        """Test case insensitive matching."""
        cmd = VoiceCommand(
            name="status",
            category=CommandCategory.SYSTEM,
            patterns=[r"system status"],
            description="Show status",
        )

        matched, _ = cmd.matches("System Status")
        assert matched is True

        matched, _ = cmd.matches("SYSTEM STATUS")
        assert matched is True

    def test_no_match(self):
        """Test when no pattern matches."""
        cmd = VoiceCommand(
            name="help",
            category=CommandCategory.SYSTEM,
            patterns=[r"help"],
            description="Show help",
        )

        matched, params = cmd.matches("random text")
        assert matched is False
        assert params == {}


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_create_result(self):
        """Test creating a command result."""
        result = CommandResult(
            command="test",
            success=True,
            message="Test passed",
            data={"key": "value"},
        )

        assert result.command == "test"
        assert result.success is True
        assert result.message == "Test passed"
        assert result.data == {"key": "value"}
        assert result.executed_at is not None

    def test_result_failure(self):
        """Test failure result."""
        result = CommandResult(
            command="test",
            success=False,
            message="Test failed",
        )

        assert result.success is False
        assert result.data is None


class TestVoiceController:
    """Tests for VoiceController class."""

    @pytest.fixture
    def controller(self):
        """Create a voice controller."""
        return VoiceController(wake_word="jarvis")

    def test_init(self, controller):
        """Test controller initialization."""
        assert controller.wake_word == "jarvis"
        assert controller._listening is False
        assert len(controller._commands) > 0  # Has default commands

    def test_init_custom_wake_word(self):
        """Test custom wake word."""
        ctrl = VoiceController(wake_word="friday")
        assert ctrl.wake_word == "friday"

    def test_register_command(self, controller):
        """Test registering a custom command."""
        custom = VoiceCommand(
            name="custom_test",
            category=CommandCategory.SYSTEM,
            patterns=[r"custom test"],
            description="Custom test command",
        )

        controller.register_command(custom)
        assert "custom_test" in controller._commands

    def test_unregister_command(self, controller):
        """Test unregistering a command."""
        # Register first
        custom = VoiceCommand(
            name="to_remove",
            category=CommandCategory.SYSTEM,
            patterns=[r"remove me"],
            description="To be removed",
        )
        controller.register_command(custom)
        assert "to_remove" in controller._commands

        # Unregister
        result = controller.unregister_command("to_remove")
        assert result is True
        assert "to_remove" not in controller._commands

    def test_unregister_nonexistent(self, controller):
        """Test unregistering nonexistent command."""
        result = controller.unregister_command("nonexistent")
        assert result is False

    def test_get_commands_all(self, controller):
        """Test getting all commands."""
        commands = controller.get_commands()
        assert len(commands) > 0

    def test_get_commands_by_category(self, controller):
        """Test getting commands filtered by category."""
        queue_commands = controller.get_commands(CommandCategory.QUEUE)
        assert len(queue_commands) > 0
        assert all(c.category == CommandCategory.QUEUE for c in queue_commands)

    def test_parse_command_basic(self, controller):
        """Test parsing a basic command."""
        cmd, params = controller.parse_command("help")
        assert cmd is not None
        assert cmd.name == "help"

    def test_parse_command_with_wake_word(self, controller):
        """Test parsing command with wake word."""
        cmd, params = controller.parse_command("jarvis help")
        assert cmd is not None
        assert cmd.name == "help"

    def test_parse_command_hey_wake_word(self, controller):
        """Test parsing with 'hey' prefix."""
        cmd, params = controller.parse_command("hey jarvis help")
        assert cmd is not None
        assert cmd.name == "help"

    def test_parse_command_with_please(self, controller):
        """Test parsing with politeness prefix."""
        cmd, params = controller.parse_command("please show the queue")
        assert cmd is not None
        assert cmd.name == "show_queue"

    def test_parse_command_with_params(self, controller):
        """Test parsing command with parameters."""
        cmd, params = controller.parse_command("generate a dragon phone stand")
        assert cmd is not None
        assert cmd.name == "generate_model"
        assert "description" in params
        assert "dragon phone stand" in params["description"]

    def test_parse_command_unknown(self, controller):
        """Test parsing unknown command."""
        cmd, params = controller.parse_command("random nonsense text")
        assert cmd is None
        assert params == {}


class TestVoiceControllerDefaultCommands:
    """Tests for default registered commands."""

    @pytest.fixture
    def controller(self):
        """Create a voice controller."""
        return VoiceController()

    def test_generation_commands(self, controller):
        """Test generation commands are registered."""
        cmd, params = controller.parse_command("generate a phone case")
        assert cmd is not None
        assert cmd.name == "generate_model"
        assert cmd.category == CommandCategory.GENERATION

        cmd, _ = controller.parse_command("create a dragon")
        assert cmd.name == "generate_model"

        cmd, _ = controller.parse_command("make me a stand")
        assert cmd.name == "generate_model"

    def test_queue_commands(self, controller):
        """Test queue commands are registered."""
        cmd, _ = controller.parse_command("start the queue")
        assert cmd.name == "start_queue"

        cmd, _ = controller.parse_command("pause printing")
        assert cmd.name == "pause_queue"

        cmd, _ = controller.parse_command("show queue")
        assert cmd.name == "show_queue"

        cmd, params = controller.parse_command("add model.stl to queue")
        assert cmd.name == "add_to_queue"
        assert "file" in params

    def test_monitoring_commands(self, controller):
        """Test monitoring commands are registered."""
        cmd, _ = controller.parse_command("printer status")
        assert cmd.name == "print_status"

        cmd, _ = controller.parse_command("start monitoring")
        assert cmd.name == "start_monitoring"

        cmd, _ = controller.parse_command("stop monitoring")
        assert cmd.name == "stop_monitoring"

        cmd, _ = controller.parse_command("take a snapshot")
        assert cmd.name == "take_snapshot"

    def test_analytics_commands(self, controller):
        """Test analytics commands are registered."""
        cmd, _ = controller.parse_command("show analytics")
        assert cmd.name == "show_analytics"

        cmd, _ = controller.parse_command("printing statistics")
        assert cmd.name == "show_analytics"

        # Test report generation with explicit "report" keyword
        cmd, params = controller.parse_command("create a weekly report")
        assert cmd.name == "generate_report"
        assert params.get("report_type") == "weekly"

    def test_materials_commands(self, controller):
        """Test materials commands are registered."""
        cmd, _ = controller.parse_command("check material levels")
        assert cmd.name == "check_materials"

        cmd, _ = controller.parse_command("any low stock")
        assert cmd.name == "low_stock_alerts"

    def test_maintenance_commands(self, controller):
        """Test maintenance commands are registered."""
        cmd, _ = controller.parse_command("maintenance status")
        assert cmd.name == "maintenance_status"

        cmd, params = controller.parse_command("record maintenance on nozzle")
        assert cmd.name == "record_maintenance"
        assert params.get("component") == "nozzle"

    def test_ar_commands(self, controller):
        """Test AR commands are registered."""
        cmd, _ = controller.parse_command("ar preview")
        assert cmd.name == "ar_preview"

        cmd, _ = controller.parse_command("preview in ar")
        assert cmd.name == "ar_preview"

    def test_system_commands(self, controller):
        """Test system commands are registered."""
        cmd, _ = controller.parse_command("system status")
        assert cmd.name == "system_status"

        cmd, _ = controller.parse_command("help")
        assert cmd.name == "help"

        cmd, _ = controller.parse_command("stop listening")
        assert cmd.name == "stop_listening"


class TestVoiceControllerProcessCommand:
    """Tests for command processing."""

    @pytest.fixture
    def controller(self):
        """Create a voice controller."""
        return VoiceController()

    @pytest.mark.asyncio
    async def test_process_known_command(self, controller):
        """Test processing a known command."""
        result = await controller.process_command("help")

        assert result.success is True
        assert result.command == "help"
        assert "Recognized" in result.message

    @pytest.mark.asyncio
    async def test_process_unknown_command(self, controller):
        """Test processing unknown command."""
        result = await controller.process_command("unknown gibberish")

        assert result.success is False
        assert "Unknown command" in result.message

    @pytest.mark.asyncio
    async def test_process_command_with_handler(self, controller):
        """Test processing command with custom handler."""
        handler_called = False
        handler_params = None

        def test_handler(params, context):
            nonlocal handler_called, handler_params
            handler_called = True
            handler_params = params
            return {"result": "success"}

        custom = VoiceCommand(
            name="custom_handled",
            category=CommandCategory.SYSTEM,
            patterns=[r"custom handled (?P<value>.+)"],
            description="Custom handled command",
            parameters=["value"],
            handler=test_handler,
        )
        controller.register_command(custom)

        result = await controller.process_command("custom handled test_value")

        assert handler_called is True
        assert handler_params.get("value") == "test_value"
        assert result.success is True
        assert result.data == {"result": "success"}

    @pytest.mark.asyncio
    async def test_process_command_with_async_handler(self, controller):
        """Test processing command with async handler."""
        async def async_handler(params, context):
            await asyncio.sleep(0.01)
            return {"async": "result"}

        custom = VoiceCommand(
            name="async_command",
            category=CommandCategory.SYSTEM,
            patterns=[r"async test"],
            description="Async command",
            handler=async_handler,
        )
        controller.register_command(custom)

        result = await controller.process_command("async test")

        assert result.success is True
        assert result.data == {"async": "result"}

    @pytest.mark.asyncio
    async def test_process_command_handler_error(self, controller):
        """Test handling error in command handler."""
        def error_handler(params, context):
            raise ValueError("Test error")

        custom = VoiceCommand(
            name="error_command",
            category=CommandCategory.SYSTEM,
            patterns=[r"error test"],
            description="Error command",
            handler=error_handler,
        )
        controller.register_command(custom)

        result = await controller.process_command("error test")

        assert result.success is False
        assert "Error executing" in result.message

    @pytest.mark.asyncio
    async def test_command_history(self, controller):
        """Test command history tracking."""
        await controller.process_command("help")
        await controller.process_command("system status")
        await controller.process_command("unknown")

        history = controller.get_command_history()
        assert len(history) == 3
        assert history[0].command == "help"
        assert history[1].command == "system_status"
        assert history[2].success is False

    @pytest.mark.asyncio
    async def test_command_history_limit(self, controller):
        """Test command history limit."""
        # Add many commands
        for i in range(30):
            await controller.process_command("help")

        # Default limit is 20
        history = controller.get_command_history(limit=10)
        assert len(history) == 10


class TestVoiceControllerListening:
    """Tests for voice listening functionality."""

    @pytest.fixture
    def controller(self):
        """Create a voice controller."""
        return VoiceController()

    def test_is_listening_property(self, controller):
        """Test is_listening property."""
        assert controller.is_listening is False

        controller._listening = True
        assert controller.is_listening is True

    def test_stop_listening(self, controller):
        """Test stop listening."""
        controller._listening = True
        controller.stop_listening()
        assert controller._listening is False

    @pytest.mark.asyncio
    async def test_listen_no_speech_available(self, controller):
        """Test listen when speech recognition not available."""
        controller._speech_available = False

        result = await controller.listen()
        assert result is None

    @pytest.mark.asyncio
    async def test_continuous_listening_no_speech(self, controller):
        """Test continuous listening with no speech available."""
        controller._speech_available = False

        # Should return immediately
        await controller.start_continuous_listening()
        assert controller._listening is False


class TestVoiceControllerHelpText:
    """Tests for help text generation."""

    @pytest.fixture
    def controller(self):
        """Create a voice controller."""
        return VoiceController()

    def test_get_help_text(self, controller):
        """Test getting help text."""
        help_text = controller.get_help_text()

        assert "Available voice commands" in help_text
        assert "[GENERATION]" in help_text
        assert "[QUEUE]" in help_text
        assert "[MONITORING]" in help_text
        assert "[SYSTEM]" in help_text

    def test_help_text_contains_descriptions(self, controller):
        """Test help text contains command descriptions."""
        help_text = controller.get_help_text()

        # Check some descriptions
        assert "Generate a 3D model" in help_text
        assert "Start processing the print queue" in help_text
        assert "Show available commands" in help_text


class TestCreateVoiceController:
    """Tests for create_voice_controller convenience function."""

    def test_create_default(self):
        """Test creating with defaults."""
        ctrl = create_voice_controller()
        assert ctrl.wake_word == "jarvis"

    def test_create_custom_wake_word(self):
        """Test creating with custom wake word."""
        ctrl = create_voice_controller(wake_word="friday")
        assert ctrl.wake_word == "friday"


class TestVoiceControllerIntegration:
    """Integration tests for voice controller."""

    @pytest.fixture
    def controller(self):
        """Create a voice controller."""
        return VoiceController()

    @pytest.mark.asyncio
    async def test_full_command_workflow(self, controller):
        """Test complete command workflow."""
        # Parse and process command
        text = "hey jarvis please generate a dragon phone case"

        cmd, params = controller.parse_command(text)
        assert cmd is not None
        assert cmd.name == "generate_model"
        assert "dragon phone case" in params.get("description", "")

        result = await controller.process_command(text)
        assert result.success is True
        assert result.command == "generate_model"

        # Check history
        history = controller.get_command_history()
        assert len(history) == 1
        assert history[0].command == "generate_model"

    @pytest.mark.asyncio
    async def test_multiple_commands_sequence(self, controller):
        """Test sequence of multiple commands."""
        commands = [
            "show queue",
            "add test.stl to queue",
            "start printing",
            "printer status",
        ]

        for text in commands:
            result = await controller.process_command(text)
            assert result.success is True

        history = controller.get_command_history()
        assert len(history) == 4
        assert history[0].command == "show_queue"
        assert history[1].command == "add_to_queue"
        assert history[2].command == "start_queue"
        assert history[3].command == "print_status"

    @pytest.mark.asyncio
    async def test_context_passing(self, controller):
        """Test context is passed to handlers."""
        received_context = None

        def context_handler(params, context):
            nonlocal received_context
            received_context = context
            return {}

        custom = VoiceCommand(
            name="context_test",
            category=CommandCategory.SYSTEM,
            patterns=[r"context test"],
            description="Context test",
            handler=context_handler,
        )
        controller.register_command(custom)

        test_context = {"user": "test", "session": "123"}
        await controller.process_command("context test", context=test_context)

        assert received_context == test_context
