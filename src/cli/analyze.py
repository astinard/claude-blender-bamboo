"""Analysis CLI commands for Claude Fab Lab."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path

console = Console()


@click.group()
def analyze() -> None:
    """Model analysis commands."""
    pass


@analyze.command("risk")
@click.argument("file_path")
@click.option("--material", "-m", default="pla", help="Material for analysis")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def analyze_risk(file_path: str, material: str, output_json: bool) -> None:
    """Analyze print failure risk for a model.

    Examines geometry for overhangs, thin walls, bridges, and other
    issues that may cause print failures.

    Example: fab analyze risk model.stl --material abs
    """
    from src.monitoring.failure_predictor import analyze_model_risk, RiskLevel
    import json

    # Validate file exists
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    console.print(f"[bold]Analyzing: {path.name}[/bold]")
    console.print(f"Material: {material.upper()}\n")

    # Run analysis
    with console.status("Analyzing geometry..."):
        risk = analyze_model_risk(str(path), material)

    if output_json:
        console.print(json.dumps(risk.to_dict(), indent=2))
        return

    # Display results
    risk_colors = {
        RiskLevel.LOW: "green",
        RiskLevel.MEDIUM: "yellow",
        RiskLevel.HIGH: "red",
        RiskLevel.CRITICAL: "red bold",
    }

    # Overall risk panel
    color = risk_colors[risk.overall_risk]
    console.print(Panel(
        f"[{color}]{risk.overall_risk.value.upper()}[/{color}]\n"
        f"Success probability: {risk.success_probability * 100:.0f}%\n"
        f"Confidence: {risk.confidence * 100:.0f}%",
        title="[bold]Overall Risk Assessment[/bold]",
    ))

    # Geometry analysis table
    if risk.geometry_result:
        geo = risk.geometry_result
        console.print(f"\n[bold]Model Info:[/bold]")
        console.print(f"  Dimensions: {geo.bounding_box[0]:.1f} x {geo.bounding_box[1]:.1f} x {geo.bounding_box[2]:.1f} mm")
        if geo.volume_mm3 > 0:
            console.print(f"  Volume: {geo.volume_mm3 / 1000:.1f} cm³")
        console.print(f"  Triangles: {geo.triangle_count:,}")

    # Risk factors table
    if risk.risk_factors:
        console.print("\n[bold]Risk Factors:[/bold]")
        table = Table(show_header=True)
        table.add_column("Factor", style="cyan")
        table.add_column("Risk Level")
        table.add_column("Description")
        table.add_column("Mitigation", style="dim")

        for factor in risk.risk_factors:
            color = risk_colors[factor.risk_level]
            table.add_row(
                factor.name,
                f"[{color}]{factor.risk_level.value.upper()}[/{color}]",
                factor.description,
                factor.mitigation or "-",
            )

        console.print(table)

    # Geometry summary
    console.print("\n[bold]Geometry Analysis:[/bold]")
    geo_summary = risk.geometry
    console.print(f"  Overhangs: [{risk_colors[geo_summary.overhang_risk]}]{geo_summary.overhang_risk.value}[/{risk_colors[geo_summary.overhang_risk]}]")
    console.print(f"  Thin Walls: [{risk_colors[geo_summary.thin_wall_risk]}]{geo_summary.thin_wall_risk.value}[/{risk_colors[geo_summary.thin_wall_risk]}]")
    console.print(f"  Bridges: [{risk_colors[geo_summary.bridge_risk]}]{geo_summary.bridge_risk.value}[/{risk_colors[geo_summary.bridge_risk]}]")
    console.print(f"  Mesh Quality: [{risk_colors[geo_summary.manifold_risk]}]{geo_summary.manifold_risk.value}[/{risk_colors[geo_summary.manifold_risk]}]")
    console.print(f"  Supports Required: {'Yes' if geo_summary.support_required else 'No'}")

    # Material risks
    if risk.material_risk:
        mat = risk.material_risk
        console.print(f"\n[bold]Material Risks ({material.upper()}):[/bold]")
        console.print(f"  Warping: [{risk_colors[mat.warping_risk]}]{mat.warping_risk.value}[/{risk_colors[mat.warping_risk]}]")
        console.print(f"  Layer Adhesion: [{risk_colors[mat.adhesion_risk]}]{mat.adhesion_risk.value}[/{risk_colors[mat.adhesion_risk]}]")
        console.print(f"  Stringing: [{risk_colors[mat.stringing_risk]}]{mat.stringing_risk.value}[/{risk_colors[mat.stringing_risk]}]")

    # Warnings
    if risk.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in risk.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")

    # Recommendations
    if risk.recommendations:
        console.print("\n[bold green]Recommendations:[/bold green]")
        for rec in risk.recommendations:
            console.print(f"  [green]✓[/green] {rec}")


@analyze.command("suggest")
@click.argument("file_path")
@click.option("--fix-issues", is_flag=True, help="Automatically fix detected issues")
@click.option("--output", "-o", default=None, help="Output path for fixed model")
def analyze_suggest(file_path: str, fix_issues: bool, output: str) -> None:
    """Get design suggestions for a model.

    Analyzes model geometry and suggests improvements for better printability.

    Example: fab analyze suggest model.stl --fix-issues
    """
    from src.monitoring.failure_predictor import analyze_model_risk

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    console.print(f"[bold]Design Suggestions: {path.name}[/bold]\n")

    # Run analysis
    risk = analyze_model_risk(str(path))

    # Generate suggestions based on analysis
    suggestions = []

    if risk.geometry.support_required:
        suggestions.append({
            "issue": "Overhanging features detected",
            "suggestion": "Reorient model to minimize overhangs, or enable tree supports",
            "auto_fixable": False,
        })

    if risk.geometry.thin_wall_risk.value in ["high", "critical"]:
        suggestions.append({
            "issue": "Thin wall features detected",
            "suggestion": "Increase wall thickness to at least 0.8mm (2 perimeters)",
            "auto_fixable": False,
        })

    if risk.geometry.manifold_risk.value in ["high", "critical"]:
        suggestions.append({
            "issue": "Non-manifold geometry detected",
            "suggestion": "Repair mesh using Blender's 'Make Manifold' or Meshmixer",
            "auto_fixable": False,
        })

    if not suggestions:
        console.print("[green]No significant issues found. Model appears print-ready.[/green]")
        return

    for i, s in enumerate(suggestions, 1):
        console.print(f"\n[bold cyan]{i}. {s['issue']}[/bold cyan]")
        console.print(f"   Suggestion: {s['suggestion']}")
        if s['auto_fixable']:
            console.print("   [green]Can be auto-fixed[/green]")
        else:
            console.print("   [yellow]Manual fix required[/yellow]")

    if fix_issues:
        fixable = [s for s in suggestions if s['auto_fixable']]
        if fixable:
            console.print(f"\n[yellow]Auto-fix coming in Sprint 2 (P4.3)[/yellow]")
        else:
            console.print("\n[yellow]No auto-fixable issues found[/yellow]")


@analyze.command("summary")
@click.argument("file_path")
def analyze_summary(file_path: str) -> None:
    """Quick summary of model printability.

    Example: fab analyze summary model.stl
    """
    from src.monitoring.failure_predictor import analyze_model_risk, RiskLevel

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    risk = analyze_model_risk(str(path))

    risk_emoji = {
        RiskLevel.LOW: "✅",
        RiskLevel.MEDIUM: "⚠️ ",
        RiskLevel.HIGH: "🔶",
        RiskLevel.CRITICAL: "❌",
    }

    emoji = risk_emoji[risk.overall_risk]
    console.print(f"{emoji} {path.name}: {risk.overall_risk.value.upper()} risk ({risk.success_probability * 100:.0f}% success)")

    if risk.geometry.support_required:
        console.print("   └─ Supports required")
