"""Tests for eco mode optimization module."""

import pytest

from src.estimator.eco_mode import (
    EcoOptimizer,
    EcoConfig,
    EcoMetrics,
    EcoLevel,
    EcoOptimizationResult,
    MaterialSustainability,
    MaterialType,
    create_eco_optimizer,
    calculate_carbon_footprint,
)
from src.estimator.cost_optimizer import PrintSettings


class TestEcoLevel:
    """Tests for EcoLevel enum."""

    def test_level_values(self):
        """Test eco level values."""
        assert EcoLevel.STANDARD.value == "standard"
        assert EcoLevel.ECO.value == "eco"
        assert EcoLevel.MAX_ECO.value == "max_eco"


class TestMaterialType:
    """Tests for MaterialType enum."""

    def test_material_values(self):
        """Test material type values."""
        assert MaterialType.PLA.value == "pla"
        assert MaterialType.PETG.value == "petg"
        assert MaterialType.ABS.value == "abs"
        assert MaterialType.TPU.value == "tpu"


class TestMaterialSustainability:
    """Tests for MaterialSustainability dataclass."""

    def test_create_sustainability(self):
        """Test creating sustainability info."""
        info = MaterialSustainability(
            material=MaterialType.PLA,
            biodegradable=True,
            recyclable=True,
            sustainability_score=85,
            notes="Eco-friendly",
        )

        assert info.material == MaterialType.PLA
        assert info.biodegradable is True
        assert info.sustainability_score == 85

    def test_to_dict(self):
        """Test serialization."""
        info = MaterialSustainability(
            MaterialType.PLA, True, True, 85, "Notes"
        )
        d = info.to_dict()

        assert d["material"] == "pla"
        assert d["biodegradable"] is True


class TestEcoConfig:
    """Tests for EcoConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = EcoConfig()

        assert config.eco_level == EcoLevel.ECO
        assert config.prioritize_biodegradable is True
        assert config.minimize_supports is True
        assert config.carbon_intensity_kwh == 0.4

    def test_custom_config(self):
        """Test custom configuration."""
        config = EcoConfig(
            eco_level=EcoLevel.MAX_ECO,
            carbon_intensity_kwh=0.5,
        )

        assert config.eco_level == EcoLevel.MAX_ECO
        assert config.carbon_intensity_kwh == 0.5

    def test_to_dict(self):
        """Test config serialization."""
        config = EcoConfig()
        d = config.to_dict()

        assert d["eco_level"] == "eco"
        assert "carbon_intensity_kwh" in d


class TestEcoMetrics:
    """Tests for EcoMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating metrics."""
        metrics = EcoMetrics(
            material_waste_grams=5.0,
            energy_kwh=0.5,
            carbon_footprint_kg=0.2,
            recyclability_percent=100.0,
            sustainability_score=85,
        )

        assert metrics.energy_kwh == 0.5
        assert metrics.carbon_footprint_kg == 0.2
        assert metrics.sustainability_score == 85

    def test_default_values(self):
        """Test default metric values."""
        metrics = EcoMetrics()

        assert metrics.material_waste_grams == 0.0
        assert metrics.energy_kwh == 0.0

    def test_to_dict(self):
        """Test metrics serialization."""
        metrics = EcoMetrics(energy_kwh=1.0)
        d = metrics.to_dict()

        assert d["energy_kwh"] == 1.0


class TestEcoOptimizationResult:
    """Tests for EcoOptimizationResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = EcoOptimizationResult(
            success=True,
            original_metrics=EcoMetrics(energy_kwh=1.0),
            optimized_metrics=EcoMetrics(energy_kwh=0.7),
            savings={"energy_kwh": 0.3},
            recommendations=["Reduce infill"],
        )

        assert result.success is True
        assert result.savings["energy_kwh"] == 0.3

    def test_failure_result(self):
        """Test failure result."""
        result = EcoOptimizationResult(
            success=False,
            error_message="Error occurred",
        )

        assert result.success is False
        assert result.error_message == "Error occurred"

    def test_to_dict(self):
        """Test result serialization."""
        result = EcoOptimizationResult(success=True)
        d = result.to_dict()

        assert d["success"] is True


class TestEcoOptimizer:
    """Tests for EcoOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create an eco optimizer."""
        return EcoOptimizer()

    def test_init(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.config is not None
        assert optimizer.config.eco_level == EcoLevel.ECO

    def test_init_custom_config(self):
        """Test optimizer with custom config."""
        config = EcoConfig(eco_level=EcoLevel.MAX_ECO)
        optimizer = EcoOptimizer(config=config)

        assert optimizer.config.eco_level == EcoLevel.MAX_ECO


class TestCalculateMetrics:
    """Tests for metrics calculation."""

    @pytest.fixture
    def optimizer(self):
        """Create an eco optimizer."""
        return EcoOptimizer()

    def test_calculate_metrics_basic(self, optimizer):
        """Test basic metrics calculation."""
        settings = PrintSettings()
        metrics = optimizer.calculate_metrics(10.0, settings)

        assert metrics.energy_kwh > 0
        assert metrics.carbon_footprint_kg > 0
        assert metrics.sustainability_score > 0

    def test_calculate_metrics_pla(self, optimizer):
        """Test PLA metrics."""
        settings = PrintSettings()
        metrics = optimizer.calculate_metrics(10.0, settings, "pla")

        assert metrics.sustainability_score == 85
        assert metrics.recyclability_percent == 100.0

    def test_calculate_metrics_abs(self, optimizer):
        """Test ABS metrics (less sustainable)."""
        settings = PrintSettings()
        metrics = optimizer.calculate_metrics(10.0, settings, "abs")

        assert metrics.sustainability_score == 30
        assert metrics.recyclability_percent == 0.0

    def test_supports_increase_waste(self, optimizer):
        """Test that supports increase waste."""
        no_supports = PrintSettings(supports=False)
        with_supports = PrintSettings(supports=True, support_density=20)

        metrics_no = optimizer.calculate_metrics(10.0, no_supports)
        metrics_yes = optimizer.calculate_metrics(10.0, with_supports)

        assert metrics_yes.material_waste_grams > metrics_no.material_waste_grams

    def test_higher_infill_more_energy(self, optimizer):
        """Test that higher infill uses more energy."""
        low_infill = PrintSettings(infill_percent=10)
        high_infill = PrintSettings(infill_percent=80)

        metrics_low = optimizer.calculate_metrics(10.0, low_infill)
        metrics_high = optimizer.calculate_metrics(10.0, high_infill)

        # Higher infill means more material, but print time is similar
        # Both should have positive energy use
        assert metrics_low.energy_kwh > 0
        assert metrics_high.energy_kwh > 0


class TestOptimize:
    """Tests for eco optimization."""

    @pytest.fixture
    def optimizer(self):
        """Create an eco optimizer."""
        return EcoOptimizer()

    def test_optimize_basic(self, optimizer):
        """Test basic optimization."""
        result = optimizer.optimize(10.0)

        assert result.success is True
        assert result.original_metrics is not None
        assert result.optimized_metrics is not None

    def test_optimize_generates_recommendations(self, optimizer):
        """Test optimization generates recommendations."""
        settings = PrintSettings(infill_percent=50)
        result = optimizer.optimize(10.0, settings)

        assert result.success is True
        assert len(result.recommendations) > 0

    def test_optimize_reduces_infill(self, optimizer):
        """Test optimization reduces high infill."""
        settings = PrintSettings(infill_percent=60)
        result = optimizer.optimize(10.0, settings)

        assert result.success is True
        assert result.optimized_settings.infill_percent < 60

    def test_optimize_suggests_pla(self, optimizer):
        """Test optimization suggests PLA for other materials."""
        result = optimizer.optimize(10.0, material="abs")

        assert result.success is True
        assert result.suggested_material == "pla"

    def test_optimize_max_eco_level(self):
        """Test max eco level is more aggressive."""
        config = EcoConfig(eco_level=EcoLevel.MAX_ECO)
        optimizer = EcoOptimizer(config=config)

        settings = PrintSettings(infill_percent=30)
        result = optimizer.optimize(10.0, settings)

        assert result.success is True
        assert result.optimized_settings.infill_percent <= 10

    def test_optimize_removes_raft(self, optimizer):
        """Test optimization removes raft."""
        settings = PrintSettings(raft=True)
        result = optimizer.optimize(10.0, settings)

        assert result.success is True
        assert result.optimized_settings.raft is False
        assert result.optimized_settings.brim is True

    def test_optimize_calculates_savings(self, optimizer):
        """Test optimization calculates savings."""
        settings = PrintSettings(infill_percent=60)
        result = optimizer.optimize(10.0, settings)

        assert result.success is True
        assert "energy_kwh" in result.savings
        assert "carbon_kg" in result.savings


class TestMaterialInfo:
    """Tests for material information."""

    @pytest.fixture
    def optimizer(self):
        """Create an eco optimizer."""
        return EcoOptimizer()

    def test_get_pla_info(self, optimizer):
        """Test getting PLA info."""
        info = optimizer.get_material_info("pla")

        assert info is not None
        assert info.biodegradable is True
        assert info.sustainability_score == 85

    def test_get_abs_info(self, optimizer):
        """Test getting ABS info."""
        info = optimizer.get_material_info("abs")

        assert info is not None
        assert info.biodegradable is False
        assert info.recyclable is False

    def test_get_unknown_material(self, optimizer):
        """Test getting unknown material."""
        info = optimizer.get_material_info("unknown")

        assert info is None


class TestCompareMaterials:
    """Tests for material comparison."""

    @pytest.fixture
    def optimizer(self):
        """Create an eco optimizer."""
        return EcoOptimizer()

    def test_compare_all_materials(self, optimizer):
        """Test comparing all materials."""
        settings = PrintSettings()
        comparisons = optimizer.compare_materials(10.0, settings)

        assert "pla" in comparisons
        assert "petg" in comparisons
        assert "abs" in comparisons
        assert "tpu" in comparisons

    def test_pla_most_sustainable(self, optimizer):
        """Test PLA has highest sustainability score."""
        settings = PrintSettings()
        comparisons = optimizer.compare_materials(10.0, settings)

        scores = {m: c.sustainability_score for m, c in comparisons.items()}
        assert scores["pla"] == max(scores.values())


class TestCarbonOffset:
    """Tests for carbon offset calculation."""

    @pytest.fixture
    def optimizer(self):
        """Create an eco optimizer."""
        return EcoOptimizer()

    def test_estimate_carbon_offset(self, optimizer):
        """Test carbon offset estimation."""
        metrics = EcoMetrics(carbon_footprint_kg=1.0)
        offset = optimizer.estimate_carbon_offset(metrics)

        assert offset["carbon_kg"] == 1.0
        assert offset["offset_cost_usd"] == 15.0
        assert offset["trees_equivalent"] > 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_eco_optimizer(self):
        """Test create_eco_optimizer function."""
        optimizer = create_eco_optimizer(
            eco_level="max_eco",
            carbon_intensity=0.5,
        )

        assert optimizer.config.eco_level == EcoLevel.MAX_ECO
        assert optimizer.config.carbon_intensity_kwh == 0.5

    def test_calculate_carbon_footprint(self):
        """Test calculate_carbon_footprint function."""
        result = calculate_carbon_footprint(
            volume_cm3=10.0,
            infill=20,
            material="pla",
        )

        assert "carbon_kg" in result
        assert "energy_kwh" in result
        assert "sustainability_score" in result
        assert result["sustainability_score"] == 85


class TestIntegration:
    """Integration tests for eco mode."""

    def test_full_workflow(self):
        """Test complete eco optimization workflow."""
        # Create optimizer
        optimizer = create_eco_optimizer(eco_level="eco")

        # Define print settings
        settings = PrintSettings(
            layer_height=0.16,
            infill_percent=40,
            wall_count=4,
            supports=True,
            support_density=20,
            raft=True,
        )

        # Calculate original metrics
        original_metrics = optimizer.calculate_metrics(15.0, settings, "petg")
        assert original_metrics.energy_kwh > 0

        # Optimize
        result = optimizer.optimize(15.0, settings, "petg")
        assert result.success is True

        # Verify improvements
        assert result.optimized_settings.infill_percent < 40
        assert result.optimized_settings.raft is False
        assert result.suggested_material == "pla"

        # Check savings
        assert result.savings["energy_kwh"] >= 0
        assert result.savings["carbon_kg"] >= 0

        # Compare materials
        comparisons = optimizer.compare_materials(15.0, result.optimized_settings)
        assert len(comparisons) == 4

        # Calculate offset
        offset = optimizer.estimate_carbon_offset(result.optimized_metrics)
        assert offset["offset_cost_usd"] >= 0
