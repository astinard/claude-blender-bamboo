"""
3MF Export Module for Multi-Color/Material 3D Printing.

Creates 3MF files compatible with Bambu Studio and other slicers,
supporting vertex colors mapped to AMS filament slots.

3MF Structure:
    model.3mf (ZIP archive)
    ├── [Content_Types].xml
    ├── _rels/.rels
    ├── 3D/
    │   └── 3dmodel.model (main geometry + materials)
    └── Metadata/
        └── model_settings.config (slicer settings)
"""

import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
import struct

# Try to import Blender modules (only available when running in Blender)
try:
    import bpy
    import bmesh
    from mathutils import Vector, Matrix
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False


@dataclass
class MaterialSlot:
    """Material slot for 3MF export."""
    name: str
    color: Tuple[float, float, float, float]  # RGBA 0-1
    ams_slot: int = 0  # AMS slot index (0-15)


@dataclass
class MeshData:
    """Mesh data for 3MF export."""
    vertices: List[Tuple[float, float, float]]
    triangles: List[Tuple[int, int, int]]
    triangle_colors: List[int]  # Material index per triangle
    materials: List[MaterialSlot]


def color_to_hex(color: Tuple[float, float, float, float]) -> str:
    """Convert RGBA color to hex string (#RRGGBBAA)."""
    r = int(color[0] * 255)
    g = int(color[1] * 255)
    b = int(color[2] * 255)
    a = int(color[3] * 255)
    return f"#{r:02X}{g:02X}{b:02X}{a:02X}"


def quantize_color(color: Tuple[float, float, float, float], tolerance: float = 0.1) -> Tuple[int, int, int]:
    """Quantize color to reduce unique colors (for material mapping)."""
    # Convert to 0-255 range and quantize to steps
    step = int(255 * tolerance)
    if step == 0:
        step = 1
    r = (int(color[0] * 255) // step) * step
    g = (int(color[1] * 255) // step) * step
    b = (int(color[2] * 255) // step) * step
    return (r, g, b)


def get_unique_colors_from_mesh(obj) -> Dict[Tuple[int, int, int], Tuple[float, float, float, float]]:
    """
    Extract unique colors from mesh vertex colors.
    Returns dict mapping quantized RGB to original RGBA.
    """
    if not HAS_BLENDER:
        return {}

    mesh = obj.data
    unique_colors = {}

    # Get color attribute
    color_attr = mesh.color_attributes.get('Col')
    if color_attr is None:
        # No vertex colors, return default white
        return {(255, 255, 255): (1.0, 1.0, 1.0, 1.0)}

    # Collect unique colors from face corners
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            color = tuple(color_attr.data[loop_idx].color)
            quantized = quantize_color(color)
            if quantized not in unique_colors:
                unique_colors[quantized] = color

    return unique_colors


def extract_mesh_data(obj, transform: bool = True) -> MeshData:
    """
    Extract mesh data from Blender object for 3MF export.

    Args:
        obj: Blender mesh object
        transform: Apply world transform to vertices

    Returns:
        MeshData with vertices, triangles, and material assignments
    """
    if not HAS_BLENDER:
        raise RuntimeError("This function requires Blender")

    mesh = obj.data
    world_matrix = obj.matrix_world if transform else Matrix.Identity(4)

    # Ensure mesh is triangulated
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    mesh.calc_loop_triangles()

    # Get unique colors and create material mapping
    unique_colors = get_unique_colors_from_mesh(obj)
    color_to_mat_idx = {}
    materials = []

    for i, (quantized, rgba) in enumerate(unique_colors.items()):
        color_to_mat_idx[quantized] = i
        materials.append(MaterialSlot(
            name=f"Color_{i}",
            color=rgba,
            ams_slot=i % 16  # Map to AMS slots (max 16)
        ))

    # Extract vertices
    vertices = []
    for v in mesh.vertices:
        co = world_matrix @ v.co
        # Convert to mm (Blender uses meters by default, but we set scale to 0.001)
        vertices.append((co.x, co.y, co.z))

    # Extract triangles with color assignments
    triangles = []
    triangle_colors = []

    color_attr = mesh.color_attributes.get('Col')

    for tri in mesh.loop_triangles:
        # Get vertex indices
        triangles.append((tri.vertices[0], tri.vertices[1], tri.vertices[2]))

        # Get color from first vertex of triangle
        if color_attr:
            loop_idx = tri.loops[0]
            color = tuple(color_attr.data[loop_idx].color)
            quantized = quantize_color(color)
            mat_idx = color_to_mat_idx.get(quantized, 0)
        else:
            mat_idx = 0

        triangle_colors.append(mat_idx)

    return MeshData(
        vertices=vertices,
        triangles=triangles,
        triangle_colors=triangle_colors,
        materials=materials
    )


def create_content_types_xml() -> str:
    """Create [Content_Types].xml for 3MF."""
    root = ET.Element('Types')
    root.set('xmlns', 'http://schemas.openxmlformats.org/package/2006/content-types')

    # Default extensions
    ET.SubElement(root, 'Default', Extension='rels',
                  ContentType='application/vnd.openxmlformats-package.relationships+xml')
    ET.SubElement(root, 'Default', Extension='model',
                  ContentType='application/vnd.ms-package.3dmanufacturing-3dmodel+xml')

    return minidom.parseString(ET.tostring(root)).toprettyxml(indent='  ')


def create_rels_xml() -> str:
    """Create _rels/.rels for 3MF."""
    root = ET.Element('Relationships')
    root.set('xmlns', 'http://schemas.openxmlformats.org/package/2006/relationships')

    ET.SubElement(root, 'Relationship',
                  Target='/3D/3dmodel.model',
                  Id='rel0',
                  Type='http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel')

    return minidom.parseString(ET.tostring(root)).toprettyxml(indent='  ')


def create_3dmodel_xml(mesh_data: MeshData, unit: str = 'millimeter') -> str:
    """
    Create 3D/3dmodel.model XML for 3MF.

    This is the main geometry file containing vertices, triangles,
    and material definitions.
    """
    # Namespaces
    ns = {
        '': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02',
        'm': 'http://schemas.microsoft.com/3dmanufacturing/material/2015/02',
        'p': 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06',
    }

    root = ET.Element('model')
    root.set('unit', unit)
    root.set('xmlns', ns[''])
    root.set('xmlns:m', ns['m'])
    root.set('xmlns:p', ns['p'])
    root.set('requiredextensions', 'p')

    # Metadata
    metadata = ET.SubElement(root, 'metadata', name='Application')
    metadata.text = 'Claude Fab Lab'

    # Resources
    resources = ET.SubElement(root, 'resources')

    # Add base materials (color groups)
    if len(mesh_data.materials) > 1:
        basematerials = ET.SubElement(resources, 'm:basematerials', id='1')
        for mat in mesh_data.materials:
            ET.SubElement(basematerials, 'm:base',
                         name=mat.name,
                         displaycolor=color_to_hex(mat.color))

    # Add object with mesh
    obj_elem = ET.SubElement(resources, 'object', id='2', type='model')

    mesh_elem = ET.SubElement(obj_elem, 'mesh')

    # Vertices
    vertices_elem = ET.SubElement(mesh_elem, 'vertices')
    for v in mesh_data.vertices:
        ET.SubElement(vertices_elem, 'vertex',
                     x=f'{v[0]:.6f}',
                     y=f'{v[1]:.6f}',
                     z=f'{v[2]:.6f}')

    # Triangles with material assignments
    triangles_elem = ET.SubElement(mesh_elem, 'triangles')

    for i, tri in enumerate(mesh_data.triangles):
        tri_attrs = {
            'v1': str(tri[0]),
            'v2': str(tri[1]),
            'v3': str(tri[2]),
        }

        # Add material reference if multiple materials
        if len(mesh_data.materials) > 1:
            mat_idx = mesh_data.triangle_colors[i]
            tri_attrs['pid'] = '1'  # Reference to basematerials
            tri_attrs['p1'] = str(mat_idx)

        ET.SubElement(triangles_elem, 'triangle', **tri_attrs)

    # Build section
    build = ET.SubElement(root, 'build')
    ET.SubElement(build, 'item', objectid='2')

    # Format with pretty printing
    xml_str = ET.tostring(root, encoding='unicode')
    return minidom.parseString(xml_str).toprettyxml(indent='  ')


def create_bambu_config(mesh_data: MeshData, plate_name: str = "Plate 1") -> str:
    """
    Create Bambu Studio compatible config file.

    This maps materials to AMS slots.
    """
    # JSON-like config for Bambu Studio
    config = {
        "plate_name": plate_name,
        "filament_info": [],
        "objects": [
            {
                "name": "model",
                "extruder": "1",
                "support_extruder": "0",
            }
        ]
    }

    # Add filament mappings
    for i, mat in enumerate(mesh_data.materials):
        config["filament_info"].append({
            "id": i,
            "color": color_to_hex(mat.color),
            "ams_slot": mat.ams_slot,
        })

    import json
    return json.dumps(config, indent=2)


def export_3mf(obj, filepath: str, ams_mapping: Optional[Dict[int, int]] = None) -> bool:
    """
    Export Blender object to 3MF file with multi-color support.

    Args:
        obj: Blender mesh object
        filepath: Output .3mf file path
        ams_mapping: Optional dict mapping material index to AMS slot

    Returns:
        True if successful
    """
    if not HAS_BLENDER:
        raise RuntimeError("This function requires Blender")

    # Extract mesh data
    mesh_data = extract_mesh_data(obj)

    # Apply AMS mapping if provided
    if ams_mapping:
        for i, mat in enumerate(mesh_data.materials):
            if i in ams_mapping:
                mat.ams_slot = ams_mapping[i]

    # Create 3MF archive
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Content types
        zf.writestr('[Content_Types].xml', create_content_types_xml())

        # Relationships
        zf.writestr('_rels/.rels', create_rels_xml())

        # Main model
        zf.writestr('3D/3dmodel.model', create_3dmodel_xml(mesh_data))

        # Bambu config (optional, for better slicer integration)
        zf.writestr('Metadata/model_settings.config', create_bambu_config(mesh_data))

    return True


def export_3mf_command(filepath: str, ams_mapping: Optional[Dict[int, int]] = None) -> Dict:
    """
    Export active object to 3MF (for use from interactive addon).

    Args:
        filepath: Output path
        ams_mapping: Optional material to AMS slot mapping

    Returns:
        Result dict with success status and message
    """
    if not HAS_BLENDER:
        return {"success": False, "message": "Not running in Blender"}

    obj = bpy.context.active_object
    if not obj or obj.type != 'MESH':
        # Find first mesh
        for o in bpy.context.scene.objects:
            if o.type == 'MESH':
                obj = o
                break

    if not obj:
        return {"success": False, "message": "No mesh object found"}

    try:
        export_3mf(obj, filepath, ams_mapping)

        # Get material count for response
        mesh_data = extract_mesh_data(obj)
        num_colors = len(mesh_data.materials)
        num_triangles = len(mesh_data.triangles)

        return {
            "success": True,
            "message": f"Exported to {filepath}",
            "data": {
                "filepath": str(filepath),
                "colors": num_colors,
                "triangles": num_triangles,
                "materials": [
                    {"name": m.name, "color": color_to_hex(m.color), "ams_slot": m.ams_slot}
                    for m in mesh_data.materials
                ]
            }
        }
    except Exception as e:
        return {"success": False, "message": f"Export failed: {str(e)}"}


# Test without Blender
if __name__ == "__main__":
    # Create test mesh data
    test_mesh = MeshData(
        vertices=[
            (0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),  # Bottom
            (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10),  # Top
        ],
        triangles=[
            (0, 1, 2), (0, 2, 3),  # Bottom
            (4, 6, 5), (4, 7, 6),  # Top
            (0, 4, 5), (0, 5, 1),  # Front
            (2, 6, 7), (2, 7, 3),  # Back
            (0, 3, 7), (0, 7, 4),  # Left
            (1, 5, 6), (1, 6, 2),  # Right
        ],
        triangle_colors=[0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0],  # Bottom white, top red
        materials=[
            MaterialSlot("White", (1.0, 1.0, 1.0, 1.0), ams_slot=0),
            MaterialSlot("Red", (1.0, 0.0, 0.0, 1.0), ams_slot=1),
        ]
    )

    # Test XML generation
    print("Content Types:")
    print(create_content_types_xml()[:200])

    print("\nRels:")
    print(create_rels_xml()[:200])

    print("\n3D Model (first 500 chars):")
    print(create_3dmodel_xml(test_mesh)[:500])

    # Create test file
    test_path = "/tmp/test_multicolor.3mf"
    with zipfile.ZipFile(test_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', create_content_types_xml())
        zf.writestr('_rels/.rels', create_rels_xml())
        zf.writestr('3D/3dmodel.model', create_3dmodel_xml(test_mesh))
        zf.writestr('Metadata/model_settings.config', create_bambu_config(test_mesh))

    print(f"\nTest 3MF created: {test_path}")
