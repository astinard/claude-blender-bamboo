"""Materials CLI commands for Claude Fab Lab."""

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def materials() -> None:
    """Material management commands."""
    pass


@materials.command("list")
def list_materials() -> None:
    """List all available materials in the database."""
    from src.materials.material_db import MATERIAL_DATABASE

    table = Table(title="Available Materials")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Nozzle Temp", style="yellow")
    table.add_column("Bed Temp", style="yellow")
    table.add_column("Enclosure", style="magenta")
    table.add_column("Notes", style="white")

    for key, mat in MATERIAL_DATABASE.items():
        notes = []
        if mat.properties.abrasive:
            notes.append("Abrasive")
        if mat.properties.hygroscopic:
            notes.append("Hygroscopic")
        if mat.properties.toxic_fumes:
            notes.append("Ventilation needed")

        table.add_row(
            mat.name,
            mat.material_type.value,
            f"{mat.properties.nozzle_temp_min}-{mat.properties.nozzle_temp_max}°C",
            f"{mat.properties.bed_temp_min}-{mat.properties.bed_temp_max}°C",
            "Yes" if mat.properties.requires_enclosure else "No",
            ", ".join(notes) if notes else "-",
        )

    console.print(table)


@materials.command("check")
@click.argument("material_a")
@click.argument("material_b")
def check_compatibility(material_a: str, material_b: str) -> None:
    """Check compatibility between two materials.

    Example: fab materials check pla petg
    """
    from src.materials.compatibility import check_compatibility as do_check, CompatibilityLevel

    result = do_check(material_a, material_b)

    # Color based on level
    level_colors = {
        CompatibilityLevel.EXCELLENT: "green",
        CompatibilityLevel.GOOD: "green",
        CompatibilityLevel.FAIR: "yellow",
        CompatibilityLevel.POOR: "red",
        CompatibilityLevel.INCOMPATIBLE: "red bold",
    }
    color = level_colors.get(result.level, "white")

    console.print(f"\n[bold]Compatibility: {material_a.upper()} + {material_b.upper()}[/bold]")
    console.print(f"Result: [{color}]{result.level.value.upper()}[/{color}]")

    if result.issues:
        console.print("\n[bold]Issues:[/bold]")
        for issue in result.issues:
            issue_color = level_colors.get(issue.severity, "white")
            console.print(f"  [{issue_color}]•[/{issue_color}] {issue.message}")
            if issue.suggestion:
                console.print(f"    [dim]→ {issue.suggestion}[/dim]")

    if result.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in result.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")

    if result.recommendations:
        console.print("\n[bold green]Recommendations:[/bold green]")
        for rec in result.recommendations:
            console.print(f"  [green]✓[/green] {rec}")


@materials.command("multi-check")
@click.argument("materials", nargs=-1, required=True)
def multi_check(materials: tuple) -> None:
    """Check compatibility of multiple materials.

    Example: fab materials multi-check pla petg pva
    """
    from src.materials.compatibility import check_multi_material_compatibility, CompatibilityLevel

    if len(materials) < 2:
        console.print("[red]Error: At least 2 materials required[/red]")
        return

    result = check_multi_material_compatibility(list(materials))

    level_colors = {
        CompatibilityLevel.EXCELLENT: "green",
        CompatibilityLevel.GOOD: "green",
        CompatibilityLevel.FAIR: "yellow",
        CompatibilityLevel.POOR: "red",
        CompatibilityLevel.INCOMPATIBLE: "red bold",
    }
    color = level_colors.get(result.overall_compatibility, "white")

    console.print(f"\n[bold]Multi-Material Compatibility Analysis[/bold]")
    console.print(f"Materials: {', '.join(materials)}")
    console.print(f"Overall: [{color}]{result.overall_compatibility.value.upper()}[/{color}]")

    # AMS Recommendations
    if result.ams_recommendations:
        console.print("\n[bold]AMS Slot Recommendations:[/bold]")
        for rec in result.ams_recommendations:
            console.print(f"  Slot {rec.slot}: [cyan]{rec.material.upper()}[/cyan] - {rec.reason}")

    # Print settings
    if result.print_settings:
        console.print("\n[bold]Recommended Print Settings:[/bold]")
        if result.print_settings.get("nozzle_temp"):
            console.print(f"  Nozzle Temperature: {result.print_settings['nozzle_temp']}°C")
        if result.print_settings.get("bed_temp"):
            console.print(f"  Bed Temperature: {result.print_settings['bed_temp']}°C")
        if result.print_settings.get("enclosure_required"):
            console.print("  [yellow]Enclosure: Required[/yellow]")
        if result.print_settings.get("speed_modifier", 1.0) < 1.0:
            console.print(f"  Speed: {result.print_settings['speed_modifier'] * 100:.0f}% of normal")

    # Warnings
    if result.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in result.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")

    # Pairwise details
    if result.pairwise_results and len(result.pairwise_results) > 1:
        console.print("\n[bold]Pairwise Compatibility:[/bold]")
        for pair in result.pairwise_results:
            pair_color = level_colors.get(pair.level, "white")
            console.print(f"  {pair.material_a} + {pair.material_b}: [{pair_color}]{pair.level.value}[/{pair_color}]")


@materials.command("suggest-support")
@click.argument("material")
def suggest_support(material: str) -> None:
    """Suggest the best support material for a given main material.

    Example: fab materials suggest-support abs
    """
    from src.materials.compatibility import suggest_support_material
    from src.materials.material_db import get_material

    mat = get_material(material)
    if mat is None:
        console.print(f"[red]Unknown material: {material}[/red]")
        return

    support = suggest_support_material(material)

    console.print(f"\n[bold]Support Material for {mat.name}[/bold]")
    if support:
        support_mat = get_material(support)
        if support_mat:
            console.print(f"Recommended: [green]{support_mat.name}[/green]")
            if support == "pva":
                console.print("  [dim]Water-soluble support - dissolves in water[/dim]")
            elif support == "hips":
                console.print("  [dim]Limonene-soluble support - dissolves in limonene[/dim]")
        else:
            console.print(f"Recommended: [green]{support}[/green]")
    else:
        console.print("[yellow]No specific support material recommended[/yellow]")
        console.print("  [dim]Use same material or generic support[/dim]")

    if mat.properties.compatible_supports:
        console.print(f"\n[dim]All compatible supports: {', '.join(mat.properties.compatible_supports)}[/dim]")


# Inventory commands
@materials.group()
def inventory() -> None:
    """Material inventory management."""
    pass


@inventory.command("list")
def inventory_list() -> None:
    """List all spools in inventory."""
    from src.materials.inventory import InventoryManager

    mgr = InventoryManager()
    spools = mgr.list_all()

    if not spools:
        console.print("[yellow]No spools in inventory[/yellow]")
        console.print("Add spools with: fab materials inventory add")
        return

    table = Table(title="Filament Inventory")
    table.add_column("ID", style="cyan")
    table.add_column("Material", style="green")
    table.add_column("Brand")
    table.add_column("Color", style="magenta")
    table.add_column("Remaining", style="yellow")
    table.add_column("Value", style="green")

    for spool in spools:
        remaining = f"{spool.remaining_grams:.0f}g ({spool.remaining_percent:.0f}%)"
        if spool.remaining_percent <= 20:
            remaining = f"[red]{remaining}[/red]"
        elif spool.remaining_percent <= 50:
            remaining = f"[yellow]{remaining}[/yellow]"

        table.add_row(
            spool.id,
            spool.material.upper(),
            spool.brand,
            spool.color,
            remaining,
            f"${spool.remaining_cost:.2f}",
        )

    console.print(table)

    # Summary
    summary = mgr.get_inventory_summary()
    console.print(f"\n[bold]Total:[/bold] {summary['total_spools']} spools, {summary['total_weight_grams']:.0f}g, ${summary['total_value']:.2f}")

    # Low stock alerts
    alerts = mgr.get_low_stock_alerts()
    if alerts:
        console.print(f"\n[bold red]Low Stock Alerts ({len(alerts)}):[/bold red]")
        for alert in alerts:
            console.print(f"  [red]⚠[/red] {alert.message}")


@inventory.command("add")
@click.option("--material", "-m", required=True, help="Material type (e.g., pla, petg)")
@click.option("--brand", "-b", required=True, help="Brand name")
@click.option("--color", "-c", required=True, help="Filament color")
@click.option("--weight", "-w", default=1000, type=float, help="Spool weight in grams (default: 1000)")
@click.option("--cost", default=25.0, type=float, help="Cost per kg (default: 25.0)")
@click.option("--notes", "-n", default="", help="Additional notes")
def inventory_add(material: str, brand: str, color: str, weight: float, cost: float, notes: str) -> None:
    """Add a new spool to inventory.

    Example: fab materials inventory add -m pla -b Bambu -c "Jade White" -w 1000 --cost 30
    """
    from src.materials.inventory import InventoryManager
    from src.materials.material_db import get_material

    # Validate material
    mat = get_material(material)
    if mat is None:
        console.print(f"[yellow]Warning: Unknown material type '{material}'[/yellow]")
        console.print("Will add anyway, but compatibility checks may not work")

    mgr = InventoryManager()
    spool = mgr.add_spool(
        material=material,
        brand=brand,
        color=color,
        weight_grams=weight,
        cost_per_kg=cost,
        notes=notes,
    )

    console.print(f"[green]Added spool {spool.id}[/green]")
    console.print(f"  {brand} {material.upper()} ({color})")
    console.print(f"  {weight}g @ ${cost}/kg = ${spool.remaining_cost:.2f}")


@inventory.command("remove")
@click.argument("spool_id")
def inventory_remove(spool_id: str) -> None:
    """Remove a spool from inventory."""
    from src.materials.inventory import InventoryManager

    mgr = InventoryManager()
    if mgr.remove_spool(spool_id):
        console.print(f"[green]Removed spool {spool_id}[/green]")
    else:
        console.print(f"[red]Spool {spool_id} not found[/red]")


@inventory.command("use")
@click.argument("spool_id")
@click.argument("grams", type=float)
def inventory_use(spool_id: str, grams: float) -> None:
    """Deduct material usage from a spool.

    Example: fab materials inventory use abc123 50.5
    """
    from src.materials.inventory import InventoryManager

    mgr = InventoryManager()
    spool = mgr.get_spool(spool_id)

    if spool is None:
        console.print(f"[red]Spool {spool_id} not found[/red]")
        return

    if mgr.use_material(spool_id, grams):
        spool = mgr.get_spool(spool_id)
        console.print(f"[green]Used {grams}g from spool {spool_id}[/green]")
        console.print(f"  Remaining: {spool.remaining_grams:.1f}g ({spool.remaining_percent:.1f}%)")
    else:
        console.print(f"[red]Insufficient material in spool {spool_id}[/red]")
        console.print(f"  Available: {spool.remaining_grams:.1f}g, Requested: {grams}g")
