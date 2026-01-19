"""Tests for photogrammetry module."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.capture.photogrammetry import (
    PhotogrammetryPipeline,
    PipelineConfig,
    PipelineResult,
    ProcessingStage,
    create_pipeline,
    run_photogrammetry,
)


class TestProcessingStage:
    """Tests for ProcessingStage enum."""

    def test_stage_values(self):
        """Test stage values."""
        assert ProcessingStage.INIT.value == "init"
        assert ProcessingStage.FEATURE_EXTRACTION.value == "feature_extraction"
        assert ProcessingStage.FEATURE_MATCHING.value == "feature_matching"
        assert ProcessingStage.STRUCTURE_FROM_MOTION.value == "structure_from_motion"
        assert ProcessingStage.DEPTH_MAP.value == "depth_map"
        assert ProcessingStage.MESHING.value == "meshing"
        assert ProcessingStage.TEXTURING.value == "texturing"
        assert ProcessingStage.EXPORT.value == "export"
        assert ProcessingStage.COMPLETE.value == "complete"
        assert ProcessingStage.ERROR.value == "error"


class TestPipelineConfig:
    """Tests for PipelineConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = PipelineConfig()

        assert config.quality == "normal"
        assert config.describer_preset == "normal"
        assert config.force_sequential is False
        assert config.mesh_max_faces == 500000
        assert config.texture_size == 4096
        assert config.output_format == "obj"
        assert config.use_gpu is True
        assert config.num_threads == 0

    def test_custom_config(self):
        """Test custom configuration."""
        config = PipelineConfig(
            quality="high",
            output_format="stl",
            mesh_max_faces=100000,
        )

        assert config.quality == "high"
        assert config.output_format == "stl"
        assert config.mesh_max_faces == 100000

    def test_to_dict(self):
        """Test config serialization."""
        config = PipelineConfig(quality="ultra")
        d = config.to_dict()

        assert d["quality"] == "ultra"
        assert "output_format" in d
        assert "use_gpu" in d

    def test_from_dict(self):
        """Test config deserialization."""
        data = {
            "quality": "draft",
            "output_format": "ply",
            "mesh_max_faces": 250000,
        }
        config = PipelineConfig.from_dict(data)

        assert config.quality == "draft"
        assert config.output_format == "ply"
        assert config.mesh_max_faces == 250000


class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = PipelineResult(
            success=True,
            mesh_path="/path/to/mesh.obj",
            camera_count=10,
            matched_images=8,
            vertex_count=1000,
            face_count=2000,
            processing_time=120.5,
            stage_completed=ProcessingStage.COMPLETE,
        )

        assert result.success is True
        assert result.mesh_path == "/path/to/mesh.obj"
        assert result.camera_count == 10
        assert result.vertex_count == 1000

    def test_failure_result(self):
        """Test failure result."""
        result = PipelineResult(
            success=False,
            error_message="Not enough images",
            stage_completed=ProcessingStage.ERROR,
        )

        assert result.success is False
        assert result.error_message == "Not enough images"

    def test_to_dict(self):
        """Test result serialization."""
        result = PipelineResult(
            success=True,
            mesh_path="/mesh.obj",
            vertex_count=500,
            stage_completed=ProcessingStage.COMPLETE,
        )
        d = result.to_dict()

        assert d["success"] is True
        assert d["mesh_path"] == "/mesh.obj"
        assert d["stage_completed"] == "complete"


class TestPhotogrammetryPipeline:
    """Tests for PhotogrammetryPipeline class."""

    @pytest.fixture
    def pipeline(self, tmp_path):
        """Create a pipeline with temp directory."""
        return PhotogrammetryPipeline(output_dir=str(tmp_path))

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test image files."""
        images = []
        for i in range(5):
            img_path = tmp_path / f"image_{i}.jpg"
            img_path.write_bytes(b"fake jpeg data")
            images.append(str(img_path))
        return images

    def test_init(self, pipeline):
        """Test pipeline initialization."""
        assert pipeline.config is not None
        assert pipeline.output_dir.exists()

    def test_init_custom_config(self, tmp_path):
        """Test pipeline with custom config."""
        config = PipelineConfig(quality="high", output_format="stl")
        pipeline = PhotogrammetryPipeline(config=config, output_dir=str(tmp_path))

        assert pipeline.config.quality == "high"
        assert pipeline.config.output_format == "stl"

    def test_meshroom_available_property(self, pipeline):
        """Test meshroom_available property."""
        # On most test systems, Meshroom won't be installed
        assert isinstance(pipeline.meshroom_available, bool)

    @pytest.mark.asyncio
    async def test_process_no_images(self, pipeline):
        """Test processing with no images."""
        result = await pipeline.process([])

        assert result.success is False
        assert "No images provided" in result.error_message

    @pytest.mark.asyncio
    async def test_process_too_few_images(self, pipeline, tmp_path):
        """Test processing with too few images."""
        # Create only 2 images
        images = []
        for i in range(2):
            img = tmp_path / f"img_{i}.jpg"
            img.write_bytes(b"fake")
            images.append(str(img))

        result = await pipeline.process(images)

        assert result.success is False
        assert "at least 3" in result.error_message

    @pytest.mark.asyncio
    async def test_process_invalid_images(self, pipeline, tmp_path):
        """Test processing with non-existent images."""
        images = [
            str(tmp_path / "nonexistent1.jpg"),
            str(tmp_path / "nonexistent2.jpg"),
            str(tmp_path / "nonexistent3.jpg"),
        ]

        result = await pipeline.process(images)

        assert result.success is False
        assert "at least 3" in result.error_message

    @pytest.mark.asyncio
    async def test_process_fallback(self, pipeline, test_images):
        """Test fallback processing."""
        result = await pipeline.process(test_images, project_name="test_project")

        # Fallback should succeed
        assert result.success is True
        assert result.mesh_path is not None
        assert result.camera_count == 5
        assert result.stage_completed == ProcessingStage.COMPLETE

    @pytest.mark.asyncio
    async def test_process_with_project_name(self, pipeline, test_images):
        """Test processing with custom project name."""
        result = await pipeline.process(test_images, project_name="my_project")

        assert result.success is True
        assert "my_project" in result.mesh_path

    @pytest.mark.asyncio
    async def test_process_generates_mesh_file(self, pipeline, test_images):
        """Test that processing generates mesh file."""
        result = await pipeline.process(test_images, project_name="mesh_test")

        assert result.success is True
        assert Path(result.mesh_path).exists()

    @pytest.mark.asyncio
    async def test_process_different_formats(self, tmp_path, test_images):
        """Test processing with different output formats."""
        for fmt in ["obj", "stl", "ply"]:
            config = PipelineConfig(output_format=fmt)
            pipeline = PhotogrammetryPipeline(config=config, output_dir=str(tmp_path))

            result = await pipeline.process(test_images, project_name=f"test_{fmt}")

            assert result.success is True
            assert result.mesh_path.endswith(f".{fmt}")


class TestProgressCallback:
    """Tests for progress callback functionality."""

    @pytest.fixture
    def pipeline(self, tmp_path):
        """Create a pipeline with temp directory."""
        return PhotogrammetryPipeline(output_dir=str(tmp_path))

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test image files."""
        images = []
        for i in range(5):
            img_path = tmp_path / f"image_{i}.jpg"
            img_path.write_bytes(b"fake jpeg data")
            images.append(str(img_path))
        return images

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, tmp_path, test_images):
        """Test that progress callback is called."""
        stages_received = []

        def callback(stage: ProcessingStage, percent: float):
            stages_received.append(stage)

        pipeline = PhotogrammetryPipeline(
            output_dir=str(tmp_path),
            progress_callback=callback,
        )

        await pipeline.process(test_images)

        assert len(stages_received) > 0
        assert ProcessingStage.INIT in stages_received
        assert ProcessingStage.COMPLETE in stages_received


class TestProjectManagement:
    """Tests for project management functions."""

    @pytest.fixture
    def pipeline(self, tmp_path):
        """Create a pipeline with temp directory."""
        return PhotogrammetryPipeline(output_dir=str(tmp_path))

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test image files."""
        images = []
        for i in range(5):
            img_path = tmp_path / f"image_{i}.jpg"
            img_path.write_bytes(b"fake jpeg data")
            images.append(str(img_path))
        return images

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, pipeline):
        """Test listing when no projects exist."""
        projects = pipeline.list_projects()
        assert projects == []

    @pytest.mark.asyncio
    async def test_list_projects(self, pipeline, test_images):
        """Test listing projects."""
        # Create some projects
        await pipeline.process(test_images, project_name="project1")
        await pipeline.process(test_images, project_name="project2")

        projects = pipeline.list_projects()
        assert len(projects) == 2

        names = [p["name"] for p in projects]
        assert "project1" in names
        assert "project2" in names

    @pytest.mark.asyncio
    async def test_get_project_info(self, pipeline, test_images):
        """Test getting project info."""
        await pipeline.process(test_images, project_name="info_test")

        info = pipeline.get_project_info("info_test")

        assert info is not None
        assert info["name"] == "info_test"
        assert "path" in info
        assert "created" in info
        assert len(info["mesh_files"]) > 0

    def test_get_project_info_not_found(self, pipeline):
        """Test getting info for non-existent project."""
        info = pipeline.get_project_info("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_delete_project(self, pipeline, test_images):
        """Test deleting a project."""
        await pipeline.process(test_images, project_name="to_delete")

        # Verify it exists
        assert pipeline.get_project_info("to_delete") is not None

        # Delete it
        result = pipeline.delete_project("to_delete")
        assert result is True

        # Verify it's gone
        assert pipeline.get_project_info("to_delete") is None

    def test_delete_nonexistent_project(self, pipeline):
        """Test deleting non-existent project."""
        result = pipeline.delete_project("nonexistent")
        assert result is False


class TestMeshElementCounting:
    """Tests for mesh element counting."""

    @pytest.fixture
    def pipeline(self, tmp_path):
        """Create a pipeline with temp directory."""
        return PhotogrammetryPipeline(output_dir=str(tmp_path))

    def test_count_obj_elements(self, pipeline, tmp_path):
        """Test counting OBJ mesh elements."""
        obj_file = tmp_path / "test.obj"
        obj_file.write_text("""# Test OBJ
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
f 1 2 3
f 1 3 4
""")

        v, f = pipeline._count_mesh_elements(obj_file)
        assert v == 4
        assert f == 2

    def test_count_ply_elements(self, pipeline, tmp_path):
        """Test counting PLY mesh elements."""
        ply_file = tmp_path / "test.ply"
        ply_file.write_text("""ply
format ascii 1.0
element vertex 8
property float x
property float y
property float z
element face 6
property list uchar int vertex_indices
end_header
0 0 0
1 0 0
""")

        v, f = pipeline._count_mesh_elements(ply_file)
        assert v == 8
        assert f == 6


class TestPlaceholderMesh:
    """Tests for placeholder mesh generation."""

    @pytest.fixture
    def pipeline(self, tmp_path):
        """Create a pipeline with temp directory."""
        return PhotogrammetryPipeline(output_dir=str(tmp_path))

    def test_create_obj_placeholder(self, pipeline, tmp_path):
        """Test creating OBJ placeholder."""
        output = tmp_path / "placeholder.obj"
        pipeline._create_placeholder_mesh(output, 10)

        assert output.exists()
        content = output.read_text()
        assert "v " in content
        assert "f " in content
        assert "10 images" in content

    def test_create_stl_placeholder(self, pipeline, tmp_path):
        """Test creating STL placeholder."""
        output = tmp_path / "placeholder.stl"
        pipeline._create_placeholder_mesh(output, 5)

        assert output.exists()
        content = output.read_text()
        assert "solid" in content
        assert "facet" in content

    def test_create_ply_placeholder(self, pipeline, tmp_path):
        """Test creating PLY placeholder."""
        output = tmp_path / "placeholder.ply"
        pipeline._create_placeholder_mesh(output, 8)

        assert output.exists()
        content = output.read_text()
        assert "ply" in content
        assert "element vertex" in content


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_pipeline(self, tmp_path):
        """Test create_pipeline function."""
        pipeline = create_pipeline(quality="high", output_dir=str(tmp_path))

        assert pipeline.config.quality == "high"
        assert pipeline.output_dir == tmp_path / "photogrammetry"

    def test_create_pipeline_with_callback(self, tmp_path):
        """Test create_pipeline with progress callback."""
        callback = Mock()
        pipeline = create_pipeline(
            output_dir=str(tmp_path),
            progress_callback=callback,
        )

        assert pipeline._progress_callback == callback

    @pytest.mark.asyncio
    async def test_run_photogrammetry(self, tmp_path):
        """Test run_photogrammetry convenience function."""
        # Create test images
        images = []
        for i in range(5):
            img = tmp_path / f"img_{i}.jpg"
            img.write_bytes(b"fake")
            images.append(str(img))

        result = await run_photogrammetry(
            images,
            quality="draft",
            output_format="stl",
            project_name="convenience_test",
        )

        assert result.success is True
        assert result.mesh_path.endswith(".stl")


class TestImageValidation:
    """Tests for image validation."""

    @pytest.fixture
    def pipeline(self, tmp_path):
        """Create a pipeline with temp directory."""
        return PhotogrammetryPipeline(output_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_accepts_jpg(self, pipeline, tmp_path):
        """Test accepting JPG images."""
        images = []
        for i in range(3):
            img = tmp_path / f"img_{i}.jpg"
            img.write_bytes(b"fake")
            images.append(str(img))

        result = await pipeline.process(images)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_accepts_jpeg(self, pipeline, tmp_path):
        """Test accepting JPEG images."""
        images = []
        for i in range(3):
            img = tmp_path / f"img_{i}.jpeg"
            img.write_bytes(b"fake")
            images.append(str(img))

        result = await pipeline.process(images)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_accepts_png(self, pipeline, tmp_path):
        """Test accepting PNG images."""
        images = []
        for i in range(3):
            img = tmp_path / f"img_{i}.png"
            img.write_bytes(b"fake")
            images.append(str(img))

        result = await pipeline.process(images)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_rejects_invalid_extension(self, pipeline, tmp_path):
        """Test rejecting invalid file extensions."""
        images = []
        for i in range(3):
            img = tmp_path / f"img_{i}.txt"
            img.write_bytes(b"fake")
            images.append(str(img))

        result = await pipeline.process(images)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid(self, pipeline, tmp_path):
        """Test with mix of valid and invalid images."""
        # 2 valid, 2 invalid
        images = []
        for i in range(2):
            img = tmp_path / f"valid_{i}.jpg"
            img.write_bytes(b"fake")
            images.append(str(img))

        for i in range(2):
            img = tmp_path / f"invalid_{i}.txt"
            img.write_bytes(b"fake")
            images.append(str(img))

        result = await pipeline.process(images)
        # Only 2 valid images, not enough
        assert result.success is False


class TestIntegration:
    """Integration tests for photogrammetry pipeline."""

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test image files."""
        images = []
        for i in range(10):
            img_path = tmp_path / f"image_{i}.jpg"
            img_path.write_bytes(b"fake jpeg data")
            images.append(str(img_path))
        return images

    @pytest.mark.asyncio
    async def test_full_workflow(self, tmp_path, test_images):
        """Test complete photogrammetry workflow."""
        # Create pipeline
        pipeline = create_pipeline(quality="draft", output_dir=str(tmp_path))

        # Process images
        result = await pipeline.process(test_images, project_name="workflow_test")
        assert result.success is True
        assert result.mesh_path is not None

        # List projects
        projects = pipeline.list_projects()
        assert len(projects) == 1

        # Get project info
        info = pipeline.get_project_info("workflow_test")
        assert info is not None
        assert info["name"] == "workflow_test"

        # Delete project
        deleted = pipeline.delete_project("workflow_test")
        assert deleted is True

        # Verify deleted
        projects = pipeline.list_projects()
        assert len(projects) == 0
