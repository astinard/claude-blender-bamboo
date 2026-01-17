"""
Comprehensive Cost Estimation for 3D Printing and Laser Cutting.

Features:
- Material usage estimation (grams, meters)
- Print/cut time estimation
- Cost calculation with detailed breakdown
- Multi-material/multi-color support
- Machine time costs (hourly rate)
- Energy costs (optional)
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple


class ManufacturingMethod(Enum):
    """Types of manufacturing methods."""
    FDM_PRINT = "fdm_print"  # Fused Deposition Modeling (3D printing)
    LASER_CUT = "laser_cut"  # Laser cutting
    LASER_ENGRAVE = "laser_engrave"  # Laser engraving


@dataclass
class MaterialCost:
    """Cost information for a material."""
    name: str
    cost_per_kg: float = 25.0  # USD per kg for filament
    cost_per_m2: float = 0.0  # USD per m² for sheet materials
    cost_per_meter: float = 0.0  # USD per linear meter
    density: float = 1.24  # g/cm³ (PLA default)

    @property
    def cost_per_gram(self) -> float:
        """Get cost per gram."""
        return self.cost_per_kg / 1000

    @property
    def cost_per_cm3(self) -> float:
        """Get cost per cubic centimeter."""
        return self.cost_per_gram * self.density


@dataclass
class MachineCosts:
    """Machine operating costs."""
    hourly_rate: float = 0.50  # USD per hour (depreciation + maintenance)
    energy_cost_per_kwh: float = 0.12  # USD per kWh
    average_power_watts: float = 150  # Average power consumption

    @property
    def energy_cost_per_hour(self) -> float:
        """Get energy cost per hour."""
        return (self.average_power_watts / 1000) * self.energy_cost_per_kwh


@dataclass
class CostBreakdown:
    """Detailed cost breakdown."""
    material_cost: float = 0.0
    machine_time_cost: float = 0.0
    energy_cost: float = 0.0
    overhead_cost: float = 0.0  # Markup, overhead, etc.

    @property
    def total_cost(self) -> float:
        """Get total cost."""
        return self.material_cost + self.machine_time_cost + self.energy_cost + self.overhead_cost

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "material_cost": self.material_cost,
            "machine_time_cost": self.machine_time_cost,
            "energy_cost": self.energy_cost,
            "overhead_cost": self.overhead_cost,
            "total_cost": self.total_cost,
        }


@dataclass
class MaterialUsage:
    """Material usage for a single material/color."""
    name: str
    color: Optional[str] = None
    volume_mm3: float = 0.0  # Volume in cubic mm
    weight_grams: float = 0.0  # Weight in grams
    length_meters: float = 0.0  # Length in meters (for paths/filament)
    area_mm2: float = 0.0  # Area in square mm (for sheets)
    cost: float = 0.0  # Cost in USD

    @property
    def volume_cm3(self) -> float:
        """Get volume in cubic cm."""
        return self.volume_mm3 / 1000

    @property
    def area_cm2(self) -> float:
        """Get area in square cm."""
        return self.area_mm2 / 100


@dataclass
class PrintEstimate:
    """3D print cost and time estimate."""
    # Basic info
    model_name: str = ""
    method: ManufacturingMethod = ManufacturingMethod.FDM_PRINT

    # Volume and weight
    total_volume_mm3: float = 0.0
    total_weight_grams: float = 0.0
    filament_length_meters: float = 0.0

    # Time estimates
    print_time_seconds: float = 0.0
    print_time_per_color_seconds: Dict[str, float] = field(default_factory=dict)

    # Material usage by color
    material_usage: List[MaterialUsage] = field(default_factory=list)

    # Cost breakdown
    cost_breakdown: CostBreakdown = field(default_factory=CostBreakdown)

    # Settings used for estimate
    layer_height_mm: float = 0.2
    infill_percent: int = 20

    @property
    def print_time_minutes(self) -> float:
        """Get print time in minutes."""
        return self.print_time_seconds / 60

    @property
    def print_time_hours(self) -> float:
        """Get print time in hours."""
        return self.print_time_seconds / 3600

    @property
    def print_time_formatted(self) -> str:
        """Get human-readable print time."""
        hours = int(self.print_time_hours)
        mins = int((self.print_time_seconds % 3600) / 60)
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    @property
    def total_cost(self) -> float:
        """Get total cost."""
        return self.cost_breakdown.total_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "method": self.method.value,
            "total_volume_mm3": self.total_volume_mm3,
            "total_weight_grams": self.total_weight_grams,
            "filament_length_meters": self.filament_length_meters,
            "print_time_seconds": self.print_time_seconds,
            "print_time_formatted": self.print_time_formatted,
            "layer_height_mm": self.layer_height_mm,
            "infill_percent": self.infill_percent,
            "material_usage": [
                {
                    "name": m.name,
                    "color": m.color,
                    "weight_grams": m.weight_grams,
                    "cost": m.cost,
                }
                for m in self.material_usage
            ],
            "cost_breakdown": self.cost_breakdown.to_dict(),
            "total_cost": self.total_cost,
        }


@dataclass
class LaserEstimate:
    """Laser cutting/engraving cost and time estimate."""
    # Basic info
    job_name: str = ""
    method: ManufacturingMethod = ManufacturingMethod.LASER_CUT

    # Path metrics
    total_path_length_mm: float = 0.0
    total_area_mm2: float = 0.0
    path_count: int = 0

    # Time estimates
    cut_time_seconds: float = 0.0
    travel_time_seconds: float = 0.0
    total_time_seconds: float = 0.0

    # Material usage
    material_usage: List[MaterialUsage] = field(default_factory=list)

    # Cost breakdown
    cost_breakdown: CostBreakdown = field(default_factory=CostBreakdown)

    # Settings used
    cut_speed_mm_per_sec: float = 10.0
    travel_speed_mm_per_sec: float = 100.0
    material_name: str = ""
    material_thickness_mm: float = 3.0

    @property
    def total_time_minutes(self) -> float:
        """Get total time in minutes."""
        return self.total_time_seconds / 60

    @property
    def total_time_formatted(self) -> str:
        """Get human-readable total time."""
        mins = int(self.total_time_minutes)
        secs = int(self.total_time_seconds % 60)
        if mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"

    @property
    def total_cost(self) -> float:
        """Get total cost."""
        return self.cost_breakdown.total_cost

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_name": self.job_name,
            "method": self.method.value,
            "total_path_length_mm": self.total_path_length_mm,
            "total_area_mm2": self.total_area_mm2,
            "path_count": self.path_count,
            "cut_time_seconds": self.cut_time_seconds,
            "travel_time_seconds": self.travel_time_seconds,
            "total_time_seconds": self.total_time_seconds,
            "total_time_formatted": self.total_time_formatted,
            "material_name": self.material_name,
            "material_thickness_mm": self.material_thickness_mm,
            "cost_breakdown": self.cost_breakdown.to_dict(),
            "total_cost": self.total_cost,
        }


# Default material costs
DEFAULT_FILAMENT_COSTS: Dict[str, MaterialCost] = {
    "pla": MaterialCost("PLA", cost_per_kg=25.0, density=1.24),
    "petg": MaterialCost("PETG", cost_per_kg=30.0, density=1.27),
    "abs": MaterialCost("ABS", cost_per_kg=28.0, density=1.04),
    "tpu": MaterialCost("TPU", cost_per_kg=45.0, density=1.21),
    "pa": MaterialCost("PA/Nylon", cost_per_kg=60.0, density=1.14),
    "asa": MaterialCost("ASA", cost_per_kg=35.0, density=1.07),
    "pc": MaterialCost("PC", cost_per_kg=50.0, density=1.20),
    "pla_silk": MaterialCost("PLA Silk", cost_per_kg=35.0, density=1.24),
    "pla_cf": MaterialCost("PLA-CF", cost_per_kg=55.0, density=1.30),
}

DEFAULT_SHEET_COSTS: Dict[str, MaterialCost] = {
    "plywood_3mm": MaterialCost("Plywood 3mm", cost_per_m2=8.0),
    "plywood_6mm": MaterialCost("Plywood 6mm", cost_per_m2=12.0),
    "mdf_3mm": MaterialCost("MDF 3mm", cost_per_m2=6.0),
    "mdf_6mm": MaterialCost("MDF 6mm", cost_per_m2=10.0),
    "acrylic_3mm": MaterialCost("Acrylic 3mm", cost_per_m2=25.0),
    "acrylic_6mm": MaterialCost("Acrylic 6mm", cost_per_m2=45.0),
    "cardboard": MaterialCost("Cardboard", cost_per_m2=2.0),
    "leather_3mm": MaterialCost("Leather 3mm", cost_per_m2=80.0),
    "cork_3mm": MaterialCost("Cork 3mm", cost_per_m2=15.0),
    "basswood_3mm": MaterialCost("Basswood 3mm", cost_per_m2=20.0),
}


class CostEstimator:
    """
    Comprehensive cost estimator for 3D printing and laser cutting.
    """

    def __init__(
        self,
        filament_costs: Optional[Dict[str, MaterialCost]] = None,
        sheet_costs: Optional[Dict[str, MaterialCost]] = None,
        machine_costs: Optional[MachineCosts] = None,
        overhead_percent: float = 0.0,  # Markup percentage
    ):
        self.filament_costs = filament_costs or DEFAULT_FILAMENT_COSTS
        self.sheet_costs = sheet_costs or DEFAULT_SHEET_COSTS
        self.machine_costs = machine_costs or MachineCosts()
        self.overhead_percent = overhead_percent

    def estimate_print(
        self,
        volume_mm3: float,
        material: str = "pla",
        layer_height_mm: float = 0.2,
        infill_percent: int = 20,
        model_name: str = "",
        color_volumes: Optional[Dict[str, float]] = None,  # color -> volume_mm3
        print_speed_mm_per_sec: float = 60.0,
    ) -> PrintEstimate:
        """
        Estimate 3D print cost and time.

        Args:
            volume_mm3: Total model volume in cubic mm
            material: Material type (pla, petg, abs, etc.)
            layer_height_mm: Layer height for printing
            infill_percent: Infill percentage (0-100)
            model_name: Name of the model
            color_volumes: Optional per-color volume breakdown
            print_speed_mm_per_sec: Print speed in mm/s

        Returns:
            PrintEstimate with detailed breakdown
        """
        material_info = self.filament_costs.get(
            material.lower(),
            self.filament_costs.get("pla", MaterialCost("Unknown", 25.0, 1.24))
        )

        # Calculate weight
        volume_cm3 = volume_mm3 / 1000
        weight_grams = volume_cm3 * material_info.density

        # Calculate filament length (1.75mm diameter filament)
        filament_diameter = 1.75  # mm
        filament_area = math.pi * (filament_diameter / 2) ** 2  # mm²
        filament_length_mm = volume_mm3 / filament_area
        filament_length_meters = filament_length_mm / 1000

        # Calculate material usage by color
        material_usage = []
        if color_volumes:
            for color, vol in color_volumes.items():
                vol_cm3 = vol / 1000
                wt = vol_cm3 * material_info.density
                cost = wt * material_info.cost_per_gram
                material_usage.append(MaterialUsage(
                    name=material_info.name,
                    color=color,
                    volume_mm3=vol,
                    weight_grams=wt,
                    cost=cost,
                ))
        else:
            material_usage.append(MaterialUsage(
                name=material_info.name,
                volume_mm3=volume_mm3,
                weight_grams=weight_grams,
                cost=weight_grams * material_info.cost_per_gram,
            ))

        # Estimate print time
        # Based on: time = (perimeter + infill + travel) / speed
        # Simplified: roughly proportional to volume / (layer_height * speed)
        # With adjustments for perimeter walls and infill

        # Effective print speed (accounting for acceleration, corners, etc.)
        effective_speed = print_speed_mm_per_sec * 0.6  # ~60% efficiency

        # Rough approximation: print time in seconds
        # Based on the idea that printing 1cm³ at 0.2mm layer height takes ~5-10 minutes
        base_time_per_cm3 = 8 * 60  # 8 minutes per cm³ at 0.2mm layer
        layer_factor = 0.2 / layer_height_mm  # Thicker layers = faster
        infill_factor = 0.3 + (infill_percent / 100) * 0.7  # More infill = slower

        print_time_seconds = volume_cm3 * base_time_per_cm3 * layer_factor * infill_factor

        # Calculate costs
        material_cost = sum(m.cost for m in material_usage)
        machine_time_hours = print_time_seconds / 3600
        machine_time_cost = machine_time_hours * self.machine_costs.hourly_rate
        energy_cost = machine_time_hours * self.machine_costs.energy_cost_per_hour

        subtotal = material_cost + machine_time_cost + energy_cost
        overhead_cost = subtotal * (self.overhead_percent / 100)

        cost_breakdown = CostBreakdown(
            material_cost=material_cost,
            machine_time_cost=machine_time_cost,
            energy_cost=energy_cost,
            overhead_cost=overhead_cost,
        )

        return PrintEstimate(
            model_name=model_name,
            method=ManufacturingMethod.FDM_PRINT,
            total_volume_mm3=volume_mm3,
            total_weight_grams=weight_grams,
            filament_length_meters=filament_length_meters,
            print_time_seconds=print_time_seconds,
            material_usage=material_usage,
            cost_breakdown=cost_breakdown,
            layer_height_mm=layer_height_mm,
            infill_percent=infill_percent,
        )

    def estimate_laser_cut(
        self,
        path_length_mm: float,
        travel_length_mm: float = 0,
        area_mm2: float = 0,
        path_count: int = 1,
        material: str = "plywood_3mm",
        cut_speed_mm_per_sec: float = 10.0,
        travel_speed_mm_per_sec: float = 100.0,
        job_name: str = "",
    ) -> LaserEstimate:
        """
        Estimate laser cutting cost and time.

        Args:
            path_length_mm: Total cutting path length in mm
            travel_length_mm: Total travel (non-cutting) distance in mm
            area_mm2: Material area used in mm²
            path_count: Number of distinct paths
            material: Material type (plywood_3mm, acrylic_3mm, etc.)
            cut_speed_mm_per_sec: Cutting speed in mm/s
            travel_speed_mm_per_sec: Travel speed in mm/s
            job_name: Name of the job

        Returns:
            LaserEstimate with detailed breakdown
        """
        material_info = self.sheet_costs.get(
            material.lower(),
            MaterialCost("Unknown", cost_per_m2=10.0)
        )

        # Calculate times
        cut_time_seconds = path_length_mm / cut_speed_mm_per_sec
        travel_time_seconds = travel_length_mm / travel_speed_mm_per_sec if travel_length_mm > 0 else 0

        # Add setup time per path (laser on/off, settling)
        setup_time_per_path = 0.5  # seconds
        total_time_seconds = cut_time_seconds + travel_time_seconds + (path_count * setup_time_per_path)

        # Calculate material cost
        area_m2 = area_mm2 / 1_000_000
        material_cost = area_m2 * material_info.cost_per_m2

        # Material usage
        material_usage = [MaterialUsage(
            name=material_info.name,
            area_mm2=area_mm2,
            cost=material_cost,
        )]

        # Calculate costs
        machine_time_hours = total_time_seconds / 3600
        machine_time_cost = machine_time_hours * self.machine_costs.hourly_rate
        energy_cost = machine_time_hours * self.machine_costs.energy_cost_per_hour

        subtotal = material_cost + machine_time_cost + energy_cost
        overhead_cost = subtotal * (self.overhead_percent / 100)

        cost_breakdown = CostBreakdown(
            material_cost=material_cost,
            machine_time_cost=machine_time_cost,
            energy_cost=energy_cost,
            overhead_cost=overhead_cost,
        )

        # Extract thickness from material name
        thickness = 3.0
        if "6mm" in material:
            thickness = 6.0
        elif "3mm" in material:
            thickness = 3.0

        return LaserEstimate(
            job_name=job_name,
            method=ManufacturingMethod.LASER_CUT,
            total_path_length_mm=path_length_mm,
            total_area_mm2=area_mm2,
            path_count=path_count,
            cut_time_seconds=cut_time_seconds,
            travel_time_seconds=travel_time_seconds,
            total_time_seconds=total_time_seconds,
            material_usage=material_usage,
            cost_breakdown=cost_breakdown,
            cut_speed_mm_per_sec=cut_speed_mm_per_sec,
            travel_speed_mm_per_sec=travel_speed_mm_per_sec,
            material_name=material_info.name,
            material_thickness_mm=thickness,
        )

    def estimate_laser_engrave(
        self,
        area_mm2: float,
        fill_percent: float = 100.0,
        material: str = "plywood_3mm",
        engrave_speed_mm_per_sec: float = 100.0,
        line_spacing_mm: float = 0.1,
        job_name: str = "",
    ) -> LaserEstimate:
        """
        Estimate laser engraving cost and time.

        Args:
            area_mm2: Total area to engrave in mm²
            fill_percent: Percentage of area that is filled (0-100)
            material: Material type
            engrave_speed_mm_per_sec: Engraving speed in mm/s
            line_spacing_mm: Line spacing for engraving
            job_name: Name of the job

        Returns:
            LaserEstimate with detailed breakdown
        """
        # Calculate total path length for engraving
        # Engraving fills area with parallel lines
        actual_area = area_mm2 * (fill_percent / 100)

        # Estimate bounding box dimensions (assume square for simplicity)
        side_length = math.sqrt(actual_area)
        num_lines = side_length / line_spacing_mm
        path_length_mm = num_lines * side_length  # Total length of engraving lines

        # Travel between lines
        travel_length_mm = num_lines * line_spacing_mm

        # Use laser_cut estimation with engraving parameters
        estimate = self.estimate_laser_cut(
            path_length_mm=path_length_mm,
            travel_length_mm=travel_length_mm,
            area_mm2=area_mm2,
            path_count=int(num_lines),
            material=material,
            cut_speed_mm_per_sec=engrave_speed_mm_per_sec,
            job_name=job_name,
        )

        estimate.method = ManufacturingMethod.LASER_ENGRAVE

        return estimate


# Convenience functions

def estimate_print_cost(
    volume_mm3: float,
    material: str = "pla",
    **kwargs
) -> PrintEstimate:
    """Quick print cost estimation."""
    estimator = CostEstimator()
    return estimator.estimate_print(volume_mm3, material, **kwargs)


def estimate_laser_cost(
    path_length_mm: float,
    material: str = "plywood_3mm",
    **kwargs
) -> LaserEstimate:
    """Quick laser cost estimation."""
    estimator = CostEstimator()
    return estimator.estimate_laser_cut(path_length_mm, material=material, **kwargs)


def format_estimate(estimate: PrintEstimate | LaserEstimate) -> str:
    """Format estimate for display."""
    lines = []

    if isinstance(estimate, PrintEstimate):
        lines.extend([
            f"=== 3D PRINT ESTIMATE ===",
            f"Model: {estimate.model_name or 'Unnamed'}",
            f"",
            f"MATERIAL USAGE:",
            f"  Total volume: {estimate.total_volume_mm3/1000:.2f} cm³",
            f"  Total weight: {estimate.total_weight_grams:.1f} g",
            f"  Filament length: {estimate.filament_length_meters:.1f} m",
        ])

        if len(estimate.material_usage) > 1:
            lines.append(f"")
            lines.append(f"  BY COLOR:")
            for m in estimate.material_usage:
                lines.append(f"    {m.color}: {m.weight_grams:.1f}g (${m.cost:.2f})")

        lines.extend([
            f"",
            f"PRINT SETTINGS:",
            f"  Layer height: {estimate.layer_height_mm}mm",
            f"  Infill: {estimate.infill_percent}%",
            f"",
            f"TIME ESTIMATE:",
            f"  Print time: {estimate.print_time_formatted}",
        ])

    elif isinstance(estimate, LaserEstimate):
        lines.extend([
            f"=== LASER {'ENGRAVE' if estimate.method == ManufacturingMethod.LASER_ENGRAVE else 'CUT'} ESTIMATE ===",
            f"Job: {estimate.job_name or 'Unnamed'}",
            f"",
            f"PATH METRICS:",
            f"  Path length: {estimate.total_path_length_mm/10:.1f} cm",
            f"  Path count: {estimate.path_count}",
            f"  Material area: {estimate.total_area_mm2/100:.1f} cm²",
            f"",
            f"MATERIAL:",
            f"  Type: {estimate.material_name}",
            f"  Thickness: {estimate.material_thickness_mm}mm",
            f"",
            f"TIME ESTIMATE:",
            f"  Cut time: {estimate.cut_time_seconds:.1f}s",
            f"  Travel time: {estimate.travel_time_seconds:.1f}s",
            f"  Total time: {estimate.total_time_formatted}",
        ])

    # Cost breakdown (common)
    breakdown = estimate.cost_breakdown
    lines.extend([
        f"",
        f"COST BREAKDOWN:",
        f"  Material: ${breakdown.material_cost:.2f}",
        f"  Machine time: ${breakdown.machine_time_cost:.2f}",
        f"  Energy: ${breakdown.energy_cost:.2f}",
    ])

    if breakdown.overhead_cost > 0:
        lines.append(f"  Overhead: ${breakdown.overhead_cost:.2f}")

    lines.extend([
        f"  ───────────────",
        f"  TOTAL: ${breakdown.total_cost:.2f}",
    ])

    return "\n".join(lines)


# Testing
if __name__ == "__main__":
    print("Cost Estimator Module Test")
    print("=" * 60)

    estimator = CostEstimator()

    # Test print estimation
    print("\n--- 3D Print Estimate ---\n")

    # A typical model: ~50cm³ volume
    print_estimate = estimator.estimate_print(
        volume_mm3=50000,  # 50 cm³
        material="pla",
        layer_height_mm=0.2,
        infill_percent=20,
        model_name="Phone Stand",
    )

    print(format_estimate(print_estimate))

    # Test multi-color print
    print("\n\n--- Multi-Color Print Estimate ---\n")

    multicolor_estimate = estimator.estimate_print(
        volume_mm3=30000,  # 30 cm³
        material="pla",
        model_name="Logo Badge",
        color_volumes={
            "White": 20000,
            "Red": 8000,
            "Blue": 2000,
        },
    )

    print(format_estimate(multicolor_estimate))

    # Test laser cutting
    print("\n\n--- Laser Cut Estimate ---\n")

    laser_estimate = estimator.estimate_laser_cut(
        path_length_mm=2000,  # 2 meters of cuts
        travel_length_mm=500,  # 0.5 meters of travel
        area_mm2=40000,  # 20x20cm sheet
        path_count=25,
        material="plywood_3mm",
        job_name="Custom Coasters",
    )

    print(format_estimate(laser_estimate))

    # Test laser engraving
    print("\n\n--- Laser Engrave Estimate ---\n")

    engrave_estimate = estimator.estimate_laser_engrave(
        area_mm2=10000,  # 10x10cm area
        fill_percent=50,
        material="plywood_3mm",
        job_name="Logo Engraving",
    )

    print(format_estimate(engrave_estimate))

    print("\n" + "=" * 60)
    print("All estimates completed successfully!")
