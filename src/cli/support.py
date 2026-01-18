"""Support generation CLI commands for Claude Fab Lab."""

import click
from rich.console import Console
from rich.table import Table
from pathlib import Path

console = Console()


@click.command("supports")
@click.argument("file_path")
@click.option("--type", "-t", "support_type", default="tree",
              type=click.Choice(["normal", "tree", "linear"]),
              help="Support type to generate")
@click.option("--density", "-d", default="normal",
              type=click.Choice(["sparse", "normal", "dense", "solid"]),
              help="Support density")
@click.option("--optimize", "-o", is_flag=True, help="Apply optimization")
@click.option("--goal", "-g", default="balanced",
              type=click.Choice(["material", "strength", "removal", "balanced", "speed"]),
              help="Optimization goal")
@click.option("--compare", "-c", is_flag=True, help="Compare support strategies")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def supports(
    file_path: str,
    support_type: str,
    density: str,
    optimize: bool,
    goal: str,
    compare: bool,
    output_json: bool,
) -> None:
    """Generate optimized support structures.

    Example: fab supports model.stl --type tree --optimize

    Generates support structures for 3D printing with options
    for tree supports and material optimization.
    """
    from src.blender.support_generator import (
        SupportGenerator,
        SupportSettings,
        SupportType,
        SupportDensity,
    )
    from src.blender.support_optimizer import (
        SupportOptimizer,
        OptimizationGoal,
        compare_support_strategies,
    )

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    # Compare mode
    if compare:
        try:
            comparison = compare_support_strategies(str(path))
        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
            return

        if output_json:
            import json
            console.print(json.dumps(comparison, indent=2))
            return

        console.print(f"[bold]Support Strategy Comparison: {path.name}[/bold]\n")

        table = Table()
        table.add_column("Strategy", style="cyan")
        table.add_column("Volume (mm³)", justify="right")
        table.add_column("Material (g)", justify="right")
        table.add_column("Structures", justify="right")
        table.add_column("Savings", justify="right")

        for name, data in comparison["strategies"].items():
            savings = f"{data.get('savings_percent', 0):.0f}%" if "savings_percent" in data else "-"
            table.add_row(
                name,
                f"{data['volume_mm3']:.1f}",
                f"{data['material_grams']:.2f}",
                str(data['structures']),
                savings,
            )

        console.print(table)
        console.print(f"\n[green]Recommendation: {comparison['recommendation']}[/green]")
        console.print(f"[dim]Potential savings: {comparison['potential_savings']}[/dim]")
        return

    # Generate supports
    try:
        settings = SupportSettings(
            support_type=SupportType(support_type),
            density=SupportDensity(density),
        )
        generator = SupportGenerator(settings)
        result = generator.generate(str(path))
    except Exception as e:
        console.print(f"[red]Generation failed: {e}[/red]")
        return

    # Optimize if requested
    opt_result = None
    if optimize:
        try:
            optimizer = SupportOptimizer()
            opt_result = optimizer.optimize(result, goal=OptimizationGoal(goal))
            result = opt_result.optimized
        except Exception as e:
            console.print(f"[yellow]Optimization failed: {e}[/yellow]")

    # Output JSON
    if output_json:
        import json
        data = {
            "file_path": result.file_path,
            "support_type": support_type,
            "structures": len(result.structures),
            "total_volume_mm3": result.total_support_volume,
            "total_material_grams": result.total_material_grams,
            "material_savings_percent": result.material_savings_percent,
        }
        if opt_result:
            data["optimization"] = {
                "goal": goal,
                "reduction_percent": opt_result.reduction_percent,
                "supports_merged": opt_result.supports_merged,
                "supports_removed": opt_result.supports_removed,
            }
        console.print(json.dumps(data, indent=2))
        return

    # Display results
    console.print(f"[bold]Support Generation: {path.name}[/bold]\n")
    console.print(f"  Type: {support_type}")
    console.print(f"  Density: {density}")
    console.print(f"  Structures: {len(result.structures)}")
    console.print(f"  Total Volume: {result.total_support_volume:.1f} mm³")
    console.print(f"  Material: {result.total_material_grams:.2f}g")

    if result.material_savings_percent > 0:
        console.print(f"  [green]Savings: {result.material_savings_percent:.0f}% vs normal supports[/green]")

    # Optimization details
    if opt_result:
        console.print(f"\n[bold]Optimization ({goal}):[/bold]")
        console.print(f"  Supports merged: {opt_result.supports_merged}")
        console.print(f"  Supports removed: {opt_result.supports_removed}")
        console.print(f"  Supports reinforced: {opt_result.supports_reinforced}")
        console.print(f"  [green]Material reduction: {opt_result.reduction_percent:.0f}%[/green]")

        if opt_result.warnings:
            console.print(f"\n[yellow]Warnings:[/yellow]")
            for warn in opt_result.warnings:
                console.print(f"  ⚠ {warn}")

        if opt_result.recommendations:
            console.print(f"\n[dim]Recommendations:[/dim]")
            for rec in opt_result.recommendations:
                console.print(f"  • {rec}")

    # Structure details (if verbose or few structures)
    if len(result.structures) <= 5:
        console.print(f"\n[bold]Support Structures:[/bold]")

        table = Table(show_header=True)
        table.add_column("ID", style="cyan")
        table.add_column("Type")
        table.add_column("Height (mm)", justify="right")
        table.add_column("Volume (mm³)", justify="right")
        table.add_column("Material (g)", justify="right")

        for struct in result.structures:
            table.add_row(
                struct.structure_id,
                struct.support_type.value,
                f"{struct.height:.1f}",
                f"{struct.volume:.1f}",
                f"{struct.estimated_material_grams:.2f}",
            )

        console.print(table)

    # Next steps
    console.print(f"\n[dim]Next steps:[/dim]")
    console.print(f"  fab queue add {path} --with-supports")
    console.print(f"  fab preview {path} --show-supports")
