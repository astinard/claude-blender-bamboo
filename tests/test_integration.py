"""
Integration Tests for Claude Fab Lab.

Tests the complete pipeline from model creation to print/laser export.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_materials_library():
    """Test materials library integration."""
    print("Testing: Materials Library Integration")

    from materials.library import (
        get_material, find_material, list_filaments, list_sheets,
        get_color, MaterialProperty
    )

    # Test filament lookup
    pla = get_material("pla")
    assert pla is not None, "PLA should exist"
    assert pla.nozzle_temp > 0, "PLA should have nozzle temp"

    # Test natural language alias
    rubber = find_material("rubber")
    assert rubber is not None, "Rubber alias should find TPU"

    # Test sheet lookup
    wood = get_material("wood_3mm")
    assert wood is not None, "Wood 3mm should exist"

    # Test lists
    assert len(list_filaments()) >= 10, "Should have 10+ filaments"
    assert len(list_sheets()) >= 10, "Should have 10+ sheets"

    # Test colors
    white = get_color("white")
    assert white is not None, "White color should exist"
    assert len(white) == 4, "Color should be RGBA"

    print("  ✓ All materials tests passed")
    return True


def test_laser_complete_workflow():
    """Test complete laser cutting workflow."""
    print("Testing: Complete Laser Workflow")

    from laser.cross_section import Path2D
    from laser.presets import get_preset, get_preset_for_material
    from laser.svg_export import SVGExporter
    from laser.dxf_export import DXFExporter
    from laser.job_control import LaserJobController
    from laser.path_optimizer import optimize_paths

    # Create test paths
    outer_path = Path2D(
        points=[(0, 0), (100, 0), (100, 80), (0, 80)],
        is_closed=True,
        is_outer=True
    )
    inner_path = Path2D(
        points=[(30, 30), (70, 30), (70, 50), (30, 50)],
        is_closed=True,
        is_outer=False
    )
    paths = [outer_path, inner_path]

    # Get preset
    preset = get_preset("wood_3mm_cut")
    assert preset is not None, "Wood preset should exist"
    assert preset.power > 0, "Preset should have power"

    # Optimize paths
    optimized = optimize_paths(paths, inner_first=True)
    assert optimized.stats.travel_reduction_percent >= 0, "Should optimize"
    print(f"  Path optimization: {optimized.stats.travel_reduction_percent:.1f}% reduction")

    # Create job
    controller = LaserJobController()
    job = controller.create_job("Test Job", optimized.paths, preset=preset)
    assert job is not None, "Job should be created"
    assert job.total_paths == 2, "Job should have 2 paths"

    # Export to SVG
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        controller.export_job(job, f.name, format="svg")
        svg_path = Path(f.name)
        assert svg_path.exists(), "SVG should be created"
        content = svg_path.read_text()
        assert "<svg" in content, "SVG should have svg tag"
        assert "<path" in content, "SVG should have path elements"
        svg_path.unlink()

    # Export to DXF
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        controller.export_job(job, f.name, format="dxf")
        dxf_path = Path(f.name)
        assert dxf_path.exists(), "DXF should be created"
        content = dxf_path.read_text()
        assert "LWPOLYLINE" in content, "DXF should have polylines"
        dxf_path.unlink()

    print("  ✓ All laser workflow tests passed")
    return True


def test_multicolor_print_workflow():
    """Test multi-color 3D printing workflow."""
    print("Testing: Multi-Color Print Workflow")

    from printer.ams_manager import AMSManager, FilamentInfo
    from printer.print_preview import PrintPreviewGenerator

    # Set up AMS with filaments
    ams = AMSManager()
    ams.set_slot(0, 0, FilamentInfo(
        color=(1.0, 1.0, 1.0),
        color_name="White",
        material_type="PLA"
    ))
    ams.set_slot(0, 1, FilamentInfo(
        color=(1.0, 0.0, 0.0),
        color_name="Red",
        material_type="PLA"
    ))
    ams.set_slot(0, 2, FilamentInfo(
        color=(0.0, 0.0, 1.0),
        color_name="Blue",
        material_type="PLA"
    ))

    # Generate preview
    generator = PrintPreviewGenerator(ams)
    preview = generator.generate_preview(
        model_name="Multi-Color Test",
        colors=[
            (1.0, 1.0, 1.0),  # White
            (1.0, 0.0, 0.0),  # Red
            (0.0, 1.0, 0.0),  # Green (not loaded)
        ],
        triangle_counts=[1000, 500, 200],
        total_volume_mm3=10000
    )

    assert preview is not None, "Preview should be generated"
    assert preview.color_count == 3, "Should have 3 colors"
    assert len(preview.warnings) > 0, "Should warn about missing green"

    # Check color mapping
    mapped = [c for c in preview.colors if c.mapped_slot is not None]
    assert len(mapped) >= 2, "At least 2 colors should be mapped"

    # Check estimates
    assert preview.estimated_print_time_seconds > 0, "Should estimate time"
    assert preview.estimated_filament_grams > 0, "Should estimate filament"
    assert preview.estimated_cost_usd > 0, "Should estimate cost"

    print(f"  Preview: {preview.estimated_print_time_formatted}, {preview.estimated_filament_grams:.1f}g, ${preview.estimated_cost_usd:.2f}")
    print("  ✓ All multi-color tests passed")
    return True


def test_mock_printer_simulation():
    """Test mock printer simulation."""
    print("Testing: Mock Printer Simulation")

    from printer.mock import MockPrinter
    from printer.connection import PrinterState

    printer = MockPrinter()
    assert printer.status.state == PrinterState.IDLE, "Should start idle"

    # Connect
    printer.connect()
    assert printer.is_connected, "Should be connected"

    # Upload file
    result = printer.upload_file("test.3mf", 1024)
    assert result.success, "Upload should succeed"

    # Start print
    result = printer.start_print("test.3mf")
    assert result.success, "Start should succeed"

    # Check state changed
    import time
    time.sleep(0.2)
    assert printer.status.state != PrinterState.IDLE, "State should change"

    # Stop print
    result = printer.stop_print()
    assert result.success, "Stop should succeed"
    assert printer.status.state == PrinterState.IDLE, "Should return to idle"

    # Disconnect
    printer.disconnect()
    assert not printer.is_connected, "Should be disconnected"

    print("  ✓ All mock printer tests passed")
    return True


def test_3mf_export_functions():
    """Test 3MF export functionality."""
    print("Testing: 3MF Export Functions")

    from blender.export_3mf import (
        MaterialSlot, MeshData, color_to_hex, quantize_color,
        create_content_types_xml, create_rels_xml, create_3dmodel_xml
    )

    # Create material slots
    slot1 = MaterialSlot(name="White", color=(1.0, 1.0, 1.0, 1.0), ams_slot=0)
    slot2 = MaterialSlot(name="Red", color=(1.0, 0.0, 0.0, 1.0), ams_slot=1)

    # Create mesh data
    mesh = MeshData(
        vertices=[(0, 0, 0), (10, 0, 0), (5, 10, 0), (5, 5, 10)],
        triangles=[(0, 1, 2), (0, 1, 3), (1, 2, 3), (0, 2, 3)],
        triangle_colors=[0, 0, 1, 1],  # 2 white, 2 red triangles
        materials=[slot1, slot2]
    )

    # Test color conversion
    assert color_to_hex((1.0, 0.0, 0.0, 1.0)) == "#FF0000FF", "Red hex"
    assert color_to_hex((1.0, 1.0, 1.0, 1.0)) == "#FFFFFFFF", "White hex"

    # Test color quantization
    q1 = quantize_color((0.99, 0.01, 0.02, 1.0))
    q2 = quantize_color((1.0, 0.0, 0.0, 1.0))
    assert q1 == q2, "Similar colors should quantize the same"

    # Test XML generation
    content_xml = create_content_types_xml()
    assert "[Content_Types]" in content_xml or "ContentType" in content_xml

    rels_xml = create_rels_xml()
    assert "Relationships" in rels_xml

    model_xml = create_3dmodel_xml(mesh)
    assert "vertex" in model_xml.lower(), "Should have vertices"
    assert "triangle" in model_xml.lower(), "Should have triangles"

    print("  ✓ All 3MF export tests passed")
    return True


def test_command_interpreter():
    """Test natural language command interpretation."""
    print("Testing: Command Interpreter")

    from blender.command_interpreter import interpret_command, parse_measurement, to_mm

    # Test measurement parsing
    val, unit = parse_measurement("5 mm")
    assert val == 5.0 and unit == "mm"

    val, unit = parse_measurement("10cm")
    assert val == 10.0

    # Test unit conversion
    assert to_mm(1, "cm") == 10
    assert to_mm(1, "m") == 1000
    assert to_mm(1, "inches") == 25.4  # 1 inch = 25.4mm

    # Test command interpretation
    cmd = interpret_command("scale by 2")
    assert cmd is not None and cmd.get("action") == "scale"

    cmd = interpret_command("rotate 45 degrees")
    assert cmd is not None and cmd.get("action") == "rotate"

    cmd = interpret_command("export to stl")
    assert cmd is not None and cmd.get("action") == "export"

    print("  ✓ All command interpreter tests passed")
    return True


def test_mesh_repair():
    """Test mesh repair analysis."""
    print("Testing: Mesh Repair Analysis")

    from blender.mesh_repair import (
        MeshAnalyzer, MeshAnalysis, MeshIssueType, RepairSeverity,
        analyze_mesh, format_analysis
    )

    # Create a mesh with issues (cube missing one face = hole)
    vertices = [
        (0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),  # bottom
        (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10),  # top
    ]
    # Missing front face creates a hole
    faces = [
        (0, 1, 2), (0, 2, 3),  # bottom
        (4, 6, 5), (4, 7, 6),  # top
        (0, 4, 5), (0, 5, 1),  # front
        (2, 6, 7), (2, 7, 3),  # back
        (0, 3, 7), (0, 7, 4),  # left
        # right face missing - creates hole
    ]

    # Analyze mesh
    analyzer = MeshAnalyzer()
    analysis = analyzer.analyze_mesh_data(vertices, faces)

    assert analysis is not None, "Analysis should be returned"
    assert not analysis.is_watertight, "Mesh with missing face should not be watertight"

    # Check issue detection
    hole_issues = [i for i in analysis.issues if i.issue_type == MeshIssueType.HOLE]
    assert len(hole_issues) >= 1, "Should detect hole from missing face"

    # Test convenience function
    analysis2 = analyze_mesh(vertices, faces)
    assert analysis2 is not None, "Convenience function should work"

    # Test formatting
    formatted = format_analysis(analysis)
    assert "watertight" in formatted.lower() or "hole" in formatted.lower(), "Format should include status"

    print(f"  Found {len(analysis.issues)} issues in test mesh")
    print("  ✓ All mesh repair tests passed")
    return True


def test_latency_requirements():
    """Test that operations meet latency requirements (<5ms)."""
    print("Testing: Latency Requirements")

    import time
    from materials.library import get_material
    from laser.presets import get_preset
    from laser.svg_export import SVGExporter
    from laser.cross_section import Path2D

    # Test material lookup (1000 iterations)
    start = time.perf_counter()
    for _ in range(1000):
        get_material("pla")
    elapsed_material = (time.perf_counter() - start) / 1000 * 1000  # ms per lookup
    assert elapsed_material < 5, f"Material lookup too slow: {elapsed_material:.2f}ms"

    # Test preset lookup
    start = time.perf_counter()
    for _ in range(1000):
        get_preset("wood_3mm_cut")
    elapsed_preset = (time.perf_counter() - start) / 1000 * 1000
    assert elapsed_preset < 5, f"Preset lookup too slow: {elapsed_preset:.2f}ms"

    # Test SVG generation
    paths = [Path2D(points=[(0, 0), (10, 0), (10, 10), (0, 10)], is_closed=True)]
    exporter = SVGExporter()
    start = time.perf_counter()
    for _ in range(100):
        exporter.paths_to_svg(paths)
    elapsed_svg = (time.perf_counter() - start) / 100 * 1000
    assert elapsed_svg < 5, f"SVG generation too slow: {elapsed_svg:.2f}ms"

    print(f"  Material lookup: {elapsed_material:.3f}ms")
    print(f"  Preset lookup: {elapsed_preset:.3f}ms")
    print(f"  SVG generation: {elapsed_svg:.3f}ms")
    print("  ✓ All latency tests passed")
    return True


def run_all_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("INTEGRATION TEST SUITE")
    print("=" * 60)
    print()

    tests = [
        test_materials_library,
        test_laser_complete_workflow,
        test_multicolor_print_workflow,
        test_mock_printer_simulation,
        test_3mf_export_functions,
        test_command_interpreter,
        test_mesh_repair,
        test_latency_requirements,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
