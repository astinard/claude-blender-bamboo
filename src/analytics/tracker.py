"""Print tracking for analytics.

Tracks print jobs and their outcomes for analytics and reporting.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from src.utils import get_logger
from src.analytics.storage import AnalyticsStorage, create_storage

logger = get_logger("analytics.tracker")


class PrintOutcome(str, Enum):
    """Possible outcomes for a print job."""
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class PrintRecord:
    """
    Record of a completed print job.

    Tracks all relevant information about a print for analytics.
    """

    id: str
    file_name: str
    started_at: str
    outcome: PrintOutcome = PrintOutcome.UNKNOWN

    # Optional fields
    file_path: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    layers_total: Optional[int] = None
    layers_completed: Optional[int] = None
    material_type: Optional[str] = None
    material_used_grams: Optional[float] = None
    material_cost: Optional[float] = None
    printer_id: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "outcome": self.outcome.value,
            "duration_seconds": self.duration_seconds,
            "layers_total": self.layers_total,
            "layers_completed": self.layers_completed,
            "material_type": self.material_type,
            "material_used_grams": self.material_used_grams,
            "material_cost": self.material_cost,
            "printer_id": self.printer_id,
            "notes": self.notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrintRecord":
        """Create from dictionary."""
        outcome = data.get("outcome", "unknown")
        if isinstance(outcome, str):
            outcome = PrintOutcome(outcome)

        return cls(
            id=data["id"],
            file_name=data["file_name"],
            file_path=data.get("file_path"),
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            outcome=outcome,
            duration_seconds=data.get("duration_seconds"),
            layers_total=data.get("layers_total"),
            layers_completed=data.get("layers_completed"),
            material_type=data.get("material_type"),
            material_used_grams=data.get("material_used_grams"),
            material_cost=data.get("material_cost"),
            printer_id=data.get("printer_id"),
            notes=data.get("notes"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ActivePrint:
    """An active print being tracked."""
    record_id: str
    file_name: str
    file_path: Optional[str]
    started_at: float  # Unix timestamp
    material_type: Optional[str]
    layers_total: Optional[int]
    printer_id: Optional[str]


class PrintTracker:
    """
    Tracks print jobs for analytics.

    Monitors print start/completion and records statistics.
    """

    def __init__(self, storage: Optional[AnalyticsStorage] = None):
        """
        Initialize print tracker.

        Args:
            storage: Analytics storage (created if not provided)
        """
        self.storage = storage or create_storage()
        self._active_prints: Dict[str, ActivePrint] = {}
        self._completion_callbacks: List[Callable[[PrintRecord], None]] = []

    @property
    def active_count(self) -> int:
        """Get number of active prints."""
        return len(self._active_prints)

    @property
    def active_prints(self) -> List[ActivePrint]:
        """Get list of active prints."""
        return list(self._active_prints.values())

    def start_print(
        self,
        file_name: str,
        file_path: Optional[str] = None,
        material_type: Optional[str] = None,
        layers_total: Optional[int] = None,
        printer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start tracking a print job.

        Args:
            file_name: Name of the file being printed
            file_path: Full path to the file
            material_type: Type of material used
            layers_total: Total number of layers
            printer_id: ID of the printer
            metadata: Additional metadata

        Returns:
            Record ID for tracking
        """
        record_id = str(uuid4())[:8]
        started_at = time.time()

        # Create active print
        active = ActivePrint(
            record_id=record_id,
            file_name=file_name,
            file_path=file_path,
            started_at=started_at,
            material_type=material_type,
            layers_total=layers_total,
            printer_id=printer_id,
        )
        self._active_prints[record_id] = active

        # Create initial record
        record = PrintRecord(
            id=record_id,
            file_name=file_name,
            file_path=file_path,
            started_at=datetime.fromtimestamp(started_at).isoformat(),
            material_type=material_type,
            layers_total=layers_total,
            printer_id=printer_id,
            metadata=metadata or {},
        )

        # Save to storage
        self.storage.save_print_record(record.to_dict())

        # Update daily stats
        date = datetime.fromtimestamp(started_at).strftime("%Y-%m-%d")
        self.storage.update_daily_stats(date, prints_started=1)

        logger.info(f"Started tracking print: {record_id} ({file_name})")
        return record_id

    def complete_print(
        self,
        record_id: str,
        outcome: PrintOutcome = PrintOutcome.SUCCESS,
        layers_completed: Optional[int] = None,
        material_used_grams: Optional[float] = None,
        material_cost: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> Optional[PrintRecord]:
        """
        Complete a tracked print.

        Args:
            record_id: Record ID from start_print
            outcome: Print outcome
            layers_completed: Number of layers completed
            material_used_grams: Material used in grams
            material_cost: Cost of material used
            notes: Additional notes

        Returns:
            Completed print record
        """
        if record_id not in self._active_prints:
            logger.warning(f"Print {record_id} not found in active prints")
            # Try to get from storage
            data = self.storage.get_print_record(record_id)
            if not data:
                return None

            record = PrintRecord.from_dict(data)
            record.outcome = outcome
            record.completed_at = datetime.now().isoformat()
            self.storage.save_print_record(record.to_dict())
            return record

        active = self._active_prints.pop(record_id)
        completed_at = time.time()
        duration = int(completed_at - active.started_at)

        # Create completed record
        record = PrintRecord(
            id=record_id,
            file_name=active.file_name,
            file_path=active.file_path,
            started_at=datetime.fromtimestamp(active.started_at).isoformat(),
            completed_at=datetime.fromtimestamp(completed_at).isoformat(),
            outcome=outcome,
            duration_seconds=duration,
            layers_total=active.layers_total,
            layers_completed=layers_completed or active.layers_total,
            material_type=active.material_type,
            material_used_grams=material_used_grams,
            material_cost=material_cost,
            printer_id=active.printer_id,
            notes=notes,
        )

        # Save to storage
        self.storage.save_print_record(record.to_dict())

        # Log material usage
        if material_used_grams and active.material_type:
            self.storage.log_material_usage(
                material_type=active.material_type,
                amount_grams=material_used_grams,
                cost=material_cost,
                print_id=record_id,
            )

        # Update daily stats
        date = datetime.fromtimestamp(completed_at).strftime("%Y-%m-%d")
        if outcome == PrintOutcome.SUCCESS:
            self.storage.update_daily_stats(
                date,
                prints_completed=1,
                print_time_seconds=duration,
                material_grams=material_used_grams or 0,
                cost=material_cost or 0,
            )
        elif outcome == PrintOutcome.FAILED:
            self.storage.update_daily_stats(date, prints_failed=1)

        # Notify callbacks
        for callback in self._completion_callbacks:
            try:
                callback(record)
            except Exception as e:
                logger.error(f"Completion callback error: {e}")

        logger.info(f"Completed print: {record_id} ({outcome.value})")
        return record

    def fail_print(
        self,
        record_id: str,
        notes: Optional[str] = None,
        layers_completed: Optional[int] = None,
    ) -> Optional[PrintRecord]:
        """
        Mark a print as failed.

        Args:
            record_id: Record ID
            notes: Failure notes
            layers_completed: Layers completed before failure

        Returns:
            Failed print record
        """
        return self.complete_print(
            record_id=record_id,
            outcome=PrintOutcome.FAILED,
            layers_completed=layers_completed,
            notes=notes,
        )

    def cancel_print(
        self,
        record_id: str,
        notes: Optional[str] = None,
        layers_completed: Optional[int] = None,
    ) -> Optional[PrintRecord]:
        """
        Mark a print as cancelled.

        Args:
            record_id: Record ID
            notes: Cancellation notes
            layers_completed: Layers completed before cancellation

        Returns:
            Cancelled print record
        """
        return self.complete_print(
            record_id=record_id,
            outcome=PrintOutcome.CANCELLED,
            layers_completed=layers_completed,
            notes=notes,
        )

    def get_record(self, record_id: str) -> Optional[PrintRecord]:
        """
        Get a print record.

        Args:
            record_id: Record ID

        Returns:
            Print record or None
        """
        data = self.storage.get_print_record(record_id)
        if data:
            return PrintRecord.from_dict(data)
        return None

    def get_records(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        outcome: Optional[PrintOutcome] = None,
        material_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[PrintRecord]:
        """
        Get print records with filters.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date
            outcome: Filter by outcome
            material_type: Filter by material type
            limit: Maximum records

        Returns:
            List of print records
        """
        records = self.storage.get_print_records(
            start_date=start_date,
            end_date=end_date,
            outcome=outcome.value if outcome else None,
            material_type=material_type,
            limit=limit,
        )
        return [PrintRecord.from_dict(r) for r in records]

    def get_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregate statistics.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Statistics dictionary
        """
        stats = self.storage.get_aggregate_stats(start_date, end_date)

        # Calculate success rate
        total = stats.get("total_prints", 0)
        successful = stats.get("successful_prints", 0)
        stats["success_rate"] = (successful / total * 100) if total > 0 else 0

        return stats

    def register_completion_callback(
        self,
        callback: Callable[[PrintRecord], None],
    ) -> None:
        """Register callback for print completion."""
        self._completion_callbacks.append(callback)

    def is_active(self, record_id: str) -> bool:
        """Check if a print is active."""
        return record_id in self._active_prints

    def get_active(self, record_id: str) -> Optional[ActivePrint]:
        """Get an active print."""
        return self._active_prints.get(record_id)


def track_print(
    file_path: str,
    material_type: Optional[str] = None,
    layers_total: Optional[int] = None,
    printer_id: Optional[str] = None,
) -> PrintTracker:
    """
    Convenience function to create a tracker and start tracking.

    Args:
        file_path: Path to file being printed
        material_type: Material type
        layers_total: Total layers
        printer_id: Printer ID

    Returns:
        PrintTracker with active print
    """
    tracker = PrintTracker()
    file_name = Path(file_path).name

    tracker.start_print(
        file_name=file_name,
        file_path=file_path,
        material_type=material_type,
        layers_total=layers_total,
        printer_id=printer_id,
    )

    return tracker
