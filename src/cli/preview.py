"""Preview CLI commands for Claude Fab Lab."""

import click
from rich.console import Console
from pathlib import Path

console = Console()


@click.group()
def preview() -> None:
    """Print preview commands."""
    pass


@preview.command("print")
@click.argument("file_path")
@click.option("--materials", "-m", multiple=True, help="Materials for each AMS slot")
@click.option("--colors", "-c", multiple=True, help="Colors for each AMS slot")
@click.option("--export-html", is_flag=True, help="Export HTML preview")
@click.option("--output", "-o", default=None, help="Output path for HTML export")
def preview_print(file_path: str, materials: tuple, colors: tuple, export_html: bool, output: str) -> None:
    """Generate print preview with AMS slot visualization.

    Example: fab preview print model.3mf -m pla -m petg -c white -c black --export-html
    """
    from src.printer.print_preview import (
        generate_preview,
        export_preview_html,
        create_ams_config,
    )

    # Validate file exists
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    # Create AMS configuration
    if not materials:
        materials = ("pla",)  # Default to single PLA

    if not colors:
        colors = ("white",) * len(materials)

    # Pad colors if fewer than materials
    colors = list(colors) + ["white"] * (len(materials) - len(colors))

    ams_config = create_ams_config(
        materials=list(materials),
        colors=list(colors[:len(materials)]),
    )

    console.print(f"[bold]Print Preview: {path.name}[/bold]\n")

    # Generate preview
    preview = generate_preview(str(path), ams_config)

    # Display AMS configuration
    console.print("[bold]AMS Slot Configuration:[/bold]")
    for slot in preview.ams_slots:
        mat = slot.material_obj
        mat_name = mat.name if mat else slot.material.upper()
        console.print(f"  Slot {slot.slot}: [cyan]{mat_name}[/cyan] ({slot.color})")

    # Display compatibility
    if preview.compatibility_level:
        level = preview.compatibility_level
        color_map = {
            "excellent": "green",
            "good": "green",
            "fair": "yellow",
            "poor": "red",
            "incompatible": "red bold",
        }
        color = color_map.get(level, "white")
        console.print(f"\n[bold]Material Compatibility:[/bold] [{color}]{level.upper()}[/{color}]")

    # Display warnings
    if preview.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in preview.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")

    # Display estimate if available
    if preview.estimate and preview.estimate.total_time_seconds > 0:
        from src.utils import format_duration
        console.print("\n[bold]Print Estimate:[/bold]")
        console.print(f"  Time: {format_duration(preview.estimate.total_time_seconds)}")
        console.print(f"  Layers: {preview.estimate.total_layers}")
        console.print(f"  Height: {preview.estimate.max_z_height:.1f}mm")

    # Export HTML if requested
    if export_html:
        html_path = export_preview_html(preview, output)
        console.print(f"\n[green]HTML preview exported to: {html_path}[/green]")


@preview.command("ar")
@click.argument("file_path")
@click.option("--serve", is_flag=True, help="Start local server for AR preview")
@click.option("--port", default=9880, help="Server port (default: 9880)")
def preview_ar(file_path: str, serve: bool, port: int) -> None:
    """Generate AR preview for iOS devices.

    Converts STL/OBJ to USDZ format and optionally serves it
    with a QR code for quick iPhone scanning.

    Example: fab preview ar model.stl --serve
    """
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    console.print(f"[bold]AR Preview: {path.name}[/bold]")
    console.print("[yellow]AR preview (USDZ export) coming in Sprint 6+ (P6.1)[/yellow]")

    if serve:
        console.print(f"\n[dim]Would start server on port {port}[/dim]")
        console.print("[dim]Would generate QR code for iPhone scanning[/dim]")
