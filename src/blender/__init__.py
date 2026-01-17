"""Blender automation module for 3D model creation and export."""

# Note: Some imports will fail outside of Blender
# Use runner.py for command-line automation

# Standalone modules (work without Blender)
from .mesh_repair import (
    MeshAnalyzer,
    MeshAnalysis,
    MeshIssue,
    MeshIssueType,
    RepairSeverity,
    analyze_mesh,
    format_analysis,
)

# Blender-dependent modules are imported conditionally
try:
    from .mesh_repair import MeshRepairer
    HAS_BLENDER_REPAIR = True
except:
    HAS_BLENDER_REPAIR = False
    MeshRepairer = None

__all__ = [
    "primitives",
    "exporter",
    "mesh_utils",
    "runner",
    # Mesh repair (standalone)
    "MeshAnalyzer",
    "MeshAnalysis",
    "MeshIssue",
    "MeshIssueType",
    "RepairSeverity",
    "analyze_mesh",
    "format_analysis",
    # Mesh repair (Blender)
    "MeshRepairer",
    "HAS_BLENDER_REPAIR",
]
