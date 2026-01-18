"""Dashboard CLI commands for Claude Fab Lab."""

import asyncio
import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8080, type=int, help="Port to bind to")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
def dashboard(host: str, port: int, no_browser: bool) -> None:
    """Start the remote monitoring dashboard.

    Launches a web-based dashboard for monitoring 3D prints remotely.
    Features include:
    - Live temperature graphs
    - Print progress tracking
    - Alert notifications
    - Camera feed (when available)

    Examples:

        fab dashboard

        fab dashboard --port 9000

        fab dashboard --host 127.0.0.1 --no-browser
    """
    from src.jarvis import Dashboard, DashboardConfig

    config = DashboardConfig(host=host, port=port)
    dash = Dashboard(config)

    console.print("[bold]Claude Fab Lab Dashboard[/bold]")
    console.print()

    try:
        asyncio.run(_run_dashboard(dash, no_browser))
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped[/yellow]")


async def _run_dashboard(dash, no_browser: bool) -> None:
    """Run the dashboard server."""
    success = await dash.start()

    if not success:
        console.print("[red]Failed to start dashboard[/red]")
        console.print("[dim]Make sure aiohttp is installed: pip install aiohttp[/dim]")
        return

    console.print(f"[green]Dashboard running at {dash.url}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    # Open browser
    if not no_browser:
        try:
            import webbrowser
            webbrowser.open(dash.url)
        except Exception:
            pass

    # Keep running
    try:
        while dash.is_running:
            await asyncio.sleep(1)
    finally:
        await dash.stop()


@click.command()
@click.option("--printer-ip", "-p", help="Printer IP address")
@click.option("--mock", is_flag=True, help="Use mock data")
def printer_status(printer_ip: str, mock: bool) -> None:
    """Show printer status summary.

    Displays current printer status including:
    - Connection status
    - Current temperatures
    - Print progress (if printing)

    Examples:

        fab printer-status

        fab printer-status -p 192.168.1.100
    """
    from rich.table import Table
    from rich.panel import Panel

    console.print("[bold]Printer Status[/bold]")
    console.print()

    if mock:
        # Mock data for demo
        status_table = Table(show_header=False, box=None)
        status_table.add_row("Connection:", "[green]Connected[/green]")
        status_table.add_row("Status:", "[blue]Printing[/blue]")
        status_table.add_row("Model:", "benchy.3mf")
        status_table.add_row("Progress:", "45.2%")
        status_table.add_row("Layer:", "120/450")
        status_table.add_row("Time Elapsed:", "1:23:45")
        status_table.add_row("Time Remaining:", "1:42:00")
        console.print(status_table)

        console.print()
        console.print("[bold]Temperatures[/bold]")

        temp_table = Table(show_header=True)
        temp_table.add_column("Component")
        temp_table.add_column("Current")
        temp_table.add_column("Target")
        temp_table.add_row("Nozzle", "200.5C", "200C")
        temp_table.add_row("Bed", "60.2C", "60C")
        temp_table.add_row("Chamber", "35.0C", "35C")
        console.print(temp_table)
    else:
        console.print("[yellow]Connect to a printer with --printer-ip or use --mock for demo[/yellow]")
