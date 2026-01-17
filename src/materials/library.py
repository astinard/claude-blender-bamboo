"""
Material Library for Claude Fab Lab.

Comprehensive database of 3D printing filaments and laser-cuttable sheet materials
with their properties, print settings, and constraints.

Usage:
    from src.materials import FILAMENTS, SHEETS, get_material, find_material

    # Get specific material
    pla = get_material('pla')
    print(pla.nozzle_temp)  # 210

    # Find by natural language
    material = find_material('rubber')  # Returns TPU
    material = find_material('flexible')  # Returns TPU
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Tuple


class MaterialType(Enum):
    """Type of material."""
    FILAMENT = "filament"
    SHEET = "sheet"


class MaterialProperty(Enum):
    """Material properties for selection."""
    RIGID = "rigid"
    FLEXIBLE = "flexible"
    HEAT_RESISTANT = "heat_resistant"
    FOOD_SAFE = "food_safe"
    UV_RESISTANT = "uv_resistant"
    WATER_RESISTANT = "water_resistant"
    BIODEGRADABLE = "biodegradable"
    HIGH_STRENGTH = "high_strength"
    CHEMICAL_RESISTANT = "chemical_resistant"
    TRANSPARENT = "transparent"
    MATTE = "matte"
    GLOSSY = "glossy"


@dataclass
class FilamentMaterial:
    """
    3D printing filament material definition.

    Contains all parameters needed for optimal printing.
    """
    # Identity
    name: str
    short_name: str
    type: MaterialType = MaterialType.FILAMENT

    # Temperature settings (°C)
    nozzle_temp: int = 210
    nozzle_temp_range: Tuple[int, int] = (190, 230)
    bed_temp: int = 60
    bed_temp_range: Tuple[int, int] = (50, 70)
    chamber_temp: int = 0  # 0 = not required
    chamber_temp_range: Tuple[int, int] = (0, 0)

    # Physical properties
    density: float = 1.24  # g/cm³
    shore_hardness: str = ""  # For flexible materials (e.g., "95A")
    glass_transition_temp: int = 60  # °C

    # Printing constraints
    min_layer_height: float = 0.08  # mm
    max_layer_height: float = 0.28  # mm
    recommended_layer_height: float = 0.20  # mm
    min_wall_thickness: float = 0.8  # mm (2 walls at 0.4mm)
    max_overhang_angle: int = 45  # degrees without support
    supports_required_angle: int = 60  # degrees
    print_speed_factor: float = 1.0  # Multiplier vs standard

    # Retraction settings
    retraction_distance: float = 0.8  # mm
    retraction_speed: int = 30  # mm/s

    # Cooling
    min_fan_speed: int = 0  # %
    max_fan_speed: int = 100  # %
    bridge_fan_speed: int = 100  # %
    enable_fan_first_layers: int = 3  # Layers before full fan

    # Available colors (common ones)
    colors: List[str] = field(default_factory=list)

    # Properties for material selection
    properties: List[MaterialProperty] = field(default_factory=list)

    # Cost estimation
    cost_per_kg: float = 25.0  # USD

    # Special requirements
    requires_enclosure: bool = False
    requires_dry_box: bool = False
    requires_hardened_nozzle: bool = False

    # Notes
    notes: str = ""


@dataclass
class SheetMaterial:
    """
    Laser-cuttable sheet material definition.

    Contains settings for both cutting and engraving operations.
    """
    # Identity
    name: str
    short_name: str
    type: MaterialType = MaterialType.SHEET

    # Physical properties
    thickness: float = 3.0  # mm
    thickness_tolerance: float = 0.2  # mm

    # Cutting settings (for 40W laser)
    can_cut: bool = True
    cut_power: int = 70  # % (0-100)
    cut_speed: int = 10  # mm/s
    cut_passes: int = 1
    cut_z_offset: float = 0.0  # Focus offset in mm
    cut_air_assist: bool = True

    # Engraving settings
    can_engrave: bool = True
    engrave_power: int = 30  # %
    engrave_speed: int = 100  # mm/s
    engrave_dpi: int = 254  # dots per inch
    engrave_bidirectional: bool = True

    # Safety
    produces_toxic_fumes: bool = False
    requires_ventilation: bool = True
    fire_risk: str = "low"  # low, medium, high

    # Available colors/finishes
    colors: List[str] = field(default_factory=list)

    # Properties
    properties: List[MaterialProperty] = field(default_factory=list)

    # Cost
    cost_per_sheet: float = 10.0  # USD (standard size)
    sheet_size: Tuple[int, int] = (300, 200)  # mm

    # Notes
    notes: str = ""


# =============================================================================
# FILAMENT LIBRARY
# =============================================================================

FILAMENTS: Dict[str, FilamentMaterial] = {
    # ----- PLA Family -----
    'pla': FilamentMaterial(
        name='PLA (Polylactic Acid)',
        short_name='PLA',
        nozzle_temp=210,
        nozzle_temp_range=(190, 230),
        bed_temp=60,
        bed_temp_range=(50, 70),
        density=1.24,
        glass_transition_temp=60,
        max_overhang_angle=50,
        max_fan_speed=100,
        colors=['white', 'black', 'red', 'blue', 'green', 'yellow', 'orange',
                'purple', 'pink', 'gray', 'brown', 'gold', 'silver', 'clear'],
        properties=[MaterialProperty.RIGID, MaterialProperty.BIODEGRADABLE, MaterialProperty.MATTE],
        cost_per_kg=25.0,
        notes='Most common filament. Easy to print, low warping. Not heat resistant.',
    ),

    'pla_plus': FilamentMaterial(
        name='PLA+ (Enhanced PLA)',
        short_name='PLA+',
        nozzle_temp=215,
        nozzle_temp_range=(200, 235),
        bed_temp=60,
        bed_temp_range=(50, 70),
        density=1.24,
        glass_transition_temp=65,
        max_overhang_angle=50,
        properties=[MaterialProperty.RIGID, MaterialProperty.HIGH_STRENGTH],
        cost_per_kg=28.0,
        notes='Stronger than regular PLA, slightly better heat resistance.',
    ),

    'pla_silk': FilamentMaterial(
        name='PLA Silk (Shiny PLA)',
        short_name='Silk PLA',
        nozzle_temp=215,
        nozzle_temp_range=(200, 230),
        bed_temp=60,
        bed_temp_range=(50, 65),
        density=1.24,
        max_overhang_angle=45,
        print_speed_factor=0.9,
        colors=['gold', 'silver', 'copper', 'blue', 'red', 'green', 'purple'],
        properties=[MaterialProperty.RIGID, MaterialProperty.GLOSSY],
        cost_per_kg=32.0,
        notes='Shiny finish, slightly weaker than regular PLA.',
    ),

    # ----- PETG Family -----
    'petg': FilamentMaterial(
        name='PETG (Polyethylene Terephthalate Glycol)',
        short_name='PETG',
        nozzle_temp=240,
        nozzle_temp_range=(220, 260),
        bed_temp=80,
        bed_temp_range=(70, 90),
        density=1.27,
        glass_transition_temp=80,
        max_overhang_angle=40,
        supports_required_angle=55,
        retraction_distance=1.0,
        min_fan_speed=30,
        max_fan_speed=70,
        colors=['white', 'black', 'blue', 'clear', 'orange', 'red', 'green'],
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT,
                    MaterialProperty.CHEMICAL_RESISTANT, MaterialProperty.WATER_RESISTANT],
        cost_per_kg=30.0,
        notes='Good balance of strength and ease. Layer adhesion can be too strong (hard to remove supports).',
    ),

    # ----- TPU/Flexible Family -----
    'tpu': FilamentMaterial(
        name='TPU (Thermoplastic Polyurethane)',
        short_name='TPU',
        nozzle_temp=220,
        nozzle_temp_range=(210, 240),
        bed_temp=50,
        bed_temp_range=(40, 60),
        density=1.21,
        shore_hardness='95A',
        min_layer_height=0.12,
        max_layer_height=0.24,
        min_wall_thickness=1.2,
        max_overhang_angle=35,
        print_speed_factor=0.5,  # Print slow!
        retraction_distance=0.5,
        retraction_speed=20,
        max_fan_speed=50,
        colors=['white', 'black', 'clear', 'red', 'blue'],
        properties=[MaterialProperty.FLEXIBLE, MaterialProperty.WATER_RESISTANT],
        cost_per_kg=40.0,
        notes='Flexible, rubber-like material. Print slowly with direct drive extruder preferred.',
    ),

    'tpu_soft': FilamentMaterial(
        name='TPU 85A (Soft)',
        short_name='TPU 85A',
        nozzle_temp=225,
        nozzle_temp_range=(215, 240),
        bed_temp=50,
        bed_temp_range=(40, 60),
        density=1.19,
        shore_hardness='85A',
        min_layer_height=0.16,
        max_layer_height=0.24,
        min_wall_thickness=1.6,
        print_speed_factor=0.3,  # Very slow!
        retraction_distance=0.3,
        retraction_speed=15,
        max_fan_speed=30,
        colors=['white', 'black', 'clear'],
        properties=[MaterialProperty.FLEXIBLE],
        cost_per_kg=50.0,
        notes='Very soft and flexible. Difficult to print, requires direct drive.',
    ),

    # ----- ABS Family -----
    'abs': FilamentMaterial(
        name='ABS (Acrylonitrile Butadiene Styrene)',
        short_name='ABS',
        nozzle_temp=250,
        nozzle_temp_range=(230, 270),
        bed_temp=100,
        bed_temp_range=(90, 110),
        chamber_temp=45,
        chamber_temp_range=(40, 60),
        density=1.04,
        glass_transition_temp=105,
        max_overhang_angle=40,
        min_fan_speed=0,
        max_fan_speed=30,
        colors=['white', 'black', 'red', 'blue', 'yellow', 'gray'],
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT, MaterialProperty.HIGH_STRENGTH],
        cost_per_kg=28.0,
        requires_enclosure=True,
        notes='Strong and heat resistant. Requires enclosure to prevent warping. Produces fumes.',
    ),

    'asa': FilamentMaterial(
        name='ASA (Acrylonitrile Styrene Acrylate)',
        short_name='ASA',
        nozzle_temp=250,
        nozzle_temp_range=(235, 265),
        bed_temp=100,
        bed_temp_range=(90, 110),
        chamber_temp=45,
        chamber_temp_range=(40, 55),
        density=1.07,
        glass_transition_temp=100,
        max_overhang_angle=40,
        min_fan_speed=0,
        max_fan_speed=40,
        colors=['white', 'black', 'gray', 'beige'],
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT,
                    MaterialProperty.UV_RESISTANT, MaterialProperty.HIGH_STRENGTH],
        cost_per_kg=35.0,
        requires_enclosure=True,
        notes='Like ABS but UV resistant. Great for outdoor use.',
    ),

    # ----- Engineering Filaments -----
    'pa': FilamentMaterial(
        name='PA (Nylon/Polyamide)',
        short_name='Nylon',
        nozzle_temp=260,
        nozzle_temp_range=(240, 280),
        bed_temp=80,
        bed_temp_range=(70, 100),
        chamber_temp=50,
        chamber_temp_range=(45, 60),
        density=1.14,
        glass_transition_temp=70,
        max_overhang_angle=35,
        min_fan_speed=0,
        max_fan_speed=30,
        colors=['natural', 'black', 'white'],
        properties=[MaterialProperty.RIGID, MaterialProperty.HIGH_STRENGTH,
                    MaterialProperty.CHEMICAL_RESISTANT, MaterialProperty.HEAT_RESISTANT],
        cost_per_kg=50.0,
        requires_enclosure=True,
        requires_dry_box=True,
        notes='Very strong and durable. Highly hygroscopic - must be kept dry!',
    ),

    'pa_cf': FilamentMaterial(
        name='PA-CF (Carbon Fiber Nylon)',
        short_name='PA-CF',
        nozzle_temp=280,
        nozzle_temp_range=(260, 300),
        bed_temp=90,
        bed_temp_range=(80, 100),
        chamber_temp=55,
        chamber_temp_range=(50, 65),
        density=1.20,
        glass_transition_temp=75,
        print_speed_factor=0.8,
        colors=['black'],
        properties=[MaterialProperty.RIGID, MaterialProperty.HIGH_STRENGTH, MaterialProperty.HEAT_RESISTANT],
        cost_per_kg=80.0,
        requires_enclosure=True,
        requires_dry_box=True,
        requires_hardened_nozzle=True,
        notes='Extremely strong with carbon fiber reinforcement. Abrasive - requires hardened nozzle.',
    ),

    'pc': FilamentMaterial(
        name='PC (Polycarbonate)',
        short_name='PC',
        nozzle_temp=280,
        nozzle_temp_range=(260, 310),
        bed_temp=110,
        bed_temp_range=(100, 120),
        chamber_temp=60,
        chamber_temp_range=(55, 70),
        density=1.20,
        glass_transition_temp=150,
        max_overhang_angle=35,
        min_fan_speed=0,
        max_fan_speed=30,
        colors=['clear', 'black', 'white'],
        properties=[MaterialProperty.RIGID, MaterialProperty.HIGH_STRENGTH,
                    MaterialProperty.HEAT_RESISTANT, MaterialProperty.TRANSPARENT],
        cost_per_kg=55.0,
        requires_enclosure=True,
        notes='Very strong and heat resistant. Can be transparent. Requires high temps.',
    ),

    # ----- Specialty -----
    'pva': FilamentMaterial(
        name='PVA (Polyvinyl Alcohol)',
        short_name='PVA',
        nozzle_temp=200,
        nozzle_temp_range=(185, 215),
        bed_temp=50,
        bed_temp_range=(45, 60),
        density=1.23,
        print_speed_factor=0.7,
        colors=['natural'],
        properties=[MaterialProperty.WATER_RESISTANT],  # Dissolves in water
        cost_per_kg=60.0,
        requires_dry_box=True,
        notes='Water-soluble support material for PLA. Very hygroscopic.',
    ),
}


# =============================================================================
# SHEET MATERIAL LIBRARY (For Laser)
# =============================================================================

SHEETS: Dict[str, SheetMaterial] = {
    # ----- Wood -----
    'wood_3mm': SheetMaterial(
        name='Plywood/MDF 3mm',
        short_name='Wood 3mm',
        thickness=3.0,
        cut_power=70,
        cut_speed=10,
        cut_passes=1,
        engrave_power=25,
        engrave_speed=150,
        fire_risk='medium',
        colors=['natural', 'birch', 'walnut', 'cherry'],
        properties=[MaterialProperty.MATTE],
        cost_per_sheet=5.0,
        notes='Most common laser material. Clean cuts with slight char.',
    ),

    'wood_5mm': SheetMaterial(
        name='Plywood/MDF 5mm',
        short_name='Wood 5mm',
        thickness=5.0,
        cut_power=85,
        cut_speed=6,
        cut_passes=1,
        engrave_power=25,
        engrave_speed=150,
        fire_risk='medium',
        colors=['natural', 'birch', 'walnut'],
        properties=[MaterialProperty.MATTE],
        cost_per_sheet=8.0,
        notes='Thicker wood, may need slower speed or multiple passes.',
    ),

    'wood_10mm': SheetMaterial(
        name='Plywood/MDF 10mm',
        short_name='Wood 10mm',
        thickness=10.0,
        cut_power=100,
        cut_speed=3,
        cut_passes=2,
        engrave_power=30,
        engrave_speed=120,
        fire_risk='high',
        colors=['natural', 'birch'],
        properties=[MaterialProperty.MATTE],
        cost_per_sheet=15.0,
        notes='Thick wood requires multiple passes. Watch for fire.',
    ),

    'wood_15mm': SheetMaterial(
        name='Plywood/MDF 15mm',
        short_name='Wood 15mm',
        thickness=15.0,
        cut_power=100,
        cut_speed=2,
        cut_passes=3,
        engrave_power=30,
        engrave_speed=100,
        fire_risk='high',
        colors=['natural'],
        properties=[MaterialProperty.MATTE],
        cost_per_sheet=20.0,
        notes='Maximum thickness for 40W laser. Multiple passes required.',
    ),

    'balsa_3mm': SheetMaterial(
        name='Balsa Wood 3mm',
        short_name='Balsa 3mm',
        thickness=3.0,
        cut_power=30,
        cut_speed=25,
        cut_passes=1,
        engrave_power=10,
        engrave_speed=200,
        fire_risk='high',
        colors=['natural'],
        properties=[MaterialProperty.MATTE],
        cost_per_sheet=4.0,
        notes='Very soft, cuts easily. High fire risk - watch carefully.',
    ),

    # ----- Acrylic -----
    'acrylic_dark_3mm': SheetMaterial(
        name='Dark Acrylic 3mm',
        short_name='Acrylic 3mm',
        thickness=3.0,
        cut_power=80,
        cut_speed=8,
        cut_passes=1,
        engrave_power=20,
        engrave_speed=200,
        engrave_dpi=300,
        produces_toxic_fumes=True,
        fire_risk='low',
        colors=['black', 'dark blue', 'dark red', 'dark green', 'dark brown'],
        properties=[MaterialProperty.RIGID, MaterialProperty.GLOSSY],
        cost_per_sheet=12.0,
        notes='Dark acrylic only! Clear/light acrylic is transparent to blue laser.',
    ),

    'acrylic_dark_5mm': SheetMaterial(
        name='Dark Acrylic 5mm',
        short_name='Acrylic 5mm',
        thickness=5.0,
        cut_power=100,
        cut_speed=4,
        cut_passes=1,
        engrave_power=25,
        engrave_speed=180,
        produces_toxic_fumes=True,
        fire_risk='low',
        colors=['black', 'dark blue', 'dark red'],
        properties=[MaterialProperty.RIGID, MaterialProperty.GLOSSY],
        cost_per_sheet=18.0,
        notes='Dark acrylic only. Clean polished edges.',
    ),

    # ----- Leather -----
    'leather_2mm': SheetMaterial(
        name='Leather 2mm',
        short_name='Leather 2mm',
        thickness=2.0,
        cut_power=50,
        cut_speed=15,
        cut_passes=1,
        engrave_power=15,
        engrave_speed=250,
        fire_risk='medium',
        colors=['natural', 'brown', 'black', 'tan'],
        properties=[MaterialProperty.FLEXIBLE, MaterialProperty.MATTE],
        cost_per_sheet=25.0,
        notes='Natural leather. Produces strong smell when cutting.',
    ),

    'leather_3mm': SheetMaterial(
        name='Leather 3mm',
        short_name='Leather 3mm',
        thickness=3.0,
        cut_power=65,
        cut_speed=10,
        cut_passes=1,
        engrave_power=18,
        engrave_speed=220,
        fire_risk='medium',
        colors=['natural', 'brown', 'black'],
        properties=[MaterialProperty.FLEXIBLE, MaterialProperty.MATTE],
        cost_per_sheet=35.0,
        notes='Thicker leather for wallets, belts, etc.',
    ),

    'faux_leather_2mm': SheetMaterial(
        name='Faux Leather 2mm',
        short_name='Faux Leather',
        thickness=2.0,
        cut_power=40,
        cut_speed=20,
        cut_passes=1,
        engrave_power=12,
        engrave_speed=280,
        fire_risk='medium',
        colors=['black', 'brown', 'white', 'red', 'blue'],
        properties=[MaterialProperty.FLEXIBLE],
        cost_per_sheet=10.0,
        notes='PU leather alternative. Check material safety.',
    ),

    # ----- Paper/Cardboard -----
    'cardboard_2mm': SheetMaterial(
        name='Cardboard 2mm',
        short_name='Cardboard',
        thickness=2.0,
        cut_power=25,
        cut_speed=30,
        cut_passes=1,
        engrave_power=8,
        engrave_speed=300,
        fire_risk='high',
        colors=['natural', 'white', 'black'],
        properties=[MaterialProperty.MATTE],
        cost_per_sheet=2.0,
        notes='Watch closely for fire. Clean cuts.',
    ),

    'paper_cardstock': SheetMaterial(
        name='Cardstock Paper',
        short_name='Cardstock',
        thickness=0.3,
        cut_power=10,
        cut_speed=50,
        cut_passes=1,
        engrave_power=5,
        engrave_speed=400,
        fire_risk='high',
        colors=['white', 'black', 'various'],
        properties=[MaterialProperty.MATTE],
        cost_per_sheet=0.50,
        notes='Very fast cuts. High fire risk.',
    ),

    # ----- Rubber -----
    'rubber_3mm': SheetMaterial(
        name='Rubber 3mm',
        short_name='Rubber 3mm',
        thickness=3.0,
        cut_power=60,
        cut_speed=12,
        cut_passes=1,
        engrave_power=20,
        engrave_speed=180,
        produces_toxic_fumes=True,
        fire_risk='medium',
        colors=['black', 'red', 'gray'],
        properties=[MaterialProperty.FLEXIBLE],
        cost_per_sheet=15.0,
        notes='Good for stamps and gaskets. Produces smoke.',
    ),

    # ----- Metal (Engraving Only) -----
    'aluminum_anodized': SheetMaterial(
        name='Anodized Aluminum',
        short_name='Anodized Alu',
        thickness=1.0,
        can_cut=False,
        cut_power=0,
        cut_speed=0,
        engrave_power=60,
        engrave_speed=150,
        engrave_dpi=400,
        fire_risk='low',
        colors=['black', 'blue', 'red', 'gold', 'silver'],
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT],
        cost_per_sheet=20.0,
        notes='Engraving only - removes anodized layer to reveal metal.',
    ),

    'stainless_coated': SheetMaterial(
        name='Coated Stainless Steel',
        short_name='Stainless',
        thickness=0.5,
        can_cut=False,
        cut_power=0,
        cut_speed=0,
        engrave_power=70,
        engrave_speed=100,
        engrave_dpi=400,
        fire_risk='low',
        colors=['natural'],
        properties=[MaterialProperty.RIGID, MaterialProperty.HEAT_RESISTANT],
        cost_per_sheet=25.0,
        notes='Engraving only - marks by oxidation.',
    ),
}


# =============================================================================
# NATURAL LANGUAGE ALIASES
# =============================================================================

MATERIAL_ALIASES: Dict[str, str] = {
    # PLA
    'plastic': 'pla',
    'standard': 'pla',
    'basic': 'pla',
    'easy': 'pla',
    'beginner': 'pla',

    # PETG
    'strong plastic': 'petg',
    'durable': 'petg',
    'water resistant': 'petg',
    'pet': 'petg',

    # TPU/Flexible
    'rubber': 'tpu',
    'flexible': 'tpu',
    'bendy': 'tpu',
    'soft': 'tpu',
    'elastic': 'tpu',
    'bouncy': 'tpu',
    'squishy': 'tpu',
    'very soft': 'tpu_soft',
    'extra soft': 'tpu_soft',
    'super flexible': 'tpu_soft',

    # ABS
    'heat resistant': 'abs',
    'automotive': 'abs',
    'lego': 'abs',

    # ASA
    'outdoor': 'asa',
    'uv resistant': 'asa',
    'weatherproof': 'asa',

    # Nylon
    'nylon': 'pa',
    'polyamide': 'pa',
    'strong': 'pa',
    'tough': 'pa',
    'industrial': 'pa',
    'carbon fiber': 'pa_cf',
    'carbon': 'pa_cf',

    # PC
    'polycarbonate': 'pc',
    'clear strong': 'pc',
    'bulletproof': 'pc',

    # Wood sheets
    'wood': 'wood_3mm',
    'plywood': 'wood_3mm',
    'thin wood': 'wood_3mm',
    'medium wood': 'wood_5mm',
    'thick wood': 'wood_10mm',
    'very thick wood': 'wood_15mm',
    'balsa': 'balsa_3mm',
    'light wood': 'balsa_3mm',

    # Acrylic
    'acrylic': 'acrylic_dark_3mm',
    'plexiglass': 'acrylic_dark_3mm',
    'perspex': 'acrylic_dark_3mm',
    'thick acrylic': 'acrylic_dark_5mm',

    # Leather
    'leather': 'leather_2mm',
    'thin leather': 'leather_2mm',
    'thick leather': 'leather_3mm',
    'fake leather': 'faux_leather_2mm',
    'vegan leather': 'faux_leather_2mm',

    # Paper
    'cardboard': 'cardboard_2mm',
    'card': 'cardboard_2mm',
    'paper': 'paper_cardstock',
    'cardstock': 'paper_cardstock',

    # Rubber
    'rubber sheet': 'rubber_3mm',
    'gasket': 'rubber_3mm',
    'stamp': 'rubber_3mm',

    # Metal
    'aluminum': 'aluminum_anodized',
    'metal': 'aluminum_anodized',
    'steel': 'stainless_coated',
    'stainless': 'stainless_coated',
}

COLOR_ALIASES: Dict[str, Tuple[float, float, float, float]] = {
    # Basic colors (RGBA 0-1)
    'red': (1.0, 0.0, 0.0, 1.0),
    'green': (0.0, 0.8, 0.0, 1.0),
    'blue': (0.0, 0.0, 1.0, 1.0),
    'yellow': (1.0, 1.0, 0.0, 1.0),
    'orange': (1.0, 0.5, 0.0, 1.0),
    'purple': (0.5, 0.0, 1.0, 1.0),
    'pink': (1.0, 0.4, 0.7, 1.0),
    'cyan': (0.0, 1.0, 1.0, 1.0),
    'magenta': (1.0, 0.0, 1.0, 1.0),

    # Neutrals
    'white': (1.0, 1.0, 1.0, 1.0),
    'black': (0.0, 0.0, 0.0, 1.0),
    'gray': (0.5, 0.5, 0.5, 1.0),
    'grey': (0.5, 0.5, 0.5, 1.0),
    'dark gray': (0.25, 0.25, 0.25, 1.0),
    'light gray': (0.75, 0.75, 0.75, 1.0),

    # Earth tones
    'brown': (0.6, 0.3, 0.0, 1.0),
    'tan': (0.82, 0.71, 0.55, 1.0),
    'beige': (0.96, 0.96, 0.86, 1.0),

    # Metallics
    'gold': (1.0, 0.84, 0.0, 1.0),
    'silver': (0.75, 0.75, 0.75, 1.0),
    'copper': (0.72, 0.45, 0.2, 1.0),
    'bronze': (0.8, 0.5, 0.2, 1.0),

    # Special
    'clear': (1.0, 1.0, 1.0, 0.3),
    'transparent': (1.0, 1.0, 1.0, 0.1),
    'natural': (0.9, 0.85, 0.7, 1.0),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_material(name: str) -> Optional[FilamentMaterial | SheetMaterial]:
    """
    Get material by exact name.

    Args:
        name: Material key (e.g., 'pla', 'wood_3mm')

    Returns:
        Material object or None
    """
    name = name.lower().strip()
    if name in FILAMENTS:
        return FILAMENTS[name]
    if name in SHEETS:
        return SHEETS[name]
    return None


def find_material(query: str) -> Optional[FilamentMaterial | SheetMaterial]:
    """
    Find material by natural language query.

    Args:
        query: Natural language description (e.g., 'rubber', 'flexible', 'wood')

    Returns:
        Best matching material or None
    """
    query = query.lower().strip()

    # Direct match
    material = get_material(query)
    if material:
        return material

    # Alias match
    if query in MATERIAL_ALIASES:
        return get_material(MATERIAL_ALIASES[query])

    # Partial alias match
    for alias, material_name in MATERIAL_ALIASES.items():
        if alias in query or query in alias:
            return get_material(material_name)

    return None


def get_color(name: str) -> Optional[Tuple[float, float, float, float]]:
    """
    Get color RGBA by name.

    Args:
        name: Color name (e.g., 'red', 'blue')

    Returns:
        RGBA tuple (0-1 range) or None
    """
    name = name.lower().strip()
    return COLOR_ALIASES.get(name)


def list_filaments() -> List[str]:
    """List all available filament names."""
    return list(FILAMENTS.keys())


def list_sheets() -> List[str]:
    """List all available sheet material names."""
    return list(SHEETS.keys())


def get_materials_by_property(prop: MaterialProperty) -> List[FilamentMaterial | SheetMaterial]:
    """Get all materials with a specific property."""
    results = []
    for mat in FILAMENTS.values():
        if prop in mat.properties:
            results.append(mat)
    for mat in SHEETS.values():
        if prop in mat.properties:
            results.append(mat)
    return results


def suggest_material(requirements: List[str]) -> Optional[FilamentMaterial | SheetMaterial]:
    """
    Suggest best material based on requirements.

    Args:
        requirements: List of requirements like ['flexible', 'cheap', 'waterproof']

    Returns:
        Best matching material
    """
    # Score each material
    scores = {}

    all_materials = {**FILAMENTS, **SHEETS}

    for name, mat in all_materials.items():
        score = 0

        for req in requirements:
            req = req.lower()

            # Check properties
            for prop in mat.properties:
                if req in prop.value.lower():
                    score += 10

            # Check name
            if req in mat.name.lower():
                score += 5

            # Check aliases
            for alias, mat_name in MATERIAL_ALIASES.items():
                if req in alias and mat_name == name:
                    score += 8

            # Check notes
            if hasattr(mat, 'notes') and req in mat.notes.lower():
                score += 3

        if score > 0:
            scores[name] = score

    if not scores:
        return None

    best = max(scores.items(), key=lambda x: x[1])
    return all_materials[best[0]]
