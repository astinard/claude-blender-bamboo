"""
Pipeline workflow orchestrator.

Orchestrates the full workflow from model creation to printing:
1. Create/load 3D model in Blender
2. Validate and export for printing
3. Upload to printer
4. Start print job
5. Monitor progress
"""

import subprocess
import json
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import sys
import os

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config import (
    BLENDER_EXECUTABLE,
    OUTPUT_DIR,
    TEMP_DIR,
    DEFAULT_EXPORT_FORMAT,
    PRINTER_IP,
    PRINTER_ACCESS_CODE,
    PRINTER_SERIAL,
)
from src.printer import (
    BambooConnection,
    PrinterCommands,
    PrinterFileTransfer,
    PrinterStatus,
    PrinterState,
    MockPrinter,
    create_mock_printer,
)


class WorkflowStage(Enum):
    """Stages of the print workflow."""
    IDLE = "idle"
    MODELING = "modeling"
    EXPORTING = "exporting"
    VALIDATING = "validating"
    UPLOADING = "uploading"
    PRINTING = "printing"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowResult:
    """Result of a workflow operation."""
    success: bool
    message: str
    stage: WorkflowStage
    output_path: Optional[Path] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowConfig:
    """Configuration for a workflow run."""
    # Model settings
    model_type: str = "cube"  # cube, cylinder, sphere, cone, torus, custom
    model_params: Dict[str, Any] = field(default_factory=dict)
    custom_script: Optional[Path] = None  # For custom Blender scripts

    # Export settings
    export_format: str = "stl"
    output_name: str = "model"

    # Printer settings
    printer_ip: str = ""
    printer_access_code: str = ""
    printer_serial: str = ""
    use_mock_printer: bool = False

    # Workflow options
    auto_start_print: bool = False
    monitor_print: bool = True
    cleanup_temp_files: bool = True


class PrintWorkflow:
    """
    Main workflow orchestrator for the Blender-to-Bamboo pipeline.
    """

    def __init__(
        self,
        config: Optional[WorkflowConfig] = None,
        progress_callback: Optional[Callable[[WorkflowStage, str], None]] = None
    ):
        """
        Initialize workflow.

        Args:
            config: Workflow configuration
            progress_callback: Callback for progress updates
        """
        self.config = config or WorkflowConfig()
        self.progress_callback = progress_callback
        self.current_stage = WorkflowStage.IDLE

        # Set defaults from config module
        if not self.config.printer_ip:
            self.config.printer_ip = PRINTER_IP
        if not self.config.printer_access_code:
            self.config.printer_access_code = PRINTER_ACCESS_CODE
        if not self.config.printer_serial:
            self.config.printer_serial = PRINTER_SERIAL

        self._printer_conn: Optional[BambooConnection] = None
        self._mock_printer: Optional[MockPrinter] = None

    def _update_stage(self, stage: WorkflowStage, message: str = ""):
        """Update current stage and notify callback."""
        self.current_stage = stage
        if self.progress_callback:
            self.progress_callback(stage, message)

    def _run_blender(self, script_args: List[str]) -> Dict[str, Any]:
        """
        Run Blender with given script arguments.

        Returns:
            Parsed JSON result from Blender script
        """
        runner_path = project_root / "src" / "blender" / "runner.py"

        cmd = [
            BLENDER_EXECUTABLE,
            "--background",
            "--python", str(runner_path),
            "--"
        ] + script_args + ["--json-output"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            # Parse JSON output
            for line in result.stdout.split('\n'):
                if line.startswith('JSON_RESULT:'):
                    return json.loads(line[12:])

            # No JSON result found
            return {
                "success": False,
                "error": result.stderr or "No output from Blender",
                "stdout": result.stdout
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Blender execution timed out"}
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Blender not found at: {BLENDER_EXECUTABLE}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_model(self) -> WorkflowResult:
        """
        Create a 3D model based on configuration.

        Returns:
            WorkflowResult with model creation status
        """
        self._update_stage(WorkflowStage.MODELING, "Creating 3D model...")

        output_path = OUTPUT_DIR / f"{self.config.output_name}.{self.config.export_format}"

        # Build script arguments
        args = [
            "--action", f"create_{self.config.model_type}",
            "--output", str(output_path),
            "--format", self.config.export_format,
        ]

        # Add model-specific parameters
        params = self.config.model_params
        if "size" in params:
            args.extend(["--size", str(params["size"])])
        if "radius" in params:
            args.extend(["--radius", str(params["radius"])])
        if "height" in params:
            args.extend(["--height", str(params["height"])])

        result = self._run_blender(args)

        if result.get("success"):
            self._update_stage(WorkflowStage.EXPORTING, "Model created and exported")
            return WorkflowResult(
                success=True,
                message="Model created successfully",
                stage=WorkflowStage.EXPORTING,
                output_path=output_path,
                data=result
            )
        else:
            self._update_stage(WorkflowStage.FAILED, result.get("error", "Unknown error"))
            return WorkflowResult(
                success=False,
                message=result.get("error", "Model creation failed"),
                stage=WorkflowStage.FAILED,
                data=result
            )

    def validate_model(self, model_path: Path) -> WorkflowResult:
        """
        Validate a model file for 3D printing.

        Args:
            model_path: Path to the model file

        Returns:
            WorkflowResult with validation status
        """
        self._update_stage(WorkflowStage.VALIDATING, "Validating model...")

        if not model_path.exists():
            return WorkflowResult(
                success=False,
                message=f"Model file not found: {model_path}",
                stage=WorkflowStage.FAILED
            )

        # Check file size
        file_size = model_path.stat().st_size
        if file_size == 0:
            return WorkflowResult(
                success=False,
                message="Model file is empty",
                stage=WorkflowStage.FAILED
            )

        # For STL files, we could run additional validation through Blender
        # For now, basic validation
        return WorkflowResult(
            success=True,
            message="Model validation passed",
            stage=WorkflowStage.VALIDATING,
            output_path=model_path,
            data={"file_size": file_size}
        )

    def upload_to_printer(self, model_path: Path) -> WorkflowResult:
        """
        Upload model to printer.

        Args:
            model_path: Path to model file

        Returns:
            WorkflowResult with upload status
        """
        self._update_stage(WorkflowStage.UPLOADING, "Uploading to printer...")

        if self.config.use_mock_printer:
            # Mock upload
            time.sleep(1)  # Simulate upload time
            return WorkflowResult(
                success=True,
                message="Mock upload successful",
                stage=WorkflowStage.UPLOADING,
                output_path=model_path,
                data={"remote_path": f"/cache/{model_path.name}"}
            )

        try:
            transfer = PrinterFileTransfer(
                ip=self.config.printer_ip,
                access_code=self.config.printer_access_code
            )

            if not transfer.connect():
                return WorkflowResult(
                    success=False,
                    message="Failed to connect to printer for file transfer",
                    stage=WorkflowStage.FAILED
                )

            result = transfer.upload_file(model_path)
            transfer.disconnect()

            if result.success:
                return WorkflowResult(
                    success=True,
                    message="File uploaded successfully",
                    stage=WorkflowStage.UPLOADING,
                    output_path=model_path,
                    data={"remote_path": result.remote_path}
                )
            else:
                return WorkflowResult(
                    success=False,
                    message=result.message,
                    stage=WorkflowStage.FAILED
                )

        except Exception as e:
            return WorkflowResult(
                success=False,
                message=f"Upload error: {str(e)}",
                stage=WorkflowStage.FAILED
            )

    def start_print(self, filename: str) -> WorkflowResult:
        """
        Start a print job on the printer.

        Args:
            filename: Name of file to print (must already be on printer)

        Returns:
            WorkflowResult with print start status
        """
        self._update_stage(WorkflowStage.PRINTING, "Starting print...")

        if self.config.use_mock_printer:
            if self._mock_printer is None:
                self._mock_printer = create_mock_printer()
                self._mock_printer.connect()

            # Upload file to mock
            self._mock_printer.upload_file(filename)
            result = self._mock_printer.start_print(filename)

            if result.success:
                return WorkflowResult(
                    success=True,
                    message=f"Mock print started: {filename}",
                    stage=WorkflowStage.PRINTING
                )
            else:
                return WorkflowResult(
                    success=False,
                    message=result.message,
                    stage=WorkflowStage.FAILED
                )

        try:
            conn = BambooConnection(
                ip=self.config.printer_ip,
                access_code=self.config.printer_access_code,
                serial=self.config.printer_serial
            )

            if not conn.connect():
                return WorkflowResult(
                    success=False,
                    message="Failed to connect to printer",
                    stage=WorkflowStage.FAILED
                )

            self._printer_conn = conn
            commands = PrinterCommands(conn)

            result = commands.start_print(filename)

            if result.success:
                return WorkflowResult(
                    success=True,
                    message=f"Print started: {filename}",
                    stage=WorkflowStage.PRINTING
                )
            else:
                return WorkflowResult(
                    success=False,
                    message=result.message,
                    stage=WorkflowStage.FAILED
                )

        except Exception as e:
            return WorkflowResult(
                success=False,
                message=f"Print start error: {str(e)}",
                stage=WorkflowStage.FAILED
            )

    def monitor_print(
        self,
        status_callback: Optional[Callable[[PrinterStatus], None]] = None,
        poll_interval: float = 5.0
    ) -> WorkflowResult:
        """
        Monitor an active print job.

        Args:
            status_callback: Callback for status updates
            poll_interval: Seconds between status checks

        Returns:
            WorkflowResult when print completes or fails
        """
        self._update_stage(WorkflowStage.MONITORING, "Monitoring print...")

        if self.config.use_mock_printer and self._mock_printer:
            while True:
                status = self._mock_printer.status
                if status_callback:
                    status_callback(status)

                if status.state == PrinterState.FINISHED:
                    return WorkflowResult(
                        success=True,
                        message="Print completed successfully",
                        stage=WorkflowStage.COMPLETED
                    )
                elif status.state == PrinterState.ERROR:
                    return WorkflowResult(
                        success=False,
                        message=f"Print error: {status.error_message}",
                        stage=WorkflowStage.FAILED
                    )
                elif status.state == PrinterState.IDLE:
                    # Print was cancelled or stopped
                    return WorkflowResult(
                        success=False,
                        message="Print was stopped",
                        stage=WorkflowStage.FAILED
                    )

                time.sleep(poll_interval)

        if self._printer_conn and self._printer_conn.is_connected:
            while True:
                status = self._printer_conn.refresh_status()
                if status_callback:
                    status_callback(status)

                if status.state == PrinterState.FINISHED:
                    return WorkflowResult(
                        success=True,
                        message="Print completed successfully",
                        stage=WorkflowStage.COMPLETED
                    )
                elif status.state == PrinterState.ERROR:
                    return WorkflowResult(
                        success=False,
                        message=f"Print error: {status.error_message}",
                        stage=WorkflowStage.FAILED
                    )
                elif status.state == PrinterState.IDLE:
                    return WorkflowResult(
                        success=False,
                        message="Print was stopped or cancelled",
                        stage=WorkflowStage.FAILED
                    )

                time.sleep(poll_interval)

        return WorkflowResult(
            success=False,
            message="No printer connection for monitoring",
            stage=WorkflowStage.FAILED
        )

    def run_full_workflow(self) -> WorkflowResult:
        """
        Run the complete workflow from model creation to print completion.

        Returns:
            Final WorkflowResult
        """
        # Step 1: Create model
        result = self.create_model()
        if not result.success:
            return result

        model_path = result.output_path

        # Step 2: Validate
        result = self.validate_model(model_path)
        if not result.success:
            return result

        # Step 3: Upload
        result = self.upload_to_printer(model_path)
        if not result.success:
            return result

        # Step 4: Start print (if auto-start enabled)
        if self.config.auto_start_print:
            result = self.start_print(model_path.name)
            if not result.success:
                return result

            # Step 5: Monitor (if enabled)
            if self.config.monitor_print:
                result = self.monitor_print()

        self._update_stage(WorkflowStage.COMPLETED, "Workflow completed")
        return WorkflowResult(
            success=True,
            message="Workflow completed successfully",
            stage=WorkflowStage.COMPLETED,
            output_path=model_path
        )

    def cleanup(self):
        """Clean up resources."""
        if self._printer_conn:
            self._printer_conn.disconnect()
        if self._mock_printer:
            self._mock_printer.disconnect()

        if self.config.cleanup_temp_files:
            # Clean temp directory
            for f in TEMP_DIR.glob("*"):
                try:
                    f.unlink()
                except:
                    pass
