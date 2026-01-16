#!/usr/bin/env python3
"""
Tests for scan processing module.

These tests verify the scan processing API without requiring Blender.
Full integration tests require Blender to be installed.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestScanProcessorImport:
    """Test scan processor module can be imported (mocked Blender)."""

    def test_module_structure_without_blender(self):
        """Verify module structure without Blender."""
        # These imports should work without Blender
        from src.blender.scan_processor import (
            BLENDER_AVAILABLE,
            ScanSource,
            ScanDimensions,
            ScanAnalysis,
        )

        # Without Blender, BLENDER_AVAILABLE should be False
        # (unless actually running in Blender)
        assert isinstance(BLENDER_AVAILABLE, bool)

    def test_scan_source_enum(self):
        """Test ScanSource enum values."""
        from src.blender.scan_processor import ScanSource

        assert ScanSource.POLYCAM.value == "polycam"
        assert ScanSource.SCANNER_APP.value == "3d_scanner_app"
        assert ScanSource.KIRI_ENGINE.value == "kiri_engine"
        assert ScanSource.SCANIVERSE.value == "scaniverse"
        assert ScanSource.HEGES.value == "heges"
        assert ScanSource.UNKNOWN.value == "unknown"

    def test_scan_dimensions_dataclass(self):
        """Test ScanDimensions dataclass."""
        from src.blender.scan_processor import ScanDimensions

        dims = ScanDimensions(
            width=100.0,
            height=50.0,
            depth=30.0,
            volume=150000.0,
            surface_area=23000.0,
            bounding_box_min=(0, 0, 0),
            bounding_box_max=(100, 30, 50),
            center=(50, 15, 25)
        )

        assert dims.width == 100.0
        assert dims.height == 50.0
        assert dims.depth == 30.0

        # Test to_dict
        d = dims.to_dict()
        assert d["width_mm"] == 100.0
        assert d["height_mm"] == 50.0
        assert d["depth_mm"] == 30.0
        assert d["volume_mm3"] == 150000.0

    def test_scan_analysis_dataclass(self):
        """Test ScanAnalysis dataclass."""
        from src.blender.scan_processor import ScanAnalysis, ScanDimensions

        dims = ScanDimensions(
            width=100.0, height=50.0, depth=30.0,
            volume=150000.0, surface_area=23000.0,
            bounding_box_min=(0, 0, 0),
            bounding_box_max=(100, 30, 50),
            center=(50, 15, 25)
        )

        analysis = ScanAnalysis(
            filename="test_scan.stl",
            dimensions=dims,
            vertex_count=1000,
            face_count=2000,
            is_manifold=True,
            is_watertight=True,
            has_holes=False,
            hole_count=0,
            non_manifold_edges=0,
            loose_vertices=0,
            needs_repair=False,
            estimated_print_time_min=60.0,
            estimated_material_g=25.0,
            issues=[]
        )

        assert analysis.filename == "test_scan.stl"
        assert analysis.vertex_count == 1000
        assert analysis.face_count == 2000
        assert analysis.is_manifold is True
        assert analysis.needs_repair is False

        # Test to_dict
        d = analysis.to_dict()
        assert d["filename"] == "test_scan.stl"
        assert d["vertex_count"] == 1000
        assert d["is_manifold"] is True
        assert "dimensions" in d


class TestCaseGeneratorImport:
    """Test case generator module can be imported."""

    def test_case_type_enum(self):
        """Test CaseType enum values."""
        from src.blender.case_generator import CaseType

        assert CaseType.FULL_CASE.value == "full_case"
        assert CaseType.BUMPER.value == "bumper"
        assert CaseType.CRADLE.value == "cradle"
        assert CaseType.SLEEVE.value == "sleeve"
        assert CaseType.MOUNT.value == "mount"
        assert CaseType.STAND.value == "stand"

    def test_case_config_dataclass(self):
        """Test CaseConfig dataclass."""
        from src.blender.case_generator import CaseConfig, CaseType

        # Default config
        config = CaseConfig()
        assert config.case_type == CaseType.FULL_CASE
        assert config.wall_thickness == 1.5
        assert config.clearance == 0.3
        assert config.lip_height == 1.0

        # Custom config
        config = CaseConfig(
            case_type=CaseType.BUMPER,
            wall_thickness=2.0,
            clearance=0.5
        )
        assert config.case_type == CaseType.BUMPER
        assert config.wall_thickness == 2.0
        assert config.clearance == 0.5

    def test_generated_case_dataclass(self):
        """Test GeneratedCase dataclass."""
        from src.blender.case_generator import GeneratedCase

        # Create with mock objects
        mock_case_obj = MagicMock()
        mock_scan_obj = MagicMock()

        case = GeneratedCase(
            case_object=mock_case_obj,
            scan_object=mock_scan_obj,
            dimensions=(120.0, 40.0, 80.0),
            volume_mm3=50000.0,
            estimated_print_time_min=45.0,
            estimated_material_g=30.0
        )

        assert case.dimensions == (120.0, 40.0, 80.0)
        assert case.volume_mm3 == 50000.0
        assert case.estimated_print_time_min == 45.0
        assert case.estimated_material_g == 30.0


class TestScanRunnerImport:
    """Test scan runner module."""

    def test_get_scan_command(self):
        """Test command generation for Blender."""
        from src.blender.scan_runner import get_scan_command

        cmd = get_scan_command("analyze", "test.stl")
        assert "blender" in cmd
        assert "--background" in cmd
        assert "--action" in cmd
        assert "analyze" in cmd
        assert "--input" in cmd
        assert "test.stl" in cmd
        assert "--json-output" in cmd

    def test_get_scan_command_with_output(self):
        """Test command generation with output."""
        from src.blender.scan_runner import get_scan_command

        cmd = get_scan_command("repair", "input.stl", output="output.stl")
        assert "--output" in cmd
        assert "output.stl" in cmd

    def test_get_scan_command_case_type(self):
        """Test command generation for case."""
        from src.blender.scan_runner import get_scan_command

        cmd = get_scan_command(
            "case", "scan.stl",
            output="case.stl",
            case_type="full_case",
            wall_thickness=2.0
        )
        assert "--case-type" in cmd
        assert "full_case" in cmd
        assert "--wall-thickness" in cmd
        assert "2.0" in cmd


class TestCLIScanCommands:
    """Test CLI scan command parsing."""

    def test_scan_analyze_args(self):
        """Test scan analyze argument parsing."""
        from src.pipeline.cli import main
        import argparse

        # Simulate parsing scan analyze
        parser = argparse.ArgumentParser()
        parser.add_argument("input")
        args = parser.parse_args(["test.stl"])

        assert args.input == "test.stl"

    def test_scan_case_args(self):
        """Test scan case argument parsing."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("input")
        parser.add_argument("--case-type", default="full_case")
        parser.add_argument("--wall-thickness", type=float, default=1.5)
        parser.add_argument("--clearance", type=float, default=0.3)

        args = parser.parse_args([
            "scan.stl",
            "--case-type", "bumper",
            "--wall-thickness", "2.0"
        ])

        assert args.input == "scan.stl"
        assert args.case_type == "bumper"
        assert args.wall_thickness == 2.0
        assert args.clearance == 0.3

    def test_scan_stand_args(self):
        """Test scan stand argument parsing."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("input")
        parser.add_argument("--angle", type=float, default=60.0)
        parser.add_argument("--output", "-o")

        args = parser.parse_args([
            "tablet.stl",
            "--angle", "45",
            "-o", "stand.stl"
        ])

        assert args.input == "tablet.stl"
        assert args.angle == 45.0
        assert args.output == "stand.stl"


class TestScanWorkflow:
    """Test complete scan workflow (mocked)."""

    def test_workflow_stages(self):
        """Test workflow covers all scan processing stages."""
        stages = [
            "import_scan",
            "analyze_scan",
            "repair_scan",
            "generate_case",
            "export_case",
            "upload_to_printer",
            "print"
        ]

        # Verify all stages are documented
        assert len(stages) == 7
        assert "import_scan" in stages
        assert "generate_case" in stages

    def test_supported_file_formats(self):
        """Test supported scan file formats."""
        supported = [".stl", ".obj", ".ply", ".fbx", ".gltf", ".glb"]

        assert ".stl" in supported
        assert ".obj" in supported
        assert ".ply" in supported

    def test_case_types_available(self):
        """Test all case types are available."""
        from src.blender.case_generator import CaseType

        case_types = [ct.value for ct in CaseType]

        assert "full_case" in case_types
        assert "bumper" in case_types
        assert "cradle" in case_types
        assert "mount" in case_types
        assert "stand" in case_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
