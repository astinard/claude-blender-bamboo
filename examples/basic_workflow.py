#!/usr/bin/env python3
"""
Basic workflow example.

Demonstrates creating a model and sending to printer (mock).
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pipeline.workflow import PrintWorkflow, WorkflowConfig, WorkflowStage
from src.printer import PrinterStatus


def progress_callback(stage: WorkflowStage, message: str):
    """Print workflow progress."""
    print(f"[{stage.value.upper()}] {message}")


def status_callback(status: PrinterStatus):
    """Print printer status updates."""
    if status.progress > 0:
        print(f"  Progress: {status.progress:.1f}% | "
              f"Bed: {status.bed_temp:.0f}°C | "
              f"Nozzle: {status.nozzle_temp:.0f}°C")


def main():
    """Run basic workflow example."""
    print("=" * 50)
    print("Blender + Bamboo Labs Basic Workflow Example")
    print("=" * 50)

    # Configure workflow
    config = WorkflowConfig(
        model_type="cube",
        model_params={"size": 20},  # 20mm cube
        export_format="stl",
        output_name="example_cube",
        use_mock_printer=True,  # Use mock for testing
        auto_start_print=True,
        monitor_print=True,
    )

    print(f"\nConfiguration:")
    print(f"  Model: {config.model_type}")
    print(f"  Size: {config.model_params.get('size', 'default')}mm")
    print(f"  Format: {config.export_format}")
    print(f"  Mock printer: {config.use_mock_printer}")
    print()

    # Create workflow
    workflow = PrintWorkflow(config, progress_callback)

    try:
        # Run full workflow
        result = workflow.run_full_workflow()

        print("\n" + "=" * 50)
        if result.success:
            print("SUCCESS!")
            if result.output_path:
                print(f"Output file: {result.output_path}")
        else:
            print(f"FAILED: {result.message}")

    finally:
        workflow.cleanup()


if __name__ == "__main__":
    main()
