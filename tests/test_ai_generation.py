"""Tests for AI text-to-3D generation."""

import pytest
import asyncio
from pathlib import Path

from src.ai.text_to_3d import (
    TextTo3DGenerator,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    GenerationProvider,
    ModelFormat,
    ArtStyle,
    generate_model,
)
from src.ai.mock_client import MockClient
from src.ai.meshy_client import MeshyClient
from src.ai.tripo_client import TripoClient


class TestGenerationProvider:
    """Tests for GenerationProvider enum."""

    def test_provider_values(self):
        """Test provider enum values."""
        assert GenerationProvider.MESHY.value == "meshy"
        assert GenerationProvider.TRIPO.value == "tripo"
        assert GenerationProvider.MOCK.value == "mock"

    def test_provider_from_string(self):
        """Test creating provider from string."""
        assert GenerationProvider("meshy") == GenerationProvider.MESHY
        assert GenerationProvider("mock") == GenerationProvider.MOCK


class TestGenerationStatus:
    """Tests for GenerationStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert GenerationStatus.PENDING.value == "pending"
        assert GenerationStatus.PROCESSING.value == "processing"
        assert GenerationStatus.COMPLETED.value == "completed"
        assert GenerationStatus.FAILED.value == "failed"


class TestModelFormat:
    """Tests for ModelFormat enum."""

    def test_format_values(self):
        """Test format enum values."""
        assert ModelFormat.STL.value == "stl"
        assert ModelFormat.OBJ.value == "obj"
        assert ModelFormat.GLB.value == "glb"
        assert ModelFormat.THREEMF.value == "3mf"


class TestArtStyle:
    """Tests for ArtStyle enum."""

    def test_style_values(self):
        """Test style enum values."""
        assert ArtStyle.REALISTIC.value == "realistic"
        assert ArtStyle.PRINTABLE.value == "printable"
        assert ArtStyle.LOW_POLY.value == "low_poly"


class TestGenerationRequest:
    """Tests for GenerationRequest dataclass."""

    def test_create_request(self):
        """Test creating a generation request."""
        request = GenerationRequest(
            prompt="a dragon phone stand",
            provider=GenerationProvider.MOCK,
        )

        assert request.prompt == "a dragon phone stand"
        assert request.provider == GenerationProvider.MOCK
        assert request.output_format == ModelFormat.STL
        assert request.art_style == ArtStyle.PRINTABLE
        assert request.request_id is not None

    def test_request_validation_empty_prompt(self):
        """Test prompt validation."""
        with pytest.raises(ValueError, match="at least 3 characters"):
            GenerationRequest(prompt="ab")

    def test_request_validation_long_prompt(self):
        """Test long prompt validation."""
        with pytest.raises(ValueError, match="under 500 characters"):
            GenerationRequest(prompt="x" * 501)

    def test_request_with_options(self):
        """Test request with all options."""
        request = GenerationRequest(
            prompt="a cute robot",
            provider=GenerationProvider.MESHY,
            output_format=ModelFormat.OBJ,
            art_style=ArtStyle.CARTOON,
            negative_prompt="scary, damaged",
            seed=12345,
            resolution="high",
        )

        assert request.negative_prompt == "scary, damaged"
        assert request.seed == 12345
        assert request.resolution == "high"


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_create_result(self):
        """Test creating a generation result."""
        result = GenerationResult(
            request_id="test123",
            status=GenerationStatus.COMPLETED,
            provider=GenerationProvider.MOCK,
            output_path="/path/to/model.stl",
        )

        assert result.request_id == "test123"
        assert result.status == GenerationStatus.COMPLETED
        assert result.is_successful

    def test_failed_result(self):
        """Test failed result."""
        result = GenerationResult(
            request_id="test123",
            status=GenerationStatus.FAILED,
            provider=GenerationProvider.MOCK,
            error_message="API error",
            error_code="API_ERROR",
        )

        assert not result.is_successful
        assert result.error_message == "API error"

    def test_result_without_output(self):
        """Test result without output path is not successful."""
        result = GenerationResult(
            request_id="test123",
            status=GenerationStatus.COMPLETED,
            provider=GenerationProvider.MOCK,
            output_path=None,
        )

        assert not result.is_successful


class TestMockClient:
    """Tests for MockClient."""

    @pytest.fixture
    def client(self):
        """Create a mock client."""
        return MockClient()

    @pytest.fixture
    def gen_request(self, tmp_path):
        """Create a test request."""
        return GenerationRequest(
            prompt="test model",
            provider=GenerationProvider.MOCK,
            output_dir=str(tmp_path),
            output_name="test_output",
        )

    def test_generate_creates_file(self, client, gen_request, tmp_path):
        """Test generate creates output file."""
        result = asyncio.run(client.generate(gen_request))

        assert result.status == GenerationStatus.COMPLETED
        assert result.output_path is not None
        assert Path(result.output_path).exists()

    def test_generate_returns_stl_content(self, client, gen_request, tmp_path):
        """Test generated file contains valid STL."""
        result = asyncio.run(client.generate(gen_request))

        content = Path(result.output_path).read_text()
        assert "solid" in content.lower()
        assert "facet" in content.lower()
        assert "endsolid" in content.lower()

    def test_check_status(self, client, gen_request):
        """Test checking status of a task."""
        # First generate
        gen_result = asyncio.run(client.generate(gen_request))

        # Then check status
        status_result = asyncio.run(client.check_status(gen_result.provider_task_id))

        assert status_result.status == GenerationStatus.COMPLETED

    def test_check_status_unknown_task(self, client):
        """Test checking status of unknown task."""
        result = asyncio.run(client.check_status("unknown_task"))

        assert result.status == GenerationStatus.FAILED

    def test_download_model(self, client, gen_request, tmp_path):
        """Test downloading model."""
        gen_result = asyncio.run(client.generate(gen_request))

        output_path = str(tmp_path / "downloaded.stl")
        success = asyncio.run(client.download_model(
            gen_result.provider_task_id,
            output_path,
        ))

        assert success
        assert Path(output_path).exists()


class TestMeshyClient:
    """Tests for MeshyClient."""

    @pytest.fixture
    def client(self):
        """Create client without API key."""
        return MeshyClient(api_key=None)

    def test_no_api_key_error(self, client):
        """Test error when no API key configured."""
        request = GenerationRequest(prompt="test")
        result = asyncio.run(client.generate(request))

        assert result.status == GenerationStatus.FAILED
        assert "API key" in result.error_message

    def test_headers(self):
        """Test headers include auth."""
        client = MeshyClient(api_key="test_key")
        headers = client._get_headers()

        assert "Authorization" in headers
        assert "Bearer test_key" in headers["Authorization"]


class TestTripoClient:
    """Tests for TripoClient."""

    @pytest.fixture
    def client(self):
        """Create client without API key."""
        return TripoClient(api_key=None)

    def test_no_api_key_error(self, client):
        """Test error when no API key configured."""
        request = GenerationRequest(prompt="test")
        result = asyncio.run(client.generate(request))

        assert result.status == GenerationStatus.FAILED
        assert "API key" in result.error_message


class TestTextTo3DGenerator:
    """Tests for TextTo3DGenerator."""

    @pytest.fixture
    def generator(self):
        """Create a generator."""
        return TextTo3DGenerator(default_provider=GenerationProvider.MOCK)

    def test_mock_always_available(self, generator):
        """Test mock provider is always available."""
        assert generator.is_provider_available(GenerationProvider.MOCK)

    def test_get_available_providers(self, generator):
        """Test getting available providers."""
        providers = generator.get_available_providers()

        assert GenerationProvider.MOCK in providers

    def test_generate_with_mock(self, generator, tmp_path):
        """Test generating with mock provider."""
        result = asyncio.run(generator.generate(
            prompt="test cube",
            provider=GenerationProvider.MOCK,
            output_dir=str(tmp_path),
        ))

        assert result.is_successful
        assert Path(result.output_path).exists()

    def test_generate_sync(self, generator, tmp_path):
        """Test synchronous generate wrapper."""
        result = generator.generate_sync(
            prompt="test sphere",
            provider=GenerationProvider.MOCK,
            output_dir=str(tmp_path),
        )

        assert result.is_successful

    def test_unavailable_provider_error(self, generator):
        """Test error for unavailable provider."""
        with pytest.raises(ValueError, match="not available"):
            asyncio.run(generator.generate(
                prompt="test",
                provider=GenerationProvider.MESHY,  # No API key
            ))

    def test_generate_with_all_options(self, generator, tmp_path):
        """Test generate with all options specified."""
        result = asyncio.run(generator.generate(
            prompt="a robot figure",
            provider=GenerationProvider.MOCK,
            output_format=ModelFormat.STL,
            art_style=ArtStyle.PRINTABLE,
            output_dir=str(tmp_path),
            output_name="robot_test",
            negative_prompt="broken, damaged",
            seed=42,
        ))

        assert result.is_successful
        assert "robot_test" in result.output_path


class TestGenerateModelFunction:
    """Tests for generate_model convenience function."""

    def test_generate_model_mock(self, tmp_path):
        """Test convenience function with mock."""
        result = generate_model(
            prompt="simple cube",
            provider="mock",
            output_dir=str(tmp_path),
        )

        assert result.is_successful

    def test_generate_model_unknown_provider(self):
        """Test error for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            generate_model(
                prompt="test",
                provider="unknown_provider",
            )


class TestGenerationIntegration:
    """Integration tests for the full generation flow."""

    def test_full_mock_flow(self, tmp_path):
        """Test complete generation flow with mock."""
        generator = TextTo3DGenerator()

        # Generate
        result = asyncio.run(generator.generate(
            prompt="phone case with dragon design",
            provider=GenerationProvider.MOCK,
            output_format=ModelFormat.STL,
            output_dir=str(tmp_path),
            output_name="dragon_case",
        ))

        assert result.is_successful
        assert result.output_path is not None

        # Verify file
        output_file = Path(result.output_path)
        assert output_file.exists()
        assert output_file.suffix == ".stl"
        assert output_file.stat().st_size > 0

        # Verify content
        content = output_file.read_text()
        assert "solid" in content.lower()

    def test_generation_with_analysis(self, tmp_path):
        """Test generation followed by design analysis."""
        from src.blender.design_advisor import DesignAdvisor

        # Generate model
        generator = TextTo3DGenerator()
        gen_result = asyncio.run(generator.generate(
            prompt="simple bracket",
            provider=GenerationProvider.MOCK,
            output_dir=str(tmp_path),
        ))

        assert gen_result.is_successful

        # Analyze the generated model
        advisor = DesignAdvisor()
        advice = advisor.analyze(gen_result.output_path)

        # Should be able to analyze the mock model
        assert advice.printability_score >= 0
        assert advice.file_path == gen_result.output_path
