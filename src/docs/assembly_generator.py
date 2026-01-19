"""Assembly instruction generator for multi-part prints.

Creates step-by-step assembly guides with visual aids.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("docs.assembly_generator")


class ConnectionType(str, Enum):
    """Types of part connections."""
    SNAP_FIT = "snap_fit"
    SCREW = "screw"
    GLUE = "glue"
    PRESS_FIT = "press_fit"
    SLIDE = "slide"
    HINGE = "hinge"
    MAGNET = "magnet"
    THREADED = "threaded"


@dataclass
class AssemblyPart:
    """A part in the assembly."""
    name: str
    file_path: str
    quantity: int = 1
    material: str = "pla"
    color: Optional[str] = None
    print_time_hours: float = 0.0
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "file_path": self.file_path,
            "quantity": self.quantity,
            "material": self.material,
            "color": self.color,
            "print_time_hours": self.print_time_hours,
            "notes": self.notes,
        }


@dataclass
class AssemblyStep:
    """A step in the assembly process."""
    step_number: int
    description: str
    parts_used: List[str] = field(default_factory=list)
    connection_type: Optional[ConnectionType] = None
    tools_needed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    tips: List[str] = field(default_factory=list)
    image_path: Optional[str] = None
    estimated_time_minutes: int = 5

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "step_number": self.step_number,
            "description": self.description,
            "parts_used": self.parts_used,
            "connection_type": self.connection_type.value if self.connection_type else None,
            "tools_needed": self.tools_needed,
            "warnings": self.warnings,
            "tips": self.tips,
            "image_path": self.image_path,
            "estimated_time_minutes": self.estimated_time_minutes,
        }


@dataclass
class AssemblyConfig:
    """Configuration for assembly generation."""
    project_name: str = "Assembly"
    author: str = ""
    include_bom: bool = True  # Bill of Materials
    include_print_settings: bool = True
    include_hardware: bool = True
    include_tools: bool = True
    include_safety_warnings: bool = True
    output_format: str = "markdown"  # markdown, html, pdf

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "project_name": self.project_name,
            "author": self.author,
            "include_bom": self.include_bom,
            "include_print_settings": self.include_print_settings,
            "include_hardware": self.include_hardware,
            "include_tools": self.include_tools,
            "include_safety_warnings": self.include_safety_warnings,
            "output_format": self.output_format,
        }


@dataclass
class HardwareItem:
    """Hardware item (screw, nut, etc.)."""
    name: str
    specification: str
    quantity: int
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "specification": self.specification,
            "quantity": self.quantity,
            "notes": self.notes,
        }


@dataclass
class AssemblyInstructions:
    """Complete assembly instructions."""
    success: bool
    project_name: str = ""
    parts: List[AssemblyPart] = field(default_factory=list)
    steps: List[AssemblyStep] = field(default_factory=list)
    hardware: List[HardwareItem] = field(default_factory=list)
    tools_required: List[str] = field(default_factory=list)
    total_print_time_hours: float = 0.0
    total_assembly_time_minutes: int = 0
    safety_warnings: List[str] = field(default_factory=list)
    generated_at: str = ""
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "project_name": self.project_name,
            "parts": [p.to_dict() for p in self.parts],
            "steps": [s.to_dict() for s in self.steps],
            "hardware": [h.to_dict() for h in self.hardware],
            "tools_required": self.tools_required,
            "total_print_time_hours": self.total_print_time_hours,
            "total_assembly_time_minutes": self.total_assembly_time_minutes,
            "safety_warnings": self.safety_warnings,
            "generated_at": self.generated_at,
            "error_message": self.error_message,
        }


class AssemblyGenerator:
    """
    Assembly instruction generator.

    Creates comprehensive assembly guides for multi-part prints.
    """

    def __init__(self, config: Optional[AssemblyConfig] = None):
        """
        Initialize assembly generator.

        Args:
            config: Assembly configuration
        """
        self.config = config or AssemblyConfig()

    def generate(
        self,
        parts: List[AssemblyPart],
        steps: Optional[List[AssemblyStep]] = None,
        hardware: Optional[List[HardwareItem]] = None,
    ) -> AssemblyInstructions:
        """
        Generate assembly instructions.

        Args:
            parts: List of parts
            steps: Optional pre-defined steps
            hardware: Optional hardware items

        Returns:
            Assembly instructions
        """
        if not parts:
            return AssemblyInstructions(
                success=False,
                error_message="No parts provided",
            )

        try:
            # Calculate totals
            total_print_time = sum(p.print_time_hours * p.quantity for p in parts)

            # Auto-generate steps if not provided
            if steps is None:
                steps = self._auto_generate_steps(parts, hardware or [])

            total_assembly_time = sum(s.estimated_time_minutes for s in steps)

            # Collect all tools needed
            tools = set()
            for step in steps:
                tools.update(step.tools_needed)

            # Add standard tools based on connection types
            for step in steps:
                if step.connection_type:
                    tools.update(self._get_tools_for_connection(step.connection_type))

            # Generate safety warnings
            safety_warnings = self._generate_safety_warnings(parts, steps, hardware or [])

            return AssemblyInstructions(
                success=True,
                project_name=self.config.project_name,
                parts=parts,
                steps=steps,
                hardware=hardware or [],
                tools_required=sorted(list(tools)),
                total_print_time_hours=round(total_print_time, 1),
                total_assembly_time_minutes=total_assembly_time,
                safety_warnings=safety_warnings,
                generated_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f"Assembly generation error: {e}")
            return AssemblyInstructions(
                success=False,
                error_message=str(e),
            )

    def _auto_generate_steps(
        self,
        parts: List[AssemblyPart],
        hardware: List[HardwareItem],
    ) -> List[AssemblyStep]:
        """Auto-generate assembly steps based on parts."""
        steps = []
        step_num = 1

        # Step 1: Print preparation
        steps.append(AssemblyStep(
            step_number=step_num,
            description="Print all parts according to the Bill of Materials. Ensure proper bed adhesion and layer settings.",
            parts_used=[],
            tips=[
                "Check each part for defects after printing",
                "Remove any stringing or support material",
                "Allow parts to cool completely before assembly",
            ],
            estimated_time_minutes=5,
        ))
        step_num += 1

        # Step 2: Parts preparation
        steps.append(AssemblyStep(
            step_number=step_num,
            description="Prepare all printed parts by removing support material and cleaning surfaces.",
            parts_used=[p.name for p in parts],
            tools_needed=["Flush cutters", "Sandpaper (220 grit)"],
            tips=[
                "Sand mating surfaces for better fit",
                "Check hole sizes with appropriate hardware",
            ],
            estimated_time_minutes=10,
        ))
        step_num += 1

        # Generate steps for each part (simplified auto-generation)
        for i, part in enumerate(parts):
            if i == 0:
                description = f"Begin with the {part.name}. This will be the base of the assembly."
            else:
                description = f"Attach the {part.name} to the previous assembly."

            steps.append(AssemblyStep(
                step_number=step_num,
                description=description,
                parts_used=[part.name],
                connection_type=ConnectionType.PRESS_FIT,
                tips=[f"Ensure {part.name} is properly aligned"],
                estimated_time_minutes=5,
            ))
            step_num += 1

        # Final inspection step
        steps.append(AssemblyStep(
            step_number=step_num,
            description="Perform final inspection. Check all connections and ensure proper alignment.",
            parts_used=[],
            tips=[
                "Test any moving parts for smooth operation",
                "Verify structural integrity",
            ],
            estimated_time_minutes=5,
        ))

        return steps

    def _get_tools_for_connection(self, connection_type: ConnectionType) -> List[str]:
        """Get tools needed for a connection type."""
        tools_map = {
            ConnectionType.SNAP_FIT: [],
            ConnectionType.SCREW: ["Screwdriver (appropriate size)"],
            ConnectionType.GLUE: ["CA glue", "Gloves"],
            ConnectionType.PRESS_FIT: ["Rubber mallet (optional)"],
            ConnectionType.SLIDE: [],
            ConnectionType.HINGE: ["Pin or rod"],
            ConnectionType.MAGNET: ["CA glue (for magnet installation)"],
            ConnectionType.THREADED: ["Soldering iron (for heat-set inserts)", "Gloves"],
        }
        return tools_map.get(connection_type, [])

    def _generate_safety_warnings(
        self,
        parts: List[AssemblyPart],
        steps: List[AssemblyStep],
        hardware: List[HardwareItem],
    ) -> List[str]:
        """Generate safety warnings based on assembly components."""
        warnings = []

        # Check for glue usage
        for step in steps:
            if step.connection_type == ConnectionType.GLUE:
                warnings.append("CA glue bonds skin instantly. Work in ventilated area.")
                break

        # Check for heat-set inserts
        for step in steps:
            if step.connection_type == ConnectionType.THREADED:
                warnings.append("Soldering iron gets extremely hot. Use with caution.")
                break

        # General warnings
        if any("sandpaper" in t.lower() for s in steps for t in s.tools_needed):
            warnings.append("Wear eye protection when sanding parts.")

        # Small parts warning
        if hardware:
            warnings.append("Contains small parts. Keep away from children.")

        return warnings

    def export_markdown(self, instructions: AssemblyInstructions) -> str:
        """Export instructions as Markdown."""
        lines = [
            f"# {instructions.project_name} Assembly Instructions",
            "",
            f"*Generated: {instructions.generated_at}*",
            "",
        ]

        # Safety warnings
        if instructions.safety_warnings:
            lines.extend([
                "## Safety Warnings",
                "",
            ])
            for warning in instructions.safety_warnings:
                lines.append(f"- {warning}")
            lines.append("")

        # Bill of Materials
        if self.config.include_bom:
            lines.extend([
                "## Bill of Materials",
                "",
                "### Printed Parts",
                "",
                "| Part | Quantity | Material | Color | Print Time |",
                "|------|----------|----------|-------|------------|",
            ])
            for part in instructions.parts:
                color = part.color or "Any"
                time_str = f"{part.print_time_hours:.1f}h" if part.print_time_hours else "-"
                lines.append(
                    f"| {part.name} | {part.quantity} | {part.material.upper()} | {color} | {time_str} |"
                )
            lines.append("")

        # Hardware
        if self.config.include_hardware and instructions.hardware:
            lines.extend([
                "### Hardware",
                "",
                "| Item | Specification | Quantity | Notes |",
                "|------|---------------|----------|-------|",
            ])
            for item in instructions.hardware:
                notes = item.notes or "-"
                lines.append(
                    f"| {item.name} | {item.specification} | {item.quantity} | {notes} |"
                )
            lines.append("")

        # Tools
        if self.config.include_tools and instructions.tools_required:
            lines.extend([
                "## Tools Required",
                "",
            ])
            for tool in instructions.tools_required:
                lines.append(f"- {tool}")
            lines.append("")

        # Summary
        lines.extend([
            "## Time Estimates",
            "",
            f"- **Total Print Time:** {instructions.total_print_time_hours:.1f} hours",
            f"- **Assembly Time:** {instructions.total_assembly_time_minutes} minutes",
            "",
        ])

        # Assembly Steps
        lines.extend([
            "## Assembly Steps",
            "",
        ])
        for step in instructions.steps:
            lines.append(f"### Step {step.step_number}")
            lines.append("")
            lines.append(step.description)
            lines.append("")

            if step.parts_used:
                lines.append(f"**Parts:** {', '.join(step.parts_used)}")
                lines.append("")

            if step.connection_type:
                lines.append(f"**Connection:** {step.connection_type.value.replace('_', ' ').title()}")
                lines.append("")

            if step.tools_needed:
                lines.append(f"**Tools:** {', '.join(step.tools_needed)}")
                lines.append("")

            if step.tips:
                lines.append("**Tips:**")
                for tip in step.tips:
                    lines.append(f"- {tip}")
                lines.append("")

            if step.warnings:
                lines.append("**Warnings:**")
                for warning in step.warnings:
                    lines.append(f"- {warning}")
                lines.append("")

        return "\n".join(lines)

    def export_html(self, instructions: AssemblyInstructions) -> str:
        """Export instructions as HTML."""
        md_content = self.export_markdown(instructions)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{instructions.project_name} Assembly Instructions</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        h3 {{ color: #666; }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        th {{ background-color: #f5f5f5; }}
        .warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 10px;
            margin: 10px 0;
        }}
        .tip {{
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 10px;
            margin: 10px 0;
        }}
        .step {{
            background-color: #f8f9fa;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <h1>{instructions.project_name} Assembly Instructions</h1>
    <p><em>Generated: {instructions.generated_at}</em></p>
"""

        # Safety warnings
        if instructions.safety_warnings:
            html += "<h2>Safety Warnings</h2>"
            for warning in instructions.safety_warnings:
                html += f'<div class="warning">{warning}</div>'

        # Bill of Materials
        if self.config.include_bom:
            html += """
    <h2>Bill of Materials</h2>
    <h3>Printed Parts</h3>
    <table>
        <tr><th>Part</th><th>Quantity</th><th>Material</th><th>Color</th><th>Print Time</th></tr>
"""
            for part in instructions.parts:
                color = part.color or "Any"
                time_str = f"{part.print_time_hours:.1f}h" if part.print_time_hours else "-"
                html += f"        <tr><td>{part.name}</td><td>{part.quantity}</td><td>{part.material.upper()}</td><td>{color}</td><td>{time_str}</td></tr>\n"
            html += "    </table>\n"

        # Hardware
        if self.config.include_hardware and instructions.hardware:
            html += """
    <h3>Hardware</h3>
    <table>
        <tr><th>Item</th><th>Specification</th><th>Quantity</th><th>Notes</th></tr>
"""
            for item in instructions.hardware:
                notes = item.notes or "-"
                html += f"        <tr><td>{item.name}</td><td>{item.specification}</td><td>{item.quantity}</td><td>{notes}</td></tr>\n"
            html += "    </table>\n"

        # Tools
        if self.config.include_tools and instructions.tools_required:
            html += "    <h2>Tools Required</h2>\n    <ul>\n"
            for tool in instructions.tools_required:
                html += f"        <li>{tool}</li>\n"
            html += "    </ul>\n"

        # Time estimates
        html += f"""
    <h2>Time Estimates</h2>
    <ul>
        <li><strong>Total Print Time:</strong> {instructions.total_print_time_hours:.1f} hours</li>
        <li><strong>Assembly Time:</strong> {instructions.total_assembly_time_minutes} minutes</li>
    </ul>
"""

        # Assembly Steps
        html += "    <h2>Assembly Steps</h2>\n"
        for step in instructions.steps:
            html += f"""
    <div class="step">
        <h3>Step {step.step_number}</h3>
        <p>{step.description}</p>
"""
            if step.parts_used:
                html += f"        <p><strong>Parts:</strong> {', '.join(step.parts_used)}</p>\n"
            if step.connection_type:
                html += f"        <p><strong>Connection:</strong> {step.connection_type.value.replace('_', ' ').title()}</p>\n"
            if step.tools_needed:
                html += f"        <p><strong>Tools:</strong> {', '.join(step.tools_needed)}</p>\n"
            if step.tips:
                for tip in step.tips:
                    html += f'        <div class="tip">{tip}</div>\n'
            if step.warnings:
                for warning in step.warnings:
                    html += f'        <div class="warning">{warning}</div>\n'
            html += "    </div>\n"

        html += """
</body>
</html>
"""
        return html

    def save(
        self,
        instructions: AssemblyInstructions,
        output_path: str,
    ) -> bool:
        """Save instructions to file."""
        try:
            path = Path(output_path)

            if self.config.output_format == "html" or path.suffix == ".html":
                content = self.export_html(instructions)
            else:
                content = self.export_markdown(instructions)

            path.write_text(content)
            logger.info(f"Saved assembly instructions to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving instructions: {e}")
            return False


# Convenience functions
def create_generator(
    project_name: str = "Assembly",
    output_format: str = "markdown",
) -> AssemblyGenerator:
    """Create an assembly generator with specified settings."""
    config = AssemblyConfig(
        project_name=project_name,
        output_format=output_format,
    )
    return AssemblyGenerator(config=config)


def generate_instructions(
    parts: List[dict],
    project_name: str = "Assembly",
) -> AssemblyInstructions:
    """
    Quick assembly instruction generation.

    Args:
        parts: List of part dictionaries with name, file_path, quantity
        project_name: Name of the project

    Returns:
        Assembly instructions
    """
    generator = create_generator(project_name=project_name)

    assembly_parts = []
    for p in parts:
        assembly_parts.append(AssemblyPart(
            name=p.get("name", "Part"),
            file_path=p.get("file_path", ""),
            quantity=p.get("quantity", 1),
            material=p.get("material", "pla"),
            color=p.get("color"),
            print_time_hours=p.get("print_time_hours", 0.0),
        ))

    return generator.generate(assembly_parts)
