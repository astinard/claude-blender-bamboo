"""Geometry analyzer for detecting printability issues.

P4.2: Print Failure Prediction - Geometry Analysis

Analyzes 3D models to detect:
- Overhangs that may require support
- Thin walls that may be too fragile
- Bridges that may fail
- Other geometry issues
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple
import math

from src.utils import get_logger

logger = get_logger("monitoring.geometry")


class IssueSeverity(str, Enum):
    """Severity of geometry issue."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class OverhangInfo:
    """Information about an overhang in the model."""
    angle: float  # Degrees from vertical (0 = vertical wall, 90 = horizontal ceiling)
    area_mm2: float  # Approximate affected area
    location: Tuple[float, float, float]  # Approximate center point
    severity: IssueSeverity

    @property
    def needs_support(self) -> bool:
        """Check if this overhang likely needs support."""
        return self.angle > 45

    def __str__(self) -> str:
        return f"Overhang at {self.angle:.1f}° ({self.severity.value})"


@dataclass
class ThinWallInfo:
    """Information about a thin wall in the model."""
    thickness_mm: float
    height_mm: float
    location: Tuple[float, float, float]
    severity: IssueSeverity

    @property
    def is_printable(self) -> bool:
        """Check if wall is likely printable with standard settings."""
        return self.thickness_mm >= 0.4  # Single wall minimum

    def __str__(self) -> str:
        return f"Thin wall: {self.thickness_mm:.2f}mm ({self.severity.value})"


@dataclass
class BridgeInfo:
    """Information about a bridge (unsupported span) in the model."""
    length_mm: float
    width_mm: float
    height_z: float  # Z position of bridge
    severity: IssueSeverity

    @property
    def is_printable(self) -> bool:
        """Check if bridge is likely printable without support."""
        # Most printers can bridge up to ~10mm reliably
        return self.length_mm <= 10

    def __str__(self) -> str:
        return f"Bridge: {self.length_mm:.1f}mm span ({self.severity.value})"


@dataclass
class GeometryIssue:
    """Generic geometry issue."""
    issue_type: str
    severity: IssueSeverity
    message: str
    suggestion: Optional[str] = None
    location: Optional[Tuple[float, float, float]] = None


@dataclass
class GeometryAnalysisResult:
    """Complete geometry analysis result."""
    overhangs: List[OverhangInfo] = field(default_factory=list)
    thin_walls: List[ThinWallInfo] = field(default_factory=list)
    bridges: List[BridgeInfo] = field(default_factory=list)
    other_issues: List[GeometryIssue] = field(default_factory=list)

    # Model dimensions
    bounding_box: Tuple[float, float, float] = (0, 0, 0)  # x, y, z dimensions
    volume_mm3: float = 0
    surface_area_mm2: float = 0
    triangle_count: int = 0

    @property
    def has_critical_issues(self) -> bool:
        """Check if any critical issues exist."""
        all_issues = (
            [o.severity for o in self.overhangs] +
            [t.severity for t in self.thin_walls] +
            [b.severity for b in self.bridges] +
            [i.severity for i in self.other_issues]
        )
        return IssueSeverity.CRITICAL in all_issues

    @property
    def total_issues(self) -> int:
        """Get total number of issues."""
        return (
            len(self.overhangs) +
            len(self.thin_walls) +
            len(self.bridges) +
            len(self.other_issues)
        )

    @property
    def needs_support(self) -> bool:
        """Check if model likely needs support structures."""
        return any(o.needs_support for o in self.overhangs)


def _load_mesh(file_path: Path):
    """Load a mesh from file. Returns trimesh if available, else None."""
    try:
        import trimesh
        mesh = trimesh.load(str(file_path))
        if hasattr(mesh, 'faces'):
            return mesh
        # Handle scene with multiple meshes
        if hasattr(mesh, 'geometry'):
            meshes = list(mesh.geometry.values())
            if meshes:
                return trimesh.util.concatenate(meshes)
        return None
    except ImportError:
        logger.warning("trimesh not installed, using simplified analysis")
        return None
    except Exception as e:
        logger.error(f"Failed to load mesh: {e}")
        return None


def _analyze_overhangs(mesh) -> List[OverhangInfo]:
    """Analyze mesh for overhangs."""
    overhangs = []

    if mesh is None:
        return overhangs

    try:
        import numpy as np

        # Get face normals
        normals = mesh.face_normals

        # Calculate angle from vertical (Z-up)
        z_axis = np.array([0, 0, 1])
        for i, normal in enumerate(normals):
            # Angle between face normal and Z axis
            # For downward-facing surfaces, the normal points down
            dot = np.dot(normal, z_axis)
            angle_rad = np.arccos(np.clip(dot, -1, 1))
            angle_deg = np.degrees(angle_rad)

            # Convert to overhang angle (90 = ceiling, 0 = floor)
            overhang_angle = 180 - angle_deg if normal[2] < 0 else angle_deg

            # Only consider downward-facing surfaces as overhangs
            if normal[2] < -0.01:  # Normal pointing down
                # Calculate actual overhang angle from horizontal
                overhang_from_horiz = 90 - abs(np.degrees(np.arcsin(abs(normal[2]))))

                if overhang_from_horiz > 30:  # Only report significant overhangs
                    # Get face centroid
                    face = mesh.faces[i]
                    centroid = mesh.vertices[face].mean(axis=0)
                    area = mesh.area_faces[i] if hasattr(mesh, 'area_faces') else 1.0

                    # Determine severity
                    if overhang_from_horiz > 60:
                        severity = IssueSeverity.CRITICAL
                    elif overhang_from_horiz > 45:
                        severity = IssueSeverity.WARNING
                    else:
                        severity = IssueSeverity.INFO

                    overhangs.append(OverhangInfo(
                        angle=overhang_from_horiz,
                        area_mm2=area,
                        location=tuple(centroid),
                        severity=severity,
                    ))

        # Deduplicate/cluster nearby overhangs
        if len(overhangs) > 100:
            # Just keep top 20 most severe
            overhangs.sort(key=lambda x: (x.severity.value, -x.angle))
            overhangs = overhangs[:20]

    except Exception as e:
        logger.warning(f"Overhang analysis error: {e}")

    return overhangs


def _analyze_thin_walls(mesh) -> List[ThinWallInfo]:
    """Analyze mesh for thin walls."""
    thin_walls = []

    if mesh is None:
        return thin_walls

    try:
        import numpy as np

        # Simple approach: check for vertices that are very close together
        # but belong to different faces (potential thin walls)

        # For now, check bounding box aspect ratios as a simpler heuristic
        bounds = mesh.bounds
        dimensions = bounds[1] - bounds[0]

        # Check for very thin dimensions
        for i, dim in enumerate(dimensions):
            if dim < 0.8 and dim > 0:  # Less than 0.8mm
                axis = ['X', 'Y', 'Z'][i]
                severity = IssueSeverity.CRITICAL if dim < 0.4 else IssueSeverity.WARNING
                thin_walls.append(ThinWallInfo(
                    thickness_mm=dim,
                    height_mm=max(dimensions),
                    location=tuple((bounds[0] + bounds[1]) / 2),
                    severity=severity,
                ))

    except Exception as e:
        logger.warning(f"Thin wall analysis error: {e}")

    return thin_walls


def _analyze_bridges(mesh) -> List[BridgeInfo]:
    """Analyze mesh for bridges (unsupported spans)."""
    bridges = []

    # Bridge detection requires more sophisticated analysis
    # For now, return empty list - would need layer-by-layer analysis
    # to properly detect bridges

    return bridges


def _check_manifold(mesh) -> List[GeometryIssue]:
    """Check if mesh is watertight/manifold."""
    issues = []

    if mesh is None:
        return issues

    try:
        if not mesh.is_watertight:
            issues.append(GeometryIssue(
                issue_type="non_manifold",
                severity=IssueSeverity.WARNING,
                message="Mesh is not watertight (has holes or non-manifold edges)",
                suggestion="Use mesh repair tools in Blender or Meshmixer",
            ))

        if hasattr(mesh, 'is_volume') and not mesh.is_volume:
            issues.append(GeometryIssue(
                issue_type="no_volume",
                severity=IssueSeverity.CRITICAL,
                message="Mesh does not enclose a volume",
                suggestion="Ensure all faces are properly connected",
            ))

    except Exception as e:
        logger.warning(f"Manifold check error: {e}")

    return issues


def analyze_geometry(file_path: str) -> GeometryAnalysisResult:
    """
    Analyze a 3D model file for geometry issues.

    Args:
        file_path: Path to STL, OBJ, or other mesh file

    Returns:
        GeometryAnalysisResult with all detected issues
    """
    path = Path(file_path)

    if not path.exists():
        return GeometryAnalysisResult(
            other_issues=[GeometryIssue(
                issue_type="file_not_found",
                severity=IssueSeverity.CRITICAL,
                message=f"File not found: {file_path}",
            )]
        )

    mesh = _load_mesh(path)

    result = GeometryAnalysisResult()

    if mesh is not None:
        # Get basic mesh info
        try:
            bounds = mesh.bounds
            result.bounding_box = tuple(bounds[1] - bounds[0])
            result.volume_mm3 = abs(mesh.volume) if hasattr(mesh, 'volume') else 0
            result.surface_area_mm2 = mesh.area if hasattr(mesh, 'area') else 0
            result.triangle_count = len(mesh.faces) if hasattr(mesh, 'faces') else 0
        except Exception as e:
            logger.warning(f"Failed to get mesh info: {e}")

        # Run analyses
        result.overhangs = _analyze_overhangs(mesh)
        result.thin_walls = _analyze_thin_walls(mesh)
        result.bridges = _analyze_bridges(mesh)
        result.other_issues = _check_manifold(mesh)

    else:
        result.other_issues.append(GeometryIssue(
            issue_type="load_failed",
            severity=IssueSeverity.WARNING,
            message="Could not load mesh for detailed analysis",
            suggestion="Install trimesh: pip install trimesh",
        ))

    logger.info(f"Geometry analysis complete: {result.total_issues} issues found")
    return result
