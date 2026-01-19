"""Adaptive layer height optimization for 3D printing.

Analyzes model geometry to suggest variable layer heights
for optimal print quality and speed.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("slicing.adaptive_layers")


class OptimizationStrategy(str, Enum):
    """Layer height optimization strategies."""
    QUALITY = "quality"  # Prioritize surface quality
    SPEED = "speed"  # Prioritize print speed
    BALANCED = "balanced"  # Balance quality and speed
    CUSTOM = "custom"  # Custom configuration


@dataclass
class LayerRegion:
    """A region of the model with specific layer height."""
    start_z: float  # Start height in mm
    end_z: float  # End height in mm
    layer_height: float  # Layer height for this region in mm
    reason: str  # Why this layer height was chosen
    curvature: float = 0.0  # Average surface curvature
    overhang_angle: float = 0.0  # Max overhang angle in region

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "start_z": self.start_z,
            "end_z": self.end_z,
            "layer_height": self.layer_height,
            "reason": self.reason,
            "curvature": self.curvature,
            "overhang_angle": self.overhang_angle,
        }


@dataclass
class LayerConfig:
    """Configuration for adaptive layer optimization."""
    # Layer height range
    min_layer_height: float = 0.08  # Minimum layer height in mm
    max_layer_height: float = 0.28  # Maximum layer height in mm
    default_layer_height: float = 0.20  # Default layer height

    # Quality thresholds
    quality_threshold: float = 0.5  # Curvature threshold for fine layers
    overhang_threshold: float = 45.0  # Angle threshold for fine layers

    # Strategy
    strategy: OptimizationStrategy = OptimizationStrategy.BALANCED

    # Nozzle size (affects valid layer heights)
    nozzle_diameter: float = 0.4

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "min_layer_height": self.min_layer_height,
            "max_layer_height": self.max_layer_height,
            "default_layer_height": self.default_layer_height,
            "quality_threshold": self.quality_threshold,
            "overhang_threshold": self.overhang_threshold,
            "strategy": self.strategy.value,
            "nozzle_diameter": self.nozzle_diameter,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LayerConfig":
        """Create from dictionary."""
        return cls(
            min_layer_height=data.get("min_layer_height", 0.08),
            max_layer_height=data.get("max_layer_height", 0.28),
            default_layer_height=data.get("default_layer_height", 0.20),
            quality_threshold=data.get("quality_threshold", 0.5),
            overhang_threshold=data.get("overhang_threshold", 45.0),
            strategy=OptimizationStrategy(data.get("strategy", "balanced")),
            nozzle_diameter=data.get("nozzle_diameter", 0.4),
        )

    @classmethod
    def for_strategy(cls, strategy: OptimizationStrategy) -> "LayerConfig":
        """Create config optimized for a strategy."""
        if strategy == OptimizationStrategy.QUALITY:
            return cls(
                min_layer_height=0.06,
                max_layer_height=0.16,
                default_layer_height=0.12,
                quality_threshold=0.3,
                strategy=strategy,
            )
        elif strategy == OptimizationStrategy.SPEED:
            return cls(
                min_layer_height=0.16,
                max_layer_height=0.32,
                default_layer_height=0.28,
                quality_threshold=0.7,
                strategy=strategy,
            )
        else:  # BALANCED
            return cls(strategy=strategy)


@dataclass
class LayerResult:
    """Result of adaptive layer analysis."""
    success: bool
    regions: List[LayerRegion] = field(default_factory=list)
    total_layers: int = 0
    estimated_time_savings: float = 0.0  # Percentage time saved vs uniform
    quality_score: float = 0.0  # 0-100 quality estimate
    model_height: float = 0.0
    analysis_time: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "regions": [r.to_dict() for r in self.regions],
            "total_layers": self.total_layers,
            "estimated_time_savings": self.estimated_time_savings,
            "quality_score": self.quality_score,
            "model_height": self.model_height,
            "analysis_time": self.analysis_time,
            "error_message": self.error_message,
        }


class AdaptiveLayerOptimizer:
    """
    Adaptive layer height optimizer.

    Analyzes model geometry to determine optimal variable
    layer heights for different regions.
    """

    def __init__(self, config: Optional[LayerConfig] = None):
        """
        Initialize optimizer.

        Args:
            config: Layer configuration
        """
        self.config = config or LayerConfig()

    def analyze_model(self, mesh_path: str) -> LayerResult:
        """
        Analyze a model and determine optimal layer heights.

        Args:
            mesh_path: Path to the mesh file

        Returns:
            Layer analysis result
        """
        start_time = datetime.now()

        mesh = Path(mesh_path)
        if not mesh.exists():
            return LayerResult(
                success=False,
                error_message=f"Mesh file not found: {mesh_path}",
            )

        try:
            # Load and analyze mesh
            vertices, faces = self._load_mesh(mesh)

            if not vertices:
                return LayerResult(
                    success=False,
                    error_message="Failed to load mesh or mesh is empty",
                )

            # Get model bounds
            z_min, z_max = self._get_z_bounds(vertices)
            model_height = z_max - z_min

            if model_height <= 0:
                return LayerResult(
                    success=False,
                    error_message="Invalid model height",
                )

            # Analyze geometry at different heights
            regions = self._analyze_geometry(vertices, faces, z_min, z_max)

            # Calculate statistics
            total_layers = self._count_layers(regions)
            uniform_layers = math.ceil(model_height / self.config.default_layer_height)
            time_savings = max(0, (1 - total_layers / uniform_layers) * 100) if uniform_layers > 0 else 0
            quality_score = self._calculate_quality_score(regions)

            analysis_time = (datetime.now() - start_time).total_seconds()

            return LayerResult(
                success=True,
                regions=regions,
                total_layers=total_layers,
                estimated_time_savings=time_savings,
                quality_score=quality_score,
                model_height=model_height,
                analysis_time=analysis_time,
            )

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return LayerResult(
                success=False,
                error_message=str(e),
                analysis_time=(datetime.now() - start_time).total_seconds(),
            )

    def _load_mesh(self, mesh_path: Path) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
        """Load mesh vertices and faces."""
        vertices = []
        faces = []

        try:
            if mesh_path.suffix.lower() == ".obj":
                with open(mesh_path, "r") as f:
                    for line in f:
                        if line.startswith("v "):
                            parts = line.split()
                            if len(parts) >= 4:
                                vertices.append((
                                    float(parts[1]),
                                    float(parts[2]),
                                    float(parts[3]),
                                ))
                        elif line.startswith("f "):
                            parts = line.split()[1:]
                            # Handle both "1" and "1/2/3" formats
                            indices = []
                            for p in parts[:3]:  # Just triangles
                                idx = int(p.split("/")[0]) - 1
                                indices.append(idx)
                            if len(indices) == 3:
                                faces.append(tuple(indices))

            elif mesh_path.suffix.lower() == ".stl":
                # ASCII STL parser
                with open(mesh_path, "r") as f:
                    content = f.read()

                if "solid" in content.lower() and "vertex" in content.lower():
                    # ASCII STL
                    import re
                    vertex_pattern = r"vertex\s+([\d.e+-]+)\s+([\d.e+-]+)\s+([\d.e+-]+)"
                    matches = re.findall(vertex_pattern, content, re.IGNORECASE)
                    for i, match in enumerate(matches):
                        vertices.append((float(match[0]), float(match[1]), float(match[2])))
                        if (i + 1) % 3 == 0:
                            base = len(vertices) - 3
                            faces.append((base, base + 1, base + 2))

        except Exception as e:
            logger.warning(f"Error loading mesh: {e}")

        return vertices, faces

    def _get_z_bounds(self, vertices: List[Tuple[float, float, float]]) -> Tuple[float, float]:
        """Get min and max Z values."""
        if not vertices:
            return 0.0, 0.0

        z_values = [v[2] for v in vertices]
        return min(z_values), max(z_values)

    def _analyze_geometry(
        self,
        vertices: List[Tuple[float, float, float]],
        faces: List[Tuple[int, int, int]],
        z_min: float,
        z_max: float,
    ) -> List[LayerRegion]:
        """Analyze geometry at different Z heights."""
        regions = []
        model_height = z_max - z_min

        # Sample at regular intervals
        sample_interval = self.config.max_layer_height
        num_samples = max(1, int(model_height / sample_interval))

        for i in range(num_samples):
            start_z = z_min + i * sample_interval
            end_z = min(z_min + (i + 1) * sample_interval, z_max)

            # Analyze this region
            curvature = self._estimate_curvature(vertices, faces, start_z, end_z)
            overhang = self._estimate_overhang(vertices, faces, start_z, end_z)

            # Determine appropriate layer height
            layer_height, reason = self._select_layer_height(curvature, overhang)

            regions.append(LayerRegion(
                start_z=start_z,
                end_z=end_z,
                layer_height=layer_height,
                reason=reason,
                curvature=curvature,
                overhang_angle=overhang,
            ))

        # Merge adjacent regions with same layer height
        regions = self._merge_regions(regions)

        return regions

    def _estimate_curvature(
        self,
        vertices: List[Tuple[float, float, float]],
        faces: List[Tuple[int, int, int]],
        z_min: float,
        z_max: float,
    ) -> float:
        """Estimate surface curvature in a Z range."""
        # Simplified curvature estimation based on vertex density variation
        region_vertices = [v for v in vertices if z_min <= v[2] <= z_max]

        if len(region_vertices) < 3:
            return 0.0

        # Calculate variance in X and Y positions as proxy for curvature
        x_vals = [v[0] for v in region_vertices]
        y_vals = [v[1] for v in region_vertices]

        x_variance = self._variance(x_vals)
        y_variance = self._variance(y_vals)

        # Normalize to 0-1 range
        curvature = min(1.0, math.sqrt(x_variance + y_variance) / 10.0)
        return curvature

    def _estimate_overhang(
        self,
        vertices: List[Tuple[float, float, float]],
        faces: List[Tuple[int, int, int]],
        z_min: float,
        z_max: float,
    ) -> float:
        """Estimate maximum overhang angle in a Z range."""
        max_overhang = 0.0

        for face in faces:
            if face[0] >= len(vertices) or face[1] >= len(vertices) or face[2] >= len(vertices):
                continue

            v0 = vertices[face[0]]
            v1 = vertices[face[1]]
            v2 = vertices[face[2]]

            # Check if face is in Z range
            face_z = (v0[2] + v1[2] + v2[2]) / 3
            if not (z_min <= face_z <= z_max):
                continue

            # Calculate face normal
            normal = self._calculate_normal(v0, v1, v2)
            if normal is None:
                continue

            # Overhang angle from horizontal (90 - angle from vertical)
            vertical_component = abs(normal[2])
            angle = 90 - math.degrees(math.acos(min(1.0, vertical_component)))
            max_overhang = max(max_overhang, angle)

        return max_overhang

    def _calculate_normal(
        self,
        v0: Tuple[float, float, float],
        v1: Tuple[float, float, float],
        v2: Tuple[float, float, float],
    ) -> Optional[Tuple[float, float, float]]:
        """Calculate face normal vector."""
        # Edge vectors
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

        # Cross product
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]

        # Normalize
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length < 1e-10:
            return None

        return (nx / length, ny / length, nz / length)

    def _variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)

    def _select_layer_height(self, curvature: float, overhang: float) -> Tuple[float, str]:
        """Select appropriate layer height based on geometry."""
        config = self.config

        # Check strategy
        if config.strategy == OptimizationStrategy.QUALITY:
            # Prefer finer layers
            if curvature > config.quality_threshold or overhang > config.overhang_threshold:
                return config.min_layer_height, "High detail region"
            else:
                return config.default_layer_height, "Standard quality"

        elif config.strategy == OptimizationStrategy.SPEED:
            # Prefer coarser layers
            if overhang > 60:  # Only fine for extreme overhangs
                return config.default_layer_height, "Overhang support"
            else:
                return config.max_layer_height, "Speed optimized"

        else:  # BALANCED
            if curvature > config.quality_threshold:
                return config.min_layer_height, "High curvature detected"
            elif overhang > config.overhang_threshold:
                return config.min_layer_height + 0.04, "Moderate overhang"
            elif curvature < 0.1 and overhang < 20:
                return config.max_layer_height, "Flat region"
            else:
                return config.default_layer_height, "Standard region"

    def _merge_regions(self, regions: List[LayerRegion]) -> List[LayerRegion]:
        """Merge adjacent regions with same layer height."""
        if not regions:
            return []

        merged = [regions[0]]

        for region in regions[1:]:
            last = merged[-1]
            if abs(last.layer_height - region.layer_height) < 0.01:
                # Same layer height, merge
                merged[-1] = LayerRegion(
                    start_z=last.start_z,
                    end_z=region.end_z,
                    layer_height=last.layer_height,
                    reason=last.reason,
                    curvature=max(last.curvature, region.curvature),
                    overhang_angle=max(last.overhang_angle, region.overhang_angle),
                )
            else:
                merged.append(region)

        return merged

    def _count_layers(self, regions: List[LayerRegion]) -> int:
        """Count total layers across all regions."""
        total = 0
        for region in regions:
            height = region.end_z - region.start_z
            if region.layer_height > 0:
                total += math.ceil(height / region.layer_height)
        return total

    def _calculate_quality_score(self, regions: List[LayerRegion]) -> float:
        """Calculate estimated quality score (0-100)."""
        if not regions:
            return 0.0

        # Score based on using appropriate layer heights
        score = 100.0

        for region in regions:
            # Penalty for coarse layers in curved areas
            if region.curvature > 0.3 and region.layer_height > 0.15:
                score -= 10 * region.curvature

            # Penalty for coarse layers in overhang areas
            if region.overhang_angle > 45 and region.layer_height > 0.12:
                score -= 5

        return max(0, min(100, score))

    def get_layer_heights_at_z(self, result: LayerResult, z: float) -> float:
        """Get the layer height at a specific Z position."""
        for region in result.regions:
            if region.start_z <= z <= region.end_z:
                return region.layer_height
        return self.config.default_layer_height

    def export_to_gcode_variable_layer(self, result: LayerResult) -> str:
        """Export variable layer configuration for slicer."""
        lines = ["; Variable layer height configuration",
                 f"; Generated: {datetime.now().isoformat()}",
                 f"; Total layers: {result.total_layers}",
                 f"; Quality score: {result.quality_score:.1f}",
                 ""]

        for i, region in enumerate(result.regions):
            lines.append(f"; Region {i + 1}: Z={region.start_z:.2f}-{region.end_z:.2f}mm")
            lines.append(f";   Layer height: {region.layer_height:.2f}mm")
            lines.append(f";   Reason: {region.reason}")
            lines.append("")

        return "\n".join(lines)


# Convenience functions
def create_optimizer(
    strategy: str = "balanced",
    min_layer: float = 0.08,
    max_layer: float = 0.28,
) -> AdaptiveLayerOptimizer:
    """Create an optimizer with the specified settings."""
    config = LayerConfig(
        min_layer_height=min_layer,
        max_layer_height=max_layer,
        strategy=OptimizationStrategy(strategy),
    )
    return AdaptiveLayerOptimizer(config=config)


def analyze_layers(
    mesh_path: str,
    strategy: str = "balanced",
) -> LayerResult:
    """
    Analyze a mesh for adaptive layer heights.

    Args:
        mesh_path: Path to the mesh file
        strategy: Optimization strategy (quality, speed, balanced)

    Returns:
        Layer analysis result
    """
    config = LayerConfig.for_strategy(OptimizationStrategy(strategy))
    optimizer = AdaptiveLayerOptimizer(config=config)
    return optimizer.analyze_model(mesh_path)
