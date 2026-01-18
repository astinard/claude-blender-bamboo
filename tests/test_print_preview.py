"""Tests for print preview functionality."""

import pytest
from pathlib import Path
import tempfile

from src.printer.print_preview import (
    PrintPreview,
    AMSSlotConfig,
    PrintEstimate,
    generate_preview,
    export_preview_html,
    create_ams_config,
    FILAMENT_COLORS,
)


class TestAMSSlotConfig:
    """Tests for AMS slot configuration."""

    def test_create_slot(self):
        """Test creating an AMS slot."""
        slot = AMSSlotConfig(
            slot=1,
            material="pla",
            color="white",
            brand="Bambu",
        )
        assert slot.slot == 1
        assert slot.material == "pla"
        assert slot.color == "white"
        assert slot.brand == "Bambu"

    def test_color_hex_named(self):
        """Test color hex for named colors."""
        slot = AMSSlotConfig(slot=1, material="pla", color="white")
        assert slot.color_hex == "#FFFFFF"

        slot2 = AMSSlotConfig(slot=1, material="pla", color="red")
        assert slot2.color_hex == "#E63946"

    def test_color_hex_custom(self):
        """Test custom hex color."""
        slot = AMSSlotConfig(slot=1, material="pla", color="#FF00FF")
        assert slot.color_hex == "#FF00FF"

    def test_color_hex_unknown(self):
        """Test unknown color defaults to gray."""
        slot = AMSSlotConfig(slot=1, material="pla", color="unicorn-sparkle")
        assert slot.color_hex == "#808080"

    def test_material_obj(self):
        """Test getting material object."""
        slot = AMSSlotConfig(slot=1, material="pla", color="white")
        mat = slot.material_obj
        assert mat is not None
        assert mat.name == "PLA"

    def test_material_obj_unknown(self):
        """Test material object for unknown material."""
        slot = AMSSlotConfig(slot=1, material="unknown", color="white")
        assert slot.material_obj is None


class TestCreateAMSConfig:
    """Tests for AMS config helper."""

    def test_single_material(self):
        """Test creating config for single material."""
        config = create_ams_config(["pla"])
        assert len(config) == 1
        assert config[0].slot == 1
        assert config[0].material == "pla"

    def test_multiple_materials(self):
        """Test creating config for multiple materials."""
        config = create_ams_config(["pla", "petg", "abs"])
        assert len(config) == 3
        assert config[0].slot == 1
        assert config[1].slot == 2
        assert config[2].slot == 3

    def test_with_colors(self):
        """Test creating config with colors."""
        config = create_ams_config(
            materials=["pla", "petg"],
            colors=["white", "blue"],
        )
        assert config[0].color == "white"
        assert config[1].color == "blue"

    def test_with_brands(self):
        """Test creating config with brands."""
        config = create_ams_config(
            materials=["pla"],
            brands=["Bambu"],
        )
        assert config[0].brand == "Bambu"


class TestPrintPreview:
    """Tests for PrintPreview class."""

    def test_get_slot(self):
        """Test getting slot by number."""
        preview = PrintPreview(
            filename="test.stl",
            ams_slots=[
                AMSSlotConfig(slot=1, material="pla", color="white"),
                AMSSlotConfig(slot=2, material="petg", color="black"),
            ],
        )
        slot = preview.get_slot(1)
        assert slot is not None
        assert slot.material == "pla"

        slot2 = preview.get_slot(3)
        assert slot2 is None

    def test_get_materials(self):
        """Test getting materials list."""
        preview = PrintPreview(
            filename="test.stl",
            ams_slots=create_ams_config(["pla", "petg"]),
        )
        mats = preview.get_materials()
        assert mats == ["pla", "petg"]

    def test_get_color_preview(self):
        """Test getting color preview mapping."""
        preview = PrintPreview(
            filename="test.stl",
            ams_slots=create_ams_config(["pla", "petg"], ["white", "black"]),
        )
        colors = preview.get_color_preview()
        assert colors[1] == "#FFFFFF"
        assert colors[2] == "#1A1A1A"

    def test_to_dict(self):
        """Test dictionary serialization."""
        preview = PrintPreview(
            filename="test.stl",
            ams_slots=create_ams_config(["pla"]),
            warnings=["Test warning"],
            compatibility_level="excellent",
        )
        d = preview.to_dict()
        assert d["filename"] == "test.stl"
        assert len(d["ams_slots"]) == 1
        assert d["warnings"] == ["Test warning"]
        assert d["compatibility_level"] == "excellent"


class TestGeneratePreview:
    """Tests for preview generation."""

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a temporary STL file."""
        stl_file = tmp_path / "test.stl"
        # Write minimal ASCII STL
        stl_content = """solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 0 1 0
  endloop
endfacet
endsolid test
"""
        stl_file.write_text(stl_content)
        return stl_file

    def test_generate_basic_preview(self, temp_stl):
        """Test generating basic preview."""
        config = create_ams_config(["pla"], ["white"])
        preview = generate_preview(str(temp_stl), config)

        assert preview.filename == "test.stl"
        assert len(preview.ams_slots) == 1

    def test_generate_multi_material_preview(self, temp_stl):
        """Test preview with multiple materials."""
        config = create_ams_config(["pla", "petg", "pva"], ["white", "black", "natural"])
        preview = generate_preview(str(temp_stl), config)

        assert len(preview.ams_slots) == 3
        assert preview.compatibility_level is not None

    def test_preview_with_abrasive_material(self, temp_stl):
        """Test preview warns about abrasive materials."""
        config = create_ams_config(["carbon_pla"], ["black"])
        preview = generate_preview(str(temp_stl), config)

        assert any("hardened" in w.lower() for w in preview.warnings)

    def test_preview_with_toxic_material(self, temp_stl):
        """Test preview warns about toxic fumes."""
        config = create_ams_config(["abs"], ["black"])
        preview = generate_preview(str(temp_stl), config)

        assert any("ventilation" in w.lower() for w in preview.warnings)


class TestExportHTML:
    """Tests for HTML export."""

    def test_export_html(self, tmp_path):
        """Test exporting HTML preview."""
        preview = PrintPreview(
            filename="test.stl",
            ams_slots=create_ams_config(["pla", "petg"], ["white", "blue"]),
            warnings=["Test warning"],
            compatibility_level="good",
        )

        output_path = tmp_path / "preview.html"
        result = export_preview_html(preview, str(output_path))

        assert Path(result).exists()
        content = Path(result).read_text()

        # Check content
        assert "test.stl" in content
        assert "PLA" in content
        assert "PETG" in content
        assert "Test warning" in content
        assert "GOOD" in content

    def test_export_html_with_estimate(self, tmp_path):
        """Test HTML export includes estimate."""
        preview = PrintPreview(
            filename="test.stl",
            ams_slots=create_ams_config(["pla"]),
            estimate=PrintEstimate(
                total_time_seconds=3661,  # 1h 1m 1s
                material_usage_grams={1: 50.0},
                total_layers=100,
                max_z_height=25.5,
                print_volume=(50, 50, 25.5),
            ),
        )

        output_path = tmp_path / "preview.html"
        result = export_preview_html(preview, str(output_path))
        content = Path(result).read_text()

        assert "100" in content  # layers
        assert "25.5" in content  # height


class TestFilamentColors:
    """Tests for filament color database."""

    def test_common_colors_exist(self):
        """Test common colors are defined."""
        assert "white" in FILAMENT_COLORS
        assert "black" in FILAMENT_COLORS
        assert "red" in FILAMENT_COLORS
        assert "blue" in FILAMENT_COLORS

    def test_color_format(self):
        """Test colors are valid hex codes."""
        for name, color in FILAMENT_COLORS.items():
            if not color.startswith("rgba"):
                assert color.startswith("#")
                assert len(color) == 7
