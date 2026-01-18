"""Tests for print failure prediction."""

import pytest
from pathlib import Path
import tempfile

from src.monitoring.geometry_analyzer import (
    GeometryAnalysisResult,
    OverhangInfo,
    ThinWallInfo,
    BridgeInfo,
    GeometryIssue,
    IssueSeverity,
    analyze_geometry,
)
from src.monitoring.failure_predictor import (
    FailurePredictor,
    FailureRisk,
    RiskLevel,
    GeometryAnalysis,
    MaterialRisk,
    analyze_model_risk,
)


class TestGeometryAnalyzer:
    """Tests for geometry analysis."""

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a simple test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_content = """solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 10 0 0
    vertex 0 10 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 10 0 0
    vertex 10 10 0
    vertex 0 10 0
  endloop
endfacet
endsolid test
"""
        stl_file.write_text(stl_content)
        return stl_file

    def test_analyze_nonexistent_file(self):
        """Test analyzing a file that doesn't exist."""
        result = analyze_geometry("/nonexistent/file.stl")
        assert result.total_issues > 0
        assert any(i.issue_type == "file_not_found" for i in result.other_issues)

    def test_analyze_simple_stl(self, temp_stl):
        """Test analyzing a simple STL file."""
        result = analyze_geometry(str(temp_stl))
        # Should complete without errors
        assert isinstance(result, GeometryAnalysisResult)

    def test_geometry_result_properties(self):
        """Test GeometryAnalysisResult properties."""
        result = GeometryAnalysisResult(
            overhangs=[
                OverhangInfo(angle=50, area_mm2=10, location=(0, 0, 0), severity=IssueSeverity.WARNING),
            ],
            thin_walls=[],
            bridges=[],
            other_issues=[],
        )
        assert result.total_issues == 1
        assert result.needs_support
        assert not result.has_critical_issues

    def test_critical_issues_detection(self):
        """Test detection of critical issues."""
        result = GeometryAnalysisResult(
            overhangs=[],
            thin_walls=[],
            bridges=[],
            other_issues=[
                GeometryIssue(
                    issue_type="no_volume",
                    severity=IssueSeverity.CRITICAL,
                    message="Test",
                )
            ],
        )
        assert result.has_critical_issues


class TestOverhangInfo:
    """Tests for overhang analysis."""

    def test_needs_support_threshold(self):
        """Test overhang support threshold."""
        low_angle = OverhangInfo(angle=30, area_mm2=10, location=(0, 0, 0), severity=IssueSeverity.INFO)
        assert not low_angle.needs_support

        high_angle = OverhangInfo(angle=50, area_mm2=10, location=(0, 0, 0), severity=IssueSeverity.WARNING)
        assert high_angle.needs_support

    def test_str_representation(self):
        """Test string representation."""
        overhang = OverhangInfo(angle=45.5, area_mm2=10, location=(0, 0, 0), severity=IssueSeverity.WARNING)
        assert "45.5" in str(overhang)
        assert "warning" in str(overhang)


class TestThinWallInfo:
    """Tests for thin wall analysis."""

    def test_is_printable_threshold(self):
        """Test thin wall printability threshold."""
        thick = ThinWallInfo(thickness_mm=0.8, height_mm=10, location=(0, 0, 0), severity=IssueSeverity.INFO)
        assert thick.is_printable

        thin = ThinWallInfo(thickness_mm=0.3, height_mm=10, location=(0, 0, 0), severity=IssueSeverity.CRITICAL)
        assert not thin.is_printable


class TestBridgeInfo:
    """Tests for bridge analysis."""

    def test_is_printable_threshold(self):
        """Test bridge printability threshold."""
        short = BridgeInfo(length_mm=5, width_mm=2, height_z=10, severity=IssueSeverity.INFO)
        assert short.is_printable

        long_bridge = BridgeInfo(length_mm=15, width_mm=2, height_z=10, severity=IssueSeverity.WARNING)
        assert not long_bridge.is_printable


class TestFailurePredictor:
    """Tests for failure prediction."""

    @pytest.fixture
    def predictor_pla(self):
        """Create predictor with PLA material."""
        return FailurePredictor(material="pla")

    @pytest.fixture
    def predictor_abs(self):
        """Create predictor with ABS material."""
        return FailurePredictor(material="abs")

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a simple test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_content = """solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 10 0 0
    vertex 0 10 0
  endloop
endfacet
endsolid test
"""
        stl_file.write_text(stl_content)
        return stl_file

    def test_analyze_simple_model(self, predictor_pla, temp_stl):
        """Test analyzing a simple model."""
        risk = predictor_pla.analyze(str(temp_stl))
        assert isinstance(risk, FailureRisk)
        assert risk.overall_risk in RiskLevel
        assert 0 <= risk.confidence <= 1
        assert 0 <= risk.success_probability <= 1

    def test_material_affects_risk(self, temp_stl):
        """Test that material affects risk assessment."""
        pla_risk = analyze_model_risk(str(temp_stl), "pla")
        abs_risk = analyze_model_risk(str(temp_stl), "abs")

        # ABS should have higher warping risk than PLA
        # Use enum ordering: critical > high > medium > low
        risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
        assert risk_order[abs_risk.material_risk.warping_risk] >= risk_order[pla_risk.material_risk.warping_risk]

    def test_no_material_analysis(self, temp_stl):
        """Test analysis without material."""
        predictor = FailurePredictor()
        risk = predictor.analyze(str(temp_stl))
        assert risk.material_risk is None

    def test_risk_to_dict(self, predictor_pla, temp_stl):
        """Test serialization to dictionary."""
        risk = predictor_pla.analyze(str(temp_stl))
        d = risk.to_dict()

        assert "overall_risk" in d
        assert "confidence" in d
        assert "success_probability" in d
        assert "geometry" in d
        assert "risk_factors" in d
        assert "recommendations" in d


class TestAnalyzeModelRisk:
    """Tests for convenience function."""

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a simple test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_content = """solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 10 0 0
    vertex 0 10 0
  endloop
endfacet
endsolid test
"""
        stl_file.write_text(stl_content)
        return stl_file

    def test_basic_usage(self, temp_stl):
        """Test basic function usage."""
        risk = analyze_model_risk(str(temp_stl))
        assert isinstance(risk, FailureRisk)

    def test_with_material(self, temp_stl):
        """Test with material specified."""
        risk = analyze_model_risk(str(temp_stl), material="petg")
        assert risk.material_risk is not None

    def test_recommendations_generated(self, temp_stl):
        """Test that recommendations are generated."""
        risk = analyze_model_risk(str(temp_stl))
        assert len(risk.recommendations) > 0


class TestRiskCalculation:
    """Tests for risk calculation logic."""

    def test_no_issues_low_risk(self):
        """Test that no issues results in low risk."""
        predictor = FailurePredictor()
        risk, conf, prob = predictor._calculate_overall_risk([])
        assert risk == RiskLevel.LOW
        assert prob >= 0.9

    def test_critical_issues_high_risk(self):
        """Test that critical issues result in high risk."""
        from src.monitoring.failure_predictor import RiskFactor

        predictor = FailurePredictor()
        factors = [
            RiskFactor(
                name="Test",
                risk_level=RiskLevel.CRITICAL,
                description="Critical issue",
                weight=2.0,
            ),
        ]
        risk, conf, prob = predictor._calculate_overall_risk(factors)
        assert risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert prob < 0.6


class TestMaterialRisk:
    """Tests for material risk analysis."""

    def test_abs_warping_risk(self):
        """Test ABS has high warping risk."""
        predictor = FailurePredictor(material="abs")
        mat_risk = predictor._analyze_material_risks()
        assert mat_risk.warping_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    def test_pla_low_warping(self):
        """Test PLA has low warping risk."""
        predictor = FailurePredictor(material="pla")
        mat_risk = predictor._analyze_material_risks()
        assert mat_risk.warping_risk == RiskLevel.LOW

    def test_environmental_requirements(self):
        """Test environmental requirements are detected."""
        predictor = FailurePredictor(material="abs")
        mat_risk = predictor._analyze_material_risks()
        assert len(mat_risk.environmental_requirements) > 0
        assert any("enclosure" in req.lower() for req in mat_risk.environmental_requirements)
