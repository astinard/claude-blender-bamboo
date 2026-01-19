"""Tests for texture capture module."""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock

from src.capture.texture_capture import (
    TextureCapturer,
    TextureConfig,
    TextureResult,
    TextureFormat,
    TextureType,
    create_texture_capturer,
    capture_textures,
)


class TestTextureFormat:
    """Tests for TextureFormat enum."""

    def test_format_values(self):
        """Test format values."""
        assert TextureFormat.PNG.value == "png"
        assert TextureFormat.JPG.value == "jpg"
        assert TextureFormat.TIFF.value == "tiff"
        assert TextureFormat.EXR.value == "exr"


class TestTextureType:
    """Tests for TextureType enum."""

    def test_type_values(self):
        """Test texture type values."""
        assert TextureType.DIFFUSE.value == "diffuse"
        assert TextureType.NORMAL.value == "normal"
        assert TextureType.ROUGHNESS.value == "roughness"
        assert TextureType.METALLIC.value == "metallic"
        assert TextureType.AO.value == "ao"
        assert TextureType.HEIGHT.value == "height"


class TestTextureConfig:
    """Tests for TextureConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = TextureConfig()

        assert config.width == 2048
        assert config.height == 2048
        assert config.output_format == TextureFormat.PNG
        assert TextureType.DIFFUSE in config.texture_types
        assert config.quality == 95
        assert config.uv_margin == 0.01
        assert config.denoise is True
        assert config.color_correct is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = TextureConfig(
            width=4096,
            height=4096,
            output_format=TextureFormat.JPG,
            texture_types=[TextureType.DIFFUSE, TextureType.NORMAL],
        )

        assert config.width == 4096
        assert config.output_format == TextureFormat.JPG
        assert len(config.texture_types) == 2

    def test_to_dict(self):
        """Test config serialization."""
        config = TextureConfig(
            width=1024,
            texture_types=[TextureType.DIFFUSE, TextureType.AO],
        )
        d = config.to_dict()

        assert d["width"] == 1024
        assert "diffuse" in d["texture_types"]
        assert "ao" in d["texture_types"]

    def test_from_dict(self):
        """Test config deserialization."""
        data = {
            "width": 512,
            "height": 512,
            "output_format": "jpg",
            "texture_types": ["diffuse", "normal"],
            "quality": 85,
        }
        config = TextureConfig.from_dict(data)

        assert config.width == 512
        assert config.output_format == TextureFormat.JPG
        assert TextureType.NORMAL in config.texture_types


class TestTextureResult:
    """Tests for TextureResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = TextureResult(
            success=True,
            texture_paths={"diffuse": "/path/to/diffuse.png"},
            mesh_path="/path/to/mesh.obj",
            resolution=(2048, 2048),
            processing_time=5.5,
        )

        assert result.success is True
        assert "diffuse" in result.texture_paths
        assert result.resolution == (2048, 2048)

    def test_failure_result(self):
        """Test failure result."""
        result = TextureResult(
            success=False,
            error_message="Mesh not found",
        )

        assert result.success is False
        assert result.error_message == "Mesh not found"

    def test_to_dict(self):
        """Test result serialization."""
        result = TextureResult(
            success=True,
            texture_paths={"diffuse": "/diffuse.png"},
            resolution=(1024, 1024),
        )
        d = result.to_dict()

        assert d["success"] is True
        assert "diffuse" in d["texture_paths"]
        assert d["resolution"] == [1024, 1024]


class TestTextureCapturer:
    """Tests for TextureCapturer class."""

    @pytest.fixture
    def capturer(self, tmp_path):
        """Create a texture capturer with temp directory."""
        return TextureCapturer(output_dir=str(tmp_path))

    @pytest.fixture
    def test_mesh(self, tmp_path):
        """Create a test mesh file."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("""# Test mesh
v 0 0 0
v 1 0 0
v 1 1 0
f 1 2 3
""")
        return str(mesh_path)

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test image files."""
        images = []
        for i in range(3):
            img_path = tmp_path / f"image_{i}.jpg"
            img_path.write_bytes(b"fake jpeg data")
            images.append(str(img_path))
        return images

    def test_init(self, capturer):
        """Test capturer initialization."""
        assert capturer.config is not None
        assert capturer.output_dir.exists()

    def test_init_custom_config(self, tmp_path):
        """Test capturer with custom config."""
        config = TextureConfig(width=4096, output_format=TextureFormat.JPG)
        capturer = TextureCapturer(config=config, output_dir=str(tmp_path))

        assert capturer.config.width == 4096
        assert capturer.config.output_format == TextureFormat.JPG

    @pytest.mark.asyncio
    async def test_capture_no_mesh(self, capturer, test_images):
        """Test capture with missing mesh."""
        result = await capturer.capture_from_images(
            "/nonexistent/mesh.obj",
            test_images,
        )

        assert result.success is False
        assert "not found" in result.error_message

    @pytest.mark.asyncio
    async def test_capture_no_images(self, capturer, test_mesh):
        """Test capture with no images."""
        result = await capturer.capture_from_images(test_mesh, [])

        assert result.success is False
        assert "No valid images" in result.error_message

    @pytest.mark.asyncio
    async def test_capture_invalid_images(self, capturer, test_mesh):
        """Test capture with invalid image paths."""
        result = await capturer.capture_from_images(
            test_mesh,
            ["/nonexistent/img1.jpg", "/nonexistent/img2.jpg"],
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_capture_success(self, capturer, test_mesh, test_images):
        """Test successful texture capture."""
        result = await capturer.capture_from_images(
            test_mesh,
            test_images,
            project_name="test_capture",
        )

        assert result.success is True
        assert result.mesh_path is not None
        assert "diffuse" in result.texture_paths
        assert result.processing_time > 0

    @pytest.mark.asyncio
    async def test_capture_with_project_name(self, capturer, test_mesh, test_images):
        """Test capture with custom project name."""
        result = await capturer.capture_from_images(
            test_mesh,
            test_images,
            project_name="my_texture_project",
        )

        assert result.success is True
        assert "my_texture_project" in result.mesh_path

    @pytest.mark.asyncio
    async def test_capture_generates_files(self, capturer, test_mesh, test_images):
        """Test that capture generates texture files."""
        result = await capturer.capture_from_images(
            test_mesh,
            test_images,
            project_name="file_test",
        )

        assert result.success is True
        for tex_path in result.texture_paths.values():
            assert Path(tex_path).exists()

    @pytest.mark.asyncio
    async def test_capture_multiple_types(self, tmp_path, test_mesh, test_images):
        """Test capturing multiple texture types."""
        config = TextureConfig(
            texture_types=[TextureType.DIFFUSE, TextureType.NORMAL, TextureType.AO]
        )
        capturer = TextureCapturer(config=config, output_dir=str(tmp_path))

        result = await capturer.capture_from_images(
            test_mesh,
            test_images,
            project_name="multi_type",
        )

        assert result.success is True
        assert "diffuse" in result.texture_paths
        assert "normal" in result.texture_paths
        assert "ao" in result.texture_paths


class TestMTLGeneration:
    """Tests for MTL file generation."""

    @pytest.fixture
    def capturer(self, tmp_path):
        """Create a texture capturer with temp directory."""
        return TextureCapturer(output_dir=str(tmp_path))

    @pytest.fixture
    def test_mesh(self, tmp_path):
        """Create a test OBJ mesh file."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("v 0 0 0\nf 1")
        return str(mesh_path)

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test image files."""
        images = []
        for i in range(3):
            img_path = tmp_path / f"image_{i}.jpg"
            img_path.write_bytes(b"fake")
            images.append(str(img_path))
        return images

    @pytest.mark.asyncio
    async def test_mtl_created_for_obj(self, capturer, test_mesh, test_images):
        """Test MTL file is created for OBJ meshes."""
        result = await capturer.capture_from_images(
            test_mesh,
            test_images,
            project_name="mtl_test",
        )

        assert result.success is True
        assert result.mtl_path is not None
        assert Path(result.mtl_path).exists()

    @pytest.mark.asyncio
    async def test_mtl_content(self, capturer, test_mesh, test_images):
        """Test MTL file content."""
        result = await capturer.capture_from_images(
            test_mesh,
            test_images,
            project_name="mtl_content",
        )

        assert result.mtl_path is not None
        mtl_content = Path(result.mtl_path).read_text()

        assert "newmtl" in mtl_content
        assert "map_Kd" in mtl_content  # Diffuse map


class TestColorExtraction:
    """Tests for color extraction functionality."""

    @pytest.fixture
    def capturer(self, tmp_path):
        """Create a texture capturer with temp directory."""
        return TextureCapturer(output_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_extract_color_invalid_image(self, capturer):
        """Test color extraction with invalid image."""
        result = await capturer.extract_color_from_image("/nonexistent.jpg")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_extract_color_success(self, capturer, tmp_path):
        """Test successful color extraction."""
        img_path = tmp_path / "test.jpg"
        img_path.write_bytes(b"fake jpeg data")

        result = await capturer.extract_color_from_image(str(img_path))

        assert "dominant_color" in result
        assert "palette" in result
        assert "average_brightness" in result


class TestProjectManagement:
    """Tests for project management functions."""

    @pytest.fixture
    def capturer(self, tmp_path):
        """Create a texture capturer with temp directory."""
        return TextureCapturer(output_dir=str(tmp_path))

    @pytest.fixture
    def test_mesh(self, tmp_path):
        """Create a test mesh file."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("v 0 0 0\nf 1")
        return str(mesh_path)

    @pytest.fixture
    def test_images(self, tmp_path):
        """Create test image files."""
        images = []
        for i in range(3):
            img_path = tmp_path / f"image_{i}.jpg"
            img_path.write_bytes(b"fake")
            images.append(str(img_path))
        return images

    def test_list_projects_empty(self, capturer):
        """Test listing when no projects exist."""
        projects = capturer.list_projects()
        assert projects == []

    @pytest.mark.asyncio
    async def test_list_projects(self, capturer, test_mesh, test_images):
        """Test listing projects."""
        await capturer.capture_from_images(test_mesh, test_images, "project1")
        await capturer.capture_from_images(test_mesh, test_images, "project2")

        projects = capturer.list_projects()
        assert len(projects) == 2

        names = [p["name"] for p in projects]
        assert "project1" in names
        assert "project2" in names

    @pytest.mark.asyncio
    async def test_get_project_info(self, capturer, test_mesh, test_images):
        """Test getting project info."""
        await capturer.capture_from_images(test_mesh, test_images, "info_test")

        info = capturer.get_project_info("info_test")

        assert info is not None
        assert info["name"] == "info_test"
        assert "textures" in info
        assert "meshes" in info

    def test_get_project_info_not_found(self, capturer):
        """Test getting info for non-existent project."""
        info = capturer.get_project_info("nonexistent")
        assert info is None

    @pytest.mark.asyncio
    async def test_delete_project(self, capturer, test_mesh, test_images):
        """Test deleting a project."""
        await capturer.capture_from_images(test_mesh, test_images, "to_delete")

        assert capturer.get_project_info("to_delete") is not None

        result = capturer.delete_project("to_delete")
        assert result is True

        assert capturer.get_project_info("to_delete") is None

    def test_delete_nonexistent_project(self, capturer):
        """Test deleting non-existent project."""
        result = capturer.delete_project("nonexistent")
        assert result is False


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_texture_capturer(self, tmp_path):
        """Test create_texture_capturer function."""
        capturer = create_texture_capturer(
            resolution=1024,
            output_format="jpg",
            output_dir=str(tmp_path),
        )

        assert capturer.config.width == 1024
        assert capturer.config.height == 1024
        assert capturer.config.output_format == TextureFormat.JPG

    @pytest.mark.asyncio
    async def test_capture_textures(self, tmp_path):
        """Test capture_textures convenience function."""
        # Create test files
        mesh_path = tmp_path / "mesh.obj"
        mesh_path.write_text("v 0 0 0\nf 1")

        images = []
        for i in range(3):
            img = tmp_path / f"img_{i}.jpg"
            img.write_bytes(b"fake")
            images.append(str(img))

        result = await capture_textures(
            str(mesh_path),
            images,
            texture_types=["diffuse", "normal"],
            resolution=512,
            project_name="convenience_test",
        )

        assert result.success is True
        assert "diffuse" in result.texture_paths
        assert "normal" in result.texture_paths


class TestPlaceholderTextures:
    """Tests for placeholder texture generation."""

    @pytest.fixture
    def capturer(self, tmp_path):
        """Create a texture capturer with temp directory."""
        return TextureCapturer(output_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_png_placeholder(self, capturer, tmp_path):
        """Test PNG placeholder generation."""
        output = tmp_path / "test.png"
        await capturer._create_placeholder_texture(output, TextureType.DIFFUSE, 5)

        assert output.exists()
        # Check PNG signature
        data = output.read_bytes()
        assert data[:4] == b'\x89PNG'

    @pytest.mark.asyncio
    async def test_different_texture_types(self, capturer, tmp_path):
        """Test placeholder generation for different types."""
        for tex_type in TextureType:
            output = tmp_path / f"{tex_type.value}.png"
            await capturer._create_placeholder_texture(output, tex_type, 3)
            assert output.exists()


class TestImageValidation:
    """Tests for image validation."""

    @pytest.fixture
    def capturer(self, tmp_path):
        """Create a texture capturer with temp directory."""
        return TextureCapturer(output_dir=str(tmp_path))

    @pytest.fixture
    def test_mesh(self, tmp_path):
        """Create a test mesh file."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("v 0 0 0\nf 1")
        return str(mesh_path)

    @pytest.mark.asyncio
    async def test_accepts_jpg(self, capturer, test_mesh, tmp_path):
        """Test accepting JPG images."""
        images = [str(tmp_path / f"img_{i}.jpg") for i in range(3)]
        for img in images:
            Path(img).write_bytes(b"fake")

        result = await capturer.capture_from_images(test_mesh, images)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_accepts_png(self, capturer, test_mesh, tmp_path):
        """Test accepting PNG images."""
        images = [str(tmp_path / f"img_{i}.png") for i in range(3)]
        for img in images:
            Path(img).write_bytes(b"fake")

        result = await capturer.capture_from_images(test_mesh, images)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_rejects_invalid_extension(self, capturer, test_mesh, tmp_path):
        """Test rejecting invalid file extensions."""
        images = [str(tmp_path / f"img_{i}.txt") for i in range(3)]
        for img in images:
            Path(img).write_bytes(b"fake")

        result = await capturer.capture_from_images(test_mesh, images)
        assert result.success is False


class TestIntegration:
    """Integration tests for texture capture."""

    @pytest.fixture
    def test_mesh(self, tmp_path):
        """Create a test mesh file."""
        mesh_path = tmp_path / "test.obj"
        mesh_path.write_text("v 0 0 0\nv 1 0 0\nv 1 1 0\nf 1 2 3")
        return str(mesh_path)

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
    async def test_full_workflow(self, tmp_path, test_mesh, test_images):
        """Test complete texture capture workflow."""
        # Create capturer
        capturer = create_texture_capturer(
            resolution=1024,
            output_dir=str(tmp_path),
        )

        # Capture textures
        result = await capturer.capture_from_images(
            test_mesh,
            test_images,
            project_name="workflow_test",
        )
        assert result.success is True
        assert result.mesh_path is not None

        # List projects
        projects = capturer.list_projects()
        assert len(projects) == 1

        # Get project info
        info = capturer.get_project_info("workflow_test")
        assert info is not None
        assert len(info["textures"]) > 0

        # Delete project
        deleted = capturer.delete_project("workflow_test")
        assert deleted is True

        # Verify deleted
        projects = capturer.list_projects()
        assert len(projects) == 0
