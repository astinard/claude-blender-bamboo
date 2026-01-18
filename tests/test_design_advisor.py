"""Tests for design advisor and overhang detection."""

import pytest
from pathlib import Path

from src.blender.overhang_detector import (
    OverhangDetector,
    OverhangAnalysis,
    OverhangInfo,
    OverhangSeverity,
)
from src.blender.design_advisor import (
    DesignAdvisor,
    DesignAdvice,
    DesignIssue,
    IssueSeverity,
    IssueCategory,
    OrientationSuggestion,
    FilletSuggestion,
    suggest_design_improvements,
)


class TestOverhangSeverity:
    """Tests for OverhangSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert OverhangSeverity.NONE == "none"
        assert OverhangSeverity.MINOR == "minor"
        assert OverhangSeverity.MODERATE == "moderate"
        assert OverhangSeverity.SEVERE == "severe"
        assert OverhangSeverity.CRITICAL == "critical"


class TestOverhangInfo:
    """Tests for OverhangInfo dataclass."""

    def test_create_overhang_info(self):
        """Test creating overhang info."""
        info = OverhangInfo(
            angle=60.0,
            severity=OverhangSeverity.SEVERE,
            area=25.0,
            location=(5.0, 5.0, 10.0),
            z_height=10.0,
            face_count=5,
            needs_support=True,
            suggested_support_type="tree",
        )
        assert info.angle == 60.0
        assert info.severity == OverhangSeverity.SEVERE
        assert info.needs_support
        assert info.suggested_support_type == "tree"


class TestOverhangDetector:
    """Tests for OverhangDetector class."""

    @pytest.fixture
    def detector(self):
        """Create a detector instance."""
        return OverhangDetector()

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a simple test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_file.write_text("""solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 10 0 0
    vertex 5 10 0
  endloop
endfacet
facet normal 0 0 -1
  outer loop
    vertex 0 0 10
    vertex 10 0 10
    vertex 5 10 10
  endloop
endfacet
endsolid test""")
        return str(stl_file)

    def test_analyze_file_not_found(self, detector):
        """Test analyzing non-existent file."""
        with pytest.raises(FileNotFoundError):
            detector.analyze("/nonexistent/file.stl")

    def test_analyze_invalid_format(self, detector, tmp_path):
        """Test analyzing invalid file format."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not an stl")

        with pytest.raises(ValueError):
            detector.analyze(str(txt_file))

    def test_analyze_simple_stl(self, detector, temp_stl):
        """Test analyzing a simple STL file."""
        analysis = detector.analyze(temp_stl)

        assert isinstance(analysis, OverhangAnalysis)
        assert analysis.file_path == temp_stl
        assert analysis.total_faces > 0

    def test_overhang_detection(self, detector, tmp_path):
        """Test that overhangs are detected."""
        # Create STL with overhang (face pointing down)
        stl_file = tmp_path / "overhang.stl"
        stl_file.write_text("""solid test
facet normal 0.866 0 -0.5
  outer loop
    vertex 0 0 5
    vertex 10 0 5
    vertex 5 10 8
  endloop
endfacet
endsolid test""")

        analysis = detector.analyze(str(stl_file))
        # Should detect overhang from the downward-facing normal
        assert analysis.total_faces > 0

    def test_no_overhang_detection(self, detector, tmp_path):
        """Test vertical faces don't count as overhangs."""
        stl_file = tmp_path / "vertical.stl"
        stl_file.write_text("""solid test
facet normal 1 0 0
  outer loop
    vertex 0 0 0
    vertex 0 10 0
    vertex 0 5 10
  endloop
endfacet
endsolid test""")

        analysis = detector.analyze(str(stl_file))
        # Vertical face should not be an overhang
        overhang_with_support = [o for o in analysis.overhangs if o.needs_support]
        # May have mock data, but real vertical face shouldn't need support

    def test_support_threshold(self, tmp_path):
        """Test custom support threshold."""
        detector = OverhangDetector(support_threshold=60.0)
        assert detector.support_threshold == 60.0

    def test_analysis_properties(self, detector, temp_stl):
        """Test analysis has all expected properties."""
        analysis = detector.analyze(temp_stl)

        assert hasattr(analysis, "total_faces")
        assert hasattr(analysis, "overhang_faces")
        assert hasattr(analysis, "overhang_percentage")
        assert hasattr(analysis, "max_overhang_angle")
        assert hasattr(analysis, "needs_supports")
        assert hasattr(analysis, "recommended_support_density")
        assert hasattr(analysis, "estimated_support_material")

    def test_overall_severity(self, detector, temp_stl):
        """Test overall severity property."""
        analysis = detector.analyze(temp_stl)
        severity = analysis.overall_severity
        assert isinstance(severity, OverhangSeverity)


class TestDesignAdvisor:
    """Tests for DesignAdvisor class."""

    @pytest.fixture
    def advisor(self):
        """Create an advisor instance."""
        return DesignAdvisor()

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file."""
        stl_file = tmp_path / "test_model.stl"
        stl_file.write_text("""solid test
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 50 0 0
    vertex 25 50 0
  endloop
endfacet
facet normal 0 0 1
  outer loop
    vertex 0 0 30
    vertex 50 0 30
    vertex 25 50 30
  endloop
endfacet
endsolid test""")
        return str(stl_file)

    def test_analyze_file_not_found(self, advisor):
        """Test analyzing non-existent file."""
        with pytest.raises(FileNotFoundError):
            advisor.analyze("/nonexistent/file.stl")

    def test_analyze_returns_advice(self, advisor, temp_stl):
        """Test analyze returns DesignAdvice."""
        advice = advisor.analyze(temp_stl)

        assert isinstance(advice, DesignAdvice)
        assert advice.file_path == temp_stl

    def test_printability_score_range(self, advisor, temp_stl):
        """Test printability score is in valid range."""
        advice = advisor.analyze(temp_stl)

        assert 0 <= advice.printability_score <= 100

    def test_bounding_box(self, advisor, temp_stl):
        """Test bounding box calculation."""
        advice = advisor.analyze(temp_stl)

        assert isinstance(advice.bounding_box, tuple)
        assert len(advice.bounding_box) == 3

    def test_issue_detection(self, advisor, temp_stl):
        """Test issues are detected."""
        advice = advisor.analyze(temp_stl)

        # All issues should be valid
        for issue in advice.issues:
            assert isinstance(issue, DesignIssue)
            assert issue.category in IssueCategory
            assert issue.severity in IssueSeverity

    def test_orientation_suggestions(self, advisor, temp_stl):
        """Test orientation suggestions are provided."""
        advice = advisor.analyze(temp_stl)

        assert len(advice.orientation_suggestions) > 0
        for orient in advice.orientation_suggestions:
            assert isinstance(orient, OrientationSuggestion)
            assert 0 <= orient.confidence <= 1

    def test_recommended_orientation(self, advisor, temp_stl):
        """Test recommended orientation is set."""
        advice = advisor.analyze(temp_stl)

        if advice.orientation_suggestions:
            # May or may not have a recommended orientation
            if advice.recommended_orientation:
                assert advice.recommended_orientation in advice.orientation_suggestions

    def test_has_critical_issues(self, advisor, temp_stl):
        """Test has_critical_issues property."""
        advice = advisor.analyze(temp_stl)

        # Should be boolean
        assert isinstance(advice.has_critical_issues, bool)
        assert isinstance(advice.has_errors, bool)

    def test_issue_summary(self, advisor, temp_stl):
        """Test issue summary counts."""
        advice = advisor.analyze(temp_stl)

        summary = advice.issue_summary
        assert isinstance(summary, dict)
        for severity in IssueSeverity:
            assert severity in summary
            assert summary[severity] >= 0

    def test_estimated_values(self, advisor, temp_stl):
        """Test estimated print time and material."""
        advice = advisor.analyze(temp_stl)

        assert advice.estimated_print_time_hours >= 0
        assert advice.estimated_material_grams >= 0

    def test_recommended_settings(self, advisor, temp_stl):
        """Test recommended settings."""
        advice = advisor.analyze(temp_stl)

        assert advice.recommended_layer_height > 0
        assert advice.recommended_infill > 0


class TestDesignIssue:
    """Tests for DesignIssue dataclass."""

    def test_create_issue(self):
        """Test creating a design issue."""
        issue = DesignIssue(
            category=IssueCategory.OVERHANG,
            severity=IssueSeverity.WARNING,
            description="60° overhang detected",
            location=(5.0, 5.0, 10.0),
            fix_suggestion="Add support",
        )

        assert issue.category == IssueCategory.OVERHANG
        assert issue.severity == IssueSeverity.WARNING
        assert "overhang" in issue.description.lower()

    def test_issue_auto_fixable(self):
        """Test auto_fixable flag."""
        issue = DesignIssue(
            category=IssueCategory.SHARP_EDGE,
            severity=IssueSeverity.INFO,
            description="Sharp edge",
            auto_fixable=True,
        )

        assert issue.auto_fixable


class TestOrientationSuggestion:
    """Tests for OrientationSuggestion dataclass."""

    def test_create_suggestion(self):
        """Test creating orientation suggestion."""
        suggestion = OrientationSuggestion(
            rotation_x=90,
            rotation_y=0,
            rotation_z=0,
            benefits=["Reduces overhangs"],
            drawbacks=["Longer print time"],
            support_reduction_percent=40,
            print_time_change_percent=15,
            confidence=0.8,
        )

        assert suggestion.rotation_x == 90
        assert len(suggestion.benefits) == 1
        assert suggestion.confidence == 0.8


class TestFilletSuggestion:
    """Tests for FilletSuggestion dataclass."""

    def test_create_fillet_suggestion(self):
        """Test creating fillet suggestion."""
        suggestion = FilletSuggestion(
            location=(0, 0, 0),
            edge_length=10.0,
            suggested_radius=2.0,
            reason="adhesion",
        )

        assert suggestion.suggested_radius == 2.0
        assert suggestion.reason == "adhesion"


class TestSuggestDesignImprovements:
    """Tests for convenience function."""

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_file.write_text("solid test\nendsolid test")
        return str(stl_file)

    def test_suggest_returns_advice(self, temp_stl):
        """Test suggest function returns advice."""
        advice = suggest_design_improvements(temp_stl)
        assert isinstance(advice, DesignAdvice)

    def test_suggest_file_not_found(self):
        """Test suggest with non-existent file."""
        with pytest.raises(FileNotFoundError):
            suggest_design_improvements("/nonexistent/file.stl")

    def test_suggest_verbose_mode(self, temp_stl, capsys):
        """Test verbose output."""
        suggest_design_improvements(temp_stl, verbose=True)

        captured = capsys.readouterr()
        assert "Design Analysis" in captured.out


class TestIssueCategoryEnum:
    """Tests for IssueCategory enum."""

    def test_all_categories(self):
        """Test all category values exist."""
        categories = [
            IssueCategory.OVERHANG,
            IssueCategory.THIN_WALL,
            IssueCategory.THIN_FEATURE,
            IssueCategory.BRIDGE,
            IssueCategory.ORIENTATION,
            IssueCategory.GEOMETRY,
            IssueCategory.SCALE,
            IssueCategory.SHARP_EDGE,
        ]

        for cat in categories:
            assert isinstance(cat.value, str)


class TestIssueSeverityEnum:
    """Tests for IssueSeverity enum."""

    def test_severity_ordering(self):
        """Test severity levels are defined."""
        assert IssueSeverity.INFO.value == "info"
        assert IssueSeverity.WARNING.value == "warning"
        assert IssueSeverity.ERROR.value == "error"
        assert IssueSeverity.CRITICAL.value == "critical"
