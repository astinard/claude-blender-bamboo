"""Tests for post-processing guide module."""

import pytest

from src.docs.post_processing import (
    PostProcessingGuide,
    ProcessingGuide,
    ProcessStep,
    ProcessType,
    FinishLevel,
    create_guide,
    get_finish_steps,
)


class TestFinishLevel:
    """Tests for FinishLevel enum."""

    def test_level_values(self):
        """Test finish level values."""
        assert FinishLevel.RAW.value == "raw"
        assert FinishLevel.BASIC.value == "basic"
        assert FinishLevel.SMOOTH.value == "smooth"
        assert FinishLevel.POLISHED.value == "polished"
        assert FinishLevel.PAINTED.value == "painted"


class TestProcessType:
    """Tests for ProcessType enum."""

    def test_process_values(self):
        """Test process type values."""
        assert ProcessType.SUPPORT_REMOVAL.value == "support_removal"
        assert ProcessType.SANDING.value == "sanding"
        assert ProcessType.VAPOR_SMOOTHING.value == "vapor_smoothing"
        assert ProcessType.PAINTING.value == "painting"


class TestProcessStep:
    """Tests for ProcessStep dataclass."""

    def test_create_step(self):
        """Test creating a process step."""
        step = ProcessStep(
            process_type=ProcessType.SANDING,
            name="Sanding",
            description="Sand the surface",
            materials_needed=["Sandpaper"],
            tools_needed=["Sanding block"],
            estimated_time_minutes=30,
            difficulty="medium",
        )

        assert step.name == "Sanding"
        assert step.estimated_time_minutes == 30
        assert "Sandpaper" in step.materials_needed

    def test_to_dict(self):
        """Test step serialization."""
        step = ProcessStep(
            ProcessType.PAINTING,
            "Paint",
            "Apply paint",
        )
        d = step.to_dict()

        assert d["name"] == "Paint"
        assert d["process_type"] == "painting"


class TestProcessingGuide:
    """Tests for ProcessingGuide dataclass."""

    def test_success_guide(self):
        """Test successful guide."""
        guide = ProcessingGuide(
            success=True,
            material="PLA",
            target_finish=FinishLevel.SMOOTH,
            steps=[ProcessStep(ProcessType.SANDING, "Sand", "Sand it")],
            total_time_minutes=30,
        )

        assert guide.success is True
        assert len(guide.steps) == 1

    def test_failure_guide(self):
        """Test failure guide."""
        guide = ProcessingGuide(
            success=False,
            error_message="Error occurred",
        )

        assert guide.success is False
        assert guide.error_message == "Error occurred"

    def test_to_dict(self):
        """Test guide serialization."""
        guide = ProcessingGuide(
            success=True,
            material="PETG",
            target_finish=FinishLevel.POLISHED,
        )
        d = guide.to_dict()

        assert d["success"] is True
        assert d["material"] == "PETG"


class TestPostProcessingGuide:
    """Tests for PostProcessingGuide class."""

    @pytest.fixture
    def guide_gen(self):
        """Create a post-processing guide generator."""
        return PostProcessingGuide()

    def test_init(self, guide_gen):
        """Test guide generator initialization."""
        assert guide_gen is not None


class TestGuideGeneration:
    """Tests for guide generation."""

    @pytest.fixture
    def guide_gen(self):
        """Create a post-processing guide generator."""
        return PostProcessingGuide()

    def test_generate_basic(self, guide_gen):
        """Test basic guide generation."""
        result = guide_gen.generate_guide(target_finish=FinishLevel.BASIC)

        assert result.success is True
        assert len(result.steps) > 0

    def test_generate_smooth(self, guide_gen):
        """Test smooth finish guide."""
        result = guide_gen.generate_guide(target_finish=FinishLevel.SMOOTH)

        assert result.success is True
        # Should include sanding
        assert any(s.process_type == ProcessType.SANDING for s in result.steps)

    def test_generate_polished(self, guide_gen):
        """Test polished finish guide."""
        result = guide_gen.generate_guide(target_finish=FinishLevel.POLISHED)

        assert result.success is True
        # Should include sanding and filling
        step_types = [s.process_type for s in result.steps]
        assert ProcessType.SANDING in step_types
        assert ProcessType.FILLING in step_types

    def test_generate_painted(self, guide_gen):
        """Test painted finish guide."""
        result = guide_gen.generate_guide(target_finish=FinishLevel.PAINTED)

        assert result.success is True
        # Should include priming and painting
        step_types = [s.process_type for s in result.steps]
        assert ProcessType.PRIMING in step_types
        assert ProcessType.PAINTING in step_types

    def test_generate_with_supports(self, guide_gen):
        """Test guide with support removal."""
        result = guide_gen.generate_guide(
            target_finish=FinishLevel.BASIC,
            has_supports=True,
        )

        assert result.success is True
        assert any(s.process_type == ProcessType.SUPPORT_REMOVAL for s in result.steps)

    def test_generate_without_supports(self, guide_gen):
        """Test guide without support removal."""
        result = guide_gen.generate_guide(
            target_finish=FinishLevel.BASIC,
            has_supports=False,
        )

        assert result.success is True
        assert not any(s.process_type == ProcessType.SUPPORT_REMOVAL for s in result.steps)

    def test_generate_abs_vapor_smoothing(self, guide_gen):
        """Test ABS includes vapor smoothing option."""
        result = guide_gen.generate_guide(
            material="abs",
            target_finish=FinishLevel.SMOOTH,
        )

        assert result.success is True
        assert any(s.process_type == ProcessType.VAPOR_SMOOTHING for s in result.steps)

    def test_generate_with_threading(self, guide_gen):
        """Test guide with threading step."""
        result = guide_gen.generate_guide(
            target_finish=FinishLevel.BASIC,
            needs_threading=True,
        )

        assert result.success is True
        assert any(s.process_type == ProcessType.THREADING for s in result.steps)


class TestMaterialsAndTools:
    """Tests for materials and tools collection."""

    @pytest.fixture
    def guide_gen(self):
        """Create a post-processing guide generator."""
        return PostProcessingGuide()

    def test_collects_materials(self, guide_gen):
        """Test that guide collects required materials."""
        result = guide_gen.generate_guide(target_finish=FinishLevel.PAINTED)

        assert len(result.materials_list) > 0
        assert any("sand" in m.lower() for m in result.materials_list)

    def test_collects_tools(self, guide_gen):
        """Test that guide collects required tools."""
        result = guide_gen.generate_guide(target_finish=FinishLevel.SMOOTH)

        assert len(result.tools_list) > 0

    def test_collects_safety_warnings(self, guide_gen):
        """Test that guide collects safety warnings."""
        result = guide_gen.generate_guide(target_finish=FinishLevel.PAINTED)

        assert len(result.safety_warnings) > 0


class TestProcessInfo:
    """Tests for process information retrieval."""

    @pytest.fixture
    def guide_gen(self):
        """Create a post-processing guide generator."""
        return PostProcessingGuide()

    def test_get_sanding_info(self, guide_gen):
        """Test getting sanding process info."""
        info = guide_gen.get_process_info(ProcessType.SANDING)

        assert info is not None
        assert info.name == "Sanding"
        assert len(info.tips) > 0

    def test_get_vapor_smoothing_info(self, guide_gen):
        """Test getting vapor smoothing info."""
        info = guide_gen.get_process_info(ProcessType.VAPOR_SMOOTHING)

        assert info is not None
        assert len(info.safety_notes) > 0


class TestMaterialRecommendations:
    """Tests for material recommendations."""

    @pytest.fixture
    def guide_gen(self):
        """Create a post-processing guide generator."""
        return PostProcessingGuide()

    def test_pla_recommendations(self, guide_gen):
        """Test PLA recommendations."""
        recs = guide_gen.get_material_recommendations("pla")

        assert "smoothing" in recs
        assert "painting" in recs

    def test_abs_recommendations(self, guide_gen):
        """Test ABS recommendations."""
        recs = guide_gen.get_material_recommendations("abs")

        assert "acetone" in recs["smoothing"].lower()

    def test_unknown_material(self, guide_gen):
        """Test unknown material defaults to PLA."""
        recs = guide_gen.get_material_recommendations("unknown")

        assert recs is not None


class TestExport:
    """Tests for guide export."""

    @pytest.fixture
    def guide_gen(self):
        """Create a post-processing guide generator."""
        return PostProcessingGuide()

    def test_export_markdown(self, guide_gen):
        """Test exporting as markdown."""
        result = guide_gen.generate_guide(target_finish=FinishLevel.SMOOTH)
        md = guide_gen.export_markdown(result)

        assert "# Post-Processing Guide" in md
        assert "Sanding" in md
        assert "## Steps" in md


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_guide(self):
        """Test create_guide function."""
        guide = create_guide(
            material="petg",
            finish="polished",
            has_supports=True,
        )

        assert guide.success is True
        assert guide.material == "PETG"

    def test_get_finish_steps(self):
        """Test get_finish_steps function."""
        steps = get_finish_steps("painted")

        assert len(steps) > 0
        assert "Painting" in steps


class TestIntegration:
    """Integration tests for post-processing guide."""

    def test_full_workflow(self):
        """Test complete guide generation workflow."""
        # Create guide generator
        guide_gen = PostProcessingGuide()

        # Generate guide for painted ABS part with supports and threading
        result = guide_gen.generate_guide(
            material="abs",
            target_finish=FinishLevel.PAINTED,
            has_supports=True,
            needs_threading=True,
        )

        assert result.success is True
        assert result.material == "ABS"
        assert result.target_finish == FinishLevel.PAINTED

        # Verify steps include expected processes
        step_types = [s.process_type for s in result.steps]
        assert ProcessType.SUPPORT_REMOVAL in step_types
        assert ProcessType.SANDING in step_types
        # Note: Vapor smoothing is for SMOOTH/POLISHED, not PAINTED
        assert ProcessType.PRIMING in step_types
        assert ProcessType.PAINTING in step_types
        assert ProcessType.THREADING in step_types

        # Verify materials and tools collected
        assert len(result.materials_list) > 0
        assert len(result.tools_list) > 0

        # Verify safety warnings for ABS vapor smoothing
        assert len(result.safety_warnings) > 0

        # Export to markdown
        md = guide_gen.export_markdown(result)
        assert "Post-Processing Guide" in md
        assert "ABS" in md
        assert "Sanding" in md
        assert "Painting" in md
