"""Support structure generation for 3D printing.

Generates optimized support structures for overhanging geometry,
including tree supports for better material efficiency.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from src.utils import get_logger
from src.blender.overhang_detector import OverhangDetector, OverhangAnalysis, OverhangInfo

logger = get_logger("blender.support")


class SupportType(str, Enum):
    """Types of support structures."""
    NORMAL = "normal"      # Traditional column supports
    TREE = "tree"          # Tree-like branching supports
    LINEAR = "linear"      # Linear/grid supports
    ORGANIC = "organic"    # Curved organic supports
    CUSTOM = "custom"      # Custom support regions


class SupportDensity(str, Enum):
    """Support density presets."""
    SPARSE = "sparse"      # ~10% - fast removal, less material
    NORMAL = "normal"      # ~15% - balanced
    DENSE = "dense"        # ~20% - stronger support
    SOLID = "solid"        # ~30% - for critical overhangs


class SupportPattern(str, Enum):
    """Support infill patterns."""
    LINES = "lines"
    GRID = "grid"
    ZIGZAG = "zigzag"
    TRIANGLES = "triangles"
    GYROID = "gyroid"


@dataclass
class SupportSettings:
    """Settings for support generation."""

    support_type: SupportType = SupportType.TREE
    density: SupportDensity = SupportDensity.NORMAL
    pattern: SupportPattern = SupportPattern.ZIGZAG

    # Angle threshold
    overhang_angle: float = 45.0  # degrees

    # Geometry settings
    z_distance: float = 0.2       # Distance from model (mm)
    xy_distance: float = 0.7      # Horizontal distance from model (mm)
    tower_diameter: float = 3.0   # Diameter of support pillars (mm)

    # Tree support specific
    tree_branch_angle: float = 45.0   # Max branch angle
    tree_branch_diameter: float = 2.0  # Branch diameter (mm)
    tree_trunk_diameter: float = 4.0   # Trunk diameter (mm)

    # Interface settings
    interface_layers: int = 3     # Layers between support and model
    interface_density: float = 0.8  # 80% density for interface

    # Material savings
    optimize_material: bool = True
    max_material_reduction: float = 0.4  # Target 40% reduction

    @property
    def density_percent(self) -> float:
        """Get density as percentage."""
        return {
            SupportDensity.SPARSE: 0.10,
            SupportDensity.NORMAL: 0.15,
            SupportDensity.DENSE: 0.20,
            SupportDensity.SOLID: 0.30,
        }.get(self.density, 0.15)


@dataclass
class SupportPoint:
    """A point requiring support."""

    position: Tuple[float, float, float]  # x, y, z
    overhang_angle: float
    area: float  # mm²
    needs_reinforcement: bool = False


@dataclass
class SupportStructure:
    """A generated support structure."""

    structure_id: str
    support_type: SupportType
    points: List[SupportPoint]

    # Geometry
    base_position: Tuple[float, float, float]
    height: float
    volume: float  # mm³

    # Tree-specific
    branches: List[Dict] = field(default_factory=list)
    trunk_positions: List[Tuple[float, float, float]] = field(default_factory=list)

    # Stats
    estimated_material_grams: float = 0.0
    material_savings_percent: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.structure_id,
            "type": self.support_type.value,
            "base": self.base_position,
            "height": self.height,
            "volume": self.volume,
            "material_grams": self.estimated_material_grams,
            "savings_percent": self.material_savings_percent,
        }


@dataclass
class SupportResult:
    """Result of support generation."""

    file_path: str
    settings: SupportSettings
    structures: List[SupportStructure] = field(default_factory=list)

    # Overall stats
    total_support_volume: float = 0.0  # mm³
    total_material_grams: float = 0.0
    material_savings_percent: float = 0.0

    # Comparison
    normal_support_volume: float = 0.0
    tree_support_volume: float = 0.0

    @property
    def support_count(self) -> int:
        """Number of support structures."""
        return len(self.structures)


class SupportGenerator:
    """
    Generates optimized support structures.

    Features:
    - Tree support generation
    - Material optimization
    - Customizable density and patterns
    """

    PLA_DENSITY = 1.24  # g/cm³

    def __init__(self, settings: Optional[SupportSettings] = None):
        """
        Initialize generator.

        Args:
            settings: Support settings (defaults used if not provided)
        """
        self.settings = settings or SupportSettings()
        self.overhang_detector = OverhangDetector(
            support_threshold=self.settings.overhang_angle
        )

    def generate(self, file_path: str) -> SupportResult:
        """
        Generate supports for a model.

        Args:
            file_path: Path to the STL file

        Returns:
            SupportResult with generated structures
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Analyze overhangs
        analysis = self.overhang_detector.analyze(file_path)

        # Generate support structures
        if self.settings.support_type == SupportType.TREE:
            structures = self._generate_tree_supports(analysis)
        else:
            structures = self._generate_normal_supports(analysis)

        # Calculate totals
        total_volume = sum(s.volume for s in structures)
        total_grams = self._volume_to_grams(total_volume)

        # Calculate comparison (normal vs tree)
        normal_volume = self._estimate_normal_support_volume(analysis)
        tree_volume = total_volume if self.settings.support_type == SupportType.TREE else self._estimate_tree_support_volume(analysis)

        savings = 0.0
        if normal_volume > 0:
            savings = (1 - total_volume / normal_volume) * 100

        result = SupportResult(
            file_path=str(path),
            settings=self.settings,
            structures=structures,
            total_support_volume=total_volume,
            total_material_grams=total_grams,
            material_savings_percent=max(0, savings),
            normal_support_volume=normal_volume,
            tree_support_volume=tree_volume,
        )

        logger.info(f"Generated {len(structures)} support structures, {total_grams:.1f}g material")
        return result

    def _generate_tree_supports(self, analysis: OverhangAnalysis) -> List[SupportStructure]:
        """Generate tree-style supports."""
        structures = []

        for overhang in analysis.overhangs:
            if not overhang.needs_support:
                continue

            # Create tree structure
            structure = self._create_tree_structure(overhang)
            if structure:
                structures.append(structure)

        return structures

    def _create_tree_structure(self, overhang: OverhangInfo) -> Optional[SupportStructure]:
        """Create a single tree support structure."""
        if overhang.area < 1.0:  # Skip tiny areas
            return None

        # Calculate trunk position (below overhang centroid)
        trunk_x = overhang.location[0]
        trunk_y = overhang.location[1]
        trunk_z_start = 0  # From bed

        # Create branches to reach overhang points
        branches = self._generate_branches(
            trunk_pos=(trunk_x, trunk_y, trunk_z_start),
            target_z=overhang.z_height,
            spread_radius=math.sqrt(overhang.area / math.pi),
        )

        # Calculate volume
        trunk_height = overhang.z_height
        trunk_volume = math.pi * (self.settings.tree_trunk_diameter / 2) ** 2 * trunk_height

        branch_volume = 0.0
        for branch in branches:
            branch_volume += math.pi * (self.settings.tree_branch_diameter / 2) ** 2 * branch.get("length", 5.0)

        total_volume = trunk_volume + branch_volume

        # Calculate material
        material_grams = self._volume_to_grams(total_volume)

        # Estimate savings vs normal support
        normal_volume = overhang.area * overhang.z_height * self.settings.density_percent
        savings = (1 - total_volume / normal_volume) * 100 if normal_volume > 0 else 0

        return SupportStructure(
            structure_id=str(uuid4())[:8],
            support_type=SupportType.TREE,
            points=[SupportPoint(
                position=overhang.location,
                overhang_angle=overhang.angle,
                area=overhang.area,
            )],
            base_position=(trunk_x, trunk_y, 0),
            height=overhang.z_height,
            volume=total_volume,
            branches=branches,
            trunk_positions=[(trunk_x, trunk_y, z) for z in range(0, int(trunk_height), 5)],
            estimated_material_grams=material_grams,
            material_savings_percent=max(0, savings),
        )

    def _generate_branches(
        self,
        trunk_pos: Tuple[float, float, float],
        target_z: float,
        spread_radius: float,
    ) -> List[Dict]:
        """Generate branches from trunk to support points."""
        branches = []

        # Calculate branch points around the overhang
        num_branches = max(3, int(spread_radius / 2))

        for i in range(num_branches):
            angle = (2 * math.pi * i) / num_branches
            branch_end_x = trunk_pos[0] + spread_radius * math.cos(angle)
            branch_end_y = trunk_pos[1] + spread_radius * math.sin(angle)

            # Branch starts partway up the trunk
            branch_start_z = target_z * 0.7

            # Branch length
            dx = branch_end_x - trunk_pos[0]
            dy = branch_end_y - trunk_pos[1]
            dz = target_z - branch_start_z
            length = math.sqrt(dx*dx + dy*dy + dz*dz)

            branches.append({
                "start": (trunk_pos[0], trunk_pos[1], branch_start_z),
                "end": (branch_end_x, branch_end_y, target_z),
                "length": length,
                "angle": math.degrees(math.atan2(math.sqrt(dx*dx + dy*dy), dz)),
            })

        return branches

    def _generate_normal_supports(self, analysis: OverhangAnalysis) -> List[SupportStructure]:
        """Generate traditional column supports."""
        structures = []

        for overhang in analysis.overhangs:
            if not overhang.needs_support:
                continue

            # Create simple column structure
            volume = overhang.area * overhang.z_height * self.settings.density_percent
            material_grams = self._volume_to_grams(volume)

            structure = SupportStructure(
                structure_id=str(uuid4())[:8],
                support_type=SupportType.NORMAL,
                points=[SupportPoint(
                    position=overhang.location,
                    overhang_angle=overhang.angle,
                    area=overhang.area,
                )],
                base_position=(overhang.location[0], overhang.location[1], 0),
                height=overhang.z_height,
                volume=volume,
                estimated_material_grams=material_grams,
                material_savings_percent=0,
            )
            structures.append(structure)

        return structures

    def _estimate_normal_support_volume(self, analysis: OverhangAnalysis) -> float:
        """Estimate volume if using normal supports."""
        total = 0.0
        for overhang in analysis.overhangs:
            if overhang.needs_support:
                # Normal support: full column under overhang
                total += overhang.area * overhang.z_height * self.settings.density_percent
        return total

    def _estimate_tree_support_volume(self, analysis: OverhangAnalysis) -> float:
        """Estimate volume if using tree supports."""
        total = 0.0
        for overhang in analysis.overhangs:
            if overhang.needs_support:
                # Tree support: trunk + branches (roughly 60% of normal)
                normal_vol = overhang.area * overhang.z_height * self.settings.density_percent
                total += normal_vol * 0.6
        return total

    def _volume_to_grams(self, volume_mm3: float) -> float:
        """Convert volume in mm³ to grams."""
        volume_cm3 = volume_mm3 / 1000  # mm³ to cm³
        return volume_cm3 * self.PLA_DENSITY

    def compare_support_types(self, file_path: str) -> Dict:
        """
        Compare different support types for a model.

        Args:
            file_path: Path to STL file

        Returns:
            Comparison data for each support type
        """
        analysis = self.overhang_detector.analyze(file_path)

        normal_vol = self._estimate_normal_support_volume(analysis)
        tree_vol = self._estimate_tree_support_volume(analysis)

        return {
            "file": file_path,
            "overhangs": len(analysis.overhangs),
            "needs_supports": analysis.needs_supports,
            "comparison": {
                "normal": {
                    "volume_mm3": normal_vol,
                    "material_grams": self._volume_to_grams(normal_vol),
                    "relative": 1.0,
                },
                "tree": {
                    "volume_mm3": tree_vol,
                    "material_grams": self._volume_to_grams(tree_vol),
                    "relative": tree_vol / normal_vol if normal_vol > 0 else 0,
                    "savings_percent": (1 - tree_vol / normal_vol) * 100 if normal_vol > 0 else 0,
                },
            },
            "recommendation": "tree" if tree_vol < normal_vol else "normal",
        }
