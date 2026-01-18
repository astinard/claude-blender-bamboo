"""Material database and properties for 3D printing."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class MaterialType(str, Enum):
    """Types of 3D printing materials."""
    PLA = "pla"
    PETG = "petg"
    ABS = "abs"
    ASA = "asa"
    TPU = "tpu"
    PA = "pa"  # Nylon
    PC = "pc"  # Polycarbonate
    PVA = "pva"  # Water-soluble support
    HIPS = "hips"  # Support material for ABS
    WOOD = "wood"  # Wood-filled PLA
    CARBON = "carbon"  # Carbon fiber reinforced
    METAL = "metal"  # Metal-filled
    SILK = "silk"  # Silk PLA
    MATTE = "matte"  # Matte PLA
    GLOW = "glow"  # Glow-in-the-dark


@dataclass
class MaterialProperties:
    """Physical and printing properties of a material."""

    # Temperature settings
    nozzle_temp_min: int
    nozzle_temp_max: int
    nozzle_temp_default: int
    bed_temp_min: int
    bed_temp_max: int
    bed_temp_default: int

    # Mechanical properties
    density: float  # g/cm³
    tensile_strength: float  # MPa
    flexibility: float  # 0-1 scale
    layer_adhesion: float  # 0-1 scale

    # Printing characteristics
    requires_enclosure: bool = False
    requires_heated_bed: bool = True
    hygroscopic: bool = False  # Absorbs moisture
    warping_tendency: float = 0.0  # 0-1 scale
    stringing_tendency: float = 0.0  # 0-1 scale

    # Speed settings
    speed_modifier: float = 1.0  # Multiplier for default speed

    # Special handling
    abrasive: bool = False  # Requires hardened nozzle
    toxic_fumes: bool = False  # Requires ventilation

    # Compatible support materials
    compatible_supports: List[str] = field(default_factory=list)


@dataclass
class Material:
    """A 3D printing material with all its properties."""

    name: str
    material_type: MaterialType
    properties: MaterialProperties
    description: str = ""
    brand: Optional[str] = None
    color: Optional[str] = None

    @property
    def temp_range(self) -> tuple[int, int]:
        """Get nozzle temperature range."""
        return (self.properties.nozzle_temp_min, self.properties.nozzle_temp_max)

    @property
    def bed_temp_range(self) -> tuple[int, int]:
        """Get bed temperature range."""
        return (self.properties.bed_temp_min, self.properties.bed_temp_max)


# Material database with properties for common materials
MATERIAL_DATABASE: Dict[str, Material] = {
    "pla": Material(
        name="PLA",
        material_type=MaterialType.PLA,
        description="Polylactic Acid - Easy to print, biodegradable, low warp",
        properties=MaterialProperties(
            nozzle_temp_min=190,
            nozzle_temp_max=230,
            nozzle_temp_default=210,
            bed_temp_min=45,
            bed_temp_max=65,
            bed_temp_default=55,
            density=1.24,
            tensile_strength=50,
            flexibility=0.2,
            layer_adhesion=0.7,
            warping_tendency=0.1,
            stringing_tendency=0.3,
            compatible_supports=["pla", "pva"],
        ),
    ),
    "petg": Material(
        name="PETG",
        material_type=MaterialType.PETG,
        description="Polyethylene Terephthalate Glycol - Strong, flexible, food-safe",
        properties=MaterialProperties(
            nozzle_temp_min=220,
            nozzle_temp_max=260,
            nozzle_temp_default=240,
            bed_temp_min=70,
            bed_temp_max=90,
            bed_temp_default=80,
            density=1.27,
            tensile_strength=53,
            flexibility=0.4,
            layer_adhesion=0.8,
            warping_tendency=0.2,
            stringing_tendency=0.6,
            hygroscopic=True,
            compatible_supports=["petg", "pva"],
        ),
    ),
    "abs": Material(
        name="ABS",
        material_type=MaterialType.ABS,
        description="Acrylonitrile Butadiene Styrene - Durable, heat resistant",
        properties=MaterialProperties(
            nozzle_temp_min=230,
            nozzle_temp_max=270,
            nozzle_temp_default=250,
            bed_temp_min=90,
            bed_temp_max=110,
            bed_temp_default=100,
            density=1.04,
            tensile_strength=43,
            flexibility=0.3,
            layer_adhesion=0.9,
            requires_enclosure=True,
            warping_tendency=0.8,
            stringing_tendency=0.3,
            toxic_fumes=True,
            compatible_supports=["abs", "hips"],
        ),
    ),
    "asa": Material(
        name="ASA",
        material_type=MaterialType.ASA,
        description="Acrylonitrile Styrene Acrylate - UV resistant, outdoor use",
        properties=MaterialProperties(
            nozzle_temp_min=235,
            nozzle_temp_max=265,
            nozzle_temp_default=250,
            bed_temp_min=90,
            bed_temp_max=110,
            bed_temp_default=100,
            density=1.07,
            tensile_strength=55,
            flexibility=0.3,
            layer_adhesion=0.85,
            requires_enclosure=True,
            warping_tendency=0.6,
            stringing_tendency=0.3,
            toxic_fumes=True,
            compatible_supports=["asa", "hips"],
        ),
    ),
    "tpu": Material(
        name="TPU",
        material_type=MaterialType.TPU,
        description="Thermoplastic Polyurethane - Flexible, rubber-like",
        properties=MaterialProperties(
            nozzle_temp_min=210,
            nozzle_temp_max=240,
            nozzle_temp_default=225,
            bed_temp_min=40,
            bed_temp_max=60,
            bed_temp_default=50,
            density=1.21,
            tensile_strength=39,
            flexibility=0.95,
            layer_adhesion=0.9,
            warping_tendency=0.05,
            stringing_tendency=0.8,
            speed_modifier=0.5,  # Print slower
            hygroscopic=True,
            compatible_supports=["pva"],
        ),
    ),
    "pa": Material(
        name="Nylon (PA)",
        material_type=MaterialType.PA,
        description="Polyamide - Strong, durable, wear-resistant",
        properties=MaterialProperties(
            nozzle_temp_min=250,
            nozzle_temp_max=280,
            nozzle_temp_default=265,
            bed_temp_min=70,
            bed_temp_max=100,
            bed_temp_default=85,
            density=1.14,
            tensile_strength=70,
            flexibility=0.5,
            layer_adhesion=0.95,
            requires_enclosure=True,
            warping_tendency=0.7,
            stringing_tendency=0.5,
            hygroscopic=True,
            compatible_supports=["pva"],
        ),
    ),
    "pc": Material(
        name="Polycarbonate",
        material_type=MaterialType.PC,
        description="Polycarbonate - Very strong, high heat resistance",
        properties=MaterialProperties(
            nozzle_temp_min=260,
            nozzle_temp_max=310,
            nozzle_temp_default=285,
            bed_temp_min=100,
            bed_temp_max=120,
            bed_temp_default=110,
            density=1.20,
            tensile_strength=65,
            flexibility=0.3,
            layer_adhesion=0.85,
            requires_enclosure=True,
            warping_tendency=0.9,
            stringing_tendency=0.4,
            hygroscopic=True,
            toxic_fumes=True,
            compatible_supports=["hips"],
        ),
    ),
    "pva": Material(
        name="PVA",
        material_type=MaterialType.PVA,
        description="Polyvinyl Alcohol - Water-soluble support material",
        properties=MaterialProperties(
            nozzle_temp_min=180,
            nozzle_temp_max=210,
            nozzle_temp_default=195,
            bed_temp_min=45,
            bed_temp_max=60,
            bed_temp_default=55,
            density=1.19,
            tensile_strength=30,
            flexibility=0.2,
            layer_adhesion=0.6,
            hygroscopic=True,
            warping_tendency=0.3,
            stringing_tendency=0.4,
            compatible_supports=[],
        ),
    ),
    "hips": Material(
        name="HIPS",
        material_type=MaterialType.HIPS,
        description="High Impact Polystyrene - Support for ABS, limonene-soluble",
        properties=MaterialProperties(
            nozzle_temp_min=220,
            nozzle_temp_max=250,
            nozzle_temp_default=235,
            bed_temp_min=90,
            bed_temp_max=110,
            bed_temp_default=100,
            density=1.04,
            tensile_strength=32,
            flexibility=0.25,
            layer_adhesion=0.7,
            requires_enclosure=True,
            warping_tendency=0.5,
            stringing_tendency=0.3,
            compatible_supports=[],
        ),
    ),
    "carbon_pla": Material(
        name="Carbon Fiber PLA",
        material_type=MaterialType.CARBON,
        description="Carbon fiber reinforced PLA - Stiff, lightweight",
        properties=MaterialProperties(
            nozzle_temp_min=200,
            nozzle_temp_max=240,
            nozzle_temp_default=220,
            bed_temp_min=50,
            bed_temp_max=70,
            bed_temp_default=60,
            density=1.15,
            tensile_strength=60,
            flexibility=0.1,
            layer_adhesion=0.65,
            warping_tendency=0.15,
            stringing_tendency=0.4,
            abrasive=True,  # Requires hardened nozzle
            compatible_supports=["pla", "pva"],
        ),
    ),
    "carbon_petg": Material(
        name="Carbon Fiber PETG",
        material_type=MaterialType.CARBON,
        description="Carbon fiber reinforced PETG - Strong, heat resistant",
        properties=MaterialProperties(
            nozzle_temp_min=230,
            nozzle_temp_max=270,
            nozzle_temp_default=250,
            bed_temp_min=75,
            bed_temp_max=95,
            bed_temp_default=85,
            density=1.18,
            tensile_strength=65,
            flexibility=0.15,
            layer_adhesion=0.7,
            warping_tendency=0.25,
            stringing_tendency=0.5,
            abrasive=True,
            hygroscopic=True,
            compatible_supports=["petg", "pva"],
        ),
    ),
}


def get_material(name: str) -> Optional[Material]:
    """Get a material by name."""
    return MATERIAL_DATABASE.get(name.lower())


def get_materials_by_type(material_type: MaterialType) -> List[Material]:
    """Get all materials of a specific type."""
    return [m for m in MATERIAL_DATABASE.values() if m.material_type == material_type]


def list_all_materials() -> List[str]:
    """List all available material names."""
    return list(MATERIAL_DATABASE.keys())
