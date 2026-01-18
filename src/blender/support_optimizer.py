"""Support structure optimization for 3D printing.

Optimizes generated support structures to minimize material usage
while maintaining print quality.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from src.utils import get_logger
from src.blender.support_generator import (
    SupportGenerator,
    SupportResult,
    SupportStructure,
    SupportSettings,
    SupportType,
    SupportDensity,
)

logger = get_logger("blender.support_optimizer")


class OptimizationGoal(str, Enum):
    """Optimization goals."""
    MATERIAL = "material"       # Minimize material usage
    STRENGTH = "strength"       # Maximize support strength
    REMOVAL = "removal"         # Easiest support removal
    BALANCED = "balanced"       # Balance all factors
    SPEED = "speed"            # Fastest print time


@dataclass
class OptimizationSettings:
    """Settings for support optimization."""

    goal: OptimizationGoal = OptimizationGoal.BALANCED

    # Material targets
    target_material_reduction: float = 0.4  # 40% reduction target

    # Constraints
    min_support_density: float = 0.08      # Minimum 8% density
    max_support_density: float = 0.30      # Maximum 30% density
    min_trunk_diameter: float = 1.5        # mm
    max_branch_angle: float = 60.0         # degrees

    # Optimization parameters
    merge_distance: float = 5.0            # Merge supports within this distance (mm)
    remove_redundant: bool = True          # Remove unnecessary supports
    reinforce_critical: bool = True        # Extra support for critical overhangs


@dataclass
class OptimizationResult:
    """Result of support optimization."""

    original: SupportResult
    optimized: SupportResult

    # Savings
    volume_reduction_mm3: float = 0.0
    material_reduction_grams: float = 0.0
    reduction_percent: float = 0.0

    # Changes made
    supports_merged: int = 0
    supports_removed: int = 0
    supports_reinforced: int = 0

    # Recommendations
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class SupportOptimizer:
    """
    Optimizes support structures for material efficiency.

    Techniques:
    - Merges nearby supports
    - Removes redundant supports
    - Adjusts density based on overhang severity
    - Converts to tree supports where beneficial
    """

    def __init__(self, settings: Optional[OptimizationSettings] = None):
        """
        Initialize optimizer.

        Args:
            settings: Optimization settings
        """
        self.settings = settings or OptimizationSettings()

    def optimize(
        self,
        support_result: SupportResult,
        goal: Optional[OptimizationGoal] = None,
    ) -> OptimizationResult:
        """
        Optimize a support result.

        Args:
            support_result: Original support result
            goal: Optimization goal (overrides settings)

        Returns:
            OptimizationResult with optimized supports
        """
        goal = goal or self.settings.goal
        logger.info(f"Optimizing supports with goal: {goal.value}")

        # Start with copy of original structures
        optimized_structures = list(support_result.structures)
        changes = {
            "merged": 0,
            "removed": 0,
            "reinforced": 0,
        }
        warnings = []
        recommendations = []

        # Apply optimization techniques based on goal
        if goal in [OptimizationGoal.MATERIAL, OptimizationGoal.BALANCED]:
            optimized_structures, merged = self._merge_nearby_supports(optimized_structures)
            changes["merged"] = merged

            if self.settings.remove_redundant:
                optimized_structures, removed = self._remove_redundant_supports(optimized_structures)
                changes["removed"] = removed

        if goal in [OptimizationGoal.STRENGTH, OptimizationGoal.BALANCED]:
            if self.settings.reinforce_critical:
                optimized_structures, reinforced = self._reinforce_critical_supports(optimized_structures)
                changes["reinforced"] = reinforced

        if goal == OptimizationGoal.REMOVAL:
            optimized_structures = self._optimize_for_removal(optimized_structures)
            recommendations.append("Use tree supports for easier removal")

        if goal == OptimizationGoal.SPEED:
            optimized_structures = self._optimize_for_speed(optimized_structures)
            recommendations.append("Using sparse supports for faster printing")

        # Calculate new totals
        optimized_volume = sum(s.volume for s in optimized_structures)
        optimized_grams = optimized_volume / 1000 * 1.24

        # Calculate reduction
        original_volume = support_result.total_support_volume
        volume_reduction = original_volume - optimized_volume
        grams_reduction = support_result.total_material_grams - optimized_grams
        reduction_percent = (volume_reduction / original_volume * 100) if original_volume > 0 else 0

        # Check if we met target
        if reduction_percent < self.settings.target_material_reduction * 100:
            recommendations.append(
                f"Material reduction {reduction_percent:.0f}% is below target {self.settings.target_material_reduction*100:.0f}%"
            )

        # Generate warnings for potential issues
        if len(optimized_structures) < len(support_result.structures) * 0.5:
            warnings.append("Significant support reduction - verify print stability")

        for struct in optimized_structures:
            if struct.height > 50 and struct.support_type == SupportType.TREE:
                warnings.append(f"Tall tree support ({struct.height:.0f}mm) may need reinforcement")

        # Create optimized result
        optimized_result = SupportResult(
            file_path=support_result.file_path,
            settings=support_result.settings,
            structures=optimized_structures,
            total_support_volume=optimized_volume,
            total_material_grams=optimized_grams,
            material_savings_percent=reduction_percent,
        )

        return OptimizationResult(
            original=support_result,
            optimized=optimized_result,
            volume_reduction_mm3=volume_reduction,
            material_reduction_grams=grams_reduction,
            reduction_percent=reduction_percent,
            supports_merged=changes["merged"],
            supports_removed=changes["removed"],
            supports_reinforced=changes["reinforced"],
            warnings=warnings,
            recommendations=recommendations,
        )

    def _merge_nearby_supports(
        self,
        structures: List[SupportStructure],
    ) -> Tuple[List[SupportStructure], int]:
        """Merge supports that are close together."""
        if len(structures) < 2:
            return structures, 0

        merged_count = 0
        result = []
        used = set()

        for i, struct_a in enumerate(structures):
            if i in used:
                continue

            # Find nearby structures to merge
            to_merge = [struct_a]
            for j, struct_b in enumerate(structures[i+1:], i+1):
                if j in used:
                    continue

                distance = self._distance(struct_a.base_position, struct_b.base_position)
                if distance < self.settings.merge_distance:
                    to_merge.append(struct_b)
                    used.add(j)
                    merged_count += 1

            # Create merged structure
            if len(to_merge) > 1:
                merged = self._create_merged_structure(to_merge)
                result.append(merged)
            else:
                result.append(struct_a)

        return result, merged_count

    def _create_merged_structure(
        self,
        structures: List[SupportStructure],
    ) -> SupportStructure:
        """Create a single structure from multiple merged structures."""
        # Calculate centroid
        cx = sum(s.base_position[0] for s in structures) / len(structures)
        cy = sum(s.base_position[1] for s in structures) / len(structures)

        # Max height
        max_height = max(s.height for s in structures)

        # Combine points
        all_points = []
        for s in structures:
            all_points.extend(s.points)

        # Total volume (reduced due to merging)
        total_volume = sum(s.volume for s in structures) * 0.8  # 20% reduction from merging

        # Use tree support type for merged structures
        return SupportStructure(
            structure_id=structures[0].structure_id,
            support_type=SupportType.TREE,
            points=all_points,
            base_position=(cx, cy, 0),
            height=max_height,
            volume=total_volume,
            estimated_material_grams=total_volume / 1000 * 1.24,
            material_savings_percent=20,
        )

    def _remove_redundant_supports(
        self,
        structures: List[SupportStructure],
    ) -> Tuple[List[SupportStructure], int]:
        """Remove supports that aren't necessary."""
        if not structures:
            return structures, 0

        removed_count = 0
        result = []

        for struct in structures:
            # Keep all structures with significant overhangs
            max_angle = max((p.overhang_angle for p in struct.points), default=0)

            if max_angle >= 45:  # Keep
                result.append(struct)
            elif struct.height > 2.0:  # Keep taller structures
                result.append(struct)
            else:
                # Remove small, low-angle supports
                removed_count += 1
                logger.debug(f"Removed redundant support: angle={max_angle:.0f}°, height={struct.height:.1f}mm")

        return result, removed_count

    def _reinforce_critical_supports(
        self,
        structures: List[SupportStructure],
    ) -> Tuple[List[SupportStructure], int]:
        """Reinforce supports under critical overhangs."""
        reinforced_count = 0
        result = []

        for struct in structures:
            max_angle = max((p.overhang_angle for p in struct.points), default=0)
            max_area = max((p.area for p in struct.points), default=0)

            # Reinforce critical overhangs
            needs_reinforcement = max_angle >= 70 or max_area > 100

            if needs_reinforcement:
                # Increase volume by 20% for reinforcement
                struct.volume *= 1.2
                struct.estimated_material_grams *= 1.2
                for point in struct.points:
                    point.needs_reinforcement = True
                reinforced_count += 1

            result.append(struct)

        return result, reinforced_count

    def _optimize_for_removal(
        self,
        structures: List[SupportStructure],
    ) -> List[SupportStructure]:
        """Optimize supports for easy removal."""
        result = []

        for struct in structures:
            # Convert to tree supports for easier removal
            struct.support_type = SupportType.TREE

            # Reduce contact area
            struct.volume *= 0.9

            result.append(struct)

        return result

    def _optimize_for_speed(
        self,
        structures: List[SupportStructure],
    ) -> List[SupportStructure]:
        """Optimize supports for faster printing."""
        result = []

        for struct in structures:
            # Use sparse density
            struct.volume *= 0.7  # Reduce volume

            result.append(struct)

        return result

    def _distance(
        self,
        a: Tuple[float, float, float],
        b: Tuple[float, float, float],
    ) -> float:
        """Calculate distance between two points."""
        return math.sqrt(
            (a[0] - b[0]) ** 2 +
            (a[1] - b[1]) ** 2 +
            (a[2] - b[2]) ** 2
        )


def generate_optimized_supports(
    file_path: str,
    support_type: SupportType = SupportType.TREE,
    goal: OptimizationGoal = OptimizationGoal.BALANCED,
) -> OptimizationResult:
    """
    Generate and optimize supports in one step.

    Args:
        file_path: Path to STL file
        support_type: Type of support to generate
        goal: Optimization goal

    Returns:
        OptimizationResult with optimized supports
    """
    # Generate initial supports
    settings = SupportSettings(support_type=support_type)
    generator = SupportGenerator(settings)
    support_result = generator.generate(file_path)

    # Optimize
    optimizer = SupportOptimizer()
    return optimizer.optimize(support_result, goal=goal)


def compare_support_strategies(file_path: str) -> Dict:
    """
    Compare different support strategies.

    Args:
        file_path: Path to STL file

    Returns:
        Comparison data for different strategies
    """
    results = {}

    # Normal supports
    normal_settings = SupportSettings(support_type=SupportType.NORMAL)
    normal_gen = SupportGenerator(normal_settings)
    results["normal"] = normal_gen.generate(file_path)

    # Tree supports
    tree_settings = SupportSettings(support_type=SupportType.TREE)
    tree_gen = SupportGenerator(tree_settings)
    results["tree"] = tree_gen.generate(file_path)

    # Optimized tree
    optimizer = SupportOptimizer()
    results["optimized"] = optimizer.optimize(results["tree"])

    return {
        "file": file_path,
        "strategies": {
            "normal": {
                "volume_mm3": results["normal"].total_support_volume,
                "material_grams": results["normal"].total_material_grams,
                "structures": len(results["normal"].structures),
            },
            "tree": {
                "volume_mm3": results["tree"].total_support_volume,
                "material_grams": results["tree"].total_material_grams,
                "structures": len(results["tree"].structures),
            },
            "optimized_tree": {
                "volume_mm3": results["optimized"].optimized.total_support_volume,
                "material_grams": results["optimized"].optimized.total_material_grams,
                "structures": len(results["optimized"].optimized.structures),
                "savings_percent": results["optimized"].reduction_percent,
            },
        },
        "recommendation": "optimized_tree",
        "potential_savings": f"{results['optimized'].reduction_percent:.0f}% vs tree, "
                           f"{((results['normal'].total_support_volume - results['optimized'].optimized.total_support_volume) / results['normal'].total_support_volume * 100) if results['normal'].total_support_volume > 0 else 0:.0f}% vs normal",
    }
