"""Healthcare module for medical device manufacturing compliance.

Provides tools for FDA 21 CFR Part 820 compliance, including:
- Material biocompatibility validation
- Sterilization compatibility checking
- Dimensional tolerance verification
- Design History File (DHF) generation
- Risk analysis (ISO 14971)
"""

from src.healthcare.validation import (
    HealthcareValidator,
    Material,
    ToleranceSpec,
    MeasurementResult,
    RiskItem,
    ValidationResult,
    BiocompatibilityClass,
    ContactDuration,
    SterilizationMethod,
    RiskSeverity,
    RiskProbability,
    DeviceClass,
    MEDICAL_MATERIALS,
    get_healthcare_validator,
)

from src.healthcare.dhf import (
    DHFGenerator,
    DHFProject,
    DesignInput,
    DesignOutput,
    DesignReview,
    VerificationRecord,
    ValidationRecord,
    Signature,
    DocumentType,
    ApprovalStatus,
    get_dhf_generator,
)

__all__ = [
    # Validation
    "HealthcareValidator",
    "Material",
    "ToleranceSpec",
    "MeasurementResult",
    "RiskItem",
    "ValidationResult",
    "BiocompatibilityClass",
    "ContactDuration",
    "SterilizationMethod",
    "RiskSeverity",
    "RiskProbability",
    "DeviceClass",
    "MEDICAL_MATERIALS",
    "get_healthcare_validator",
    # DHF
    "DHFGenerator",
    "DHFProject",
    "DesignInput",
    "DesignOutput",
    "DesignReview",
    "VerificationRecord",
    "ValidationRecord",
    "Signature",
    "DocumentType",
    "ApprovalStatus",
    "get_dhf_generator",
]
