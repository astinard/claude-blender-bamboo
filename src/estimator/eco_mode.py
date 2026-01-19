"""Eco mode optimization for environmentally-friendly printing.

Minimizes material waste, energy consumption, and environmental impact.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from src.utils import get_logger
from src.estimator.cost_optimizer import PrintSettings, CostConfig

logger = get_logger("estimator.eco_mode")


class EcoLevel(str, Enum):
    """Eco optimization levels."""
    STANDARD = "standard"  # Balanced approach
    ECO = "eco"  # Moderate savings
    MAX_ECO = "max_eco"  # Maximum environmental focus


class MaterialType(str, Enum):
    """Material sustainability ratings."""
    PLA = "pla"  # Biodegradable (corn starch)
    PETG = "petg"  # Recyclable
    ABS = "abs"  # Not easily recyclable
    TPU = "tpu"  # Not easily recyclable


@dataclass
class MaterialSustainability:
    """Sustainability info for a material."""
    material: MaterialType
    biodegradable: bool
    recyclable: bool
    sustainability_score: int  # 0-100
    notes: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "material": self.material.value,
            "biodegradable": self.biodegradable,
            "recyclable": self.recyclable,
            "sustainability_score": self.sustainability_score,
            "notes": self.notes,
        }


@dataclass
class EcoConfig:
    """Configuration for eco mode optimization."""
    eco_level: EcoLevel = EcoLevel.ECO
    prioritize_biodegradable: bool = True
    minimize_supports: bool = True
    optimize_orientation: bool = True
    reduce_infill: bool = True
    use_recycled_material: bool = False
    carbon_offset_enabled: bool = False

    # Regional electricity carbon intensity (kg CO2/kWh)
    carbon_intensity_kwh: float = 0.4  # US average

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "eco_level": self.eco_level.value,
            "prioritize_biodegradable": self.prioritize_biodegradable,
            "minimize_supports": self.minimize_supports,
            "optimize_orientation": self.optimize_orientation,
            "reduce_infill": self.reduce_infill,
            "use_recycled_material": self.use_recycled_material,
            "carbon_offset_enabled": self.carbon_offset_enabled,
            "carbon_intensity_kwh": self.carbon_intensity_kwh,
        }


@dataclass
class EcoMetrics:
    """Environmental impact metrics."""
    material_waste_grams: float = 0.0
    energy_kwh: float = 0.0
    carbon_footprint_kg: float = 0.0
    recyclability_percent: float = 0.0
    sustainability_score: int = 0  # 0-100

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "material_waste_grams": self.material_waste_grams,
            "energy_kwh": self.energy_kwh,
            "carbon_footprint_kg": self.carbon_footprint_kg,
            "recyclability_percent": self.recyclability_percent,
            "sustainability_score": self.sustainability_score,
        }


@dataclass
class EcoOptimizationResult:
    """Result of eco mode optimization."""
    success: bool
    original_metrics: Optional[EcoMetrics] = None
    optimized_metrics: Optional[EcoMetrics] = None
    savings: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    optimized_settings: Optional[PrintSettings] = None
    suggested_material: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "original_metrics": self.original_metrics.to_dict() if self.original_metrics else None,
            "optimized_metrics": self.optimized_metrics.to_dict() if self.optimized_metrics else None,
            "savings": self.savings,
            "recommendations": self.recommendations,
            "optimized_settings": self.optimized_settings.to_dict() if self.optimized_settings else None,
            "suggested_material": self.suggested_material,
            "error_message": self.error_message,
        }


class EcoOptimizer:
    """
    Eco mode optimizer for sustainable 3D printing.

    Analyzes and optimizes prints for minimal environmental impact.
    """

    # Material sustainability data
    MATERIAL_INFO = {
        MaterialType.PLA: MaterialSustainability(
            material=MaterialType.PLA,
            biodegradable=True,
            recyclable=True,
            sustainability_score=85,
            notes="Made from renewable corn starch, industrially compostable",
        ),
        MaterialType.PETG: MaterialSustainability(
            material=MaterialType.PETG,
            biodegradable=False,
            recyclable=True,
            sustainability_score=60,
            notes="Recyclable with #1 plastics, durable for long-term use",
        ),
        MaterialType.ABS: MaterialSustainability(
            material=MaterialType.ABS,
            biodegradable=False,
            recyclable=False,
            sustainability_score=30,
            notes="Petroleum-based, not easily recycled, releases fumes",
        ),
        MaterialType.TPU: MaterialSustainability(
            material=MaterialType.TPU,
            biodegradable=False,
            recyclable=False,
            sustainability_score=35,
            notes="Not recyclable, but durable and flexible",
        ),
    }

    def __init__(self, config: Optional[EcoConfig] = None):
        """
        Initialize eco optimizer.

        Args:
            config: Eco configuration
        """
        self.config = config or EcoConfig()

    def calculate_metrics(
        self,
        volume_cm3: float,
        settings: PrintSettings,
        material: str = "pla",
        printer_watts: float = 150.0,
    ) -> EcoMetrics:
        """
        Calculate environmental metrics for a print.

        Args:
            volume_cm3: Part volume in cm³
            settings: Print settings
            material: Material type
            printer_watts: Printer power consumption

        Returns:
            Environmental impact metrics
        """
        # Material density (g/cm³)
        densities = {"pla": 1.24, "petg": 1.27, "abs": 1.04, "tpu": 1.21}
        density = densities.get(material.lower(), 1.24)

        # Calculate material used
        infill_factor = settings.infill_percent / 100
        shell_factor = 0.3  # Approximate shell proportion
        material_volume = volume_cm3 * (shell_factor + (1 - shell_factor) * infill_factor)

        if settings.supports:
            material_volume *= (1 + settings.support_density / 100 * 0.2)

        material_grams = material_volume * density

        # Estimate waste (supports, failed prints, etc.)
        waste_factor = 0.15 if settings.supports else 0.05
        waste_grams = material_grams * waste_factor

        # Calculate print time (hours)
        base_speed = 40  # mm³/s average
        layer_factor = 0.2 / settings.layer_height
        print_time_hours = (volume_cm3 * 1000) / base_speed / 3600 * layer_factor

        # Energy consumption
        energy_kwh = print_time_hours * (printer_watts / 1000)

        # Carbon footprint
        carbon_kg = energy_kwh * self.config.carbon_intensity_kwh

        # Material sustainability
        try:
            mat_type = MaterialType(material.lower())
            mat_info = self.MATERIAL_INFO[mat_type]
            sustainability = mat_info.sustainability_score
            recyclability = 100.0 if mat_info.recyclable else 0.0
        except ValueError:
            sustainability = 50
            recyclability = 0.0

        return EcoMetrics(
            material_waste_grams=round(waste_grams, 1),
            energy_kwh=round(energy_kwh, 3),
            carbon_footprint_kg=round(carbon_kg, 4),
            recyclability_percent=recyclability,
            sustainability_score=sustainability,
        )

    def optimize(
        self,
        volume_cm3: float,
        current_settings: Optional[PrintSettings] = None,
        material: str = "pla",
        printer_watts: float = 150.0,
    ) -> EcoOptimizationResult:
        """
        Optimize print for minimal environmental impact.

        Args:
            volume_cm3: Part volume
            current_settings: Current settings
            material: Current material
            printer_watts: Printer power

        Returns:
            Optimization result with recommendations
        """
        current_settings = current_settings or PrintSettings()

        try:
            # Calculate original metrics
            original_metrics = self.calculate_metrics(
                volume_cm3, current_settings, material, printer_watts
            )

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
            suggested_material = None

            # Apply eco optimizations based on level
            if self.config.eco_level in [EcoLevel.ECO, EcoLevel.MAX_ECO]:
                # Reduce infill
                if self.config.reduce_infill and current_settings.infill_percent > 15:
                    target_infill = 10 if self.config.eco_level == EcoLevel.MAX_ECO else 15
                    optimized_settings.infill_percent = target_infill
                    recommendations.append(
                        f"Reduce infill to {target_infill}% (-{current_settings.infill_percent - target_infill}%)"
                    )

                # Increase layer height for faster, less energy-intensive prints
                if current_settings.layer_height < 0.28:
                    target_layer = 0.32 if self.config.eco_level == EcoLevel.MAX_ECO else 0.28
                    optimized_settings.layer_height = target_layer
                    recommendations.append(
                        f"Increase layer height to {target_layer}mm for faster printing"
                    )

                # Reduce walls if > 2
                if current_settings.wall_count > 2:
                    optimized_settings.wall_count = 2
                    recommendations.append("Reduce wall count to 2")

                # Minimize supports
                if self.config.minimize_supports and current_settings.supports:
                    if current_settings.support_density > 10:
                        optimized_settings.support_density = 10
                        recommendations.append("Reduce support density to 10%")

                # Remove raft (uses extra material)
                if current_settings.raft:
                    optimized_settings.raft = False
                    optimized_settings.brim = True
                    recommendations.append("Replace raft with brim to save material")

            # Material recommendation
            if self.config.prioritize_biodegradable:
                mat_lower = material.lower()
                if mat_lower != "pla":
                    suggested_material = "pla"
                    recommendations.append(
                        "Consider using PLA (biodegradable, lower environmental impact)"
                    )

            # Add general eco tips
            recommendations.extend(self._get_eco_tips(current_settings, material))

            # Calculate optimized metrics
            opt_material = suggested_material or material
            optimized_metrics = self.calculate_metrics(
                volume_cm3, optimized_settings, opt_material, printer_watts
            )

            # Calculate savings
            savings = {
                "material_waste_grams": round(
                    original_metrics.material_waste_grams - optimized_metrics.material_waste_grams, 1
                ),
                "energy_kwh": round(
                    original_metrics.energy_kwh - optimized_metrics.energy_kwh, 3
                ),
                "carbon_kg": round(
                    original_metrics.carbon_footprint_kg - optimized_metrics.carbon_footprint_kg, 4
                ),
            }

            return EcoOptimizationResult(
                success=True,
                original_metrics=original_metrics,
                optimized_metrics=optimized_metrics,
                savings=savings,
                recommendations=recommendations,
                optimized_settings=optimized_settings,
                suggested_material=suggested_material,
            )

        except Exception as e:
            logger.error(f"Eco optimization error: {e}")
            return EcoOptimizationResult(
                success=False,
                error_message=str(e),
            )

    def _get_eco_tips(self, settings: PrintSettings, material: str) -> List[str]:
        """Get general eco-friendly printing tips."""
        tips = []

        # Only return tips relevant to settings
        if settings.supports:
            tips.append("Optimize part orientation to minimize support requirements")

        if material.lower() == "abs":
            tips.append("ABS releases fumes; ensure proper ventilation or switch to PLA")

        return tips

    def get_material_info(self, material: str) -> Optional[MaterialSustainability]:
        """Get sustainability information for a material."""
        try:
            mat_type = MaterialType(material.lower())
            return self.MATERIAL_INFO.get(mat_type)
        except ValueError:
            return None

    def compare_materials(self, volume_cm3: float, settings: PrintSettings) -> Dict[str, EcoMetrics]:
        """Compare environmental impact across materials."""
        comparisons = {}
        for mat_type in MaterialType:
            metrics = self.calculate_metrics(volume_cm3, settings, mat_type.value)
            comparisons[mat_type.value] = metrics
        return comparisons

    def estimate_carbon_offset(
        self,
        metrics: EcoMetrics,
        offset_cost_per_kg: float = 15.0,
    ) -> Dict[str, float]:
        """Calculate carbon offset cost."""
        carbon_kg = metrics.carbon_footprint_kg
        offset_cost = carbon_kg * offset_cost_per_kg

        return {
            "carbon_kg": round(carbon_kg, 4),
            "offset_cost_usd": round(offset_cost, 2),
            "trees_equivalent": round(carbon_kg / 21.77, 4),  # kg CO2 absorbed by tree/year
        }


# Convenience functions
def create_eco_optimizer(
    eco_level: str = "eco",
    carbon_intensity: float = 0.4,
) -> EcoOptimizer:
    """Create an eco optimizer with specified settings."""
    config = EcoConfig(
        eco_level=EcoLevel(eco_level),
        carbon_intensity_kwh=carbon_intensity,
    )
    return EcoOptimizer(config=config)


def calculate_carbon_footprint(
    volume_cm3: float,
    infill: int = 20,
    material: str = "pla",
    print_time_hours: float = 0.0,
    printer_watts: float = 150.0,
) -> Dict[str, float]:
    """
    Quick carbon footprint calculation.

    Args:
        volume_cm3: Part volume
        infill: Infill percentage
        material: Material type
        print_time_hours: Print time (estimated if 0)
        printer_watts: Printer power consumption

    Returns:
        Carbon footprint data
    """
    settings = PrintSettings(infill_percent=infill)
    optimizer = EcoOptimizer()
    metrics = optimizer.calculate_metrics(volume_cm3, settings, material, printer_watts)

    return {
        "carbon_kg": metrics.carbon_footprint_kg,
        "energy_kwh": metrics.energy_kwh,
        "sustainability_score": metrics.sustainability_score,
    }
