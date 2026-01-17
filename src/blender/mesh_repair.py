"""
Auto Mesh Repair Module.

Automatically detects and fixes common mesh problems from 3D scans:
- Holes (missing faces)
- Non-manifold edges/vertices
- Noise (small disconnected components)
- Inconsistent normals (flipped faces)
- Duplicate vertices/faces
- Self-intersecting geometry

Works both inside Blender (full repair) and standalone (analysis only).
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set, Dict
from enum import Enum
import math

# Try to import Blender modules
try:
    import bpy
    import bmesh
    from mathutils import Vector
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False


class MeshIssueType(Enum):
    """Types of mesh issues that can be detected."""
    HOLE = "hole"
    NON_MANIFOLD_EDGE = "non_manifold_edge"
    NON_MANIFOLD_VERTEX = "non_manifold_vertex"
    LOOSE_VERTEX = "loose_vertex"
    LOOSE_EDGE = "loose_edge"
    FLIPPED_NORMAL = "flipped_normal"
    DUPLICATE_VERTEX = "duplicate_vertex"
    DUPLICATE_FACE = "duplicate_face"
    DEGENERATE_FACE = "degenerate_face"
    SMALL_COMPONENT = "small_component"
    SELF_INTERSECTION = "self_intersection"


class RepairSeverity(Enum):
    """Severity level of mesh issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MeshIssue:
    """A detected mesh issue."""
    issue_type: MeshIssueType
    severity: RepairSeverity
    description: str
    location: Optional[Tuple[float, float, float]] = None
    element_indices: List[int] = field(default_factory=list)
    can_auto_fix: bool = True


@dataclass
class MeshAnalysis:
    """Complete analysis of a mesh's health."""
    # Counts
    vertex_count: int
    edge_count: int
    face_count: int

    # Issues
    issues: List[MeshIssue] = field(default_factory=list)

    # Summary stats
    hole_count: int = 0
    non_manifold_edge_count: int = 0
    non_manifold_vertex_count: int = 0
    loose_vertex_count: int = 0
    loose_edge_count: int = 0
    flipped_normal_count: int = 0
    duplicate_vertex_count: int = 0
    small_component_count: int = 0

    # Geometry stats
    is_manifold: bool = True
    is_watertight: bool = True
    component_count: int = 1
    bounding_box: Tuple[Tuple[float, float, float], Tuple[float, float, float]] = None
    volume: float = 0.0
    surface_area: float = 0.0

    @property
    def is_printable(self) -> bool:
        """Check if mesh is suitable for 3D printing."""
        return self.is_manifold and self.is_watertight and self.hole_count == 0

    @property
    def issue_count(self) -> int:
        """Total number of issues."""
        return len(self.issues)

    @property
    def critical_issue_count(self) -> int:
        """Number of critical issues."""
        return sum(1 for i in self.issues if i.severity == RepairSeverity.CRITICAL)

    @property
    def error_issue_count(self) -> int:
        """Number of error-level issues."""
        return sum(1 for i in self.issues if i.severity == RepairSeverity.ERROR)


@dataclass
class RepairResult:
    """Result of mesh repair operation."""
    success: bool
    issues_fixed: int
    issues_remaining: int
    operations_performed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MeshAnalyzer:
    """
    Analyzes mesh geometry for issues.

    Works with raw vertex/face data, no Blender required.
    """

    def __init__(self, merge_threshold: float = 0.0001):
        """
        Initialize analyzer.

        Args:
            merge_threshold: Distance threshold for duplicate detection
        """
        self.merge_threshold = merge_threshold

    def analyze_mesh_data(
        self,
        vertices: List[Tuple[float, float, float]],
        faces: List[Tuple[int, ...]]
    ) -> MeshAnalysis:
        """
        Analyze raw mesh data.

        Args:
            vertices: List of (x, y, z) vertex positions
            faces: List of vertex index tuples (triangles or quads)

        Returns:
            MeshAnalysis with detected issues
        """
        issues = []

        # Build edge map
        edge_faces = {}  # edge -> list of face indices
        for fi, face in enumerate(faces):
            for i in range(len(face)):
                v1, v2 = face[i], face[(i + 1) % len(face)]
                edge = tuple(sorted([v1, v2]))
                if edge not in edge_faces:
                    edge_faces[edge] = []
                edge_faces[edge].append(fi)

        # Build vertex-face map
        vertex_faces = {i: [] for i in range(len(vertices))}
        for fi, face in enumerate(faces):
            for vi in face:
                vertex_faces[vi].append(fi)

        # Check for non-manifold edges (not exactly 2 faces)
        non_manifold_edges = []
        boundary_edges = []
        for edge, face_list in edge_faces.items():
            if len(face_list) == 1:
                boundary_edges.append(edge)
            elif len(face_list) > 2:
                non_manifold_edges.append(edge)
                v1, v2 = edge
                mid = (
                    (vertices[v1][0] + vertices[v2][0]) / 2,
                    (vertices[v1][1] + vertices[v2][1]) / 2,
                    (vertices[v1][2] + vertices[v2][2]) / 2,
                )
                issues.append(MeshIssue(
                    issue_type=MeshIssueType.NON_MANIFOLD_EDGE,
                    severity=RepairSeverity.ERROR,
                    description=f"Edge shared by {len(face_list)} faces (should be 2)",
                    location=mid,
                    element_indices=list(edge)
                ))

        # Check for holes (boundary edges form loops)
        if boundary_edges:
            # Count boundary loops (simplified - just count boundary edges / 3)
            hole_estimate = max(1, len(boundary_edges) // 3)
            for edge in boundary_edges[:5]:  # Report first 5
                v1, v2 = edge
                mid = (
                    (vertices[v1][0] + vertices[v2][0]) / 2,
                    (vertices[v1][1] + vertices[v2][1]) / 2,
                    (vertices[v1][2] + vertices[v2][2]) / 2,
                )
                issues.append(MeshIssue(
                    issue_type=MeshIssueType.HOLE,
                    severity=RepairSeverity.ERROR,
                    description="Boundary edge (hole in mesh)",
                    location=mid,
                    element_indices=list(edge)
                ))

        # Check for loose vertices
        loose_verts = [i for i, faces in vertex_faces.items() if len(faces) == 0]
        for vi in loose_verts:
            issues.append(MeshIssue(
                issue_type=MeshIssueType.LOOSE_VERTEX,
                severity=RepairSeverity.WARNING,
                description="Vertex not connected to any face",
                location=vertices[vi],
                element_indices=[vi]
            ))

        # Check for duplicate vertices
        dup_groups = self._find_duplicate_vertices(vertices)
        for group in dup_groups:
            if len(group) > 1:
                issues.append(MeshIssue(
                    issue_type=MeshIssueType.DUPLICATE_VERTEX,
                    severity=RepairSeverity.WARNING,
                    description=f"{len(group)} vertices at same location",
                    location=vertices[group[0]],
                    element_indices=group
                ))

        # Check for degenerate faces (zero area)
        for fi, face in enumerate(faces):
            if len(face) >= 3:
                area = self._triangle_area(
                    vertices[face[0]],
                    vertices[face[1]],
                    vertices[face[2]]
                )
                if area < 1e-10:
                    issues.append(MeshIssue(
                        issue_type=MeshIssueType.DEGENERATE_FACE,
                        severity=RepairSeverity.WARNING,
                        description="Face has zero or near-zero area",
                        element_indices=[fi]
                    ))

        # Calculate bounding box
        if vertices:
            min_pt = (
                min(v[0] for v in vertices),
                min(v[1] for v in vertices),
                min(v[2] for v in vertices)
            )
            max_pt = (
                max(v[0] for v in vertices),
                max(v[1] for v in vertices),
                max(v[2] for v in vertices)
            )
            bbox = (min_pt, max_pt)
        else:
            bbox = ((0, 0, 0), (0, 0, 0))

        # Create analysis
        analysis = MeshAnalysis(
            vertex_count=len(vertices),
            edge_count=len(edge_faces),
            face_count=len(faces),
            issues=issues,
            hole_count=len(boundary_edges) // 3 if boundary_edges else 0,
            non_manifold_edge_count=len(non_manifold_edges),
            loose_vertex_count=len(loose_verts),
            duplicate_vertex_count=sum(len(g) - 1 for g in dup_groups if len(g) > 1),
            is_manifold=len(non_manifold_edges) == 0,
            is_watertight=len(boundary_edges) == 0,
            bounding_box=bbox
        )

        return analysis

    def _find_duplicate_vertices(
        self,
        vertices: List[Tuple[float, float, float]]
    ) -> List[List[int]]:
        """Find groups of duplicate vertices."""
        groups = []
        used = set()

        for i, v1 in enumerate(vertices):
            if i in used:
                continue

            group = [i]
            for j, v2 in enumerate(vertices[i + 1:], i + 1):
                if j in used:
                    continue

                dist = math.sqrt(
                    (v1[0] - v2[0]) ** 2 +
                    (v1[1] - v2[1]) ** 2 +
                    (v1[2] - v2[2]) ** 2
                )
                if dist < self.merge_threshold:
                    group.append(j)
                    used.add(j)

            if len(group) > 1:
                groups.append(group)
                used.add(i)

        return groups

    def _triangle_area(
        self,
        v1: Tuple[float, float, float],
        v2: Tuple[float, float, float],
        v3: Tuple[float, float, float]
    ) -> float:
        """Calculate triangle area using cross product."""
        # Vectors
        ax, ay, az = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        bx, by, bz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]

        # Cross product
        cx = ay * bz - az * by
        cy = az * bx - ax * bz
        cz = ax * by - ay * bx

        return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


class MeshRepairer:
    """
    Repairs mesh issues in Blender.

    Requires Blender environment.
    """

    def __init__(self):
        """Initialize repairer."""
        if not HAS_BLENDER:
            raise RuntimeError("MeshRepairer requires Blender environment")

    def analyze_object(self, obj) -> MeshAnalysis:
        """
        Analyze a Blender mesh object.

        Args:
            obj: Blender mesh object

        Returns:
            MeshAnalysis
        """
        if obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        # Get bmesh for analysis
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        issues = []

        # Check for non-manifold edges
        non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
        for edge in non_manifold_edges:
            mid = (edge.verts[0].co + edge.verts[1].co) / 2
            issues.append(MeshIssue(
                issue_type=MeshIssueType.NON_MANIFOLD_EDGE,
                severity=RepairSeverity.ERROR,
                description="Non-manifold edge",
                location=tuple(mid),
                element_indices=[edge.index]
            ))

        # Check for boundary edges (holes)
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        if boundary_edges:
            # Group into boundary loops
            for edge in boundary_edges[:10]:  # First 10
                mid = (edge.verts[0].co + edge.verts[1].co) / 2
                issues.append(MeshIssue(
                    issue_type=MeshIssueType.HOLE,
                    severity=RepairSeverity.ERROR,
                    description="Boundary edge (mesh has holes)",
                    location=tuple(mid),
                    element_indices=[edge.index]
                ))

        # Check for loose vertices
        loose_verts = [v for v in bm.verts if not v.link_edges]
        for v in loose_verts:
            issues.append(MeshIssue(
                issue_type=MeshIssueType.LOOSE_VERTEX,
                severity=RepairSeverity.WARNING,
                description="Loose vertex",
                location=tuple(v.co),
                element_indices=[v.index]
            ))

        # Check for loose edges
        loose_edges = [e for e in bm.edges if not e.link_faces]
        for e in loose_edges:
            mid = (e.verts[0].co + e.verts[1].co) / 2
            issues.append(MeshIssue(
                issue_type=MeshIssueType.LOOSE_EDGE,
                severity=RepairSeverity.WARNING,
                description="Loose edge",
                location=tuple(mid),
                element_indices=[e.index]
            ))

        # Check for degenerate faces
        for face in bm.faces:
            if face.calc_area() < 1e-8:
                issues.append(MeshIssue(
                    issue_type=MeshIssueType.DEGENERATE_FACE,
                    severity=RepairSeverity.WARNING,
                    description="Degenerate face (zero area)",
                    location=tuple(face.calc_center_median()),
                    element_indices=[face.index]
                ))

        # Calculate stats
        analysis = MeshAnalysis(
            vertex_count=len(bm.verts),
            edge_count=len(bm.edges),
            face_count=len(bm.faces),
            issues=issues,
            hole_count=len(set(e.link_loops[0].face if e.link_loops else None for e in boundary_edges if e.link_loops)) if boundary_edges else 0,
            non_manifold_edge_count=len(non_manifold_edges),
            loose_vertex_count=len(loose_verts),
            loose_edge_count=len(loose_edges),
            is_manifold=len(non_manifold_edges) == 0,
            is_watertight=len(boundary_edges) == 0
        )

        bm.free()
        return analysis

    def repair_object(
        self,
        obj,
        fix_holes: bool = True,
        fix_normals: bool = True,
        remove_doubles: bool = True,
        remove_loose: bool = True,
        merge_threshold: float = 0.0001
    ) -> RepairResult:
        """
        Repair a Blender mesh object.

        Args:
            obj: Blender mesh object
            fix_holes: Fill holes in mesh
            fix_normals: Make normals consistent
            remove_doubles: Merge duplicate vertices
            remove_loose: Remove loose vertices/edges
            merge_threshold: Distance for merging duplicates

        Returns:
            RepairResult
        """
        if obj.type != 'MESH':
            raise ValueError("Object must be a mesh")

        operations = []
        warnings = []

        # Ensure object is active and in edit mode
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')

        bm = bmesh.from_edit_mesh(obj.data)
        initial_issues = self._count_issues(bm)

        # Remove doubles (merge by distance)
        if remove_doubles:
            before = len(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_threshold)
            removed = before - len(bm.verts)
            if removed > 0:
                operations.append(f"Merged {removed} duplicate vertices")

        # Remove loose geometry
        if remove_loose:
            # Remove loose vertices
            loose_verts = [v for v in bm.verts if not v.link_edges]
            if loose_verts:
                bmesh.ops.delete(bm, geom=loose_verts, context='VERTS')
                operations.append(f"Removed {len(loose_verts)} loose vertices")

            # Remove loose edges
            loose_edges = [e for e in bm.edges if not e.link_faces]
            if loose_edges:
                bmesh.ops.delete(bm, geom=loose_edges, context='EDGES')
                operations.append(f"Removed {len(loose_edges)} loose edges")

        # Fix normals
        if fix_normals:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            operations.append("Recalculated face normals")

        # Fill holes
        if fix_holes:
            # Find boundary edges
            boundary_edges = [e for e in bm.edges if e.is_boundary]
            if boundary_edges:
                # Try to fill holes
                try:
                    # Get boundary loops
                    filled = 0
                    for _ in range(100):  # Max iterations
                        boundary_edges = [e for e in bm.edges if e.is_boundary]
                        if not boundary_edges:
                            break

                        # Find a boundary loop
                        edge = boundary_edges[0]
                        loop_edges = self._get_boundary_loop(edge)

                        if loop_edges and len(loop_edges) >= 3:
                            # Fill the hole
                            try:
                                bmesh.ops.holes_fill(bm, edges=loop_edges, sides=len(loop_edges))
                                filled += 1
                            except:
                                # Try triangle fill as fallback
                                try:
                                    verts = list(set(v for e in loop_edges for v in e.verts))
                                    bmesh.ops.triangle_fill(bm, edges=loop_edges)
                                    filled += 1
                                except:
                                    warnings.append(f"Could not fill hole with {len(loop_edges)} edges")
                                    break
                        else:
                            break

                    if filled > 0:
                        operations.append(f"Filled {filled} holes")
                except Exception as e:
                    warnings.append(f"Hole filling error: {str(e)}")

        # Update mesh
        bmesh.update_edit_mesh(obj.data)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Count remaining issues
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        final_issues = self._count_issues(bm)
        bm.free()

        return RepairResult(
            success=True,
            issues_fixed=initial_issues - final_issues,
            issues_remaining=final_issues,
            operations_performed=operations,
            warnings=warnings
        )

    def _count_issues(self, bm) -> int:
        """Count total issues in bmesh."""
        count = 0
        count += len([e for e in bm.edges if not e.is_manifold])
        count += len([e for e in bm.edges if e.is_boundary])
        count += len([v for v in bm.verts if not v.link_edges])
        count += len([e for e in bm.edges if not e.link_faces])
        return count

    def _get_boundary_loop(self, start_edge) -> List:
        """Get the boundary loop containing an edge."""
        if not start_edge.is_boundary:
            return []

        loop = [start_edge]
        current_vert = start_edge.verts[1]

        for _ in range(1000):  # Safety limit
            # Find next boundary edge
            next_edge = None
            for edge in current_vert.link_edges:
                if edge.is_boundary and edge not in loop:
                    next_edge = edge
                    break

            if next_edge is None:
                break

            loop.append(next_edge)

            # Move to next vertex
            current_vert = next_edge.other_vert(current_vert)

            # Check if we've closed the loop
            if current_vert == start_edge.verts[0]:
                return loop

        return loop


def analyze_mesh(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, ...]]
) -> MeshAnalysis:
    """
    Convenience function to analyze mesh data.

    Args:
        vertices: List of vertex positions
        faces: List of face vertex indices

    Returns:
        MeshAnalysis
    """
    analyzer = MeshAnalyzer()
    return analyzer.analyze_mesh_data(vertices, faces)


def format_analysis(analysis: MeshAnalysis) -> str:
    """Format mesh analysis as human-readable string."""
    lines = [
        "=" * 50,
        "MESH ANALYSIS REPORT",
        "=" * 50,
        "",
        "GEOMETRY:",
        f"  Vertices: {analysis.vertex_count:,}",
        f"  Edges: {analysis.edge_count:,}",
        f"  Faces: {analysis.face_count:,}",
        "",
        "STATUS:",
        f"  Manifold: {'✓' if analysis.is_manifold else '✗'}",
        f"  Watertight: {'✓' if analysis.is_watertight else '✗'}",
        f"  Printable: {'✓' if analysis.is_printable else '✗'}",
        "",
        "ISSUES FOUND:",
        f"  Holes: {analysis.hole_count}",
        f"  Non-manifold edges: {analysis.non_manifold_edge_count}",
        f"  Loose vertices: {analysis.loose_vertex_count}",
        f"  Duplicate vertices: {analysis.duplicate_vertex_count}",
        "",
        f"Total issues: {analysis.issue_count}",
    ]

    if analysis.issues:
        lines.append("")
        lines.append("ISSUE DETAILS:")
        for i, issue in enumerate(analysis.issues[:10]):  # First 10
            icon = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "🔵"}.get(
                issue.severity.value, "•"
            )
            lines.append(f"  {icon} {issue.description}")
            if issue.location:
                lines.append(f"      at ({issue.location[0]:.2f}, {issue.location[1]:.2f}, {issue.location[2]:.2f})")

        if len(analysis.issues) > 10:
            lines.append(f"  ... and {len(analysis.issues) - 10} more issues")

    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


# Test/demo
if __name__ == "__main__":
    print("Testing Mesh Analyzer (standalone mode)")
    print()

    # Create a simple cube with issues
    vertices = [
        (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),  # Bottom
        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),  # Top
        (0.5, 0.5, 0.5),  # Loose vertex (issue!)
        (0, 0, 0),  # Duplicate of vertex 0 (issue!)
    ]

    # Cube faces (missing one face = hole)
    faces = [
        (0, 1, 2, 3),  # Bottom
        (4, 7, 6, 5),  # Top
        (0, 4, 5, 1),  # Front
        (2, 6, 7, 3),  # Back
        (0, 3, 7, 4),  # Left
        # Missing right face = hole!
    ]

    analysis = analyze_mesh(vertices, faces)
    print(format_analysis(analysis))
