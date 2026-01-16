"""Tests for pipeline workflow module."""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline.workflow import (
    PrintWorkflow,
    WorkflowConfig,
    WorkflowStage,
    WorkflowResult,
)


class TestWorkflowConfig:
    """Tests for WorkflowConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WorkflowConfig()
        assert config.model_type == "cube"
        assert config.export_format == "stl"
        assert config.auto_start_print is False
        assert config.monitor_print is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = WorkflowConfig(
            model_type="sphere",
            model_params={"radius": 15},
            export_format="obj",
            use_mock_printer=True,
            auto_start_print=True
        )
        assert config.model_type == "sphere"
        assert config.model_params["radius"] == 15
        assert config.export_format == "obj"
        assert config.use_mock_printer is True


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = WorkflowResult(
            success=True,
            message="Test passed",
            stage=WorkflowStage.COMPLETED
        )
        assert result.success is True
        assert result.stage == WorkflowStage.COMPLETED

    def test_failure_result(self):
        """Test failure result."""
        result = WorkflowResult(
            success=False,
            message="Test failed",
            stage=WorkflowStage.FAILED
        )
        assert result.success is False
        assert result.stage == WorkflowStage.FAILED


class TestPrintWorkflow:
    """Tests for PrintWorkflow class."""

    def test_workflow_initialization(self):
        """Test workflow initialization."""
        config = WorkflowConfig(use_mock_printer=True)
        workflow = PrintWorkflow(config)
        assert workflow.current_stage == WorkflowStage.IDLE

    def test_workflow_with_progress_callback(self):
        """Test workflow with progress callback."""
        stages_seen = []

        def callback(stage, message):
            stages_seen.append(stage)

        config = WorkflowConfig(use_mock_printer=True)
        workflow = PrintWorkflow(config, progress_callback=callback)

        # This would require Blender to be installed
        # Just test that callback is set
        assert workflow.progress_callback is not None

    def test_validate_model_missing_file(self):
        """Test validation of missing file."""
        config = WorkflowConfig(use_mock_printer=True)
        workflow = PrintWorkflow(config)

        result = workflow.validate_model(Path("/nonexistent/file.stl"))
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_mock_upload(self):
        """Test mock upload functionality."""
        config = WorkflowConfig(use_mock_printer=True)
        workflow = PrintWorkflow(config)

        # Create a temporary test file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        try:
            result = workflow.upload_to_printer(temp_path)
            assert result.success is True
            assert "mock" in result.message.lower()
        finally:
            temp_path.unlink()

    def test_cleanup(self):
        """Test workflow cleanup."""
        config = WorkflowConfig(use_mock_printer=True)
        workflow = PrintWorkflow(config)
        # Should not raise
        workflow.cleanup()


class TestWorkflowStages:
    """Tests for WorkflowStage enum."""

    def test_all_stages_defined(self):
        """Test that all expected stages exist."""
        expected = [
            "IDLE", "MODELING", "EXPORTING", "VALIDATING",
            "UPLOADING", "PRINTING", "MONITORING", "COMPLETED", "FAILED"
        ]
        for stage_name in expected:
            assert hasattr(WorkflowStage, stage_name)

    def test_stage_values(self):
        """Test stage string values."""
        assert WorkflowStage.IDLE.value == "idle"
        assert WorkflowStage.PRINTING.value == "printing"
        assert WorkflowStage.COMPLETED.value == "completed"
        assert WorkflowStage.FAILED.value == "failed"
