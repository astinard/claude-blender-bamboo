"""Print failure prediction based on geometry and material analysis.

P4.2: Print Failure Prediction

Combines geometry analysis with material properties to predict
print success likelihood and recommend mitigations.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.materials.material_db import get_material, Material
from src.monitoring.geometry_analyzer import (
    analyze_geometry,
    GeometryAnalysisResult,
    GeometryIssue,
    IssueSeverity,
)
from src.utils import get_logger

logger = get_logger("monitoring.failure_predictor")


class RiskLevel(str, Enum):
    """Overall risk level for print failure."""
    LOW = "low"  # High confidence of success
    MEDIUM = "medium"  # Some concerns, monitor closely
    HIGH = "high"  # Significant risk, consider modifications
    CRITICAL = "critical"  # Very likely to fail without changes


@dataclass
class RiskFactor:
    """A specific risk factor affecting print success."""
    name: str
    risk_level: RiskLevel
    description: str
    mitigation: Optional[str] = None
    weight: float = 1.0  # How much this affects overall score


@dataclass
class GeometryAnalysis:
    """Summary of geometry-related risks."""
    overhang_risk: RiskLevel
    thin_wall_risk: RiskLevel
    bridge_risk: RiskLevel
    manifold_risk: RiskLevel
    support_required: bool
    estimated_support_volume_mm3: float = 0


@dataclass
class MaterialRisk:
    """Material-specific risk factors."""
    warping_risk: RiskLevel
    adhesion_risk: RiskLevel
    stringing_risk: RiskLevel
    environmental_requirements: List[str]


@dataclass
class FailureRisk:
    """Complete failure risk assessment."""
    overall_risk: RiskLevel
    confidence: float  # 0-1, how confident we are in this assessment
    success_probability: float  # 0-1, estimated chance of successful print

    # Detailed breakdowns
    geometry: GeometryAnalysis
    material_risk: Optional[MaterialRisk]
    risk_factors: List[RiskFactor]

    # Recommendations
    recommendations: List[str]
    warnings: List[str]

    # Raw analysis data
    geometry_result: Optional[GeometryAnalysisResult] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "overall_risk": self.overall_risk.value,
            "confidence": self.confidence,
            "success_probability": self.success_probability,
            "geometry": {
                "overhang_risk": self.geometry.overhang_risk.value,
                "thin_wall_risk": self.geometry.thin_wall_risk.value,
                "bridge_risk": self.geometry.bridge_risk.value,
                "manifold_risk": self.geometry.manifold_risk.value,
                "support_required": self.geometry.support_required,
            },
            "risk_factors": [
                {
                    "name": rf.name,
                    "risk_level": rf.risk_level.value,
                    "description": rf.description,
                    "mitigation": rf.mitigation,
                }
                for rf in self.risk_factors
            ],
            "recommendations": self.recommendations,
            "warnings": self.warnings,
        }


class FailurePredictor:
    """Predicts print failure likelihood and suggests mitigations."""

    # Risk thresholds
    OVERHANG_ANGLE_WARNING = 45  # degrees
    OVERHANG_ANGLE_CRITICAL = 60
    THIN_WALL_WARNING = 0.8  # mm
    THIN_WALL_CRITICAL = 0.4
    BRIDGE_LENGTH_WARNING = 10  # mm
    BRIDGE_LENGTH_CRITICAL = 20

    def __init__(self, material: Optional[str] = None):
        """
        Initialize predictor.

        Args:
            material: Material name for material-specific analysis
        """
        self.material = get_material(material) if material else None

    def analyze(self, file_path: str) -> FailureRisk:
        """
        Analyze a model file for failure risk.

        Args:
            file_path: Path to 3D model file

        Returns:
            FailureRisk with complete analysis
        """
        # Run geometry analysis
        geo_result = analyze_geometry(file_path)

        # Analyze geometry risks
        geometry = self._analyze_geometry_risks(geo_result)

        # Analyze material risks
        material_risk = self._analyze_material_risks() if self.material else None

        # Collect all risk factors
        risk_factors = self._collect_risk_factors(geo_result, geometry, material_risk)

        # Calculate overall risk
        overall_risk, confidence, success_prob = self._calculate_overall_risk(risk_factors)

        # Generate recommendations
        recommendations, warnings = self._generate_recommendations(
            geo_result, geometry, material_risk, risk_factors
        )

        return FailureRisk(
            overall_risk=overall_risk,
            confidence=confidence,
            success_probability=success_prob,
            geometry=geometry,
            material_risk=material_risk,
            risk_factors=risk_factors,
            recommendations=recommendations,
            warnings=warnings,
            geometry_result=geo_result,
        )

    def _analyze_geometry_risks(self, geo: GeometryAnalysisResult) -> GeometryAnalysis:
        """Analyze geometry-specific risks."""

        # Overhang risk
        if not geo.overhangs:
            overhang_risk = RiskLevel.LOW
        else:
            max_angle = max(o.angle for o in geo.overhangs)
            critical_count = sum(1 for o in geo.overhangs if o.severity == IssueSeverity.CRITICAL)

            if max_angle > self.OVERHANG_ANGLE_CRITICAL or critical_count > 5:
                overhang_risk = RiskLevel.CRITICAL
            elif max_angle > self.OVERHANG_ANGLE_WARNING or critical_count > 0:
                overhang_risk = RiskLevel.HIGH
            elif max_angle > 30:
                overhang_risk = RiskLevel.MEDIUM
            else:
                overhang_risk = RiskLevel.LOW

        # Thin wall risk
        if not geo.thin_walls:
            thin_wall_risk = RiskLevel.LOW
        else:
            min_thickness = min(t.thickness_mm for t in geo.thin_walls)
            if min_thickness < self.THIN_WALL_CRITICAL:
                thin_wall_risk = RiskLevel.CRITICAL
            elif min_thickness < self.THIN_WALL_WARNING:
                thin_wall_risk = RiskLevel.HIGH
            else:
                thin_wall_risk = RiskLevel.MEDIUM

        # Bridge risk
        if not geo.bridges:
            bridge_risk = RiskLevel.LOW
        else:
            max_bridge = max(b.length_mm for b in geo.bridges)
            if max_bridge > self.BRIDGE_LENGTH_CRITICAL:
                bridge_risk = RiskLevel.CRITICAL
            elif max_bridge > self.BRIDGE_LENGTH_WARNING:
                bridge_risk = RiskLevel.HIGH
            else:
                bridge_risk = RiskLevel.MEDIUM

        # Manifold risk
        manifold_issues = [i for i in geo.other_issues if i.issue_type in ["non_manifold", "no_volume"]]
        if not manifold_issues:
            manifold_risk = RiskLevel.LOW
        elif any(i.severity == IssueSeverity.CRITICAL for i in manifold_issues):
            manifold_risk = RiskLevel.CRITICAL
        else:
            manifold_risk = RiskLevel.HIGH

        # Estimate support volume (rough approximation)
        support_required = geo.needs_support
        support_volume = 0
        if support_required:
            # Very rough estimate: 5% of model volume per severe overhang
            severe_overhangs = sum(1 for o in geo.overhangs if o.angle > 45)
            support_volume = geo.volume_mm3 * 0.05 * severe_overhangs

        return GeometryAnalysis(
            overhang_risk=overhang_risk,
            thin_wall_risk=thin_wall_risk,
            bridge_risk=bridge_risk,
            manifold_risk=manifold_risk,
            support_required=support_required,
            estimated_support_volume_mm3=support_volume,
        )

    def _analyze_material_risks(self) -> MaterialRisk:
        """Analyze material-specific risks."""
        mat = self.material

        # Warping risk
        warp = mat.properties.warping_tendency
        if warp > 0.7:
            warping_risk = RiskLevel.CRITICAL
        elif warp > 0.4:
            warping_risk = RiskLevel.HIGH
        elif warp > 0.2:
            warping_risk = RiskLevel.MEDIUM
        else:
            warping_risk = RiskLevel.LOW

        # Adhesion risk (inverse of layer_adhesion)
        adhesion = mat.properties.layer_adhesion
        if adhesion < 0.5:
            adhesion_risk = RiskLevel.HIGH
        elif adhesion < 0.7:
            adhesion_risk = RiskLevel.MEDIUM
        else:
            adhesion_risk = RiskLevel.LOW

        # Stringing risk
        string = mat.properties.stringing_tendency
        if string > 0.7:
            stringing_risk = RiskLevel.HIGH
        elif string > 0.4:
            stringing_risk = RiskLevel.MEDIUM
        else:
            stringing_risk = RiskLevel.LOW

        # Environmental requirements
        env_reqs = []
        if mat.properties.requires_enclosure:
            env_reqs.append("Heated enclosure required")
        if mat.properties.toxic_fumes:
            env_reqs.append("Ventilation required")
        if mat.properties.hygroscopic:
            env_reqs.append("Store in dry box")

        return MaterialRisk(
            warping_risk=warping_risk,
            adhesion_risk=adhesion_risk,
            stringing_risk=stringing_risk,
            environmental_requirements=env_reqs,
        )

    def _collect_risk_factors(
        self,
        geo: GeometryAnalysisResult,
        geometry: GeometryAnalysis,
        material_risk: Optional[MaterialRisk],
    ) -> List[RiskFactor]:
        """Collect all risk factors into a list."""
        factors = []

        # Geometry factors
        if geometry.overhang_risk != RiskLevel.LOW:
            factors.append(RiskFactor(
                name="Overhangs",
                risk_level=geometry.overhang_risk,
                description=f"{len(geo.overhangs)} overhang(s) detected that may need support",
                mitigation="Add support structures or reorient model",
                weight=1.5,
            ))

        if geometry.thin_wall_risk != RiskLevel.LOW:
            factors.append(RiskFactor(
                name="Thin Walls",
                risk_level=geometry.thin_wall_risk,
                description=f"{len(geo.thin_walls)} thin wall section(s) detected",
                mitigation="Increase wall thickness or use smaller nozzle",
                weight=1.2,
            ))

        if geometry.bridge_risk != RiskLevel.LOW:
            factors.append(RiskFactor(
                name="Bridges",
                risk_level=geometry.bridge_risk,
                description=f"{len(geo.bridges)} unsupported bridge(s) detected",
                mitigation="Add support under bridges or reduce bridge length",
                weight=1.3,
            ))

        if geometry.manifold_risk != RiskLevel.LOW:
            factors.append(RiskFactor(
                name="Mesh Quality",
                risk_level=geometry.manifold_risk,
                description="Mesh has geometry errors that may cause slicing issues",
                mitigation="Repair mesh in Blender or Meshmixer",
                weight=1.5,
            ))

        # Material factors
        if material_risk:
            if material_risk.warping_risk != RiskLevel.LOW:
                factors.append(RiskFactor(
                    name="Warping",
                    risk_level=material_risk.warping_risk,
                    description=f"{self.material.name} is prone to warping",
                    mitigation="Use brim/raft, heated bed, and enclosure",
                    weight=1.4,
                ))

            if material_risk.adhesion_risk != RiskLevel.LOW:
                factors.append(RiskFactor(
                    name="Layer Adhesion",
                    risk_level=material_risk.adhesion_risk,
                    description=f"{self.material.name} may have layer adhesion issues",
                    mitigation="Increase nozzle temperature, reduce cooling",
                    weight=1.1,
                ))

        return factors

    def _calculate_overall_risk(
        self, factors: List[RiskFactor]
    ) -> Tuple[RiskLevel, float, float]:
        """Calculate overall risk level and success probability."""

        if not factors:
            return RiskLevel.LOW, 0.9, 0.95

        # Calculate weighted risk score
        risk_values = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }

        total_weight = sum(f.weight for f in factors)
        weighted_score = sum(
            risk_values[f.risk_level] * f.weight for f in factors
        ) / total_weight if total_weight > 0 else 1

        # Determine overall risk
        if weighted_score >= 3.5:
            overall = RiskLevel.CRITICAL
            success_prob = 0.2
        elif weighted_score >= 2.5:
            overall = RiskLevel.HIGH
            success_prob = 0.5
        elif weighted_score >= 1.5:
            overall = RiskLevel.MEDIUM
            success_prob = 0.75
        else:
            overall = RiskLevel.LOW
            success_prob = 0.9

        # Confidence based on how much data we have
        confidence = min(0.9, 0.5 + len(factors) * 0.1)

        return overall, confidence, success_prob

    def _generate_recommendations(
        self,
        geo: GeometryAnalysisResult,
        geometry: GeometryAnalysis,
        material_risk: Optional[MaterialRisk],
        risk_factors: List[RiskFactor],
    ) -> Tuple[List[str], List[str]]:
        """Generate recommendations and warnings."""
        recommendations = []
        warnings = []

        # Support recommendations
        if geometry.support_required:
            recommendations.append("Enable support structures for overhanging areas")
            if geometry.overhang_risk == RiskLevel.CRITICAL:
                recommendations.append("Consider tree supports for better surface quality")

        # Material-specific
        if material_risk:
            if material_risk.warping_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                recommendations.append("Use brim (8-10mm) for better bed adhesion")
                recommendations.append("Ensure heated bed and enclosure are active")

            for req in material_risk.environmental_requirements:
                warnings.append(req)

        # Print settings
        if geometry.thin_wall_risk != RiskLevel.LOW:
            recommendations.append("Consider using a 0.2mm or 0.25mm nozzle for thin features")

        # Mesh quality
        if geometry.manifold_risk != RiskLevel.LOW:
            recommendations.append("Repair mesh before slicing")
            warnings.append("Non-manifold geometry may cause slicing errors")

        # General
        if len(risk_factors) > 3:
            recommendations.append("Consider simplifying the model or printing in parts")

        if not recommendations:
            recommendations.append("Model appears print-ready with standard settings")

        return recommendations, warnings


def analyze_model_risk(
    file_path: str,
    material: Optional[str] = None,
) -> FailureRisk:
    """
    Convenience function to analyze a model's failure risk.

    Args:
        file_path: Path to 3D model file
        material: Optional material name for material-specific analysis

    Returns:
        FailureRisk assessment
    """
    predictor = FailurePredictor(material=material)
    return predictor.analyze(file_path)
