"""
AMS (Automatic Material System) Manager for Bambu Lab printers.

Manages the mapping between model colors/materials and physical filament slots.
Supports:
- Bambu Lab X1 Carbon: 4 AMS units x 4 slots = 16 colors max
- Bambu Lab H2D: Same AMS support

The AMS manager handles:
1. Tracking what filaments are loaded in each AMS slot
2. Automatically mapping model colors to best-matching slots
3. Suggesting which filaments to load for a given model
4. Generating print commands with correct AMS mappings
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math


@dataclass
class FilamentInfo:
    """Information about a loaded filament."""
    color: Tuple[float, float, float]  # RGB 0-1
    color_name: str  # Human-readable name (e.g., "red", "white")
    material_type: str  # PLA, PETG, TPU, etc.
    brand: str = ""
    weight_remaining: float = 100.0  # Percentage remaining
    nozzle_temp: int = 210  # Recommended nozzle temp


@dataclass
class AMSSlot:
    """Represents a single AMS slot."""
    unit: int  # AMS unit number (0-3)
    slot: int  # Slot within unit (0-3)
    filament: Optional[FilamentInfo] = None
    is_empty: bool = True

    @property
    def global_index(self) -> int:
        """Get global slot index (0-15)."""
        return self.unit * 4 + self.slot

    @property
    def display_name(self) -> str:
        """Get human-readable slot name."""
        if self.is_empty or self.filament is None:
            return f"AMS{self.unit + 1} Slot {self.slot + 1} (Empty)"
        return f"AMS{self.unit + 1} Slot {self.slot + 1}: {self.filament.color_name} {self.filament.material_type}"


class AMSManager:
    """
    Manages AMS slots and color-to-slot mapping.

    Usage:
        manager = AMSManager()

        # Configure loaded filaments
        manager.set_slot(0, 0, FilamentInfo(
            color=(1.0, 0.0, 0.0),
            color_name="Red",
            material_type="PLA"
        ))

        # Get mapping for model colors
        model_colors = [(1.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 1.0)]
        mapping = manager.suggest_mapping(model_colors)
        # Returns {0: 0, 1: 3} meaning color 0 -> slot 0, color 1 -> slot 3
    """

    def __init__(self, num_units: int = 4, slots_per_unit: int = 4):
        """
        Initialize AMS manager.

        Args:
            num_units: Number of AMS units (default 4 for X1/H2D)
            slots_per_unit: Slots per unit (default 4)
        """
        self.num_units = num_units
        self.slots_per_unit = slots_per_unit
        self.slots: List[AMSSlot] = []

        # Initialize all slots
        for unit in range(num_units):
            for slot in range(slots_per_unit):
                self.slots.append(AMSSlot(unit=unit, slot=slot))

    @property
    def max_slots(self) -> int:
        """Maximum number of filament slots."""
        return self.num_units * self.slots_per_unit

    def get_slot(self, unit: int, slot: int) -> AMSSlot:
        """Get slot by unit and slot number."""
        idx = unit * self.slots_per_unit + slot
        return self.slots[idx]

    def get_slot_by_index(self, index: int) -> AMSSlot:
        """Get slot by global index (0-15)."""
        return self.slots[index]

    def set_slot(self, unit: int, slot: int, filament: FilamentInfo):
        """Load filament into slot."""
        ams_slot = self.get_slot(unit, slot)
        ams_slot.filament = filament
        ams_slot.is_empty = False

    def clear_slot(self, unit: int, slot: int):
        """Clear/empty a slot."""
        ams_slot = self.get_slot(unit, slot)
        ams_slot.filament = None
        ams_slot.is_empty = True

    def get_loaded_slots(self) -> List[AMSSlot]:
        """Get all slots with filament loaded."""
        return [s for s in self.slots if not s.is_empty]

    def get_empty_slots(self) -> List[AMSSlot]:
        """Get all empty slots."""
        return [s for s in self.slots if s.is_empty]

    @staticmethod
    def color_distance(c1: Tuple[float, float, float], c2: Tuple[float, float, float]) -> float:
        """
        Calculate color distance using weighted Euclidean in RGB space.
        Weights are perceptually adjusted (human eye is more sensitive to green).
        """
        # Weighted RGB distance
        r_weight = 0.30
        g_weight = 0.59
        b_weight = 0.11

        dr = (c1[0] - c2[0]) * r_weight
        dg = (c1[1] - c2[1]) * g_weight
        db = (c1[2] - c2[2]) * b_weight

        return math.sqrt(dr * dr + dg * dg + db * db)

    def find_closest_slot(self, color: Tuple[float, float, float],
                          exclude: List[int] = None) -> Optional[AMSSlot]:
        """
        Find the slot with the closest color match.

        Args:
            color: Target RGB color (0-1)
            exclude: List of slot indices to exclude

        Returns:
            Best matching slot or None
        """
        exclude = exclude or []
        loaded = [s for s in self.get_loaded_slots() if s.global_index not in exclude]

        if not loaded:
            return None

        best_slot = None
        best_distance = float('inf')

        for slot in loaded:
            if slot.filament is None:
                continue
            distance = self.color_distance(color, slot.filament.color)
            if distance < best_distance:
                best_distance = distance
                best_slot = slot

        return best_slot

    def suggest_mapping(self, model_colors: List[Tuple[float, float, float, float]],
                        strict: bool = False) -> Dict[int, int]:
        """
        Suggest AMS slot mapping for model colors.

        Args:
            model_colors: List of RGBA colors from the model
            strict: If True, only map exact matches

        Returns:
            Dict mapping color index to AMS slot index
        """
        mapping = {}
        used_slots = []

        for i, rgba in enumerate(model_colors):
            rgb = (rgba[0], rgba[1], rgba[2])

            # Find closest available slot
            slot = self.find_closest_slot(rgb, exclude=used_slots)

            if slot is not None:
                distance = self.color_distance(rgb, slot.filament.color)

                # In strict mode, only accept very close matches
                if strict and distance > 0.1:
                    continue

                mapping[i] = slot.global_index
                used_slots.append(slot.global_index)
            else:
                # No slot available, use index directly (may fail at print time)
                mapping[i] = i % self.max_slots

        return mapping

    def get_missing_colors(self, model_colors: List[Tuple[float, float, float, float]],
                           threshold: float = 0.2) -> List[Tuple[int, Tuple[float, float, float]]]:
        """
        Find model colors that don't have a close match in loaded filaments.

        Args:
            model_colors: List of RGBA colors
            threshold: Color distance threshold for "close enough"

        Returns:
            List of (color_index, rgb) tuples for colors needing new filament
        """
        missing = []

        for i, rgba in enumerate(model_colors):
            rgb = (rgba[0], rgba[1], rgba[2])
            slot = self.find_closest_slot(rgb)

            if slot is None:
                missing.append((i, rgb))
            elif slot.filament is not None:
                distance = self.color_distance(rgb, slot.filament.color)
                if distance > threshold:
                    missing.append((i, rgb))

        return missing

    def suggest_filament_load(self, model_colors: List[Tuple[float, float, float, float]]) -> List[Dict]:
        """
        Suggest which filaments to load for a model.

        Returns list of suggestions with slot and color info.
        """
        suggestions = []
        missing = self.get_missing_colors(model_colors)
        empty_slots = self.get_empty_slots()

        for i, (color_idx, rgb) in enumerate(missing):
            if i < len(empty_slots):
                slot = empty_slots[i]
                suggestions.append({
                    "action": "load",
                    "unit": slot.unit,
                    "slot": slot.slot,
                    "color": rgb,
                    "color_name": self._rgb_to_name(rgb),
                    "reason": f"Model color {color_idx} needs this color"
                })
            else:
                suggestions.append({
                    "action": "replace",
                    "color": rgb,
                    "color_name": self._rgb_to_name(rgb),
                    "reason": f"No empty slot for color {color_idx}, replace existing"
                })

        return suggestions

    def _rgb_to_name(self, rgb: Tuple[float, float, float]) -> str:
        """Convert RGB to approximate color name."""
        # Simple color naming
        r, g, b = rgb

        if r > 0.8 and g > 0.8 and b > 0.8:
            return "white"
        if r < 0.2 and g < 0.2 and b < 0.2:
            return "black"
        if r > 0.7 and g < 0.3 and b < 0.3:
            return "red"
        if r < 0.3 and g > 0.7 and b < 0.3:
            return "green"
        if r < 0.3 and g < 0.3 and b > 0.7:
            return "blue"
        if r > 0.7 and g > 0.7 and b < 0.3:
            return "yellow"
        if r > 0.7 and g > 0.3 and b < 0.3:
            return "orange"
        if r > 0.5 and g < 0.3 and b > 0.5:
            return "purple"
        if r > 0.4 and g > 0.4 and b > 0.4:
            return "gray"

        return f"RGB({int(r*255)},{int(g*255)},{int(b*255)})"

    def configure_from_printer_status(self, ams_status: Dict):
        """
        Configure AMS slots from printer status.

        Args:
            ams_status: AMS status from BambuRealPrinter.get_ams_status()
        """
        for slot_info in ams_status.get("slots", []):
            unit = slot_info.get("unit", 0)
            slot = slot_info.get("slot", 0)
            color = slot_info.get("color", "#FFFFFF")
            material = slot_info.get("material", "PLA")

            # Parse hex color
            if color.startswith("#"):
                r = int(color[1:3], 16) / 255.0
                g = int(color[3:5], 16) / 255.0
                b = int(color[5:7], 16) / 255.0
            else:
                r = g = b = 0.8  # Default gray

            filament = FilamentInfo(
                color=(r, g, b),
                color_name=self._rgb_to_name((r, g, b)),
                material_type=material
            )
            self.set_slot(unit, slot, filament)

    def to_ams_mapping_list(self, color_mapping: Dict[int, int]) -> List[int]:
        """
        Convert color mapping dict to AMS mapping list for print command.

        The list format is what Bambu printers expect:
        [slot_for_color0, slot_for_color1, slot_for_color2, ...]
        """
        if not color_mapping:
            return []

        max_color = max(color_mapping.keys()) + 1
        result = [0] * max_color

        for color_idx, slot_idx in color_mapping.items():
            result[color_idx] = slot_idx

        return result

    def __str__(self) -> str:
        """String representation of AMS status."""
        lines = ["AMS Status:"]
        for slot in self.slots:
            if not slot.is_empty:
                lines.append(f"  {slot.display_name}")
        if len(lines) == 1:
            lines.append("  (No filaments loaded)")
        return "\n".join(lines)


# Convenience function for common setup
def create_ams_manager_with_defaults() -> AMSManager:
    """
    Create AMS manager with common default filaments.

    Sets up:
    - Slot 0: White PLA
    - Slot 1: Black PLA
    - Slot 2: Red PLA
    - Slot 3: Blue PLA
    """
    manager = AMSManager()

    defaults = [
        (0, 0, (1.0, 1.0, 1.0), "White", "PLA"),
        (0, 1, (0.0, 0.0, 0.0), "Black", "PLA"),
        (0, 2, (1.0, 0.0, 0.0), "Red", "PLA"),
        (0, 3, (0.0, 0.0, 1.0), "Blue", "PLA"),
    ]

    for unit, slot, color, name, material in defaults:
        manager.set_slot(unit, slot, FilamentInfo(
            color=color,
            color_name=name,
            material_type=material
        ))

    return manager


if __name__ == "__main__":
    # Test the AMS manager
    manager = create_ams_manager_with_defaults()
    print(manager)

    # Test color mapping
    model_colors = [
        (1.0, 0.0, 0.0, 1.0),  # Red
        (0.0, 0.0, 1.0, 1.0),  # Blue
        (1.0, 1.0, 1.0, 1.0),  # White
        (0.0, 1.0, 0.0, 1.0),  # Green (not loaded)
    ]

    print("\nModel colors:")
    for i, c in enumerate(model_colors):
        print(f"  {i}: RGB({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})")

    mapping = manager.suggest_mapping(model_colors)
    print(f"\nSuggested mapping: {mapping}")

    missing = manager.get_missing_colors(model_colors)
    print(f"Missing colors: {missing}")

    suggestions = manager.suggest_filament_load(model_colors)
    print(f"\nLoad suggestions:")
    for s in suggestions:
        print(f"  {s}")

    ams_list = manager.to_ams_mapping_list(mapping)
    print(f"\nAMS mapping list for print command: {ams_list}")
