"""Hybrid manufacturing operations workflow.

Combines 3D printing with other processes like CNC, laser cutting, etc.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Any

from src.utils import get_logger

logger = get_logger("workflow.hybrid_ops")


class StepType(str, Enum):
    """Types of workflow steps."""
    PRINT_3D = "print_3d"
    CNC_MILL = "cnc_mill"
    LASER_CUT = "laser_cut"
    ASSEMBLY = "assembly"
    FINISHING = "finishing"
    INSPECTION = "inspection"
    CUSTOM = "custom"


class StepStatus(str, Enum):
    """Status of a workflow step."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """A single step in the workflow."""
    name: str
    step_type: StepType
    description: str = ""
    estimated_time_minutes: int = 0
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "step_type": self.step_type.value,
            "description": self.description,
            "estimated_time_minutes": self.estimated_time_minutes,
            "dependencies": self.dependencies,
            "parameters": self.parameters,
            "status": self.status.value,
            "result": self.result,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class WorkflowConfig:
    """Configuration for hybrid workflow."""
    name: str = "Hybrid Workflow"
    description: str = ""
    parallel_execution: bool = False
    stop_on_failure: bool = True
    auto_save_state: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "parallel_execution": self.parallel_execution,
            "stop_on_failure": self.stop_on_failure,
            "auto_save_state": self.auto_save_state,
        }


@dataclass
class WorkflowResult:
    """Result of workflow execution."""
    success: bool
    workflow_name: str = ""
    steps_completed: int = 0
    steps_failed: int = 0
    steps_skipped: int = 0
    total_steps: int = 0
    total_time_minutes: float = 0.0
    step_results: Dict[str, Dict] = field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "workflow_name": self.workflow_name,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "steps_skipped": self.steps_skipped,
            "total_steps": self.total_steps,
            "total_time_minutes": self.total_time_minutes,
            "step_results": self.step_results,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class HybridWorkflow:
    """
    Hybrid manufacturing workflow manager.

    Coordinates multi-step manufacturing processes combining
    3D printing with other operations.
    """

    def __init__(self, config: Optional[WorkflowConfig] = None):
        """
        Initialize hybrid workflow.

        Args:
            config: Workflow configuration
        """
        self.config = config or WorkflowConfig()
        self.steps: List[WorkflowStep] = []
        self.step_handlers: Dict[StepType, Callable] = {}
        self._current_step_index: int = -1

    def add_step(
        self,
        name: str,
        step_type: StepType,
        description: str = "",
        estimated_time: int = 0,
        dependencies: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> WorkflowStep:
        """
        Add a step to the workflow.

        Args:
            name: Step name
            step_type: Type of step
            description: Step description
            estimated_time: Estimated time in minutes
            dependencies: List of step names this depends on
            parameters: Step parameters

        Returns:
            Created workflow step
        """
        step = WorkflowStep(
            name=name,
            step_type=step_type,
            description=description,
            estimated_time_minutes=estimated_time,
            dependencies=dependencies or [],
            parameters=parameters or {},
        )
        self.steps.append(step)
        return step

    def remove_step(self, name: str) -> bool:
        """Remove a step from the workflow."""
        for i, step in enumerate(self.steps):
            if step.name == name:
                self.steps.pop(i)
                return True
        return False

    def get_step(self, name: str) -> Optional[WorkflowStep]:
        """Get a step by name."""
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def register_handler(
        self,
        step_type: StepType,
        handler: Callable[[WorkflowStep], Dict[str, Any]],
    ) -> None:
        """
        Register a handler for a step type.

        Args:
            step_type: Step type to handle
            handler: Handler function (step) -> result dict
        """
        self.step_handlers[step_type] = handler

    def validate(self) -> List[str]:
        """
        Validate the workflow.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not self.steps:
            errors.append("Workflow has no steps")
            return errors

        # Check for duplicate names
        names = [s.name for s in self.steps]
        if len(names) != len(set(names)):
            errors.append("Duplicate step names found")

        # Check dependencies exist
        for step in self.steps:
            for dep in step.dependencies:
                if dep not in names:
                    errors.append(f"Step '{step.name}' depends on non-existent step '{dep}'")

        # Check for circular dependencies
        if self._has_circular_dependencies():
            errors.append("Circular dependencies detected")

        return errors

    def _has_circular_dependencies(self) -> bool:
        """Check for circular dependencies using DFS."""
        visited = set()
        rec_stack = set()

        def dfs(step_name: str) -> bool:
            visited.add(step_name)
            rec_stack.add(step_name)

            step = self.get_step(step_name)
            if step:
                for dep in step.dependencies:
                    if dep not in visited:
                        if dfs(dep):
                            return True
                    elif dep in rec_stack:
                        return True

            rec_stack.remove(step_name)
            return False

        for step in self.steps:
            if step.name not in visited:
                if dfs(step.name):
                    return True
        return False

    def _get_execution_order(self) -> List[WorkflowStep]:
        """Get steps in dependency-resolved order."""
        # Topological sort
        in_degree = {s.name: 0 for s in self.steps}
        for step in self.steps:
            for dep in step.dependencies:
                if dep in in_degree:
                    in_degree[step.name] += 1

        # Start with steps that have no dependencies
        queue = [s for s in self.steps if in_degree[s.name] == 0]
        result = []

        while queue:
            step = queue.pop(0)
            result.append(step)

            # Reduce in-degree for dependent steps
            for s in self.steps:
                if step.name in s.dependencies:
                    in_degree[s.name] -= 1
                    if in_degree[s.name] == 0:
                        queue.append(s)

        return result

    def run(self, dry_run: bool = False) -> WorkflowResult:
        """
        Execute the workflow.

        Args:
            dry_run: If True, simulate without executing

        Returns:
            Workflow result
        """
        start_time = datetime.now()

        # Validate first
        errors = self.validate()
        if errors:
            return WorkflowResult(
                success=False,
                workflow_name=self.config.name,
                error_message="; ".join(errors),
            )

        try:
            ordered_steps = self._get_execution_order()
            completed = 0
            failed = 0
            skipped = 0
            step_results = {}

            for step in ordered_steps:
                self._current_step_index = self.steps.index(step)

                # Check if dependencies completed successfully
                deps_ok = all(
                    self.get_step(dep).status == StepStatus.COMPLETED
                    for dep in step.dependencies
                )

                if not deps_ok:
                    step.status = StepStatus.SKIPPED
                    skipped += 1
                    continue

                # Execute step
                step.status = StepStatus.IN_PROGRESS
                step.started_at = datetime.now().isoformat()

                if dry_run:
                    # Simulate success
                    step.status = StepStatus.COMPLETED
                    step.result = {"dry_run": True}
                    completed += 1
                else:
                    # Execute with handler if available
                    handler = self.step_handlers.get(step.step_type)
                    if handler:
                        try:
                            result = handler(step)
                            step.result = result
                            step.status = StepStatus.COMPLETED
                            completed += 1
                        except Exception as e:
                            step.status = StepStatus.FAILED
                            step.error_message = str(e)
                            failed += 1

                            if self.config.stop_on_failure:
                                break
                    else:
                        # No handler, mark as completed (manual step)
                        step.status = StepStatus.COMPLETED
                        step.result = {"manual": True}
                        completed += 1

                step.completed_at = datetime.now().isoformat()
                step_results[step.name] = step.to_dict()

            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds() / 60

            return WorkflowResult(
                success=failed == 0,
                workflow_name=self.config.name,
                steps_completed=completed,
                steps_failed=failed,
                steps_skipped=skipped,
                total_steps=len(self.steps),
                total_time_minutes=round(total_time, 2),
                step_results=step_results,
                started_at=start_time.isoformat(),
                completed_at=end_time.isoformat(),
            )

        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            return WorkflowResult(
                success=False,
                workflow_name=self.config.name,
                error_message=str(e),
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current workflow status."""
        pending = sum(1 for s in self.steps if s.status == StepStatus.PENDING)
        in_progress = sum(1 for s in self.steps if s.status == StepStatus.IN_PROGRESS)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)

        return {
            "name": self.config.name,
            "total_steps": len(self.steps),
            "pending": pending,
            "in_progress": in_progress,
            "completed": completed,
            "failed": failed,
            "progress_percent": round((completed / len(self.steps)) * 100, 1) if self.steps else 0,
        }

    def reset(self) -> None:
        """Reset all steps to pending."""
        for step in self.steps:
            step.status = StepStatus.PENDING
            step.result = None
            step.error_message = None
            step.started_at = None
            step.completed_at = None
        self._current_step_index = -1

    def export_plan(self) -> str:
        """Export workflow as a text plan."""
        lines = [
            f"# {self.config.name}",
            "",
            f"*{self.config.description}*" if self.config.description else "",
            "",
            "## Steps",
            "",
        ]

        total_time = 0
        for i, step in enumerate(self.steps, 1):
            status_icon = {
                StepStatus.PENDING: "[ ]",
                StepStatus.IN_PROGRESS: "[~]",
                StepStatus.COMPLETED: "[x]",
                StepStatus.FAILED: "[!]",
                StepStatus.SKIPPED: "[-]",
            }.get(step.status, "[ ]")

            lines.append(f"{status_icon} **Step {i}: {step.name}** ({step.step_type.value})")
            if step.description:
                lines.append(f"    {step.description}")
            if step.estimated_time_minutes:
                lines.append(f"    Estimated: {step.estimated_time_minutes} min")
                total_time += step.estimated_time_minutes
            if step.dependencies:
                lines.append(f"    Depends on: {', '.join(step.dependencies)}")
            lines.append("")

        lines.extend([
            "## Summary",
            "",
            f"- Total steps: {len(self.steps)}",
            f"- Estimated time: {total_time} minutes",
        ])

        return "\n".join(lines)


# Convenience functions
def create_workflow(
    name: str = "Workflow",
    description: str = "",
) -> HybridWorkflow:
    """Create a hybrid workflow with specified settings."""
    config = WorkflowConfig(
        name=name,
        description=description,
    )
    return HybridWorkflow(config=config)


def run_workflow(
    steps: List[Dict[str, Any]],
    name: str = "Quick Workflow",
) -> WorkflowResult:
    """
    Quick workflow execution.

    Args:
        steps: List of step dictionaries
        name: Workflow name

    Returns:
        Workflow result
    """
    workflow = create_workflow(name=name)

    for step_data in steps:
        workflow.add_step(
            name=step_data.get("name", "Step"),
            step_type=StepType(step_data.get("type", "custom")),
            description=step_data.get("description", ""),
            estimated_time=step_data.get("time", 0),
            dependencies=step_data.get("dependencies", []),
            parameters=step_data.get("parameters", {}),
        )

    return workflow.run(dry_run=True)
