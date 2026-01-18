"""Tests for adaptive layer height module."""

import pytest
import math
from pathlib import Path

from src.slicing.adaptive_layers import (
    AdaptiveLayerOptimizer,
    LayerConfig,
    LayerResult,
    LayerRegion,
    OptimizationStrategy,
    create_optimizer,
    analyze_layers,
)


class TestOptimizationStrategy:
    """Tests for OptimizationStrategy enum."""

    def test_strategy_values(self):
        """Test strategy values."""
        assert OptimizationStrategy.QUALITY.value == "quality"
        assert OptimizationStrategy.SPEED.value == "speed"
        assert OptimizationStrategy.BALANCED.value == "balanced"
        assert OptimizationStrategy.CUSTOM.value == "custom"


class TestLayerRegion:
    """Tests for LayerRegion dataclass."""

    def test_create_region(self):
        """Test creating a layer region."""
        region = LayerRegion(
            start_z=0.0,
            end_z=10.0,
            layer_height=0.2,
            reason="Standard region",
            curvature=0.3,
            overhang_angle=30.0,
        )

        assert region.start_z == 0.0
        assert region.end_z == 10.0
        assert region.layer_height == 0.2
        assert region.curvature == 0.3

    def test_to_dict(self):
        """Test region serialization."""
        region = LayerRegion(
            start_z=5.0,
            end_z=15.0,
            layer_height=0.12,
            reason="High detail",
        )
        d = region.to_dict()

        assert d["start_z"] == 5.0
        assert d["end_z"] == 15.0
        assert d["layer_height"] == 0.12
        assert d["reason"] == "High detail"


class TestLayerConfig:
    """Tests for LayerConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = LayerConfig()

        assert config.min_layer_height == 0.08
        assert config.max_layer_height == 0.28
        assert config.default_layer_height == 0.20
        assert config.quality_threshold == 0.5
        assert config.overhang_threshold == 45.0
        assert config.strategy == OptimizationStrategy.BALANCED
        assert config.nozzle_diameter == 0.4

    def test_custom_config(self):
        """Test custom configuration."""
        config = LayerConfig(
            min_layer_height=0.06,
            max_layer_height=0.32,
            strategy=OptimizationStrategy.SPEED,
        )

        assert config.min_layer_height == 0.06
        assert config.max_layer_height == 0.32
        assert config.strategy == OptimizationStrategy.SPEED

    def test_to_dict(self):
        """Test config serialization."""
        config = LayerConfig(strategy=OptimizationStrategy.QUALITY)
        d = config.to_dict()

        assert "min_layer_height" in d
        assert d["strategy"] == "quality"

    def test_from_dict(self):
        """Test config deserialization."""
        data = {
            "min_layer_height": 0.1,
            "max_layer_height": 0.3,
            "strategy": "speed",
        }
        config = LayerConfig.from_dict(data)

        assert config.min_layer_height == 0.1
        assert config.max_layer_height == 0.3
        assert config.strategy == OptimizationStrategy.SPEED

    def test_for_strategy_quality(self):
        """Test quality strategy preset."""
        config = LayerConfig.for_strategy(OptimizationStrategy.QUALITY)

        assert config.min_layer_height <= 0.08
        assert config.max_layer_height <= 0.20
        assert config.strategy == OptimizationStrategy.QUALITY

    def test_for_strategy_speed(self):
        """Test speed strategy preset."""
        config = LayerConfig.for_strategy(OptimizationStrategy.SPEED)

        assert config.min_layer_height >= 0.12
        assert config.max_layer_height >= 0.28
        assert config.strategy == OptimizationStrategy.SPEED

    def test_for_strategy_balanced(self):
        """Test balanced strategy preset."""
        config = LayerConfig.for_strategy(OptimizationStrategy.BALANCED)

        assert config.strategy == OptimizationStrategy.BALANCED


class TestLayerResult:
    """Tests for LayerResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        regions = [
            LayerRegion(0, 10, 0.2, "Test"),
            LayerRegion(10, 20, 0.12, "Detail"),
        ]
        result = LayerResult(
            success=True,
            regions=regions,
            total_layers=100,
            estimated_time_savings=15.0,
            quality_score=85.0,
            model_height=20.0,
        )

        assert result.success is True
        assert len(result.regions) == 2
        assert result.total_layers == 100
        assert result.quality_score == 85.0

    def test_failure_result(self):
        """Test failure result."""
        result = LayerResult(
            success=False,
            error_message="Mesh not found",
        )

        assert result.success is False
        assert result.error_message == "Mesh not found"

    def test_to_dict(self):
        """Test result serialization."""
        result = LayerResult(
            success=True,
            regions=[LayerRegion(0, 10, 0.2, "Test")],
            total_layers=50,
        )
        d = result.to_dict()

        assert d["success"] is True
        assert len(d["regions"]) == 1
        assert d["total_layers"] == 50


class TestAdaptiveLayerOptimizer:
    """Tests for AdaptiveLayerOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create an optimizer."""
        return AdaptiveLayerOptimizer()

    @pytest.fixture
    def test_mesh_obj(self, tmp_path):
        """Create a test OBJ mesh file."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("""# Test cube
v 0 0 0
v 10 0 0
v 10 10 0
v 0 10 0
v 0 0 10
v 10 0 10
v 10 10 10
v 0 10 10
f 1 2 3
f 1 3 4
f 5 6 7
f 5 7 8
f 1 2 6
f 1 6 5
f 2 3 7
f 2 7 6
f 3 4 8
f 3 8 7
f 4 1 5
f 4 5 8
""")
        return str(mesh_path)

    @pytest.fixture
    def test_mesh_stl(self, tmp_path):
        """Create a test STL mesh file."""
        mesh_path = tmp_path / "test.stl"
        mesh_path.write_text("""solid test
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 10 0 0
      vertex 10 10 0
    endloop
  endfacet
  facet normal 0 0 1
    outer loop
      vertex 0 0 10
      vertex 10 0 10
      vertex 10 10 10
    endloop
  endfacet
endsolid test
""")
        return str(mesh_path)

    def test_init(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.config is not None
        assert optimizer.config.strategy == OptimizationStrategy.BALANCED

    def test_init_custom_config(self):
        """Test optimizer with custom config."""
        config = LayerConfig(strategy=OptimizationStrategy.QUALITY)
        optimizer = AdaptiveLayerOptimizer(config=config)

        assert optimizer.config.strategy == OptimizationStrategy.QUALITY

    def test_analyze_nonexistent_mesh(self, optimizer):
        """Test analyzing non-existent mesh."""
        result = optimizer.analyze_model("/nonexistent/mesh.obj")

        assert result.success is False
        assert "not found" in result.error_message

    def test_analyze_obj_mesh(self, optimizer, test_mesh_obj):
        """Test analyzing OBJ mesh."""
        result = optimizer.analyze_model(test_mesh_obj)

        assert result.success is True
        assert result.model_height > 0
        assert len(result.regions) > 0
        assert result.total_layers > 0

    def test_analyze_stl_mesh(self, optimizer, test_mesh_stl):
        """Test analyzing STL mesh."""
        result = optimizer.analyze_model(test_mesh_stl)

        assert result.success is True
        assert result.model_height > 0

    def test_analyze_generates_regions(self, optimizer, test_mesh_obj):
        """Test that analysis generates layer regions."""
        result = optimizer.analyze_model(test_mesh_obj)

        assert result.success is True
        assert len(result.regions) > 0

        for region in result.regions:
            assert region.start_z < region.end_z
            assert region.layer_height > 0
            assert region.layer_height <= optimizer.config.max_layer_height

    def test_quality_score_in_range(self, optimizer, test_mesh_obj):
        """Test quality score is in valid range."""
        result = optimizer.analyze_model(test_mesh_obj)

        assert result.success is True
        assert 0 <= result.quality_score <= 100

    def test_different_strategies(self, test_mesh_obj):
        """Test different optimization strategies produce different results."""
        quality_opt = AdaptiveLayerOptimizer(
            LayerConfig.for_strategy(OptimizationStrategy.QUALITY)
        )
        speed_opt = AdaptiveLayerOptimizer(
            LayerConfig.for_strategy(OptimizationStrategy.SPEED)
        )

        quality_result = quality_opt.analyze_model(test_mesh_obj)
        speed_result = speed_opt.analyze_model(test_mesh_obj)

        assert quality_result.success and speed_result.success

        # Speed should use fewer layers
        assert speed_result.total_layers <= quality_result.total_layers


class TestGeometryAnalysis:
    """Tests for geometry analysis functions."""

    @pytest.fixture
    def optimizer(self):
        """Create an optimizer."""
        return AdaptiveLayerOptimizer()

    def test_load_obj_mesh(self, optimizer, tmp_path):
        """Test loading OBJ mesh."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("""v 0 0 0
v 1 0 0
v 1 1 0
f 1 2 3
""")

        vertices, faces = optimizer._load_mesh(mesh_path)

        assert len(vertices) == 3
        assert len(faces) == 1
        assert vertices[0] == (0.0, 0.0, 0.0)

    def test_load_stl_mesh(self, optimizer, tmp_path):
        """Test loading STL mesh."""
        mesh_path = tmp_path / "test.stl"
        mesh_path.write_text("""solid test
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 1 1 0
    endloop
  endfacet
endsolid test
""")

        vertices, faces = optimizer._load_mesh(mesh_path)

        assert len(vertices) == 3
        assert len(faces) == 1

    def test_get_z_bounds(self, optimizer):
        """Test getting Z bounds."""
        vertices = [(0, 0, 0), (1, 1, 5), (2, 2, 10)]

        z_min, z_max = optimizer._get_z_bounds(vertices)

        assert z_min == 0
        assert z_max == 10

    def test_get_z_bounds_empty(self, optimizer):
        """Test getting Z bounds for empty list."""
        z_min, z_max = optimizer._get_z_bounds([])

        assert z_min == 0
        assert z_max == 0

    def test_calculate_normal(self, optimizer):
        """Test face normal calculation."""
        v0 = (0, 0, 0)
        v1 = (1, 0, 0)
        v2 = (0, 1, 0)

        normal = optimizer._calculate_normal(v0, v1, v2)

        assert normal is not None
        # Normal should point in Z direction for XY plane triangle
        assert abs(normal[2]) > 0.9


class TestLayerSelection:
    """Tests for layer height selection."""

    @pytest.fixture
    def optimizer(self):
        """Create an optimizer."""
        return AdaptiveLayerOptimizer()

    def test_select_for_high_curvature(self, optimizer):
        """Test layer selection for high curvature."""
        height, reason = optimizer._select_layer_height(
            curvature=0.8,  # High
            overhang=0.0,
        )

        assert height == optimizer.config.min_layer_height
        assert "curvature" in reason.lower() or "detail" in reason.lower()

    def test_select_for_overhang(self, optimizer):
        """Test layer selection for overhangs."""
        height, reason = optimizer._select_layer_height(
            curvature=0.0,
            overhang=60.0,  # Steep overhang
        )

        # Should select finer layer for overhang
        assert height <= optimizer.config.default_layer_height

    def test_select_for_flat_region(self, optimizer):
        """Test layer selection for flat regions."""
        height, reason = optimizer._select_layer_height(
            curvature=0.05,  # Very flat
            overhang=10.0,  # Minimal overhang
        )

        assert height == optimizer.config.max_layer_height
        assert "flat" in reason.lower()


class TestRegionMerging:
    """Tests for region merging."""

    @pytest.fixture
    def optimizer(self):
        """Create an optimizer."""
        return AdaptiveLayerOptimizer()

    def test_merge_same_height(self, optimizer):
        """Test merging regions with same layer height."""
        regions = [
            LayerRegion(0, 5, 0.2, "A"),
            LayerRegion(5, 10, 0.2, "A"),
            LayerRegion(10, 15, 0.2, "A"),
        ]

        merged = optimizer._merge_regions(regions)

        assert len(merged) == 1
        assert merged[0].start_z == 0
        assert merged[0].end_z == 15

    def test_merge_different_heights(self, optimizer):
        """Test regions with different heights are not merged."""
        regions = [
            LayerRegion(0, 5, 0.2, "A"),
            LayerRegion(5, 10, 0.12, "B"),
            LayerRegion(10, 15, 0.2, "A"),
        ]

        merged = optimizer._merge_regions(regions)

        assert len(merged) == 3

    def test_merge_empty(self, optimizer):
        """Test merging empty list."""
        merged = optimizer._merge_regions([])
        assert merged == []


class TestExport:
    """Tests for export functionality."""

    @pytest.fixture
    def optimizer(self):
        """Create an optimizer."""
        return AdaptiveLayerOptimizer()

    @pytest.fixture
    def test_result(self):
        """Create a test result."""
        return LayerResult(
            success=True,
            regions=[
                LayerRegion(0, 10, 0.2, "Standard"),
                LayerRegion(10, 20, 0.12, "Detail"),
            ],
            total_layers=100,
            quality_score=85.0,
        )

    def test_export_gcode_variable_layer(self, optimizer, test_result):
        """Test exporting variable layer config."""
        output = optimizer.export_to_gcode_variable_layer(test_result)

        assert "Variable layer height" in output
        assert "Total layers: 100" in output
        assert "Quality score: 85" in output
        assert "0.20mm" in output
        assert "0.12mm" in output


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_optimizer(self):
        """Test create_optimizer function."""
        optimizer = create_optimizer(
            strategy="quality",
            min_layer=0.06,
            max_layer=0.16,
        )

        assert optimizer.config.strategy == OptimizationStrategy.QUALITY
        assert optimizer.config.min_layer_height == 0.06
        assert optimizer.config.max_layer_height == 0.16

    def test_analyze_layers(self, tmp_path):
        """Test analyze_layers convenience function."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("""v 0 0 0
v 10 0 0
v 10 10 0
v 0 0 10
f 1 2 3
f 1 2 4
""")

        result = analyze_layers(str(mesh_path), strategy="balanced")

        assert result.success is True
        assert result.model_height > 0


class TestGetLayerHeightAtZ:
    """Tests for get_layer_heights_at_z function."""

    @pytest.fixture
    def optimizer(self):
        """Create an optimizer."""
        return AdaptiveLayerOptimizer()

    @pytest.fixture
    def test_result(self):
        """Create a test result."""
        return LayerResult(
            success=True,
            regions=[
                LayerRegion(0, 10, 0.2, "A"),
                LayerRegion(10, 20, 0.12, "B"),
            ],
        )

    def test_get_height_in_first_region(self, optimizer, test_result):
        """Test getting height in first region."""
        height = optimizer.get_layer_heights_at_z(test_result, 5.0)
        assert height == 0.2

    def test_get_height_in_second_region(self, optimizer, test_result):
        """Test getting height in second region."""
        height = optimizer.get_layer_heights_at_z(test_result, 15.0)
        assert height == 0.12

    def test_get_height_outside_regions(self, optimizer, test_result):
        """Test getting height outside regions."""
        height = optimizer.get_layer_heights_at_z(test_result, 25.0)
        assert height == optimizer.config.default_layer_height


class TestIntegration:
    """Integration tests for adaptive layers."""

    @pytest.fixture
    def test_mesh(self, tmp_path):
        """Create a test mesh file."""
        mesh_path = tmp_path / "complex.obj"
        mesh_path.write_text("""# Complex test mesh
v 0 0 0
v 20 0 0
v 20 20 0
v 0 20 0
v 5 5 10
v 15 5 10
v 15 15 10
v 5 15 10
v 10 10 20
f 1 2 5
f 2 6 5
f 2 3 6
f 3 7 6
f 3 4 7
f 4 8 7
f 4 1 8
f 1 5 8
f 5 6 9
f 6 7 9
f 7 8 9
f 8 5 9
""")
        return str(mesh_path)

    def test_full_workflow(self, test_mesh):
        """Test complete adaptive layer workflow."""
        # Create optimizer
        optimizer = create_optimizer(strategy="balanced")

        # Analyze mesh
        result = optimizer.analyze_model(test_mesh)
        assert result.success is True
        assert result.model_height > 0
        assert len(result.regions) > 0

        # Check regions are valid
        for region in result.regions:
            assert region.start_z < region.end_z
            assert region.layer_height > 0

        # Export configuration
        export = optimizer.export_to_gcode_variable_layer(result)
        assert len(export) > 0
        assert "Region" in export

    def test_all_strategies(self, test_mesh):
        """Test all optimization strategies."""
        for strategy in [OptimizationStrategy.QUALITY,
                        OptimizationStrategy.SPEED,
                        OptimizationStrategy.BALANCED]:
            config = LayerConfig.for_strategy(strategy)
            optimizer = AdaptiveLayerOptimizer(config=config)
            result = optimizer.analyze_model(test_mesh)

            assert result.success is True, f"Strategy {strategy.value} failed"
            assert result.total_layers > 0
