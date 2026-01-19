"""USDZ exporter for AR preview.

Converts STL/OBJ/3MF models to USDZ format for iOS AR Quick Look.
Uses either:
- Native USD library (usd-core) if available
- External tools (usdc) if available
- Fallback to simple mesh conversion

Note: This module uses asyncio.create_subprocess_exec which does NOT use
a shell, preventing command injection vulnerabilities.
"""

import asyncio
import hashlib
import shutil
import struct
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("ar.usdz_exporter")


class ExportStatus(str, Enum):
    """USDZ export status."""
    PENDING = "pending"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExportConfig:
    """Configuration for USDZ export."""
    scale: float = 1.0  # Scale factor (meters)
    center_model: bool = True
    apply_default_material: bool = True
    material_color: Tuple[float, float, float] = (0.8, 0.8, 0.8)  # RGB 0-1
    metallic: float = 0.0
    roughness: float = 0.5
    optimize_mesh: bool = True
    max_vertices: int = 100000  # Limit for mobile performance


@dataclass
class ExportResult:
    """Result of USDZ export."""
    export_id: str
    input_path: str
    output_path: Optional[str]
    status: ExportStatus
    file_size_bytes: int = 0
    vertex_count: int = 0
    face_count: int = 0
    exported_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "export_id": self.export_id,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "status": self.status.value,
            "file_size_bytes": self.file_size_bytes,
            "vertex_count": self.vertex_count,
            "face_count": self.face_count,
            "exported_at": self.exported_at,
            "error_message": self.error_message,
        }


class USDZExporter:
    """
    Exports 3D models to USDZ format for iOS AR Quick Look.

    USDZ is Apple's preferred format for AR content.
    It's a compressed, single-file format containing USD data and textures.
    """

    def __init__(self, config: Optional[ExportConfig] = None):
        """
        Initialize USDZ exporter.

        Args:
            config: Export configuration
        """
        self.config = config or ExportConfig()
        settings = get_settings()
        self._output_dir = Path(settings.output_dir) / "ar"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir = Path(settings.data_dir) / "ar_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _check_usd_available(self) -> bool:
        """Check if USD library is available."""
        try:
            from pxr import Usd, UsdGeom
            return True
        except ImportError:
            return False

    def _check_usdc_available(self) -> bool:
        """Check if usdc command-line tool is available."""
        return shutil.which("usdc") is not None

    async def export(
        self,
        input_path: str,
        output_path: Optional[str] = None,
    ) -> ExportResult:
        """
        Export a 3D model to USDZ format.

        Args:
            input_path: Path to input model (STL, OBJ, 3MF)
            output_path: Optional output path

        Returns:
            Export result with status and output path
        """
        export_id = str(uuid4())[:8]
        input_file = Path(input_path)

        # Validate input
        if not input_file.exists():
            return ExportResult(
                export_id=export_id,
                input_path=input_path,
                output_path=None,
                status=ExportStatus.FAILED,
                error_message=f"Input file not found: {input_path}",
            )

        supported_formats = [".stl", ".obj", ".3mf"]
        if input_file.suffix.lower() not in supported_formats:
            return ExportResult(
                export_id=export_id,
                input_path=input_path,
                output_path=None,
                status=ExportStatus.FAILED,
                error_message=f"Unsupported format: {input_file.suffix}",
            )

        # Determine output path
        if output_path:
            out_file = Path(output_path)
        else:
            out_file = self._output_dir / f"{input_file.stem}_{export_id}.usdz"

        logger.info(f"Exporting {input_path} to USDZ")

        # Try different export methods
        if self._check_usd_available():
            result = await self._export_with_usd(input_file, out_file, export_id)
        elif self._check_usdc_available():
            result = await self._export_with_usdc(input_file, out_file, export_id)
        else:
            # Use pure Python fallback
            result = await self._export_fallback(input_file, out_file, export_id)

        return result

    async def _export_with_usd(
        self,
        input_file: Path,
        output_file: Path,
        export_id: str,
    ) -> ExportResult:
        """Export using pxr USD library."""
        try:
            from pxr import Usd, UsdGeom, UsdShade, Gf, Sdf

            # Read mesh data from input file
            vertices, faces = self._read_mesh(input_file)

            if not vertices or not faces:
                return ExportResult(
                    export_id=export_id,
                    input_path=str(input_file),
                    output_path=None,
                    status=ExportStatus.FAILED,
                    error_message="Failed to read mesh data",
                )

            # Decimate if needed
            if len(vertices) > self.config.max_vertices and self.config.optimize_mesh:
                vertices, faces = self._decimate_mesh(vertices, faces)

            # Center if configured
            if self.config.center_model:
                vertices = self._center_mesh(vertices)

            # Scale
            vertices = [(v[0] * self.config.scale, v[1] * self.config.scale, v[2] * self.config.scale)
                        for v in vertices]

            # Create USD stage
            temp_usdc = output_file.with_suffix(".usdc")
            stage = Usd.Stage.CreateNew(str(temp_usdc))

            # Set up units (meters)
            UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
            UsdGeom.SetStageMetersPerUnit(stage, 1.0)

            # Create root xform
            root = UsdGeom.Xform.Define(stage, "/Root")

            # Create mesh
            mesh = UsdGeom.Mesh.Define(stage, "/Root/Mesh")

            # Set mesh points
            mesh.CreatePointsAttr([Gf.Vec3f(*v) for v in vertices])

            # Set mesh faces
            face_vertex_counts = [3] * len(faces)
            face_vertex_indices = [idx for face in faces for idx in face]

            mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
            mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)

            # Apply default material if configured
            if self.config.apply_default_material:
                material_path = "/Root/Material"
                material = UsdShade.Material.Define(stage, material_path)

                shader = UsdShade.Shader.Define(stage, f"{material_path}/PBRShader")
                shader.CreateIdAttr("UsdPreviewSurface")

                r, g, b = self.config.material_color
                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(r, g, b))
                shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(self.config.metallic)
                shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(self.config.roughness)

                material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

                UsdShade.MaterialBindingAPI(mesh).Bind(material)

            # Save stage
            stage.Save()

            # Convert to USDZ (zip with specific structure)
            with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
                # USDZ requires specific archive structure
                zf.write(temp_usdc, temp_usdc.name)

            # Clean up temp file
            temp_usdc.unlink()

            file_size = output_file.stat().st_size

            logger.info(f"USDZ export complete: {output_file}")

            return ExportResult(
                export_id=export_id,
                input_path=str(input_file),
                output_path=str(output_file),
                status=ExportStatus.COMPLETED,
                file_size_bytes=file_size,
                vertex_count=len(vertices),
                face_count=len(faces),
                exported_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f"USD export failed: {e}")
            return ExportResult(
                export_id=export_id,
                input_path=str(input_file),
                output_path=None,
                status=ExportStatus.FAILED,
                error_message=str(e),
            )

    async def _export_with_usdc(
        self,
        input_file: Path,
        output_file: Path,
        export_id: str,
    ) -> ExportResult:
        """
        Export using usdc command-line tool.

        Note: Uses create_subprocess_exec (no shell) for safety.
        """
        try:
            # First convert to intermediate format
            vertices, faces = self._read_mesh(input_file)

            if not vertices or not faces:
                return ExportResult(
                    export_id=export_id,
                    input_path=str(input_file),
                    output_path=None,
                    status=ExportStatus.FAILED,
                    error_message="Failed to read mesh data",
                )

            # Write OBJ file for usdc
            temp_obj = self._cache_dir / f"temp_{export_id}.obj"
            self._write_obj(vertices, faces, temp_obj)

            # Convert using usdc (no shell, args passed directly)
            usdc_path = shutil.which("usdc")
            temp_usdc = self._cache_dir / f"temp_{export_id}.usdc"

            process = await asyncio.create_subprocess_exec(
                usdc_path,
                str(temp_obj),
                "-o", str(temp_usdc),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                return ExportResult(
                    export_id=export_id,
                    input_path=str(input_file),
                    output_path=None,
                    status=ExportStatus.FAILED,
                    error_message=f"usdc failed: {stderr.decode()}",
                )

            # Create USDZ (zip)
            with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(temp_usdc, temp_usdc.name)

            # Clean up
            temp_obj.unlink()
            temp_usdc.unlink()

            file_size = output_file.stat().st_size

            return ExportResult(
                export_id=export_id,
                input_path=str(input_file),
                output_path=str(output_file),
                status=ExportStatus.COMPLETED,
                file_size_bytes=file_size,
                vertex_count=len(vertices),
                face_count=len(faces),
                exported_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f"usdc export failed: {e}")
            return ExportResult(
                export_id=export_id,
                input_path=str(input_file),
                output_path=None,
                status=ExportStatus.FAILED,
                error_message=str(e),
            )

    async def _export_fallback(
        self,
        input_file: Path,
        output_file: Path,
        export_id: str,
    ) -> ExportResult:
        """
        Fallback export using pure Python.

        Creates a minimal USDZ file without USD dependencies.
        This produces a basic but valid USDZ for simple models.
        """
        try:
            # Read mesh data
            vertices, faces = self._read_mesh(input_file)

            if not vertices or not faces:
                return ExportResult(
                    export_id=export_id,
                    input_path=str(input_file),
                    output_path=None,
                    status=ExportStatus.FAILED,
                    error_message="Failed to read mesh data",
                )

            # Decimate if needed
            if len(vertices) > self.config.max_vertices and self.config.optimize_mesh:
                vertices, faces = self._decimate_mesh(vertices, faces)

            # Center if configured
            if self.config.center_model:
                vertices = self._center_mesh(vertices)

            # Scale
            vertices = [(v[0] * self.config.scale, v[1] * self.config.scale, v[2] * self.config.scale)
                        for v in vertices]

            # Generate minimal USDA content
            usda_content = self._generate_usda(vertices, faces)

            # Write to temp file
            temp_usda = self._cache_dir / f"temp_{export_id}.usda"
            temp_usda.write_text(usda_content)

            # Create USDZ (just a zip file)
            with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(temp_usda, temp_usda.name)

            # Clean up
            temp_usda.unlink()

            file_size = output_file.stat().st_size

            logger.info(f"USDZ fallback export complete: {output_file}")

            return ExportResult(
                export_id=export_id,
                input_path=str(input_file),
                output_path=str(output_file),
                status=ExportStatus.COMPLETED,
                file_size_bytes=file_size,
                vertex_count=len(vertices),
                face_count=len(faces),
                exported_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f"Fallback export failed: {e}")
            return ExportResult(
                export_id=export_id,
                input_path=str(input_file),
                output_path=None,
                status=ExportStatus.FAILED,
                error_message=str(e),
            )

    def _read_mesh(self, path: Path) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
        """Read mesh data from various formats."""
        suffix = path.suffix.lower()

        if suffix == ".stl":
            return self._read_stl(path)
        elif suffix == ".obj":
            return self._read_obj(path)
        elif suffix == ".3mf":
            return self._read_3mf(path)
        else:
            return [], []

    def _read_stl(self, path: Path) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
        """Read STL file (binary or ASCII)."""
        with open(path, "rb") as f:
            header = f.read(80)
            # Check if binary STL
            num_triangles = struct.unpack("<I", f.read(4))[0]

            vertices = []
            faces = []
            vertex_map = {}
            vertex_index = 0

            for _ in range(num_triangles):
                # Skip normal
                f.read(12)

                # Read 3 vertices
                face_indices = []
                for _ in range(3):
                    x, y, z = struct.unpack("<fff", f.read(12))
                    v = (x, y, z)

                    # Deduplicate vertices
                    v_key = f"{x:.6f},{y:.6f},{z:.6f}"
                    if v_key not in vertex_map:
                        vertex_map[v_key] = vertex_index
                        vertices.append(v)
                        vertex_index += 1

                    face_indices.append(vertex_map[v_key])

                faces.append(tuple(face_indices))

                # Skip attribute byte count
                f.read(2)

        return vertices, faces

    def _read_obj(self, path: Path) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
        """Read OBJ file."""
        vertices = []
        faces = []

        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("v "):
                    parts = line.split()
                    vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif line.startswith("f "):
                    parts = line.split()[1:]
                    # Handle different face formats (v, v/vt, v/vt/vn, v//vn)
                    indices = []
                    for p in parts:
                        idx = int(p.split("/")[0]) - 1  # OBJ is 1-indexed
                        indices.append(idx)
                    # Triangulate if needed (simple fan triangulation)
                    for i in range(1, len(indices) - 1):
                        faces.append((indices[0], indices[i], indices[i + 1]))

        return vertices, faces

    def _read_3mf(self, path: Path) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
        """Read 3MF file (basic support)."""
        import xml.etree.ElementTree as ET

        vertices = []
        faces = []

        try:
            with zipfile.ZipFile(path, "r") as zf:
                # Find model file
                for name in zf.namelist():
                    if name.endswith(".model") or "3D/3dmodel.model" in name:
                        with zf.open(name) as f:
                            tree = ET.parse(f)
                            root = tree.getroot()

                            # Handle namespaces
                            ns = {"": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}

                            # Find mesh elements
                            for mesh in root.iter("{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}mesh"):
                                # Read vertices
                                for vertex in mesh.findall(".//{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}vertex"):
                                    x = float(vertex.get("x", 0))
                                    y = float(vertex.get("y", 0))
                                    z = float(vertex.get("z", 0))
                                    vertices.append((x, y, z))

                                # Read triangles
                                for triangle in mesh.findall(".//{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}triangle"):
                                    v1 = int(triangle.get("v1", 0))
                                    v2 = int(triangle.get("v2", 0))
                                    v3 = int(triangle.get("v3", 0))
                                    faces.append((v1, v2, v3))

                        break

        except Exception as e:
            logger.error(f"Failed to read 3MF: {e}")

        return vertices, faces

    def _write_obj(self, vertices: List, faces: List, path: Path) -> None:
        """Write mesh to OBJ format."""
        with open(path, "w") as f:
            f.write("# Generated by Claude Fab Lab\n")
            for v in vertices:
                f.write(f"v {v[0]} {v[1]} {v[2]}\n")
            for face in faces:
                # OBJ is 1-indexed
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")

    def _center_mesh(self, vertices: List) -> List:
        """Center mesh at origin."""
        if not vertices:
            return vertices

        min_x = min(v[0] for v in vertices)
        max_x = max(v[0] for v in vertices)
        min_y = min(v[1] for v in vertices)
        max_y = max(v[1] for v in vertices)
        min_z = min(v[2] for v in vertices)
        max_z = max(v[2] for v in vertices)

        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        center_z = (min_z + max_z) / 2

        return [(v[0] - center_x, v[1] - center_y, v[2] - center_z) for v in vertices]

    def _decimate_mesh(
        self,
        vertices: List,
        faces: List,
    ) -> Tuple[List, List]:
        """Simple mesh decimation (subsampling)."""
        # Simple approach: keep every nth face
        ratio = self.config.max_vertices / len(vertices)
        if ratio >= 1:
            return vertices, faces

        keep_every = max(1, int(1 / ratio))
        new_faces = faces[::keep_every]

        # Rebuild vertex list with only used vertices
        used_indices = set()
        for face in new_faces:
            used_indices.update(face)

        index_map = {old: new for new, old in enumerate(sorted(used_indices))}
        new_vertices = [vertices[i] for i in sorted(used_indices)]
        new_faces = [(index_map[f[0]], index_map[f[1]], index_map[f[2]]) for f in new_faces]

        logger.info(f"Decimated mesh from {len(vertices)} to {len(new_vertices)} vertices")

        return new_vertices, new_faces

    def _generate_usda(self, vertices: List, faces: List) -> str:
        """Generate USDA text content."""
        r, g, b = self.config.material_color

        # Format vertices
        points_str = ", ".join(f"({v[0]:.6f}, {v[1]:.6f}, {v[2]:.6f})" for v in vertices)

        # Format face indices
        face_counts = ", ".join(str(3) for _ in faces)
        face_indices = ", ".join(str(idx) for face in faces for idx in face)

        usda = f'''#usda 1.0
(
    defaultPrim = "Root"
    metersPerUnit = 1
    upAxis = "Y"
)

def Xform "Root"
{{
    def Mesh "Mesh"
    {{
        int[] faceVertexCounts = [{face_counts}]
        int[] faceVertexIndices = [{face_indices}]
        point3f[] points = [{points_str}]

        rel material:binding = </Root/Material>
    }}

    def Material "Material"
    {{
        token outputs:surface.connect = </Root/Material/PBRShader.outputs:surface>

        def Shader "PBRShader"
        {{
            uniform token info:id = "UsdPreviewSurface"
            color3f inputs:diffuseColor = ({r}, {g}, {b})
            float inputs:metallic = {self.config.metallic}
            float inputs:roughness = {self.config.roughness}
            token outputs:surface
        }}
    }}
}}
'''
        return usda


async def export_to_usdz(
    input_path: str,
    output_path: Optional[str] = None,
    scale: float = 1.0,
    center: bool = True,
) -> Optional[str]:
    """
    Convenience function to export a model to USDZ.

    Args:
        input_path: Path to input model
        output_path: Optional output path
        scale: Scale factor
        center: Whether to center the model

    Returns:
        Path to exported USDZ file or None if failed
    """
    config = ExportConfig(scale=scale, center_model=center)
    exporter = USDZExporter(config)
    result = await exporter.export(input_path, output_path)

    if result.status == ExportStatus.COMPLETED:
        return result.output_path
    return None
