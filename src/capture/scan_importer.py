"""Scan importer for Polycam and other 3D scanning apps.

Watches a folder for incoming STL/OBJ files and imports them into JARVIS.
"""

import asyncio
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass

from src.utils import get_logger

logger = get_logger("capture.scan_importer")


@dataclass
class ImportedScan:
    """Result of importing a scan."""
    success: bool
    original_path: Path
    imported_path: Optional[Path] = None
    name: str = ""
    vertices: int = 0
    faces: int = 0
    file_size_mb: float = 0.0
    message: str = ""


class ScanImporter:
    """Import scans from Polycam and other scanning apps."""

    SUPPORTED_FORMATS = {".stl", ".obj", ".ply", ".glb", ".gltf", ".usdz", ".3mf"}

    def __init__(
        self,
        watch_folder: Optional[Path] = None,
        import_folder: Optional[Path] = None,
    ):
        """Initialize the scan importer.

        Args:
            watch_folder: Folder to watch for incoming scans (default: ~/projects/.../scans/incoming)
            import_folder: Folder to store imported scans (default: ~/projects/.../scans/imported)
        """
        base_path = Path(__file__).parent.parent.parent
        self.watch_folder = watch_folder or base_path / "scans" / "incoming"
        self.import_folder = import_folder or base_path / "scans" / "imported"

        # Create folders if they don't exist
        self.watch_folder.mkdir(parents=True, exist_ok=True)
        self.import_folder.mkdir(parents=True, exist_ok=True)

        self._watching = False
        self._callbacks: list[Callable[[ImportedScan], None]] = []

    def get_watch_folder(self) -> Path:
        """Get the folder path for incoming scans."""
        return self.watch_folder

    def import_scan(self, file_path: Path) -> ImportedScan:
        """Import a single scan file.

        Args:
            file_path: Path to the scan file

        Returns:
            ImportedScan with details about the import
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return ImportedScan(
                success=False,
                original_path=file_path,
                message=f"File not found: {file_path}"
            )

        if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            return ImportedScan(
                success=False,
                original_path=file_path,
                message=f"Unsupported format: {file_path.suffix}. Supported: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        # Generate unique name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = file_path.stem
        new_name = f"{base_name}_{timestamp}{file_path.suffix}"
        imported_path = self.import_folder / new_name

        try:
            # Copy file to import folder
            shutil.copy2(file_path, imported_path)

            # Get file stats
            file_size_mb = imported_path.stat().st_size / (1024 * 1024)

            # Try to get mesh info
            vertices, faces = self._get_mesh_info(imported_path)

            logger.info(f"Imported scan: {new_name} ({vertices} vertices, {faces} faces)")

            return ImportedScan(
                success=True,
                original_path=file_path,
                imported_path=imported_path,
                name=base_name,
                vertices=vertices,
                faces=faces,
                file_size_mb=round(file_size_mb, 2),
                message=f"Successfully imported {new_name}"
            )

        except Exception as e:
            logger.error(f"Failed to import {file_path}: {e}")
            return ImportedScan(
                success=False,
                original_path=file_path,
                message=f"Import failed: {str(e)}"
            )

    def _get_mesh_info(self, file_path: Path) -> tuple[int, int]:
        """Get vertex and face count from mesh file."""
        try:
            import trimesh
            mesh = trimesh.load(file_path)
            if hasattr(mesh, 'vertices') and hasattr(mesh, 'faces'):
                return len(mesh.vertices), len(mesh.faces)
        except ImportError:
            # trimesh not available, estimate from file size
            pass
        except Exception:
            pass

        # Rough estimate based on file size
        file_size = file_path.stat().st_size
        estimated_vertices = int(file_size / 50)  # ~50 bytes per vertex in STL
        estimated_faces = estimated_vertices // 3
        return estimated_vertices, estimated_faces

    def check_for_new_scans(self) -> list[ImportedScan]:
        """Check watch folder for new scans and import them.

        Returns:
            List of ImportedScan results
        """
        results = []

        for file_path in self.watch_folder.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                result = self.import_scan(file_path)
                results.append(result)

                # Remove original after successful import
                if result.success:
                    try:
                        file_path.unlink()
                    except Exception as e:
                        logger.warning(f"Could not remove original file: {e}")

        return results

    def list_imported_scans(self) -> list[dict]:
        """List all imported scans.

        Returns:
            List of scan info dicts
        """
        scans = []
        for file_path in self.import_folder.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                stat = file_path.stat()
                scans.append({
                    "name": file_path.stem,
                    "path": str(file_path),
                    "format": file_path.suffix.lower(),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "imported_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        # Sort by import date, newest first
        scans.sort(key=lambda x: x["imported_at"], reverse=True)
        return scans

    def on_scan_imported(self, callback: Callable[[ImportedScan], None]):
        """Register a callback for when a scan is imported."""
        self._callbacks.append(callback)

    async def watch(self, interval: float = 2.0):
        """Watch for new scans continuously.

        Args:
            interval: Check interval in seconds
        """
        self._watching = True
        logger.info(f"Watching for scans in: {self.watch_folder}")

        while self._watching:
            results = self.check_for_new_scans()
            for result in results:
                if result.success:
                    for callback in self._callbacks:
                        try:
                            callback(result)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

            await asyncio.sleep(interval)

    def stop_watching(self):
        """Stop the watch loop."""
        self._watching = False


def create_importer(
    watch_folder: Optional[Path] = None,
    import_folder: Optional[Path] = None,
) -> ScanImporter:
    """Create a scan importer instance."""
    return ScanImporter(watch_folder=watch_folder, import_folder=import_folder)


# Polycam-specific helpers
class PolycamIntegration:
    """Helper for Polycam-specific features."""

    @staticmethod
    def get_airdrop_folder() -> Path:
        """Get the default AirDrop downloads folder."""
        return Path.home() / "Downloads"

    @staticmethod
    def get_icloud_folder() -> Optional[Path]:
        """Get the iCloud Drive folder if available."""
        icloud_path = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
        if icloud_path.exists():
            return icloud_path
        return None

    @staticmethod
    def setup_polycam_export_instructions() -> str:
        """Get instructions for exporting from Polycam."""
        return """
Polycam Export Instructions:
=============================

1. In Polycam, open your scan
2. Tap "Export"
3. Choose format: STL (for 3D printing) or OBJ (with textures)
4. Select export quality (High recommended)
5. Choose destination:

   Option A - AirDrop (Fastest):
   - Tap "Share" → AirDrop → Your Mac
   - File will appear in ~/Downloads
   - Move to: scans/incoming/

   Option B - iCloud Drive:
   - Tap "Save to Files" → iCloud Drive
   - Create a "Polycam Exports" folder
   - Sync will happen automatically

   Option C - Direct folder (if set up):
   - Save directly to the watched folder

The scan will be automatically imported into JARVIS!
"""
