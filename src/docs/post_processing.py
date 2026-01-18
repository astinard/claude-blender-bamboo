"""Post-processing guide generator for 3D printed parts.

Provides recommendations for finishing and post-processing techniques.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from src.utils import get_logger

logger = get_logger("docs.post_processing")


class FinishLevel(str, Enum):
    """Finish quality levels."""
    RAW = "raw"  # As printed
    BASIC = "basic"  # Support removal, cleanup
    SMOOTH = "smooth"  # Sanding, filling
    POLISHED = "polished"  # High-quality finish
    PAINTED = "painted"  # Paint ready/painted


class ProcessType(str, Enum):
    """Types of post-processing."""
    SUPPORT_REMOVAL = "support_removal"
    SANDING = "sanding"
    FILLING = "filling"
    PRIMING = "priming"
    PAINTING = "painting"
    VAPOR_SMOOTHING = "vapor_smoothing"
    HEAT_TREATMENT = "heat_treatment"
    UV_CURING = "uv_curing"
    THREADING = "threading"
    ASSEMBLY = "assembly"


@dataclass
class ProcessStep:
    """A post-processing step."""
    process_type: ProcessType
    name: str
    description: str
    materials_needed: List[str] = field(default_factory=list)
    tools_needed: List[str] = field(default_factory=list)
    estimated_time_minutes: int = 0
    difficulty: str = "easy"  # easy, medium, hard
    safety_notes: List[str] = field(default_factory=list)
    tips: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "process_type": self.process_type.value,
            "name": self.name,
            "description": self.description,
            "materials_needed": self.materials_needed,
            "tools_needed": self.tools_needed,
            "estimated_time_minutes": self.estimated_time_minutes,
            "difficulty": self.difficulty,
            "safety_notes": self.safety_notes,
            "tips": self.tips,
        }


@dataclass
class ProcessingGuide:
    """Complete post-processing guide."""
    success: bool
    material: str = ""
    target_finish: FinishLevel = FinishLevel.BASIC
    steps: List[ProcessStep] = field(default_factory=list)
    total_time_minutes: int = 0
    materials_list: List[str] = field(default_factory=list)
    tools_list: List[str] = field(default_factory=list)
    safety_warnings: List[str] = field(default_factory=list)
    generated_at: str = ""
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "material": self.material,
            "target_finish": self.target_finish.value,
            "steps": [s.to_dict() for s in self.steps],
            "total_time_minutes": self.total_time_minutes,
            "materials_list": self.materials_list,
            "tools_list": self.tools_list,
            "safety_warnings": self.safety_warnings,
            "generated_at": self.generated_at,
            "error_message": self.error_message,
        }


class PostProcessingGuide:
    """
    Post-processing guide generator.

    Provides step-by-step instructions for finishing 3D prints.
    """

    # Process library
    PROCESS_LIBRARY = {
        ProcessType.SUPPORT_REMOVAL: ProcessStep(
            process_type=ProcessType.SUPPORT_REMOVAL,
            name="Support Removal",
            description="Carefully remove support structures from the print.",
            tools_needed=["Flush cutters", "Needle-nose pliers"],
            estimated_time_minutes=10,
            difficulty="easy",
            tips=[
                "Work slowly to avoid damaging the part",
                "Cut supports close to the part surface",
                "Use pliers for stubborn supports",
            ],
        ),
        ProcessType.SANDING: ProcessStep(
            process_type=ProcessType.SANDING,
            name="Sanding",
            description="Sand the surface to remove layer lines and imperfections.",
            materials_needed=["Sandpaper (120, 220, 400, 800 grit)"],
            tools_needed=["Sanding block", "Safety glasses"],
            estimated_time_minutes=30,
            difficulty="medium",
            safety_notes=["Wear a dust mask", "Work in ventilated area"],
            tips=[
                "Start with coarse grit, progress to finer",
                "Sand in consistent direction",
                "Wet sanding reduces dust and improves finish",
            ],
        ),
        ProcessType.FILLING: ProcessStep(
            process_type=ProcessType.FILLING,
            name="Gap Filling",
            description="Fill gaps, holes, and surface imperfections.",
            materials_needed=["Filler putty or wood filler", "Spot putty"],
            tools_needed=["Putty knife", "Sandpaper (220+ grit)"],
            estimated_time_minutes=45,
            difficulty="medium",
            tips=[
                "Apply thin layers, multiple coats if needed",
                "Sand between coats",
                "Use spot putty for small imperfections",
            ],
        ),
        ProcessType.PRIMING: ProcessStep(
            process_type=ProcessType.PRIMING,
            name="Priming",
            description="Apply primer to prepare surface for painting.",
            materials_needed=["Filler primer spray", "Sandable primer"],
            tools_needed=["Spray booth or newspaper", "Respirator"],
            estimated_time_minutes=30,
            difficulty="easy",
            safety_notes=["Use in ventilated area", "Wear respirator"],
            tips=[
                "Apply light, even coats",
                "Sand lightly between coats with 400 grit",
                "2-3 coats typically needed",
            ],
        ),
        ProcessType.PAINTING: ProcessStep(
            process_type=ProcessType.PAINTING,
            name="Painting",
            description="Apply paint for final color and finish.",
            materials_needed=["Paint (spray or brush)", "Clear coat"],
            tools_needed=["Spray booth", "Respirator", "Brushes (if needed)"],
            estimated_time_minutes=60,
            difficulty="medium",
            safety_notes=["Use in ventilated area", "Wear respirator"],
            tips=[
                "Light coats, multiple passes",
                "Allow proper dry time between coats",
                "Finish with clear coat for durability",
            ],
        ),
        ProcessType.VAPOR_SMOOTHING: ProcessStep(
            process_type=ProcessType.VAPOR_SMOOTHING,
            name="Vapor Smoothing (ABS)",
            description="Use acetone vapor to smooth ABS prints.",
            materials_needed=["Acetone", "Glass jar with lid"],
            tools_needed=["Paper towels", "Heat-safe gloves"],
            estimated_time_minutes=20,
            difficulty="hard",
            safety_notes=[
                "Acetone is flammable - no open flames",
                "Use in very well ventilated area",
                "Wear chemical-resistant gloves",
            ],
            tips=[
                "Don't over-expose - details can be lost",
                "Check progress every few minutes",
                "Allow part to cure 24 hours after",
            ],
        ),
        ProcessType.HEAT_TREATMENT: ProcessStep(
            process_type=ProcessType.HEAT_TREATMENT,
            name="Heat Treatment (Annealing)",
            description="Heat treat to improve strength and reduce warping.",
            materials_needed=["Sand or salt (for support)"],
            tools_needed=["Oven", "Thermometer"],
            estimated_time_minutes=120,
            difficulty="medium",
            safety_notes=["Monitor temperature carefully", "Allow slow cooling"],
            tips=[
                "PLA: 60-70°C for 1-2 hours",
                "PETG: 70-80°C for 2-3 hours",
                "Support part in sand to prevent deformation",
            ],
        ),
        ProcessType.THREADING: ProcessStep(
            process_type=ProcessType.THREADING,
            name="Thread Installation",
            description="Install heat-set threaded inserts.",
            materials_needed=["Heat-set inserts"],
            tools_needed=["Soldering iron", "Heat-set tips"],
            estimated_time_minutes=15,
            difficulty="medium",
            safety_notes=["Soldering iron is very hot", "Work on heat-safe surface"],
            tips=[
                "Ensure hole is sized correctly",
                "Insert straight, don't tilt",
                "Let cool before applying load",
            ],
        ),
    }

    def __init__(self):
        """Initialize post-processing guide."""
        pass

    def generate_guide(
        self,
        material: str = "pla",
        target_finish: FinishLevel = FinishLevel.SMOOTH,
        has_supports: bool = True,
        needs_threading: bool = False,
    ) -> ProcessingGuide:
        """
        Generate a post-processing guide.

        Args:
            material: Print material
            target_finish: Desired finish level
            has_supports: Whether print has supports
            needs_threading: Whether to add threading step

        Returns:
            Processing guide
        """
        try:
            steps = []
            materials = set()
            tools = set()
            safety_warnings = set()

            # Support removal if needed
            if has_supports:
                step = self.PROCESS_LIBRARY[ProcessType.SUPPORT_REMOVAL]
                steps.append(step)
                tools.update(step.tools_needed)

            # Sanding for smooth or better finish
            if target_finish in [FinishLevel.SMOOTH, FinishLevel.POLISHED, FinishLevel.PAINTED]:
                step = self.PROCESS_LIBRARY[ProcessType.SANDING]
                steps.append(step)
                materials.update(step.materials_needed)
                tools.update(step.tools_needed)
                safety_warnings.update(step.safety_notes)

            # Filling for polished/painted
            if target_finish in [FinishLevel.POLISHED, FinishLevel.PAINTED]:
                step = self.PROCESS_LIBRARY[ProcessType.FILLING]
                steps.append(step)
                materials.update(step.materials_needed)
                tools.update(step.tools_needed)

            # Vapor smoothing for ABS
            if material.lower() == "abs" and target_finish in [FinishLevel.POLISHED, FinishLevel.SMOOTH]:
                step = self.PROCESS_LIBRARY[ProcessType.VAPOR_SMOOTHING]
                steps.append(step)
                materials.update(step.materials_needed)
                tools.update(step.tools_needed)
                safety_warnings.update(step.safety_notes)

            # Priming and painting
            if target_finish == FinishLevel.PAINTED:
                priming = self.PROCESS_LIBRARY[ProcessType.PRIMING]
                steps.append(priming)
                materials.update(priming.materials_needed)
                tools.update(priming.tools_needed)
                safety_warnings.update(priming.safety_notes)

                painting = self.PROCESS_LIBRARY[ProcessType.PAINTING]
                steps.append(painting)
                materials.update(painting.materials_needed)
                tools.update(painting.tools_needed)
                safety_warnings.update(painting.safety_notes)

            # Threading
            if needs_threading:
                step = self.PROCESS_LIBRARY[ProcessType.THREADING]
                steps.append(step)
                materials.update(step.materials_needed)
                tools.update(step.tools_needed)
                safety_warnings.update(step.safety_notes)

            total_time = sum(s.estimated_time_minutes for s in steps)

            return ProcessingGuide(
                success=True,
                material=material.upper(),
                target_finish=target_finish,
                steps=steps,
                total_time_minutes=total_time,
                materials_list=sorted(list(materials)),
                tools_list=sorted(list(tools)),
                safety_warnings=sorted(list(safety_warnings)),
                generated_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f"Guide generation error: {e}")
            return ProcessingGuide(
                success=False,
                error_message=str(e),
            )

    def get_process_info(self, process_type: ProcessType) -> Optional[ProcessStep]:
        """Get information about a specific process."""
        return self.PROCESS_LIBRARY.get(process_type)

    def get_material_recommendations(self, material: str) -> Dict[str, str]:
        """Get material-specific post-processing recommendations."""
        recommendations = {
            "pla": {
                "smoothing": "Sanding or filler primer (no vapor smoothing)",
                "painting": "Works well with acrylic paints",
                "heat_limit": "Avoid temperatures above 60°C",
                "best_for": "Prototypes, display models",
            },
            "petg": {
                "smoothing": "Sanding only (no vapor smoothing)",
                "painting": "Use plastic-compatible primers",
                "heat_limit": "Good heat resistance up to 70°C",
                "best_for": "Functional parts, food-safe items",
            },
            "abs": {
                "smoothing": "Acetone vapor smoothing works well",
                "painting": "Excellent paint adhesion",
                "heat_limit": "Good heat resistance up to 100°C",
                "best_for": "Enclosures, automotive parts",
            },
            "tpu": {
                "smoothing": "Limited options - mostly as-printed",
                "painting": "Flexible paints only",
                "heat_limit": "Moderate heat resistance",
                "best_for": "Flexible functional parts",
            },
        }
        return recommendations.get(material.lower(), recommendations["pla"])

    def export_markdown(self, guide: ProcessingGuide) -> str:
        """Export guide as markdown."""
        lines = [
            "# Post-Processing Guide",
            "",
            f"*Material: {guide.material}*",
            f"*Target Finish: {guide.target_finish.value.title()}*",
            f"*Generated: {guide.generated_at}*",
            "",
        ]

        # Safety warnings
        if guide.safety_warnings:
            lines.extend([
                "## Safety Warnings",
                "",
            ])
            for warning in guide.safety_warnings:
                lines.append(f"- {warning}")
            lines.append("")

        # Materials needed
        if guide.materials_list:
            lines.extend([
                "## Materials Needed",
                "",
            ])
            for mat in guide.materials_list:
                lines.append(f"- {mat}")
            lines.append("")

        # Tools needed
        if guide.tools_list:
            lines.extend([
                "## Tools Needed",
                "",
            ])
            for tool in guide.tools_list:
                lines.append(f"- {tool}")
            lines.append("")

        # Summary
        lines.extend([
            "## Summary",
            "",
            f"- **Total Steps:** {len(guide.steps)}",
            f"- **Estimated Time:** {guide.total_time_minutes} minutes",
            "",
        ])

        # Steps
        lines.extend([
            "## Steps",
            "",
        ])

        for i, step in enumerate(guide.steps, 1):
            lines.append(f"### Step {i}: {step.name}")
            lines.append("")
            lines.append(step.description)
            lines.append("")
            lines.append(f"**Time:** ~{step.estimated_time_minutes} minutes")
            lines.append(f"**Difficulty:** {step.difficulty.title()}")
            lines.append("")

            if step.materials_needed:
                lines.append("**Materials:**")
                for mat in step.materials_needed:
                    lines.append(f"- {mat}")
                lines.append("")

            if step.tools_needed:
                lines.append("**Tools:**")
                for tool in step.tools_needed:
                    lines.append(f"- {tool}")
                lines.append("")

            if step.tips:
                lines.append("**Tips:**")
                for tip in step.tips:
                    lines.append(f"- {tip}")
                lines.append("")

            if step.safety_notes:
                lines.append("**Safety:**")
                for note in step.safety_notes:
                    lines.append(f"- {note}")
                lines.append("")

        return "\n".join(lines)


# Convenience functions
def create_guide(
    material: str = "pla",
    finish: str = "smooth",
    has_supports: bool = True,
) -> ProcessingGuide:
    """Create a post-processing guide."""
    guide = PostProcessingGuide()
    return guide.generate_guide(
        material=material,
        target_finish=FinishLevel(finish),
        has_supports=has_supports,
    )


def get_finish_steps(finish_level: str) -> List[str]:
    """Get list of steps for a finish level."""
    guide = PostProcessingGuide()
    result = guide.generate_guide(
        target_finish=FinishLevel(finish_level),
    )
    return [s.name for s in result.steps]
