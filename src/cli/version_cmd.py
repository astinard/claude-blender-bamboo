"""Version history CLI commands for Claude Fab Lab."""

import click
from rich.console import Console
from rich.table import Table
from pathlib import Path

console = Console()


@click.group()
def version() -> None:
    """Design version history commands."""
    pass


@version.command("save")
@click.argument("file_path")
@click.option("--message", "-m", required=True, help="Version message")
@click.option("--design-id", "-d", default=None, help="Design ID (auto-detected if not provided)")
def version_save(file_path: str, message: str, design_id: str) -> None:
    """Save a new version of a design.

    Example: fab version save model.stl -m "Added mounting holes"
    """
    from src.version.history import VersionHistory

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return

    history = VersionHistory()

    try:
        ver = history.save_version(str(path), message, design_id=design_id)
        console.print(f"[green]Saved version {ver.version_id}[/green]")
        console.print(f"  Version: v{ver.version_number}")
        console.print(f"  Message: {message}")
        console.print(f"  Branch: {ver.branch}")
        console.print(f"  Hash: {ver.file_hash[:12]}...")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@version.command("list")
@click.argument("file_path", required=False)
@click.option("--design-id", "-d", default=None, help="Design ID")
@click.option("--branch", "-b", default=None, help="Branch filter")
@click.option("--limit", "-n", default=10, help="Max versions to show")
def version_list(file_path: str, design_id: str, branch: str, limit: int) -> None:
    """List versions of a design.

    Example: fab version list model.stl
    """
    from src.version.history import VersionHistory

    history = VersionHistory()

    # Find design ID
    if design_id is None and file_path:
        design_id = history.get_design_by_path(file_path)
        if design_id is None:
            console.print(f"[yellow]No version history for {file_path}[/yellow]")
            console.print("Save a version first with: fab version save <file> -m 'message'")
            return

    if design_id is None:
        # List all designs
        designs = history.list_designs()
        if not designs:
            console.print("[yellow]No designs registered[/yellow]")
            return

        table = Table(title="Registered Designs")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Branch")
        table.add_column("Versions")

        for design in designs:
            versions = history.get_versions(design["id"])
            table.add_row(
                design["id"],
                design["name"],
                design["current_branch"],
                str(len(versions)),
            )

        console.print(table)
        return

    # List versions for specific design
    design = history.get_design(design_id)
    if design is None:
        console.print(f"[red]Design {design_id} not found[/red]")
        return

    versions = history.get_versions(design_id, branch)
    if not versions:
        console.print(f"[yellow]No versions found[/yellow]")
        return

    table = Table(title=f"Version History: {design['name']}")
    table.add_column("Ver", style="dim")
    table.add_column("ID", style="cyan")
    table.add_column("Message")
    table.add_column("Branch")
    table.add_column("Date")
    table.add_column("Tags")

    for ver in versions[:limit]:
        is_head = ver.version_id == design["head"]
        id_display = f"[green]{ver.version_id}[/green]" if is_head else ver.version_id

        table.add_row(
            f"v{ver.version_number}",
            id_display,
            ver.message[:30],
            ver.branch,
            ver.timestamp[:10],
            ", ".join(ver.tags) if ver.tags else "-",
        )

    console.print(table)

    if is_head := design["head"]:
        console.print(f"\n[dim]HEAD: {is_head}[/dim]")


@version.command("restore")
@click.argument("version_id")
@click.option("--output", "-o", default=None, help="Output path (default: original location)")
def version_restore(version_id: str, output: str) -> None:
    """Restore a specific version.

    Example: fab version restore abc123 -o restored_model.stl
    """
    from src.version.history import VersionHistory

    history = VersionHistory()
    ver = history.get_version(version_id)

    if ver is None:
        console.print(f"[red]Version {version_id} not found[/red]")
        return

    # Determine output path
    if output is None:
        design = history.get_design(ver.design_id)
        if design:
            output = design["original_path"]
        else:
            console.print("[red]No output path specified[/red]")
            return

    if history.restore_version(version_id, output):
        console.print(f"[green]Restored version v{ver.version_number} to {output}[/green]")
    else:
        console.print(f"[red]Failed to restore version[/red]")


@version.command("diff")
@click.argument("version_a")
@click.argument("version_b")
def version_diff(version_a: str, version_b: str) -> None:
    """Compare two versions of a design.

    Example: fab version diff abc123 def456
    """
    from src.version.history import VersionHistory

    history = VersionHistory()

    diff = history.diff_versions(version_a, version_b)
    if diff is None:
        console.print("[red]One or both versions not found[/red]")
        return

    va = history.get_version(version_a)
    vb = history.get_version(version_b)

    console.print(f"[bold]Comparing versions[/bold]")
    console.print(f"  {version_a} (v{va.version_number}): {va.message}")
    console.print(f"  {version_b} (v{vb.version_number}): {vb.message}")
    console.print()

    if diff.file_changed:
        console.print(f"[yellow]File content changed[/yellow]")
        if diff.size_diff > 0:
            console.print(f"  Size: +{diff.size_diff} bytes")
        elif diff.size_diff < 0:
            console.print(f"  Size: {diff.size_diff} bytes")
        else:
            console.print(f"  Size: unchanged")
    else:
        console.print(f"[green]File content identical[/green]")

    if diff.metadata_changes:
        console.print(f"\n[bold]Metadata changes:[/bold]")
        for key, (old, new) in diff.metadata_changes.items():
            console.print(f"  {key}: {old} -> {new}")


@version.command("branch")
@click.argument("design_id")
@click.argument("branch_name")
@click.option("--from", "from_version", default=None, help="Version to branch from")
def version_branch(design_id: str, branch_name: str, from_version: str) -> None:
    """Create a new branch for a design.

    Example: fab version branch abc123 experimental
    """
    from src.version.history import VersionHistory

    history = VersionHistory()

    if history.create_branch(design_id, branch_name, from_version):
        console.print(f"[green]Created branch {branch_name}[/green]")
    else:
        console.print(f"[red]Failed to create branch[/red]")


@version.command("tag")
@click.argument("version_id")
@click.argument("tag")
def version_tag(version_id: str, tag: str) -> None:
    """Add a tag to a version.

    Example: fab version tag abc123 release-1.0
    """
    from src.version.history import VersionHistory

    history = VersionHistory()

    if history.tag_version(version_id, tag):
        console.print(f"[green]Tagged version {version_id} as '{tag}'[/green]")
    else:
        console.print(f"[red]Version not found[/red]")


@version.command("show")
@click.argument("version_id")
def version_show(version_id: str) -> None:
    """Show details of a specific version.

    Example: fab version show abc123
    """
    from src.version.history import VersionHistory

    history = VersionHistory()
    ver = history.get_version(version_id)

    if ver is None:
        console.print(f"[red]Version {version_id} not found[/red]")
        return

    design = history.get_design(ver.design_id)

    console.print(f"[bold]Version {ver.version_id}[/bold]")
    console.print(f"  Design: {design['name'] if design else 'Unknown'}")
    console.print(f"  Version: v{ver.version_number}")
    console.print(f"  Message: {ver.message}")
    console.print(f"  Branch: {ver.branch}")
    console.print(f"  Timestamp: {ver.timestamp}")
    console.print(f"  File Hash: {ver.file_hash}")
    console.print(f"  File Size: {ver.file_size} bytes")
    if ver.parent_id:
        console.print(f"  Parent: {ver.parent_id}")
    if ver.tags:
        console.print(f"  Tags: {', '.join(ver.tags)}")
    if ver.metadata:
        console.print(f"  Metadata: {ver.metadata}")
