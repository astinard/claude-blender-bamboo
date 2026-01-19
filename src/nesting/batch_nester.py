"""Batch nesting for optimizing part placement on build plate.

Efficiently packs multiple parts to minimize print time and waste.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("nesting.batch_nester")


class NestingStrategy(str, Enum):
    """Nesting optimization strategies."""
    DENSITY = "density"  # Maximize plate utilization
    HEIGHT = "height"  # Group by similar heights
    SPACING = "spacing"  # Prioritize part spacing
    SEQUENTIAL = "sequential"  # Simple row-by-row


@dataclass
class PlacedPart:
    """A part placed on the build plate."""
    name: str
    file_path: str
    x: float  # X position on plate
    y: float  # Y position on plate
    rotation: float  # Z rotation in degrees
    width: float  # Part bounding box width
    depth: float  # Part bounding box depth
    height: float  # Part height

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "file_path": self.file_path,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
        }


@dataclass
class NestingConfig:
    """Configuration for batch nesting."""
    # Build plate dimensions (mm)
    plate_width: float = 256.0  # X1C build plate
    plate_depth: float = 256.0
    plate_height: float = 256.0

    # Spacing
    part_spacing: float = 5.0  # Minimum spacing between parts
    edge_margin: float = 10.0  # Margin from plate edges

    # Strategy
    strategy: NestingStrategy = NestingStrategy.DENSITY

    # Options
    allow_rotation: bool = True  # Allow 90 degree rotations
    group_by_height: bool = False  # Group similar heights

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "plate_width": self.plate_width,
            "plate_depth": self.plate_depth,
            "plate_height": self.plate_height,
            "part_spacing": self.part_spacing,
            "edge_margin": self.edge_margin,
            "strategy": self.strategy.value,
            "allow_rotation": self.allow_rotation,
            "group_by_height": self.group_by_height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NestingConfig":
        """Create from dictionary."""
        return cls(
            plate_width=data.get("plate_width", 256.0),
            plate_depth=data.get("plate_depth", 256.0),
            plate_height=data.get("plate_height", 256.0),
            part_spacing=data.get("part_spacing", 5.0),
            edge_margin=data.get("edge_margin", 10.0),
            strategy=NestingStrategy(data.get("strategy", "density")),
            allow_rotation=data.get("allow_rotation", True),
            group_by_height=data.get("group_by_height", False),
        )

    @classmethod
    def for_printer(cls, printer_model: str) -> "NestingConfig":
        """Create config for specific printer."""
        configs = {
            "bambu_x1c": cls(plate_width=256.0, plate_depth=256.0, plate_height=256.0),
            "bambu_p1s": cls(plate_width=256.0, plate_depth=256.0, plate_height=256.0),
            "bambu_a1": cls(plate_width=256.0, plate_depth=256.0, plate_height=256.0),
        }
        return configs.get(printer_model, cls())


@dataclass
class NestingResult:
    """Result of batch nesting operation."""
    success: bool
    placed_parts: List[PlacedPart] = field(default_factory=list)
    unplaced_parts: List[str] = field(default_factory=list)
    plate_utilization: float = 0.0  # Percentage of plate used
    total_height: float = 0.0  # Maximum height of nested parts
    num_batches: int = 1  # Number of print batches needed
    processing_time: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "placed_parts": [p.to_dict() for p in self.placed_parts],
            "unplaced_parts": self.unplaced_parts,
            "plate_utilization": self.plate_utilization,
            "total_height": self.total_height,
            "num_batches": self.num_batches,
            "processing_time": self.processing_time,
            "error_message": self.error_message,
        }


class BatchNester:
    """
    Batch nesting optimizer for build plate layout.

    Efficiently arranges multiple parts to maximize plate
    utilization and minimize print batches.
    """

    def __init__(self, config: Optional[NestingConfig] = None):
        """
        Initialize batch nester.

        Args:
            config: Nesting configuration
        """
        self.config = config or NestingConfig()

    def nest_parts(self, part_paths: List[str]) -> NestingResult:
        """
        Nest multiple parts on the build plate.

        Args:
            part_paths: List of paths to part files

        Returns:
            Nesting result with part placements
        """
        start_time = datetime.now()

        if not part_paths:
            return NestingResult(
                success=False,
                error_message="No parts provided",
            )

        try:
            # Load part dimensions
            parts = []
            for path in part_paths:
                dims = self._get_part_dimensions(path)
                if dims:
                    parts.append({
                        "path": path,
                        "name": Path(path).stem,
                        "width": dims[0],
                        "depth": dims[1],
                        "height": dims[2],
                    })
                else:
                    logger.warning(f"Could not load dimensions for: {path}")

            if not parts:
                return NestingResult(
                    success=False,
                    error_message="Could not load any part dimensions",
                )

            # Sort parts by strategy
            parts = self._sort_parts(parts)

            # Place parts on plate
            placed, unplaced = self._place_parts(parts)

            # Calculate statistics
            utilization = self._calculate_utilization(placed)
            max_height = max((p.height for p in placed), default=0)
            num_batches = 1 + len(unplaced) // max(1, len(placed)) if unplaced else 1

            processing_time = (datetime.now() - start_time).total_seconds()

            return NestingResult(
                success=True,
                placed_parts=placed,
                unplaced_parts=unplaced,
                plate_utilization=utilization,
                total_height=max_height,
                num_batches=num_batches,
                processing_time=processing_time,
            )

        except Exception as e:
            logger.error(f"Nesting error: {e}")
            return NestingResult(
                success=False,
                error_message=str(e),
                processing_time=(datetime.now() - start_time).total_seconds(),
            )

    def _get_part_dimensions(self, path: str) -> Optional[Tuple[float, float, float]]:
        """Get bounding box dimensions of a part."""
        mesh = Path(path)
        if not mesh.exists():
            return None

        try:
            # Parse mesh to get bounds
            min_x = min_y = min_z = float('inf')
            max_x = max_y = max_z = float('-inf')

            if mesh.suffix.lower() == ".obj":
                with open(mesh, "r") as f:
                    for line in f:
                        if line.startswith("v "):
                            parts = line.split()
                            if len(parts) >= 4:
                                x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                                min_x, max_x = min(min_x, x), max(max_x, x)
                                min_y, max_y = min(min_y, y), max(max_y, y)
                                min_z, max_z = min(min_z, z), max(max_z, z)

            elif mesh.suffix.lower() == ".stl":
                import re
                with open(mesh, "r") as f:
                    content = f.read()
                vertex_pattern = r"vertex\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)"
                for match in re.finditer(vertex_pattern, content, re.IGNORECASE):
                    x, y, z = float(match.group(1)), float(match.group(2)), float(match.group(3))
                    min_x, max_x = min(min_x, x), max(max_x, x)
                    min_y, max_y = min(min_y, y), max(max_y, y)
                    min_z, max_z = min(min_z, z), max(max_z, z)

            if min_x == float('inf'):
                return None

            return (max_x - min_x, max_y - min_y, max_z - min_z)

        except Exception as e:
            logger.warning(f"Error reading dimensions from {path}: {e}")
            return None

    def _sort_parts(self, parts: List[dict]) -> List[dict]:
        """Sort parts based on nesting strategy."""
        if self.config.strategy == NestingStrategy.DENSITY:
            # Sort by area (largest first)
            return sorted(parts, key=lambda p: p["width"] * p["depth"], reverse=True)

        elif self.config.strategy == NestingStrategy.HEIGHT:
            # Sort by height (tallest first)
            return sorted(parts, key=lambda p: p["height"], reverse=True)

        elif self.config.strategy == NestingStrategy.SPACING:
            # Sort by diagonal (largest first)
            return sorted(
                parts,
                key=lambda p: math.sqrt(p["width"]**2 + p["depth"]**2),
                reverse=True
            )

        else:  # SEQUENTIAL
            return parts

    def _place_parts(self, parts: List[dict]) -> Tuple[List[PlacedPart], List[str]]:
        """Place parts on the build plate."""
        placed = []
        unplaced = []

        # Available area
        usable_width = self.config.plate_width - 2 * self.config.edge_margin
        usable_depth = self.config.plate_depth - 2 * self.config.edge_margin

        # Track occupied spaces
        occupied = []  # List of (x, y, width, depth) rectangles

        for part in parts:
            width = part["width"]
            depth = part["depth"]
            height = part["height"]

            # Check if part fits at all
            if width > usable_width or depth > usable_depth:
                if self.config.allow_rotation:
                    # Try rotated
                    if depth <= usable_width and width <= usable_depth:
                        width, depth = depth, width
                        rotation = 90.0
                    else:
                        unplaced.append(part["path"])
                        continue
                else:
                    unplaced.append(part["path"])
                    continue
            else:
                rotation = 0.0

            # Find position using bottom-left placement
            position = self._find_position(width, depth, occupied, usable_width, usable_depth)

            if position:
                x, y = position
                placed.append(PlacedPart(
                    name=part["name"],
                    file_path=part["path"],
                    x=x + self.config.edge_margin,
                    y=y + self.config.edge_margin,
                    rotation=rotation,
                    width=width,
                    depth=depth,
                    height=height,
                ))
                occupied.append((x, y, width + self.config.part_spacing,
                               depth + self.config.part_spacing))
            else:
                unplaced.append(part["path"])

        return placed, unplaced

    def _find_position(
        self,
        width: float,
        depth: float,
        occupied: List[Tuple[float, float, float, float]],
        max_width: float,
        max_depth: float,
    ) -> Optional[Tuple[float, float]]:
        """Find a position for a part using bottom-left algorithm."""
        # Try positions at regular intervals
        step = self.config.part_spacing

        for y in range(0, int(max_depth - depth) + 1, int(max(1, step))):
            for x in range(0, int(max_width - width) + 1, int(max(1, step))):
                if self._can_place(x, y, width, depth, occupied):
                    return (float(x), float(y))

        return None

    def _can_place(
        self,
        x: float,
        y: float,
        width: float,
        depth: float,
        occupied: List[Tuple[float, float, float, float]],
    ) -> bool:
        """Check if a part can be placed at the given position."""
        for ox, oy, ow, od in occupied:
            # Check for overlap
            if (x < ox + ow and x + width > ox and
                y < oy + od and y + depth > oy):
                return False
        return True

    def _calculate_utilization(self, placed: List[PlacedPart]) -> float:
        """Calculate plate utilization percentage."""
        if not placed:
            return 0.0

        total_area = sum(p.width * p.depth for p in placed)
        plate_area = (
            (self.config.plate_width - 2 * self.config.edge_margin) *
            (self.config.plate_depth - 2 * self.config.edge_margin)
        )

        return min(100.0, (total_area / plate_area) * 100)

    def estimate_batches(self, part_paths: List[str]) -> int:
        """Estimate number of print batches needed."""
        result = self.nest_parts(part_paths)
        return result.num_batches

    def export_layout(self, result: NestingResult) -> str:
        """Export layout as text description."""
        lines = [
            f"; Build plate layout",
            f"; Plate: {self.config.plate_width}x{self.config.plate_depth}mm",
            f"; Utilization: {result.plate_utilization:.1f}%",
            f"; Parts placed: {len(result.placed_parts)}",
            "",
        ]

        for i, part in enumerate(result.placed_parts):
            lines.append(f"; Part {i + 1}: {part.name}")
            lines.append(f";   Position: ({part.x:.1f}, {part.y:.1f})")
            lines.append(f";   Size: {part.width:.1f}x{part.depth:.1f}x{part.height:.1f}")
            lines.append(f";   Rotation: {part.rotation}\u00b0")
            lines.append("")

        if result.unplaced_parts:
            lines.append(f"; Unplaced parts ({len(result.unplaced_parts)}):")
            for path in result.unplaced_parts:
                lines.append(f";   - {Path(path).name}")

        return "\n".join(lines)


# Convenience functions
def create_nester(
    plate_width: float = 256.0,
    plate_depth: float = 256.0,
    strategy: str = "density",
) -> BatchNester:
    """Create a batch nester with specified settings."""
    config = NestingConfig(
        plate_width=plate_width,
        plate_depth=plate_depth,
        strategy=NestingStrategy(strategy),
    )
    return BatchNester(config=config)


def nest_parts(
    part_paths: List[str],
    plate_size: float = 256.0,
    strategy: str = "density",
) -> NestingResult:
    """
    Nest parts on a build plate.

    Args:
        part_paths: List of paths to part files
        plate_size: Build plate size (square)
        strategy: Nesting strategy

    Returns:
        Nesting result
    """
    config = NestingConfig(
        plate_width=plate_size,
        plate_depth=plate_size,
        strategy=NestingStrategy(strategy),
    )
    nester = BatchNester(config=config)
    return nester.nest_parts(part_paths)
