"""Print queue CLI commands for Claude Fab Lab."""

import click
from rich.console import Console
from rich.table import Table
from pathlib import Path

console = Console()


@click.group()
def queue() -> None:
    """Print queue management commands."""
    pass


@queue.command("add")
@click.argument("file_path")
@click.option("--priority", "-p", default="normal",
              type=click.Choice(["low", "normal", "high", "urgent"]),
              help="Job priority")
@click.option("--name", "-n", default=None, help="Job name")
@click.option("--material", "-m", default="pla", help="Material type")
@click.option("--color", "-c", default="white", help="Filament color")
@click.option("--depends-on", "-d", multiple=True, help="Job IDs this depends on")
def queue_add(file_path: str, priority: str, name: str, material: str, color: str, depends_on: tuple) -> None:
    """Add a model to the print queue.

    Example: fab queue add model.stl --priority high --material petg
    """
    from src.queue.job_queue import PrintQueue, JobPriority

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    queue_mgr = PrintQueue()
    job = queue_mgr.add_job(
        file_path=str(path),
        name=name,
        priority=JobPriority(priority),
        material=material,
        color=color,
        depends_on=list(depends_on) if depends_on else None,
    )

    console.print(f"[green]Added job {job.id}[/green]")
    console.print(f"  Name: {job.name}")
    console.print(f"  Priority: {job.priority.value}")
    console.print(f"  Material: {job.material} ({job.color})")
    if depends_on:
        console.print(f"  Depends on: {', '.join(depends_on)}")


@queue.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show completed jobs too")
def queue_list(show_all: bool) -> None:
    """List all jobs in the print queue."""
    from src.queue.job_queue import PrintQueue, JobStatus

    queue_mgr = PrintQueue()
    jobs = queue_mgr.list_all()

    if not jobs:
        console.print("[yellow]Queue is empty[/yellow]")
        console.print("Add jobs with: fab queue add <file>")
        return

    # Filter out completed if not showing all
    if not show_all:
        jobs = [j for j in jobs if not j.is_complete]

    if not jobs:
        console.print("[green]All jobs completed[/green]")
        console.print("Use --all to see completed jobs")
        return

    table = Table(title="Print Queue")
    table.add_column("#", style="dim")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Material")
    table.add_column("Progress")

    status_colors = {
        JobStatus.PENDING: "white",
        JobStatus.READY: "yellow",
        JobStatus.PRINTING: "green",
        JobStatus.PAUSED: "yellow",
        JobStatus.COMPLETED: "green",
        JobStatus.FAILED: "red",
        JobStatus.CANCELLED: "dim",
    }

    for i, job in enumerate(jobs, 1):
        color = status_colors.get(job.status, "white")
        progress = f"{job.progress_percent:.0f}%" if job.progress_percent > 0 else "-"

        table.add_row(
            str(i),
            job.id,
            job.name[:20],
            f"[{color}]{job.status.value}[/{color}]",
            job.priority.value,
            f"{job.material} ({job.color})",
            progress,
        )

    console.print(table)

    # Summary
    counts = queue_mgr.count()
    console.print(f"\n[dim]Pending: {counts[JobStatus.PENDING] + counts[JobStatus.READY]} | "
                  f"Printing: {counts[JobStatus.PRINTING]} | "
                  f"Completed: {counts[JobStatus.COMPLETED]} | "
                  f"Failed: {counts[JobStatus.FAILED]}[/dim]")


@queue.command("start")
@click.option("--mock", is_flag=True, help="Use mock mode (no actual printing)")
@click.option("--strategy", "-s", default="fifo",
              type=click.Choice(["fifo", "shortest_first", "material_batch"]),
              help="Scheduling strategy")
def queue_start(mock: bool, strategy: str) -> None:
    """Start processing the print queue."""
    from src.queue.job_queue import PrintQueue
    from src.queue.scheduler import QueueScheduler, SchedulerConfig, SchedulingStrategy

    queue_mgr = PrintQueue()

    if len(queue_mgr) == 0:
        console.print("[yellow]Queue is empty[/yellow]")
        return

    config = SchedulerConfig(
        strategy=SchedulingStrategy(strategy),
        mock_mode=mock,
    )

    def on_start(job):
        console.print(f"[green]Starting job {job.id}: {job.name}[/green]")

    def on_complete(job):
        console.print(f"[green]Completed job {job.id}: {job.name}[/green]")

    def on_failed(job, error):
        console.print(f"[red]Failed job {job.id}: {error}[/red]")

    scheduler = QueueScheduler(
        queue=queue_mgr,
        config=config,
        on_job_start=on_start,
        on_job_complete=on_complete,
        on_job_failed=on_failed,
    )

    console.print(f"[bold]Starting queue processing[/bold]")
    console.print(f"Strategy: {strategy}")
    console.print(f"Mock mode: {mock}")
    console.print()

    job = scheduler.start()

    if job:
        if mock:
            console.print(f"\n[green]Mock processing complete[/green]")
            status = scheduler.get_status()
            console.print(f"  Jobs completed: {status['jobs_completed']}")
        else:
            console.print(f"\n[yellow]Queue started (would connect to printer)[/yellow]")
            console.print("Real printer integration coming in Sprint 4")
    else:
        console.print("[yellow]No jobs ready to print[/yellow]")


@queue.command("remove")
@click.argument("job_id")
def queue_remove(job_id: str) -> None:
    """Remove a job from the queue."""
    from src.queue.job_queue import PrintQueue

    queue_mgr = PrintQueue()

    if queue_mgr.remove_job(job_id):
        console.print(f"[green]Removed job {job_id}[/green]")
    else:
        console.print(f"[red]Could not remove job {job_id}[/red]")
        console.print("[dim]Job may be active or not exist[/dim]")


@queue.command("priority")
@click.argument("job_id")
@click.argument("priority", type=click.Choice(["low", "normal", "high", "urgent"]))
def queue_priority(job_id: str, priority: str) -> None:
    """Change a job's priority."""
    from src.queue.job_queue import PrintQueue, JobPriority

    queue_mgr = PrintQueue()

    if queue_mgr.set_priority(job_id, JobPriority(priority)):
        console.print(f"[green]Set job {job_id} priority to {priority}[/green]")
    else:
        console.print(f"[red]Could not change priority for job {job_id}[/red]")


@queue.command("move")
@click.argument("job_id")
@click.argument("position", type=click.Choice(["top", "bottom"]))
def queue_move(job_id: str, position: str) -> None:
    """Move a job to top or bottom of its priority group."""
    from src.queue.job_queue import PrintQueue

    queue_mgr = PrintQueue()

    if position == "top":
        success = queue_mgr.move_to_top(job_id)
    else:
        success = queue_mgr.move_to_bottom(job_id)

    if success:
        console.print(f"[green]Moved job {job_id} to {position}[/green]")
    else:
        console.print(f"[red]Could not move job {job_id}[/red]")


@queue.command("clear")
@click.option("--completed", is_flag=True, help="Clear only completed jobs")
@click.confirmation_option(prompt="Are you sure you want to clear the queue?")
def queue_clear(completed: bool) -> None:
    """Clear jobs from the queue."""
    from src.queue.job_queue import PrintQueue

    queue_mgr = PrintQueue()

    if completed:
        count = queue_mgr.clear_completed()
        console.print(f"[green]Cleared {count} completed jobs[/green]")
    else:
        # Clear all non-active jobs
        pending = queue_mgr.get_pending_jobs()
        for job in pending:
            queue_mgr.remove_job(job.id)
        console.print(f"[green]Cleared {len(pending)} pending jobs[/green]")


@queue.command("info")
@click.argument("job_id")
def queue_info(job_id: str) -> None:
    """Show detailed information about a job."""
    from src.queue.job_queue import PrintQueue
    from src.utils import format_duration

    queue_mgr = PrintQueue()
    job = queue_mgr.get_job(job_id)

    if job is None:
        console.print(f"[red]Job {job_id} not found[/red]")
        return

    console.print(f"[bold]Job: {job.name}[/bold]")
    console.print(f"  ID: {job.id}")
    console.print(f"  File: {job.file_path}")
    console.print(f"  Status: {job.status.value}")
    console.print(f"  Priority: {job.priority.value}")
    console.print()
    console.print(f"[bold]Material:[/bold]")
    console.print(f"  Type: {job.material}")
    console.print(f"  Color: {job.color}")
    if job.ams_slot:
        console.print(f"  AMS Slot: {job.ams_slot}")
    console.print()
    console.print(f"[bold]Settings:[/bold]")
    console.print(f"  Quality: {job.quality}")
    console.print(f"  Infill: {job.infill_percent}%")
    console.print(f"  Supports: {'Yes' if job.supports_enabled else 'No'}")
    console.print()
    console.print(f"[bold]Progress:[/bold]")
    console.print(f"  Progress: {job.progress_percent:.1f}%")
    if job.total_layers > 0:
        console.print(f"  Layer: {job.current_layer}/{job.total_layers}")
    console.print()
    console.print(f"[bold]Timing:[/bold]")
    console.print(f"  Created: {job.created_at}")
    if job.started_at:
        console.print(f"  Started: {job.started_at}")
    if job.completed_at:
        console.print(f"  Completed: {job.completed_at}")
    if job.estimated_time_seconds > 0:
        console.print(f"  Estimated: {format_duration(job.estimated_time_seconds)}")
    if job.depends_on:
        console.print()
        console.print(f"[bold]Dependencies:[/bold] {', '.join(job.depends_on)}")
    if job.notes:
        console.print()
        console.print(f"[bold]Notes:[/bold] {job.notes}")
