"""CLI commands for cost estimation and optimization."""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group("cost")
def cost_group():
    """Cost estimation and optimization commands."""
    pass


@cost_group.command("estimate")
@click.argument("model_path", type=click.Path(exists=True), required=False)
@click.option("--volume", "-v", type=float, help="Volume in cm³ (if no model)")
@click.option("--material", "-m", default="pla", help="Material type (pla, petg, abs, tpu)")
@click.option("--infill", "-i", type=int, default=20, help="Infill percentage")
@click.option("--layer-height", "-l", type=float, default=0.20, help="Layer height in mm")
@click.option("--supports", is_flag=True, help="Enable supports")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def estimate_cost(model_path, volume, material, infill, layer_height, supports, as_json):
    """Estimate print cost for a model or volume."""
    from src.estimator import CostOptimizer, PrintSettings
    import json

    optimizer = CostOptimizer()
    settings = PrintSettings(
        layer_height=layer_height,
        infill_percent=infill,
        supports=supports,
    )

    if model_path:
        estimate = optimizer.estimate_from_mesh(model_path, settings, material)
        source = f"Model: {Path(model_path).name}"
    elif volume:
        estimate = optimizer.estimate_cost(volume, settings, material)
        source = f"Volume: {volume} cm³"
    else:
        console.print("[red]Error: Provide either a model path or --volume[/red]")
        return

    if as_json:
        click.echo(json.dumps(estimate.to_dict(), indent=2))
        return

    # Create output table
    table = Table(title=f"Cost Estimate - {source}")
    table.add_column("Category", style="cyan")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("Details", style="dim")

    table.add_row("Material", f"${estimate.material_cost:.3f}", f"{estimate.material_grams:.1f}g {material.upper()}")
    table.add_row("Electricity", f"${estimate.electricity_cost:.3f}", f"{estimate.print_time_hours:.1f}h print time")
    table.add_row("Machine", f"${estimate.machine_cost:.3f}", "Depreciation")
    table.add_row("Labor", f"${estimate.labor_cost:.3f}", "Setup time")
    table.add_row("", "", "")
    table.add_row("[bold]Total[/bold]", f"[bold]${estimate.total_cost:.3f}[/bold]", "")

    console.print(table)


@cost_group.command("optimize")
@click.argument("model_path", type=click.Path(exists=True), required=False)
@click.option("--volume", "-v", type=float, help="Volume in cm³ (if no model)")
@click.option("--material", "-m", default="pla", help="Material type")
@click.option("--infill", "-i", type=int, default=50, help="Current infill percentage")
@click.option("--layer-height", "-l", type=float, default=0.16, help="Current layer height")
@click.option("--quality", "-q", type=click.Choice(["draft", "normal", "high"]), default="normal")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def optimize_cost(model_path, volume, material, infill, layer_height, quality, as_json):
    """Optimize print settings for lower cost."""
    from src.estimator import CostOptimizer, PrintSettings
    import json

    optimizer = CostOptimizer()
    settings = PrintSettings(
        layer_height=layer_height,
        infill_percent=infill,
    )

    if model_path:
        vol = optimizer._calculate_volume(model_path)
        if vol <= 0:
            vol = 10.0  # Default
        source = f"Model: {Path(model_path).name}"
    elif volume:
        vol = volume
        source = f"Volume: {volume} cm³"
    else:
        console.print("[red]Error: Provide either a model path or --volume[/red]")
        return

    result = optimizer.optimize(vol, settings, material, quality)

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2))
        return

    # Display optimization results
    panel_content = f"""[bold cyan]Original Cost:[/bold cyan] ${result.original_cost:.3f}
[bold green]Optimized Cost:[/bold green] ${result.optimized_cost:.3f}
[bold yellow]Savings:[/bold yellow] ${result.savings:.3f} ({result.savings_percent:.1f}%)
"""

    console.print(Panel(panel_content, title=f"Cost Optimization - {source}"))

    if result.recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for rec in result.recommendations:
            console.print(f"  [green]•[/green] {rec}")

    if result.optimized_settings:
        console.print("\n[bold]Optimized Settings:[/bold]")
        settings = result.optimized_settings
        console.print(f"  Layer height: {settings.layer_height}mm")
        console.print(f"  Infill: {settings.infill_percent}%")
        console.print(f"  Walls: {settings.wall_count}")


@cost_group.command("compare")
@click.argument("model_path", type=click.Path(exists=True), required=False)
@click.option("--volume", "-v", type=float, help="Volume in cm³ (if no model)")
@click.option("--infill", "-i", type=int, default=20, help="Infill percentage")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def compare_materials(model_path, volume, infill, as_json):
    """Compare costs across different materials."""
    from src.estimator import CostOptimizer, PrintSettings
    import json

    optimizer = CostOptimizer()
    settings = PrintSettings(infill_percent=infill)

    if model_path:
        vol = optimizer._calculate_volume(model_path)
        if vol <= 0:
            vol = 10.0
        source = f"Model: {Path(model_path).name}"
    elif volume:
        vol = volume
        source = f"Volume: {volume} cm³"
    else:
        console.print("[red]Error: Provide either a model path or --volume[/red]")
        return

    comparisons = optimizer.compare_materials(vol, settings)

    if as_json:
        data = {m: e.to_dict() for m, e in comparisons.items()}
        click.echo(json.dumps(data, indent=2))
        return

    table = Table(title=f"Material Comparison - {source}")
    table.add_column("Material", style="cyan")
    table.add_column("Material Cost", justify="right")
    table.add_column("Total Cost", justify="right", style="green")
    table.add_column("Material (g)", justify="right")
    table.add_column("Time (h)", justify="right")

    # Sort by total cost
    sorted_items = sorted(comparisons.items(), key=lambda x: x[1].total_cost)

    for material, estimate in sorted_items:
        table.add_row(
            material.upper(),
            f"${estimate.material_cost:.3f}",
            f"${estimate.total_cost:.3f}",
            f"{estimate.material_grams:.1f}",
            f"{estimate.print_time_hours:.1f}",
        )

    console.print(table)

    cheapest = sorted_items[0]
    console.print(f"\n[green]Cheapest option: {cheapest[0].upper()} at ${cheapest[1].total_cost:.3f}[/green]")


@cost_group.command("config")
@click.option("--pla", type=float, help="PLA cost per gram")
@click.option("--petg", type=float, help="PETG cost per gram")
@click.option("--abs", type=float, help="ABS cost per gram")
@click.option("--tpu", type=float, help="TPU cost per gram")
@click.option("--electricity", type=float, help="Electricity cost per kWh")
@click.option("--machine", type=float, help="Machine cost per hour")
@click.option("--show", is_flag=True, help="Show current config")
def configure(pla, petg, abs, tpu, electricity, machine, show):
    """Configure cost calculation parameters."""
    from src.estimator import CostConfig

    config = CostConfig()

    if show or not any([pla, petg, abs, tpu, electricity, machine]):
        table = Table(title="Cost Configuration")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("PLA cost/gram", f"${config.pla_cost_per_gram:.3f}")
        table.add_row("PETG cost/gram", f"${config.petg_cost_per_gram:.3f}")
        table.add_row("ABS cost/gram", f"${config.abs_cost_per_gram:.3f}")
        table.add_row("TPU cost/gram", f"${config.tpu_cost_per_gram:.3f}")
        table.add_row("Electricity/kWh", f"${config.electricity_cost_per_kwh:.3f}")
        table.add_row("Machine/hour", f"${config.machine_cost_per_hour:.3f}")
        table.add_row("Printer power", f"{config.printer_power_watts}W")

        console.print(table)
    else:
        console.print("[yellow]Note: Configuration changes are not persisted in this version[/yellow]")
        if pla:
            console.print(f"  PLA: ${pla:.3f}/g")
        if petg:
            console.print(f"  PETG: ${petg:.3f}/g")
        if electricity:
            console.print(f"  Electricity: ${electricity:.3f}/kWh")
