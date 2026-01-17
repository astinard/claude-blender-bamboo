"""
DXF Export for Laser Cutting Paths.

Generates DXF (AutoCAD Drawing Exchange Format) files from 2D paths.
DXF is widely supported by laser cutting software and CAD programs.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from pathlib import Path

from .cross_section import Path2D, CrossSectionResult
from .projection import ProjectionResult


# DXF layer colors (ACI - AutoCAD Color Index)
DXF_COLORS = {
    'red': 1,
    'yellow': 2,
    'green': 3,
    'cyan': 4,
    'blue': 5,
    'magenta': 6,
    'white': 7,
    'gray': 8,
    'black': 0,
}

# Operation to layer mapping
DXF_LAYERS = {
    'cut': ('CUT', 1),        # Red
    'engrave': ('ENGRAVE', 5), # Blue
    'score': ('SCORE', 3),     # Green
    'outline': ('OUTLINE', 7), # White
}


class DXFExporter:
    """
    Exports 2D paths to DXF format for laser cutting.

    Creates DXF files compatible with:
    - AutoCAD
    - LibreCAD
    - Lightburn
    - LaserGRBL
    - Most CNC/laser software

    Usage:
        exporter = DXFExporter()
        dxf_content = exporter.export(paths, layer='cut')
        exporter.save(paths, 'output.dxf')
    """

    def __init__(self, precision: int = 6):
        """
        Initialize DXF exporter.

        Args:
            precision: Decimal precision for coordinates
        """
        self.precision = precision

    def paths_to_dxf(self, paths: List[Path2D],
                     layer: str = 'cut',
                     offset: Tuple[float, float] = (0, 0)) -> str:
        """
        Convert paths to DXF string.

        Args:
            paths: List of Path2D objects
            layer: Layer name ('cut', 'engrave', 'score')
            offset: X, Y offset to apply

        Returns:
            DXF content as string
        """
        layer_name, color = DXF_LAYERS.get(layer, DXF_LAYERS['cut'])

        lines = []

        # DXF Header
        lines.extend(self._dxf_header())

        # Tables section (layers)
        lines.extend(self._dxf_tables([(layer_name, color)]))

        # Entities section
        lines.append('0')
        lines.append('SECTION')
        lines.append('2')
        lines.append('ENTITIES')

        # Add polylines for each path
        for path in paths:
            if len(path.points) >= 2:
                lines.extend(self._path_to_polyline(path, layer_name, offset))

        # End entities section
        lines.append('0')
        lines.append('ENDSEC')

        # End of file
        lines.append('0')
        lines.append('EOF')

        return '\n'.join(lines)

    def export_result(self, result, layer: str = 'cut') -> str:
        """
        Export CrossSectionResult or ProjectionResult to DXF.

        Args:
            result: CrossSectionResult or ProjectionResult
            layer: Layer name

        Returns:
            DXF content string
        """
        return self.paths_to_dxf(result.paths, layer=layer)

    def save(self, paths: List[Path2D], filepath: str, layer: str = 'cut', **kwargs):
        """
        Save paths to DXF file.

        Args:
            paths: List of Path2D objects
            filepath: Output file path
            layer: Layer name
            **kwargs: Additional arguments
        """
        dxf_content = self.paths_to_dxf(paths, layer=layer, **kwargs)

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w') as f:
            f.write(dxf_content)

    def save_result(self, result, filepath: str, layer: str = 'cut', **kwargs):
        """Save result object to DXF file."""
        self.save(result.paths, filepath, layer, **kwargs)

    def _dxf_header(self) -> List[str]:
        """Generate DXF header section."""
        return [
            '0', 'SECTION',
            '2', 'HEADER',
            '9', '$ACADVER',
            '1', 'AC1014',  # AutoCAD R14 format (widely compatible)
            '9', '$INSUNITS',
            '70', '4',  # Millimeters
            '9', '$MEASUREMENT',
            '70', '1',  # Metric
            '0', 'ENDSEC',
        ]

    def _dxf_tables(self, layers: List[Tuple[str, int]]) -> List[str]:
        """Generate DXF tables section with layers."""
        lines = [
            '0', 'SECTION',
            '2', 'TABLES',
            '0', 'TABLE',
            '2', 'LAYER',
            '70', str(len(layers)),
        ]

        for layer_name, color in layers:
            lines.extend([
                '0', 'LAYER',
                '2', layer_name,
                '70', '0',  # Layer state (0 = on)
                '62', str(color),  # Color number
                '6', 'CONTINUOUS',  # Linetype
            ])

        lines.extend([
            '0', 'ENDTAB',
            '0', 'ENDSEC',
        ])

        return lines

    def _path_to_polyline(self, path: Path2D, layer: str,
                         offset: Tuple[float, float]) -> List[str]:
        """Convert Path2D to DXF LWPOLYLINE entity."""
        lines = [
            '0', 'LWPOLYLINE',
            '8', layer,  # Layer name
            '90', str(len(path.points)),  # Number of vertices
            '70', '1' if path.is_closed else '0',  # Closed flag
        ]

        # Add vertices
        for x, y in path.points:
            lines.extend([
                '10', f'{x + offset[0]:.{self.precision}f}',
                '20', f'{y + offset[1]:.{self.precision}f}',
            ])

        return lines

    def _point_to_circle(self, x: float, y: float, radius: float, layer: str) -> List[str]:
        """Create a circle entity (useful for drill holes)."""
        return [
            '0', 'CIRCLE',
            '8', layer,
            '10', f'{x:.{self.precision}f}',
            '20', f'{y:.{self.precision}f}',
            '40', f'{radius:.{self.precision}f}',
        ]

    def _line_to_dxf(self, x1: float, y1: float, x2: float, y2: float, layer: str) -> List[str]:
        """Create a line entity."""
        return [
            '0', 'LINE',
            '8', layer,
            '10', f'{x1:.{self.precision}f}',
            '20', f'{y1:.{self.precision}f}',
            '11', f'{x2:.{self.precision}f}',
            '21', f'{y2:.{self.precision}f}',
        ]


def export_to_dxf(paths: List[Path2D], filepath: str, layer: str = 'cut'):
    """
    Convenience function to export paths to DXF file.

    Args:
        paths: List of Path2D objects
        filepath: Output file path
        layer: Layer name
    """
    exporter = DXFExporter()
    exporter.save(paths, filepath, layer)


def paths_to_dxf(paths: List[Path2D], layer: str = 'cut') -> str:
    """
    Convenience function to convert paths to DXF string.

    Args:
        paths: List of Path2D objects
        layer: Layer name

    Returns:
        DXF content string
    """
    exporter = DXFExporter()
    return exporter.paths_to_dxf(paths, layer)


# Test function
if __name__ == "__main__":
    # Create test paths
    test_paths = [
        Path2D(
            points=[(-25, -15), (25, -15), (25, 15), (-25, 15)],
            is_closed=True,
            is_outer=True
        ),
        Path2D(
            points=[(-10, -5), (10, -5), (10, 5), (-10, 5)],
            is_closed=True,
            is_outer=False  # This is a hole
        ),
    ]

    exporter = DXFExporter()
    dxf_content = exporter.paths_to_dxf(test_paths, layer='cut')

    print("Generated DXF (first 50 lines):")
    lines = dxf_content.split('\n')
    for line in lines[:50]:
        print(line)

    # Save to file
    test_path = "/tmp/test_laser.dxf"
    exporter.save(test_paths, test_path)
    print(f"\n...\nSaved to: {test_path}")
