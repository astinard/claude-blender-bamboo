"""AR Preview module for Claude Fab Lab.

Provides augmented reality preview capabilities for 3D models,
allowing users to visualize prints in physical space using iOS AR.
"""

from src.ar.usdz_exporter import (
    USDZExporter,
    ExportConfig,
    ExportResult,
    export_to_usdz,
)
from src.ar.qr_generator import (
    QRGenerator,
    QRConfig,
    generate_qr_code,
)
from src.ar.ar_server import (
    ARServer,
    ARSession,
    serve_ar_preview,
)

__all__ = [
    "USDZExporter",
    "ExportConfig",
    "ExportResult",
    "export_to_usdz",
    "QRGenerator",
    "QRConfig",
    "generate_qr_code",
    "ARServer",
    "ARSession",
    "serve_ar_preview",
]
