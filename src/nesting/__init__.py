"""Nesting module for optimizing part placement on build plate.

Provides batch nesting to efficiently pack multiple parts.
"""

from src.nesting.batch_nester import (
    BatchNester,
    NestingConfig,
    NestingResult,
    PlacedPart,
    NestingStrategy,
    create_nester,
    nest_parts,
)

__all__ = [
    "BatchNester",
    "NestingConfig",
    "NestingResult",
    "PlacedPart",
    "NestingStrategy",
    "create_nester",
    "nest_parts",
]
