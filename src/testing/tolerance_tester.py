"""Tolerance testing for 3D printed parts.

Validates dimensional accuracy and fit requirements.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("testing.tolerance_tester")


class ToleranceLevel(str, Enum):
    """Standard tolerance levels for 3D printing."""
    COARSE = "coarse"  # ±0.5mm - Decorative parts
    STANDARD = "standard"  # ±0.2mm - General use
    FINE = "fine"  # ±0.1mm - Functional parts
    PRECISION = "precision"  # ±0.05mm - High precision


class FitType(str, Enum):
    """Types of fits for mating parts."""
    CLEARANCE = "clearance"  # Parts move freely
    TRANSITION = "transition"  # Slight interference
    INTERFERENCE = "interference"  # Press fit


@dataclass
class DimensionCheck:
    """A single dimension check result."""
    name: str
    nominal: float  # Design dimension
    actual: float  # Measured dimension
    tolerance: float  # Allowed deviation
    deviation: float = 0.0
    passed: bool = True
    unit: str = "mm"

    def __post_init__(self):
        """Calculate deviation and pass/fail."""
        self.deviation = self.actual - self.nominal
        self.passed = abs(self.deviation) <= self.tolerance

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "nominal": self.nominal,
            "actual": self.actual,
            "tolerance": self.tolerance,
            "deviation": round(self.deviation, 4),
            "passed": self.passed,
            "unit": self.unit,
        }


@dataclass
class ToleranceConfig:
    """Configuration for tolerance testing."""
    tolerance_level: ToleranceLevel = ToleranceLevel.STANDARD
    custom_tolerance: Optional[float] = None  # Override level
    material: str = "pla"
    compensate_shrinkage: bool = True
    include_statistical: bool = True

    # Material shrinkage factors (percentage)
    shrinkage_factors: Dict[str, float] = field(default_factory=lambda: {
        "pla": 0.3,
        "petg": 0.4,
        "abs": 0.8,
        "tpu": 0.2,
    })

    def get_tolerance(self) -> float:
        """Get the tolerance value in mm."""
        if self.custom_tolerance is not None:
            return self.custom_tolerance

        tolerances = {
            ToleranceLevel.COARSE: 0.5,
            ToleranceLevel.STANDARD: 0.2,
            ToleranceLevel.FINE: 0.1,
            ToleranceLevel.PRECISION: 0.05,
        }
        return tolerances[self.tolerance_level]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "tolerance_level": self.tolerance_level.value,
            "tolerance_mm": self.get_tolerance(),
            "custom_tolerance": self.custom_tolerance,
            "material": self.material,
            "compensate_shrinkage": self.compensate_shrinkage,
        }


@dataclass
class ToleranceResult:
    """Result of tolerance testing."""
    success: bool
    all_passed: bool = False
    checks: List[DimensionCheck] = field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    tolerance_used: float = 0.0
    statistics: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    tested_at: str = ""
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "all_passed": self.all_passed,
            "checks": [c.to_dict() for c in self.checks],
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "tolerance_used": self.tolerance_used,
            "statistics": self.statistics,
            "recommendations": self.recommendations,
            "tested_at": self.tested_at,
            "error_message": self.error_message,
        }


@dataclass
class FitCheck:
    """Check for mating parts fit."""
    hole_diameter: float
    shaft_diameter: float
    fit_type: FitType
    clearance: float = 0.0
    recommendation: str = ""

    def __post_init__(self):
        """Calculate clearance and recommendation."""
        self.clearance = self.hole_diameter - self.shaft_diameter

        # Standard fit recommendations
        if self.fit_type == FitType.CLEARANCE:
            if self.clearance < 0.2:
                self.recommendation = "Increase clearance (recommend 0.2-0.4mm for clearance fit)"
            elif self.clearance > 0.6:
                self.recommendation = "Clearance may be excessive (> 0.6mm)"
            else:
                self.recommendation = "Good clearance fit"
        elif self.fit_type == FitType.TRANSITION:
            if abs(self.clearance) > 0.1:
                self.recommendation = "Adjust for tighter transition fit (±0.1mm)"
            else:
                self.recommendation = "Good transition fit"
        else:  # INTERFERENCE
            if self.clearance > 0:
                self.recommendation = "Shaft should be larger than hole for press fit"
            elif self.clearance < -0.3:
                self.recommendation = "Interference may be too tight (< -0.3mm)"
            else:
                self.recommendation = "Good interference fit"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hole_diameter": self.hole_diameter,
            "shaft_diameter": self.shaft_diameter,
            "fit_type": self.fit_type.value,
            "clearance": round(self.clearance, 3),
            "recommendation": self.recommendation,
        }


class ToleranceTester:
    """
    Tolerance tester for 3D printed parts.

    Validates dimensional accuracy against specified tolerances.
    """

    def __init__(self, config: Optional[ToleranceConfig] = None):
        """
        Initialize tolerance tester.

        Args:
            config: Tolerance configuration
        """
        self.config = config or ToleranceConfig()

    def test_dimensions(
        self,
        measurements: List[Tuple[str, float, float]],
    ) -> ToleranceResult:
        """
        Test multiple dimensions against tolerance.

        Args:
            measurements: List of (name, nominal, actual) tuples

        Returns:
            Tolerance test result
        """
        if not measurements:
            return ToleranceResult(
                success=False,
                error_message="No measurements provided",
            )

        try:
            tolerance = self.config.get_tolerance()
            checks = []

            for name, nominal, actual in measurements:
                # Apply shrinkage compensation if enabled
                if self.config.compensate_shrinkage:
                    shrinkage = self.config.shrinkage_factors.get(
                        self.config.material.lower(), 0.3
                    )
                    expected = nominal * (1 - shrinkage / 100)
                else:
                    expected = nominal

                check = DimensionCheck(
                    name=name,
                    nominal=expected,
                    actual=actual,
                    tolerance=tolerance,
                )
                checks.append(check)

            # Calculate statistics
            deviations = [c.deviation for c in checks]
            statistics = self._calculate_statistics(deviations)

            # Generate recommendations
            recommendations = self._generate_recommendations(checks, statistics)

            passed = sum(1 for c in checks if c.passed)
            failed = len(checks) - passed

            return ToleranceResult(
                success=True,
                all_passed=failed == 0,
                checks=checks,
                passed_count=passed,
                failed_count=failed,
                tolerance_used=tolerance,
                statistics=statistics,
                recommendations=recommendations,
                tested_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f"Tolerance test error: {e}")
            return ToleranceResult(
                success=False,
                error_message=str(e),
            )

    def _calculate_statistics(self, deviations: List[float]) -> Dict[str, float]:
        """Calculate statistical measures."""
        if not deviations:
            return {}

        n = len(deviations)
        mean = sum(deviations) / n

        # Variance and std dev
        variance = sum((d - mean) ** 2 for d in deviations) / n
        std_dev = math.sqrt(variance)

        # Range
        min_dev = min(deviations)
        max_dev = max(deviations)

        return {
            "mean_deviation": round(mean, 4),
            "std_deviation": round(std_dev, 4),
            "min_deviation": round(min_dev, 4),
            "max_deviation": round(max_dev, 4),
            "range": round(max_dev - min_dev, 4),
        }

    def _generate_recommendations(
        self,
        checks: List[DimensionCheck],
        statistics: Dict[str, float],
    ) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []

        # Check for systematic bias
        mean_dev = statistics.get("mean_deviation", 0)
        if abs(mean_dev) > 0.1:
            if mean_dev > 0:
                recommendations.append(
                    f"Parts are consistently oversized by ~{mean_dev:.2f}mm. "
                    "Consider reducing flow rate or horizontal expansion."
                )
            else:
                recommendations.append(
                    f"Parts are consistently undersized by ~{abs(mean_dev):.2f}mm. "
                    "Consider increasing flow rate or adjusting shrinkage compensation."
                )

        # Check for high variability
        std_dev = statistics.get("std_deviation", 0)
        if std_dev > 0.15:
            recommendations.append(
                f"High dimensional variability (σ={std_dev:.3f}mm). "
                "Check belt tension, filament quality, and bed adhesion."
            )

        # Specific dimension failures
        failed = [c for c in checks if not c.passed]
        if failed:
            for check in failed[:3]:  # Limit to first 3
                recommendations.append(
                    f"'{check.name}' is out of tolerance by {abs(check.deviation):.3f}mm"
                )

        return recommendations

    def check_fit(
        self,
        hole_diameter: float,
        shaft_diameter: float,
        fit_type: FitType = FitType.CLEARANCE,
    ) -> FitCheck:
        """
        Check fit between mating parts.

        Args:
            hole_diameter: Measured hole diameter
            shaft_diameter: Measured shaft diameter
            fit_type: Desired fit type

        Returns:
            Fit check result
        """
        return FitCheck(
            hole_diameter=hole_diameter,
            shaft_diameter=shaft_diameter,
            fit_type=fit_type,
        )

    def calculate_shrinkage(
        self,
        nominal: float,
        actual: float,
    ) -> Dict[str, float]:
        """
        Calculate actual shrinkage from measurements.

        Args:
            nominal: Design dimension
            actual: Measured dimension

        Returns:
            Shrinkage analysis
        """
        shrinkage_mm = nominal - actual
        shrinkage_percent = (shrinkage_mm / nominal) * 100 if nominal > 0 else 0

        # Expected shrinkage
        expected = self.config.shrinkage_factors.get(
            self.config.material.lower(), 0.3
        )

        return {
            "shrinkage_mm": round(shrinkage_mm, 3),
            "shrinkage_percent": round(shrinkage_percent, 2),
            "expected_percent": expected,
            "difference_from_expected": round(shrinkage_percent - expected, 2),
        }

    def generate_test_print(self) -> Dict[str, any]:
        """Generate specifications for a tolerance test print."""
        tolerance = self.config.get_tolerance()

        return {
            "name": "Tolerance Test Print",
            "description": f"Test print for {self.config.tolerance_level.value} tolerance ({tolerance}mm)",
            "features": [
                {"type": "cube", "size": 20.0, "label": "20mm reference cube"},
                {"type": "hole", "diameter": 5.0, "label": "5mm test hole"},
                {"type": "hole", "diameter": 8.0, "label": "8mm test hole"},
                {"type": "post", "diameter": 5.0, "label": "5mm test post"},
                {"type": "post", "diameter": 8.0, "label": "8mm test post"},
                {"type": "slot", "width": 3.0, "label": "3mm slot"},
            ],
            "expected_tolerance": tolerance,
            "print_settings": {
                "layer_height": 0.2 if tolerance > 0.15 else 0.1,
                "infill": 20,
                "walls": 3,
            },
        }

    def export_report(self, result: ToleranceResult) -> str:
        """Export tolerance test report as markdown."""
        lines = [
            "# Tolerance Test Report",
            "",
            f"*Tested: {result.tested_at}*",
            "",
            f"**Tolerance Level:** {self.config.tolerance_level.value}",
            f"**Tolerance:** ±{result.tolerance_used}mm",
            f"**Material:** {self.config.material.upper()}",
            "",
            "## Summary",
            "",
            f"- **Total Checks:** {result.passed_count + result.failed_count}",
            f"- **Passed:** {result.passed_count}",
            f"- **Failed:** {result.failed_count}",
            f"- **Result:** {'✅ PASS' if result.all_passed else '❌ FAIL'}",
            "",
        ]

        # Dimension checks table
        lines.extend([
            "## Dimension Checks",
            "",
            "| Dimension | Nominal | Actual | Deviation | Status |",
            "|-----------|---------|--------|-----------|--------|",
        ])
        for check in result.checks:
            status = "✅" if check.passed else "❌"
            lines.append(
                f"| {check.name} | {check.nominal:.3f} | {check.actual:.3f} | "
                f"{check.deviation:+.3f} | {status} |"
            )
        lines.append("")

        # Statistics
        if result.statistics:
            lines.extend([
                "## Statistics",
                "",
                f"- **Mean Deviation:** {result.statistics.get('mean_deviation', 0):.4f}mm",
                f"- **Std Deviation:** {result.statistics.get('std_deviation', 0):.4f}mm",
                f"- **Range:** {result.statistics.get('range', 0):.4f}mm",
                "",
            ])

        # Recommendations
        if result.recommendations:
            lines.extend([
                "## Recommendations",
                "",
            ])
            for rec in result.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)


# Convenience functions
def create_tester(
    tolerance_level: str = "standard",
    material: str = "pla",
) -> ToleranceTester:
    """Create a tolerance tester with specified settings."""
    config = ToleranceConfig(
        tolerance_level=ToleranceLevel(tolerance_level),
        material=material,
    )
    return ToleranceTester(config=config)


def check_tolerance(
    nominal: float,
    actual: float,
    tolerance: float = 0.2,
    name: str = "dimension",
) -> DimensionCheck:
    """
    Quick tolerance check for a single dimension.

    Args:
        nominal: Design dimension
        actual: Measured dimension
        tolerance: Allowed deviation
        name: Dimension name

    Returns:
        Dimension check result
    """
    return DimensionCheck(
        name=name,
        nominal=nominal,
        actual=actual,
        tolerance=tolerance,
    )
