"""Tests for tolerance testing module."""

import pytest

from src.testing.tolerance_tester import (
    ToleranceTester,
    ToleranceConfig,
    ToleranceResult,
    DimensionCheck,
    ToleranceLevel,
    FitType,
    FitCheck,
    create_tester,
    check_tolerance,
)


class TestToleranceLevel:
    """Tests for ToleranceLevel enum."""

    def test_level_values(self):
        """Test tolerance level values."""
        assert ToleranceLevel.COARSE.value == "coarse"
        assert ToleranceLevel.STANDARD.value == "standard"
        assert ToleranceLevel.FINE.value == "fine"
        assert ToleranceLevel.PRECISION.value == "precision"


class TestFitType:
    """Tests for FitType enum."""

    def test_fit_values(self):
        """Test fit type values."""
        assert FitType.CLEARANCE.value == "clearance"
        assert FitType.TRANSITION.value == "transition"
        assert FitType.INTERFERENCE.value == "interference"


class TestDimensionCheck:
    """Tests for DimensionCheck dataclass."""

    def test_passing_check(self):
        """Test dimension within tolerance."""
        check = DimensionCheck(
            name="width",
            nominal=10.0,
            actual=10.1,
            tolerance=0.2,
        )

        assert check.passed is True
        assert abs(check.deviation - 0.1) < 0.001

    def test_failing_check(self):
        """Test dimension out of tolerance."""
        check = DimensionCheck(
            name="height",
            nominal=20.0,
            actual=20.5,
            tolerance=0.2,
        )

        assert check.passed is False
        assert abs(check.deviation - 0.5) < 0.001

    def test_negative_deviation(self):
        """Test undersized dimension."""
        check = DimensionCheck(
            name="diameter",
            nominal=5.0,
            actual=4.8,
            tolerance=0.1,
        )

        assert abs(check.deviation - (-0.2)) < 0.001
        assert check.passed is False

    def test_to_dict(self):
        """Test check serialization."""
        check = DimensionCheck("test", 10.0, 10.05, 0.1)
        d = check.to_dict()

        assert d["name"] == "test"
        assert d["passed"] is True


class TestToleranceConfig:
    """Tests for ToleranceConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = ToleranceConfig()

        assert config.tolerance_level == ToleranceLevel.STANDARD
        assert config.material == "pla"
        assert config.compensate_shrinkage is True

    def test_get_tolerance_standard(self):
        """Test standard tolerance value."""
        config = ToleranceConfig(tolerance_level=ToleranceLevel.STANDARD)
        assert config.get_tolerance() == 0.2

    def test_get_tolerance_fine(self):
        """Test fine tolerance value."""
        config = ToleranceConfig(tolerance_level=ToleranceLevel.FINE)
        assert config.get_tolerance() == 0.1

    def test_get_tolerance_custom(self):
        """Test custom tolerance override."""
        config = ToleranceConfig(custom_tolerance=0.15)
        assert config.get_tolerance() == 0.15

    def test_to_dict(self):
        """Test config serialization."""
        config = ToleranceConfig()
        d = config.to_dict()

        assert d["tolerance_level"] == "standard"
        assert "tolerance_mm" in d


class TestFitCheck:
    """Tests for FitCheck dataclass."""

    def test_clearance_fit_good(self):
        """Test good clearance fit."""
        fit = FitCheck(
            hole_diameter=5.3,
            shaft_diameter=5.0,
            fit_type=FitType.CLEARANCE,
        )

        assert abs(fit.clearance - 0.3) < 0.001
        assert "Good clearance" in fit.recommendation

    def test_clearance_fit_tight(self):
        """Test too tight clearance."""
        fit = FitCheck(
            hole_diameter=5.1,
            shaft_diameter=5.0,
            fit_type=FitType.CLEARANCE,
        )

        assert abs(fit.clearance - 0.1) < 0.001
        assert "Increase clearance" in fit.recommendation

    def test_interference_fit(self):
        """Test press fit."""
        fit = FitCheck(
            hole_diameter=5.0,
            shaft_diameter=5.1,
            fit_type=FitType.INTERFERENCE,
        )

        assert abs(fit.clearance - (-0.1)) < 0.001
        assert "Good interference" in fit.recommendation

    def test_to_dict(self):
        """Test fit check serialization."""
        fit = FitCheck(5.0, 4.8, FitType.CLEARANCE)
        d = fit.to_dict()

        assert "clearance" in d
        assert d["fit_type"] == "clearance"


class TestToleranceResult:
    """Tests for ToleranceResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = ToleranceResult(
            success=True,
            all_passed=True,
            checks=[DimensionCheck("x", 10.0, 10.1, 0.2)],
            passed_count=1,
            failed_count=0,
        )

        assert result.success is True
        assert result.all_passed is True
        assert len(result.checks) == 1

    def test_failure_result(self):
        """Test failure result."""
        result = ToleranceResult(
            success=False,
            error_message="Error occurred",
        )

        assert result.success is False
        assert result.error_message == "Error occurred"

    def test_to_dict(self):
        """Test result serialization."""
        result = ToleranceResult(success=True, all_passed=True)
        d = result.to_dict()

        assert d["success"] is True
        assert d["all_passed"] is True


class TestToleranceTester:
    """Tests for ToleranceTester class."""

    @pytest.fixture
    def tester(self):
        """Create a tolerance tester."""
        return ToleranceTester()

    def test_init(self, tester):
        """Test tester initialization."""
        assert tester.config is not None
        assert tester.config.tolerance_level == ToleranceLevel.STANDARD

    def test_init_custom_config(self):
        """Test tester with custom config."""
        config = ToleranceConfig(tolerance_level=ToleranceLevel.FINE)
        tester = ToleranceTester(config=config)

        assert tester.config.tolerance_level == ToleranceLevel.FINE


class TestDimensions:
    """Tests for dimension testing."""

    @pytest.fixture
    def tester(self):
        """Create a tolerance tester."""
        config = ToleranceConfig(compensate_shrinkage=False)
        return ToleranceTester(config=config)

    def test_test_no_measurements(self, tester):
        """Test with no measurements."""
        result = tester.test_dimensions([])

        assert result.success is False
        assert "No measurements" in result.error_message

    def test_test_single_dimension(self, tester):
        """Test single dimension."""
        result = tester.test_dimensions([("width", 10.0, 10.1)])

        assert result.success is True
        assert len(result.checks) == 1
        assert result.passed_count == 1

    def test_test_multiple_dimensions(self, tester):
        """Test multiple dimensions."""
        measurements = [
            ("width", 10.0, 10.1),
            ("height", 20.0, 20.15),
            ("depth", 15.0, 14.85),
        ]
        result = tester.test_dimensions(measurements)

        assert result.success is True
        assert len(result.checks) == 3
        assert result.passed_count == 3

    def test_test_with_failures(self, tester):
        """Test with failing dimensions."""
        measurements = [
            ("width", 10.0, 10.1),  # Pass
            ("height", 20.0, 20.5),  # Fail
        ]
        result = tester.test_dimensions(measurements)

        assert result.success is True
        assert result.all_passed is False
        assert result.passed_count == 1
        assert result.failed_count == 1

    def test_test_with_shrinkage_compensation(self):
        """Test with shrinkage compensation enabled."""
        config = ToleranceConfig(
            material="pla",
            compensate_shrinkage=True,
        )
        tester = ToleranceTester(config=config)

        # PLA shrinks ~0.3%, so 10mm becomes 9.97mm expected
        result = tester.test_dimensions([("width", 10.0, 9.97)])

        assert result.success is True
        assert result.all_passed is True


class TestStatistics:
    """Tests for statistical calculations."""

    @pytest.fixture
    def tester(self):
        """Create a tolerance tester."""
        config = ToleranceConfig(compensate_shrinkage=False)
        return ToleranceTester(config=config)

    def test_calculate_statistics(self, tester):
        """Test statistics calculation."""
        deviations = [0.1, -0.1, 0.05, -0.05, 0.0]
        stats = tester._calculate_statistics(deviations)

        assert "mean_deviation" in stats
        assert "std_deviation" in stats
        assert stats["mean_deviation"] == 0.0

    def test_result_includes_statistics(self, tester):
        """Test result includes statistics."""
        measurements = [
            ("a", 10.0, 10.1),
            ("b", 10.0, 10.05),
            ("c", 10.0, 9.95),
        ]
        result = tester.test_dimensions(measurements)

        assert result.success is True
        assert "mean_deviation" in result.statistics


class TestRecommendations:
    """Tests for recommendation generation."""

    @pytest.fixture
    def tester(self):
        """Create a tolerance tester."""
        config = ToleranceConfig(compensate_shrinkage=False)
        return ToleranceTester(config=config)

    def test_oversized_recommendation(self, tester):
        """Test recommendation for oversized parts."""
        measurements = [
            ("a", 10.0, 10.2),
            ("b", 10.0, 10.25),
            ("c", 10.0, 10.15),
        ]
        result = tester.test_dimensions(measurements)

        assert any("oversized" in r.lower() for r in result.recommendations)

    def test_undersized_recommendation(self, tester):
        """Test recommendation for undersized parts."""
        measurements = [
            ("a", 10.0, 9.8),
            ("b", 10.0, 9.75),
            ("c", 10.0, 9.85),
        ]
        result = tester.test_dimensions(measurements)

        assert any("undersized" in r.lower() for r in result.recommendations)


class TestFitChecking:
    """Tests for fit checking."""

    @pytest.fixture
    def tester(self):
        """Create a tolerance tester."""
        return ToleranceTester()

    def test_check_clearance_fit(self, tester):
        """Test clearance fit check."""
        fit = tester.check_fit(5.3, 5.0, FitType.CLEARANCE)

        assert abs(fit.clearance - 0.3) < 0.001
        assert "Good" in fit.recommendation

    def test_check_interference_fit(self, tester):
        """Test interference fit check."""
        fit = tester.check_fit(5.0, 5.15, FitType.INTERFERENCE)

        assert abs(fit.clearance - (-0.15)) < 0.001
        assert "Good" in fit.recommendation


class TestShrinkage:
    """Tests for shrinkage calculation."""

    @pytest.fixture
    def tester(self):
        """Create a tolerance tester."""
        return ToleranceTester()

    def test_calculate_shrinkage(self, tester):
        """Test shrinkage calculation."""
        result = tester.calculate_shrinkage(10.0, 9.97)

        assert result["shrinkage_mm"] == 0.03
        assert result["shrinkage_percent"] == 0.3

    def test_shrinkage_comparison(self, tester):
        """Test shrinkage comparison to expected."""
        result = tester.calculate_shrinkage(10.0, 9.95)

        assert "difference_from_expected" in result


class TestTestPrint:
    """Tests for test print generation."""

    @pytest.fixture
    def tester(self):
        """Create a tolerance tester."""
        return ToleranceTester()

    def test_generate_test_print(self, tester):
        """Test generating test print specs."""
        spec = tester.generate_test_print()

        assert "name" in spec
        assert "features" in spec
        assert len(spec["features"]) > 0


class TestExport:
    """Tests for report export."""

    @pytest.fixture
    def tester(self):
        """Create a tolerance tester."""
        config = ToleranceConfig(compensate_shrinkage=False)
        return ToleranceTester(config=config)

    def test_export_report(self, tester):
        """Test exporting tolerance report."""
        result = tester.test_dimensions([
            ("width", 10.0, 10.1),
            ("height", 20.0, 20.3),
        ])

        report = tester.export_report(result)

        assert "# Tolerance Test Report" in report
        assert "width" in report
        assert "height" in report
        assert "PASS" in report or "FAIL" in report


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_tester(self):
        """Test create_tester function."""
        tester = create_tester(
            tolerance_level="fine",
            material="petg",
        )

        assert tester.config.tolerance_level == ToleranceLevel.FINE
        assert tester.config.material == "petg"

    def test_check_tolerance_pass(self):
        """Test check_tolerance function (passing)."""
        check = check_tolerance(10.0, 10.1, tolerance=0.2, name="width")

        assert check.passed is True
        assert abs(check.deviation - 0.1) < 0.001

    def test_check_tolerance_fail(self):
        """Test check_tolerance function (failing)."""
        check = check_tolerance(10.0, 10.5, tolerance=0.2, name="height")

        assert check.passed is False
        assert abs(check.deviation - 0.5) < 0.001


class TestIntegration:
    """Integration tests for tolerance testing."""

    def test_full_workflow(self):
        """Test complete tolerance testing workflow."""
        # Create tester
        tester = create_tester(tolerance_level="standard", material="pla")

        # Define measurements
        measurements = [
            ("X dimension", 20.0, 20.05),
            ("Y dimension", 20.0, 19.95),
            ("Hole diameter", 5.0, 4.9),
            ("Post diameter", 5.0, 5.1),
        ]

        # Run tests
        result = tester.test_dimensions(measurements)

        assert result.success is True
        assert len(result.checks) == 4

        # Check fit
        fit = tester.check_fit(4.9, 5.1, FitType.INTERFERENCE)
        assert fit.clearance < 0

        # Calculate shrinkage
        shrinkage = tester.calculate_shrinkage(20.0, 19.95)
        assert shrinkage["shrinkage_percent"] == 0.25

        # Generate test print spec
        spec = tester.generate_test_print()
        assert len(spec["features"]) > 0

        # Export report
        report = tester.export_report(result)
        assert "Tolerance Test Report" in report
        assert "X dimension" in report
