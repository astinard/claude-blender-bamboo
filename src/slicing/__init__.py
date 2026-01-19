"""Slicing module for advanced print preparation.

Provides adaptive layer height optimization and slicing utilities.
"""

from src.slicing.adaptive_layers import (
    AdaptiveLayerOptimizer,
    LayerConfig,
    LayerResult,
    LayerRegion,
    OptimizationStrategy,
    create_optimizer,
    analyze_layers,
)

__all__ = [
    "AdaptiveLayerOptimizer",
    "LayerConfig",
    "LayerResult",
    "LayerRegion",
    "OptimizationStrategy",
    "create_optimizer",
    "analyze_layers",
]
