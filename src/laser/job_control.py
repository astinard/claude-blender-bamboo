"""
Laser Job Control for Bambu Lab H2D.

Manages laser cutting/engraving jobs on the H2D printer.
Handles job preparation, upload, and execution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum
import json
import time

from .presets import LaserPreset, get_preset, get_preset_for_material
from .svg_export import SVGExporter, paths_to_svg
from .dxf_export import DXFExporter, paths_to_dxf
from .cross_section import Path2D


class LaserJobStatus(Enum):
    """Status of a laser job."""
    PENDING = "pending"
    PREPARING = "preparing"
    UPLOADING = "uploading"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LaserJobLayer:
    """A layer in a laser job (one operation type)."""
    name: str
    paths: List[Path2D]
    preset: LaserPreset
    color: str = "#FF0000"  # Display color in UI


@dataclass
class LaserJob:
    """A complete laser job with multiple layers/operations."""
    name: str
    layers: List[LaserJobLayer] = field(default_factory=list)
    status: LaserJobStatus = LaserJobStatus.PENDING

    # Job settings
    origin: Tuple[float, float] = (0, 0)  # Job origin on bed
    repeat_count: int = 1
    air_assist: bool = True

    # Metadata
    created_at: float = field(default_factory=time.time)
    estimated_time: float = 0  # seconds
    material_used: str = ""

    @property
    def total_paths(self) -> int:
        return sum(len(layer.paths) for layer in self.layers)

    @property
    def bounding_box(self) -> Tuple[float, float, float, float]:
        """Get bounding box of all paths."""
        all_points = []
        for layer in self.layers:
            for path in layer.paths:
                all_points.extend(path.points)

        if not all_points:
            return (0, 0, 0, 0)

        min_x = min(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_x = max(p[0] for p in all_points)
        max_y = max(p[1] for p in all_points)

        return (min_x, min_y, max_x, max_y)

    @property
    def size(self) -> Tuple[float, float]:
        """Get job size (width, height)."""
        bbox = self.bounding_box
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])


class LaserJobController:
    """
    Controls laser jobs on the H2D printer.

    Usage:
        controller = LaserJobController()

        # Create job from paths
        job = controller.create_job("my_project", paths, preset='wood_3mm_cut')

        # Export to file
        controller.export_job(job, 'output/project.svg')

        # Or send to printer (when connected)
        controller.send_to_printer(job, printer)
    """

    def __init__(self):
        """Initialize laser job controller."""
        self.current_job: Optional[LaserJob] = None
        self.job_history: List[LaserJob] = []

    def create_job(self, name: str, paths: List[Path2D],
                   preset: str | LaserPreset = 'wood_3mm_cut',
                   material: str = None,
                   thickness: float = 3.0,
                   operation: str = 'cut') -> LaserJob:
        """
        Create a new laser job.

        Args:
            name: Job name
            paths: List of 2D paths
            preset: Preset name or LaserPreset object
            material: Material name (alternative to preset)
            thickness: Material thickness (if using material)
            operation: Operation type (if using material)

        Returns:
            LaserJob
        """
        # Get preset
        if isinstance(preset, str):
            laser_preset = get_preset(preset)
            if laser_preset is None and material:
                laser_preset = get_preset_for_material(material, thickness, operation)
            if laser_preset is None:
                laser_preset = get_preset('wood_3mm_cut')  # Default
        else:
            laser_preset = preset

        # Create layer
        layer = LaserJobLayer(
            name=f"{operation.title()} Layer",
            paths=paths,
            preset=laser_preset,
            color="#FF0000" if operation == 'cut' else "#0000FF"
        )

        # Create job
        job = LaserJob(
            name=name,
            layers=[layer],
            material_used=laser_preset.material if laser_preset else "unknown"
        )

        # Estimate time
        job.estimated_time = self._estimate_time(job)

        self.current_job = job
        return job

    def add_layer(self, job: LaserJob, paths: List[Path2D],
                  preset: str | LaserPreset, name: str = None) -> LaserJob:
        """
        Add a layer to an existing job.

        Args:
            job: Existing LaserJob
            paths: Paths for new layer
            preset: Preset for new layer
            name: Layer name

        Returns:
            Updated LaserJob
        """
        if isinstance(preset, str):
            laser_preset = get_preset(preset)
        else:
            laser_preset = preset

        layer_name = name or f"Layer {len(job.layers) + 1}"

        layer = LaserJobLayer(
            name=layer_name,
            paths=paths,
            preset=laser_preset
        )

        job.layers.append(layer)
        job.estimated_time = self._estimate_time(job)

        return job

    def export_job(self, job: LaserJob, filepath: str,
                   format: str = 'svg') -> bool:
        """
        Export job to file.

        Args:
            job: LaserJob to export
            filepath: Output file path
            format: 'svg' or 'dxf'

        Returns:
            True if successful
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Combine all paths
        all_paths = []
        for layer in job.layers:
            all_paths.extend(layer.paths)

        if format.lower() == 'svg':
            exporter = SVGExporter()
            # Use first layer's operation for style
            style = job.layers[0].preset.operation if job.layers else 'cut'
            exporter.save(all_paths, str(filepath), style=style)
        elif format.lower() == 'dxf':
            exporter = DXFExporter()
            layer = job.layers[0].preset.operation if job.layers else 'cut'
            exporter.save(all_paths, str(filepath), layer=layer)
        else:
            return False

        return True

    def export_layered_svg(self, job: LaserJob, filepath: str) -> bool:
        """
        Export job with separate SVG groups for each layer.

        Useful for software that supports layer-based laser control.
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Build combined SVG with multiple groups
        exporter = SVGExporter()

        # Get overall bounding box
        all_points = []
        for layer in job.layers:
            for path in layer.paths:
                all_points.extend(path.points)

        if not all_points:
            return False

        min_x = min(p[0] for p in all_points)
        min_y = min(p[1] for p in all_points)
        max_x = max(p[0] for p in all_points)
        max_y = max(p[1] for p in all_points)

        margin = 5.0
        width = max_x - min_x + 2 * margin
        height = max_y - min_y + 2 * margin

        # Build SVG manually for layered export
        import xml.etree.ElementTree as ET
        from xml.dom import minidom

        root = ET.Element('svg')
        root.set('xmlns', 'http://www.w3.org/2000/svg')
        root.set('width', f'{width:.3f}mm')
        root.set('height', f'{height:.3f}mm')
        root.set('viewBox', f'0 0 {width:.3f} {height:.3f}')

        # Add each layer as a group
        for i, layer in enumerate(job.layers):
            group = ET.SubElement(root, 'g')
            group.set('id', f'layer_{i}_{layer.preset.operation}')
            group.set('inkscape:label', layer.name)
            group.set('stroke', layer.color)
            group.set('stroke-width', '0.1')
            group.set('fill', 'none')

            for j, path in enumerate(layer.paths):
                if len(path.points) < 2:
                    continue

                d_parts = [f'M {path.points[0][0] + margin - min_x:.3f},{path.points[0][1] + margin - min_y:.3f}']
                for x, y in path.points[1:]:
                    d_parts.append(f'L {x + margin - min_x:.3f},{y + margin - min_y:.3f}')
                if path.is_closed:
                    d_parts.append('Z')

                path_elem = ET.SubElement(group, 'path')
                path_elem.set('id', f'path_{i}_{j}')
                path_elem.set('d', ' '.join(d_parts))

        # Write file
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent='  ')
        with open(filepath, 'w') as f:
            f.write(xml_str)

        return True

    def send_to_printer(self, job: LaserJob, printer) -> Dict:
        """
        Send job to H2D printer.

        Args:
            job: LaserJob to send
            printer: BambuRealPrinter instance

        Returns:
            Result dict with success status
        """
        # Export to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
            temp_path = f.name

        self.export_job(job, temp_path, format='svg')

        # Upload to printer
        try:
            result = printer.upload_file(temp_path, f"{job.name}.svg")
            if result.success:
                job.status = LaserJobStatus.QUEUED
                self.job_history.append(job)
                return {
                    "success": True,
                    "message": f"Job '{job.name}' uploaded to printer",
                    "job_id": job.name
                }
            else:
                job.status = LaserJobStatus.FAILED
                return {
                    "success": False,
                    "message": f"Upload failed: {result.message}"
                }
        except Exception as e:
            job.status = LaserJobStatus.FAILED
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
        finally:
            # Clean up temp file
            try:
                Path(temp_path).unlink()
            except:
                pass

    def _estimate_time(self, job: LaserJob) -> float:
        """
        Estimate job time in seconds.

        This is a rough estimate based on path lengths and speeds.
        """
        total_time = 0

        for layer in job.layers:
            if not layer.preset:
                continue

            speed = layer.preset.speed  # mm/s

            # Calculate total path length
            path_length = 0
            for path in layer.paths:
                for i in range(len(path.points) - 1):
                    p0 = path.points[i]
                    p1 = path.points[i + 1]
                    path_length += ((p1[0] - p0[0])**2 + (p1[1] - p0[1])**2)**0.5

            # Time = distance / speed * passes
            layer_time = (path_length / speed) * layer.preset.passes

            # Add overhead for acceleration/deceleration (rough estimate)
            layer_time *= 1.2

            total_time += layer_time

        return total_time

    def get_job_summary(self, job: LaserJob) -> str:
        """Get human-readable job summary."""
        lines = [
            f"Job: {job.name}",
            f"Status: {job.status.value}",
            f"Layers: {len(job.layers)}",
            f"Total paths: {job.total_paths}",
            f"Size: {job.size[0]:.1f} x {job.size[1]:.1f} mm",
            f"Estimated time: {job.estimated_time:.0f} seconds ({job.estimated_time/60:.1f} min)",
            f"Material: {job.material_used}",
            "",
            "Layers:",
        ]

        for i, layer in enumerate(job.layers):
            lines.append(f"  {i+1}. {layer.name}")
            if layer.preset:
                lines.append(f"      Preset: {layer.preset.name}")
                lines.append(f"      Power: {layer.preset.power}% @ {layer.preset.speed} mm/s")
                lines.append(f"      Paths: {len(layer.paths)}")

        return '\n'.join(lines)


# Convenience function
def create_laser_job(name: str, paths: List[Path2D],
                     material: str = 'wood',
                     thickness: float = 3.0,
                     operation: str = 'cut') -> LaserJob:
    """
    Convenience function to create a laser job.

    Args:
        name: Job name
        paths: 2D paths
        material: Material name
        thickness: Material thickness
        operation: Operation type

    Returns:
        LaserJob
    """
    controller = LaserJobController()
    return controller.create_job(
        name=name,
        paths=paths,
        material=material,
        thickness=thickness,
        operation=operation
    )


if __name__ == "__main__":
    # Test job creation
    from .cross_section import Path2D

    test_paths = [
        Path2D(
            points=[(-25, -15), (25, -15), (25, 15), (-25, 15)],
            is_closed=True
        ),
        Path2D(
            points=[(0, 0), (10, 0), (10, 10), (0, 10)],
            is_closed=True
        ),
    ]

    controller = LaserJobController()
    job = controller.create_job(
        name="Test Project",
        paths=test_paths,
        material='wood',
        thickness=3.0,
        operation='cut'
    )

    print(controller.get_job_summary(job))

    # Export
    controller.export_job(job, "/tmp/test_job.svg")
    controller.export_job(job, "/tmp/test_job.dxf", format='dxf')
    print("\nExported to /tmp/test_job.svg and /tmp/test_job.dxf")
