"""Cost estimation and optimization for 3D printing.

Provides detailed cost breakdowns and optimization suggestions.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("estimator.cost_optimizer")


@dataclass
class PrintSettings:
    """Settings that affect print cost."""
    layer_height: float = 0.20  # mm
    infill_percent: int = 20  # 0-100
    wall_count: int = 3
    top_layers: int = 4
    bottom_layers: int = 4
    supports: bool = False
    support_density: int = 15  # percent
    brim: bool = False
    raft: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "layer_height": self.layer_height,
            "infill_percent": self.infill_percent,
            "wall_count": self.wall_count,
            "top_layers": self.top_layers,
            "bottom_layers": self.bottom_layers,
            "supports": self.supports,
            "support_density": self.support_density,
            "brim": self.brim,
            "raft": self.raft,
        }


@dataclass
class CostConfig:
    """Configuration for cost calculation."""
    # Material costs (per gram)
    pla_cost_per_gram: float = 0.025
    petg_cost_per_gram: float = 0.030
    abs_cost_per_gram: float = 0.028
    tpu_cost_per_gram: float = 0.045

    # Electricity cost
    electricity_cost_per_kwh: float = 0.12
    printer_power_watts: float = 150.0

    # Machine costs
    machine_cost_per_hour: float = 0.50  # Depreciation/maintenance

    # Labor costs
    labor_cost_per_print: float = 0.0  # Optional setup time

    # Default material
    default_material: str = "pla"

    def get_material_cost(self, material: str) -> float:
        """Get cost per gram for a material."""
        costs = {
            "pla": self.pla_cost_per_gram,
            "petg": self.petg_cost_per_gram,
            "abs": self.abs_cost_per_gram,
            "tpu": self.tpu_cost_per_gram,
        }
        return costs.get(material.lower(), self.pla_cost_per_gram)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "pla_cost_per_gram": self.pla_cost_per_gram,
            "petg_cost_per_gram": self.petg_cost_per_gram,
            "abs_cost_per_gram": self.abs_cost_per_gram,
            "tpu_cost_per_gram": self.tpu_cost_per_gram,
            "electricity_cost_per_kwh": self.electricity_cost_per_kwh,
            "printer_power_watts": self.printer_power_watts,
            "machine_cost_per_hour": self.machine_cost_per_hour,
            "labor_cost_per_print": self.labor_cost_per_print,
        }


@dataclass
class CostEstimate:
    """Detailed cost estimate for a print."""
    material_cost: float = 0.0
    electricity_cost: float = 0.0
    machine_cost: float = 0.0
    labor_cost: float = 0.0
    total_cost: float = 0.0
    material_grams: float = 0.0
    print_time_hours: float = 0.0
    cost_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "material_cost": self.material_cost,
            "electricity_cost": self.electricity_cost,
            "machine_cost": self.machine_cost,
            "labor_cost": self.labor_cost,
            "total_cost": self.total_cost,
            "material_grams": self.material_grams,
            "print_time_hours": self.print_time_hours,
            "cost_breakdown": self.cost_breakdown,
        }


@dataclass
class OptimizationResult:
    """Result of cost optimization."""
    success: bool
    original_cost: float = 0.0
    optimized_cost: float = 0.0
    savings: float = 0.0
    savings_percent: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    optimized_settings: Optional[PrintSettings] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "original_cost": self.original_cost,
            "optimized_cost": self.optimized_cost,
            "savings": self.savings,
            "savings_percent": self.savings_percent,
            "recommendations": self.recommendations,
            "optimized_settings": self.optimized_settings.to_dict() if self.optimized_settings else None,
            "error_message": self.error_message,
        }


class CostOptimizer:
    """
    Cost estimator and optimizer for 3D printing.

    Calculates detailed cost breakdowns and provides
    optimization recommendations.
    """

    def __init__(self, config: Optional[CostConfig] = None):
        """
        Initialize cost optimizer.

        Args:
            config: Cost configuration
        """
        self.config = config or CostConfig()

    def estimate_cost(
        self,
        volume_cm3: float,
        settings: Optional[PrintSettings] = None,
        material: str = "pla",
    ) -> CostEstimate:
        """
        Estimate cost for a print.

        Args:
            volume_cm3: Part volume in cubic centimeters
            settings: Print settings
            material: Material type

        Returns:
            Detailed cost estimate
        """
        settings = settings or PrintSettings()

        # Estimate material usage
        material_grams = self._estimate_material(volume_cm3, settings)

        # Estimate print time
        print_time_hours = self._estimate_time(volume_cm3, settings)

        # Calculate costs
        material_cost = material_grams * self.config.get_material_cost(material)
        electricity_cost = (
            print_time_hours *
            (self.config.printer_power_watts / 1000) *
            self.config.electricity_cost_per_kwh
        )
        machine_cost = print_time_hours * self.config.machine_cost_per_hour
        labor_cost = self.config.labor_cost_per_print

        total_cost = material_cost + electricity_cost + machine_cost + labor_cost

        return CostEstimate(
            material_cost=round(material_cost, 3),
            electricity_cost=round(electricity_cost, 3),
            machine_cost=round(machine_cost, 3),
            labor_cost=round(labor_cost, 3),
            total_cost=round(total_cost, 3),
            material_grams=round(material_grams, 1),
            print_time_hours=round(print_time_hours, 2),
            cost_breakdown={
                "material": round(material_cost, 3),
                "electricity": round(electricity_cost, 3),
                "machine": round(machine_cost, 3),
                "labor": round(labor_cost, 3),
            },
        )

    def _estimate_material(
        self,
        volume_cm3: float,
        settings: PrintSettings,
    ) -> float:
        """Estimate material usage in grams."""
        # Base material from volume (PLA density ~1.24 g/cm3)
        density = 1.24  # g/cm3

        # Estimate shell volume (walls)
        # Assume typical shell is ~10-20% of volume for normal parts
        shell_percent = min(100, settings.wall_count * 5 + settings.top_layers * 2 + settings.bottom_layers * 2)

        # Infill volume
        infill_volume = volume_cm3 * (1 - shell_percent / 100) * (settings.infill_percent / 100)
        shell_volume = volume_cm3 * (shell_percent / 100)

        total_volume = infill_volume + shell_volume

        # Add supports if enabled
        if settings.supports:
            # Rough estimate: supports add 10-30% material
            support_factor = 0.1 + (settings.support_density / 100) * 0.2
            total_volume *= (1 + support_factor)

        # Add brim/raft
        if settings.brim:
            total_volume += 0.5  # Approximate brim volume
        if settings.raft:
            total_volume += 2.0  # Approximate raft volume

        return total_volume * density

    def _estimate_time(
        self,
        volume_cm3: float,
        settings: PrintSettings,
    ) -> float:
        """Estimate print time in hours."""
        # Base time estimation
        # Typical print speed: ~50mm3/s for infill, ~30mm3/s for walls

        # Convert to mm3
        volume_mm3 = volume_cm3 * 1000

        # Estimate time based on layer height
        # Thinner layers = more passes = more time
        layer_factor = 0.2 / settings.layer_height  # Normalized to 0.2mm

        # Estimate speed based on infill
        avg_speed = 40 + (settings.infill_percent / 100) * 10  # mm3/s

        # Base time
        base_time_seconds = volume_mm3 / avg_speed * layer_factor

        # Add time for supports
        if settings.supports:
            base_time_seconds *= 1.15  # 15% extra time

        # Convert to hours
        return base_time_seconds / 3600

    def optimize(
        self,
        volume_cm3: float,
        current_settings: Optional[PrintSettings] = None,
        material: str = "pla",
        min_quality: str = "normal",  # draft, normal, high
    ) -> OptimizationResult:
        """
        Optimize print settings for cost.

        Args:
            volume_cm3: Part volume
            current_settings: Current settings
            material: Material type
            min_quality: Minimum acceptable quality

        Returns:
            Optimization result with recommendations
        """
        current_settings = current_settings or PrintSettings()

        # Calculate original cost
        original_estimate = self.estimate_cost(volume_cm3, current_settings, material)
        original_cost = original_estimate.total_cost

        # Create optimized settings
        optimized_settings = PrintSettings(
            layer_height=current_settings.layer_height,
            infill_percent=current_settings.infill_percent,
            wall_count=current_settings.wall_count,
            top_layers=current_settings.top_layers,
            bottom_layers=current_settings.bottom_layers,
            supports=current_settings.supports,
            support_density=current_settings.support_density,
            brim=current_settings.brim,
            raft=current_settings.raft,
        )

        recommendations = []

        # Quality-dependent optimizations
        if min_quality in ["draft", "normal"]:
            # Increase layer height
            if current_settings.layer_height < 0.28:
                max_layer = 0.28 if min_quality == "draft" else 0.24
                optimized_settings.layer_height = max_layer
                recommendations.append(
                    f"Increase layer height to {max_layer}mm for faster printing"
                )

        # Reduce infill if high
        if current_settings.infill_percent > 25:
            suggested_infill = 15 if min_quality == "draft" else 20
            optimized_settings.infill_percent = suggested_infill
            recommendations.append(
                f"Reduce infill to {suggested_infill}% (sufficient for most parts)"
            )

        # Reduce walls if > 3
        if current_settings.wall_count > 3:
            optimized_settings.wall_count = 3
            recommendations.append("Reduce wall count to 3 (standard strength)")

        # Reduce top/bottom if > 4
        if current_settings.top_layers > 4:
            optimized_settings.top_layers = 4
            recommendations.append("Reduce top layers to 4")
        if current_settings.bottom_layers > 4:
            optimized_settings.bottom_layers = 4
            recommendations.append("Reduce bottom layers to 4")

        # Reduce support density if supports enabled
        if current_settings.supports and current_settings.support_density > 15:
            optimized_settings.support_density = 10
            recommendations.append("Reduce support density to 10%")

        # Remove raft if not needed
        if current_settings.raft:
            optimized_settings.raft = False
            optimized_settings.brim = True
            recommendations.append("Replace raft with brim (saves material)")

        # Calculate optimized cost
        optimized_estimate = self.estimate_cost(volume_cm3, optimized_settings, material)
        optimized_cost = optimized_estimate.total_cost

        savings = original_cost - optimized_cost
        savings_percent = (savings / original_cost * 100) if original_cost > 0 else 0

        return OptimizationResult(
            success=True,
            original_cost=original_cost,
            optimized_cost=optimized_cost,
            savings=round(savings, 3),
            savings_percent=round(savings_percent, 1),
            recommendations=recommendations,
            optimized_settings=optimized_settings,
        )

    def estimate_from_mesh(
        self,
        mesh_path: str,
        settings: Optional[PrintSettings] = None,
        material: str = "pla",
    ) -> CostEstimate:
        """
        Estimate cost from a mesh file.

        Args:
            mesh_path: Path to mesh file
            settings: Print settings
            material: Material type

        Returns:
            Cost estimate
        """
        volume = self._calculate_volume(mesh_path)
        if volume <= 0:
            logger.warning(f"Could not calculate volume for {mesh_path}")
            volume = 1.0  # Default 1 cm3

        return self.estimate_cost(volume, settings, material)

    def _calculate_volume(self, mesh_path: str) -> float:
        """Calculate volume of a mesh in cm3."""
        mesh = Path(mesh_path)
        if not mesh.exists():
            return 0.0

        try:
            # Parse mesh and calculate volume
            vertices = []
            faces = []

            if mesh.suffix.lower() == ".obj":
                with open(mesh, "r") as f:
                    for line in f:
                        if line.startswith("v "):
                            parts = line.split()
                            if len(parts) >= 4:
                                vertices.append((
                                    float(parts[1]),
                                    float(parts[2]),
                                    float(parts[3]),
                                ))
                        elif line.startswith("f "):
                            parts = line.split()[1:]
                            indices = [int(p.split("/")[0]) - 1 for p in parts[:3]]
                            if len(indices) == 3:
                                faces.append(tuple(indices))

            elif mesh.suffix.lower() == ".stl":
                import re
                with open(mesh, "r") as f:
                    content = f.read()
                vertex_pattern = r"vertex\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)"
                for i, match in enumerate(re.finditer(vertex_pattern, content, re.IGNORECASE)):
                    vertices.append((float(match.group(1)), float(match.group(2)), float(match.group(3))))
                    if (i + 1) % 3 == 0:
                        base = len(vertices) - 3
                        faces.append((base, base + 1, base + 2))

            if not vertices or not faces:
                return 0.0

            # Calculate volume using signed volume formula
            volume = 0.0
            for face in faces:
                if max(face) >= len(vertices):
                    continue
                v0 = vertices[face[0]]
                v1 = vertices[face[1]]
                v2 = vertices[face[2]]

                # Signed volume of tetrahedron with origin
                volume += (
                    v0[0] * (v1[1] * v2[2] - v2[1] * v1[2]) +
                    v1[0] * (v2[1] * v0[2] - v0[1] * v2[2]) +
                    v2[0] * (v0[1] * v1[2] - v1[1] * v0[2])
                ) / 6.0

            # Convert mm3 to cm3
            return abs(volume) / 1000

        except Exception as e:
            logger.warning(f"Error calculating volume: {e}")
            return 0.0

    def compare_materials(
        self,
        volume_cm3: float,
        settings: Optional[PrintSettings] = None,
    ) -> Dict[str, CostEstimate]:
        """Compare costs across different materials."""
        materials = ["pla", "petg", "abs", "tpu"]
        comparisons = {}

        for material in materials:
            comparisons[material] = self.estimate_cost(volume_cm3, settings, material)

        return comparisons


# Convenience functions
def create_optimizer(
    material_cost: float = 0.025,
    electricity_cost: float = 0.12,
) -> CostOptimizer:
    """Create a cost optimizer with specified rates."""
    config = CostConfig(
        pla_cost_per_gram=material_cost,
        electricity_cost_per_kwh=electricity_cost,
    )
    return CostOptimizer(config=config)


def estimate_cost(
    volume_cm3: float,
    infill: int = 20,
    layer_height: float = 0.20,
    material: str = "pla",
) -> CostEstimate:
    """
    Quick cost estimate.

    Args:
        volume_cm3: Part volume
        infill: Infill percentage
        layer_height: Layer height in mm
        material: Material type

    Returns:
        Cost estimate
    """
    settings = PrintSettings(
        layer_height=layer_height,
        infill_percent=infill,
    )
    optimizer = CostOptimizer()
    return optimizer.estimate_cost(volume_cm3, settings, material)
