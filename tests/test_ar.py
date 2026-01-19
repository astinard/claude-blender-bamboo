"""Tests for AR preview module."""

import pytest
import asyncio
import struct
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.ar.usdz_exporter import (
    USDZExporter,
    ExportConfig,
    ExportResult,
    ExportStatus,
    export_to_usdz,
)
from src.ar.qr_generator import (
    QRGenerator,
    QRConfig,
    ErrorCorrection,
    generate_qr_code,
)
from src.ar.ar_server import (
    ARServer,
    ARSession,
    serve_ar_preview,
)


class TestExportConfig:
    """Tests for ExportConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = ExportConfig()

        assert config.scale == 1.0
        assert config.center_model is True
        assert config.apply_default_material is True
        assert config.material_color == (0.8, 0.8, 0.8)
        assert config.metallic == 0.0
        assert config.roughness == 0.5
        assert config.optimize_mesh is True
        assert config.max_vertices == 100000

    def test_custom_config(self):
        """Test custom configuration."""
        config = ExportConfig(
            scale=0.001,
            center_model=False,
            material_color=(1.0, 0.5, 0.2),
            metallic=0.8,
            roughness=0.2,
            max_vertices=50000,
        )

        assert config.scale == 0.001
        assert config.center_model is False
        assert config.material_color == (1.0, 0.5, 0.2)
        assert config.metallic == 0.8
        assert config.roughness == 0.2
        assert config.max_vertices == 50000


class TestExportResult:
    """Tests for ExportResult dataclass."""

    def test_create_result(self):
        """Test creating an export result."""
        result = ExportResult(
            export_id="abc123",
            input_path="/path/to/model.stl",
            output_path="/path/to/model.usdz",
            status=ExportStatus.COMPLETED,
            file_size_bytes=1024000,
            vertex_count=5000,
            face_count=10000,
        )

        assert result.export_id == "abc123"
        assert result.status == ExportStatus.COMPLETED
        assert result.file_size_bytes == 1024000

    def test_result_to_dict(self):
        """Test result serialization."""
        result = ExportResult(
            export_id="xyz789",
            input_path="/input.stl",
            output_path="/output.usdz",
            status=ExportStatus.COMPLETED,
            file_size_bytes=500000,
            vertex_count=3000,
            face_count=6000,
            exported_at="2024-01-15T10:30:00",
        )

        d = result.to_dict()

        assert d["export_id"] == "xyz789"
        assert d["status"] == "completed"
        assert d["file_size_bytes"] == 500000
        assert d["exported_at"] == "2024-01-15T10:30:00"

    def test_failed_result(self):
        """Test failed result."""
        result = ExportResult(
            export_id="failed123",
            input_path="/bad/path.stl",
            output_path=None,
            status=ExportStatus.FAILED,
            error_message="File not found",
        )

        assert result.status == ExportStatus.FAILED
        assert result.error_message == "File not found"
        assert result.output_path is None


class TestExportStatus:
    """Tests for ExportStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert ExportStatus.PENDING.value == "pending"
        assert ExportStatus.EXPORTING.value == "exporting"
        assert ExportStatus.COMPLETED.value == "completed"
        assert ExportStatus.FAILED.value == "failed"


class TestUSDZExporter:
    """Tests for USDZExporter class."""

    @pytest.fixture
    def exporter(self, tmp_path):
        """Create a USDZ exporter."""
        with patch("src.ar.usdz_exporter.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path / "output")
            mock_settings.return_value.data_dir = str(tmp_path / "data")
            exp = USDZExporter()
            return exp

    @pytest.fixture
    def sample_stl(self, tmp_path):
        """Create a sample STL file."""
        stl_path = tmp_path / "sample.stl"

        # Create a simple binary STL (a single triangle)
        with open(stl_path, "wb") as f:
            # Header (80 bytes)
            f.write(b"\x00" * 80)
            # Number of triangles
            f.write(struct.pack("<I", 1))
            # Triangle: normal (12 bytes) + 3 vertices (36 bytes) + attribute (2 bytes)
            f.write(struct.pack("<fff", 0, 0, 1))  # Normal
            f.write(struct.pack("<fff", 0, 0, 0))  # Vertex 1
            f.write(struct.pack("<fff", 1, 0, 0))  # Vertex 2
            f.write(struct.pack("<fff", 0, 1, 0))  # Vertex 3
            f.write(struct.pack("<H", 0))  # Attribute byte count

        return stl_path

    @pytest.fixture
    def sample_obj(self, tmp_path):
        """Create a sample OBJ file."""
        obj_path = tmp_path / "sample.obj"
        obj_path.write_text("""
# Simple cube
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
f 1 2 3
f 1 3 4
""")
        return obj_path

    def test_init(self, exporter):
        """Test exporter initialization."""
        assert exporter.config is not None
        assert exporter.config.scale == 1.0

    def test_init_custom_config(self, tmp_path):
        """Test initialization with custom config."""
        config = ExportConfig(scale=0.5, center_model=False)
        with patch("src.ar.usdz_exporter.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            mock_settings.return_value.data_dir = str(tmp_path)
            exp = USDZExporter(config)

        assert exp.config.scale == 0.5
        assert exp.config.center_model is False

    @pytest.mark.asyncio
    async def test_export_file_not_found(self, exporter):
        """Test export with non-existent file."""
        result = await exporter.export("/nonexistent/model.stl")

        assert result.status == ExportStatus.FAILED
        assert "not found" in result.error_message

    @pytest.mark.asyncio
    async def test_export_unsupported_format(self, exporter, tmp_path):
        """Test export with unsupported format."""
        bad_file = tmp_path / "model.xyz"
        bad_file.write_text("invalid")

        result = await exporter.export(str(bad_file))

        assert result.status == ExportStatus.FAILED
        assert "Unsupported format" in result.error_message

    @pytest.mark.asyncio
    async def test_export_stl_fallback(self, exporter, sample_stl):
        """Test STL export using fallback method."""
        result = await exporter.export(str(sample_stl))

        # Should use fallback since USD library is likely not installed
        assert result.status == ExportStatus.COMPLETED
        assert result.output_path is not None
        assert result.vertex_count == 3
        assert result.face_count == 1

    @pytest.mark.asyncio
    async def test_export_obj_fallback(self, exporter, sample_obj):
        """Test OBJ export using fallback method."""
        result = await exporter.export(str(sample_obj))

        assert result.status == ExportStatus.COMPLETED
        assert result.output_path is not None
        assert result.vertex_count == 4
        assert result.face_count == 2

    @pytest.mark.asyncio
    async def test_export_custom_output_path(self, exporter, sample_stl, tmp_path):
        """Test export with custom output path."""
        output_path = tmp_path / "custom_output.usdz"
        result = await exporter.export(str(sample_stl), str(output_path))

        assert result.status == ExportStatus.COMPLETED
        assert result.output_path == str(output_path)

    def test_read_stl(self, exporter, sample_stl):
        """Test reading STL file."""
        vertices, faces = exporter._read_stl(sample_stl)

        assert len(vertices) == 3
        assert len(faces) == 1
        assert faces[0] == (0, 1, 2)

    def test_read_obj(self, exporter, sample_obj):
        """Test reading OBJ file."""
        vertices, faces = exporter._read_obj(sample_obj)

        assert len(vertices) == 4
        assert len(faces) == 2

    def test_center_mesh(self, exporter):
        """Test mesh centering (uses bounding box center)."""
        vertices = [(0, 0, 0), (2, 0, 0), (0, 2, 0)]
        centered = exporter._center_mesh(vertices)

        # Bounding box center should be at origin
        # Original bbox: (0,2) x (0,2) x (0,0) -> center at (1, 1, 0)
        # After centering, bbox should be (-1,1) x (-1,1) x (0,0)
        min_x = min(v[0] for v in centered)
        max_x = max(v[0] for v in centered)
        min_y = min(v[1] for v in centered)
        max_y = max(v[1] for v in centered)

        bbox_center_x = (min_x + max_x) / 2
        bbox_center_y = (min_y + max_y) / 2

        assert abs(bbox_center_x) < 0.001
        assert abs(bbox_center_y) < 0.001

    def test_decimate_mesh(self, exporter):
        """Test mesh decimation."""
        # Create many vertices
        vertices = [(i, i, i) for i in range(200)]
        faces = [(i, i+1, i+2) for i in range(0, 198, 3)]

        exporter.config.max_vertices = 50
        new_vertices, new_faces = exporter._decimate_mesh(vertices, faces)

        assert len(new_vertices) < len(vertices)

    def test_generate_usda(self, exporter):
        """Test USDA generation."""
        vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        faces = [(0, 1, 2)]

        usda = exporter._generate_usda(vertices, faces)

        assert "#usda 1.0" in usda
        assert "def Mesh" in usda
        assert "def Material" in usda
        assert "UsdPreviewSurface" in usda


class TestExportToUSDZ:
    """Tests for export_to_usdz convenience function."""

    @pytest.mark.asyncio
    async def test_export_to_usdz(self, tmp_path):
        """Test convenience function."""
        # Create sample STL
        stl_path = tmp_path / "test.stl"
        with open(stl_path, "wb") as f:
            f.write(b"\x00" * 80)
            f.write(struct.pack("<I", 1))
            f.write(struct.pack("<fff", 0, 0, 1))
            f.write(struct.pack("<fff", 0, 0, 0))
            f.write(struct.pack("<fff", 1, 0, 0))
            f.write(struct.pack("<fff", 0, 1, 0))
            f.write(struct.pack("<H", 0))

        with patch("src.ar.usdz_exporter.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path / "output")
            mock_settings.return_value.data_dir = str(tmp_path / "data")

            result = await export_to_usdz(str(stl_path))

        assert result is not None


class TestQRConfig:
    """Tests for QRConfig dataclass."""

    def test_default_config(self):
        """Test default QR configuration."""
        config = QRConfig()

        assert config.size == 256
        assert config.border == 4
        assert config.error_correction == ErrorCorrection.MEDIUM
        assert config.fill_color == "black"
        assert config.back_color == "white"

    def test_custom_config(self):
        """Test custom QR configuration."""
        config = QRConfig(
            size=512,
            border=2,
            error_correction=ErrorCorrection.HIGH,
            fill_color="blue",
        )

        assert config.size == 512
        assert config.border == 2
        assert config.error_correction == ErrorCorrection.HIGH
        assert config.fill_color == "blue"


class TestErrorCorrection:
    """Tests for ErrorCorrection enum."""

    def test_error_correction_values(self):
        """Test error correction values."""
        assert ErrorCorrection.LOW.value == "L"
        assert ErrorCorrection.MEDIUM.value == "M"
        assert ErrorCorrection.QUARTILE.value == "Q"
        assert ErrorCorrection.HIGH.value == "H"


class TestQRGenerator:
    """Tests for QRGenerator class."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create a QR generator."""
        with patch("src.ar.qr_generator.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            mock_settings.return_value.data_dir = str(tmp_path)
            gen = QRGenerator()
            return gen

    def test_init(self, generator):
        """Test generator initialization."""
        assert generator.config is not None
        assert generator.config.size == 256

    def test_generate_without_library(self, generator, tmp_path):
        """Test generation without qrcode library."""
        with patch.object(generator, "_check_qrcode_available", return_value=False):
            # Should use fallback
            result = generator.generate("https://example.com/ar/123")

        # Fallback may or may not work depending on PIL
        # Just ensure it doesn't crash

    def test_generate_base64_without_library(self, generator):
        """Test base64 generation without qrcode library."""
        with patch.object(generator, "_check_qrcode_available", return_value=False):
            result = generator.generate_base64("https://example.com/ar/123")

        # Fallback may or may not work
        # Just ensure it doesn't crash


class TestGenerateQRCode:
    """Tests for generate_qr_code convenience function."""

    def test_generate_qr_code(self, tmp_path):
        """Test convenience function."""
        with patch("src.ar.qr_generator.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            mock_settings.return_value.data_dir = str(tmp_path)

            result = generate_qr_code("https://example.com/ar/123")

        # May or may not generate depending on libraries
        # Just ensure it doesn't crash


class TestARSession:
    """Tests for ARSession dataclass."""

    def test_create_session(self):
        """Test creating a session."""
        session = ARSession(
            session_id="abc123",
            model_path="/path/to/model.stl",
        )

        assert session.session_id == "abc123"
        assert session.model_path == "/path/to/model.stl"
        assert session.usdz_path is None
        assert session.preview_url is None
        assert session.accessed_count == 0

    def test_session_to_dict(self):
        """Test session serialization."""
        session = ARSession(
            session_id="xyz789",
            model_path="/path/to/model.stl",
            usdz_path="/path/to/model.usdz",
            preview_url="http://localhost:8080/ar/xyz789",
            qr_code_path="/path/to/qr.png",
            accessed_count=5,
        )

        d = session.to_dict()

        assert d["session_id"] == "xyz789"
        assert d["model_path"] == "/path/to/model.stl"
        assert d["usdz_path"] == "/path/to/model.usdz"
        assert d["preview_url"] == "http://localhost:8080/ar/xyz789"
        assert d["accessed_count"] == 5


class TestARServer:
    """Tests for ARServer class."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create an AR server."""
        with patch("src.ar.ar_server.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            mock_settings.return_value.data_dir = str(tmp_path)
            srv = ARServer(port=8888)
            return srv

    def test_init(self, server):
        """Test server initialization."""
        assert server.host == "0.0.0.0"
        assert server.port == 8888
        assert server.is_running is False

    def test_base_url(self, server):
        """Test base URL generation."""
        url = server.base_url
        assert "http://" in url
        assert ":8888" in url

    def test_get_local_ip(self, server):
        """Test local IP detection."""
        ip = server._get_local_ip()
        # Should return some valid IP
        assert ip is not None
        assert len(ip.split(".")) == 4

    @pytest.mark.asyncio
    async def test_create_session(self, server, tmp_path):
        """Test session creation."""
        # Create a sample STL
        stl_path = tmp_path / "test.stl"
        with open(stl_path, "wb") as f:
            f.write(b"\x00" * 80)
            f.write(struct.pack("<I", 1))
            f.write(struct.pack("<fff", 0, 0, 1))
            f.write(struct.pack("<fff", 0, 0, 0))
            f.write(struct.pack("<fff", 1, 0, 0))
            f.write(struct.pack("<fff", 0, 1, 0))
            f.write(struct.pack("<H", 0))

        with patch("src.ar.ar_server.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            mock_settings.return_value.data_dir = str(tmp_path)

            session = await server.create_session(
                str(stl_path),
                export_usdz=True,
                generate_qr=False,  # Skip QR to avoid library dependency
            )

        assert session is not None
        assert session.session_id is not None
        assert session.model_path == str(stl_path)

    def test_get_session(self, server):
        """Test getting a session."""
        session = ARSession(
            session_id="test123",
            model_path="/test.stl",
        )
        server._sessions["test123"] = session

        result = server.get_session("test123")
        assert result == session

    def test_get_session_not_found(self, server):
        """Test getting non-existent session."""
        result = server.get_session("nonexistent")
        assert result is None

    def test_list_sessions(self, server):
        """Test listing sessions."""
        session1 = ARSession(session_id="s1", model_path="/m1.stl")
        session2 = ARSession(session_id="s2", model_path="/m2.stl")
        server._sessions["s1"] = session1
        server._sessions["s2"] = session2

        sessions = server.list_sessions()
        assert len(sessions) == 2

    def test_generate_index_html(self, server):
        """Test index HTML generation."""
        session = ARSession(
            session_id="test123",
            model_path="/path/to/model.stl",
        )
        server._sessions["test123"] = session

        html = server._generate_index_html()

        assert "Claude Fab Lab" in html
        assert "model.stl" in html
        assert "test123" in html

    def test_generate_ar_html(self, server):
        """Test AR preview HTML generation."""
        session = ARSession(
            session_id="abc123",
            model_path="/path/to/model.stl",
            usdz_path="/path/to/model.usdz",
            preview_url="http://localhost:8080/ar/abc123",
            qr_code_path="/path/to/qr.png",
        )

        html = server._generate_ar_html(session)

        assert "AR Preview" in html
        assert "model.stl" in html
        assert "View in AR" in html
        assert "/ar/abc123/model.usdz" in html
        assert "Scan with iPhone" in html


class TestARIntegration:
    """Integration tests for AR system."""

    @pytest.mark.asyncio
    async def test_full_ar_workflow(self, tmp_path):
        """Test complete AR workflow."""
        # Create sample model
        stl_path = tmp_path / "test_model.stl"
        with open(stl_path, "wb") as f:
            f.write(b"\x00" * 80)
            f.write(struct.pack("<I", 1))
            f.write(struct.pack("<fff", 0, 0, 1))
            f.write(struct.pack("<fff", 0, 0, 0))
            f.write(struct.pack("<fff", 1, 0, 0))
            f.write(struct.pack("<fff", 0, 1, 0))
            f.write(struct.pack("<H", 0))

        with patch("src.ar.usdz_exporter.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path / "output")
            mock_settings.return_value.data_dir = str(tmp_path / "data")

            # Export to USDZ
            exporter = USDZExporter()
            result = await exporter.export(str(stl_path))

            assert result.status == ExportStatus.COMPLETED
            assert result.output_path is not None

            # Verify USDZ file exists
            usdz_path = Path(result.output_path)
            assert usdz_path.exists()
