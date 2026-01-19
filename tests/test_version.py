"""Tests for version history management."""

import pytest
from pathlib import Path

from src.version.history import (
    DesignVersion,
    VersionHistory,
    VersionDiff,
)


class TestDesignVersion:
    """Tests for DesignVersion class."""

    def test_create_version(self):
        """Test creating a design version."""
        ver = DesignVersion(
            version_id="abc123",
            design_id="design1",
            version_number=1,
            message="Initial version",
            file_hash="hash123",
            file_size=1024,
            timestamp="2024-01-01T12:00:00",
        )
        assert ver.version_id == "abc123"
        assert ver.design_id == "design1"
        assert ver.version_number == 1
        assert ver.branch == "main"
        assert ver.tags == []

    def test_version_with_branch(self):
        """Test version with custom branch."""
        ver = DesignVersion(
            version_id="abc123",
            design_id="design1",
            version_number=1,
            message="Test",
            file_hash="hash123",
            file_size=1024,
            timestamp="2024-01-01T12:00:00",
            branch="experimental",
        )
        assert ver.branch == "experimental"

    def test_version_with_tags(self):
        """Test version with tags."""
        ver = DesignVersion(
            version_id="abc123",
            design_id="design1",
            version_number=1,
            message="Release",
            file_hash="hash123",
            file_size=1024,
            timestamp="2024-01-01T12:00:00",
            tags=["v1.0", "release"],
        )
        assert "v1.0" in ver.tags
        assert "release" in ver.tags

    def test_version_serialization(self):
        """Test version to_dict and from_dict."""
        ver = DesignVersion(
            version_id="abc123",
            design_id="design1",
            version_number=1,
            message="Test",
            file_hash="hash123",
            file_size=1024,
            timestamp="2024-01-01T12:00:00",
            branch="main",
            tags=["test"],
            metadata={"key": "value"},
        )

        d = ver.to_dict()
        assert d["version_id"] == "abc123"
        assert d["metadata"] == {"key": "value"}

        restored = DesignVersion.from_dict(d)
        assert restored.version_id == ver.version_id
        assert restored.metadata == ver.metadata


class TestVersionHistory:
    """Tests for VersionHistory class."""

    @pytest.fixture
    def temp_history(self, tmp_path):
        """Create a temporary version history."""
        storage_dir = tmp_path / "versions"
        return VersionHistory(storage_dir)

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_file.write_text("solid test\nendsolid test")
        return str(stl_file)

    @pytest.fixture
    def temp_stl_modified(self, tmp_path):
        """Create a modified test STL file."""
        stl_file = tmp_path / "test_modified.stl"
        stl_file.write_text("solid test\n  facet normal 0 0 1\nendsolid test")
        return str(stl_file)

    def test_register_design(self, temp_history, temp_stl):
        """Test registering a new design."""
        design_id = temp_history.register_design(temp_stl, "Test Design")

        assert design_id is not None
        assert len(design_id) == 8

        design = temp_history.get_design(design_id)
        assert design["name"] == "Test Design"
        assert design["current_branch"] == "main"

    def test_save_version(self, temp_history, temp_stl):
        """Test saving a version."""
        ver = temp_history.save_version(temp_stl, "Initial version")

        assert ver.version_number == 1
        assert ver.message == "Initial version"
        assert ver.branch == "main"
        assert ver.file_hash is not None

    def test_save_version_auto_registers(self, temp_history, temp_stl):
        """Test that save_version auto-registers unknown files."""
        ver = temp_history.save_version(temp_stl, "Auto-registered")

        design = temp_history.get_design(ver.design_id)
        assert design is not None

    def test_save_multiple_versions(self, temp_history, tmp_path):
        """Test saving multiple versions."""
        stl_file = tmp_path / "multi.stl"

        # Version 1
        stl_file.write_text("solid v1\nendsolid v1")
        ver1 = temp_history.save_version(str(stl_file), "Version 1")

        # Version 2
        stl_file.write_text("solid v2\nendsolid v2")
        ver2 = temp_history.save_version(str(stl_file), "Version 2")

        # Version 3
        stl_file.write_text("solid v3\nendsolid v3")
        ver3 = temp_history.save_version(str(stl_file), "Version 3")

        assert ver1.version_number == 1
        assert ver2.version_number == 2
        assert ver3.version_number == 3
        assert ver2.parent_id == ver1.version_id
        assert ver3.parent_id == ver2.version_id

    def test_save_unchanged_file(self, temp_history, temp_stl):
        """Test saving unchanged file returns existing version."""
        ver1 = temp_history.save_version(temp_stl, "First save")
        ver2 = temp_history.save_version(temp_stl, "Second save")

        # Should return same version since file unchanged
        assert ver1.version_id == ver2.version_id

    def test_get_version(self, temp_history, temp_stl):
        """Test getting a specific version."""
        ver = temp_history.save_version(temp_stl, "Test")

        retrieved = temp_history.get_version(ver.version_id)
        assert retrieved is not None
        assert retrieved.version_id == ver.version_id

    def test_get_nonexistent_version(self, temp_history):
        """Test getting a version that doesn't exist."""
        ver = temp_history.get_version("nonexistent")
        assert ver is None

    def test_get_versions(self, temp_history, tmp_path):
        """Test getting all versions of a design."""
        stl_file = tmp_path / "versioned.stl"

        stl_file.write_text("v1")
        ver1 = temp_history.save_version(str(stl_file), "V1")

        stl_file.write_text("v2")
        ver2 = temp_history.save_version(str(stl_file), "V2")

        versions = temp_history.get_versions(ver1.design_id)
        assert len(versions) == 2
        # Newest first
        assert versions[0].version_number == 2
        assert versions[1].version_number == 1

    def test_get_latest(self, temp_history, tmp_path):
        """Test getting the latest version."""
        stl_file = tmp_path / "latest.stl"

        stl_file.write_text("v1")
        temp_history.save_version(str(stl_file), "V1")

        stl_file.write_text("v2")
        ver2 = temp_history.save_version(str(stl_file), "V2")

        latest = temp_history.get_latest(ver2.design_id)
        assert latest.version_number == 2

    def test_restore_version(self, temp_history, tmp_path):
        """Test restoring a version."""
        stl_file = tmp_path / "restore.stl"
        output_file = tmp_path / "restored.stl"

        # Save original
        stl_file.write_text("original content")
        ver1 = temp_history.save_version(str(stl_file), "Original")

        # Modify file
        stl_file.write_text("modified content")
        temp_history.save_version(str(stl_file), "Modified")

        # Restore original
        success = temp_history.restore_version(ver1.version_id, str(output_file))
        assert success

        # Verify content
        assert output_file.read_text() == "original content"

    def test_restore_nonexistent_version(self, temp_history, tmp_path):
        """Test restoring a version that doesn't exist."""
        output_file = tmp_path / "output.stl"
        success = temp_history.restore_version("nonexistent", str(output_file))
        assert not success

    def test_diff_versions(self, temp_history, tmp_path):
        """Test comparing two versions."""
        stl_file = tmp_path / "diff.stl"

        stl_file.write_text("small content")
        ver1 = temp_history.save_version(str(stl_file), "Small", metadata={"size": "small"})

        stl_file.write_text("larger content here with more data")
        ver2 = temp_history.save_version(str(stl_file), "Large", metadata={"size": "large"})

        diff = temp_history.diff_versions(ver1.version_id, ver2.version_id)

        assert diff is not None
        assert diff.file_changed
        assert diff.size_diff > 0  # File got bigger
        assert "size" in diff.metadata_changes

    def test_diff_identical_versions(self, temp_history, tmp_path):
        """Test diffing identical versions."""
        stl_file = tmp_path / "same.stl"
        stl_file.write_text("content")
        ver = temp_history.save_version(str(stl_file), "Test")

        diff = temp_history.diff_versions(ver.version_id, ver.version_id)
        assert diff is not None
        assert not diff.file_changed
        assert diff.size_diff == 0

    def test_diff_nonexistent_versions(self, temp_history):
        """Test diffing nonexistent versions."""
        diff = temp_history.diff_versions("a", "b")
        assert diff is None

    def test_create_branch(self, temp_history, temp_stl):
        """Test creating a branch."""
        ver = temp_history.save_version(temp_stl, "Main version")

        success = temp_history.create_branch(ver.design_id, "experimental")
        assert success

        design = temp_history.get_design(ver.design_id)
        assert design["current_branch"] == "experimental"

    def test_switch_branch(self, temp_history, temp_stl):
        """Test switching branches."""
        ver = temp_history.save_version(temp_stl, "Test")
        temp_history.create_branch(ver.design_id, "feature")

        success = temp_history.switch_branch(ver.design_id, "main")
        assert success

        design = temp_history.get_design(ver.design_id)
        assert design["current_branch"] == "main"

    def test_tag_version(self, temp_history, temp_stl):
        """Test tagging a version."""
        ver = temp_history.save_version(temp_stl, "Release")

        success = temp_history.tag_version(ver.version_id, "v1.0")
        assert success

        tagged = temp_history.get_version(ver.version_id)
        assert "v1.0" in tagged.tags

    def test_tag_version_no_duplicates(self, temp_history, temp_stl):
        """Test that duplicate tags are not added."""
        ver = temp_history.save_version(temp_stl, "Test")

        temp_history.tag_version(ver.version_id, "release")
        temp_history.tag_version(ver.version_id, "release")

        tagged = temp_history.get_version(ver.version_id)
        assert tagged.tags.count("release") == 1

    def test_get_version_by_tag(self, temp_history, tmp_path):
        """Test finding version by tag."""
        stl_file = tmp_path / "tagged.stl"

        stl_file.write_text("v1")
        ver1 = temp_history.save_version(str(stl_file), "V1")
        temp_history.tag_version(ver1.version_id, "alpha")

        stl_file.write_text("v2")
        ver2 = temp_history.save_version(str(stl_file), "V2")
        temp_history.tag_version(ver2.version_id, "beta")

        found = temp_history.get_version_by_tag(ver1.design_id, "alpha")
        assert found is not None
        assert found.version_id == ver1.version_id

    def test_list_designs(self, temp_history, tmp_path):
        """Test listing all designs."""
        stl1 = tmp_path / "design1.stl"
        stl2 = tmp_path / "design2.stl"

        stl1.write_text("design 1")
        stl2.write_text("design 2")

        temp_history.save_version(str(stl1), "First design")
        temp_history.save_version(str(stl2), "Second design")

        designs = temp_history.list_designs()
        assert len(designs) == 2

    def test_get_design_by_path(self, temp_history, temp_stl):
        """Test finding design by file path."""
        ver = temp_history.save_version(temp_stl, "Test")

        found_id = temp_history.get_design_by_path(temp_stl)
        assert found_id == ver.design_id

    def test_get_design_by_path_not_found(self, temp_history):
        """Test finding design that doesn't exist."""
        found_id = temp_history.get_design_by_path("/nonexistent/file.stl")
        assert found_id is None

    def test_persistence(self, tmp_path):
        """Test version history persists across instances."""
        storage_dir = tmp_path / "persistent"
        stl_file = tmp_path / "persist.stl"
        stl_file.write_text("persistent content")

        # Create first instance and save
        history1 = VersionHistory(storage_dir)
        ver = history1.save_version(str(stl_file), "Persistent version")

        # Create second instance
        history2 = VersionHistory(storage_dir)

        # Should find the version
        loaded = history2.get_version(ver.version_id)
        assert loaded is not None
        assert loaded.message == "Persistent version"

    def test_get_versions_by_branch(self, temp_history, tmp_path):
        """Test filtering versions by branch."""
        stl_file = tmp_path / "branched.stl"

        # Main branch versions
        stl_file.write_text("main v1")
        ver1 = temp_history.save_version(str(stl_file), "Main 1")

        stl_file.write_text("main v2")
        temp_history.save_version(str(stl_file), "Main 2")

        # Create and switch to feature branch
        temp_history.create_branch(ver1.design_id, "feature")

        stl_file.write_text("feature v1")
        temp_history.save_version(str(stl_file), "Feature 1")

        # Get only main branch versions
        main_versions = temp_history.get_versions(ver1.design_id, branch="main")
        assert len(main_versions) == 2

        # Get only feature branch versions
        feature_versions = temp_history.get_versions(ver1.design_id, branch="feature")
        assert len(feature_versions) == 1

    def test_version_metadata(self, temp_history, temp_stl):
        """Test saving and retrieving metadata."""
        metadata = {
            "scale": 1.5,
            "units": "mm",
            "author": "test",
        }
        ver = temp_history.save_version(temp_stl, "With metadata", metadata=metadata)

        retrieved = temp_history.get_version(ver.version_id)
        assert retrieved.metadata == metadata


class TestVersionDiff:
    """Tests for VersionDiff class."""

    def test_diff_creation(self):
        """Test creating a version diff."""
        diff = VersionDiff(
            version_a="abc",
            version_b="def",
            size_diff=100,
            file_changed=True,
            metadata_changes={"key": ("old", "new")},
        )
        assert diff.version_a == "abc"
        assert diff.size_diff == 100
        assert diff.file_changed
        assert diff.metadata_changes["key"] == ("old", "new")
