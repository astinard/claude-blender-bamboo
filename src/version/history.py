"""Design version history management.

P4.5: Version History

Features:
- Git-like versioning for designs
- Save/restore any version
- Compare versions (diff)
- Branch designs
"""

import hashlib
import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from src.utils import get_logger, file_hash

logger = get_logger("version.history")


@dataclass
class DesignVersion:
    """A single version of a design file."""

    version_id: str
    design_id: str
    version_number: int
    message: str
    file_hash: str
    file_size: int
    timestamp: str
    parent_id: Optional[str] = None
    branch: str = "main"
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DesignVersion":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class VersionDiff:
    """Difference between two versions."""

    version_a: str
    version_b: str
    size_diff: int  # bytes
    file_changed: bool
    metadata_changes: Dict[str, Tuple[any, any]]  # key -> (old, new)


class VersionHistory:
    """
    Manages version history for design files.

    Provides git-like functionality:
    - Save versions with messages
    - Restore previous versions
    - Compare versions
    - Branch/tag support
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize version history manager.

        Args:
            storage_dir: Directory to store version data
        """
        self.storage_dir = storage_dir or Path("data/versions")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.index_file = self.storage_dir / "index.json"
        self.versions_dir = self.storage_dir / "objects"
        self.versions_dir.mkdir(exist_ok=True)

        self.designs: Dict[str, Dict] = {}  # design_id -> design info
        self.versions: Dict[str, DesignVersion] = {}  # version_id -> version
        self._load()

    def _load(self) -> None:
        """Load index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    data = json.load(f)
                self.designs = data.get("designs", {})
                self.versions = {
                    vid: DesignVersion.from_dict(v)
                    for vid, v in data.get("versions", {}).items()
                }
                logger.info(f"Loaded {len(self.versions)} versions for {len(self.designs)} designs")
            except Exception as e:
                logger.error(f"Failed to load version index: {e}")

    def _save(self) -> None:
        """Save index to disk."""
        data = {
            "designs": self.designs,
            "versions": {vid: v.to_dict() for vid, v in self.versions.items()},
        }
        with open(self.index_file, "w") as f:
            json.dump(data, f, indent=2)

    def _get_object_path(self, file_hash: str) -> Path:
        """Get path for stored file object."""
        # Use first 2 chars as subdirectory (like git)
        subdir = self.versions_dir / file_hash[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / file_hash

    def register_design(self, file_path: str, name: Optional[str] = None) -> str:
        """
        Register a new design for version tracking.

        Args:
            file_path: Path to the design file
            name: Optional name for the design

        Returns:
            Design ID
        """
        path = Path(file_path)
        design_id = str(uuid4())[:8]

        self.designs[design_id] = {
            "id": design_id,
            "name": name or path.stem,
            "original_path": str(path.absolute()),
            "current_branch": "main",
            "head": None,  # Latest version ID
            "created_at": datetime.now().isoformat(),
        }

        self._save()
        logger.info(f"Registered design {design_id}: {self.designs[design_id]['name']}")
        return design_id

    def save_version(
        self,
        file_path: str,
        message: str,
        design_id: Optional[str] = None,
        branch: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> DesignVersion:
        """
        Save a new version of a design.

        Args:
            file_path: Path to the current design file
            message: Version message
            design_id: Design ID (auto-registered if not provided)
            branch: Branch name (defaults to current branch)
            metadata: Optional metadata to store

        Returns:
            The created DesignVersion
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Auto-register if needed
        if design_id is None:
            # Check if file was previously registered
            for did, design in self.designs.items():
                if design["original_path"] == str(path.absolute()):
                    design_id = did
                    break
            if design_id is None:
                design_id = self.register_design(file_path)

        design = self.designs.get(design_id)
        if design is None:
            raise ValueError(f"Unknown design: {design_id}")

        # Calculate file hash
        fhash = file_hash(path)

        # Check if this exact version already exists
        for v in self.versions.values():
            if v.design_id == design_id and v.file_hash == fhash:
                logger.info(f"File unchanged from version {v.version_id}")
                return v

        # Copy file to storage
        object_path = self._get_object_path(fhash)
        if not object_path.exists():
            shutil.copy2(path, object_path)

        # Get version number
        design_versions = self.get_versions(design_id)
        version_number = len(design_versions) + 1

        # Get parent
        branch_name = branch or design["current_branch"]
        parent_id = design["head"]

        # Create version
        version = DesignVersion(
            version_id=str(uuid4())[:8],
            design_id=design_id,
            version_number=version_number,
            message=message,
            file_hash=fhash,
            file_size=path.stat().st_size,
            timestamp=datetime.now().isoformat(),
            parent_id=parent_id,
            branch=branch_name,
            metadata=metadata or {},
        )

        self.versions[version.version_id] = version
        design["head"] = version.version_id
        self._save()

        logger.info(f"Saved version {version.version_id} (v{version_number}): {message}")
        return version

    def get_version(self, version_id: str) -> Optional[DesignVersion]:
        """Get a specific version."""
        return self.versions.get(version_id)

    def get_versions(self, design_id: str, branch: Optional[str] = None) -> List[DesignVersion]:
        """
        Get all versions of a design.

        Args:
            design_id: Design ID
            branch: Optional branch filter

        Returns:
            List of versions, newest first
        """
        versions = [
            v for v in self.versions.values()
            if v.design_id == design_id
            and (branch is None or v.branch == branch)
        ]
        versions.sort(key=lambda v: v.version_number, reverse=True)
        return versions

    def get_latest(self, design_id: str) -> Optional[DesignVersion]:
        """Get the latest version of a design."""
        design = self.designs.get(design_id)
        if design and design["head"]:
            return self.versions.get(design["head"])
        return None

    def restore_version(self, version_id: str, output_path: str) -> bool:
        """
        Restore a specific version to a file.

        Args:
            version_id: Version to restore
            output_path: Where to write the restored file

        Returns:
            True if successful
        """
        version = self.versions.get(version_id)
        if version is None:
            logger.error(f"Version not found: {version_id}")
            return False

        object_path = self._get_object_path(version.file_hash)
        if not object_path.exists():
            logger.error(f"Version file missing: {version.file_hash}")
            return False

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(object_path, output)

        logger.info(f"Restored version {version_id} to {output_path}")
        return True

    def diff_versions(self, version_a_id: str, version_b_id: str) -> Optional[VersionDiff]:
        """
        Compare two versions.

        Args:
            version_a_id: First version
            version_b_id: Second version

        Returns:
            VersionDiff with comparison results
        """
        va = self.versions.get(version_a_id)
        vb = self.versions.get(version_b_id)

        if va is None or vb is None:
            return None

        # Check for file changes
        file_changed = va.file_hash != vb.file_hash
        size_diff = vb.file_size - va.file_size

        # Compare metadata
        metadata_changes = {}
        all_keys = set(va.metadata.keys()) | set(vb.metadata.keys())
        for key in all_keys:
            old_val = va.metadata.get(key)
            new_val = vb.metadata.get(key)
            if old_val != new_val:
                metadata_changes[key] = (old_val, new_val)

        return VersionDiff(
            version_a=version_a_id,
            version_b=version_b_id,
            size_diff=size_diff,
            file_changed=file_changed,
            metadata_changes=metadata_changes,
        )

    def create_branch(self, design_id: str, branch_name: str, from_version: Optional[str] = None) -> bool:
        """
        Create a new branch for a design.

        Args:
            design_id: Design ID
            branch_name: Name for the new branch
            from_version: Version to branch from (default: latest)

        Returns:
            True if successful
        """
        design = self.designs.get(design_id)
        if design is None:
            return False

        # Get starting version
        if from_version:
            version = self.versions.get(from_version)
        else:
            version = self.get_latest(design_id)

        if version is None:
            logger.error("No version to branch from")
            return False

        # Switch to new branch
        design["current_branch"] = branch_name
        self._save()

        logger.info(f"Created branch {branch_name} from {version.version_id}")
        return True

    def switch_branch(self, design_id: str, branch_name: str) -> bool:
        """Switch to a different branch."""
        design = self.designs.get(design_id)
        if design is None:
            return False

        design["current_branch"] = branch_name
        self._save()
        return True

    def tag_version(self, version_id: str, tag: str) -> bool:
        """Add a tag to a version."""
        version = self.versions.get(version_id)
        if version is None:
            return False

        if tag not in version.tags:
            version.tags.append(tag)
            self._save()
        return True

    def get_version_by_tag(self, design_id: str, tag: str) -> Optional[DesignVersion]:
        """Find a version by tag."""
        for v in self.versions.values():
            if v.design_id == design_id and tag in v.tags:
                return v
        return None

    def list_designs(self) -> List[Dict]:
        """List all registered designs."""
        return list(self.designs.values())

    def get_design(self, design_id: str) -> Optional[Dict]:
        """Get design information."""
        return self.designs.get(design_id)

    def get_design_by_path(self, file_path: str) -> Optional[str]:
        """Find design ID by file path."""
        path = Path(file_path).absolute()
        for design_id, design in self.designs.items():
            if design["original_path"] == str(path):
                return design_id
        return None
