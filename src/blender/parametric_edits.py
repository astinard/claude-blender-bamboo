"""
Parametric Editing Module for Mesh Features.

Enables natural language edits like:
- "Make all holes 2mm bigger"
- "Enlarge circular features by 10%"
- "Shrink holes to 5mm diameter"
- "Offset all edges outward by 1mm"

Works with both 2D paths (laser cutting) and 3D meshes.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any, Union


class FeatureType(Enum):
    """Types of geometric features that can be detected and edited."""
    HOLE = "hole"  # Circular hole (inner contour)
    SLOT = "slot"  # Elongated hole
    RECTANGLE = "rectangle"  # Rectangular cutout
    POLYGON = "polygon"  # Regular polygon (hex, octagon)
    CIRCLE = "circle"  # Circular outer contour
    FILLET = "fillet"  # Rounded corner
    CHAMFER = "chamfer"  # Angled corner
    EDGE = "edge"  # Linear edge
    CONTOUR = "contour"  # Generic closed contour


class EditOperation(Enum):
    """Types of parametric edit operations."""
    RESIZE = "resize"  # Change size (absolute or relative)
    OFFSET = "offset"  # Move edges in/out
    SCALE = "scale"  # Scale by factor
    MOVE = "move"  # Translate position
    ROTATE = "rotate"  # Rotate feature
    DELETE = "delete"  # Remove feature
    DUPLICATE = "duplicate"  # Copy feature
    FILLET = "fillet"  # Add rounded corners
    CHAMFER = "chamfer"  # Add angled corners


@dataclass
class DetectedFeature:
    """A detected geometric feature."""
    feature_type: FeatureType
    center: Tuple[float, float]  # (x, y) center point
    size: float  # Primary size (diameter for circles, width for slots)
    secondary_size: Optional[float] = None  # Height for slots/rectangles
    rotation: float = 0.0  # Rotation angle in degrees
    vertices: List[Tuple[float, float]] = field(default_factory=list)
    path_index: int = -1  # Index in original path list
    is_inner: bool = True  # True if hole/cutout, False if outer contour
    confidence: float = 1.0  # Detection confidence (0-1)

    @property
    def area(self) -> float:
        """Calculate approximate area."""
        if self.feature_type == FeatureType.HOLE or self.feature_type == FeatureType.CIRCLE:
            return math.pi * (self.size / 2) ** 2
        elif self.feature_type == FeatureType.RECTANGLE:
            return self.size * (self.secondary_size or self.size)
        elif self.feature_type == FeatureType.SLOT:
            # Slot is rectangle + two semicircles
            width = self.size
            length = self.secondary_size or self.size
            return (length - width) * width + math.pi * (width / 2) ** 2
        else:
            # Use shoelace formula for polygons
            if len(self.vertices) < 3:
                return 0
            n = len(self.vertices)
            area = 0
            for i in range(n):
                j = (i + 1) % n
                area += self.vertices[i][0] * self.vertices[j][1]
                area -= self.vertices[j][0] * self.vertices[i][1]
            return abs(area) / 2

    @property
    def perimeter(self) -> float:
        """Calculate approximate perimeter."""
        if self.feature_type == FeatureType.HOLE or self.feature_type == FeatureType.CIRCLE:
            return math.pi * self.size
        elif self.feature_type == FeatureType.RECTANGLE:
            return 2 * (self.size + (self.secondary_size or self.size))
        elif self.feature_type == FeatureType.SLOT:
            width = self.size
            length = self.secondary_size or self.size
            return 2 * (length - width) + math.pi * width
        else:
            # Sum of edge lengths
            if len(self.vertices) < 2:
                return 0
            total = 0
            for i in range(len(self.vertices)):
                j = (i + 1) % len(self.vertices)
                dx = self.vertices[j][0] - self.vertices[i][0]
                dy = self.vertices[j][1] - self.vertices[i][1]
                total += math.sqrt(dx * dx + dy * dy)
            return total


@dataclass
class EditResult:
    """Result of a parametric edit operation."""
    success: bool
    message: str
    features_modified: int = 0
    original_features: List[DetectedFeature] = field(default_factory=list)
    modified_features: List[DetectedFeature] = field(default_factory=list)
    modified_paths: List[List[Tuple[float, float]]] = field(default_factory=list)


class FeatureDetector:
    """
    Detects geometric features in 2D paths.

    Features detected:
    - Circular holes (high circularity, inner contour)
    - Slots (elongated holes with rounded ends)
    - Rectangles (4 corners, parallel sides)
    - Regular polygons (equal sides and angles)
    """

    def __init__(
        self,
        circularity_threshold: float = 0.85,
        min_hole_diameter: float = 0.5,  # mm
        max_hole_diameter: float = 1000.0,  # mm
    ):
        self.circularity_threshold = circularity_threshold
        self.min_hole_diameter = min_hole_diameter
        self.max_hole_diameter = max_hole_diameter

    def detect_features(
        self,
        paths: List[List[Tuple[float, float]]],
        inner_flags: Optional[List[bool]] = None,
    ) -> List[DetectedFeature]:
        """
        Detect geometric features in a list of 2D paths.

        Args:
            paths: List of paths, each path is a list of (x, y) points
            inner_flags: Optional list of booleans indicating inner/outer contours

        Returns:
            List of detected features
        """
        features = []

        if inner_flags is None:
            inner_flags = [True] * len(paths)

        for i, (path, is_inner) in enumerate(zip(paths, inner_flags)):
            if len(path) < 3:
                continue

            feature = self._classify_path(path, is_inner, i)
            if feature:
                features.append(feature)

        return features

    def _classify_path(
        self,
        path: List[Tuple[float, float]],
        is_inner: bool,
        path_index: int,
    ) -> Optional[DetectedFeature]:
        """Classify a single path as a geometric feature."""
        # Calculate basic metrics
        center = self._calculate_center(path)
        bbox = self._calculate_bbox(path)
        area = self._calculate_area(path)
        perimeter = self._calculate_perimeter(path)

        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]

        # Skip if outside size bounds
        size = max(width, height)
        if size < self.min_hole_diameter or size > self.max_hole_diameter:
            return None

        # Calculate circularity: 4*pi*area / perimeter^2
        # Perfect circle = 1.0
        circularity = (4 * math.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0

        # Check for circle
        if circularity >= self.circularity_threshold:
            # Calculate diameter from area
            diameter = 2 * math.sqrt(area / math.pi)
            return DetectedFeature(
                feature_type=FeatureType.HOLE if is_inner else FeatureType.CIRCLE,
                center=center,
                size=diameter,
                vertices=list(path),
                path_index=path_index,
                is_inner=is_inner,
                confidence=circularity,
            )

        # Check for slot (elongated with rounded ends)
        aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 1
        if aspect_ratio > 1.5 and circularity > 0.6:
            # Likely a slot
            return DetectedFeature(
                feature_type=FeatureType.SLOT,
                center=center,
                size=min(width, height),  # Width
                secondary_size=max(width, height),  # Length
                rotation=0 if width < height else 90,
                vertices=list(path),
                path_index=path_index,
                is_inner=is_inner,
                confidence=0.8,
            )

        # Check for rectangle (4 corners, near 90 degrees)
        corners = self._detect_corners(path)
        if len(corners) == 4:
            angles = self._calculate_corner_angles(path, corners)
            if all(85 < abs(angle) < 95 for angle in angles):
                return DetectedFeature(
                    feature_type=FeatureType.RECTANGLE,
                    center=center,
                    size=width,
                    secondary_size=height,
                    vertices=list(path),
                    path_index=path_index,
                    is_inner=is_inner,
                    confidence=0.9,
                )

        # Check for regular polygon
        if len(corners) >= 3 and len(corners) <= 12:
            angles = self._calculate_corner_angles(path, corners)
            expected_angle = 180 - (360 / len(corners))
            if all(abs(abs(a) - expected_angle) < 10 for a in angles):
                return DetectedFeature(
                    feature_type=FeatureType.POLYGON,
                    center=center,
                    size=size,
                    vertices=list(path),
                    path_index=path_index,
                    is_inner=is_inner,
                    confidence=0.85,
                )

        # Default: generic contour
        return DetectedFeature(
            feature_type=FeatureType.CONTOUR,
            center=center,
            size=size,
            vertices=list(path),
            path_index=path_index,
            is_inner=is_inner,
            confidence=0.5,
        )

    def _calculate_center(self, path: List[Tuple[float, float]]) -> Tuple[float, float]:
        """Calculate centroid of path."""
        if not path:
            return (0, 0)
        x = sum(p[0] for p in path) / len(path)
        y = sum(p[1] for p in path) / len(path)
        return (x, y)

    def _calculate_bbox(
        self, path: List[Tuple[float, float]]
    ) -> Tuple[float, float, float, float]:
        """Calculate bounding box (min_x, min_y, max_x, max_y)."""
        if not path:
            return (0, 0, 0, 0)
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        return (min(xs), min(ys), max(xs), max(ys))

    def _calculate_area(self, path: List[Tuple[float, float]]) -> float:
        """Calculate area using shoelace formula."""
        if len(path) < 3:
            return 0
        n = len(path)
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += path[i][0] * path[j][1]
            area -= path[j][0] * path[i][1]
        return abs(area) / 2

    def _calculate_perimeter(self, path: List[Tuple[float, float]]) -> float:
        """Calculate perimeter of path."""
        if len(path) < 2:
            return 0
        total = 0
        for i in range(len(path)):
            j = (i + 1) % len(path)
            dx = path[j][0] - path[i][0]
            dy = path[j][1] - path[i][1]
            total += math.sqrt(dx * dx + dy * dy)
        return total

    def _detect_corners(
        self, path: List[Tuple[float, float]], angle_threshold: float = 30
    ) -> List[int]:
        """Detect corner indices in path."""
        if len(path) < 3:
            return []

        corners = []
        n = len(path)

        for i in range(n):
            # Get vectors to adjacent points
            p0 = path[(i - 1) % n]
            p1 = path[i]
            p2 = path[(i + 1) % n]

            v1 = (p0[0] - p1[0], p0[1] - p1[1])
            v2 = (p2[0] - p1[0], p2[1] - p1[1])

            # Calculate angle between vectors
            len1 = math.sqrt(v1[0]**2 + v1[1]**2)
            len2 = math.sqrt(v2[0]**2 + v2[1]**2)

            if len1 > 0 and len2 > 0:
                dot = v1[0]*v2[0] + v1[1]*v2[1]
                cos_angle = max(-1, min(1, dot / (len1 * len2)))
                angle = math.degrees(math.acos(cos_angle))

                if angle < (180 - angle_threshold):
                    corners.append(i)

        return corners

    def _calculate_corner_angles(
        self, path: List[Tuple[float, float]], corners: List[int]
    ) -> List[float]:
        """Calculate angles at detected corners."""
        angles = []
        n = len(path)

        for i in corners:
            p0 = path[(i - 1) % n]
            p1 = path[i]
            p2 = path[(i + 1) % n]

            v1 = (p0[0] - p1[0], p0[1] - p1[1])
            v2 = (p2[0] - p1[0], p2[1] - p1[1])

            len1 = math.sqrt(v1[0]**2 + v1[1]**2)
            len2 = math.sqrt(v2[0]**2 + v2[1]**2)

            if len1 > 0 and len2 > 0:
                dot = v1[0]*v2[0] + v1[1]*v2[1]
                cos_angle = max(-1, min(1, dot / (len1 * len2)))
                angle = math.degrees(math.acos(cos_angle))
                angles.append(angle)

        return angles


class ParametricEditor:
    """
    Applies parametric edits to detected features.

    Supports operations like:
    - Resize holes: "make all holes 2mm bigger"
    - Offset edges: "offset outer contour by 1mm"
    - Scale features: "scale holes by 150%"
    """

    def __init__(self):
        self.detector = FeatureDetector()

    def resize_holes(
        self,
        paths: List[List[Tuple[float, float]]],
        inner_flags: Optional[List[bool]] = None,
        delta: float = 0,  # Size change in mm
        scale: float = 1.0,  # Scale factor (1.0 = no change)
        target_size: Optional[float] = None,  # Absolute target size in mm
        feature_filter: Optional[FeatureType] = None,  # Only edit this type
        min_size: Optional[float] = None,  # Only edit if >= this size
        max_size: Optional[float] = None,  # Only edit if <= this size
    ) -> EditResult:
        """
        Resize holes/circles in paths.

        Args:
            paths: List of 2D paths
            inner_flags: Which paths are inner contours
            delta: Size change in mm (+2 = make 2mm bigger)
            scale: Scale factor (1.1 = 10% bigger)
            target_size: Set exact size (overrides delta/scale)
            feature_filter: Only edit specific feature type
            min_size: Only edit features >= this size
            max_size: Only edit features <= this size

        Returns:
            EditResult with modified paths
        """
        if inner_flags is None:
            inner_flags = [True] * len(paths)

        # Detect features
        features = self.detector.detect_features(paths, inner_flags)

        # Filter features
        filtered = []
        for f in features:
            # Apply type filter
            if feature_filter and f.feature_type != feature_filter:
                continue
            # Apply size filters
            if min_size is not None and f.size < min_size:
                continue
            if max_size is not None and f.size > max_size:
                continue
            # Only edit circular-ish features by default
            if feature_filter is None and f.feature_type not in (
                FeatureType.HOLE, FeatureType.CIRCLE, FeatureType.SLOT
            ):
                continue
            filtered.append(f)

        if not filtered:
            return EditResult(
                success=False,
                message="No matching features found to edit",
                features_modified=0,
            )

        # Apply edits
        modified_paths = [list(p) for p in paths]  # Copy
        modified_features = []

        for feature in filtered:
            if feature.path_index < 0 or feature.path_index >= len(modified_paths):
                continue

            # Calculate new size
            if target_size is not None:
                new_size = target_size
            else:
                new_size = (feature.size + delta) * scale

            # Ensure positive size
            if new_size <= 0:
                continue

            # Calculate scale factor for this feature
            feature_scale = new_size / feature.size if feature.size > 0 else 1.0

            # Scale the path around center
            new_path = self._scale_path_around_center(
                modified_paths[feature.path_index],
                feature.center,
                feature_scale,
            )

            modified_paths[feature.path_index] = new_path

            # Create modified feature record
            mod_feature = DetectedFeature(
                feature_type=feature.feature_type,
                center=feature.center,
                size=new_size,
                secondary_size=(
                    feature.secondary_size * feature_scale
                    if feature.secondary_size else None
                ),
                rotation=feature.rotation,
                vertices=new_path,
                path_index=feature.path_index,
                is_inner=feature.is_inner,
                confidence=feature.confidence,
            )
            modified_features.append(mod_feature)

        # Create result
        size_change = delta if delta else (scale - 1) * 100
        direction = "larger" if size_change > 0 else "smaller"

        return EditResult(
            success=True,
            message=f"Resized {len(modified_features)} features ({direction})",
            features_modified=len(modified_features),
            original_features=filtered,
            modified_features=modified_features,
            modified_paths=modified_paths,
        )

    def offset_contours(
        self,
        paths: List[List[Tuple[float, float]]],
        inner_flags: Optional[List[bool]] = None,
        offset: float = 0,  # Positive = outward, negative = inward
        inner_only: bool = False,
        outer_only: bool = False,
    ) -> EditResult:
        """
        Offset all contours in/out.

        Args:
            paths: List of 2D paths
            inner_flags: Which paths are inner contours
            offset: Distance to offset (+ = outward, - = inward)
            inner_only: Only offset inner contours
            outer_only: Only offset outer contours

        Returns:
            EditResult with modified paths
        """
        if inner_flags is None:
            inner_flags = [True] * len(paths)

        modified_paths = []
        count = 0

        for i, (path, is_inner) in enumerate(zip(paths, inner_flags)):
            # Check filter
            if inner_only and not is_inner:
                modified_paths.append(list(path))
                continue
            if outer_only and is_inner:
                modified_paths.append(list(path))
                continue

            # Apply offset
            new_path = self._offset_path(path, offset, is_inner)
            modified_paths.append(new_path)
            count += 1

        direction = "outward" if offset > 0 else "inward"

        return EditResult(
            success=True,
            message=f"Offset {count} contours {abs(offset):.2f}mm {direction}",
            features_modified=count,
            modified_paths=modified_paths,
        )

    def _scale_path_around_center(
        self,
        path: List[Tuple[float, float]],
        center: Tuple[float, float],
        scale: float,
    ) -> List[Tuple[float, float]]:
        """Scale path around a center point."""
        result = []
        for x, y in path:
            new_x = center[0] + (x - center[0]) * scale
            new_y = center[1] + (y - center[1]) * scale
            result.append((new_x, new_y))
        return result

    def _offset_path(
        self,
        path: List[Tuple[float, float]],
        offset: float,
        is_inner: bool,
    ) -> List[Tuple[float, float]]:
        """
        Offset a path by moving vertices along normals.

        For inner contours, positive offset = shrink hole
        For outer contours, positive offset = expand
        """
        if len(path) < 3:
            return list(path)

        # Adjust offset direction based on contour type
        # Inner contours: positive offset should make hole bigger (outward from center)
        # Outer contours: positive offset should make shape bigger
        actual_offset = offset if not is_inner else -offset

        result = []
        n = len(path)

        for i in range(n):
            # Get adjacent points
            p0 = path[(i - 1) % n]
            p1 = path[i]
            p2 = path[(i + 1) % n]

            # Calculate edge normals
            e1 = (p1[0] - p0[0], p1[1] - p0[1])
            e2 = (p2[0] - p1[0], p2[1] - p1[1])

            # Perpendicular (outward) normals
            len1 = math.sqrt(e1[0]**2 + e1[1]**2)
            len2 = math.sqrt(e2[0]**2 + e2[1]**2)

            if len1 > 0 and len2 > 0:
                n1 = (-e1[1] / len1, e1[0] / len1)
                n2 = (-e2[1] / len2, e2[0] / len2)

                # Average normal
                nx = (n1[0] + n2[0]) / 2
                ny = (n1[1] + n2[1]) / 2
                length = math.sqrt(nx**2 + ny**2)

                if length > 0:
                    nx /= length
                    ny /= length

                    new_x = p1[0] + nx * actual_offset
                    new_y = p1[1] + ny * actual_offset
                    result.append((new_x, new_y))
                else:
                    result.append(p1)
            else:
                result.append(p1)

        return result


# Convenience functions

def detect_features(
    paths: List[List[Tuple[float, float]]],
    inner_flags: Optional[List[bool]] = None,
) -> List[DetectedFeature]:
    """Detect geometric features in paths."""
    detector = FeatureDetector()
    return detector.detect_features(paths, inner_flags)


def resize_holes(
    paths: List[List[Tuple[float, float]]],
    delta: float = 0,
    scale: float = 1.0,
    **kwargs
) -> EditResult:
    """Resize holes in paths."""
    editor = ParametricEditor()
    return editor.resize_holes(paths, delta=delta, scale=scale, **kwargs)


def format_feature(feature: DetectedFeature) -> str:
    """Format feature for display."""
    type_name = feature.feature_type.value.replace("_", " ").title()
    location = f"at ({feature.center[0]:.1f}, {feature.center[1]:.1f})"

    if feature.feature_type in (FeatureType.HOLE, FeatureType.CIRCLE):
        size_info = f"Ø{feature.size:.2f}mm"
    elif feature.feature_type == FeatureType.SLOT:
        size_info = f"{feature.size:.2f} x {feature.secondary_size:.2f}mm"
    elif feature.feature_type == FeatureType.RECTANGLE:
        size_info = f"{feature.size:.2f} x {feature.secondary_size:.2f}mm"
    else:
        size_info = f"~{feature.size:.2f}mm"

    contour = "inner" if feature.is_inner else "outer"

    return f"{type_name} ({contour}): {size_info} {location}"


def format_edit_result(result: EditResult) -> str:
    """Format edit result for display."""
    lines = [
        f"Edit Result: {'SUCCESS' if result.success else 'FAILED'}",
        f"Message: {result.message}",
        f"Features modified: {result.features_modified}",
    ]

    if result.original_features:
        lines.append("\nOriginal features:")
        for f in result.original_features:
            lines.append(f"  - {format_feature(f)}")

    if result.modified_features:
        lines.append("\nModified features:")
        for f in result.modified_features:
            lines.append(f"  - {format_feature(f)}")

    return "\n".join(lines)


# Command interpreter integration

def interpret_parametric_command(text: str) -> Optional[Dict[str, Any]]:
    """
    Interpret natural language parametric edit commands.

    Examples:
        "make all holes 2mm bigger"
        "enlarge holes by 10%"
        "shrink holes to 5mm"
        "offset edges outward 1mm"
    """
    import re
    text = text.lower().strip()

    # Hole resize commands
    hole_keywords = ['hole', 'holes', 'circular', 'circles', 'round']
    if any(kw in text for kw in hole_keywords):
        # Parse size change
        delta = 0
        scale = 1.0
        target = None

        # "2mm bigger/larger"
        match = re.search(r'([\d.]+)\s*(?:mm|millimeter)?\s*(?:bigger|larger)', text)
        if match:
            delta = float(match.group(1))

        # "2mm smaller"
        match = re.search(r'([\d.]+)\s*(?:mm|millimeter)?\s*smaller', text)
        if match:
            delta = -float(match.group(1))

        # "by 10%" or "10% larger" or "enlarge by 10%"
        match = re.search(r'(?:by\s+)?([\d.]+)\s*%', text)
        if match:
            pct = float(match.group(1))
            # Check if shrinking or making smaller
            if 'shrink' in text or 'smaller' in text or 'reduce' in text:
                scale = 1 - pct / 100
            else:
                scale = 1 + pct / 100

        # "to 5mm" (absolute size)
        match = re.search(r'to\s+([\d.]+)\s*(?:mm|millimeter)?', text)
        if match:
            target = float(match.group(1))

        return {
            "action": "resize_holes",
            "params": {
                "delta": delta,
                "scale": scale,
                "target_size": target,
            }
        }

    # Offset commands
    if any(kw in text for kw in ['offset', 'expand', 'shrink', 'grow']):
        offset = 0

        # Find any number followed by mm (anywhere in text)
        # Patterns: "by 1mm", "1mm", "1 mm"
        match = re.search(r'(?:by\s+)?([\d.]+)\s*(?:mm|millimeter)', text)
        if match:
            offset = float(match.group(1))

        # If shrink keyword, make offset negative
        if 'shrink' in text:
            offset = -abs(offset)

        # Direction modifies sign
        if 'inward' in text or 'inside' in text:
            offset = -abs(offset)
        elif 'outward' in text or 'outside' in text:
            offset = abs(offset)

        inner_only = 'inner' in text or 'hole' in text
        outer_only = 'outer' in text or 'edge' in text

        return {
            "action": "offset_contours",
            "params": {
                "offset": offset,
                "inner_only": inner_only,
                "outer_only": outer_only,
            }
        }

    return None


# Testing
if __name__ == "__main__":
    print("Parametric Edits Module Test")
    print("=" * 50)

    # Create test paths - a circle (hole) and a rectangle
    import math

    # Circle with 10mm diameter
    circle_points = []
    for i in range(32):
        angle = 2 * math.pi * i / 32
        x = 50 + 5 * math.cos(angle)  # Radius 5mm = diameter 10mm
        y = 50 + 5 * math.sin(angle)
        circle_points.append((x, y))

    # Rectangle
    rect_points = [
        (10, 10), (30, 10), (30, 20), (10, 20)
    ]

    paths = [circle_points, rect_points]
    inner_flags = [True, True]  # Both are holes

    # Detect features
    print("\nDetecting features...")
    features = detect_features(paths, inner_flags)
    for f in features:
        print(f"  {format_feature(f)}")

    # Resize holes
    print("\nResizing holes (make 2mm bigger)...")
    result = resize_holes(paths, inner_flags=inner_flags, delta=2)
    print(format_edit_result(result))

    # Test command interpretation
    print("\n" + "=" * 50)
    print("Command Interpretation Test")
    print("=" * 50)

    test_commands = [
        "make all holes 2mm bigger",
        "enlarge holes by 10%",
        "shrink holes to 5mm diameter",
        "make circular features 3mm smaller",
        "offset edges outward 1mm",
        "shrink inner contours by 0.5mm",
    ]

    for cmd in test_commands:
        result = interpret_parametric_command(cmd)
        print(f"\n'{cmd}'")
        print(f"  -> {result}")
