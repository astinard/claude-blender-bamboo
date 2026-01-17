"""
Cross-Section Tool for Laser Cutting.

Creates 2D cross-sections from 3D models at specified heights or planes.
Used to generate laser cutting paths from 3D objects.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
import math

# Try to import Blender modules
try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
    from mathutils.geometry import intersect_line_plane
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False


@dataclass
class Path2D:
    """A 2D path (polyline or polygon)."""
    points: List[Tuple[float, float]]
    is_closed: bool = True
    is_outer: bool = True  # True for outer contour, False for hole


@dataclass
class CrossSectionResult:
    """Result of a cross-section operation."""
    paths: List[Path2D]
    height: float
    unit: str = "mm"
    bounding_box: Tuple[float, float, float, float] = (0, 0, 0, 0)  # min_x, min_y, max_x, max_y

    @property
    def width(self) -> float:
        return self.bounding_box[2] - self.bounding_box[0]

    @property
    def depth(self) -> float:
        return self.bounding_box[3] - self.bounding_box[1]


class CrossSectionTool:
    """
    Tool for creating cross-sections of 3D objects.

    Usage:
        tool = CrossSectionTool()
        result = tool.section_at_height(obj, height=10.0)
        for path in result.paths:
            print(f"Path with {len(path.points)} points")
    """

    def __init__(self, tolerance: float = 0.001):
        """
        Initialize cross-section tool.

        Args:
            tolerance: Distance tolerance for point merging
        """
        self.tolerance = tolerance

    def section_at_height(self, obj, height: float, axis: str = 'Z') -> CrossSectionResult:
        """
        Create cross-section at specified height.

        Args:
            obj: Blender mesh object
            height: Height along axis for the cutting plane
            axis: Axis perpendicular to cutting plane ('X', 'Y', 'Z')

        Returns:
            CrossSectionResult with paths
        """
        if not HAS_BLENDER:
            raise RuntimeError("This function requires Blender")

        mesh = obj.data
        world_matrix = obj.matrix_world

        # Define cutting plane
        axis = axis.upper()
        if axis == 'X':
            plane_normal = Vector((1, 0, 0))
            plane_point = Vector((height, 0, 0))
            project = lambda v: (v.y, v.z)
        elif axis == 'Y':
            plane_normal = Vector((0, 1, 0))
            plane_point = Vector((0, height, 0))
            project = lambda v: (v.x, v.z)
        else:  # Z
            plane_normal = Vector((0, 0, 1))
            plane_point = Vector((0, 0, height))
            project = lambda v: (v.x, v.y)

        # Find intersection points with each edge
        edge_intersections = []

        for edge in mesh.edges:
            v0 = world_matrix @ mesh.vertices[edge.vertices[0]].co
            v1 = world_matrix @ mesh.vertices[edge.vertices[1]].co

            intersection = intersect_line_plane(v0, v1, plane_point, plane_normal)

            if intersection is not None:
                # Check if intersection is within edge bounds
                edge_vec = v1 - v0
                if edge_vec.length > 0:
                    t = (intersection - v0).dot(edge_vec) / edge_vec.dot(edge_vec)
                    if -self.tolerance <= t <= 1 + self.tolerance:
                        # Project to 2D
                        point_2d = project(intersection)
                        edge_intersections.append({
                            'point': point_2d,
                            'edge_key': tuple(sorted(edge.vertices)),
                            'intersection_3d': intersection,
                        })

        # Build paths from intersections
        paths = self._build_paths_from_intersections(edge_intersections, mesh, world_matrix, project)

        # Calculate bounding box
        all_points = [p for path in paths for p in path.points]
        if all_points:
            min_x = min(p[0] for p in all_points)
            min_y = min(p[1] for p in all_points)
            max_x = max(p[0] for p in all_points)
            max_y = max(p[1] for p in all_points)
            bbox = (min_x, min_y, max_x, max_y)
        else:
            bbox = (0, 0, 0, 0)

        return CrossSectionResult(
            paths=paths,
            height=height,
            bounding_box=bbox
        )

    def _build_paths_from_intersections(self, intersections: List[Dict],
                                        mesh, world_matrix, project) -> List[Path2D]:
        """Build connected paths from intersection points."""
        if not intersections:
            return []

        # For proper path building, we need to trace through faces
        # This is a simplified version that groups nearby points

        # Deduplicate points
        unique_points = []
        for inter in intersections:
            point = inter['point']
            is_dup = False
            for up in unique_points:
                if abs(up[0] - point[0]) < self.tolerance and abs(up[1] - point[1]) < self.tolerance:
                    is_dup = True
                    break
            if not is_dup:
                unique_points.append(point)

        if len(unique_points) < 3:
            return []

        # Simple convex hull approach for now
        # (A full implementation would trace through mesh topology)
        paths = [self._convex_hull_path(unique_points)]

        return paths

    def _convex_hull_path(self, points: List[Tuple[float, float]]) -> Path2D:
        """Create convex hull path from points (simplified)."""
        # Graham scan algorithm for convex hull
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        points = sorted(set(points))
        if len(points) <= 1:
            return Path2D(points=points, is_closed=True)

        # Build lower hull
        lower = []
        for p in points:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        # Build upper hull
        upper = []
        for p in reversed(points):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        hull = lower[:-1] + upper[:-1]
        return Path2D(points=hull, is_closed=True, is_outer=True)

    def section_multiple(self, obj, start_height: float, end_height: float,
                        num_sections: int, axis: str = 'Z') -> List[CrossSectionResult]:
        """
        Create multiple cross-sections at regular intervals.

        Args:
            obj: Blender mesh object
            start_height: Starting height
            end_height: Ending height
            num_sections: Number of sections to create
            axis: Cutting axis

        Returns:
            List of CrossSectionResult
        """
        results = []
        step = (end_height - start_height) / max(num_sections - 1, 1)

        for i in range(num_sections):
            height = start_height + i * step
            result = self.section_at_height(obj, height, axis)
            results.append(result)

        return results


def create_cross_section(obj, height: float, axis: str = 'Z') -> CrossSectionResult:
    """
    Convenience function to create a single cross-section.

    Args:
        obj: Blender mesh object
        height: Height for cutting plane
        axis: Axis perpendicular to plane

    Returns:
        CrossSectionResult
    """
    tool = CrossSectionTool()
    return tool.section_at_height(obj, height, axis)


def create_multiple_sections(obj, start: float, end: float,
                            count: int, axis: str = 'Z') -> List[CrossSectionResult]:
    """
    Convenience function to create multiple cross-sections.

    Args:
        obj: Blender mesh object
        start: Start height
        end: End height
        count: Number of sections
        axis: Cutting axis

    Returns:
        List of CrossSectionResult
    """
    tool = CrossSectionTool()
    return tool.section_multiple(obj, start, end, count, axis)


# Non-Blender implementation for testing
def _simple_box_section(width: float, depth: float, height: float,
                       section_height: float) -> CrossSectionResult:
    """Create cross-section of a simple box (for testing without Blender)."""
    half_w = width / 2
    half_d = depth / 2

    if 0 <= section_height <= height:
        # Section through the box
        points = [
            (-half_w, -half_d),
            (half_w, -half_d),
            (half_w, half_d),
            (-half_w, half_d),
        ]
        paths = [Path2D(points=points, is_closed=True)]
    else:
        paths = []

    return CrossSectionResult(
        paths=paths,
        height=section_height,
        bounding_box=(-half_w, -half_d, half_w, half_d) if paths else (0, 0, 0, 0)
    )


if __name__ == "__main__":
    # Test without Blender
    print("Cross-section test (box 50x30x20):")
    result = _simple_box_section(50, 30, 20, section_height=10)
    print(f"Height: {result.height}mm")
    print(f"Paths: {len(result.paths)}")
    print(f"Bounding box: {result.bounding_box}")
    if result.paths:
        print(f"First path points: {result.paths[0].points}")
