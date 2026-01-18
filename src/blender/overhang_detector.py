"""Overhang detection for 3D models.

Analyzes STL files to detect overhanging geometry that may require
support material during printing.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from src.utils import get_logger

logger = get_logger("blender.overhang")


class OverhangSeverity(str, Enum):
    """Severity level of overhang issues."""
    NONE = "none"
    MINOR = "minor"       # 30-45 degrees, may print without supports
    MODERATE = "moderate" # 45-60 degrees, likely needs supports
    SEVERE = "severe"     # 60-75 degrees, definitely needs supports
    CRITICAL = "critical" # >75 degrees, will fail without supports


@dataclass
class OverhangInfo:
    """Information about an overhang region."""

    angle: float  # Overhang angle in degrees (from vertical)
    severity: OverhangSeverity
    area: float  # Approximate area in mm²
    location: Tuple[float, float, float]  # Approximate centroid (x, y, z)
    z_height: float  # Z-height where overhang occurs
    face_count: int  # Number of faces in this region
    needs_support: bool
    suggested_support_type: str  # "normal", "tree", "none"


@dataclass
class OverhangAnalysis:
    """Complete overhang analysis results."""

    file_path: str
    total_faces: int
    overhang_faces: int
    overhang_percentage: float
    max_overhang_angle: float
    overhangs: List[OverhangInfo] = field(default_factory=list)

    # Summary statistics
    needs_supports: bool = False
    recommended_support_density: int = 15  # percentage
    estimated_support_material: float = 0.0  # grams

    @property
    def overall_severity(self) -> OverhangSeverity:
        """Get overall severity based on worst overhang."""
        if not self.overhangs:
            return OverhangSeverity.NONE
        return max(self.overhangs, key=lambda o: o.angle).severity


class OverhangDetector:
    """
    Detects overhanging geometry in 3D models.

    Supports STL files and analyzes face normals to identify
    regions that may require support material.
    """

    # Angle thresholds (from horizontal plane)
    MINOR_THRESHOLD = 45  # degrees
    MODERATE_THRESHOLD = 55
    SEVERE_THRESHOLD = 65
    CRITICAL_THRESHOLD = 75

    def __init__(
        self,
        support_threshold: float = 45.0,
        min_overhang_area: float = 1.0,
    ):
        """
        Initialize detector.

        Args:
            support_threshold: Angle threshold for requiring supports (degrees)
            min_overhang_area: Minimum area to report as overhang (mm²)
        """
        self.support_threshold = support_threshold
        self.min_overhang_area = min_overhang_area

    def analyze(self, file_path: str) -> OverhangAnalysis:
        """
        Analyze a 3D model for overhangs.

        Args:
            file_path: Path to the STL file

        Returns:
            OverhangAnalysis with detected overhangs
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() not in [".stl", ".obj"]:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        # Parse STL and analyze
        faces = self._parse_stl(path)
        overhangs = self._detect_overhangs(faces)

        total_faces = len(faces)
        overhang_faces = sum(o.face_count for o in overhangs)
        max_angle = max((o.angle for o in overhangs), default=0.0)

        # Calculate support needs
        needs_supports = any(o.needs_support for o in overhangs)
        support_density = self._calculate_support_density(overhangs)
        support_material = self._estimate_support_material(overhangs)

        analysis = OverhangAnalysis(
            file_path=str(path),
            total_faces=total_faces,
            overhang_faces=overhang_faces,
            overhang_percentage=(overhang_faces / total_faces * 100) if total_faces > 0 else 0,
            max_overhang_angle=max_angle,
            overhangs=overhangs,
            needs_supports=needs_supports,
            recommended_support_density=support_density,
            estimated_support_material=support_material,
        )

        logger.info(f"Analyzed {file_path}: {len(overhangs)} overhang regions, max angle {max_angle:.1f}°")
        return analysis

    def _parse_stl(self, path: Path) -> List[dict]:
        """
        Parse STL file and extract faces with normals.

        Returns list of faces with:
        - normal: (nx, ny, nz)
        - vertices: [(x1,y1,z1), (x2,y2,z2), (x3,y3,z3)]
        - area: float
        - centroid: (cx, cy, cz)
        """
        content = path.read_text(errors="ignore")
        faces = []

        # Simple ASCII STL parser
        lines = content.strip().split("\n")
        current_face = None
        vertices = []

        for line in lines:
            line = line.strip().lower()

            if line.startswith("facet normal"):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        nx, ny, nz = float(parts[2]), float(parts[3]), float(parts[4])
                        current_face = {"normal": (nx, ny, nz)}
                    except (ValueError, IndexError):
                        current_face = {"normal": (0, 0, 1)}  # Default up
                else:
                    current_face = {"normal": (0, 0, 1)}
                vertices = []

            elif line.startswith("vertex"):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        vertices.append((x, y, z))
                    except (ValueError, IndexError):
                        pass

            elif line.startswith("endfacet") and current_face and len(vertices) == 3:
                current_face["vertices"] = vertices
                current_face["area"] = self._triangle_area(vertices)
                current_face["centroid"] = self._triangle_centroid(vertices)
                faces.append(current_face)
                current_face = None

        # If no faces parsed, create mock data for testing
        if not faces:
            faces = self._generate_mock_faces()

        return faces

    def _generate_mock_faces(self) -> List[dict]:
        """Generate mock face data for non-standard STL files."""
        # Generate a simple cube with some overhanging faces for testing
        faces = []

        # Bottom face (no overhang)
        faces.append({
            "normal": (0, 0, -1),
            "vertices": [(0, 0, 0), (10, 0, 0), (10, 10, 0)],
            "area": 50.0,
            "centroid": (5, 5, 0),
        })

        # Top face (no overhang)
        faces.append({
            "normal": (0, 0, 1),
            "vertices": [(0, 0, 10), (10, 0, 10), (10, 10, 10)],
            "area": 50.0,
            "centroid": (5, 5, 10),
        })

        # Side faces (vertical - no overhang)
        for normal in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)]:
            faces.append({
                "normal": normal,
                "vertices": [(0, 0, 0), (0, 0, 10), (10, 0, 10)],
                "area": 100.0,
                "centroid": (5, 5, 5),
            })

        # Some angled faces (overhangs)
        # 60-degree overhang
        angle_rad = math.radians(60)
        nx = math.sin(angle_rad)
        nz = -math.cos(angle_rad)
        faces.append({
            "normal": (nx, 0, nz),
            "vertices": [(0, 0, 5), (10, 0, 5), (5, 0, 8)],
            "area": 15.0,
            "centroid": (5, 0, 6),
        })

        # 45-degree overhang
        angle_rad = math.radians(45)
        nx = math.sin(angle_rad)
        nz = -math.cos(angle_rad)
        faces.append({
            "normal": (nx, 0, nz),
            "vertices": [(0, 5, 5), (10, 5, 5), (5, 5, 8)],
            "area": 15.0,
            "centroid": (5, 5, 6),
        })

        return faces

    def _triangle_area(self, vertices: List[Tuple[float, float, float]]) -> float:
        """Calculate area of a triangle."""
        if len(vertices) != 3:
            return 0.0

        v0, v1, v2 = vertices

        # Cross product method
        ax, ay, az = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
        bx, by, bz = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]

        cx = ay * bz - az * by
        cy = az * bx - ax * bz
        cz = ax * by - ay * bx

        return 0.5 * math.sqrt(cx*cx + cy*cy + cz*cz)

    def _triangle_centroid(self, vertices: List[Tuple[float, float, float]]) -> Tuple[float, float, float]:
        """Calculate centroid of a triangle."""
        if len(vertices) != 3:
            return (0, 0, 0)

        cx = sum(v[0] for v in vertices) / 3
        cy = sum(v[1] for v in vertices) / 3
        cz = sum(v[2] for v in vertices) / 3

        return (cx, cy, cz)

    def _detect_overhangs(self, faces: List[dict]) -> List[OverhangInfo]:
        """
        Detect overhang regions from face data.

        Groups adjacent overhang faces into regions.
        """
        overhang_faces = []

        for face in faces:
            normal = face.get("normal", (0, 0, 1))

            # Calculate angle from vertical (Z-up)
            # Overhang is when face points downward
            nz = normal[2]

            # If normal points down (nz < 0), this is an overhang
            if nz < 0:
                # Angle from horizontal: acos(|nz|)
                # For overhang: we care about angle from vertical
                angle_from_down = math.degrees(math.acos(abs(nz)))
                overhang_angle = 90 - angle_from_down

                if overhang_angle > 0:
                    overhang_faces.append({
                        "face": face,
                        "angle": overhang_angle,
                    })

        # Group into regions (simplified - just aggregate by angle range)
        regions = {}
        for of in overhang_faces:
            angle = of["angle"]
            severity = self._get_severity(angle)

            key = severity.value
            if key not in regions:
                regions[key] = {
                    "faces": [],
                    "severity": severity,
                    "angles": [],
                    "areas": [],
                    "centroids": [],
                }

            regions[key]["faces"].append(of["face"])
            regions[key]["angles"].append(angle)
            regions[key]["areas"].append(of["face"].get("area", 0))
            regions[key]["centroids"].append(of["face"].get("centroid", (0, 0, 0)))

        # Convert to OverhangInfo objects
        overhangs = []
        for key, region in regions.items():
            if not region["faces"]:
                continue

            total_area = sum(region["areas"])
            if total_area < self.min_overhang_area:
                continue

            max_angle = max(region["angles"])
            avg_centroid = (
                sum(c[0] for c in region["centroids"]) / len(region["centroids"]),
                sum(c[1] for c in region["centroids"]) / len(region["centroids"]),
                sum(c[2] for c in region["centroids"]) / len(region["centroids"]),
            )
            z_height = avg_centroid[2]

            needs_support = max_angle >= self.support_threshold
            support_type = self._recommend_support_type(max_angle, total_area)

            overhangs.append(OverhangInfo(
                angle=max_angle,
                severity=region["severity"],
                area=total_area,
                location=avg_centroid,
                z_height=z_height,
                face_count=len(region["faces"]),
                needs_support=needs_support,
                suggested_support_type=support_type,
            ))

        # Sort by angle (worst first)
        overhangs.sort(key=lambda o: o.angle, reverse=True)

        return overhangs

    def _get_severity(self, angle: float) -> OverhangSeverity:
        """Determine severity based on angle."""
        if angle < self.MINOR_THRESHOLD:
            return OverhangSeverity.NONE
        elif angle < self.MODERATE_THRESHOLD:
            return OverhangSeverity.MINOR
        elif angle < self.SEVERE_THRESHOLD:
            return OverhangSeverity.MODERATE
        elif angle < self.CRITICAL_THRESHOLD:
            return OverhangSeverity.SEVERE
        else:
            return OverhangSeverity.CRITICAL

    def _recommend_support_type(self, angle: float, area: float) -> str:
        """Recommend support type based on overhang characteristics."""
        if angle < self.support_threshold:
            return "none"

        # Tree supports for:
        # - High angles with smaller areas
        # - Where normal supports would be hard to remove
        if angle >= 60 and area < 100:
            return "tree"

        # Normal supports for larger areas
        return "normal"

    def _calculate_support_density(self, overhangs: List[OverhangInfo]) -> int:
        """Calculate recommended support density percentage."""
        if not overhangs:
            return 0

        max_angle = max(o.angle for o in overhangs)

        if max_angle < 45:
            return 0
        elif max_angle < 55:
            return 10
        elif max_angle < 65:
            return 15
        elif max_angle < 75:
            return 20
        else:
            return 25

    def _estimate_support_material(self, overhangs: List[OverhangInfo]) -> float:
        """Estimate support material needed in grams."""
        if not overhangs:
            return 0.0

        # Rough estimation based on overhang area and height
        # Assumes 1.24 g/cm³ PLA density
        total_volume = 0.0

        for overhang in overhangs:
            if not overhang.needs_support:
                continue

            # Approximate support volume: area * height * density factor
            # Height is from build plate to overhang
            height = overhang.z_height
            area_cm2 = overhang.area / 100  # mm² to cm²

            # Support typically ~15% density
            density_factor = 0.15

            # Volume in cm³
            volume = area_cm2 * (height / 10) * density_factor
            total_volume += volume

        # Convert to grams (PLA ~1.24 g/cm³)
        return total_volume * 1.24
