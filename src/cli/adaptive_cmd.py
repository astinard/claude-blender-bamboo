"""CLI commands for adaptive layer heights."""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group()
def adaptive():
    """Adaptive layer height commands."""
    pass


@adaptive.command()
@click.argument("mesh")
@click.option("--strategy", "-s", default="balanced",
              type=click.Choice(["quality", "speed", "balanced"]),
              help="Optimization strategy")
@click.option("--min-layer", type=float, help="Minimum layer height (mm)")
@click.option("--max-layer", type=float, help="Maximum layer height (mm)")
@click.pass_context
def analyze(
    ctx: click.Context,
    mesh: str,
    strategy: str,
    min_layer: float,
    max_layer: float,
) -> None:
    """Analyze model for adaptive layer heights.

    Examples:
        cli adaptive analyze model.stl
        cli adaptive analyze model.obj --strategy quality
        cli adaptive analyze model.stl --min-layer 0.1 --max-layer 0.3
    """
    from src.slicing.adaptive_layers import (
        AdaptiveLayerOptimizer, LayerConfig, OptimizationStrategy
    )

    mesh_path = Path(mesh)
    if not mesh_path.exists():
        console.print(f"[red]Error: Mesh file not found: {mesh}[/red]")
        return

    console.print(f"Analyzing {mesh_path.name} with {strategy} strategy...")

    config = LayerConfig.for_strategy(OptimizationStrategy(strategy))
    if min_layer:
        config.min_layer_height = min_layer
    if max_layer:
        config.max_layer_height = max_layer

    optimizer = AdaptiveLayerOptimizer(config=config)
    result = optimizer.analyze_model(str(mesh_path))

    if result.success:
        # Summary panel
        console.print(Panel(
            f"[bold green]Analysis Complete[/bold green]\n\n"
            f"Model Height: {result.model_height:.1f}mm\n"
            f"Total Layers: {result.total_layers}\n"
            f"Quality Score: {result.quality_score:.0f}/100\n"
            f"Time Savings: ~{result.estimated_time_savings:.1f}%\n"
            f"Analysis Time: {result.analysis_time:.2f}s",
            title="Adaptive Layer Analysis",
        ))

        # Regions table
        if result.regions:
            table = Table(title="Layer Regions")
            table.add_column("Z Range")
            table.add_column("Layer Height")
            table.add_column("Reason")
            table.add_column("Curvature")
            table.add_column("Overhang")

            for region in result.regions:
                height_color = "green" if region.layer_height <= 0.12 else (
                    "yellow" if region.layer_height <= 0.20 else "dim"
                )
                table.add_row(
                    f"{region.start_z:.1f}-{region.end_z:.1f}mm",
                    f"[{height_color}]{region.layer_height:.2f}mm[/{height_color}]",
                    region.reason,
                    f"{region.curvature:.2f}",
                    f"{region.overhang_angle:.0f}\u00b0",
                )

            console.print(table)
    else:
        console.print(f"[red]Analysis failed: {result.error_message}[/red]")


@adaptive.command()
@click.argument("mesh")
@click.option("--output", "-o", help="Output file path")
@click.option("--strategy", "-s", default="balanced",
              type=click.Choice(["quality", "speed", "balanced"]),
              help="Optimization strategy")
@click.pass_context
def export(
    ctx: click.Context,
    mesh: str,
    output: str,
    strategy: str,
) -> None:
    """Export adaptive layer configuration.

    Examples:
        cli adaptive export model.stl
        cli adaptive export model.stl -o layers.txt
    """
    from src.slicing.adaptive_layers import (
        AdaptiveLayerOptimizer, LayerConfig, OptimizationStrategy
    )

    mesh_path = Path(mesh)
    if not mesh_path.exists():
        console.print(f"[red]Error: Mesh file not found: {mesh}[/red]")
        return

    config = LayerConfig.for_strategy(OptimizationStrategy(strategy))
    optimizer = AdaptiveLayerOptimizer(config=config)
    result = optimizer.analyze_model(str(mesh_path))

    if not result.success:
        console.print(f"[red]Analysis failed: {result.error_message}[/red]")
        return

    content = optimizer.export_to_gcode_variable_layer(result)

    if output:
        output_path = Path(output)
        output_path.write_text(content)
        console.print(f"[green]Exported to: {output_path}[/green]")
    else:
        console.print(content)


@adaptive.command()
@click.pass_context
def presets(ctx: click.Context) -> None:
    """Show available optimization presets.

    Examples:
        cli adaptive presets
    """
    from src.slicing.adaptive_layers import LayerConfig, OptimizationStrategy

    console.print("[bold]Optimization Presets[/bold]\n")

    for strategy in OptimizationStrategy:
        if strategy == OptimizationStrategy.CUSTOM:
            continue

        config = LayerConfig.for_strategy(strategy)
        console.print(Panel(
            f"[bold]Min Layer:[/bold] {config.min_layer_height}mm\n"
            f"[bold]Max Layer:[/bold] {config.max_layer_height}mm\n"
            f"[bold]Default:[/bold] {config.default_layer_height}mm\n"
            f"[bold]Quality Threshold:[/bold] {config.quality_threshold}",
            title=f"{strategy.value.upper()}",
        ))
