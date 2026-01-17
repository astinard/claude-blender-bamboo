"""
Print Preview Module for Multi-Color 3D Printing.

Generates detailed previews of print jobs before sending to printer, showing:
- Color-to-AMS slot mapping
- Material usage estimates
- Warnings for missing colors or compatibility issues
- Print time and cost estimates
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
import math

from .ams_manager import AMSManager, AMSSlot, FilamentInfo


@dataclass
class ColorUsage:
    """Usage information for a single color in the model."""
    color: Tuple[float, float, float]  # RGB 0-1
    color_name: str
    triangle_count: int
    estimated_volume_mm3: float  # Estimated material volume
    percentage: float  # Percentage of total model
    mapped_slot: Optional[int] = None  # AMS slot index, None if unmapped


@dataclass
class PrintPreviewWarning:
    """Warning or notice about a print job."""
    level: str  # 'info', 'warning', 'error'
    message: str
    suggestion: str = ""


@dataclass
class PrintPreview:
    """Complete preview of a print job."""
    # Model info
    model_name: str
    model_volume_mm3: float
    triangle_count: int

    # Colors
    colors: List[ColorUsage]
    color_mapping: Dict[int, int]  # color_index -> ams_slot

    # Estimates
    estimated_print_time_seconds: float
    estimated_filament_grams: float
    estimated_cost_usd: float

    # Warnings
    warnings: List[PrintPreviewWarning] = field(default_factory=list)

    # Status
    is_printable: bool = True
    missing_colors: List[Tuple[float, float, float]] = field(default_factory=list)

    @property
    def estimated_print_time_formatted(self) -> str:
        """Get print time as human-readable string."""
        hours = int(self.estimated_print_time_seconds // 3600)
        minutes = int((self.estimated_print_time_seconds % 3600) // 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    @property
    def color_count(self) -> int:
        """Number of unique colors in model."""
        return len(self.colors)

    @property
    def mapped_color_count(self) -> int:
        """Number of colors successfully mapped to AMS slots."""
        return sum(1 for c in self.colors if c.mapped_slot is not None)


class PrintPreviewGenerator:
    """
    Generates print previews for multi-color 3D models.

    Usage:
        generator = PrintPreviewGenerator(ams_manager)

        # From mesh data
        preview = generator.generate_preview(
            model_name="my_model",
            colors=[(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
            triangle_counts=[1000, 500],
            total_volume_mm3=15000
        )

        # Display preview
        print(generator.format_preview(preview))
    """

    # Default print settings for estimation
    DEFAULT_LAYER_HEIGHT = 0.2  # mm
    DEFAULT_PRINT_SPEED = 60  # mm/s average
    DEFAULT_FILAMENT_DENSITY = 1.24  # g/cm³ (PLA)
    DEFAULT_FILAMENT_COST_PER_KG = 25.0  # USD

    def __init__(self, ams_manager: AMSManager = None):
        """
        Initialize preview generator.

        Args:
            ams_manager: AMS manager with loaded filament info
        """
        self.ams_manager = ams_manager or AMSManager()

    def generate_preview(
        self,
        model_name: str,
        colors: List[Tuple[float, float, float]],
        triangle_counts: List[int],
        total_volume_mm3: float,
        material_type: str = "PLA"
    ) -> PrintPreview:
        """
        Generate a complete print preview.

        Args:
            model_name: Name of the model
            colors: List of RGB colors (0-1) used in model
            triangle_counts: Number of triangles for each color
            total_volume_mm3: Total model volume in mm³
            material_type: Primary material type for estimation

        Returns:
            PrintPreview with all details
        """
        warnings = []
        missing_colors = []

        # Calculate color usage
        total_triangles = sum(triangle_counts)
        color_usages = []

        for i, (color, tri_count) in enumerate(zip(colors, triangle_counts)):
            percentage = (tri_count / total_triangles * 100) if total_triangles > 0 else 0
            volume = total_volume_mm3 * (percentage / 100)

            color_usages.append(ColorUsage(
                color=color,
                color_name=self._color_to_name(color),
                triangle_count=tri_count,
                estimated_volume_mm3=volume,
                percentage=percentage
            ))

        # Map colors to AMS slots
        color_mapping = {}
        loaded_slots = self.ams_manager.get_loaded_slots()

        for i, usage in enumerate(color_usages):
            best_slot = self.ams_manager.find_closest_slot(usage.color)
            if best_slot and not best_slot.is_empty:
                slot_idx = best_slot.global_index
                color_mapping[i] = slot_idx
                usage.mapped_slot = slot_idx

                # Check color match quality
                distance = self.ams_manager.color_distance(
                    usage.color,
                    best_slot.filament.color
                )
                if distance > 0.3:
                    warnings.append(PrintPreviewWarning(
                        level="warning",
                        message=f"Color '{usage.color_name}' mapped to '{best_slot.filament.color_name}' (poor match)",
                        suggestion=f"Load a {usage.color_name} filament for better results"
                    ))
            else:
                missing_colors.append(usage.color)
                warnings.append(PrintPreviewWarning(
                    level="error",
                    message=f"No AMS slot found for color '{usage.color_name}'",
                    suggestion=f"Load a {usage.color_name} filament into an AMS slot"
                ))

        # Estimate print time (rough calculation)
        # Assume average path length per layer based on volume
        estimated_layers = self._estimate_layer_count(total_volume_mm3)
        time_per_layer = 30  # seconds average
        color_change_time = 20  # seconds per change
        estimated_changes = max(0, len(colors) - 1) * estimated_layers * 0.3  # ~30% layers have changes

        estimated_time = (
            estimated_layers * time_per_layer +
            estimated_changes * color_change_time
        )

        # Estimate filament usage
        filament_volume_cm3 = total_volume_mm3 / 1000 * 1.15  # Add 15% for infill, supports
        filament_grams = filament_volume_cm3 * self.DEFAULT_FILAMENT_DENSITY

        # Estimate cost
        cost = (filament_grams / 1000) * self.DEFAULT_FILAMENT_COST_PER_KG

        # Check printability
        is_printable = len(missing_colors) == 0

        if len(colors) > 16:
            is_printable = False
            warnings.append(PrintPreviewWarning(
                level="error",
                message=f"Model uses {len(colors)} colors, max is 16",
                suggestion="Reduce color count by merging similar colors"
            ))

        if total_volume_mm3 > 300 * 300 * 300:  # Larger than build volume
            warnings.append(PrintPreviewWarning(
                level="warning",
                message="Model may exceed build volume",
                suggestion="Check model dimensions against printer specs"
            ))

        # Add info about color changes
        if len(colors) > 1:
            warnings.append(PrintPreviewWarning(
                level="info",
                message=f"Multi-color print: {len(colors)} colors, ~{int(estimated_changes)} color changes",
                suggestion=""
            ))

        return PrintPreview(
            model_name=model_name,
            model_volume_mm3=total_volume_mm3,
            triangle_count=total_triangles,
            colors=color_usages,
            color_mapping=color_mapping,
            estimated_print_time_seconds=estimated_time,
            estimated_filament_grams=filament_grams,
            estimated_cost_usd=cost,
            warnings=warnings,
            is_printable=is_printable,
            missing_colors=missing_colors
        )

    def format_preview(self, preview: PrintPreview) -> str:
        """
        Format preview as human-readable text.

        Args:
            preview: PrintPreview to format

        Returns:
            Formatted string
        """
        lines = [
            "=" * 60,
            f"PRINT PREVIEW: {preview.model_name}",
            "=" * 60,
            "",
            "MODEL INFO:",
            f"  Volume: {preview.model_volume_mm3:.1f} mm³ ({preview.model_volume_mm3/1000:.1f} cm³)",
            f"  Triangles: {preview.triangle_count:,}",
            f"  Colors: {preview.color_count}",
            "",
            "ESTIMATES:",
            f"  Print Time: {preview.estimated_print_time_formatted}",
            f"  Filament: {preview.estimated_filament_grams:.1f}g",
            f"  Cost: ${preview.estimated_cost_usd:.2f}",
            "",
            "COLOR MAPPING:",
        ]

        for i, color in enumerate(preview.colors):
            slot_info = "NOT MAPPED"
            if color.mapped_slot is not None:
                slot = self.ams_manager.get_slot_by_index(color.mapped_slot)
                slot_info = slot.display_name

            rgb_str = f"RGB({int(color.color[0]*255)}, {int(color.color[1]*255)}, {int(color.color[2]*255)})"
            lines.append(
                f"  {i+1}. {color.color_name} {rgb_str}"
            )
            lines.append(
                f"      → {slot_info}"
            )
            lines.append(
                f"      {color.percentage:.1f}% of model ({color.triangle_count:,} triangles)"
            )

        if preview.warnings:
            lines.append("")
            lines.append("WARNINGS:")
            for warning in preview.warnings:
                icon = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(warning.level, "•")
                lines.append(f"  {icon} {warning.message}")
                if warning.suggestion:
                    lines.append(f"      Suggestion: {warning.suggestion}")

        lines.append("")
        lines.append("=" * 60)
        status = "✅ READY TO PRINT" if preview.is_printable else "❌ NOT PRINTABLE"
        lines.append(f"STATUS: {status}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def format_preview_compact(self, preview: PrintPreview) -> str:
        """
        Format preview as compact single-line summary.

        Args:
            preview: PrintPreview to format

        Returns:
            Compact summary string
        """
        status = "✅" if preview.is_printable else "❌"
        return (
            f"{status} {preview.model_name}: "
            f"{preview.color_count} colors, "
            f"{preview.estimated_print_time_formatted}, "
            f"{preview.estimated_filament_grams:.0f}g, "
            f"${preview.estimated_cost_usd:.2f}"
        )

    def _color_to_name(self, color: Tuple[float, float, float]) -> str:
        """Convert RGB color to approximate name."""
        r, g, b = color

        # Check for grayscale
        if abs(r - g) < 0.1 and abs(g - b) < 0.1:
            brightness = (r + g + b) / 3
            if brightness > 0.9:
                return "White"
            elif brightness < 0.1:
                return "Black"
            else:
                return "Gray"

        # Determine dominant color
        max_channel = max(r, g, b)

        if r == max_channel:
            if g > 0.5:
                return "Yellow" if b < 0.3 else "Pink"
            elif b > 0.5:
                return "Magenta"
            else:
                return "Red"
        elif g == max_channel:
            if r > 0.5:
                return "Yellow"
            elif b > 0.5:
                return "Cyan"
            else:
                return "Green"
        else:  # b == max_channel
            if r > 0.5:
                return "Purple"
            elif g > 0.5:
                return "Cyan"
            else:
                return "Blue"

    def _estimate_layer_count(self, volume_mm3: float) -> int:
        """Estimate number of print layers from volume."""
        # Assume cubic-ish shape, estimate height
        side_length = volume_mm3 ** (1/3)
        layers = side_length / self.DEFAULT_LAYER_HEIGHT
        return max(10, int(layers))


def create_print_preview(
    model_name: str,
    colors: List[Tuple[float, float, float]],
    triangle_counts: List[int],
    total_volume_mm3: float,
    ams_config: Dict[int, Tuple[str, Tuple[float, float, float], str]] = None
) -> PrintPreview:
    """
    Convenience function to create a print preview.

    Args:
        model_name: Name of the model
        colors: List of RGB colors (0-1)
        triangle_counts: Triangle count per color
        total_volume_mm3: Total volume
        ams_config: Optional AMS configuration
                   {slot_index: (color_name, rgb_color, material_type)}

    Returns:
        PrintPreview
    """
    ams = AMSManager()

    # Configure AMS if provided
    if ams_config:
        for slot_idx, (color_name, rgb, material) in ams_config.items():
            unit = slot_idx // 4
            slot = slot_idx % 4
            ams.set_slot(unit, slot, FilamentInfo(
                color=rgb,
                color_name=color_name,
                material_type=material
            ))

    generator = PrintPreviewGenerator(ams)
    return generator.generate_preview(
        model_name=model_name,
        colors=colors,
        triangle_counts=triangle_counts,
        total_volume_mm3=total_volume_mm3
    )


# Test/demo code
if __name__ == "__main__":
    # Create AMS manager with some filaments loaded
    ams = AMSManager()
    ams.set_slot(0, 0, FilamentInfo(
        color=(1.0, 1.0, 1.0),
        color_name="White",
        material_type="PLA"
    ))
    ams.set_slot(0, 1, FilamentInfo(
        color=(1.0, 0.0, 0.0),
        color_name="Red",
        material_type="PLA"
    ))
    ams.set_slot(0, 2, FilamentInfo(
        color=(0.0, 0.0, 1.0),
        color_name="Blue",
        material_type="PLA"
    ))
    ams.set_slot(0, 3, FilamentInfo(
        color=(0.0, 0.0, 0.0),
        color_name="Black",
        material_type="PLA"
    ))

    # Generate preview
    generator = PrintPreviewGenerator(ams)
    preview = generator.generate_preview(
        model_name="Phone Case",
        colors=[
            (1.0, 1.0, 1.0),  # White body
            (1.0, 0.0, 0.0),  # Red accent
            (0.0, 0.0, 0.0),  # Black logo
        ],
        triangle_counts=[5000, 500, 200],
        total_volume_mm3=15000
    )

    print(generator.format_preview(preview))
    print()
    print("Compact:", generator.format_preview_compact(preview))
