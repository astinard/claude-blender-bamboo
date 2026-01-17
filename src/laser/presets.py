"""
Laser Presets for Bambu Lab H2D 40W Laser Module.

Contains optimized power, speed, and pass settings for various materials.
These presets are tuned for the 40W diode laser on the H2D.
"""

from dataclasses import dataclass
from typing import Dict, Optional, List


@dataclass
class LaserPreset:
    """Laser operation preset for a specific material and operation."""
    # Identity
    name: str
    material: str
    thickness: float  # mm
    operation: str  # 'cut', 'engrave', 'score'

    # Power settings
    power: int  # 0-100%
    power_min: int = 0  # For variable power (0 = same as power)

    # Speed settings
    speed: int  # mm/s
    speed_min: int = 0  # For variable speed

    # Pass settings
    passes: int = 1
    pass_depth: float = 0.0  # Z step per pass (0 = no step)

    # Advanced settings
    air_assist: bool = True
    focus_offset: float = 0.0  # mm from surface
    line_interval: float = 0.1  # mm (for engraving)
    bidirectional: bool = True  # For engraving

    # Safety
    fire_risk: str = "low"  # 'low', 'medium', 'high'
    notes: str = ""


# Pre-configured laser presets for common materials
# Optimized for Bambu Lab H2D 40W laser

LASER_PRESETS: Dict[str, LaserPreset] = {
    # =====================
    # WOOD - Cutting
    # =====================
    'wood_3mm_cut': LaserPreset(
        name="3mm Wood Cut",
        material="wood",
        thickness=3.0,
        operation="cut",
        power=70,
        speed=10,
        passes=1,
        air_assist=True,
        fire_risk="medium",
        notes="Clean cut with slight charring on edges"
    ),

    'wood_5mm_cut': LaserPreset(
        name="5mm Wood Cut",
        material="wood",
        thickness=5.0,
        operation="cut",
        power=85,
        speed=6,
        passes=1,
        air_assist=True,
        fire_risk="medium",
        notes="May need 2 passes for clean through-cut"
    ),

    'wood_10mm_cut': LaserPreset(
        name="10mm Wood Cut",
        material="wood",
        thickness=10.0,
        operation="cut",
        power=100,
        speed=3,
        passes=2,
        pass_depth=5.0,
        air_assist=True,
        fire_risk="high",
        notes="Multiple passes required. Watch for fire."
    ),

    'balsa_3mm_cut': LaserPreset(
        name="3mm Balsa Cut",
        material="balsa",
        thickness=3.0,
        operation="cut",
        power=30,
        speed=25,
        passes=1,
        air_assist=True,
        fire_risk="high",
        notes="Very fast - high fire risk"
    ),

    # =====================
    # WOOD - Engraving
    # =====================
    'wood_engrave_light': LaserPreset(
        name="Wood Light Engrave",
        material="wood",
        thickness=0.0,
        operation="engrave",
        power=20,
        speed=200,
        line_interval=0.1,
        bidirectional=True,
        fire_risk="low",
        notes="Light surface marking"
    ),

    'wood_engrave_deep': LaserPreset(
        name="Wood Deep Engrave",
        material="wood",
        thickness=0.0,
        operation="engrave",
        power=40,
        speed=150,
        line_interval=0.08,
        bidirectional=True,
        fire_risk="medium",
        notes="Deeper engraving with contrast"
    ),

    # =====================
    # ACRYLIC - Cutting (Dark colors only!)
    # =====================
    'acrylic_3mm_cut': LaserPreset(
        name="3mm Dark Acrylic Cut",
        material="acrylic_dark",
        thickness=3.0,
        operation="cut",
        power=80,
        speed=8,
        passes=1,
        air_assist=True,
        fire_risk="low",
        notes="DARK acrylic only! Clear acrylic is transparent to blue laser."
    ),

    'acrylic_5mm_cut': LaserPreset(
        name="5mm Dark Acrylic Cut",
        material="acrylic_dark",
        thickness=5.0,
        operation="cut",
        power=100,
        speed=4,
        passes=1,
        air_assist=True,
        fire_risk="low",
        notes="DARK colors only. Clean polished edges."
    ),

    'acrylic_engrave': LaserPreset(
        name="Acrylic Engrave",
        material="acrylic",
        thickness=0.0,
        operation="engrave",
        power=25,
        speed=200,
        line_interval=0.1,
        fire_risk="low",
        notes="Creates frosted appearance"
    ),

    # =====================
    # LEATHER
    # =====================
    'leather_2mm_cut': LaserPreset(
        name="2mm Leather Cut",
        material="leather",
        thickness=2.0,
        operation="cut",
        power=50,
        speed=15,
        passes=1,
        air_assist=True,
        fire_risk="medium",
        notes="Good ventilation required"
    ),

    'leather_3mm_cut': LaserPreset(
        name="3mm Leather Cut",
        material="leather",
        thickness=3.0,
        operation="cut",
        power=65,
        speed=10,
        passes=1,
        air_assist=True,
        fire_risk="medium",
        notes="Thicker leather for wallets, belts"
    ),

    'leather_engrave': LaserPreset(
        name="Leather Engrave",
        material="leather",
        thickness=0.0,
        operation="engrave",
        power=15,
        speed=300,
        line_interval=0.1,
        bidirectional=True,
        fire_risk="low",
        notes="Creates beautiful contrast"
    ),

    # =====================
    # CARDBOARD / PAPER
    # =====================
    'cardboard_2mm_cut': LaserPreset(
        name="2mm Cardboard Cut",
        material="cardboard",
        thickness=2.0,
        operation="cut",
        power=25,
        speed=30,
        passes=1,
        air_assist=True,
        fire_risk="high",
        notes="Watch closely for fire!"
    ),

    'cardstock_cut': LaserPreset(
        name="Cardstock Cut",
        material="cardstock",
        thickness=0.3,
        operation="cut",
        power=10,
        speed=50,
        passes=1,
        air_assist=True,
        fire_risk="high",
        notes="Very fast, high fire risk"
    ),

    'paper_engrave': LaserPreset(
        name="Paper Engrave",
        material="paper",
        thickness=0.0,
        operation="engrave",
        power=5,
        speed=400,
        line_interval=0.1,
        fire_risk="high",
        notes="Minimal power to avoid burning through"
    ),

    # =====================
    # RUBBER
    # =====================
    'rubber_3mm_cut': LaserPreset(
        name="3mm Rubber Cut",
        material="rubber",
        thickness=3.0,
        operation="cut",
        power=60,
        speed=12,
        passes=1,
        air_assist=True,
        fire_risk="medium",
        notes="Good for stamps and gaskets. Produces smoke."
    ),

    'rubber_engrave': LaserPreset(
        name="Rubber Engrave",
        material="rubber",
        thickness=0.0,
        operation="engrave",
        power=25,
        speed=180,
        line_interval=0.1,
        fire_risk="low",
        notes="For stamp making"
    ),

    # =====================
    # FABRIC
    # =====================
    'cotton_cut': LaserPreset(
        name="Cotton Fabric Cut",
        material="cotton",
        thickness=0.5,
        operation="cut",
        power=20,
        speed=40,
        passes=1,
        air_assist=True,
        fire_risk="high",
        notes="Sealed edges prevent fraying"
    ),

    'felt_cut': LaserPreset(
        name="Felt Cut",
        material="felt",
        thickness=2.0,
        operation="cut",
        power=35,
        speed=25,
        passes=1,
        air_assist=True,
        fire_risk="medium",
        notes="Clean sealed edges"
    ),

    # =====================
    # METAL (Engraving only)
    # =====================
    'aluminum_anodized_engrave': LaserPreset(
        name="Anodized Aluminum Engrave",
        material="aluminum_anodized",
        thickness=0.0,
        operation="engrave",
        power=60,
        speed=150,
        line_interval=0.05,
        bidirectional=True,
        fire_risk="low",
        notes="Removes anodized layer to reveal metal"
    ),

    'stainless_marking': LaserPreset(
        name="Stainless Steel Marking",
        material="stainless",
        thickness=0.0,
        operation="engrave",
        power=70,
        speed=100,
        line_interval=0.05,
        passes=2,
        fire_risk="low",
        notes="Dark oxidation marking on stainless"
    ),

    # =====================
    # SCORE (Light cut for folding)
    # =====================
    'cardboard_score': LaserPreset(
        name="Cardboard Score",
        material="cardboard",
        thickness=0.0,
        operation="score",
        power=8,
        speed=50,
        passes=1,
        air_assist=True,
        fire_risk="medium",
        notes="Light cut for folding"
    ),

    'wood_score': LaserPreset(
        name="Wood Score",
        material="wood",
        thickness=0.0,
        operation="score",
        power=15,
        speed=30,
        passes=1,
        fire_risk="low",
        notes="Surface marking for alignment or decoration"
    ),
}


def get_preset(preset_name: str) -> Optional[LaserPreset]:
    """
    Get preset by name.

    Args:
        preset_name: Preset key (e.g., 'wood_3mm_cut')

    Returns:
        LaserPreset or None
    """
    return LASER_PRESETS.get(preset_name.lower())


def get_preset_for_material(material: str, thickness: float = 3.0,
                            operation: str = 'cut') -> Optional[LaserPreset]:
    """
    Find best preset for given material and operation.

    Args:
        material: Material name (e.g., 'wood', 'leather')
        thickness: Material thickness in mm
        operation: Operation type ('cut', 'engrave', 'score')

    Returns:
        Best matching LaserPreset or None
    """
    material = material.lower()
    operation = operation.lower()

    best_preset = None
    best_thickness_diff = float('inf')

    for preset in LASER_PRESETS.values():
        if preset.material.lower() != material:
            continue
        if preset.operation != operation:
            continue

        thickness_diff = abs(preset.thickness - thickness)
        if thickness_diff < best_thickness_diff:
            best_thickness_diff = thickness_diff
            best_preset = preset

    return best_preset


def list_presets_for_material(material: str) -> List[LaserPreset]:
    """Get all presets for a given material."""
    material = material.lower()
    return [p for p in LASER_PRESETS.values() if p.material.lower() == material]


def list_all_materials() -> List[str]:
    """Get list of all supported materials."""
    return sorted(set(p.material for p in LASER_PRESETS.values()))


def describe_preset(preset: LaserPreset) -> str:
    """Get human-readable description of a preset."""
    lines = [
        f"Preset: {preset.name}",
        f"Material: {preset.material} ({preset.thickness}mm)",
        f"Operation: {preset.operation}",
        f"Power: {preset.power}%",
        f"Speed: {preset.speed} mm/s",
        f"Passes: {preset.passes}",
        f"Air Assist: {'Yes' if preset.air_assist else 'No'}",
        f"Fire Risk: {preset.fire_risk}",
    ]
    if preset.notes:
        lines.append(f"Notes: {preset.notes}")
    return '\n'.join(lines)


if __name__ == "__main__":
    # List all materials
    print("Supported materials:")
    for mat in list_all_materials():
        print(f"  - {mat}")

    print("\n" + "="*50)

    # Show wood presets
    print("\nWood presets:")
    for preset in list_presets_for_material('wood'):
        print(f"\n{describe_preset(preset)}")

    print("\n" + "="*50)

    # Find preset for specific needs
    print("\nFinding preset for 5mm wood cut:")
    preset = get_preset_for_material('wood', thickness=5.0, operation='cut')
    if preset:
        print(describe_preset(preset))
