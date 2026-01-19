"""Blender integration and design analysis for Claude Fab Lab."""

from src.blender.overhang_detector import (
    OverhangDetector,
    OverhangInfo,
    OverhangSeverity,
)
from src.blender.design_advisor import (
    DesignAdvisor,
    DesignIssue,
    IssueSeverity,
    DesignAdvice,
    OrientationSuggestion,
)
from src.blender.support_generator import (
    SupportGenerator,
    SupportSettings,
    SupportResult,
    SupportStructure,
    SupportType,
    SupportDensity,
    SupportPattern,
)
from src.blender.support_optimizer import (
    SupportOptimizer,
    OptimizationResult,
    OptimizationSettings,
    OptimizationGoal,
    generate_optimized_supports,
    compare_support_strategies,
)

__all__ = [
    "OverhangDetector",
    "OverhangInfo",
    "OverhangSeverity",
    "DesignAdvisor",
    "DesignIssue",
    "IssueSeverity",
    "DesignAdvice",
    "OrientationSuggestion",
    "SupportGenerator",
    "SupportSettings",
    "SupportResult",
    "SupportStructure",
    "SupportType",
    "SupportDensity",
    "SupportPattern",
    "SupportOptimizer",
    "OptimizationResult",
    "OptimizationSettings",
    "OptimizationGoal",
    "generate_optimized_supports",
    "compare_support_strategies",
]
