"""Tests for cost optimizer module."""

import pytest
from pathlib import Path

from src.estimator.cost_optimizer import (
    CostOptimizer,
    CostConfig,
    CostEstimate,
    PrintSettings,
    OptimizationResult,
    create_optimizer,
    estimate_cost,
)


class TestPrintSettings:
    """Tests for PrintSettings dataclass."""

    def test_default_settings(self):
        """Test default print settings."""
        settings = PrintSettings()

        assert settings.layer_height == 0.20
        assert settings.infill_percent == 20
        assert settings.wall_count == 3
        assert settings.supports is False
        assert settings.brim is False

    def test_custom_settings(self):
        """Test custom print settings."""
        settings = PrintSettings(
            layer_height=0.12,
            infill_percent=50,
            supports=True,
        )

        assert settings.layer_height == 0.12
        assert settings.infill_percent == 50
        assert settings.supports is True

    def test_to_dict(self):
        """Test settings serialization."""
        settings = PrintSettings(layer_height=0.16)
        d = settings.to_dict()

        assert d["layer_height"] == 0.16
        assert "infill_percent" in d


class TestCostConfig:
    """Tests for CostConfig dataclass."""

    def test_default_config(self):
        """Test default cost configuration."""
        config = CostConfig()

        assert config.pla_cost_per_gram == 0.025
        assert config.electricity_cost_per_kwh == 0.12
        assert config.printer_power_watts == 150.0

    def test_get_material_cost(self):
        """Test getting material cost."""
        config = CostConfig()

        assert config.get_material_cost("pla") == 0.025
        assert config.get_material_cost("petg") == 0.030
        assert config.get_material_cost("abs") == 0.028
        assert config.get_material_cost("tpu") == 0.045

    def test_get_material_cost_unknown(self):
        """Test getting cost for unknown material."""
        config = CostConfig()

        # Should default to PLA
        assert config.get_material_cost("unknown") == 0.025

    def test_to_dict(self):
        """Test config serialization."""
        config = CostConfig()
        d = config.to_dict()

        assert "pla_cost_per_gram" in d
        assert "electricity_cost_per_kwh" in d


class TestCostEstimate:
    """Tests for CostEstimate dataclass."""

    def test_create_estimate(self):
        """Test creating cost estimate."""
        estimate = CostEstimate(
            material_cost=1.50,
            electricity_cost=0.25,
            machine_cost=0.50,
            labor_cost=0.0,
            total_cost=2.25,
            material_grams=60.0,
            print_time_hours=2.5,
        )

        assert estimate.total_cost == 2.25
        assert estimate.material_grams == 60.0

    def test_to_dict(self):
        """Test estimate serialization."""
        estimate = CostEstimate(
            material_cost=1.0,
            total_cost=1.5,
        )
        d = estimate.to_dict()

        assert d["material_cost"] == 1.0
        assert d["total_cost"] == 1.5


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""

    def test_success_result(self):
        """Test successful optimization result."""
        result = OptimizationResult(
            success=True,
            original_cost=5.0,
            optimized_cost=3.5,
            savings=1.5,
            savings_percent=30.0,
            recommendations=["Reduce infill"],
        )

        assert result.success is True
        assert result.savings == 1.5
        assert len(result.recommendations) == 1

    def test_to_dict(self):
        """Test result serialization."""
        result = OptimizationResult(
            success=True,
            original_cost=2.0,
            optimized_cost=1.5,
        )
        d = result.to_dict()

        assert d["success"] is True
        assert d["original_cost"] == 2.0


class TestCostOptimizer:
    """Tests for CostOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create a cost optimizer."""
        return CostOptimizer()

    def test_init(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.config is not None
        assert optimizer.config.pla_cost_per_gram == 0.025

    def test_init_custom_config(self):
        """Test optimizer with custom config."""
        config = CostConfig(pla_cost_per_gram=0.03)
        optimizer = CostOptimizer(config=config)

        assert optimizer.config.pla_cost_per_gram == 0.03

    def test_estimate_cost_basic(self, optimizer):
        """Test basic cost estimation."""
        estimate = optimizer.estimate_cost(volume_cm3=10.0)

        assert estimate.total_cost > 0
        assert estimate.material_grams > 0
        assert estimate.print_time_hours > 0

    def test_estimate_cost_different_materials(self, optimizer):
        """Test cost estimation with different materials."""
        pla_cost = optimizer.estimate_cost(10.0, material="pla")
        tpu_cost = optimizer.estimate_cost(10.0, material="tpu")

        # TPU should be more expensive
        assert tpu_cost.material_cost > pla_cost.material_cost

    def test_estimate_cost_with_settings(self, optimizer):
        """Test cost estimation with custom settings."""
        low_infill = PrintSettings(infill_percent=10)
        high_infill = PrintSettings(infill_percent=80)

        low_estimate = optimizer.estimate_cost(10.0, low_infill)
        high_estimate = optimizer.estimate_cost(10.0, high_infill)

        # Higher infill should use more material
        assert high_estimate.material_grams > low_estimate.material_grams

    def test_estimate_cost_with_supports(self, optimizer):
        """Test cost with supports enabled."""
        no_supports = PrintSettings(supports=False)
        with_supports = PrintSettings(supports=True)

        est_no_sup = optimizer.estimate_cost(10.0, no_supports)
        est_sup = optimizer.estimate_cost(10.0, with_supports)

        assert est_sup.material_grams > est_no_sup.material_grams

    def test_estimate_cost_breakdown(self, optimizer):
        """Test cost breakdown is provided."""
        estimate = optimizer.estimate_cost(10.0)

        assert "material" in estimate.cost_breakdown
        assert "electricity" in estimate.cost_breakdown
        assert "machine" in estimate.cost_breakdown


class TestMaterialEstimation:
    """Tests for material estimation."""

    @pytest.fixture
    def optimizer(self):
        """Create a cost optimizer."""
        return CostOptimizer()

    def test_estimate_material_basic(self, optimizer):
        """Test basic material estimation."""
        settings = PrintSettings()
        grams = optimizer._estimate_material(10.0, settings)

        assert grams > 0
        assert grams < 100  # Reasonable for 10 cm3

    def test_estimate_material_varies_with_infill(self, optimizer):
        """Test material varies with infill."""
        low = optimizer._estimate_material(10.0, PrintSettings(infill_percent=10))
        high = optimizer._estimate_material(10.0, PrintSettings(infill_percent=90))

        assert high > low


class TestTimeEstimation:
    """Tests for time estimation."""

    @pytest.fixture
    def optimizer(self):
        """Create a cost optimizer."""
        return CostOptimizer()

    def test_estimate_time_basic(self, optimizer):
        """Test basic time estimation."""
        settings = PrintSettings()
        hours = optimizer._estimate_time(10.0, settings)

        assert hours > 0
        assert hours < 100  # Reasonable for 10 cm3

    def test_estimate_time_varies_with_layer(self, optimizer):
        """Test time varies with layer height."""
        thin = optimizer._estimate_time(10.0, PrintSettings(layer_height=0.1))
        thick = optimizer._estimate_time(10.0, PrintSettings(layer_height=0.3))

        # Thinner layers take longer
        assert thin > thick


class TestOptimization:
    """Tests for cost optimization."""

    @pytest.fixture
    def optimizer(self):
        """Create a cost optimizer."""
        return CostOptimizer()

    def test_optimize_basic(self, optimizer):
        """Test basic optimization."""
        result = optimizer.optimize(10.0)

        assert result.success is True
        assert result.original_cost >= 0
        assert result.optimized_cost >= 0

    def test_optimize_high_infill(self, optimizer):
        """Test optimization with high infill."""
        high_infill = PrintSettings(infill_percent=80)
        result = optimizer.optimize(10.0, high_infill)

        assert result.success is True
        # Should recommend reducing infill
        assert any("infill" in r.lower() for r in result.recommendations)

    def test_optimize_generates_savings(self, optimizer):
        """Test optimization generates savings."""
        expensive = PrintSettings(
            layer_height=0.12,
            infill_percent=60,
            wall_count=5,
        )
        result = optimizer.optimize(10.0, expensive, min_quality="draft")

        assert result.success is True
        assert result.savings >= 0

    def test_optimize_returns_settings(self, optimizer):
        """Test optimization returns new settings."""
        result = optimizer.optimize(10.0)

        assert result.optimized_settings is not None
        assert isinstance(result.optimized_settings, PrintSettings)


class TestMeshVolume:
    """Tests for mesh volume calculation."""

    @pytest.fixture
    def optimizer(self):
        """Create a cost optimizer."""
        return CostOptimizer()

    @pytest.fixture
    def test_mesh(self, tmp_path):
        """Create a test mesh file."""
        mesh_path = tmp_path / "test.obj"
        # Simple cube 10x10x10 mm
        mesh_path.write_text("""v 0 0 0
v 10 0 0
v 10 10 0
v 0 10 0
v 0 0 10
v 10 0 10
v 10 10 10
v 0 10 10
f 1 2 3 4
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
""")
        return str(mesh_path)

    def test_calculate_volume(self, optimizer, test_mesh):
        """Test volume calculation."""
        volume = optimizer._calculate_volume(test_mesh)

        # 10x10x10 mm = 1000 mm3 = 1 cm3
        # OBJ quad faces may not calculate exact volume
        assert volume >= 0.5
        assert volume < 2.0

    def test_calculate_volume_nonexistent(self, optimizer):
        """Test volume for non-existent file."""
        volume = optimizer._calculate_volume("/nonexistent.obj")
        assert volume == 0.0

    def test_estimate_from_mesh(self, optimizer, test_mesh):
        """Test cost estimation from mesh file."""
        estimate = optimizer.estimate_from_mesh(test_mesh)

        assert estimate.total_cost > 0
        assert estimate.material_grams > 0


class TestMaterialComparison:
    """Tests for material comparison."""

    @pytest.fixture
    def optimizer(self):
        """Create a cost optimizer."""
        return CostOptimizer()

    def test_compare_materials(self, optimizer):
        """Test comparing materials."""
        comparisons = optimizer.compare_materials(10.0)

        assert "pla" in comparisons
        assert "petg" in comparisons
        assert "abs" in comparisons
        assert "tpu" in comparisons

        # All should have costs
        for material, estimate in comparisons.items():
            assert estimate.total_cost > 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_optimizer(self):
        """Test create_optimizer function."""
        optimizer = create_optimizer(
            material_cost=0.03,
            electricity_cost=0.15,
        )

        assert optimizer.config.pla_cost_per_gram == 0.03
        assert optimizer.config.electricity_cost_per_kwh == 0.15

    def test_estimate_cost_function(self):
        """Test estimate_cost convenience function."""
        estimate = estimate_cost(
            volume_cm3=10.0,
            infill=30,
            layer_height=0.16,
            material="petg",
        )

        assert estimate.total_cost > 0
        assert estimate.material_grams > 0


class TestIntegration:
    """Integration tests for cost optimizer."""

    @pytest.fixture
    def test_mesh(self, tmp_path):
        """Create a test mesh file."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("""v 0 0 0
v 20 0 0
v 20 20 0
v 0 20 0
v 0 0 15
v 20 0 15
v 20 20 15
v 0 20 15
f 1 2 3 4
f 5 6 7 8
f 1 2 6 5
""")
        return str(mesh_path)

    def test_full_workflow(self, test_mesh):
        """Test complete cost estimation workflow."""
        # Create optimizer
        optimizer = create_optimizer()

        # Estimate from mesh
        estimate = optimizer.estimate_from_mesh(test_mesh)
        assert estimate.total_cost > 0

        # Get optimization recommendations
        settings = PrintSettings(infill_percent=50)
        result = optimizer.optimize(10.0, settings)

        assert result.success is True
        assert len(result.recommendations) > 0

        # Compare materials
        comparisons = optimizer.compare_materials(10.0)
        assert len(comparisons) == 4

        # Verify TPU is most expensive
        costs = {m: e.material_cost for m, e in comparisons.items()}
        assert costs["tpu"] == max(costs.values())
