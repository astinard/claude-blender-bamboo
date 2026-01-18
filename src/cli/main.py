"""Main CLI entry point for Claude Fab Lab."""

import click
from rich.console import Console

from src import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="Claude Fab Lab")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Claude Fab Lab - AI-powered 3D printing workflow.

    A comprehensive toolkit for Blender + Bambu Labs integration with
    AI-assisted design, print management, and monitoring.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# Import and register command groups
from src.cli.materials import materials
from src.cli.generate import generate
from src.cli.queue_cmd import queue
from src.cli.analyze import analyze
from src.cli.version_cmd import version
from src.cli.monitor import monitor, snapshot, camera_status
from src.cli.preview import preview
from src.cli.suggest import suggest
from src.cli.support import supports
from src.cli.dashboard import dashboard, printer_status
from src.cli.analytics import analytics
from src.cli.timelapse_cmd import timelapse
from src.cli.ar_cmd import ar
from src.cli.maintenance_cmd import maintenance
from src.cli.photogrammetry_cmd import photogrammetry
from src.cli.texture_cmd import texture
from src.cli.adaptive_cmd import adaptive
from src.cli.cost_cmd import cost_group as cost

cli.add_command(materials)
cli.add_command(generate)
cli.add_command(queue)
cli.add_command(analyze)
cli.add_command(version)
cli.add_command(monitor)
cli.add_command(snapshot)
cli.add_command(camera_status)
cli.add_command(preview)
cli.add_command(suggest)
cli.add_command(supports)
cli.add_command(dashboard)
cli.add_command(printer_status)
cli.add_command(analytics)
cli.add_command(timelapse)
cli.add_command(ar)
cli.add_command(maintenance)
cli.add_command(photogrammetry)
cli.add_command(texture)
cli.add_command(adaptive)
cli.add_command(cost)


@cli.command()
def status() -> None:
    """Show system status and configuration."""
    from src.config import get_settings

    settings = get_settings()

    console.print("[bold]Claude Fab Lab Status[/bold]")
    console.print(f"Version: {__version__}")
    console.print()
    console.print("[bold]Configuration:[/bold]")
    console.print(f"  Output Directory: {settings.output_dir}")
    console.print(f"  Data Directory: {settings.data_dir}")
    console.print(f"  Mock Mode: {settings.mock_mode}")
    console.print()
    console.print("[bold]Printer:[/bold]")
    if settings.printer_ip:
        console.print(f"  IP: {settings.printer_ip}")
        console.print(f"  Serial: {settings.printer_serial or 'Not set'}")
    else:
        console.print("  [yellow]Not configured[/yellow]")
    console.print()
    console.print("[bold]AI Services:[/bold]")
    console.print(f"  Meshy API: {'[green]Configured[/green]' if settings.meshy_api_key else '[yellow]Not set[/yellow]'}")
    console.print(f"  Tripo API: {'[green]Configured[/green]' if settings.tripo_api_key else '[yellow]Not set[/yellow]'}")


if __name__ == "__main__":
    cli()
