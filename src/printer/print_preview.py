"""Print preview with AMS slot visualization.

P4.8 / P1.7: Print Preview Enhancement

Features:
- Visual AMS slot mapping
- Color preview render
- HTML export for sharing
- Material usage estimation
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

from src.materials.material_db import get_material, Material
from src.materials.compatibility import check_multi_material_compatibility
from src.utils import get_logger, format_duration

logger = get_logger("printer.preview")


# Common filament colors (CSS color values)
FILAMENT_COLORS = {
    "white": "#FFFFFF",
    "black": "#1A1A1A",
    "red": "#E63946",
    "blue": "#457B9D",
    "green": "#2A9D8F",
    "yellow": "#F4A261",
    "orange": "#E76F51",
    "purple": "#6A4C93",
    "pink": "#FFB5C5",
    "gray": "#808080",
    "silver": "#C0C0C0",
    "gold": "#FFD700",
    "transparent": "rgba(200, 200, 200, 0.3)",
    "natural": "#F5F5DC",
    "jade white": "#E8F5E9",
    "matte black": "#2D2D2D",
}


@dataclass
class AMSSlotConfig:
    """Configuration for a single AMS slot."""

    slot: int  # 1-4 for AMS, 5-8 for AMS Lite
    material: str  # Material type (pla, petg, etc.)
    color: str  # Color name or hex code
    brand: Optional[str] = None
    spool_id: Optional[str] = None  # Link to inventory

    @property
    def color_hex(self) -> str:
        """Get the CSS color hex code."""
        if self.color.startswith("#"):
            return self.color
        return FILAMENT_COLORS.get(self.color.lower(), "#808080")

    @property
    def material_obj(self) -> Optional[Material]:
        """Get the Material object."""
        return get_material(self.material)


@dataclass
class LayerInfo:
    """Information about a single layer."""

    layer_number: int
    z_height: float  # mm
    material_slot: int  # Which AMS slot is used
    line_width: float = 0.4  # mm
    layer_height: float = 0.2  # mm


@dataclass
class PrintEstimate:
    """Estimated print statistics."""

    total_time_seconds: float
    material_usage_grams: Dict[int, float]  # slot -> grams
    total_layers: int
    max_z_height: float
    print_volume: Tuple[float, float, float]  # x, y, z in mm


@dataclass
class PrintPreview:
    """Complete print preview information."""

    filename: str
    ams_slots: List[AMSSlotConfig]
    estimate: Optional[PrintEstimate] = None
    layers: List[LayerInfo] = field(default_factory=list)
    thumbnail_path: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    compatibility_level: Optional[str] = None

    def get_slot(self, slot_num: int) -> Optional[AMSSlotConfig]:
        """Get AMS slot by number."""
        for slot in self.ams_slots:
            if slot.slot == slot_num:
                return slot
        return None

    def get_materials(self) -> List[str]:
        """Get list of materials used."""
        return [s.material for s in self.ams_slots]

    def get_color_preview(self) -> Dict[int, str]:
        """Get slot -> color mapping for preview."""
        return {s.slot: s.color_hex for s in self.ams_slots}

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "filename": self.filename,
            "ams_slots": [
                {
                    "slot": s.slot,
                    "material": s.material,
                    "color": s.color,
                    "color_hex": s.color_hex,
                    "brand": s.brand,
                }
                for s in self.ams_slots
            ],
            "estimate": {
                "total_time": self.estimate.total_time_seconds if self.estimate else None,
                "total_time_formatted": format_duration(self.estimate.total_time_seconds)
                if self.estimate else None,
                "material_usage": self.estimate.material_usage_grams if self.estimate else {},
                "total_layers": self.estimate.total_layers if self.estimate else 0,
                "max_z_height": self.estimate.max_z_height if self.estimate else 0,
            },
            "warnings": self.warnings,
            "compatibility_level": self.compatibility_level,
        }


def generate_preview(
    file_path: str,
    ams_config: List[AMSSlotConfig],
    check_compatibility: bool = True,
) -> PrintPreview:
    """
    Generate a print preview from a model file.

    Args:
        file_path: Path to 3MF, STL, or GCODE file
        ams_config: AMS slot configuration
        check_compatibility: Whether to check material compatibility

    Returns:
        PrintPreview with all information
    """
    path = Path(file_path)
    warnings = []

    # Check material compatibility if requested
    compatibility_level = None
    if check_compatibility and len(ams_config) > 1:
        materials = [s.material for s in ams_config]
        result = check_multi_material_compatibility(materials)
        compatibility_level = result.overall_compatibility.value
        warnings.extend(result.warnings)

    # Check for material-specific warnings
    for slot in ams_config:
        mat = slot.material_obj
        if mat:
            if mat.properties.abrasive:
                warnings.append(f"Slot {slot.slot} ({mat.name}): Requires hardened steel nozzle")
            if mat.properties.toxic_fumes:
                warnings.append(f"Slot {slot.slot} ({mat.name}): Ensure proper ventilation")
            if mat.properties.hygroscopic:
                warnings.append(f"Slot {slot.slot} ({mat.name}): Store in dry box when not printing")

    # Create estimate based on file type
    estimate = None
    if path.suffix.lower() == ".gcode":
        estimate = _parse_gcode_estimate(path)
    elif path.suffix.lower() == ".3mf":
        estimate = _parse_3mf_estimate(path)
    else:
        # For STL files, estimate based on typical slicing settings
        estimate = _estimate_from_stl(path)

    preview = PrintPreview(
        filename=path.name,
        ams_slots=ams_config,
        estimate=estimate,
        warnings=warnings,
        compatibility_level=compatibility_level,
    )

    logger.info(f"Generated preview for {path.name}")
    return preview


def _parse_gcode_estimate(path: Path) -> Optional[PrintEstimate]:
    """Parse print estimate from GCODE file."""
    if not path.exists():
        return None

    try:
        # Read first 100 lines for metadata
        with open(path, "r") as f:
            lines = [f.readline() for _ in range(100)]

        total_time = None
        material_usage = {}
        total_layers = 0
        max_z = 0

        for line in lines:
            line = line.strip()
            # Bambu/PrusaSlicer format
            if "; estimated printing time" in line.lower():
                # Parse time from comment
                parts = line.split("=")
                if len(parts) > 1:
                    total_time = _parse_time_string(parts[1].strip())
            elif "; total filament used" in line.lower():
                parts = line.split("=")
                if len(parts) > 1:
                    try:
                        grams = float(parts[1].strip().replace("g", "").strip())
                        material_usage[1] = grams
                    except ValueError:
                        pass
            elif "; total layers" in line.lower():
                parts = line.split("=")
                if len(parts) > 1:
                    try:
                        total_layers = int(parts[1].strip())
                    except ValueError:
                        pass

        return PrintEstimate(
            total_time_seconds=total_time or 0,
            material_usage_grams=material_usage,
            total_layers=total_layers,
            max_z_height=max_z,
            print_volume=(0, 0, max_z),
        )

    except Exception as e:
        logger.warning(f"Failed to parse GCODE: {e}")
        return None


def _parse_3mf_estimate(path: Path) -> Optional[PrintEstimate]:
    """Parse print estimate from 3MF file."""
    # 3MF is a ZIP file with XML content
    # For now, return a placeholder
    return PrintEstimate(
        total_time_seconds=0,
        material_usage_grams={},
        total_layers=0,
        max_z_height=0,
        print_volume=(0, 0, 0),
    )


def _estimate_from_stl(path: Path) -> Optional[PrintEstimate]:
    """Estimate print parameters from STL file dimensions."""
    # Would use trimesh here to get actual dimensions
    # For now, return placeholder
    return PrintEstimate(
        total_time_seconds=0,
        material_usage_grams={},
        total_layers=0,
        max_z_height=0,
        print_volume=(0, 0, 0),
    )


def _parse_time_string(time_str: str) -> float:
    """Parse time string like '2h 30m 15s' into seconds."""
    seconds = 0
    parts = time_str.lower().split()

    for part in parts:
        if "h" in part:
            try:
                seconds += int(part.replace("h", "")) * 3600
            except ValueError:
                pass
        elif "m" in part:
            try:
                seconds += int(part.replace("m", "")) * 60
            except ValueError:
                pass
        elif "s" in part:
            try:
                seconds += int(part.replace("s", ""))
            except ValueError:
                pass

    return seconds


def export_preview_html(preview: PrintPreview, output_path: Optional[str] = None) -> str:
    """
    Export print preview as shareable HTML file.

    Args:
        preview: PrintPreview to export
        output_path: Optional output path (default: same name as file)

    Returns:
        Path to generated HTML file
    """
    if output_path is None:
        output_path = f"output/{Path(preview.filename).stem}_preview.html"

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Generate AMS slot visualization
    ams_slots_html = ""
    for slot in preview.ams_slots:
        mat = slot.material_obj
        mat_name = mat.name if mat else slot.material.upper()
        ams_slots_html += f"""
        <div class="ams-slot">
            <div class="slot-color" style="background-color: {slot.color_hex};"></div>
            <div class="slot-info">
                <div class="slot-number">Slot {slot.slot}</div>
                <div class="slot-material">{mat_name}</div>
                <div class="slot-color-name">{slot.color}</div>
                {f'<div class="slot-brand">{slot.brand}</div>' if slot.brand else ''}
            </div>
        </div>
        """

    # Generate warnings HTML
    warnings_html = ""
    if preview.warnings:
        warnings_html = '<div class="warnings"><h3>Warnings</h3><ul>'
        for warning in preview.warnings:
            warnings_html += f"<li>{warning}</li>"
        warnings_html += "</ul></div>"

    # Generate estimate HTML
    estimate_html = ""
    if preview.estimate and preview.estimate.total_time_seconds > 0:
        estimate_html = f"""
        <div class="estimate">
            <h3>Print Estimate</h3>
            <div class="estimate-item">
                <span class="label">Time:</span>
                <span class="value">{format_duration(preview.estimate.total_time_seconds)}</span>
            </div>
            <div class="estimate-item">
                <span class="label">Layers:</span>
                <span class="value">{preview.estimate.total_layers}</span>
            </div>
            <div class="estimate-item">
                <span class="label">Height:</span>
                <span class="value">{preview.estimate.max_z_height:.1f}mm</span>
            </div>
        </div>
        """

    # Compatibility badge
    compat_html = ""
    if preview.compatibility_level:
        color_map = {
            "excellent": "#4CAF50",
            "good": "#8BC34A",
            "fair": "#FFC107",
            "poor": "#FF5722",
            "incompatible": "#F44336",
        }
        color = color_map.get(preview.compatibility_level, "#9E9E9E")
        compat_html = f"""
        <div class="compatibility" style="background-color: {color};">
            Material Compatibility: {preview.compatibility_level.upper()}
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Print Preview: {preview.filename}</title>
    <style>
        :root {{
            --bg-color: #1a1a2e;
            --card-bg: #16213e;
            --text-color: #e8e8e8;
            --accent-color: #0f3460;
            --highlight: #e94560;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        h1 {{
            color: var(--highlight);
            margin-bottom: 5px;
        }}
        .subtitle {{
            color: #888;
            margin-bottom: 30px;
        }}
        .card {{
            background-color: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .ams-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }}
        .ams-slot {{
            background-color: var(--accent-color);
            border-radius: 8px;
            padding: 15px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .slot-color {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 2px solid rgba(255,255,255,0.2);
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        .slot-number {{
            font-size: 12px;
            color: #888;
        }}
        .slot-material {{
            font-weight: bold;
        }}
        .slot-color-name {{
            font-size: 12px;
            text-transform: capitalize;
        }}
        .slot-brand {{
            font-size: 11px;
            color: #666;
        }}
        .warnings {{
            background-color: rgba(255, 152, 0, 0.1);
            border-left: 3px solid #FF9800;
            padding: 15px;
            border-radius: 0 8px 8px 0;
        }}
        .warnings h3 {{
            color: #FF9800;
            margin-top: 0;
        }}
        .warnings ul {{
            margin-bottom: 0;
            padding-left: 20px;
        }}
        .warnings li {{
            margin-bottom: 8px;
        }}
        .estimate {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
        }}
        .estimate h3 {{
            grid-column: 1 / -1;
            margin-top: 0;
        }}
        .estimate-item {{
            background-color: var(--accent-color);
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }}
        .estimate-item .label {{
            display: block;
            font-size: 12px;
            color: #888;
        }}
        .estimate-item .value {{
            display: block;
            font-size: 18px;
            font-weight: bold;
            margin-top: 5px;
        }}
        .compatibility {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 20px;
        }}
        .footer {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Print Preview</h1>
        <p class="subtitle">{preview.filename}</p>

        {compat_html}

        <div class="card">
            <h3>AMS Slot Configuration</h3>
            <div class="ams-container">
                {ams_slots_html}
            </div>
        </div>

        {warnings_html}

        <div class="card">
            {estimate_html if estimate_html else '<p style="color: #666;">No print estimate available</p>'}
        </div>

        <div class="footer">
            Generated by Claude Fab Lab
        </div>
    </div>
</body>
</html>
"""

    with open(path, "w") as f:
        f.write(html)

    logger.info(f"Exported preview HTML to {path}")
    return str(path)


def create_ams_config(
    materials: List[str],
    colors: Optional[List[str]] = None,
    brands: Optional[List[str]] = None,
) -> List[AMSSlotConfig]:
    """
    Helper to create AMS configuration from material list.

    Args:
        materials: List of material names
        colors: Optional list of colors (default: auto-assign)
        brands: Optional list of brand names

    Returns:
        List of AMSSlotConfig
    """
    default_colors = ["white", "black", "red", "blue", "green", "yellow", "orange", "purple"]

    if colors is None:
        colors = default_colors[:len(materials)]
    if brands is None:
        brands = [None] * len(materials)

    configs = []
    for i, (mat, color, brand) in enumerate(zip(materials, colors, brands)):
        configs.append(AMSSlotConfig(
            slot=i + 1,
            material=mat.lower(),
            color=color,
            brand=brand,
        ))

    return configs
