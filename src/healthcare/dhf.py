"""Design History File (DHF) generation for FDA compliance.

Generates comprehensive documentation required for FDA 21 CFR Part 820
Design Control requirements, including:
- Design input/output documentation
- Risk analysis (ISO 14971)
- Verification and validation records
- Design review records
- Design transfer documentation
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from uuid import uuid4

from src.utils import get_logger
from src.healthcare.validation import (
    RiskItem, ValidationResult, ToleranceSpec,
    DeviceClass, Material, HealthcareValidator
)

logger = get_logger("healthcare.dhf")


class DocumentType(str, Enum):
    """Types of DHF documents."""
    DESIGN_INPUT = "design_input"
    DESIGN_OUTPUT = "design_output"
    DESIGN_REVIEW = "design_review"
    VERIFICATION = "verification"
    VALIDATION = "validation"
    RISK_ANALYSIS = "risk_analysis"
    DESIGN_TRANSFER = "design_transfer"
    CHANGE_ORDER = "change_order"


class ApprovalStatus(str, Enum):
    """Document approval status."""
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    OBSOLETE = "obsolete"


@dataclass
class Signature:
    """Electronic signature for document approval."""

    signer_name: str
    signer_role: str
    signer_id: str
    signed_at: datetime = field(default_factory=datetime.utcnow)
    signature_hash: str = ""
    meaning: str = ""  # "approval", "review", "authored"

    def to_dict(self) -> dict:
        return {
            "signer_name": self.signer_name,
            "signer_role": self.signer_role,
            "signer_id": self.signer_id,
            "signed_at": self.signed_at.isoformat(),
            "signature_hash": self.signature_hash,
            "meaning": self.meaning,
        }


@dataclass
class DesignInput:
    """Design input requirement."""

    input_id: str = field(default_factory=lambda: f"DI-{uuid4().hex[:8].upper()}")
    requirement: str = ""
    source: str = ""  # customer, regulatory, standard, etc.
    priority: str = "essential"  # essential, desirable, optional
    verification_method: str = ""
    acceptance_criteria: str = ""
    linked_outputs: List[str] = field(default_factory=list)
    linked_risks: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DesignOutput:
    """Design output specification."""

    output_id: str = field(default_factory=lambda: f"DO-{uuid4().hex[:8].upper()}")
    description: str = ""
    output_type: str = ""  # specification, drawing, procedure, software
    document_number: str = ""
    revision: str = "A"
    linked_inputs: List[str] = field(default_factory=list)
    acceptance_criteria: str = ""
    verification_required: bool = True
    verified: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DesignReview:
    """Design review record."""

    review_id: str = field(default_factory=lambda: f"DR-{uuid4().hex[:8].upper()}")
    review_date: datetime = field(default_factory=datetime.utcnow)
    phase: str = ""  # concept, design, verification, validation, transfer
    attendees: List[str] = field(default_factory=list)
    topics_reviewed: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    decision: str = ""  # proceed, proceed_with_actions, hold, cancel
    signatures: List[Signature] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["review_date"] = self.review_date.isoformat()
        data["signatures"] = [s.to_dict() for s in self.signatures]
        return data


@dataclass
class VerificationRecord:
    """Design verification record."""

    record_id: str = field(default_factory=lambda: f"VER-{uuid4().hex[:8].upper()}")
    input_id: str = ""  # Linked design input
    test_method: str = ""
    test_protocol: str = ""
    acceptance_criteria: str = ""
    test_date: datetime = field(default_factory=datetime.utcnow)
    tester: str = ""
    equipment_used: List[str] = field(default_factory=list)
    results: str = ""
    passed: bool = False
    deviations: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    signatures: List[Signature] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["test_date"] = self.test_date.isoformat()
        data["signatures"] = [s.to_dict() for s in self.signatures]
        return data


@dataclass
class ValidationRecord:
    """Design validation record."""

    record_id: str = field(default_factory=lambda: f"VAL-{uuid4().hex[:8].upper()}")
    user_need: str = ""
    validation_method: str = ""
    validation_protocol: str = ""
    acceptance_criteria: str = ""
    validation_date: datetime = field(default_factory=datetime.utcnow)
    validator: str = ""
    environment: str = ""  # simulated, actual use
    participants: int = 0
    results_summary: str = ""
    passed: bool = False
    observations: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    signatures: List[Signature] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["validation_date"] = self.validation_date.isoformat()
        data["signatures"] = [s.to_dict() for s in self.signatures]
        return data


@dataclass
class DHFProject:
    """Complete Design History File for a medical device project."""

    # Project identification
    project_id: str = field(default_factory=lambda: f"PRJ-{uuid4().hex[:8].upper()}")
    project_name: str = ""
    device_name: str = ""
    device_description: str = ""
    device_class: DeviceClass = DeviceClass.CLASS_I
    intended_use: str = ""
    indications_for_use: str = ""

    # Regulatory
    predicate_device: Optional[str] = None
    regulatory_pathway: str = ""  # 510k, PMA, De Novo
    standards_applied: List[str] = field(default_factory=list)

    # Design controls
    design_inputs: List[DesignInput] = field(default_factory=list)
    design_outputs: List[DesignOutput] = field(default_factory=list)
    design_reviews: List[DesignReview] = field(default_factory=list)
    verifications: List[VerificationRecord] = field(default_factory=list)
    validations: List[ValidationRecord] = field(default_factory=list)

    # Risk management
    risks: List[RiskItem] = field(default_factory=list)

    # Materials and specifications
    materials: List[str] = field(default_factory=list)
    tolerances: List[ToleranceSpec] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0"
    status: ApprovalStatus = ApprovalStatus.DRAFT

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "device_name": self.device_name,
            "device_description": self.device_description,
            "device_class": self.device_class.value,
            "intended_use": self.intended_use,
            "indications_for_use": self.indications_for_use,
            "predicate_device": self.predicate_device,
            "regulatory_pathway": self.regulatory_pathway,
            "standards_applied": self.standards_applied,
            "design_inputs": [di.to_dict() for di in self.design_inputs],
            "design_outputs": [do.to_dict() for do in self.design_outputs],
            "design_reviews": [dr.to_dict() for dr in self.design_reviews],
            "verifications": [v.to_dict() for v in self.verifications],
            "validations": [v.to_dict() for v in self.validations],
            "risks": [asdict(r) for r in self.risks],
            "materials": self.materials,
            "tolerances": [asdict(t) for t in self.tolerances],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "status": self.status.value,
        }


class DHFGenerator:
    """
    Design History File generator.

    Generates FDA-compliant documentation packages including:
    - Design Control documentation
    - Risk Management File (ISO 14971)
    - Verification/Validation summary
    - Traceability matrix
    """

    def __init__(self, output_dir: str = "output/dhf"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._projects: Dict[str, DHFProject] = {}

    def create_project(
        self,
        project_name: str,
        device_name: str,
        device_class: DeviceClass,
        intended_use: str,
        **kwargs,
    ) -> DHFProject:
        """Create a new DHF project."""
        project = DHFProject(
            project_name=project_name,
            device_name=device_name,
            device_class=device_class,
            intended_use=intended_use,
            **kwargs,
        )
        self._projects[project.project_id] = project
        logger.info(f"Created DHF project: {project.project_id} - {project_name}")
        return project

    def get_project(self, project_id: str) -> Optional[DHFProject]:
        """Get a project by ID."""
        return self._projects.get(project_id)

    def add_design_input(
        self,
        project_id: str,
        requirement: str,
        source: str,
        acceptance_criteria: str,
        **kwargs,
    ) -> DesignInput:
        """Add a design input requirement."""
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        di = DesignInput(
            requirement=requirement,
            source=source,
            acceptance_criteria=acceptance_criteria,
            **kwargs,
        )
        project.design_inputs.append(di)
        project.updated_at = datetime.utcnow()

        logger.info(f"Added design input {di.input_id} to {project_id}")
        return di

    def add_design_output(
        self,
        project_id: str,
        description: str,
        output_type: str,
        linked_inputs: List[str],
        **kwargs,
    ) -> DesignOutput:
        """Add a design output specification."""
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        do = DesignOutput(
            description=description,
            output_type=output_type,
            linked_inputs=linked_inputs,
            **kwargs,
        )
        project.design_outputs.append(do)
        project.updated_at = datetime.utcnow()

        # Link back to inputs
        for di in project.design_inputs:
            if di.input_id in linked_inputs:
                di.linked_outputs.append(do.output_id)

        logger.info(f"Added design output {do.output_id} to {project_id}")
        return do

    def add_risk(self, project_id: str, risk: RiskItem) -> None:
        """Add a risk item to the project."""
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        project.risks.append(risk)
        project.updated_at = datetime.utcnow()

    def add_verification(
        self,
        project_id: str,
        input_id: str,
        test_method: str,
        results: str,
        passed: bool,
        **kwargs,
    ) -> VerificationRecord:
        """Add a verification record."""
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        ver = VerificationRecord(
            input_id=input_id,
            test_method=test_method,
            results=results,
            passed=passed,
            **kwargs,
        )
        project.verifications.append(ver)
        project.updated_at = datetime.utcnow()

        logger.info(f"Added verification {ver.record_id} to {project_id}")
        return ver

    def add_validation(
        self,
        project_id: str,
        user_need: str,
        validation_method: str,
        results_summary: str,
        passed: bool,
        **kwargs,
    ) -> ValidationRecord:
        """Add a validation record."""
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        val = ValidationRecord(
            user_need=user_need,
            validation_method=validation_method,
            results_summary=results_summary,
            passed=passed,
            **kwargs,
        )
        project.validations.append(val)
        project.updated_at = datetime.utcnow()

        logger.info(f"Added validation {val.record_id} to {project_id}")
        return val

    def generate_traceability_matrix(self, project_id: str) -> Dict[str, Any]:
        """
        Generate requirements traceability matrix.

        Shows linkage between:
        - User needs
        - Design inputs
        - Design outputs
        - Verifications
        - Validations
        - Risks
        """
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        matrix = []

        for di in project.design_inputs:
            # Find linked outputs
            linked_outputs = [
                do for do in project.design_outputs
                if di.input_id in do.linked_inputs
            ]

            # Find verifications
            linked_vers = [
                v for v in project.verifications
                if v.input_id == di.input_id
            ]

            # Find linked risks
            linked_risks = [
                r for r in project.risks
                if r.risk_id in di.linked_risks
            ]

            matrix.append({
                "design_input": {
                    "id": di.input_id,
                    "requirement": di.requirement,
                    "source": di.source,
                },
                "design_outputs": [
                    {"id": do.output_id, "description": do.description}
                    for do in linked_outputs
                ],
                "verifications": [
                    {"id": v.record_id, "passed": v.passed, "method": v.test_method}
                    for v in linked_vers
                ],
                "risks": [
                    {"id": r.risk_id, "hazard": r.hazard, "acceptable": r.residual_risk_acceptable}
                    for r in linked_risks
                ],
                "complete": bool(linked_outputs) and all(v.passed for v in linked_vers),
            })

        return {
            "project_id": project_id,
            "project_name": project.project_name,
            "generated_at": datetime.utcnow().isoformat(),
            "total_inputs": len(project.design_inputs),
            "traced_inputs": sum(1 for row in matrix if row["complete"]),
            "matrix": matrix,
        }

    def generate_risk_summary(self, project_id: str) -> Dict[str, Any]:
        """Generate risk management summary."""
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        validator = HealthcareValidator()

        risk_summary = []
        for risk in project.risks:
            initial_level = validator.assess_risk(risk)
            if risk.residual_severity and risk.residual_probability:
                residual_level = validator.RISK_MATRIX.get(
                    (risk.residual_severity, risk.residual_probability),
                    "unacceptable"
                )
            else:
                residual_level = "not_assessed"

            risk_summary.append({
                "risk_id": risk.risk_id,
                "hazard": risk.hazard,
                "harm": risk.harm,
                "initial_severity": risk.severity.value,
                "initial_probability": risk.probability.value,
                "initial_level": initial_level,
                "control_measures": risk.control_measures,
                "residual_severity": risk.residual_severity.value if risk.residual_severity else None,
                "residual_probability": risk.residual_probability.value if risk.residual_probability else None,
                "residual_level": residual_level,
                "acceptable": residual_level in ["acceptable", "alarp"],
            })

        unacceptable_risks = [r for r in risk_summary if not r["acceptable"]]

        return {
            "project_id": project_id,
            "generated_at": datetime.utcnow().isoformat(),
            "total_risks": len(risk_summary),
            "acceptable_risks": len([r for r in risk_summary if r["acceptable"]]),
            "unacceptable_risks": len(unacceptable_risks),
            "overall_acceptable": len(unacceptable_risks) == 0,
            "risks": risk_summary,
        }

    def export_dhf(self, project_id: str, format: str = "json") -> str:
        """
        Export complete DHF package.

        Args:
            project_id: Project ID
            format: Export format (json, pdf)

        Returns:
            Path to exported file
        """
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        project_dir = self.output_dir / project_id
        project_dir.mkdir(exist_ok=True)

        # Generate all components
        dhf_data = {
            "project": project.to_dict(),
            "traceability_matrix": self.generate_traceability_matrix(project_id),
            "risk_summary": self.generate_risk_summary(project_id),
            "export_date": datetime.utcnow().isoformat(),
            "dhf_version": "1.0",
        }

        if format == "json":
            output_path = project_dir / f"dhf_{project_id}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(dhf_data, f, indent=2, default=str)
        else:
            # For PDF, would use reportlab or similar
            output_path = project_dir / f"dhf_{project_id}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(dhf_data, f, indent=2, default=str)

        logger.info(f"Exported DHF to {output_path}")
        return str(output_path)


# Global DHF generator
_dhf_generator: Optional[DHFGenerator] = None


def get_dhf_generator() -> DHFGenerator:
    """Get global DHF generator instance."""
    global _dhf_generator
    if _dhf_generator is None:
        _dhf_generator = DHFGenerator()
    return _dhf_generator
