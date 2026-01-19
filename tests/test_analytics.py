"""Tests for print analytics module."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta

from src.analytics.storage import AnalyticsStorage, create_storage
from src.analytics.tracker import (
    PrintTracker,
    PrintRecord,
    PrintOutcome,
    ActivePrint,
    track_print,
)
from src.analytics.reports import (
    AnalyticsReport,
    ReportPeriod,
    MaterialUsageReport,
    SuccessRateReport,
    CostReport,
    TimeReport,
    ReportGenerator,
    generate_report,
)


class TestPrintOutcome:
    """Tests for PrintOutcome enum."""

    def test_outcome_values(self):
        """Test outcome enum values."""
        assert PrintOutcome.SUCCESS.value == "success"
        assert PrintOutcome.FAILED.value == "failed"
        assert PrintOutcome.CANCELLED.value == "cancelled"
        assert PrintOutcome.UNKNOWN.value == "unknown"


class TestPrintRecord:
    """Tests for PrintRecord dataclass."""

    def test_create_record(self):
        """Test creating a print record."""
        record = PrintRecord(
            id="abc123",
            file_name="benchy.3mf",
            started_at="2024-01-01T12:00:00",
            outcome=PrintOutcome.SUCCESS,
        )

        assert record.id == "abc123"
        assert record.file_name == "benchy.3mf"
        assert record.outcome == PrintOutcome.SUCCESS

    def test_record_with_all_fields(self):
        """Test record with all fields."""
        record = PrintRecord(
            id="test",
            file_name="model.stl",
            started_at="2024-01-01T10:00:00",
            completed_at="2024-01-01T12:00:00",
            outcome=PrintOutcome.SUCCESS,
            duration_seconds=7200,
            layers_total=500,
            layers_completed=500,
            material_type="PLA",
            material_used_grams=45.5,
            material_cost=1.50,
            printer_id="printer1",
            notes="Test print",
            metadata={"color": "red"},
        )

        assert record.duration_seconds == 7200
        assert record.material_type == "PLA"
        assert record.metadata["color"] == "red"

    def test_record_to_dict(self):
        """Test record serialization."""
        record = PrintRecord(
            id="test",
            file_name="test.3mf",
            started_at="2024-01-01T12:00:00",
            outcome=PrintOutcome.FAILED,
        )

        d = record.to_dict()
        assert d["id"] == "test"
        assert d["file_name"] == "test.3mf"
        assert d["outcome"] == "failed"

    def test_record_from_dict(self):
        """Test record deserialization."""
        data = {
            "id": "xyz",
            "file_name": "model.3mf",
            "started_at": "2024-01-01T12:00:00",
            "outcome": "success",
            "material_type": "PETG",
        }

        record = PrintRecord.from_dict(data)
        assert record.id == "xyz"
        assert record.outcome == PrintOutcome.SUCCESS
        assert record.material_type == "PETG"


class TestAnalyticsStorage:
    """Tests for AnalyticsStorage class."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a storage instance with temp database."""
        db_path = str(tmp_path / "test_analytics.db")
        return AnalyticsStorage(db_path=db_path)

    def test_save_and_get_record(self, storage):
        """Test saving and retrieving a record."""
        record_data = {
            "id": "test123",
            "file_name": "test.3mf",
            "started_at": datetime.now().isoformat(),
            "outcome": "success",
        }

        storage.save_print_record(record_data)
        retrieved = storage.get_print_record("test123")

        assert retrieved is not None
        assert retrieved["id"] == "test123"
        assert retrieved["file_name"] == "test.3mf"

    def test_get_nonexistent_record(self, storage):
        """Test getting a nonexistent record."""
        result = storage.get_print_record("nonexistent")
        assert result is None

    def test_get_print_records_with_filters(self, storage):
        """Test getting records with filters."""
        # Add some records
        for i in range(5):
            storage.save_print_record({
                "id": f"rec{i}",
                "file_name": f"file{i}.3mf",
                "started_at": datetime.now().isoformat(),
                "outcome": "success" if i % 2 == 0 else "failed",
                "material_type": "PLA" if i < 3 else "PETG",
            })

        # Test outcome filter
        success_records = storage.get_print_records(outcome="success")
        assert len(success_records) == 3

        # Test material filter
        pla_records = storage.get_print_records(material_type="PLA")
        assert len(pla_records) == 3

        # Test limit
        limited = storage.get_print_records(limit=2)
        assert len(limited) == 2

    def test_log_material_usage(self, storage):
        """Test logging material usage."""
        storage.log_material_usage("PLA", 45.5, cost=1.50, print_id="print1")
        storage.log_material_usage("PLA", 30.0, cost=1.00, print_id="print2")
        storage.log_material_usage("PETG", 50.0, cost=2.00)

        usage = storage.get_material_usage()
        assert len(usage) == 3

    def test_get_material_usage_filtered(self, storage):
        """Test getting filtered material usage."""
        storage.log_material_usage("PLA", 45.5)
        storage.log_material_usage("PETG", 30.0)

        pla_usage = storage.get_material_usage(material_type="PLA")
        assert len(pla_usage) == 1
        assert pla_usage[0]["material_type"] == "PLA"

    def test_update_daily_stats(self, storage):
        """Test updating daily stats."""
        date = "2024-01-15"
        storage.update_daily_stats(date, prints_started=1)
        storage.update_daily_stats(date, prints_completed=1, print_time_seconds=3600)

        stats = storage.get_daily_stats()
        assert len(stats) == 1
        assert stats[0]["date"] == date
        assert stats[0]["prints_started"] == 1
        assert stats[0]["prints_completed"] == 1

    def test_get_aggregate_stats(self, storage):
        """Test getting aggregate statistics."""
        # Add some records
        for i in range(3):
            storage.save_print_record({
                "id": f"agg{i}",
                "file_name": f"file{i}.3mf",
                "started_at": datetime.now().isoformat(),
                "outcome": "success",
                "duration_seconds": 3600,
                "material_used_grams": 50.0,
                "material_cost": 2.0,
            })

        stats = storage.get_aggregate_stats()
        assert stats["total_prints"] == 3
        assert stats["successful_prints"] == 3
        assert stats["total_material_grams"] == 150.0

    def test_get_material_summary(self, storage):
        """Test getting material summary."""
        storage.log_material_usage("PLA", 100.0, cost=3.0)
        storage.log_material_usage("PLA", 50.0, cost=1.5)
        storage.log_material_usage("PETG", 75.0, cost=3.0)

        summary = storage.get_material_summary()
        assert len(summary) == 2

        pla_summary = next(s for s in summary if s["material_type"] == "PLA")
        assert pla_summary["total_grams"] == 150.0
        assert pla_summary["usage_count"] == 2

    def test_delete_print_record(self, storage):
        """Test deleting a record."""
        storage.save_print_record({
            "id": "delete_me",
            "file_name": "test.3mf",
            "started_at": datetime.now().isoformat(),
        })

        assert storage.delete_print_record("delete_me") is True
        assert storage.get_print_record("delete_me") is None

    def test_delete_nonexistent_record(self, storage):
        """Test deleting nonexistent record."""
        assert storage.delete_print_record("nonexistent") is False


class TestPrintTracker:
    """Tests for PrintTracker class."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a tracker with temp storage."""
        db_path = str(tmp_path / "tracker_test.db")
        storage = AnalyticsStorage(db_path=db_path)
        return PrintTracker(storage)

    def test_start_print(self, tracker):
        """Test starting a print."""
        record_id = tracker.start_print(
            file_name="test.3mf",
            material_type="PLA",
            layers_total=500,
        )

        assert record_id is not None
        assert tracker.active_count == 1
        assert tracker.is_active(record_id)

    def test_complete_print(self, tracker):
        """Test completing a print."""
        record_id = tracker.start_print(file_name="test.3mf")
        record = tracker.complete_print(
            record_id=record_id,
            outcome=PrintOutcome.SUCCESS,
            material_used_grams=45.5,
        )

        assert record is not None
        assert record.outcome == PrintOutcome.SUCCESS
        assert tracker.active_count == 0

    def test_fail_print(self, tracker):
        """Test failing a print."""
        record_id = tracker.start_print(file_name="test.3mf")
        record = tracker.fail_print(
            record_id=record_id,
            notes="Spaghetti detected",
            layers_completed=100,
        )

        assert record.outcome == PrintOutcome.FAILED
        assert record.notes == "Spaghetti detected"

    def test_cancel_print(self, tracker):
        """Test cancelling a print."""
        record_id = tracker.start_print(file_name="test.3mf")
        record = tracker.cancel_print(record_id, notes="User cancelled")

        assert record.outcome == PrintOutcome.CANCELLED

    def test_get_record(self, tracker):
        """Test getting a record."""
        record_id = tracker.start_print(file_name="test.3mf")
        tracker.complete_print(record_id)

        record = tracker.get_record(record_id)
        assert record is not None
        assert record.id == record_id

    def test_get_records(self, tracker):
        """Test getting multiple records."""
        for i in range(3):
            record_id = tracker.start_print(file_name=f"test{i}.3mf")
            tracker.complete_print(record_id)

        records = tracker.get_records(limit=10)
        assert len(records) == 3

    def test_get_stats(self, tracker):
        """Test getting statistics."""
        for i in range(5):
            record_id = tracker.start_print(
                file_name=f"test{i}.3mf",
                material_type="PLA",
            )
            outcome = PrintOutcome.SUCCESS if i < 4 else PrintOutcome.FAILED
            tracker.complete_print(
                record_id,
                outcome=outcome,
                material_used_grams=50.0,
            )

        stats = tracker.get_stats()
        assert stats["total_prints"] == 5
        assert stats["success_rate"] == 80.0

    def test_completion_callback(self, tracker):
        """Test completion callback."""
        callback_called = [False]
        received_record = [None]

        def on_complete(record):
            callback_called[0] = True
            received_record[0] = record

        tracker.register_completion_callback(on_complete)
        record_id = tracker.start_print(file_name="test.3mf")
        tracker.complete_print(record_id)

        assert callback_called[0] is True
        assert received_record[0] is not None


class TestReportPeriod:
    """Tests for ReportPeriod enum."""

    def test_period_values(self):
        """Test period enum values."""
        assert ReportPeriod.DAY.value == "day"
        assert ReportPeriod.WEEK.value == "week"
        assert ReportPeriod.MONTH.value == "month"
        assert ReportPeriod.QUARTER.value == "quarter"
        assert ReportPeriod.YEAR.value == "year"
        assert ReportPeriod.ALL_TIME.value == "all_time"


class TestMaterialUsageReport:
    """Tests for MaterialUsageReport."""

    def test_create_report(self):
        """Test creating a material usage report."""
        report = MaterialUsageReport(
            material_type="PLA",
            total_grams=500.0,
            total_cost=15.0,
            usage_count=10,
            avg_per_print=50.0,
        )

        assert report.material_type == "PLA"
        assert report.total_grams == 500.0

    def test_report_to_dict(self):
        """Test report serialization."""
        report = MaterialUsageReport(
            material_type="PETG",
            total_grams=300.0,
            total_cost=12.0,
            usage_count=5,
            avg_per_print=60.0,
        )

        d = report.to_dict()
        assert d["material_type"] == "PETG"
        assert d["total_grams"] == 300.0


class TestSuccessRateReport:
    """Tests for SuccessRateReport."""

    def test_create_report(self):
        """Test creating a success rate report."""
        report = SuccessRateReport(
            total_prints=100,
            successful=85,
            failed=10,
            cancelled=5,
            success_rate=85.0,
            failure_rate=10.0,
        )

        assert report.total_prints == 100
        assert report.success_rate == 85.0


class TestCostReport:
    """Tests for CostReport."""

    def test_create_report(self):
        """Test creating a cost report."""
        report = CostReport(
            total_cost=150.0,
            avg_cost_per_print=3.0,
            cost_by_material={"PLA": 100.0, "PETG": 50.0},
            cost_trend=[],
        )

        assert report.total_cost == 150.0
        assert report.cost_by_material["PLA"] == 100.0


class TestTimeReport:
    """Tests for TimeReport."""

    def test_create_report(self):
        """Test creating a time report."""
        report = TimeReport(
            total_print_time_hours=50.0,
            avg_print_time_hours=2.5,
            longest_print_hours=8.0,
            shortest_print_hours=0.5,
            prints_by_day={"Monday": 5, "Tuesday": 3},
        )

        assert report.total_print_time_hours == 50.0
        assert report.prints_by_day["Monday"] == 5


class TestReportGenerator:
    """Tests for ReportGenerator."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create a generator with temp storage."""
        db_path = str(tmp_path / "report_test.db")
        storage = AnalyticsStorage(db_path=db_path)
        return ReportGenerator(storage)

    def test_generate_empty_report(self, generator):
        """Test generating report with no data."""
        report = generator.generate_report(ReportPeriod.MONTH)

        assert isinstance(report, AnalyticsReport)
        assert report.total_prints == 0

    def test_generate_success_rate_report(self, generator):
        """Test generating success rate report."""
        # Add some data
        for i in range(5):
            generator.storage.save_print_record({
                "id": f"sr{i}",
                "file_name": f"file{i}.3mf",
                "started_at": datetime.now().isoformat(),
                "outcome": "success" if i < 4 else "failed",
            })

        report = generator.generate_success_rate_report()
        assert report.total_prints == 5
        assert report.successful == 4
        assert report.failed == 1
        assert report.success_rate == 80.0

    def test_generate_material_usage_reports(self, generator):
        """Test generating material usage reports."""
        generator.storage.log_material_usage("PLA", 100.0, cost=3.0)
        generator.storage.log_material_usage("PETG", 50.0, cost=2.0)

        reports = generator.generate_material_usage_reports()
        assert len(reports) == 2

    def test_generate_full_report(self, generator):
        """Test generating full report."""
        # Add some comprehensive data
        for i in range(3):
            generator.storage.save_print_record({
                "id": f"full{i}",
                "file_name": f"model{i}.3mf",
                "started_at": datetime.now().isoformat(),
                "outcome": "success",
                "duration_seconds": 3600,
                "material_used_grams": 50.0,
                "material_cost": 2.0,
            })
            generator.storage.log_material_usage("PLA", 50.0, cost=2.0, print_id=f"full{i}")

        report = generator.generate_report(ReportPeriod.MONTH)

        assert report.total_prints == 3
        assert report.success_rate is not None
        assert len(report.material_usage) > 0


class TestAnalyticsReport:
    """Tests for AnalyticsReport."""

    def test_report_to_dict(self):
        """Test report serialization."""
        report = AnalyticsReport(
            period=ReportPeriod.MONTH,
            start_date="2024-01-01",
            end_date="2024-01-31",
            generated_at=datetime.now().isoformat(),
            total_prints=50,
            total_material_grams=2500.0,
            total_cost=75.0,
            total_print_hours=100.0,
        )

        d = report.to_dict()
        assert d["period"] == "month"
        assert d["summary"]["total_prints"] == 50


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_track_print(self, tmp_path):
        """Test track_print function."""
        # Create a temp file
        file_path = tmp_path / "test.3mf"
        file_path.write_text("test")

        tracker = track_print(
            file_path=str(file_path),
            material_type="PLA",
            layers_total=500,
        )

        assert tracker.active_count == 1

    def test_generate_report_function(self, tmp_path, monkeypatch):
        """Test generate_report convenience function."""
        db_path = str(tmp_path / "conv_test.db")

        # Patch the create_storage to use temp path
        import src.analytics.reports as reports_module

        def mock_create_storage():
            return AnalyticsStorage(db_path=db_path)

        monkeypatch.setattr(reports_module, "create_storage", mock_create_storage)

        report = generate_report(ReportPeriod.WEEK)
        assert isinstance(report, AnalyticsReport)


class TestCreateStorage:
    """Tests for create_storage function."""

    def test_create_with_path(self, tmp_path):
        """Test creating storage with explicit path."""
        db_path = str(tmp_path / "explicit.db")
        storage = create_storage(db_path)

        assert storage.db_path == db_path


class TestIntegration:
    """Integration tests for analytics workflow."""

    def test_full_analytics_workflow(self, tmp_path):
        """Test complete analytics workflow."""
        db_path = str(tmp_path / "integration.db")
        storage = AnalyticsStorage(db_path=db_path)
        tracker = PrintTracker(storage)

        # Start and complete several prints
        for i in range(5):
            record_id = tracker.start_print(
                file_name=f"model{i}.3mf",
                material_type="PLA" if i < 3 else "PETG",
                layers_total=500,
            )

            outcome = PrintOutcome.SUCCESS if i < 4 else PrintOutcome.FAILED
            tracker.complete_print(
                record_id=record_id,
                outcome=outcome,
                material_used_grams=50.0 + i * 10,
                material_cost=2.0 + i * 0.5,
            )

        # Generate reports
        generator = ReportGenerator(storage)
        report = generator.generate_report(ReportPeriod.MONTH)

        assert report.total_prints == 5
        assert report.success_rate.success_rate == 80.0
        assert len(report.material_usage) >= 0
