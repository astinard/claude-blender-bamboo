"""Healthcare validation for medical device manufacturing.

Provides validation tools for FDA compliance, including:
- Material biocompatibility
- Sterilization compatibility
- Dimensional tolerance verification
- Risk analysis (ISO 14971)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from uuid import uuid4

from src.utils import get_logger

logger = get_logger("healthcare.validation")


class BiocompatibilityClass(str, Enum):
    """ISO 10993 biocompatibility classification."""
    SURFACE_CONTACT = "surface_contact"  # Skin contact
    EXTERNAL_COMMUNICATING = "external_communicating"  # Blood path, tissue
    IMPLANT = "implant"  # Permanent implant


class ContactDuration(str, Enum):
    """Duration of body contact."""
    LIMITED = "limited"  # < 24 hours
    PROLONGED = "prolonged"  # 24 hours - 30 days
    PERMANENT = "permanent"  # > 30 days


class SterilizationMethod(str, Enum):
    """Sterilization methods."""
    ETO = "ethylene_oxide"
    GAMMA = "gamma_radiation"
    EBEAM = "electron_beam"
    STEAM = "steam_autoclave"
    PLASMA = "hydrogen_peroxide_plasma"
    DRY_HEAT = "dry_heat"
    CHEMICAL = "chemical"


class RiskSeverity(str, Enum):
    """Risk severity levels (ISO 14971)."""
    NEGLIGIBLE = "negligible"
    MINOR = "minor"
    SERIOUS = "serious"
    CRITICAL = "critical"
    CATASTROPHIC = "catastrophic"


class RiskProbability(str, Enum):
    """Risk probability levels."""
    INCREDIBLE = "incredible"  # < 10^-6
    REMOTE = "remote"  # 10^-6 to 10^-4
    OCCASIONAL = "occasional"  # 10^-4 to 10^-2
    PROBABLE = "probable"  # 10^-2 to 10^-1
    FREQUENT = "frequent"  # > 10^-1


class DeviceClass(str, Enum):
    """FDA device classification."""
    CLASS_I = "class_i"  # Low risk, general controls
    CLASS_II = "class_ii"  # Moderate risk, special controls
    CLASS_III = "class_iii"  # High risk, premarket approval


@dataclass
class Material:
    """Medical-grade material definition."""

    name: str
    trade_name: Optional[str] = None
    manufacturer: Optional[str] = None

    # Biocompatibility
    biocompatible: bool = False
    biocompatibility_class: Optional[BiocompatibilityClass] = None
    max_contact_duration: ContactDuration = ContactDuration.LIMITED
    iso_10993_tests: List[str] = field(default_factory=list)

    # Sterilization compatibility
    sterilization_compatible: List[SterilizationMethod] = field(default_factory=list)
    max_sterilization_cycles: int = 1

    # Physical properties
    usp_class: Optional[str] = None  # USP Class I-VI
    fda_cleared: bool = False
    ce_marked: bool = False

    # Traceability
    lot_number: Optional[str] = None
    expiration_date: Optional[datetime] = None
    certificate_of_conformance: Optional[str] = None


@dataclass
class ToleranceSpec:
    """Dimensional tolerance specification."""

    feature_name: str
    nominal_value: float
    unit: str = "mm"
    tolerance_plus: float = 0.1
    tolerance_minus: float = 0.1
    critical: bool = False

    @property
    def min_value(self) -> float:
        return self.nominal_value - self.tolerance_minus

    @property
    def max_value(self) -> float:
        return self.nominal_value + self.tolerance_plus

    def is_within_tolerance(self, measured: float) -> bool:
        """Check if measured value is within tolerance."""
        return self.min_value <= measured <= self.max_value


@dataclass
class MeasurementResult:
    """Result of dimensional measurement."""

    spec: ToleranceSpec
    measured_value: float
    within_tolerance: bool
    deviation: float
    measured_at: datetime = field(default_factory=datetime.utcnow)
    measured_by: Optional[str] = None
    equipment_id: Optional[str] = None


@dataclass
class RiskItem:
    """Risk analysis item (ISO 14971)."""

    risk_id: str = field(default_factory=lambda: str(uuid4())[:8])
    hazard: str = ""
    harm: str = ""
    severity: RiskSeverity = RiskSeverity.MINOR
    probability: RiskProbability = RiskProbability.REMOTE

    # Hazard source
    foreseeable_sequence: str = ""
    hazardous_situation: str = ""

    # Risk estimation
    initial_risk_level: str = ""
    risk_acceptable: bool = False

    # Risk control
    control_measures: List[str] = field(default_factory=list)
    control_type: str = ""  # inherent_safety, protective, information
    residual_severity: Optional[RiskSeverity] = None
    residual_probability: Optional[RiskProbability] = None
    residual_risk_acceptable: bool = False

    # Verification
    verification_method: str = ""
    verification_result: Optional[str] = None
    verified: bool = False


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    category: str
    check_name: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class HealthcareValidator:
    """
    Validator for medical device manufacturing requirements.

    Supports FDA 21 CFR Part 820 (QSR), ISO 13485, and ISO 14971.
    """

    # Biocompatibility test requirements by class and duration
    BIOCOMPAT_TESTS = {
        (BiocompatibilityClass.SURFACE_CONTACT, ContactDuration.LIMITED): [
            "cytotoxicity", "sensitization", "irritation"
        ],
        (BiocompatibilityClass.SURFACE_CONTACT, ContactDuration.PROLONGED): [
            "cytotoxicity", "sensitization", "irritation", "acute_systemic_toxicity"
        ],
        (BiocompatibilityClass.EXTERNAL_COMMUNICATING, ContactDuration.LIMITED): [
            "cytotoxicity", "sensitization", "irritation", "hemocompatibility"
        ],
        (BiocompatibilityClass.IMPLANT, ContactDuration.PERMANENT): [
            "cytotoxicity", "sensitization", "irritation", "acute_systemic_toxicity",
            "subchronic_toxicity", "genotoxicity", "implantation", "chronic_toxicity",
            "carcinogenicity"
        ],
    }

    # Risk acceptability matrix
    RISK_MATRIX = {
        (RiskSeverity.NEGLIGIBLE, RiskProbability.FREQUENT): "acceptable",
        (RiskSeverity.NEGLIGIBLE, RiskProbability.PROBABLE): "acceptable",
        (RiskSeverity.NEGLIGIBLE, RiskProbability.OCCASIONAL): "acceptable",
        (RiskSeverity.NEGLIGIBLE, RiskProbability.REMOTE): "acceptable",
        (RiskSeverity.NEGLIGIBLE, RiskProbability.INCREDIBLE): "acceptable",
        (RiskSeverity.MINOR, RiskProbability.FREQUENT): "alarp",
        (RiskSeverity.MINOR, RiskProbability.PROBABLE): "acceptable",
        (RiskSeverity.MINOR, RiskProbability.OCCASIONAL): "acceptable",
        (RiskSeverity.MINOR, RiskProbability.REMOTE): "acceptable",
        (RiskSeverity.MINOR, RiskProbability.INCREDIBLE): "acceptable",
        (RiskSeverity.SERIOUS, RiskProbability.FREQUENT): "unacceptable",
        (RiskSeverity.SERIOUS, RiskProbability.PROBABLE): "alarp",
        (RiskSeverity.SERIOUS, RiskProbability.OCCASIONAL): "alarp",
        (RiskSeverity.SERIOUS, RiskProbability.REMOTE): "acceptable",
        (RiskSeverity.SERIOUS, RiskProbability.INCREDIBLE): "acceptable",
        (RiskSeverity.CRITICAL, RiskProbability.FREQUENT): "unacceptable",
        (RiskSeverity.CRITICAL, RiskProbability.PROBABLE): "unacceptable",
        (RiskSeverity.CRITICAL, RiskProbability.OCCASIONAL): "alarp",
        (RiskSeverity.CRITICAL, RiskProbability.REMOTE): "alarp",
        (RiskSeverity.CRITICAL, RiskProbability.INCREDIBLE): "acceptable",
        (RiskSeverity.CATASTROPHIC, RiskProbability.FREQUENT): "unacceptable",
        (RiskSeverity.CATASTROPHIC, RiskProbability.PROBABLE): "unacceptable",
        (RiskSeverity.CATASTROPHIC, RiskProbability.OCCASIONAL): "unacceptable",
        (RiskSeverity.CATASTROPHIC, RiskProbability.REMOTE): "alarp",
        (RiskSeverity.CATASTROPHIC, RiskProbability.INCREDIBLE): "alarp",
    }

    def __init__(self):
        self._materials: Dict[str, Material] = {}
        self._approved_materials: List[str] = []

    def register_material(self, material: Material) -> None:
        """Register a medical-grade material."""
        self._materials[material.name] = material
        if material.biocompatible and material.fda_cleared:
            self._approved_materials.append(material.name)
        logger.info(f"Registered material: {material.name}")

    def validate_biocompatibility(
        self,
        material: Material,
        intended_use_class: BiocompatibilityClass,
        contact_duration: ContactDuration,
    ) -> ValidationResult:
        """
        Validate material biocompatibility for intended use.

        Args:
            material: Material to validate
            intended_use_class: Biocompatibility class for intended use
            contact_duration: Duration of body contact

        Returns:
            ValidationResult
        """
        # Get required tests
        required_tests = self.BIOCOMPAT_TESTS.get(
            (intended_use_class, contact_duration),
            self.BIOCOMPAT_TESTS.get(
                (BiocompatibilityClass.SURFACE_CONTACT, ContactDuration.LIMITED),
                ["cytotoxicity"]
            )
        )

        # Check if material has required tests
        missing_tests = [
            test for test in required_tests
            if test not in material.iso_10993_tests
        ]

        if not material.biocompatible:
            return ValidationResult(
                passed=False,
                category="biocompatibility",
                check_name="material_biocompatible",
                message=f"Material {material.name} is not certified biocompatible",
                details={"material": material.name},
            )

        if missing_tests:
            return ValidationResult(
                passed=False,
                category="biocompatibility",
                check_name="iso_10993_tests",
                message=f"Material missing required ISO 10993 tests: {missing_tests}",
                details={
                    "material": material.name,
                    "required_tests": required_tests,
                    "completed_tests": material.iso_10993_tests,
                    "missing_tests": missing_tests,
                },
            )

        # Check contact duration compatibility
        duration_order = [ContactDuration.LIMITED, ContactDuration.PROLONGED, ContactDuration.PERMANENT]
        if duration_order.index(contact_duration) > duration_order.index(material.max_contact_duration):
            return ValidationResult(
                passed=False,
                category="biocompatibility",
                check_name="contact_duration",
                message=f"Material not rated for {contact_duration.value} contact",
                details={
                    "material": material.name,
                    "required_duration": contact_duration.value,
                    "max_duration": material.max_contact_duration.value,
                },
            )

        return ValidationResult(
            passed=True,
            category="biocompatibility",
            check_name="biocompatibility_complete",
            message=f"Material {material.name} meets biocompatibility requirements",
            details={
                "material": material.name,
                "class": intended_use_class.value,
                "duration": contact_duration.value,
                "tests_verified": required_tests,
            },
        )

    def validate_sterilization(
        self,
        material: Material,
        method: SterilizationMethod,
        cycles: int = 1,
    ) -> ValidationResult:
        """
        Validate material sterilization compatibility.

        Args:
            material: Material to validate
            method: Sterilization method
            cycles: Number of sterilization cycles

        Returns:
            ValidationResult
        """
        if method not in material.sterilization_compatible:
            return ValidationResult(
                passed=False,
                category="sterilization",
                check_name="method_compatible",
                message=f"Material not compatible with {method.value} sterilization",
                details={
                    "material": material.name,
                    "requested_method": method.value,
                    "compatible_methods": [m.value for m in material.sterilization_compatible],
                },
            )

        if cycles > material.max_sterilization_cycles:
            return ValidationResult(
                passed=False,
                category="sterilization",
                check_name="cycle_limit",
                message=f"Exceeds max sterilization cycles ({material.max_sterilization_cycles})",
                details={
                    "material": material.name,
                    "requested_cycles": cycles,
                    "max_cycles": material.max_sterilization_cycles,
                },
            )

        return ValidationResult(
            passed=True,
            category="sterilization",
            check_name="sterilization_validated",
            message=f"Sterilization validated: {method.value} x{cycles}",
            details={
                "material": material.name,
                "method": method.value,
                "cycles": cycles,
            },
        )

    def validate_tolerances(
        self,
        specs: List[ToleranceSpec],
        measurements: Dict[str, float],
    ) -> Tuple[List[MeasurementResult], ValidationResult]:
        """
        Validate dimensional measurements against specifications.

        Args:
            specs: Tolerance specifications
            measurements: Dict of feature_name -> measured_value

        Returns:
            Tuple of (measurement_results, validation_result)
        """
        results = []
        all_passed = True
        critical_failures = []

        for spec in specs:
            measured = measurements.get(spec.feature_name)
            if measured is None:
                results.append(MeasurementResult(
                    spec=spec,
                    measured_value=0,
                    within_tolerance=False,
                    deviation=0,
                ))
                all_passed = False
                if spec.critical:
                    critical_failures.append(spec.feature_name)
                continue

            within_tolerance = spec.is_within_tolerance(measured)
            deviation = measured - spec.nominal_value

            results.append(MeasurementResult(
                spec=spec,
                measured_value=measured,
                within_tolerance=within_tolerance,
                deviation=deviation,
            ))

            if not within_tolerance:
                all_passed = False
                if spec.critical:
                    critical_failures.append(spec.feature_name)

        validation = ValidationResult(
            passed=all_passed,
            category="dimensional",
            check_name="tolerance_verification",
            message="All dimensions within tolerance" if all_passed else "Tolerance violations found",
            details={
                "total_features": len(specs),
                "passed": sum(1 for r in results if r.within_tolerance),
                "failed": sum(1 for r in results if not r.within_tolerance),
                "critical_failures": critical_failures,
            },
        )

        return results, validation

    def assess_risk(self, risk: RiskItem) -> str:
        """
        Assess risk level using ISO 14971 risk matrix.

        Args:
            risk: Risk item to assess

        Returns:
            Risk level: "acceptable", "alarp", or "unacceptable"
        """
        return self.RISK_MATRIX.get(
            (risk.severity, risk.probability),
            "unacceptable"
        )

    def evaluate_residual_risk(self, risk: RiskItem) -> ValidationResult:
        """
        Evaluate residual risk after control measures.

        Args:
            risk: Risk item with control measures

        Returns:
            ValidationResult
        """
        if not risk.control_measures:
            return ValidationResult(
                passed=False,
                category="risk",
                check_name="control_measures",
                message="No risk control measures defined",
                details={"risk_id": risk.risk_id, "hazard": risk.hazard},
            )

        if risk.residual_severity is None or risk.residual_probability is None:
            return ValidationResult(
                passed=False,
                category="risk",
                check_name="residual_assessment",
                message="Residual risk not assessed",
                details={"risk_id": risk.risk_id},
            )

        residual_level = self.RISK_MATRIX.get(
            (risk.residual_severity, risk.residual_probability),
            "unacceptable"
        )

        if residual_level == "unacceptable":
            return ValidationResult(
                passed=False,
                category="risk",
                check_name="residual_acceptable",
                message=f"Residual risk unacceptable for {risk.hazard}",
                details={
                    "risk_id": risk.risk_id,
                    "residual_severity": risk.residual_severity.value,
                    "residual_probability": risk.residual_probability.value,
                    "level": residual_level,
                },
            )

        return ValidationResult(
            passed=True,
            category="risk",
            check_name="residual_acceptable",
            message=f"Residual risk {residual_level} for {risk.hazard}",
            details={
                "risk_id": risk.risk_id,
                "level": residual_level,
                "control_measures": risk.control_measures,
            },
        )


# Pre-defined medical-grade materials
MEDICAL_MATERIALS = {
    "PA12-MED": Material(
        name="PA12-MED",
        trade_name="PA 2200",
        manufacturer="EOS",
        biocompatible=True,
        biocompatibility_class=BiocompatibilityClass.SURFACE_CONTACT,
        max_contact_duration=ContactDuration.PROLONGED,
        iso_10993_tests=["cytotoxicity", "sensitization", "irritation"],
        sterilization_compatible=[
            SterilizationMethod.ETO,
            SterilizationMethod.GAMMA,
            SterilizationMethod.STEAM,
        ],
        max_sterilization_cycles=5,
        usp_class="VI",
        fda_cleared=True,
        ce_marked=True,
    ),
    "PEEK-OPTIMA": Material(
        name="PEEK-OPTIMA",
        trade_name="PEEK-OPTIMA Natural",
        manufacturer="Invibio",
        biocompatible=True,
        biocompatibility_class=BiocompatibilityClass.IMPLANT,
        max_contact_duration=ContactDuration.PERMANENT,
        iso_10993_tests=[
            "cytotoxicity", "sensitization", "irritation", "acute_systemic_toxicity",
            "subchronic_toxicity", "genotoxicity", "implantation", "chronic_toxicity",
        ],
        sterilization_compatible=[
            SterilizationMethod.ETO,
            SterilizationMethod.GAMMA,
            SterilizationMethod.STEAM,
            SterilizationMethod.PLASMA,
        ],
        max_sterilization_cycles=100,
        usp_class="VI",
        fda_cleared=True,
        ce_marked=True,
    ),
    "TITANIUM-TI64": Material(
        name="TITANIUM-TI64",
        trade_name="Ti-6Al-4V ELI",
        manufacturer="Various",
        biocompatible=True,
        biocompatibility_class=BiocompatibilityClass.IMPLANT,
        max_contact_duration=ContactDuration.PERMANENT,
        iso_10993_tests=[
            "cytotoxicity", "sensitization", "irritation", "acute_systemic_toxicity",
            "subchronic_toxicity", "genotoxicity", "implantation", "chronic_toxicity",
            "carcinogenicity",
        ],
        sterilization_compatible=[
            SterilizationMethod.ETO,
            SterilizationMethod.GAMMA,
            SterilizationMethod.STEAM,
            SterilizationMethod.PLASMA,
        ],
        max_sterilization_cycles=1000,
        usp_class="VI",
        fda_cleared=True,
        ce_marked=True,
    ),
    "DENTAL-RESIN": Material(
        name="DENTAL-RESIN",
        trade_name="Dental Model Resin",
        manufacturer="Formlabs",
        biocompatible=True,
        biocompatibility_class=BiocompatibilityClass.SURFACE_CONTACT,
        max_contact_duration=ContactDuration.LIMITED,
        iso_10993_tests=["cytotoxicity"],
        sterilization_compatible=[SterilizationMethod.CHEMICAL],
        max_sterilization_cycles=1,
        fda_cleared=True,
    ),
}


def get_healthcare_validator() -> HealthcareValidator:
    """Get healthcare validator with pre-registered materials."""
    validator = HealthcareValidator()
    for material in MEDICAL_MATERIALS.values():
        validator.register_material(material)
    return validator
