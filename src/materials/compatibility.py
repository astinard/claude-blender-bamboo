"""Material compatibility checker for multi-material 3D printing.

P4.7: Material Compatibility Warnings

Features:
- Multi-material compatibility check
- Temperature mismatch warnings
- AMS slot recommendations
- Support material suggestions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from src.materials.material_db import Material, MaterialType, get_material, MATERIAL_DATABASE


class CompatibilityLevel(str, Enum):
    """Level of compatibility between materials."""
    EXCELLENT = "excellent"  # Perfect match, no issues
    GOOD = "good"  # Compatible with minor adjustments
    FAIR = "fair"  # Will work but may have issues
    POOR = "poor"  # Not recommended, high risk of failure
    INCOMPATIBLE = "incompatible"  # Do not use together


@dataclass
class CompatibilityIssue:
    """A specific compatibility issue between materials."""
    severity: CompatibilityLevel
    message: str
    suggestion: Optional[str] = None


@dataclass
class CompatibilityResult:
    """Result of compatibility check between materials."""
    material_a: str
    material_b: str
    level: CompatibilityLevel
    issues: List[CompatibilityIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def is_compatible(self) -> bool:
        """Check if materials can be used together."""
        return self.level not in [CompatibilityLevel.POOR, CompatibilityLevel.INCOMPATIBLE]

    def __str__(self) -> str:
        lines = [f"Compatibility: {self.material_a} + {self.material_b} = {self.level.value}"]
        for issue in self.issues:
            lines.append(f"  [{issue.severity.value}] {issue.message}")
            if issue.suggestion:
                lines.append(f"    Suggestion: {issue.suggestion}")
        for warning in self.warnings:
            lines.append(f"  Warning: {warning}")
        for rec in self.recommendations:
            lines.append(f"  Recommendation: {rec}")
        return "\n".join(lines)


@dataclass
class AMSSlotRecommendation:
    """Recommendation for AMS slot assignment."""
    slot: int
    material: str
    reason: str


@dataclass
class MultiMaterialAnalysis:
    """Analysis of multiple materials for a print job."""
    materials: List[str]
    overall_compatibility: CompatibilityLevel
    pairwise_results: List[CompatibilityResult]
    ams_recommendations: List[AMSSlotRecommendation]
    warnings: List[str]
    print_settings: Dict[str, any]


# Temperature tolerance for compatibility (degrees Celsius)
TEMP_TOLERANCE_EXCELLENT = 15
TEMP_TOLERANCE_GOOD = 25
TEMP_TOLERANCE_FAIR = 40


def check_temperature_compatibility(
    mat_a: Material, mat_b: Material
) -> Tuple[CompatibilityLevel, List[CompatibilityIssue]]:
    """Check if two materials have compatible temperature requirements."""
    issues = []

    # Check nozzle temperature overlap
    nozzle_overlap = min(mat_a.properties.nozzle_temp_max, mat_b.properties.nozzle_temp_max) - \
                     max(mat_a.properties.nozzle_temp_min, mat_b.properties.nozzle_temp_min)

    if nozzle_overlap < 0:
        issues.append(CompatibilityIssue(
            severity=CompatibilityLevel.INCOMPATIBLE,
            message=f"No nozzle temperature overlap: {mat_a.name} ({mat_a.properties.nozzle_temp_min}-{mat_a.properties.nozzle_temp_max}°C) vs {mat_b.name} ({mat_b.properties.nozzle_temp_min}-{mat_b.properties.nozzle_temp_max}°C)",
            suggestion="Use different materials with overlapping temperature ranges"
        ))
        return CompatibilityLevel.INCOMPATIBLE, issues

    # Check bed temperature overlap
    bed_overlap = min(mat_a.properties.bed_temp_max, mat_b.properties.bed_temp_max) - \
                  max(mat_a.properties.bed_temp_min, mat_b.properties.bed_temp_min)

    if bed_overlap < 0:
        issues.append(CompatibilityIssue(
            severity=CompatibilityLevel.POOR,
            message=f"No bed temperature overlap: {mat_a.name} ({mat_a.properties.bed_temp_min}-{mat_a.properties.bed_temp_max}°C) vs {mat_b.name} ({mat_b.properties.bed_temp_min}-{mat_b.properties.bed_temp_max}°C)",
            suggestion="Bed temperature compromise may cause adhesion issues with one material"
        ))
        return CompatibilityLevel.POOR, issues

    # Check how much compromise is needed
    temp_diff = abs(mat_a.properties.nozzle_temp_default - mat_b.properties.nozzle_temp_default)

    if temp_diff <= TEMP_TOLERANCE_EXCELLENT:
        return CompatibilityLevel.EXCELLENT, issues
    elif temp_diff <= TEMP_TOLERANCE_GOOD:
        issues.append(CompatibilityIssue(
            severity=CompatibilityLevel.GOOD,
            message=f"Temperature difference of {temp_diff}°C between {mat_a.name} and {mat_b.name}",
            suggestion=f"Use intermediate temperature: {(mat_a.properties.nozzle_temp_default + mat_b.properties.nozzle_temp_default) // 2}°C"
        ))
        return CompatibilityLevel.GOOD, issues
    elif temp_diff <= TEMP_TOLERANCE_FAIR:
        issues.append(CompatibilityIssue(
            severity=CompatibilityLevel.FAIR,
            message=f"Significant temperature difference of {temp_diff}°C between {mat_a.name} and {mat_b.name}",
            suggestion="Consider using temperature tower test first"
        ))
        return CompatibilityLevel.FAIR, issues
    else:
        issues.append(CompatibilityIssue(
            severity=CompatibilityLevel.POOR,
            message=f"Large temperature difference of {temp_diff}°C may cause quality issues",
            suggestion="One material will be printed at sub-optimal temperature"
        ))
        return CompatibilityLevel.POOR, issues


def check_adhesion_compatibility(
    mat_a: Material, mat_b: Material
) -> Tuple[CompatibilityLevel, List[CompatibilityIssue]]:
    """Check if two materials will adhere to each other."""
    issues = []

    # Known incompatible combinations
    incompatible_pairs = [
        (MaterialType.TPU, MaterialType.ABS),
        (MaterialType.TPU, MaterialType.PC),
        (MaterialType.PLA, MaterialType.ABS),
        (MaterialType.PLA, MaterialType.PC),
        (MaterialType.PETG, MaterialType.ABS),
    ]

    # Check for known incompatible pairs
    pair = (mat_a.material_type, mat_b.material_type)
    reverse_pair = (mat_b.material_type, mat_a.material_type)

    if pair in incompatible_pairs or reverse_pair in incompatible_pairs:
        issues.append(CompatibilityIssue(
            severity=CompatibilityLevel.POOR,
            message=f"{mat_a.name} and {mat_b.name} have poor inter-layer adhesion",
            suggestion="Use a compatible interface material or redesign for mechanical joining"
        ))
        return CompatibilityLevel.POOR, issues

    # Check same-family compatibility (excellent)
    if mat_a.material_type == mat_b.material_type:
        return CompatibilityLevel.EXCELLENT, issues

    # Known good combinations
    good_pairs = [
        (MaterialType.PLA, MaterialType.PVA),
        (MaterialType.PLA, MaterialType.WOOD),
        (MaterialType.PLA, MaterialType.SILK),
        (MaterialType.PETG, MaterialType.PVA),
        (MaterialType.ABS, MaterialType.HIPS),
        (MaterialType.ASA, MaterialType.HIPS),
    ]

    if pair in good_pairs or reverse_pair in good_pairs:
        return CompatibilityLevel.GOOD, issues

    # Default: fair compatibility
    issues.append(CompatibilityIssue(
        severity=CompatibilityLevel.FAIR,
        message=f"Adhesion between {mat_a.name} and {mat_b.name} may vary",
        suggestion="Test with a small sample piece first"
    ))
    return CompatibilityLevel.FAIR, issues


def check_enclosure_requirements(
    mat_a: Material, mat_b: Material
) -> Tuple[CompatibilityLevel, List[CompatibilityIssue]]:
    """Check if enclosure requirements are compatible."""
    issues = []

    if mat_a.properties.requires_enclosure != mat_b.properties.requires_enclosure:
        if mat_a.properties.requires_enclosure:
            needs_enclosure = mat_a.name
            no_enclosure = mat_b.name
        else:
            needs_enclosure = mat_b.name
            no_enclosure = mat_a.name

        issues.append(CompatibilityIssue(
            severity=CompatibilityLevel.FAIR,
            message=f"{needs_enclosure} requires enclosure, but {no_enclosure} does not",
            suggestion=f"Use enclosure for best results with {needs_enclosure}, monitor {no_enclosure} for overheating"
        ))
        return CompatibilityLevel.FAIR, issues

    return CompatibilityLevel.EXCELLENT, issues


def check_compatibility(material_a: str, material_b: str) -> CompatibilityResult:
    """
    Check compatibility between two materials.

    Args:
        material_a: Name of first material
        material_b: Name of second material

    Returns:
        CompatibilityResult with detailed analysis
    """
    mat_a = get_material(material_a)
    mat_b = get_material(material_b)

    if mat_a is None:
        return CompatibilityResult(
            material_a=material_a,
            material_b=material_b,
            level=CompatibilityLevel.INCOMPATIBLE,
            issues=[CompatibilityIssue(
                severity=CompatibilityLevel.INCOMPATIBLE,
                message=f"Unknown material: {material_a}",
            )],
        )

    if mat_b is None:
        return CompatibilityResult(
            material_a=material_a,
            material_b=material_b,
            level=CompatibilityLevel.INCOMPATIBLE,
            issues=[CompatibilityIssue(
                severity=CompatibilityLevel.INCOMPATIBLE,
                message=f"Unknown material: {material_b}",
            )],
        )

    # Same material is always compatible
    if material_a.lower() == material_b.lower():
        return CompatibilityResult(
            material_a=material_a,
            material_b=material_b,
            level=CompatibilityLevel.EXCELLENT,
        )

    all_issues = []
    levels = []

    # Check temperature compatibility
    temp_level, temp_issues = check_temperature_compatibility(mat_a, mat_b)
    levels.append(temp_level)
    all_issues.extend(temp_issues)

    # Check adhesion compatibility
    adhesion_level, adhesion_issues = check_adhesion_compatibility(mat_a, mat_b)
    levels.append(adhesion_level)
    all_issues.extend(adhesion_issues)

    # Check enclosure requirements
    enclosure_level, enclosure_issues = check_enclosure_requirements(mat_a, mat_b)
    levels.append(enclosure_level)
    all_issues.extend(enclosure_issues)

    # Overall level is the worst of all checks
    level_priority = [
        CompatibilityLevel.INCOMPATIBLE,
        CompatibilityLevel.POOR,
        CompatibilityLevel.FAIR,
        CompatibilityLevel.GOOD,
        CompatibilityLevel.EXCELLENT,
    ]
    overall_level = min(levels, key=lambda x: level_priority.index(x))

    # Generate recommendations
    recommendations = []
    warnings = []

    # Temperature recommendations
    if temp_level in [CompatibilityLevel.GOOD, CompatibilityLevel.FAIR]:
        shared_temp = (mat_a.properties.nozzle_temp_default + mat_b.properties.nozzle_temp_default) // 2
        recommendations.append(f"Use nozzle temperature around {shared_temp}°C for best results")

    # Bed temperature
    if mat_a.properties.bed_temp_default != mat_b.properties.bed_temp_default:
        shared_bed = max(mat_a.properties.bed_temp_default, mat_b.properties.bed_temp_default)
        recommendations.append(f"Use bed temperature {shared_bed}°C (higher of the two)")

    # Enclosure warning
    if mat_a.properties.requires_enclosure or mat_b.properties.requires_enclosure:
        warnings.append("Enclosure recommended for this material combination")

    # Fume warning
    if mat_a.properties.toxic_fumes or mat_b.properties.toxic_fumes:
        warnings.append("Ensure proper ventilation - toxic fumes may be produced")

    # Abrasive warning
    if mat_a.properties.abrasive or mat_b.properties.abrasive:
        warnings.append("Use hardened steel nozzle - material is abrasive")

    # Hygroscopic warning
    if mat_a.properties.hygroscopic or mat_b.properties.hygroscopic:
        warnings.append("Store materials in dry box - hygroscopic materials present")

    return CompatibilityResult(
        material_a=material_a,
        material_b=material_b,
        level=overall_level,
        issues=all_issues,
        warnings=warnings,
        recommendations=recommendations,
    )


def check_multi_material_compatibility(materials: List[str]) -> MultiMaterialAnalysis:
    """
    Check compatibility of multiple materials for a single print.

    Args:
        materials: List of material names to check

    Returns:
        MultiMaterialAnalysis with comprehensive compatibility info
    """
    if len(materials) < 2:
        return MultiMaterialAnalysis(
            materials=materials,
            overall_compatibility=CompatibilityLevel.EXCELLENT,
            pairwise_results=[],
            ams_recommendations=[],
            warnings=["Single material print - no compatibility issues"],
            print_settings={},
        )

    # Check all pairs
    pairwise_results = []
    for i, mat_a in enumerate(materials):
        for mat_b in materials[i + 1:]:
            result = check_compatibility(mat_a, mat_b)
            pairwise_results.append(result)

    # Overall level is worst of all pairs
    level_priority = [
        CompatibilityLevel.INCOMPATIBLE,
        CompatibilityLevel.POOR,
        CompatibilityLevel.FAIR,
        CompatibilityLevel.GOOD,
        CompatibilityLevel.EXCELLENT,
    ]
    overall = min(
        [r.level for r in pairwise_results],
        key=lambda x: level_priority.index(x)
    )

    # Collect all warnings
    warnings = []
    for result in pairwise_results:
        warnings.extend(result.warnings)
    warnings = list(set(warnings))  # Deduplicate

    # Generate AMS slot recommendations
    ams_recommendations = get_ams_recommendations(materials)

    # Calculate optimal print settings
    mat_objects = [get_material(m) for m in materials if get_material(m)]
    print_settings = {}

    if mat_objects:
        # Nozzle temp: use range that works for all
        min_nozzle = max(m.properties.nozzle_temp_min for m in mat_objects)
        max_nozzle = min(m.properties.nozzle_temp_max for m in mat_objects)
        if min_nozzle <= max_nozzle:
            print_settings["nozzle_temp"] = (min_nozzle + max_nozzle) // 2
        else:
            print_settings["nozzle_temp"] = None
            warnings.append("No common nozzle temperature range - quality issues expected")

        # Bed temp: use highest required
        print_settings["bed_temp"] = max(m.properties.bed_temp_default for m in mat_objects)

        # Enclosure
        print_settings["enclosure_required"] = any(m.properties.requires_enclosure for m in mat_objects)

        # Speed: use slowest modifier
        print_settings["speed_modifier"] = min(m.properties.speed_modifier for m in mat_objects)

    return MultiMaterialAnalysis(
        materials=materials,
        overall_compatibility=overall,
        pairwise_results=pairwise_results,
        ams_recommendations=ams_recommendations,
        warnings=warnings,
        print_settings=print_settings,
    )


def get_ams_recommendations(materials: List[str]) -> List[AMSSlotRecommendation]:
    """
    Generate AMS slot assignment recommendations.

    Strategy:
    - Put main material (first) in slot 1
    - Put support materials last
    - Group similar temperature materials together
    - Consider spool loading order for efficiency
    """
    recommendations = []

    # Get material objects
    mat_objects = [(name, get_material(name)) for name in materials]

    # Separate main materials from supports
    supports = []
    main_materials = []

    for name, mat in mat_objects:
        if mat and mat.material_type in [MaterialType.PVA, MaterialType.HIPS]:
            supports.append((name, mat))
        else:
            main_materials.append((name, mat))

    # Assign slots
    slot = 1

    # Main materials first, sorted by temperature (hot to cold for better purging)
    main_materials.sort(
        key=lambda x: x[1].properties.nozzle_temp_default if x[1] else 0,
        reverse=True
    )

    for name, mat in main_materials:
        if mat:
            recommendations.append(AMSSlotRecommendation(
                slot=slot,
                material=name,
                reason=f"Main material, {mat.properties.nozzle_temp_default}°C nozzle temp"
            ))
        else:
            recommendations.append(AMSSlotRecommendation(
                slot=slot,
                material=name,
                reason="Unknown material"
            ))
        slot += 1

    # Support materials last
    for name, mat in supports:
        recommendations.append(AMSSlotRecommendation(
            slot=slot,
            material=name,
            reason="Support material - placed last for easy removal"
        ))
        slot += 1

    return recommendations


def suggest_support_material(main_material: str) -> Optional[str]:
    """Suggest the best support material for a given main material."""
    mat = get_material(main_material)
    if mat is None:
        return None

    if mat.properties.compatible_supports:
        # Prefer PVA if available (water soluble)
        if "pva" in mat.properties.compatible_supports:
            return "pva"
        return mat.properties.compatible_supports[0]

    return None
