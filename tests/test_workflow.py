"""Tests for hybrid workflow module."""

import pytest

from src.workflow.hybrid_ops import (
    HybridWorkflow,
    WorkflowConfig,
    WorkflowStep,
    WorkflowResult,
    StepType,
    StepStatus,
    create_workflow,
    run_workflow,
)


class TestStepType:
    """Tests for StepType enum."""

    def test_step_type_values(self):
        """Test step type values."""
        assert StepType.PRINT_3D.value == "print_3d"
        assert StepType.CNC_MILL.value == "cnc_mill"
        assert StepType.LASER_CUT.value == "laser_cut"
        assert StepType.ASSEMBLY.value == "assembly"


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.IN_PROGRESS.value == "in_progress"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"


class TestWorkflowStep:
    """Tests for WorkflowStep dataclass."""

    def test_create_step(self):
        """Test creating a step."""
        step = WorkflowStep(
            name="Print Base",
            step_type=StepType.PRINT_3D,
            description="Print the base component",
            estimated_time_minutes=120,
        )

        assert step.name == "Print Base"
        assert step.step_type == StepType.PRINT_3D
        assert step.status == StepStatus.PENDING

    def test_default_values(self):
        """Test default step values."""
        step = WorkflowStep("Step", StepType.CUSTOM)

        assert step.dependencies == []
        assert step.parameters == {}
        assert step.result is None

    def test_to_dict(self):
        """Test step serialization."""
        step = WorkflowStep("Test", StepType.ASSEMBLY)
        d = step.to_dict()

        assert d["name"] == "Test"
        assert d["step_type"] == "assembly"


class TestWorkflowConfig:
    """Tests for WorkflowConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = WorkflowConfig()

        assert config.name == "Hybrid Workflow"
        assert config.stop_on_failure is True
        assert config.parallel_execution is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = WorkflowConfig(
            name="Custom Workflow",
            stop_on_failure=False,
        )

        assert config.name == "Custom Workflow"
        assert config.stop_on_failure is False

    def test_to_dict(self):
        """Test config serialization."""
        config = WorkflowConfig(name="Test")
        d = config.to_dict()

        assert d["name"] == "Test"


class TestWorkflowResult:
    """Tests for WorkflowResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = WorkflowResult(
            success=True,
            workflow_name="Test",
            steps_completed=3,
            total_steps=3,
        )

        assert result.success is True
        assert result.steps_completed == 3

    def test_failure_result(self):
        """Test failure result."""
        result = WorkflowResult(
            success=False,
            error_message="Step failed",
        )

        assert result.success is False
        assert result.error_message == "Step failed"

    def test_to_dict(self):
        """Test result serialization."""
        result = WorkflowResult(success=True)
        d = result.to_dict()

        assert d["success"] is True


class TestHybridWorkflow:
    """Tests for HybridWorkflow class."""

    @pytest.fixture
    def workflow(self):
        """Create a hybrid workflow."""
        return HybridWorkflow()

    def test_init(self, workflow):
        """Test workflow initialization."""
        assert workflow.config is not None
        assert len(workflow.steps) == 0

    def test_init_custom_config(self):
        """Test workflow with custom config."""
        config = WorkflowConfig(name="Custom")
        workflow = HybridWorkflow(config=config)

        assert workflow.config.name == "Custom"


class TestStepManagement:
    """Tests for step management."""

    @pytest.fixture
    def workflow(self):
        """Create a hybrid workflow."""
        return HybridWorkflow()

    def test_add_step(self, workflow):
        """Test adding a step."""
        step = workflow.add_step(
            name="Print",
            step_type=StepType.PRINT_3D,
            description="Print the part",
            estimated_time=60,
        )

        assert len(workflow.steps) == 1
        assert step.name == "Print"

    def test_add_multiple_steps(self, workflow):
        """Test adding multiple steps."""
        workflow.add_step("Step 1", StepType.PRINT_3D)
        workflow.add_step("Step 2", StepType.ASSEMBLY)
        workflow.add_step("Step 3", StepType.INSPECTION)

        assert len(workflow.steps) == 3

    def test_remove_step(self, workflow):
        """Test removing a step."""
        workflow.add_step("Remove Me", StepType.CUSTOM)
        result = workflow.remove_step("Remove Me")

        assert result is True
        assert len(workflow.steps) == 0

    def test_remove_nonexistent_step(self, workflow):
        """Test removing non-existent step."""
        result = workflow.remove_step("Not Found")
        assert result is False

    def test_get_step(self, workflow):
        """Test getting a step by name."""
        workflow.add_step("Find Me", StepType.PRINT_3D)
        step = workflow.get_step("Find Me")

        assert step is not None
        assert step.name == "Find Me"

    def test_get_nonexistent_step(self, workflow):
        """Test getting non-existent step."""
        step = workflow.get_step("Not Found")
        assert step is None


class TestValidation:
    """Tests for workflow validation."""

    @pytest.fixture
    def workflow(self):
        """Create a hybrid workflow."""
        return HybridWorkflow()

    def test_validate_empty(self, workflow):
        """Test validating empty workflow."""
        errors = workflow.validate()
        assert "no steps" in errors[0].lower()

    def test_validate_valid_workflow(self, workflow):
        """Test validating valid workflow."""
        workflow.add_step("Step 1", StepType.PRINT_3D)
        workflow.add_step("Step 2", StepType.ASSEMBLY, dependencies=["Step 1"])

        errors = workflow.validate()
        assert len(errors) == 0

    def test_validate_duplicate_names(self, workflow):
        """Test duplicate step names."""
        workflow.add_step("Same Name", StepType.PRINT_3D)
        workflow.add_step("Same Name", StepType.ASSEMBLY)

        errors = workflow.validate()
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_missing_dependency(self, workflow):
        """Test missing dependency."""
        workflow.add_step("Step", StepType.PRINT_3D, dependencies=["Missing"])

        errors = workflow.validate()
        assert any("non-existent" in e.lower() for e in errors)

    def test_validate_circular_dependency(self, workflow):
        """Test circular dependencies."""
        workflow.add_step("A", StepType.PRINT_3D, dependencies=["B"])
        workflow.add_step("B", StepType.ASSEMBLY, dependencies=["A"])

        errors = workflow.validate()
        assert any("circular" in e.lower() for e in errors)


class TestExecution:
    """Tests for workflow execution."""

    @pytest.fixture
    def workflow(self):
        """Create a hybrid workflow."""
        return HybridWorkflow()

    def test_run_empty_workflow(self, workflow):
        """Test running empty workflow."""
        result = workflow.run()

        assert result.success is False
        assert "no steps" in result.error_message.lower()

    def test_run_simple_workflow(self, workflow):
        """Test running simple workflow."""
        workflow.add_step("Print", StepType.PRINT_3D, estimated_time=60)
        workflow.add_step("Finish", StepType.FINISHING, estimated_time=30)

        result = workflow.run(dry_run=True)

        assert result.success is True
        assert result.steps_completed == 2

    def test_run_with_dependencies(self, workflow):
        """Test running workflow with dependencies."""
        workflow.add_step("Print", StepType.PRINT_3D)
        workflow.add_step("Sand", StepType.FINISHING, dependencies=["Print"])
        workflow.add_step("Paint", StepType.FINISHING, dependencies=["Sand"])

        result = workflow.run(dry_run=True)

        assert result.success is True
        assert result.steps_completed == 3

    def test_run_with_handler(self, workflow):
        """Test running with custom handler."""
        workflow.add_step("Custom", StepType.CUSTOM)

        def handler(step):
            return {"handled": True}

        workflow.register_handler(StepType.CUSTOM, handler)
        result = workflow.run()

        assert result.success is True
        step = workflow.get_step("Custom")
        assert step.result == {"handled": True}


class TestStatus:
    """Tests for workflow status."""

    @pytest.fixture
    def workflow(self):
        """Create a hybrid workflow."""
        wf = HybridWorkflow()
        wf.add_step("Step 1", StepType.PRINT_3D)
        wf.add_step("Step 2", StepType.ASSEMBLY)
        return wf

    def test_get_status_initial(self, workflow):
        """Test initial status."""
        status = workflow.get_status()

        assert status["total_steps"] == 2
        assert status["pending"] == 2
        assert status["completed"] == 0

    def test_get_status_after_run(self, workflow):
        """Test status after running."""
        workflow.run(dry_run=True)
        status = workflow.get_status()

        assert status["completed"] == 2
        assert status["progress_percent"] == 100.0


class TestReset:
    """Tests for workflow reset."""

    @pytest.fixture
    def workflow(self):
        """Create and run a workflow."""
        wf = HybridWorkflow()
        wf.add_step("Step 1", StepType.PRINT_3D)
        wf.run(dry_run=True)
        return wf

    def test_reset_workflow(self, workflow):
        """Test resetting workflow."""
        workflow.reset()
        status = workflow.get_status()

        assert status["pending"] == 1
        assert status["completed"] == 0


class TestExport:
    """Tests for workflow export."""

    @pytest.fixture
    def workflow(self):
        """Create a workflow."""
        wf = HybridWorkflow(WorkflowConfig(name="Test Workflow"))
        wf.add_step("Print Base", StepType.PRINT_3D, estimated_time=60)
        wf.add_step("Add Components", StepType.ASSEMBLY, dependencies=["Print Base"])
        return wf

    def test_export_plan(self, workflow):
        """Test exporting workflow plan."""
        plan = workflow.export_plan()

        assert "Test Workflow" in plan
        assert "Print Base" in plan
        assert "Add Components" in plan


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_workflow(self):
        """Test create_workflow function."""
        workflow = create_workflow(
            name="My Workflow",
            description="Test description",
        )

        assert workflow.config.name == "My Workflow"
        assert workflow.config.description == "Test description"

    def test_run_workflow(self):
        """Test run_workflow function."""
        steps = [
            {"name": "Step 1", "type": "print_3d", "time": 30},
            {"name": "Step 2", "type": "assembly", "time": 15},
        ]

        result = run_workflow(steps, name="Quick Test")

        assert result.success is True
        assert result.steps_completed == 2


class TestIntegration:
    """Integration tests for hybrid workflow."""

    def test_full_workflow(self):
        """Test complete workflow execution."""
        # Create workflow
        workflow = create_workflow(
            name="Product Assembly",
            description="Complete product assembly process",
        )

        # Add steps
        workflow.add_step(
            "Print Base",
            StepType.PRINT_3D,
            description="Print the base component",
            estimated_time=120,
        )
        workflow.add_step(
            "Print Cover",
            StepType.PRINT_3D,
            description="Print the cover",
            estimated_time=90,
        )
        workflow.add_step(
            "Laser Cut Gasket",
            StepType.LASER_CUT,
            description="Cut rubber gasket",
            estimated_time=10,
        )
        workflow.add_step(
            "Assembly",
            StepType.ASSEMBLY,
            description="Assemble all components",
            estimated_time=30,
            dependencies=["Print Base", "Print Cover", "Laser Cut Gasket"],
        )
        workflow.add_step(
            "Inspection",
            StepType.INSPECTION,
            description="Quality check",
            estimated_time=15,
            dependencies=["Assembly"],
        )

        # Validate
        errors = workflow.validate()
        assert len(errors) == 0

        # Check initial status
        status = workflow.get_status()
        assert status["total_steps"] == 5
        assert status["pending"] == 5

        # Run workflow
        result = workflow.run(dry_run=True)
        assert result.success is True
        assert result.steps_completed == 5

        # Check final status
        status = workflow.get_status()
        assert status["completed"] == 5

        # Export plan
        plan = workflow.export_plan()
        assert "Product Assembly" in plan
        assert "[x]" in plan  # Completed markers
