"""
Path Optimizer for Laser Cutting.

Optimizes laser cutting paths to minimize:
- Total travel distance (non-cutting moves)
- Cut time
- Material damage from repeated passes

Optimization strategies:
1. Path ordering (TSP-like nearest neighbor)
2. Path direction optimization (start/end points)
3. Nested path ordering (inner before outer)
4. Path simplification (point reduction)
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Set
import math
from copy import deepcopy

from .cross_section import Path2D


@dataclass
class OptimizationStats:
    """Statistics from path optimization."""
    original_travel_distance: float  # mm
    optimized_travel_distance: float  # mm
    travel_reduction_percent: float
    original_path_count: int
    optimized_path_count: int
    points_removed: int = 0


@dataclass
class OptimizedPathSet:
    """Result of path optimization."""
    paths: List[Path2D]
    stats: OptimizationStats
    warnings: List[str] = field(default_factory=list)


class PathOptimizer:
    """
    Optimizes laser cutting paths for efficiency.

    Usage:
        optimizer = PathOptimizer()

        # Optimize paths
        result = optimizer.optimize(paths)

        # Access optimized paths
        for path in result.paths:
            process(path)

        # Check improvement
        print(f"Travel reduced by {result.stats.travel_reduction_percent:.1f}%")
    """

    def __init__(
        self,
        origin: Tuple[float, float] = (0, 0),
        inner_first: bool = True,
        simplify_tolerance: float = 0.0
    ):
        """
        Initialize path optimizer.

        Args:
            origin: Laser starting position (x, y)
            inner_first: Cut inner/nested paths before outer paths
            simplify_tolerance: Point simplification tolerance (0 = no simplification)
        """
        self.origin = origin
        self.inner_first = inner_first
        self.simplify_tolerance = simplify_tolerance

    def optimize(self, paths: List[Path2D]) -> OptimizedPathSet:
        """
        Optimize a set of paths.

        Args:
            paths: List of Path2D objects

        Returns:
            OptimizedPathSet with optimized paths and statistics
        """
        if not paths:
            return OptimizedPathSet(
                paths=[],
                stats=OptimizationStats(
                    original_travel_distance=0,
                    optimized_travel_distance=0,
                    travel_reduction_percent=0,
                    original_path_count=0,
                    optimized_path_count=0
                )
            )

        # Calculate original travel distance
        original_travel = self._calculate_travel_distance(paths, self.origin)
        original_count = len(paths)

        # Make copies to avoid modifying originals
        working_paths = [deepcopy(p) for p in paths]

        # Step 1: Simplify paths if tolerance set
        points_removed = 0
        if self.simplify_tolerance > 0:
            working_paths, points_removed = self._simplify_paths(
                working_paths,
                self.simplify_tolerance
            )

        # Step 2: Handle nested paths (inner before outer)
        if self.inner_first:
            working_paths = self._order_nested_paths(working_paths)

        # Step 3: Optimize path order (nearest neighbor TSP)
        working_paths = self._optimize_order(working_paths)

        # Step 4: Optimize path directions
        working_paths = self._optimize_directions(working_paths)

        # Calculate optimized travel distance
        optimized_travel = self._calculate_travel_distance(working_paths, self.origin)

        # Calculate improvement
        if original_travel > 0:
            reduction = (1 - optimized_travel / original_travel) * 100
        else:
            reduction = 0

        stats = OptimizationStats(
            original_travel_distance=original_travel,
            optimized_travel_distance=optimized_travel,
            travel_reduction_percent=reduction,
            original_path_count=original_count,
            optimized_path_count=len(working_paths),
            points_removed=points_removed
        )

        warnings = []
        if reduction < 0:
            warnings.append("Optimization increased travel distance (unusual geometry)")

        return OptimizedPathSet(
            paths=working_paths,
            stats=stats,
            warnings=warnings
        )

    def _calculate_travel_distance(
        self,
        paths: List[Path2D],
        start: Tuple[float, float]
    ) -> float:
        """Calculate total non-cutting travel distance."""
        total = 0.0
        current_pos = start

        for path in paths:
            if not path.points:
                continue

            # Travel to path start
            path_start = path.points[0]
            total += self._distance(current_pos, path_start)

            # Update position to path end
            current_pos = path.points[-1] if not path.is_closed else path.points[0]

        return total

    def _distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

    def _simplify_paths(
        self,
        paths: List[Path2D],
        tolerance: float
    ) -> Tuple[List[Path2D], int]:
        """
        Simplify paths using Ramer-Douglas-Peucker algorithm.

        Returns:
            Tuple of (simplified paths, points removed)
        """
        total_removed = 0
        simplified = []

        for path in paths:
            original_count = len(path.points)
            new_points = self._rdp_simplify(path.points, tolerance)
            total_removed += original_count - len(new_points)

            simplified.append(Path2D(
                points=new_points,
                is_closed=path.is_closed,
                is_outer=path.is_outer
            ))

        return simplified, total_removed

    def _rdp_simplify(
        self,
        points: List[Tuple[float, float]],
        tolerance: float
    ) -> List[Tuple[float, float]]:
        """Ramer-Douglas-Peucker line simplification."""
        if len(points) <= 2:
            return points

        # Find point with maximum distance from line between first and last
        max_dist = 0
        max_idx = 0

        p1 = points[0]
        p2 = points[-1]

        for i in range(1, len(points) - 1):
            dist = self._point_to_line_distance(points[i], p1, p2)
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        # If max distance is greater than tolerance, recursively simplify
        if max_dist > tolerance:
            left = self._rdp_simplify(points[:max_idx + 1], tolerance)
            right = self._rdp_simplify(points[max_idx:], tolerance)
            return left[:-1] + right
        else:
            return [points[0], points[-1]]

    def _point_to_line_distance(
        self,
        point: Tuple[float, float],
        line_start: Tuple[float, float],
        line_end: Tuple[float, float]
    ) -> float:
        """Calculate perpendicular distance from point to line."""
        x0, y0 = point
        x1, y1 = line_start
        x2, y2 = line_end

        # Line length
        line_len = self._distance(line_start, line_end)
        if line_len == 0:
            return self._distance(point, line_start)

        # Calculate perpendicular distance using cross product
        return abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1) / line_len

    def _order_nested_paths(self, paths: List[Path2D]) -> List[Path2D]:
        """
        Order paths so inner (nested) paths come before outer paths.

        This prevents cutting the outer boundary before the inner details,
        which could cause the material to shift.
        """
        if len(paths) <= 1:
            return paths

        # Calculate bounding boxes
        bboxes = []
        for path in paths:
            if not path.points:
                bboxes.append((0, 0, 0, 0))
                continue

            xs = [p[0] for p in path.points]
            ys = [p[1] for p in path.points]
            bboxes.append((min(xs), min(ys), max(xs), max(ys)))

        # Determine nesting relationships
        # A path is "inside" another if its bbox is completely contained
        nesting_levels = [0] * len(paths)

        for i, bbox_i in enumerate(bboxes):
            for j, bbox_j in enumerate(bboxes):
                if i == j:
                    continue
                # Check if bbox_i is inside bbox_j
                if (bbox_i[0] >= bbox_j[0] and bbox_i[1] >= bbox_j[1] and
                    bbox_i[2] <= bbox_j[2] and bbox_i[3] <= bbox_j[3]):
                    nesting_levels[i] += 1

        # Sort by nesting level (higher level = more nested = cut first)
        indexed_paths = list(enumerate(paths))
        indexed_paths.sort(key=lambda x: -nesting_levels[x[0]])

        return [p for _, p in indexed_paths]

    def _optimize_order(self, paths: List[Path2D]) -> List[Path2D]:
        """
        Optimize path order using nearest neighbor heuristic.

        This is a greedy approximation to the Traveling Salesman Problem.
        """
        if len(paths) <= 1:
            return paths

        remaining = set(range(len(paths)))
        ordered = []
        current_pos = self.origin

        while remaining:
            # Find nearest path
            best_idx = None
            best_dist = float('inf')

            for idx in remaining:
                path = paths[idx]
                if not path.points:
                    continue

                # Check distance to path start
                dist_to_start = self._distance(current_pos, path.points[0])
                if dist_to_start < best_dist:
                    best_dist = dist_to_start
                    best_idx = idx

                # For closed paths, also check distance to any point
                # (we can start anywhere on a closed path)
                if path.is_closed:
                    for point in path.points:
                        dist = self._distance(current_pos, point)
                        if dist < best_dist:
                            best_dist = dist
                            best_idx = idx

            if best_idx is not None:
                remaining.remove(best_idx)
                ordered.append(paths[best_idx])

                # Update current position
                path = paths[best_idx]
                if path.is_closed:
                    current_pos = path.points[0]
                else:
                    current_pos = path.points[-1]
            else:
                # Handle empty paths
                for idx in list(remaining):
                    remaining.remove(idx)
                    ordered.append(paths[idx])

        return ordered

    def _optimize_directions(self, paths: List[Path2D]) -> List[Path2D]:
        """
        Optimize path directions to minimize travel.

        For open paths, may reverse the point order.
        For closed paths, may rotate the starting point.
        """
        if not paths:
            return paths

        optimized = []
        current_pos = self.origin

        for path in paths:
            if not path.points:
                optimized.append(path)
                continue

            if path.is_closed:
                # Find best starting point on closed path
                best_idx = 0
                best_dist = self._distance(current_pos, path.points[0])

                for i, point in enumerate(path.points):
                    dist = self._distance(current_pos, point)
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = i

                # Rotate points to start at best_idx
                new_points = path.points[best_idx:] + path.points[:best_idx]
                optimized.append(Path2D(
                    points=new_points,
                    is_closed=True,
                    is_outer=path.is_outer
                ))
                current_pos = new_points[0]

            else:
                # For open paths, check if reversing is better
                dist_forward = self._distance(current_pos, path.points[0])
                dist_reverse = self._distance(current_pos, path.points[-1])

                if dist_reverse < dist_forward:
                    # Reverse the path
                    new_points = list(reversed(path.points))
                    optimized.append(Path2D(
                        points=new_points,
                        is_closed=False,
                        is_outer=path.is_outer
                    ))
                    current_pos = new_points[-1]
                else:
                    optimized.append(path)
                    current_pos = path.points[-1]

        return optimized


def optimize_paths(
    paths: List[Path2D],
    origin: Tuple[float, float] = (0, 0),
    inner_first: bool = True,
    simplify_tolerance: float = 0.0
) -> OptimizedPathSet:
    """
    Convenience function to optimize laser paths.

    Args:
        paths: List of Path2D objects
        origin: Laser starting position
        inner_first: Cut inner paths before outer
        simplify_tolerance: Point simplification tolerance (0 = none)

    Returns:
        OptimizedPathSet with optimized paths and stats
    """
    optimizer = PathOptimizer(
        origin=origin,
        inner_first=inner_first,
        simplify_tolerance=simplify_tolerance
    )
    return optimizer.optimize(paths)


def format_optimization_stats(stats: OptimizationStats) -> str:
    """Format optimization statistics as human-readable string."""
    return (
        f"Path Optimization Results:\n"
        f"  Original travel: {stats.original_travel_distance:.1f}mm\n"
        f"  Optimized travel: {stats.optimized_travel_distance:.1f}mm\n"
        f"  Reduction: {stats.travel_reduction_percent:.1f}%\n"
        f"  Paths: {stats.original_path_count} → {stats.optimized_path_count}\n"
        f"  Points removed: {stats.points_removed}"
    )


# Test/demo
if __name__ == "__main__":
    # Create test paths (scattered around)
    test_paths = [
        # Outer rectangle
        Path2D(
            points=[(0, 0), (100, 0), (100, 80), (0, 80)],
            is_closed=True,
            is_outer=True
        ),
        # Inner rectangle (should cut first)
        Path2D(
            points=[(20, 20), (80, 20), (80, 60), (20, 60)],
            is_closed=True,
            is_outer=False
        ),
        # Small circle top-right (far from origin)
        Path2D(
            points=[(90, 70), (95, 75), (90, 80), (85, 75)],
            is_closed=True,
            is_outer=False
        ),
        # Line at bottom (open path)
        Path2D(
            points=[(10, 10), (90, 10)],
            is_closed=False,
            is_outer=False
        ),
    ]

    print("Original path order:")
    for i, p in enumerate(test_paths):
        print(f"  {i}: {p.points[0]} {'(closed)' if p.is_closed else '(open)'}")

    optimizer = PathOptimizer(origin=(0, 0), inner_first=True)
    result = optimizer.optimize(test_paths)

    print("\nOptimized path order:")
    for i, p in enumerate(result.paths):
        print(f"  {i}: {p.points[0]} {'(closed)' if p.is_closed else '(open)'}")

    print(f"\n{format_optimization_stats(result.stats)}")

    # Test with simplification
    print("\n" + "=" * 50)
    print("Testing with path simplification:")

    complex_path = Path2D(
        points=[(0, 0), (1, 0.1), (2, 0), (3, 0.1), (4, 0),
                (5, 0.1), (6, 0), (7, 0.1), (8, 0), (9, 0.1), (10, 0)],
        is_closed=False
    )

    optimizer2 = PathOptimizer(simplify_tolerance=0.5)
    result2 = optimizer2.optimize([complex_path])

    print(f"Original points: 11")
    print(f"Simplified points: {len(result2.paths[0].points)}")
    print(f"Points removed: {result2.stats.points_removed}")
