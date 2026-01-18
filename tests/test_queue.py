"""Tests for print queue management."""

import pytest
from pathlib import Path

from src.queue.job_queue import (
    PrintJob,
    JobStatus,
    JobPriority,
    PrintQueue,
)
from src.queue.scheduler import (
    QueueScheduler,
    SchedulerConfig,
    SchedulingStrategy,
)


class TestPrintJob:
    """Tests for PrintJob class."""

    def test_create_job(self):
        """Test creating a print job."""
        job = PrintJob(
            id="test1",
            name="Test Job",
            file_path="/path/to/model.stl",
        )
        assert job.id == "test1"
        assert job.name == "Test Job"
        assert job.status == JobStatus.PENDING
        assert job.priority == JobPriority.NORMAL

    def test_job_lifecycle(self):
        """Test job state transitions."""
        job = PrintJob(id="test1", name="Test", file_path="test.stl")

        assert job.can_start
        assert not job.is_active
        assert not job.is_complete

        job.start()
        assert job.status == JobStatus.PRINTING
        assert job.is_active
        assert job.started_at is not None

        job.pause()
        assert job.status == JobStatus.PAUSED

        job.resume()
        assert job.status == JobStatus.PRINTING

        job.complete(success=True)
        assert job.status == JobStatus.COMPLETED
        assert job.is_complete
        assert job.completed_at is not None

    def test_job_progress(self):
        """Test updating job progress."""
        job = PrintJob(id="test1", name="Test", file_path="test.stl")
        job.start()

        job.update_progress(50, current_layer=100, total_layers=200)
        assert job.progress_percent == 50
        assert job.current_layer == 100
        assert job.total_layers == 200

    def test_job_cancel(self):
        """Test cancelling a job."""
        job = PrintJob(id="test1", name="Test", file_path="test.stl")
        job.start()
        job.cancel()

        assert job.status == JobStatus.CANCELLED
        assert job.is_complete

    def test_job_serialization(self):
        """Test job serialization to dict."""
        job = PrintJob(
            id="test1",
            name="Test",
            file_path="test.stl",
            priority=JobPriority.HIGH,
        )

        d = job.to_dict()
        assert d["id"] == "test1"
        assert d["priority"] == "high"

        restored = PrintJob.from_dict(d)
        assert restored.id == job.id
        assert restored.priority == job.priority

    def test_priority_values(self):
        """Test priority ordering."""
        assert JobPriority.LOW.value_int < JobPriority.NORMAL.value_int
        assert JobPriority.NORMAL.value_int < JobPriority.HIGH.value_int
        assert JobPriority.HIGH.value_int < JobPriority.URGENT.value_int


class TestPrintQueue:
    """Tests for PrintQueue class."""

    @pytest.fixture
    def temp_queue(self, tmp_path):
        """Create a temporary queue."""
        data_file = tmp_path / "test_queue.json"
        return PrintQueue(data_file)

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_file.write_text("solid test\nendsolid test")
        return str(stl_file)

    def test_add_job(self, temp_queue, temp_stl):
        """Test adding a job to the queue."""
        job = temp_queue.add_job(
            file_path=temp_stl,
            name="Test Job",
            priority=JobPriority.HIGH,
        )

        assert job.id is not None
        assert job.name == "Test Job"
        assert len(temp_queue) == 1

    def test_remove_job(self, temp_queue, temp_stl):
        """Test removing a job from the queue."""
        job = temp_queue.add_job(file_path=temp_stl)

        assert temp_queue.remove_job(job.id)
        assert len(temp_queue) == 0
        assert temp_queue.get_job(job.id) is None

    def test_priority_ordering(self, temp_queue, temp_stl):
        """Test jobs are ordered by priority."""
        job_low = temp_queue.add_job(file_path=temp_stl, name="Low", priority=JobPriority.LOW)
        job_high = temp_queue.add_job(file_path=temp_stl, name="High", priority=JobPriority.HIGH)
        job_normal = temp_queue.add_job(file_path=temp_stl, name="Normal", priority=JobPriority.NORMAL)

        jobs = temp_queue.list_all()
        assert jobs[0].id == job_high.id  # High priority first
        assert jobs[1].id == job_normal.id
        assert jobs[2].id == job_low.id

    def test_get_next_job(self, temp_queue, temp_stl):
        """Test getting next job to print."""
        temp_queue.add_job(file_path=temp_stl, name="Job 1")
        temp_queue.add_job(file_path=temp_stl, name="Job 2", priority=JobPriority.HIGH)

        next_job = temp_queue.get_next_job()
        assert next_job is not None
        assert next_job.name == "Job 2"  # High priority

    def test_job_dependencies(self, temp_queue, temp_stl):
        """Test job dependencies block execution."""
        job1 = temp_queue.add_job(file_path=temp_stl, name="Job 1")
        job2 = temp_queue.add_job(file_path=temp_stl, name="Job 2", depends_on=[job1.id])

        # Job 2 should not be ready until Job 1 completes
        next_job = temp_queue.get_next_job()
        assert next_job.id == job1.id

        # Complete job 1
        job1.complete(success=True)
        temp_queue._save()

        # Now job 2 should be available
        next_job = temp_queue.get_next_job()
        assert next_job.id == job2.id

    def test_move_to_top(self, temp_queue, temp_stl):
        """Test moving job to top of priority group."""
        job1 = temp_queue.add_job(file_path=temp_stl, name="Job 1")
        job2 = temp_queue.add_job(file_path=temp_stl, name="Job 2")
        job3 = temp_queue.add_job(file_path=temp_stl, name="Job 3")

        temp_queue.move_to_top(job3.id)

        jobs = temp_queue.list_all()
        assert jobs[0].id == job3.id

    def test_set_priority(self, temp_queue, temp_stl):
        """Test changing job priority."""
        job = temp_queue.add_job(file_path=temp_stl, priority=JobPriority.NORMAL)

        temp_queue.set_priority(job.id, JobPriority.URGENT)

        updated = temp_queue.get_job(job.id)
        assert updated.priority == JobPriority.URGENT

    def test_get_pending_jobs(self, temp_queue, temp_stl):
        """Test getting pending jobs."""
        job1 = temp_queue.add_job(file_path=temp_stl, name="Job 1")
        job2 = temp_queue.add_job(file_path=temp_stl, name="Job 2")

        job1.complete(success=True)
        temp_queue._save()

        pending = temp_queue.get_pending_jobs()
        assert len(pending) == 1
        assert pending[0].id == job2.id

    def test_clear_completed(self, temp_queue, temp_stl):
        """Test clearing completed jobs."""
        job1 = temp_queue.add_job(file_path=temp_stl)
        job2 = temp_queue.add_job(file_path=temp_stl)

        job1.complete(success=True)
        temp_queue._save()

        count = temp_queue.clear_completed()
        assert count == 1
        assert len(temp_queue) == 1

    def test_persistence(self, tmp_path, temp_stl):
        """Test queue persists across instances."""
        data_file = tmp_path / "persist_test.json"

        # Create queue and add job
        queue1 = PrintQueue(data_file)
        job = queue1.add_job(file_path=temp_stl, name="Persistent Job")

        # Create new queue instance
        queue2 = PrintQueue(data_file)
        loaded = queue2.get_job(job.id)

        assert loaded is not None
        assert loaded.name == "Persistent Job"


class TestQueueScheduler:
    """Tests for QueueScheduler class."""

    @pytest.fixture
    def temp_queue(self, tmp_path):
        """Create a temporary queue."""
        data_file = tmp_path / "test_queue.json"
        return PrintQueue(data_file)

    @pytest.fixture
    def temp_stl(self, tmp_path):
        """Create a test STL file."""
        stl_file = tmp_path / "test.stl"
        stl_file.write_text("solid test\nendsolid test")
        return str(stl_file)

    def test_start_scheduler(self, temp_queue, temp_stl):
        """Test starting the scheduler."""
        temp_queue.add_job(file_path=temp_stl)

        # Use non-mock mode to verify scheduler starts
        config = SchedulerConfig(mock_mode=False)
        scheduler = QueueScheduler(temp_queue, config)

        job = scheduler.start()
        assert job is not None
        # In non-mock mode, scheduler stays running until job completes
        assert scheduler.is_running or job.status == JobStatus.PRINTING

    def test_mock_mode_completes_jobs(self, temp_queue, temp_stl):
        """Test mock mode auto-completes jobs."""
        temp_queue.add_job(file_path=temp_stl)
        temp_queue.add_job(file_path=temp_stl)

        config = SchedulerConfig(mock_mode=True, auto_start_next=False)
        scheduler = QueueScheduler(temp_queue, config)

        job = scheduler.start()
        assert job.status == JobStatus.COMPLETED

    def test_job_callbacks(self, temp_queue, temp_stl):
        """Test scheduler callbacks."""
        started_jobs = []
        completed_jobs = []

        def on_start(job):
            started_jobs.append(job.id)

        def on_complete(job):
            completed_jobs.append(job.id)

        temp_queue.add_job(file_path=temp_stl)

        config = SchedulerConfig(mock_mode=True)
        scheduler = QueueScheduler(
            temp_queue,
            config,
            on_job_start=on_start,
            on_job_complete=on_complete,
        )

        scheduler.start()

        assert len(started_jobs) == 1
        assert len(completed_jobs) == 1

    def test_pause_resume(self, temp_queue, temp_stl):
        """Test pausing and resuming scheduler."""
        temp_queue.add_job(file_path=temp_stl)

        config = SchedulerConfig(mock_mode=False)  # Don't auto-complete
        scheduler = QueueScheduler(temp_queue, config)

        scheduler.start()
        assert scheduler.is_running

        scheduler.pause()
        assert scheduler.is_paused

        scheduler.resume()
        assert not scheduler.is_paused

    def test_get_status(self, temp_queue, temp_stl):
        """Test getting scheduler status."""
        temp_queue.add_job(file_path=temp_stl)

        scheduler = QueueScheduler(temp_queue, SchedulerConfig(mock_mode=True))
        scheduler.start()

        status = scheduler.get_status()
        assert "running" in status
        assert "jobs_completed" in status
        assert "strategy" in status

    def test_scheduling_strategies(self, temp_queue, temp_stl):
        """Test different scheduling strategies."""
        # Add jobs with different estimated times
        j1 = temp_queue.add_job(file_path=temp_stl, name="Long", estimated_time_seconds=3600)
        j2 = temp_queue.add_job(file_path=temp_stl, name="Short", estimated_time_seconds=600)

        # FIFO should return first added
        config_fifo = SchedulerConfig(strategy=SchedulingStrategy.FIFO)
        scheduler_fifo = QueueScheduler(temp_queue, config_fifo)
        next_fifo = scheduler_fifo._select_next_job()
        assert next_fifo.id == j1.id

        # Shortest first should return j2
        config_short = SchedulerConfig(strategy=SchedulingStrategy.SHORTEST_FIRST)
        scheduler_short = QueueScheduler(temp_queue, config_short)
        next_short = scheduler_short._select_next_job()
        assert next_short.id == j2.id
