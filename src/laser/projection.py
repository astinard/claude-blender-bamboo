"""
2D Projection Tool for Laser Cutting.

Projects 3D models onto 2D planes (top, front, side views)
to generate outline paths for laser cutting.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set
from pathlib import Path
import math

# Try to import Blender modules
try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False

from .cross_section import Path2D


@dataclass
class ProjectionResult:
    """Result of a 2D projection operation."""
    paths: List[Path2D]
    view: str  # 'top', 'front', 'side', 'iso'
    bounding_box: Tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    unit: str = "mm"

    @property
    def width(self) -> float:
        return self.bounding_box[2] - self.bounding_box[0]

    @property
    def height(self) -> float:
        return self.bounding_box[3] - self.bounding_box[1]


class ProjectionTool:
    """
    Tool for projecting 3D objects to 2D outlines.

    Supports:
    - Top view (XY plane, looking down Z)
    - Front view (XZ plane, looking along Y)
    - Side view (YZ plane, looking along X)
    - Isometric projection

    Usage:
        tool = ProjectionTool()
        result = tool.project(obj, view='top')
        # result.paths contains outline paths
    """

    def __init__(self, simplify_tolerance: float = 0.1):
        """
        Initialize projection tool.

        Args:
            simplify_tolerance: Tolerance for path simplification
        """
        self.simplify_tolerance = simplify_tolerance

    def project(self, obj, view: str = 'top') -> ProjectionResult:
        """
        Project object to 2D outline.

        Args:
            obj: Blender mesh object
            view: View direction ('top', 'front', 'side', 'iso')

        Returns:
            ProjectionResult with outline paths
        """
        if not HAS_BLENDER:
            raise RuntimeError("This function requires Blender")

        mesh = obj.data
        world_matrix = obj.matrix_world

        # Define projection based on view
        if view == 'top':
            project = lambda v: (v.x, v.y)
        elif view == 'front':
            project = lambda v: (v.x, v.z)
        elif view == 'side':
            project = lambda v: (v.y, v.z)
        elif view == 'iso':
            # Isometric projection (30 degree angles)
            angle = math.radians(30)
            project = lambda v: (
                v.x * math.cos(angle) - v.y * math.cos(angle),
                v.z + v.x * math.sin(angle) + v.y * math.sin(angle)
            )
        else:
            raise ValueError(f"Unknown view: {view}")

        # Project all vertices
        projected_verts = []
        for v in mesh.vertices:
            world_co = world_matrix @ v.co
            projected_verts.append(project(world_co))

        # Project all edges to build outline
        edge_segments = []
        for edge in mesh.edges:
            p0 = projected_verts[edge.vertices[0]]
            p1 = projected_verts[edge.vertices[1]]
            edge_segments.append((p0, p1))

        # Build outline paths from edges
        # Using convex hull as simplified outline
        all_points = list(set(projected_verts))
        hull_points = self._convex_hull(all_points)

        paths = []
        if hull_points:
            paths.append(Path2D(points=hull_points, is_closed=True, is_outer=True))

        # Calculate bounding box
        if all_points:
            min_x = min(p[0] for p in all_points)
            min_y = min(p[1] for p in all_points)
            max_x = max(p[0] for p in all_points)
            max_y = max(p[1] for p in all_points)
            bbox = (min_x, min_y, max_x, max_y)
        else:
            bbox = (0, 0, 0, 0)

        return ProjectionResult(
            paths=paths,
            view=view,
            bounding_box=bbox
        )

    def project_silhouette(self, obj, view: str = 'top') -> ProjectionResult:
        """
        Project object silhouette (true outline, not just vertices).

        This traces the actual visible outline from the given view direction.
        """
        if not HAS_BLENDER:
            raise RuntimeError("This function requires Blender")

        # For true silhouette, we need to find edges where face normals
        # point in opposite directions relative to view

        mesh = obj.data
        world_matrix = obj.matrix_world

        # Define view direction
        if view == 'top':
            view_dir = Vector((0, 0, -1))
            project = lambda v: (v.x, v.y)
        elif view == 'front':
            view_dir = Vector((0, 1, 0))
            project = lambda v: (v.x, v.z)
        elif view == 'side':
            view_dir = Vector((1, 0, 0))
            project = lambda v: (v.y, v.z)
        else:
            view_dir = Vector((0, 0, -1))
            project = lambda v: (v.x, v.y)

        # Create bmesh for topology access
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        silhouette_edges = []

        for edge in bm.edges:
            if len(edge.link_faces) == 2:
                # Interior edge - check if silhouette edge
                f1, f2 = edge.link_faces
                n1 = (world_matrix.to_3x3() @ f1.normal).normalized()
                n2 = (world_matrix.to_3x3() @ f2.normal).normalized()

                d1 = n1.dot(view_dir)
                d2 = n2.dot(view_dir)

                # Silhouette edge: one face visible, one not
                if d1 * d2 < 0:
                    v0 = world_matrix @ edge.verts[0].co
                    v1 = world_matrix @ edge.verts[1].co
                    silhouette_edges.append((project(v0), project(v1)))
            elif len(edge.link_faces) == 1:
                # Boundary edge - always include
                v0 = world_matrix @ edge.verts[0].co
                v1 = world_matrix @ edge.verts[1].co
                silhouette_edges.append((project(v0), project(v1)))

        bm.free()

        # Connect edges into paths
        paths = self._connect_edges_to_paths(silhouette_edges)

        # Calculate bounding box
        all_points = [p for seg in silhouette_edges for p in seg]
        if all_points:
            min_x = min(p[0] for p in all_points)
            min_y = min(p[1] for p in all_points)
            max_x = max(p[0] for p in all_points)
            max_y = max(p[1] for p in all_points)
            bbox = (min_x, min_y, max_x, max_y)
        else:
            bbox = (0, 0, 0, 0)

        return ProjectionResult(
            paths=paths,
            view=view,
            bounding_box=bbox
        )

    def _convex_hull(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Compute convex hull of 2D points."""
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        points = sorted(set(points))
        if len(points) <= 1:
            return points

        lower = []
        for p in points:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper = []
        for p in reversed(points):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        return lower[:-1] + upper[:-1]

    def _connect_edges_to_paths(self, edges: List[Tuple[Tuple[float, float], Tuple[float, float]]]) -> List[Path2D]:
        """Connect edge segments into continuous paths."""
        if not edges:
            return []

        # Build adjacency
        point_edges = {}
        for i, (p0, p1) in enumerate(edges):
            k0 = self._point_key(p0)
            k1 = self._point_key(p1)

            if k0 not in point_edges:
                point_edges[k0] = []
            if k1 not in point_edges:
                point_edges[k1] = []

            point_edges[k0].append((i, p1))
            point_edges[k1].append((i, p0))

        # Trace paths
        used = set()
        paths = []

        for start_idx, (p0, p1) in enumerate(edges):
            if start_idx in used:
                continue

            path_points = [p0, p1]
            used.add(start_idx)

            # Extend forward
            current = p1
            while True:
                key = self._point_key(current)
                if key not in point_edges:
                    break

                next_edge = None
                for edge_idx, next_point in point_edges[key]:
                    if edge_idx not in used:
                        next_edge = (edge_idx, next_point)
                        break

                if next_edge is None:
                    break

                used.add(next_edge[0])
                path_points.append(next_edge[1])
                current = next_edge[1]

                # Check if closed
                if self._points_close(current, p0):
                    break

            is_closed = self._points_close(path_points[-1], path_points[0])
            paths.append(Path2D(points=path_points, is_closed=is_closed))

        return paths

    def _point_key(self, p: Tuple[float, float], precision: int = 4) -> Tuple[int, int]:
        """Create hashable key for point."""
        return (round(p[0] * 10**precision), round(p[1] * 10**precision))

    def _points_close(self, p0: Tuple[float, float], p1: Tuple[float, float]) -> bool:
        """Check if two points are close."""
        return abs(p0[0] - p1[0]) < self.simplify_tolerance and abs(p0[1] - p1[1]) < self.simplify_tolerance


def project_to_2d(obj, view: str = 'top') -> ProjectionResult:
    """
    Convenience function to project object to 2D.

    Args:
        obj: Blender mesh object
        view: View direction ('top', 'front', 'side')

    Returns:
        ProjectionResult
    """
    tool = ProjectionTool()
    return tool.project(obj, view)


def project_outline(obj, view: str = 'top') -> ProjectionResult:
    """
    Convenience function to get object silhouette/outline.

    Args:
        obj: Blender mesh object
        view: View direction

    Returns:
        ProjectionResult with silhouette paths
    """
    tool = ProjectionTool()
    return tool.project_silhouette(obj, view)


# Test function without Blender
def _test_projection():
    """Test projection with dummy data."""
    # Simulate a simple box projection
    box_verts = [
        (-25, -15, 0), (25, -15, 0), (25, 15, 0), (-25, 15, 0),  # Bottom
        (-25, -15, 20), (25, -15, 20), (25, 15, 20), (-25, 15, 20),  # Top
    ]

    # Top view projection (XY)
    top_points = [(v[0], v[1]) for v in box_verts]
    hull = ProjectionTool()._convex_hull(top_points)

    print("Test projection (50x30x20 box):")
    print(f"Top view hull: {hull}")

    # Front view projection (XZ)
    front_points = [(v[0], v[2]) for v in box_verts]
    hull_front = ProjectionTool()._convex_hull(front_points)
    print(f"Front view hull: {hull_front}")


if __name__ == "__main__":
    _test_projection()
