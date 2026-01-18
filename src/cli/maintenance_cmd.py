"""CLI commands for maintenance prediction."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group()
def maintenance():
    """Maintenance prediction commands."""
    pass


@maintenance.command()
@click.option("--printer", "-p", default="bambu_x1c", help="Printer model")
@click.pass_context
def status(ctx: click.Context, printer: str) -> None:
    """Show overall maintenance status.

    Examples:
        cli maintenance status
        cli maintenance status --printer bambu_p1s
    """
    from src.maintenance.predictor import MaintenancePredictor

    predictor = MaintenancePredictor(printer_model=printer)
    overall = predictor.get_overall_status()

    # Status panel
    status_color = {
        "good": "green",
        "attention": "yellow",
        "warning": "orange1",
        "critical": "red",
    }.get(overall["status"], "white")

    console.print(Panel(
        f"[bold {status_color}]{overall['status'].upper()}[/bold {status_color}]",
        title="Maintenance Status",
    ))

    # Stats
    stats = overall["stats"]
    console.print(f"\n[bold]Printer Statistics:[/bold]")
    console.print(f"  Print Hours: {stats['total_print_hours']:.1f}")
    console.print(f"  Total Prints: {stats['total_prints']}")
    console.print(f"  Material Used: {stats['total_material_grams']:.0f}g")

    # Alerts summary
    alerts = overall["alerts_summary"]
    if alerts["total"] > 0:
        console.print(f"\n[bold]Alerts:[/bold]")
        if alerts["critical"]:
            console.print(f"  [red]Critical: {alerts['critical']}[/red]")
        if alerts["high"]:
            console.print(f"  [orange1]High: {alerts['high']}[/orange1]")
        if alerts["medium"]:
            console.print(f"  [yellow]Medium: {alerts['medium']}[/yellow]")
    else:
        console.print("\n[green]No maintenance alerts[/green]")

    # Component status
    console.print(f"\n[bold]Components:[/bold]")
    for comp, comp_status in overall["components"].items():
        status_icon = {
            "good": "[green]\u2714[/green]",
            "warning": "[yellow]\u26a0[/yellow]",
            "critical": "[red]\u2718[/red]",
        }.get(comp_status, " ")
        console.print(f"  {status_icon} {comp}")


@maintenance.command()
@click.option("--printer", "-p", default="bambu_x1c", help="Printer model")
@click.pass_context
def alerts(ctx: click.Context, printer: str) -> None:
    """Show maintenance alerts.

    Examples:
        cli maintenance alerts
    """
    from src.maintenance.predictor import MaintenancePredictor, AlertPriority

    predictor = MaintenancePredictor(printer_model=printer)
    alert_list = predictor.get_alerts()

    if not alert_list:
        console.print("[green]No maintenance alerts[/green]")
        return

    table = Table(title="Maintenance Alerts")
    table.add_column("Priority", style="bold")
    table.add_column("Task")
    table.add_column("Component")
    table.add_column("Progress")
    table.add_column("Due")

    for alert in alert_list:
        priority_style = {
            AlertPriority.CRITICAL: "red",
            AlertPriority.HIGH: "orange1",
            AlertPriority.MEDIUM: "yellow",
            AlertPriority.LOW: "dim",
        }.get(alert.priority, "white")

        table.add_row(
            f"[{priority_style}]{alert.priority.value.upper()}[/{priority_style}]",
            alert.task_name,
            alert.component,
            f"{alert.progress_percent:.0f}%",
            alert.due_at or "-",
        )

    console.print(table)


@maintenance.command()
@click.argument("component")
@click.argument("task")
@click.option("--notes", "-n", help="Optional notes")
@click.option("--printer", "-p", default="bambu_x1c", help="Printer model")
@click.pass_context
def record(
    ctx: click.Context,
    component: str,
    task: str,
    notes: str,
    printer: str,
) -> None:
    """Record a maintenance task.

    Examples:
        cli maintenance record nozzle "Nozzle Inspection"
        cli maintenance record bed "Bed Cleaning" --notes "Used IPA"
    """
    from src.maintenance.predictor import MaintenancePredictor

    predictor = MaintenancePredictor(printer_model=printer)
    predictor.record_maintenance(component, task, notes)

    console.print(f"[green]Recorded maintenance: {task} on {component}[/green]")


@maintenance.command()
@click.option("--hours", type=float, help="Print hours to add")
@click.option("--prints", type=int, help="Number of prints to add")
@click.option("--material", type=float, help="Material used (grams)")
@click.option("--printer", "-p", default="bambu_x1c", help="Printer model")
@click.pass_context
def update(
    ctx: click.Context,
    hours: float,
    prints: int,
    material: float,
    printer: str,
) -> None:
    """Update printer statistics.

    Examples:
        cli maintenance update --hours 2.5 --prints 1 --material 50
    """
    from src.maintenance.predictor import MaintenancePredictor

    if not any([hours, prints, material]):
        console.print("[yellow]No values provided to update[/yellow]")
        return

    predictor = MaintenancePredictor(printer_model=printer)
    predictor.update_stats(
        print_hours=hours,
        prints=prints,
        material_grams=material,
    )

    console.print("[green]Statistics updated[/green]")
    console.print(f"  Print Hours: {predictor.stats.total_print_hours:.1f}")
    console.print(f"  Total Prints: {predictor.stats.total_prints}")
    console.print(f"  Material Used: {predictor.stats.total_material_grams:.0f}g")


@maintenance.command()
@click.option("--component", "-c", help="Filter by component")
@click.option("--limit", "-l", default=20, help="Maximum entries")
@click.option("--printer", "-p", default="bambu_x1c", help="Printer model")
@click.pass_context
def history(
    ctx: click.Context,
    component: str,
    limit: int,
    printer: str,
) -> None:
    """Show maintenance history.

    Examples:
        cli maintenance history
        cli maintenance history --component nozzle --limit 10
    """
    from src.maintenance.predictor import MaintenancePredictor

    predictor = MaintenancePredictor(printer_model=printer)
    entries = predictor.get_maintenance_history(component=component, limit=limit)

    if not entries:
        console.print("[dim]No maintenance history[/dim]")
        return

    table = Table(title="Maintenance History")
    table.add_column("Date")
    table.add_column("Component")
    table.add_column("Task")
    table.add_column("Notes")

    for entry in reversed(entries):
        table.add_row(
            entry["date"][:10],
            entry["component"],
            entry["task"],
            entry.get("notes") or "-",
        )

    console.print(table)


@maintenance.command()
@click.argument("component")
@click.option("--printer", "-p", default="bambu_x1c", help="Printer model")
@click.pass_context
def component(ctx: click.Context, component: str, printer: str) -> None:
    """Show status for a specific component.

    Examples:
        cli maintenance component nozzle
        cli maintenance component bed
    """
    from src.maintenance.predictor import MaintenancePredictor

    predictor = MaintenancePredictor(printer_model=printer)
    status = predictor.get_component_status(component)

    if not status["tasks"]:
        console.print(f"[yellow]No maintenance tasks for component: {component}[/yellow]")
        return

    status_color = {
        "good": "green",
        "warning": "yellow",
        "critical": "red",
    }.get(status["status"], "white")

    console.print(Panel(
        f"[bold {status_color}]{status['status'].upper()}[/bold {status_color}]",
        title=f"Component: {component}",
    ))

    if status["last_maintenance"]:
        console.print(f"\nLast Maintenance: {status['last_maintenance'][:10]}")
    else:
        console.print("\n[dim]No recorded maintenance[/dim]")

    console.print(f"\n[bold]Scheduled Tasks:[/bold]")
    for task in status["tasks"]:
        console.print(f"  - {task['name']} (every {task['interval']} {task['schedule_type']})")

    if status["alerts"]:
        console.print(f"\n[bold]Active Alerts:[/bold]")
        for alert in status["alerts"]:
            console.print(f"  [{alert['priority']}] {alert['task_name']} ({alert['progress_percent']:.0f}%)")


@maintenance.command()
@click.option("--printer", "-p", default="bambu_x1c", help="Printer model")
@click.pass_context
def schedule(ctx: click.Context, printer: str) -> None:
    """Show maintenance schedule.

    Examples:
        cli maintenance schedule
    """
    from src.maintenance.schedules import get_default_schedule

    sched = get_default_schedule(printer)

    table = Table(title=f"Maintenance Schedule ({printer})")
    table.add_column("Task")
    table.add_column("Component")
    table.add_column("Interval")
    table.add_column("Type")

    for item in sched.items:
        table.add_row(
            item.name,
            item.component,
            str(item.interval),
            item.schedule_type.value,
        )

    console.print(table)
