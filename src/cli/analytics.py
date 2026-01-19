"""Analytics CLI commands for Claude Fab Lab."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import json

console = Console()


@click.group()
def analytics() -> None:
    """Print analytics and reporting.

    Track print jobs, view statistics, and generate reports.
    """
    pass


@analytics.command()
@click.option("--period", "-p", default="month",
              type=click.Choice(["day", "week", "month", "quarter", "year", "all_time"]),
              help="Report period")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def report(period: str, json_output: bool) -> None:
    """Generate an analytics report.

    Examples:

        fab analytics report

        fab analytics report --period week

        fab analytics report -p year --json-output
    """
    from src.analytics import generate_report, ReportPeriod

    period_enum = ReportPeriod(period)
    report_data = generate_report(period=period_enum)

    if json_output:
        console.print(json.dumps(report_data.to_dict(), indent=2))
        return

    console.print(f"[bold]Analytics Report ({period})[/bold]")
    console.print(f"[dim]{report_data.start_date} to {report_data.end_date}[/dim]")
    console.print()

    # Summary
    console.print("[bold]Summary[/bold]")
    summary_table = Table(show_header=False, box=None)
    summary_table.add_row("Total Prints:", str(report_data.total_prints))
    summary_table.add_row("Total Material:", f"{report_data.total_material_grams:.1f}g")
    summary_table.add_row("Total Cost:", f"${report_data.total_cost:.2f}")
    summary_table.add_row("Total Print Time:", f"{report_data.total_print_hours:.1f}h")
    console.print(summary_table)
    console.print()

    # Success rate
    if report_data.success_rate:
        sr = report_data.success_rate
        console.print("[bold]Success Rate[/bold]")
        sr_table = Table(show_header=False, box=None)
        sr_table.add_row("Success Rate:", f"[green]{sr.success_rate:.1f}%[/green]")
        sr_table.add_row("Successful:", str(sr.successful))
        sr_table.add_row("Failed:", f"[red]{sr.failed}[/red]" if sr.failed > 0 else "0")
        sr_table.add_row("Cancelled:", str(sr.cancelled))
        console.print(sr_table)
        console.print()

    # Material usage
    if report_data.material_usage:
        console.print("[bold]Material Usage[/bold]")
        mat_table = Table()
        mat_table.add_column("Material")
        mat_table.add_column("Used (g)", justify="right")
        mat_table.add_column("Cost", justify="right")
        mat_table.add_column("Prints", justify="right")

        for m in report_data.material_usage:
            mat_table.add_row(
                m.material_type,
                f"{m.total_grams:.1f}",
                f"${m.total_cost:.2f}",
                str(m.usage_count),
            )
        console.print(mat_table)
        console.print()

    # Time report
    if report_data.time:
        t = report_data.time
        console.print("[bold]Time Statistics[/bold]")
        time_table = Table(show_header=False, box=None)
        time_table.add_row("Average Print Time:", f"{t.avg_print_time_hours:.1f}h")
        time_table.add_row("Longest Print:", f"{t.longest_print_hours:.1f}h")
        time_table.add_row("Shortest Print:", f"{t.shortest_print_hours:.1f}h")
        console.print(time_table)


@analytics.command()
@click.option("--limit", "-l", default=10, help="Number of records to show")
@click.option("--outcome", "-o", type=click.Choice(["success", "failed", "cancelled"]),
              help="Filter by outcome")
@click.option("--material", "-m", help="Filter by material type")
def history(limit: int, outcome: str, material: str) -> None:
    """View print history.

    Examples:

        fab analytics history

        fab analytics history --limit 20

        fab analytics history --outcome failed
    """
    from src.analytics import PrintTracker, PrintOutcome

    tracker = PrintTracker()
    outcome_enum = PrintOutcome(outcome) if outcome else None

    records = tracker.get_records(
        outcome=outcome_enum,
        material_type=material,
        limit=limit,
    )

    if not records:
        console.print("[yellow]No print records found[/yellow]")
        return

    console.print(f"[bold]Print History[/bold] (showing {len(records)} records)")
    console.print()

    table = Table()
    table.add_column("ID")
    table.add_column("File")
    table.add_column("Outcome")
    table.add_column("Duration")
    table.add_column("Material")
    table.add_column("Date")

    for record in records:
        outcome_style = {
            "success": "green",
            "failed": "red",
            "cancelled": "yellow",
            "unknown": "dim",
        }.get(record.outcome.value, "")

        duration = ""
        if record.duration_seconds:
            hours = record.duration_seconds // 3600
            minutes = (record.duration_seconds % 3600) // 60
            duration = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        date = record.started_at[:10] if record.started_at else ""

        table.add_row(
            record.id,
            record.file_name[:20],
            f"[{outcome_style}]{record.outcome.value}[/{outcome_style}]",
            duration,
            record.material_type or "-",
            date,
        )

    console.print(table)


@analytics.command()
def stats() -> None:
    """Show quick statistics.

    Examples:

        fab analytics stats
    """
    from src.analytics import PrintTracker

    tracker = PrintTracker()
    stats = tracker.get_stats()

    console.print("[bold]Print Statistics[/bold]")
    console.print()

    table = Table(show_header=False, box=None)
    table.add_row("Total Prints:", str(stats.get("total_prints", 0)))
    table.add_row("Successful:", str(stats.get("successful_prints", 0)))
    table.add_row("Failed:", str(stats.get("failed_prints", 0)))
    table.add_row("Success Rate:", f"{stats.get('success_rate', 0):.1f}%")
    table.add_row("Total Material:", f"{stats.get('total_material_grams', 0) or 0:.1f}g")
    table.add_row("Total Cost:", f"${stats.get('total_cost', 0) or 0:.2f}")

    console.print(table)


@analytics.command()
@click.argument("file_name")
@click.option("--material", "-m", help="Material type")
@click.option("--layers", "-l", type=int, help="Total layers")
@click.option("--printer", "-p", help="Printer ID")
def start(file_name: str, material: str, layers: int, printer: str) -> None:
    """Start tracking a print job.

    Examples:

        fab analytics start benchy.3mf --material PLA

        fab analytics start model.3mf -m PETG -l 500 -p printer1
    """
    from src.analytics import PrintTracker

    tracker = PrintTracker()
    record_id = tracker.start_print(
        file_name=file_name,
        material_type=material,
        layers_total=layers,
        printer_id=printer,
    )

    console.print(f"[green]Started tracking print: {record_id}[/green]")
    console.print(f"Use 'fab analytics complete {record_id}' when done")


@analytics.command()
@click.argument("record_id")
@click.option("--outcome", "-o", default="success",
              type=click.Choice(["success", "failed", "cancelled"]),
              help="Print outcome")
@click.option("--material-used", "-m", type=float, help="Material used in grams")
@click.option("--cost", "-c", type=float, help="Cost")
@click.option("--notes", "-n", help="Notes")
def complete(record_id: str, outcome: str, material_used: float, cost: float, notes: str) -> None:
    """Complete tracking a print job.

    Examples:

        fab analytics complete abc123

        fab analytics complete abc123 --outcome failed --notes "Spaghetti"

        fab analytics complete abc123 -m 45.5 -c 1.20
    """
    from src.analytics import PrintTracker, PrintOutcome

    tracker = PrintTracker()
    outcome_enum = PrintOutcome(outcome)

    record = tracker.complete_print(
        record_id=record_id,
        outcome=outcome_enum,
        material_used_grams=material_used,
        material_cost=cost,
        notes=notes,
    )

    if record:
        console.print(f"[green]Completed print: {record_id} ({outcome})[/green]")
    else:
        console.print(f"[red]Print record not found: {record_id}[/red]")
