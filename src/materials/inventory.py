"""Material inventory tracking for Claude Fab Lab.

P5.6: Material Inventory Tracking

Features:
- Track spool quantities
- Low stock alerts
- Cost tracking
- Auto-deduct on print
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from src.materials.material_db import get_material, MaterialType
from src.utils import get_logger

logger = get_logger("materials.inventory")


@dataclass
class Spool:
    """A physical spool of filament."""

    id: str
    material: str  # Key into MATERIAL_DATABASE
    brand: str
    color: str
    weight_grams: float  # Total weight when full
    remaining_grams: float  # Current remaining weight
    cost_per_kg: float
    diameter: float = 1.75  # mm
    purchase_date: Optional[str] = None
    last_used: Optional[str] = None
    notes: str = ""

    @property
    def remaining_percent(self) -> float:
        """Get remaining material as percentage."""
        if self.weight_grams <= 0:
            return 0
        return (self.remaining_grams / self.weight_grams) * 100

    @property
    def remaining_meters(self) -> float:
        """Estimate remaining filament length in meters."""
        mat = get_material(self.material)
        if mat is None:
            density = 1.24  # Default PLA density
        else:
            density = mat.properties.density

        # Volume in cm³ = mass / density
        volume_cm3 = self.remaining_grams / density
        # Cross-section area in cm² (diameter in mm -> radius in cm)
        radius_cm = (self.diameter / 2) / 10
        area_cm2 = 3.14159 * radius_cm * radius_cm
        # Length in cm, convert to meters
        length_cm = volume_cm3 / area_cm2
        return length_cm / 100

    @property
    def remaining_cost(self) -> float:
        """Get value of remaining material."""
        return (self.remaining_grams / 1000) * self.cost_per_kg

    def use(self, grams: float) -> bool:
        """Use material from this spool. Returns True if successful."""
        if grams > self.remaining_grams:
            return False
        self.remaining_grams -= grams
        self.last_used = datetime.now().isoformat()
        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Spool":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class LowStockAlert:
    """Alert for low stock condition."""

    spool_id: str
    material: str
    brand: str
    color: str
    remaining_percent: float
    remaining_grams: float
    message: str


class InventoryManager:
    """Manages filament inventory."""

    def __init__(self, data_file: Optional[Path] = None):
        """Initialize inventory manager."""
        self.data_file = data_file or Path("data/inventory.json")
        self.spools: Dict[str, Spool] = {}
        self.low_stock_threshold: float = 20.0  # Percent
        self._load()

    def _load(self) -> None:
        """Load inventory from disk."""
        if self.data_file.exists():
            try:
                with open(self.data_file) as f:
                    data = json.load(f)
                self.spools = {
                    k: Spool.from_dict(v) for k, v in data.get("spools", {}).items()
                }
                self.low_stock_threshold = data.get("low_stock_threshold", 20.0)
                logger.info(f"Loaded {len(self.spools)} spools from inventory")
            except Exception as e:
                logger.error(f"Failed to load inventory: {e}")
                self.spools = {}

    def _save(self) -> None:
        """Save inventory to disk."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "spools": {k: v.to_dict() for k, v in self.spools.items()},
            "low_stock_threshold": self.low_stock_threshold,
        }
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug("Inventory saved")

    def add_spool(
        self,
        material: str,
        brand: str,
        color: str,
        weight_grams: float = 1000,
        cost_per_kg: float = 25.0,
        diameter: float = 1.75,
        notes: str = "",
    ) -> Spool:
        """Add a new spool to inventory."""
        spool = Spool(
            id=str(uuid4())[:8],
            material=material.lower(),
            brand=brand,
            color=color,
            weight_grams=weight_grams,
            remaining_grams=weight_grams,
            cost_per_kg=cost_per_kg,
            diameter=diameter,
            purchase_date=datetime.now().isoformat(),
            notes=notes,
        )
        self.spools[spool.id] = spool
        self._save()
        logger.info(f"Added spool {spool.id}: {brand} {material} ({color})")
        return spool

    def remove_spool(self, spool_id: str) -> bool:
        """Remove a spool from inventory."""
        if spool_id in self.spools:
            del self.spools[spool_id]
            self._save()
            logger.info(f"Removed spool {spool_id}")
            return True
        return False

    def get_spool(self, spool_id: str) -> Optional[Spool]:
        """Get a spool by ID."""
        return self.spools.get(spool_id)

    def get_spools_by_material(self, material: str) -> List[Spool]:
        """Get all spools of a specific material."""
        return [s for s in self.spools.values() if s.material == material.lower()]

    def get_spools_by_color(self, color: str) -> List[Spool]:
        """Get all spools of a specific color."""
        color_lower = color.lower()
        return [s for s in self.spools.values() if s.color.lower() == color_lower]

    def use_material(self, spool_id: str, grams: float) -> bool:
        """
        Deduct material usage from a spool.

        Args:
            spool_id: ID of the spool to use
            grams: Amount of material used in grams

        Returns:
            True if successful, False if insufficient material
        """
        spool = self.spools.get(spool_id)
        if spool is None:
            logger.warning(f"Spool {spool_id} not found")
            return False

        if spool.use(grams):
            self._save()
            logger.info(f"Used {grams}g from spool {spool_id}, {spool.remaining_grams}g remaining")
            return True
        else:
            logger.warning(f"Insufficient material in spool {spool_id}")
            return False

    def estimate_usage(self, print_grams: float, material: str) -> List[Spool]:
        """
        Find spools that can fulfill a print job.

        Args:
            print_grams: Estimated material usage for print
            material: Material type required

        Returns:
            List of suitable spools sorted by remaining amount
        """
        suitable = [
            s for s in self.spools.values()
            if s.material == material.lower() and s.remaining_grams >= print_grams
        ]
        # Sort by remaining amount (use older/smaller spools first)
        suitable.sort(key=lambda s: s.remaining_grams)
        return suitable

    def get_low_stock_alerts(self) -> List[LowStockAlert]:
        """Get alerts for spools below threshold."""
        alerts = []
        for spool in self.spools.values():
            if spool.remaining_percent <= self.low_stock_threshold:
                alerts.append(LowStockAlert(
                    spool_id=spool.id,
                    material=spool.material,
                    brand=spool.brand,
                    color=spool.color,
                    remaining_percent=spool.remaining_percent,
                    remaining_grams=spool.remaining_grams,
                    message=f"Low stock: {spool.brand} {spool.material} ({spool.color}) - {spool.remaining_percent:.1f}% remaining",
                ))
        return alerts

    def get_total_inventory_value(self) -> float:
        """Get total value of all inventory."""
        return sum(s.remaining_cost for s in self.spools.values())

    def get_inventory_summary(self) -> Dict[str, any]:
        """Get summary statistics of inventory."""
        if not self.spools:
            return {
                "total_spools": 0,
                "total_weight_grams": 0,
                "total_value": 0,
                "materials": {},
                "low_stock_count": 0,
            }

        materials_summary = {}
        for spool in self.spools.values():
            if spool.material not in materials_summary:
                materials_summary[spool.material] = {
                    "spool_count": 0,
                    "total_grams": 0,
                    "total_value": 0,
                }
            materials_summary[spool.material]["spool_count"] += 1
            materials_summary[spool.material]["total_grams"] += spool.remaining_grams
            materials_summary[spool.material]["total_value"] += spool.remaining_cost

        return {
            "total_spools": len(self.spools),
            "total_weight_grams": sum(s.remaining_grams for s in self.spools.values()),
            "total_value": self.get_total_inventory_value(),
            "materials": materials_summary,
            "low_stock_count": len(self.get_low_stock_alerts()),
        }

    def list_all(self) -> List[Spool]:
        """List all spools in inventory."""
        return list(self.spools.values())
