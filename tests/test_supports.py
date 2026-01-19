"""Tests for support generation and optimization."""

import pytest
from pathlib import Path

from src.blender.support_generator import (
    SupportGenerator,
    SupportSettings,
    SupportResult,
    SupportStructure,
    SupportPoint,
    SupportType,
    SupportDensity,
    SupportPattern,
)
from src.blender.support_optimizer import (
    SupportOptimizer,
    OptimizationSettings,
    OptimizationResult,
    OptimizationGoal,
    generate_optimized_supports,
    compare_support_strategies,
)


class TestSupportType:
    """Tests for SupportType enum."""

    def test_support_type_values(self):
        """Test support type enum values."""
        assert SupportType.NORMAL.value == "normal"
        assert SupportType.TREE.value == "tree"
        assert SupportType.LINEAR.value == "linear"


class TestSupportDensity:
    """Tests for SupportDensity enum."""

    def test_density_values(self):
        """Test density enum values."""
        assert SupportDensity.SPARSE.value == "sparse"
        assert SupportDensity.NORMAL.value == "normal"
        assert SupportDensity.DENSE.value == "dense"


class TestSupportSettings:
    """Tests for SupportSettings dataclass."""

    def test_default_settings(self):
        """Test default settings."""
        settings = SupportSettings()

        assert settings.support_type == SupportType.TREE
        assert settings.density == SupportDensity.NORMAL
        assert settings.overhang_angle == 45.0

    def test_density_percent(self):
        """Test density percentage calculation."""
        sparse = SupportSettings(density=SupportDensity.SPARSE)
        normal = SupportSettings(density=SupportDensity.NORMAL)
        dense = SupportSettings(density=SupportDensity.DENSE)

        assert sparse.density_percent == 0.10
        assert normal.density_percent == 0.15
        assert dense.density_percent == 0.20

    def test_custom_settings(self):
        """Test custom settings."""
        settings = SupportSettings(
            support_type=SupportType.NORMAL,
            density=SupportDensity.DENSE,
            overhang_angle=50.0,
            tower_diameter=4.0,
        )

        assert settings.support_type == SupportType.NORMAL
        assert settings.overhang_angle == 50.0


class TestSupportPoint:
    """Tests for SupportPoint dataclass."""

    def test_create_support_point(self):
        """Test creating a support point."""
        point = SupportPoint(
            position=(10.0, 20.0, 30.0),
            overhang_angle=60.0,
            area=25.0,
        )

        assert point.position == (10.0, 20.0, 30.0)
        assert point.overhang_angle == 60.0
        assert not point.needs_reinforcement


class TestSupportStructure:
    """Tests for SupportStructure dataclass."""

    def test_create_structure(self):
        """Test creating a support structure."""
        structure = SupportStructure(
            structure_id="test123",
            support_type=SupportType.TREE,
            points=[SupportPoint((0, 0, 10), 60, 25)],
            base_position=(0, 0, 0),
            height=10.0,
            volume=100.0,
        )

        assert structure.structure_id == "test123"
        assert structure.support_type == SupportType.TREE
        assert structure.height == 10.0

    def test_structure_to_dict(self):
        """Test structure serialization."""
        structure = SupportStructure(
            structure_id="test123",
            support_type=SupportType.TREE,
            points=[],
            base_position=(5, 5, 0),
            height=15.0,
            volume=150.0,
            estimated_material_grams=0.186,
        )

        d = structure.to_dict()
        assert d["id"] == "test123"
        assert d["type"] == "tree"
        assert d["height"] == 15.0


class TestSupportGenerator:
    """Tests for SupportGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a generator instance."""
        return SupportGenerator()

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file with overhangs."""
        stl_file = tmp_path / "test_overhang.stl"
        stl_file.write_text("""solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 50 0 0
    vertex 25 50 0
  endloop
endfacet
facet normal 0.7 0 -0.7
  outer loop
    vertex 0 0 10
    vertex 50 0 10
    vertex 25 50 15
  endloop
endfacet
endsolid test""")
        return str(stl_file)

    def test_generate_file_not_found(self, generator):
        """Test generating for non-existent file."""
        with pytest.raises(FileNotFoundError):
            generator.generate("/nonexistent/file.stl")

    def test_generate_returns_result(self, generator, temp_stl):
        """Test generate returns SupportResult."""
        result = generator.generate(temp_stl)

        assert isinstance(result, SupportResult)
        assert result.file_path == temp_stl

    def test_generate_tree_supports(self, temp_stl):
        """Test generating tree supports."""
        settings = SupportSettings(support_type=SupportType.TREE)
        generator = SupportGenerator(settings)
        result = generator.generate(temp_stl)

        for struct in result.structures:
            assert struct.support_type == SupportType.TREE

    def test_generate_normal_supports(self, temp_stl):
        """Test generating normal supports."""
        settings = SupportSettings(support_type=SupportType.NORMAL)
        generator = SupportGenerator(settings)
        result = generator.generate(temp_stl)

        for struct in result.structures:
            assert struct.support_type == SupportType.NORMAL

    def test_result_has_volume(self, generator, temp_stl):
        """Test result includes volume calculation."""
        result = generator.generate(temp_stl)

        assert result.total_support_volume >= 0

    def test_result_has_material_grams(self, generator, temp_stl):
        """Test result includes material calculation."""
        result = generator.generate(temp_stl)

        assert result.total_material_grams >= 0

    def test_compare_support_types(self, generator, temp_stl):
        """Test comparing support types."""
        comparison = generator.compare_support_types(temp_stl)

        assert "comparison" in comparison
        assert "normal" in comparison["comparison"]
        assert "tree" in comparison["comparison"]
        assert "recommendation" in comparison


class TestOptimizationGoal:
    """Tests for OptimizationGoal enum."""

    def test_goal_values(self):
        """Test optimization goal values."""
        assert OptimizationGoal.MATERIAL.value == "material"
        assert OptimizationGoal.STRENGTH.value == "strength"
        assert OptimizationGoal.BALANCED.value == "balanced"


class TestOptimizationSettings:
    """Tests for OptimizationSettings dataclass."""

    def test_default_settings(self):
        """Test default optimization settings."""
        settings = OptimizationSettings()

        assert settings.goal == OptimizationGoal.BALANCED
        assert settings.target_material_reduction == 0.4
        assert settings.remove_redundant is True

    def test_custom_settings(self):
        """Test custom optimization settings."""
        settings = OptimizationSettings(
            goal=OptimizationGoal.MATERIAL,
            target_material_reduction=0.5,
            merge_distance=8.0,
        )

        assert settings.goal == OptimizationGoal.MATERIAL
        assert settings.merge_distance == 8.0


class TestSupportOptimizer:
    """Tests for SupportOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create an optimizer instance."""
        return SupportOptimizer()

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_file.write_text("""solid test
facet normal 0.7 0 -0.7
  outer loop
    vertex 0 0 10
    vertex 50 0 10
    vertex 25 50 15
  endloop
endfacet
endsolid test""")
        return str(stl_file)

    @pytest.fixture
    def support_result(self, temp_stl):
        """Generate a support result for testing."""
        generator = SupportGenerator()
        return generator.generate(temp_stl)

    def test_optimize_returns_result(self, optimizer, support_result):
        """Test optimize returns OptimizationResult."""
        result = optimizer.optimize(support_result)

        assert isinstance(result, OptimizationResult)
        assert result.original is support_result
        assert result.optimized is not None

    def test_optimize_with_material_goal(self, optimizer, support_result):
        """Test optimization with material goal."""
        result = optimizer.optimize(support_result, goal=OptimizationGoal.MATERIAL)

        # Material optimization should reduce volume
        assert result.optimized.total_support_volume <= result.original.total_support_volume

    def test_optimize_with_strength_goal(self, optimizer, support_result):
        """Test optimization with strength goal."""
        result = optimizer.optimize(support_result, goal=OptimizationGoal.STRENGTH)

        assert isinstance(result, OptimizationResult)

    def test_optimize_tracks_changes(self, optimizer, support_result):
        """Test optimization tracks changes made."""
        result = optimizer.optimize(support_result)

        assert hasattr(result, "supports_merged")
        assert hasattr(result, "supports_removed")
        assert hasattr(result, "supports_reinforced")

    def test_optimize_includes_warnings(self, optimizer, support_result):
        """Test optimization includes warnings."""
        result = optimizer.optimize(support_result)

        assert isinstance(result.warnings, list)
        assert isinstance(result.recommendations, list)


class TestGenerateOptimizedSupports:
    """Tests for convenience function."""

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_file.write_text("solid test\nendsolid test")
        return str(stl_file)

    def test_generate_optimized_supports(self, temp_stl):
        """Test one-step generation and optimization."""
        result = generate_optimized_supports(temp_stl)

        assert isinstance(result, OptimizationResult)
        assert result.original is not None
        assert result.optimized is not None

    def test_generate_with_tree_type(self, temp_stl):
        """Test with tree support type."""
        result = generate_optimized_supports(
            temp_stl,
            support_type=SupportType.TREE,
        )

        assert isinstance(result, OptimizationResult)

    def test_generate_with_goal(self, temp_stl):
        """Test with specific optimization goal."""
        result = generate_optimized_supports(
            temp_stl,
            goal=OptimizationGoal.SPEED,
        )

        assert isinstance(result, OptimizationResult)


class TestCompareSupportStrategies:
    """Tests for strategy comparison function."""

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file."""
        stl_file = tmp_path / "compare.stl"
        stl_file.write_text("solid test\nendsolid test")
        return str(stl_file)

    def test_compare_strategies(self, temp_stl):
        """Test comparing support strategies."""
        comparison = compare_support_strategies(temp_stl)

        assert "file" in comparison
        assert "strategies" in comparison
        assert "recommendation" in comparison

    def test_compare_includes_all_strategies(self, temp_stl):
        """Test comparison includes all strategies."""
        comparison = compare_support_strategies(temp_stl)

        strategies = comparison["strategies"]
        assert "normal" in strategies
        assert "tree" in strategies
        assert "optimized_tree" in strategies

    def test_compare_includes_metrics(self, temp_stl):
        """Test comparison includes metrics for each strategy."""
        comparison = compare_support_strategies(temp_stl)

        for name, data in comparison["strategies"].items():
            assert "volume_mm3" in data
            assert "material_grams" in data
            assert "structures" in data


class TestIntegration:
    """Integration tests for support generation workflow."""

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a more complex test STL."""
        stl_file = tmp_path / "complex.stl"
        stl_file.write_text("""solid complex
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 100 0 0
    vertex 50 100 0
  endloop
endfacet
facet normal 0.866 0 -0.5
  outer loop
    vertex 0 0 20
    vertex 50 0 20
    vertex 25 50 25
  endloop
endfacet
facet normal 0.866 0 -0.5
  outer loop
    vertex 50 0 20
    vertex 100 0 20
    vertex 75 50 25
  endloop
endfacet
endsolid complex""")
        return str(stl_file)

    def test_full_workflow(self, temp_stl):
        """Test complete support generation workflow."""
        # Generate supports
        generator = SupportGenerator(SupportSettings(support_type=SupportType.TREE))
        support_result = generator.generate(temp_stl)

        assert support_result.total_support_volume >= 0

        # Optimize
        optimizer = SupportOptimizer()
        opt_result = optimizer.optimize(support_result, goal=OptimizationGoal.BALANCED)

        assert opt_result.optimized.total_support_volume >= 0

        # Compare strategies
        comparison = compare_support_strategies(temp_stl)
        assert "recommendation" in comparison

    def test_tree_vs_normal_savings(self, temp_stl):
        """Test that tree supports save material vs normal."""
        normal_gen = SupportGenerator(SupportSettings(support_type=SupportType.NORMAL))
        tree_gen = SupportGenerator(SupportSettings(support_type=SupportType.TREE))

        normal_result = normal_gen.generate(temp_stl)
        tree_result = tree_gen.generate(temp_stl)

        # Tree supports should use less or equal material
        assert tree_result.total_material_grams <= normal_result.total_material_grams * 1.1  # Allow 10% tolerance
