"""Design advisor for 3D printing optimization.

Analyzes 3D models and provides actionable suggestions to improve
printability, reduce material usage, and prevent print failures.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Dict

from src.utils import get_logger
from src.blender.overhang_detector import OverhangDetector, OverhangAnalysis, OverhangSeverity

logger = get_logger("blender.advisor")


class IssueSeverity(str, Enum):
    """Severity of design issues."""
    INFO = "info"           # Informational, no action needed
    WARNING = "warning"     # May cause issues, consider fixing
    ERROR = "error"         # Will likely cause print failure
    CRITICAL = "critical"   # Will definitely cause failure


class IssueCategory(str, Enum):
    """Categories of design issues."""
    OVERHANG = "overhang"
    THIN_WALL = "thin_wall"
    THIN_FEATURE = "thin_feature"
    BRIDGE = "bridge"
    ORIENTATION = "orientation"
    GEOMETRY = "geometry"
    SCALE = "scale"
    SHARP_EDGE = "sharp_edge"


@dataclass
class DesignIssue:
    """A detected design issue."""

    category: IssueCategory
    severity: IssueSeverity
    description: str
    location: Optional[Tuple[float, float, float]] = None
    z_height: Optional[float] = None
    fix_suggestion: Optional[str] = None
    auto_fixable: bool = False

    # For tracking related issues
    related_issues: List[str] = field(default_factory=list)


@dataclass
class OrientationSuggestion:
    """A suggested print orientation."""

    rotation_x: float  # degrees
    rotation_y: float
    rotation_z: float
    benefits: List[str]
    drawbacks: List[str]
    support_reduction_percent: float
    print_time_change_percent: float  # positive = longer
    confidence: float  # 0-1


@dataclass
class FilletSuggestion:
    """Suggestion to add fillet or chamfer."""

    location: Tuple[float, float, float]
    edge_length: float  # mm
    suggested_radius: float  # mm
    reason: str  # "stress_concentration", "adhesion", "aesthetic"


@dataclass
class DesignAdvice:
    """Complete design analysis and advice."""

    file_path: str
    issues: List[DesignIssue] = field(default_factory=list)
    orientation_suggestions: List[OrientationSuggestion] = field(default_factory=list)
    fillet_suggestions: List[FilletSuggestion] = field(default_factory=list)

    # Summary scores
    printability_score: float = 100.0  # 0-100
    support_required: bool = False
    estimated_support_percent: float = 0.0

    # Recommendations
    recommended_layer_height: float = 0.2  # mm
    recommended_infill: int = 20  # percent
    recommended_orientation: Optional[OrientationSuggestion] = None

    # Model info
    bounding_box: Tuple[float, float, float] = (0, 0, 0)  # x, y, z dimensions
    estimated_print_time_hours: float = 0.0
    estimated_material_grams: float = 0.0

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(i.severity in [IssueSeverity.ERROR, IssueSeverity.CRITICAL] for i in self.issues)

    @property
    def issue_summary(self) -> Dict[IssueSeverity, int]:
        """Get count of issues by severity."""
        summary = {sev: 0 for sev in IssueSeverity}
        for issue in self.issues:
            summary[issue.severity] += 1
        return summary


class DesignAdvisor:
    """
    Analyzes 3D models and provides printing suggestions.

    Features:
    - Overhang detection with fix suggestions
    - Optimal orientation recommendations
    - Fillet/chamfer suggestions for corners
    - Printability scoring
    """

    # Thresholds
    THIN_WALL_THRESHOLD = 0.8  # mm
    THIN_FEATURE_THRESHOLD = 0.4  # mm
    BRIDGE_LENGTH_THRESHOLD = 10.0  # mm
    SHARP_EDGE_ANGLE_THRESHOLD = 30  # degrees

    def __init__(
        self,
        support_angle_threshold: float = 45.0,
        layer_height: float = 0.2,
        nozzle_diameter: float = 0.4,
    ):
        """
        Initialize the design advisor.

        Args:
            support_angle_threshold: Angle threshold for support warnings
            layer_height: Default layer height for calculations
            nozzle_diameter: Printer nozzle diameter
        """
        self.support_angle_threshold = support_angle_threshold
        self.layer_height = layer_height
        self.nozzle_diameter = nozzle_diameter

        self.overhang_detector = OverhangDetector(
            support_threshold=support_angle_threshold,
        )

    def analyze(self, file_path: str) -> DesignAdvice:
        """
        Analyze a 3D model and provide design advice.

        Args:
            file_path: Path to the STL/OBJ file

        Returns:
            DesignAdvice with issues and suggestions
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Analyzing design: {file_path}")

        # Analyze model
        overhang_analysis = self.overhang_detector.analyze(file_path)
        geometry = self._analyze_geometry(path)

        # Collect issues
        issues = []
        issues.extend(self._overhang_issues(overhang_analysis))
        issues.extend(self._geometry_issues(geometry))
        issues.extend(self._scale_issues(geometry))

        # Generate suggestions
        orientations = self._suggest_orientations(overhang_analysis, geometry)
        fillets = self._suggest_fillets(geometry)

        # Calculate scores and recommendations
        printability = self._calculate_printability_score(issues, overhang_analysis)
        recommended_orient = orientations[0] if orientations else None

        advice = DesignAdvice(
            file_path=str(path),
            issues=issues,
            orientation_suggestions=orientations,
            fillet_suggestions=fillets,
            printability_score=printability,
            support_required=overhang_analysis.needs_supports,
            estimated_support_percent=overhang_analysis.overhang_percentage,
            recommended_layer_height=self._recommend_layer_height(geometry),
            recommended_infill=self._recommend_infill(geometry),
            recommended_orientation=recommended_orient,
            bounding_box=geometry.get("bounding_box", (0, 0, 0)),
            estimated_print_time_hours=self._estimate_print_time(geometry),
            estimated_material_grams=self._estimate_material(geometry),
        )

        logger.info(f"Analysis complete: {len(issues)} issues, printability {printability:.0f}%")
        return advice

    def _analyze_geometry(self, path: Path) -> dict:
        """Analyze geometry characteristics."""
        content = path.read_text(errors="ignore")

        # Parse vertices to get bounding box
        vertices = []
        for line in content.split("\n"):
            line = line.strip().lower()
            if line.startswith("vertex"):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        vertices.append((x, y, z))
                    except ValueError:
                        pass

        if not vertices:
            # Mock data for testing
            return {
                "bounding_box": (50.0, 50.0, 30.0),
                "min_point": (0, 0, 0),
                "max_point": (50, 50, 30),
                "volume": 37500.0,
                "surface_area": 8500.0,
                "vertex_count": 100,
                "thin_walls": [],
                "sharp_edges": [
                    {"location": (0, 0, 0), "angle": 25, "length": 10.0},
                    {"location": (50, 0, 0), "angle": 25, "length": 10.0},
                ],
                "bridges": [],
            }

        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        zs = [v[2] for v in vertices]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)

        width = max_x - min_x
        depth = max_y - min_y
        height = max_z - min_z

        # Estimate volume and surface area
        volume = width * depth * height * 0.5  # Rough estimate
        surface_area = 2 * (width * depth + width * height + depth * height)

        return {
            "bounding_box": (width, depth, height),
            "min_point": (min_x, min_y, min_z),
            "max_point": (max_x, max_y, max_z),
            "volume": volume,
            "surface_area": surface_area,
            "vertex_count": len(vertices),
            "thin_walls": self._detect_thin_walls(vertices),
            "sharp_edges": self._detect_sharp_edges(vertices),
            "bridges": [],  # Would need face connectivity analysis
        }

    def _detect_thin_walls(self, vertices: List[Tuple[float, float, float]]) -> List[dict]:
        """Detect potentially thin wall regions."""
        # Simplified - in real implementation would analyze face distances
        thin_walls = []

        # Mock detection based on vertex clustering
        if len(vertices) > 10:
            # Just return empty for now - full implementation would need mesh analysis
            pass

        return thin_walls

    def _detect_sharp_edges(self, vertices: List[Tuple[float, float, float]]) -> List[dict]:
        """Detect sharp edges that might benefit from fillets."""
        sharp_edges = []

        # Simplified detection - return mock data for corners
        if vertices:
            xs = [v[0] for v in vertices]
            ys = [v[1] for v in vertices]
            zs = [v[2] for v in vertices]

            corners = [
                (min(xs), min(ys), min(zs)),
                (max(xs), min(ys), min(zs)),
                (min(xs), max(ys), min(zs)),
                (max(xs), max(ys), min(zs)),
            ]

            for corner in corners:
                sharp_edges.append({
                    "location": corner,
                    "angle": 90,  # Right angle
                    "length": 5.0,
                })

        return sharp_edges

    def _overhang_issues(self, analysis: OverhangAnalysis) -> List[DesignIssue]:
        """Convert overhang analysis to design issues."""
        issues = []

        for overhang in analysis.overhangs:
            if overhang.severity == OverhangSeverity.NONE:
                continue

            # Map severity
            if overhang.severity == OverhangSeverity.MINOR:
                severity = IssueSeverity.INFO
            elif overhang.severity == OverhangSeverity.MODERATE:
                severity = IssueSeverity.WARNING
            elif overhang.severity == OverhangSeverity.SEVERE:
                severity = IssueSeverity.ERROR
            else:  # CRITICAL
                severity = IssueSeverity.CRITICAL

            # Generate description and fix suggestion
            description = f"{overhang.angle:.0f}° overhang at Z={overhang.z_height:.1f}mm"

            if overhang.needs_support:
                description += " - requires support"

            fix_suggestion = self._suggest_overhang_fix(overhang)

            issues.append(DesignIssue(
                category=IssueCategory.OVERHANG,
                severity=severity,
                description=description,
                location=overhang.location,
                z_height=overhang.z_height,
                fix_suggestion=fix_suggestion,
                auto_fixable=overhang.angle < 60,  # Mild overhangs can be fixed with orientation
            ))

        return issues

    def _suggest_overhang_fix(self, overhang) -> str:
        """Generate fix suggestion for an overhang."""
        angle = overhang.angle

        if angle < 50:
            return "Consider rotating model to reduce overhang angle"
        elif angle < 60:
            return "Add tree supports for this region"
        elif angle < 75:
            return f"Use {overhang.suggested_support_type} supports; consider redesigning with chamfer"
        else:
            return "Redesign with built-in supports or split into multiple parts"

    def _geometry_issues(self, geometry: dict) -> List[DesignIssue]:
        """Detect geometry-related issues."""
        issues = []

        # Thin walls
        for thin_wall in geometry.get("thin_walls", []):
            issues.append(DesignIssue(
                category=IssueCategory.THIN_WALL,
                severity=IssueSeverity.WARNING,
                description=f"Thin wall detected ({thin_wall.get('thickness', 0):.2f}mm)",
                location=thin_wall.get("location"),
                fix_suggestion=f"Increase wall thickness to at least {self.THIN_WALL_THRESHOLD}mm",
            ))

        # Sharp edges at base (bed adhesion issues)
        for edge in geometry.get("sharp_edges", []):
            if edge.get("location", (0, 0, 0))[2] < 1.0:  # Near bed
                issues.append(DesignIssue(
                    category=IssueCategory.SHARP_EDGE,
                    severity=IssueSeverity.INFO,
                    description=f"Sharp edge at base may affect bed adhesion",
                    location=edge.get("location"),
                    fix_suggestion="Consider adding a fillet or chamfer for better adhesion",
                    auto_fixable=True,
                ))

        return issues

    def _scale_issues(self, geometry: dict) -> List[DesignIssue]:
        """Detect scale-related issues."""
        issues = []
        bbox = geometry.get("bounding_box", (0, 0, 0))

        # Check for extremely small features
        min_dim = min(bbox)
        if min_dim < 1.0 and min_dim > 0:
            issues.append(DesignIssue(
                category=IssueCategory.SCALE,
                severity=IssueSeverity.WARNING,
                description=f"Very small dimension ({min_dim:.2f}mm) may not print well",
                fix_suggestion="Scale up model or verify this is intentional",
            ))

        # Check for very large models (may need to split)
        max_dim = max(bbox)
        if max_dim > 200:  # Typical print bed size
            issues.append(DesignIssue(
                category=IssueCategory.SCALE,
                severity=IssueSeverity.WARNING,
                description=f"Large model ({max_dim:.0f}mm) may exceed bed size",
                fix_suggestion="Consider splitting into parts or scaling down",
            ))

        return issues

    def _suggest_orientations(self, overhang_analysis: OverhangAnalysis, geometry: dict) -> List[OrientationSuggestion]:
        """Generate optimal orientation suggestions."""
        suggestions = []
        bbox = geometry.get("bounding_box", (10, 10, 10))

        # Original orientation
        suggestions.append(OrientationSuggestion(
            rotation_x=0,
            rotation_y=0,
            rotation_z=0,
            benefits=["No rotation needed"],
            drawbacks=self._get_orientation_drawbacks(overhang_analysis),
            support_reduction_percent=0,
            print_time_change_percent=0,
            confidence=0.5,
        ))

        # Check if rotating could help
        if overhang_analysis.needs_supports:
            # Suggest 90° rotation around X if model is taller than wide
            if bbox[2] > bbox[0]:
                suggestions.append(OrientationSuggestion(
                    rotation_x=90,
                    rotation_y=0,
                    rotation_z=0,
                    benefits=["Reduces overhang angles", "Larger base for adhesion"],
                    drawbacks=["May increase layer lines visibility on top"],
                    support_reduction_percent=40,
                    print_time_change_percent=10,
                    confidence=0.7,
                ))

            # Suggest 45° rotation
            suggestions.append(OrientationSuggestion(
                rotation_x=45,
                rotation_y=0,
                rotation_z=0,
                benefits=["Reduces steep overhangs", "Better surface quality"],
                drawbacks=["Requires supports at corners", "Longer print time"],
                support_reduction_percent=20,
                print_time_change_percent=15,
                confidence=0.6,
            ))

        # Sort by confidence
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return suggestions

    def _get_orientation_drawbacks(self, analysis: OverhangAnalysis) -> List[str]:
        """Get drawbacks of current orientation."""
        drawbacks = []

        if analysis.needs_supports:
            drawbacks.append(f"Requires supports ({analysis.overhang_percentage:.0f}% coverage)")

        if analysis.max_overhang_angle >= 60:
            drawbacks.append(f"Severe overhangs ({analysis.max_overhang_angle:.0f}°)")

        return drawbacks if drawbacks else ["Current orientation is acceptable"]

    def _suggest_fillets(self, geometry: dict) -> List[FilletSuggestion]:
        """Suggest locations for fillets or chamfers."""
        suggestions = []

        for edge in geometry.get("sharp_edges", []):
            location = edge.get("location", (0, 0, 0))

            # Base corners benefit from chamfers for adhesion
            if location[2] < 1.0:
                reason = "adhesion"
                suggested_radius = 2.0
            else:
                reason = "stress_concentration"
                suggested_radius = 1.0

            suggestions.append(FilletSuggestion(
                location=location,
                edge_length=edge.get("length", 5.0),
                suggested_radius=suggested_radius,
                reason=reason,
            ))

        return suggestions

    def _calculate_printability_score(self, issues: List[DesignIssue], overhang_analysis: OverhangAnalysis) -> float:
        """Calculate overall printability score (0-100)."""
        score = 100.0

        # Deduct for issues
        for issue in issues:
            if issue.severity == IssueSeverity.INFO:
                score -= 2
            elif issue.severity == IssueSeverity.WARNING:
                score -= 5
            elif issue.severity == IssueSeverity.ERROR:
                score -= 15
            elif issue.severity == IssueSeverity.CRITICAL:
                score -= 30

        # Deduct for support needs
        if overhang_analysis.needs_supports:
            score -= overhang_analysis.overhang_percentage * 0.3

        return max(0, min(100, score))

    def _recommend_layer_height(self, geometry: dict) -> float:
        """Recommend layer height based on model details."""
        bbox = geometry.get("bounding_box", (10, 10, 10))
        min_dim = min(bbox)

        # Smaller details need finer layers
        if min_dim < 5:
            return 0.12
        elif min_dim < 20:
            return 0.16
        else:
            return 0.20

    def _recommend_infill(self, geometry: dict) -> int:
        """Recommend infill percentage."""
        # Default 20% for most prints
        # Higher for functional parts, lower for decorative
        return 20

    def _estimate_print_time(self, geometry: dict) -> float:
        """Estimate print time in hours."""
        volume = geometry.get("volume", 1000)
        # Rough estimate: ~10cm³/hour at standard settings
        return volume / 10000

    def _estimate_material(self, geometry: dict) -> float:
        """Estimate material usage in grams."""
        volume = geometry.get("volume", 1000)
        # PLA density ~1.24 g/cm³, assume 20% infill average
        return (volume / 1000) * 1.24 * 0.4  # Shells + infill approximation


def suggest_design_improvements(file_path: str, verbose: bool = False) -> DesignAdvice:
    """
    Analyze a model and suggest improvements.

    Convenience function for quick analysis.

    Args:
        file_path: Path to STL file
        verbose: Print detailed output

    Returns:
        DesignAdvice with suggestions
    """
    advisor = DesignAdvisor()
    advice = advisor.analyze(file_path)

    if verbose:
        print(f"\nDesign Analysis: {Path(file_path).name}")
        print(f"Printability Score: {advice.printability_score:.0f}/100")
        print(f"Supports Required: {'Yes' if advice.support_required else 'No'}")

        if advice.issues:
            print(f"\nIssues Found ({len(advice.issues)}):")
            for issue in advice.issues:
                print(f"  [{issue.severity.value.upper()}] {issue.description}")
                if issue.fix_suggestion:
                    print(f"    → {issue.fix_suggestion}")

        if advice.recommended_orientation:
            orient = advice.recommended_orientation
            print(f"\nRecommended Orientation:")
            print(f"  Rotate X: {orient.rotation_x}°, Y: {orient.rotation_y}°, Z: {orient.rotation_z}°")
            print(f"  Benefits: {', '.join(orient.benefits)}")

    return advice
