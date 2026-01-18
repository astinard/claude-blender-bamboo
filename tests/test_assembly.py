"""Tests for assembly instruction generator."""

import pytest
from pathlib import Path

from src.docs.assembly_generator import (
    AssemblyGenerator,
    AssemblyConfig,
    AssemblyPart,
    AssemblyStep,
    AssemblyInstructions,
    HardwareItem,
    ConnectionType,
    create_generator,
    generate_instructions,
)


class TestConnectionType:
    """Tests for ConnectionType enum."""

    def test_connection_values(self):
        """Test connection type values."""
        assert ConnectionType.SNAP_FIT.value == "snap_fit"
        assert ConnectionType.SCREW.value == "screw"
        assert ConnectionType.GLUE.value == "glue"
        assert ConnectionType.PRESS_FIT.value == "press_fit"
        assert ConnectionType.THREADED.value == "threaded"


class TestAssemblyPart:
    """Tests for AssemblyPart dataclass."""

    def test_create_part(self):
        """Test creating a part."""
        part = AssemblyPart(
            name="Base Plate",
            file_path="/parts/base.stl",
            quantity=1,
            material="pla",
            color="black",
            print_time_hours=2.5,
        )

        assert part.name == "Base Plate"
        assert part.quantity == 1
        assert part.material == "pla"
        assert part.print_time_hours == 2.5

    def test_default_values(self):
        """Test default part values."""
        part = AssemblyPart(name="Part", file_path="/part.stl")

        assert part.quantity == 1
        assert part.material == "pla"
        assert part.color is None

    def test_to_dict(self):
        """Test part serialization."""
        part = AssemblyPart("Base", "/base.stl", quantity=2)
        d = part.to_dict()

        assert d["name"] == "Base"
        assert d["quantity"] == 2


class TestAssemblyStep:
    """Tests for AssemblyStep dataclass."""

    def test_create_step(self):
        """Test creating a step."""
        step = AssemblyStep(
            step_number=1,
            description="Attach base to frame",
            parts_used=["Base", "Frame"],
            connection_type=ConnectionType.SCREW,
            tools_needed=["Screwdriver"],
        )

        assert step.step_number == 1
        assert "base" in step.description.lower()
        assert len(step.parts_used) == 2
        assert step.connection_type == ConnectionType.SCREW

    def test_default_values(self):
        """Test default step values."""
        step = AssemblyStep(step_number=1, description="Test")

        assert step.parts_used == []
        assert step.tools_needed == []
        assert step.warnings == []
        assert step.tips == []
        assert step.estimated_time_minutes == 5

    def test_to_dict(self):
        """Test step serialization."""
        step = AssemblyStep(
            step_number=2,
            description="Connect parts",
            connection_type=ConnectionType.GLUE,
        )
        d = step.to_dict()

        assert d["step_number"] == 2
        assert d["connection_type"] == "glue"


class TestHardwareItem:
    """Tests for HardwareItem dataclass."""

    def test_create_hardware(self):
        """Test creating hardware item."""
        item = HardwareItem(
            name="Screw",
            specification="M3x10",
            quantity=4,
            notes="Socket head cap",
        )

        assert item.name == "Screw"
        assert item.specification == "M3x10"
        assert item.quantity == 4

    def test_to_dict(self):
        """Test hardware serialization."""
        item = HardwareItem("Nut", "M3", 4)
        d = item.to_dict()

        assert d["name"] == "Nut"
        assert d["quantity"] == 4


class TestAssemblyConfig:
    """Tests for AssemblyConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = AssemblyConfig()

        assert config.project_name == "Assembly"
        assert config.include_bom is True
        assert config.include_hardware is True
        assert config.output_format == "markdown"

    def test_custom_config(self):
        """Test custom configuration."""
        config = AssemblyConfig(
            project_name="Robot Arm",
            include_bom=False,
            output_format="html",
        )

        assert config.project_name == "Robot Arm"
        assert config.include_bom is False
        assert config.output_format == "html"

    def test_to_dict(self):
        """Test config serialization."""
        config = AssemblyConfig(project_name="Test")
        d = config.to_dict()

        assert d["project_name"] == "Test"
        assert "include_bom" in d


class TestAssemblyInstructions:
    """Tests for AssemblyInstructions dataclass."""

    def test_success_result(self):
        """Test successful result."""
        instructions = AssemblyInstructions(
            success=True,
            project_name="Test Project",
            parts=[AssemblyPart("Part1", "/p1.stl")],
            steps=[AssemblyStep(1, "Step 1")],
            total_print_time_hours=5.0,
            total_assembly_time_minutes=30,
        )

        assert instructions.success is True
        assert len(instructions.parts) == 1
        assert len(instructions.steps) == 1

    def test_failure_result(self):
        """Test failure result."""
        instructions = AssemblyInstructions(
            success=False,
            error_message="No parts provided",
        )

        assert instructions.success is False
        assert instructions.error_message == "No parts provided"

    def test_to_dict(self):
        """Test instructions serialization."""
        instructions = AssemblyInstructions(
            success=True,
            project_name="Test",
            parts=[AssemblyPart("P", "/p.stl")],
        )
        d = instructions.to_dict()

        assert d["success"] is True
        assert len(d["parts"]) == 1


class TestAssemblyGenerator:
    """Tests for AssemblyGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create an assembly generator."""
        return AssemblyGenerator()

    @pytest.fixture
    def sample_parts(self):
        """Create sample parts."""
        return [
            AssemblyPart("Base", "/base.stl", quantity=1, print_time_hours=2.0),
            AssemblyPart("Cover", "/cover.stl", quantity=1, print_time_hours=1.5),
            AssemblyPart("Button", "/button.stl", quantity=4, print_time_hours=0.25),
        ]

    def test_init(self, generator):
        """Test generator initialization."""
        assert generator.config is not None
        assert generator.config.project_name == "Assembly"

    def test_init_custom_config(self):
        """Test generator with custom config."""
        config = AssemblyConfig(project_name="Custom")
        generator = AssemblyGenerator(config=config)

        assert generator.config.project_name == "Custom"

    def test_generate_no_parts(self, generator):
        """Test generation with no parts."""
        result = generator.generate([])

        assert result.success is False
        assert "No parts" in result.error_message

    def test_generate_basic(self, generator, sample_parts):
        """Test basic generation."""
        result = generator.generate(sample_parts)

        assert result.success is True
        assert len(result.parts) == 3
        assert len(result.steps) > 0

    def test_generate_calculates_print_time(self, generator, sample_parts):
        """Test print time calculation."""
        result = generator.generate(sample_parts)

        # 2.0 + 1.5 + (4 * 0.25) = 4.5 hours
        assert result.total_print_time_hours == 4.5

    def test_generate_calculates_assembly_time(self, generator, sample_parts):
        """Test assembly time calculation."""
        result = generator.generate(sample_parts)

        assert result.total_assembly_time_minutes > 0

    def test_generate_with_custom_steps(self, generator, sample_parts):
        """Test generation with custom steps."""
        custom_steps = [
            AssemblyStep(1, "Insert base", parts_used=["Base"]),
            AssemblyStep(2, "Attach cover", parts_used=["Cover"]),
        ]

        result = generator.generate(sample_parts, steps=custom_steps)

        assert result.success is True
        assert len(result.steps) == 2

    def test_generate_with_hardware(self, generator, sample_parts):
        """Test generation with hardware."""
        hardware = [
            HardwareItem("Screw", "M3x10", 8),
            HardwareItem("Nut", "M3", 8),
        ]

        result = generator.generate(sample_parts, hardware=hardware)

        assert result.success is True
        assert len(result.hardware) == 2


class TestToolsGeneration:
    """Tests for tools requirement generation."""

    @pytest.fixture
    def generator(self):
        """Create an assembly generator."""
        return AssemblyGenerator()

    def test_tools_for_screw(self, generator):
        """Test tools for screw connection."""
        tools = generator._get_tools_for_connection(ConnectionType.SCREW)
        assert any("screwdriver" in t.lower() for t in tools)

    def test_tools_for_glue(self, generator):
        """Test tools for glue connection."""
        tools = generator._get_tools_for_connection(ConnectionType.GLUE)
        assert any("glue" in t.lower() for t in tools)

    def test_tools_for_threaded(self, generator):
        """Test tools for threaded inserts."""
        tools = generator._get_tools_for_connection(ConnectionType.THREADED)
        assert any("soldering" in t.lower() for t in tools)


class TestSafetyWarnings:
    """Tests for safety warning generation."""

    @pytest.fixture
    def generator(self):
        """Create an assembly generator."""
        return AssemblyGenerator()

    def test_glue_warning(self, generator):
        """Test glue safety warning."""
        parts = [AssemblyPart("Part", "/part.stl")]
        steps = [AssemblyStep(1, "Glue parts", connection_type=ConnectionType.GLUE)]

        warnings = generator._generate_safety_warnings(parts, steps, [])

        assert any("glue" in w.lower() for w in warnings)

    def test_threaded_warning(self, generator):
        """Test soldering iron warning."""
        parts = [AssemblyPart("Part", "/part.stl")]
        steps = [AssemblyStep(1, "Insert threads", connection_type=ConnectionType.THREADED)]

        warnings = generator._generate_safety_warnings(parts, steps, [])

        assert any("hot" in w.lower() for w in warnings)

    def test_small_parts_warning(self, generator):
        """Test small parts warning."""
        parts = [AssemblyPart("Part", "/part.stl")]
        steps = []
        hardware = [HardwareItem("Screw", "M2", 10)]

        warnings = generator._generate_safety_warnings(parts, steps, hardware)

        assert any("small parts" in w.lower() for w in warnings)


class TestExport:
    """Tests for export functionality."""

    @pytest.fixture
    def generator(self):
        """Create an assembly generator."""
        return AssemblyGenerator(AssemblyConfig(project_name="Test Project"))

    @pytest.fixture
    def sample_instructions(self, generator):
        """Create sample instructions."""
        parts = [
            AssemblyPart("Base", "/base.stl", quantity=1, print_time_hours=2.0),
            AssemblyPart("Top", "/top.stl", quantity=1, print_time_hours=1.0),
        ]
        return generator.generate(parts)

    def test_export_markdown(self, generator, sample_instructions):
        """Test markdown export."""
        md = generator.export_markdown(sample_instructions)

        assert "# Test Project" in md
        assert "Bill of Materials" in md
        assert "Base" in md
        assert "Assembly Steps" in md

    def test_export_html(self, generator, sample_instructions):
        """Test HTML export."""
        html = generator.export_html(sample_instructions)

        assert "<html>" in html
        assert "Test Project" in html
        assert "<table>" in html

    def test_save_markdown(self, generator, sample_instructions, tmp_path):
        """Test saving markdown file."""
        output_path = tmp_path / "instructions.md"
        result = generator.save(sample_instructions, str(output_path))

        assert result is True
        assert output_path.exists()
        content = output_path.read_text()
        assert "Test Project" in content

    def test_save_html(self, generator, sample_instructions, tmp_path):
        """Test saving HTML file."""
        generator.config.output_format = "html"
        output_path = tmp_path / "instructions.html"
        result = generator.save(sample_instructions, str(output_path))

        assert result is True
        assert output_path.exists()
        content = output_path.read_text()
        assert "<html>" in content


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_generator(self):
        """Test create_generator function."""
        generator = create_generator(
            project_name="My Project",
            output_format="html",
        )

        assert generator.config.project_name == "My Project"
        assert generator.config.output_format == "html"

    def test_generate_instructions(self):
        """Test generate_instructions function."""
        parts = [
            {"name": "Part1", "file_path": "/p1.stl", "quantity": 2},
            {"name": "Part2", "file_path": "/p2.stl"},
        ]

        result = generate_instructions(parts, project_name="Quick Assembly")

        assert result.success is True
        assert result.project_name == "Quick Assembly"
        assert len(result.parts) == 2


class TestIntegration:
    """Integration tests for assembly generator."""

    def test_full_workflow(self, tmp_path):
        """Test complete assembly generation workflow."""
        # Create generator
        generator = create_generator(project_name="Phone Stand")

        # Define parts
        parts = [
            AssemblyPart(
                name="Base",
                file_path="/base.stl",
                quantity=1,
                material="pla",
                color="black",
                print_time_hours=3.0,
            ),
            AssemblyPart(
                name="Support Arm",
                file_path="/arm.stl",
                quantity=2,
                material="pla",
                color="black",
                print_time_hours=1.5,
            ),
            AssemblyPart(
                name="Phone Holder",
                file_path="/holder.stl",
                quantity=1,
                material="tpu",
                color="grey",
                print_time_hours=2.0,
            ),
        ]

        # Define custom steps
        steps = [
            AssemblyStep(
                step_number=1,
                description="Print all parts",
                estimated_time_minutes=5,
            ),
            AssemblyStep(
                step_number=2,
                description="Attach support arms to base",
                parts_used=["Base", "Support Arm"],
                connection_type=ConnectionType.SNAP_FIT,
                tips=["Ensure arms click into place"],
            ),
            AssemblyStep(
                step_number=3,
                description="Slide phone holder onto arms",
                parts_used=["Phone Holder"],
                connection_type=ConnectionType.SLIDE,
            ),
        ]

        # Define hardware
        hardware = [
            HardwareItem("Rubber feet", "Self-adhesive", 4, "Optional for stability"),
        ]

        # Generate instructions
        result = generator.generate(parts, steps=steps, hardware=hardware)

        assert result.success is True
        assert result.project_name == "Phone Stand"
        assert len(result.parts) == 3
        assert len(result.steps) == 3
        # Total: 3 + 2*1.5 + 2 = 8 hours
        assert result.total_print_time_hours == 8.0

        # Export both formats
        md_path = tmp_path / "instructions.md"
        html_path = tmp_path / "instructions.html"

        generator.config.output_format = "markdown"
        generator.save(result, str(md_path))

        generator.config.output_format = "html"
        generator.save(result, str(html_path))

        assert md_path.exists()
        assert html_path.exists()

        # Verify content
        md_content = md_path.read_text()
        assert "Phone Stand" in md_content
        assert "Support Arm" in md_content
        assert "snap" in md_content.lower()
