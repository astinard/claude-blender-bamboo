"""Design suggestion CLI commands for Claude Fab Lab."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path

console = Console()


@click.command("suggest")
@click.argument("file_path")
@click.option("--fix-issues", is_flag=True, help="Show auto-fix suggestions")
@click.option("--orientation", "-o", is_flag=True, help="Show orientation recommendations")
@click.option("--fillets", "-f", is_flag=True, help="Show fillet/chamfer suggestions")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def suggest(file_path: str, fix_issues: bool, orientation: bool, fillets: bool, verbose: bool, output_json: bool) -> None:
    """Analyze a model and suggest design improvements.

    Example: fab suggest model.stl --fix-issues

    Checks for:
    - Overhang issues that may require supports
    - Thin walls that may not print correctly
    - Optimal print orientation
    - Sharp edges that could benefit from fillets
    """
    from src.blender.design_advisor import DesignAdvisor, IssueSeverity

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    advisor = DesignAdvisor()

    try:
        advice = advisor.analyze(str(path))
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        return

    if output_json:
        import json
        from dataclasses import asdict

        data = {
            "file_path": advice.file_path,
            "printability_score": advice.printability_score,
            "support_required": advice.support_required,
            "issues": [
                {
                    "category": i.category.value,
                    "severity": i.severity.value,
                    "description": i.description,
                    "fix_suggestion": i.fix_suggestion,
                }
                for i in advice.issues
            ],
            "bounding_box": advice.bounding_box,
            "estimated_print_time_hours": advice.estimated_print_time_hours,
            "estimated_material_grams": advice.estimated_material_grams,
        }
        console.print(json.dumps(data, indent=2))
        return

    # Header with score
    score = advice.printability_score
    if score >= 80:
        score_color = "green"
        score_label = "Good"
    elif score >= 60:
        score_color = "yellow"
        score_label = "Fair"
    elif score >= 40:
        score_color = "orange1"
        score_label = "Poor"
    else:
        score_color = "red"
        score_label = "Critical"

    console.print(Panel(
        f"[bold]Printability Score: [{score_color}]{score:.0f}/100[/{score_color}][/bold] ({score_label})",
        title=f"Design Analysis: {path.name}",
        subtitle=f"Supports: {'Required' if advice.support_required else 'Not needed'}",
    ))

    # Model info
    if verbose:
        bbox = advice.bounding_box
        console.print(f"\n[bold]Model Information:[/bold]")
        console.print(f"  Dimensions: {bbox[0]:.1f} × {bbox[1]:.1f} × {bbox[2]:.1f} mm")
        console.print(f"  Est. Print Time: {advice.estimated_print_time_hours:.1f} hours")
        console.print(f"  Est. Material: {advice.estimated_material_grams:.1f}g")
        console.print(f"  Recommended Layer: {advice.recommended_layer_height}mm")
        console.print(f"  Recommended Infill: {advice.recommended_infill}%")

    # Issues table
    if advice.issues:
        console.print(f"\n[bold]Issues Found ({len(advice.issues)}):[/bold]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Severity", width=10)
        table.add_column("Category", width=12)
        table.add_column("Description")
        if fix_issues:
            table.add_column("Suggestion")

        severity_colors = {
            IssueSeverity.INFO: "cyan",
            IssueSeverity.WARNING: "yellow",
            IssueSeverity.ERROR: "red",
            IssueSeverity.CRITICAL: "bold red",
        }

        for issue in advice.issues:
            color = severity_colors.get(issue.severity, "white")
            row = [
                f"[{color}]{issue.severity.value.upper()}[/{color}]",
                issue.category.value,
                issue.description,
            ]

            if fix_issues:
                row.append(issue.fix_suggestion or "-")

            table.add_row(*row)

        console.print(table)

        # Summary
        summary = advice.issue_summary
        console.print(f"\n[dim]Issues: {summary[IssueSeverity.CRITICAL]} critical, "
                     f"{summary[IssueSeverity.ERROR]} errors, "
                     f"{summary[IssueSeverity.WARNING]} warnings, "
                     f"{summary[IssueSeverity.INFO]} info[/dim]")
    else:
        console.print("\n[green]✓ No issues detected[/green]")

    # Orientation suggestions
    if orientation and advice.orientation_suggestions:
        console.print(f"\n[bold]Orientation Suggestions:[/bold]")

        for i, orient in enumerate(advice.orientation_suggestions[:3], 1):
            is_recommended = orient == advice.recommended_orientation
            marker = " [green](Recommended)[/green]" if is_recommended else ""

            console.print(f"\n  {i}. Rotate X={orient.rotation_x}°, Y={orient.rotation_y}°, Z={orient.rotation_z}°{marker}")
            console.print(f"     [green]Benefits:[/green] {', '.join(orient.benefits)}")
            if orient.drawbacks:
                console.print(f"     [yellow]Drawbacks:[/yellow] {', '.join(orient.drawbacks)}")
            if orient.support_reduction_percent > 0:
                console.print(f"     Support reduction: ~{orient.support_reduction_percent:.0f}%")
            console.print(f"     Confidence: {orient.confidence*100:.0f}%")

    # Fillet suggestions
    if fillets and advice.fillet_suggestions:
        console.print(f"\n[bold]Fillet/Chamfer Suggestions:[/bold]")

        for fillet in advice.fillet_suggestions[:5]:
            loc = fillet.location
            reason_desc = {
                "adhesion": "Improve bed adhesion",
                "stress_concentration": "Reduce stress concentration",
                "aesthetic": "Improve appearance",
            }
            console.print(f"  • At ({loc[0]:.1f}, {loc[1]:.1f}, {loc[2]:.1f}): "
                         f"Add {fillet.suggested_radius}mm fillet ({reason_desc.get(fillet.reason, fillet.reason)})")

    # Final recommendations
    if advice.has_critical_issues:
        console.print("\n[bold red]⚠ Critical issues must be addressed before printing![/bold red]")
    elif advice.has_errors:
        console.print("\n[yellow]⚡ Review error-level issues before printing[/yellow]")
    elif advice.support_required:
        console.print("\n[cyan]ℹ Model will print, but supports are recommended[/cyan]")
    else:
        console.print("\n[green]✓ Model is ready to print[/green]")
