"""CLI commands for photogrammetry."""

import asyncio
import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel

from src.capture.photogrammetry import ProcessingStage

console = Console()


@click.group()
def photogrammetry():
    """Photogrammetry commands for photo-to-3D conversion."""
    pass


@photogrammetry.command()
@click.argument("images", nargs=-1, required=True)
@click.option("--project", "-p", help="Project name")
@click.option("--quality", "-q", default="normal",
              type=click.Choice(["draft", "normal", "high", "ultra"]),
              help="Quality preset")
@click.option("--format", "-f", "output_format", default="obj",
              type=click.Choice(["obj", "stl", "ply"]),
              help="Output format")
@click.pass_context
def process(
    ctx: click.Context,
    images: tuple,
    project: str,
    quality: str,
    output_format: str,
) -> None:
    """Process images to create 3D model.

    Examples:
        cli photogrammetry process image1.jpg image2.jpg image3.jpg
        cli photogrammetry process *.jpg --project my_scan --quality high
    """
    from src.capture.photogrammetry import PhotogrammetryPipeline, PipelineConfig

    # Expand glob patterns
    image_paths = []
    for img in images:
        p = Path(img)
        if "*" in img:
            image_paths.extend(str(f) for f in Path(".").glob(img))
        elif p.exists():
            image_paths.append(str(p.absolute()))
        else:
            console.print(f"[yellow]Warning: Image not found: {img}[/yellow]")

    if len(image_paths) < 3:
        console.print("[red]Error: Need at least 3 valid images[/red]")
        return

    console.print(f"Processing {len(image_paths)} images...")

    config = PipelineConfig(quality=quality, output_format=output_format)

    stage_names = {
        ProcessingStage.INIT: "Initializing",
        ProcessingStage.FEATURE_EXTRACTION: "Extracting features",
        ProcessingStage.FEATURE_MATCHING: "Matching features",
        ProcessingStage.STRUCTURE_FROM_MOTION: "Structure from motion",
        ProcessingStage.DEPTH_MAP: "Computing depth maps",
        ProcessingStage.MESHING: "Generating mesh",
        ProcessingStage.TEXTURING: "Applying textures",
        ProcessingStage.EXPORT: "Exporting",
        ProcessingStage.COMPLETE: "Complete",
    }

    current_stage = [ProcessingStage.INIT]

    def progress_callback(stage: ProcessingStage, percent: float):
        current_stage[0] = stage

    pipeline = PhotogrammetryPipeline(config=config, progress_callback=progress_callback)

    if not pipeline.meshroom_available:
        console.print("[yellow]Note: Meshroom not found, using fallback processing[/yellow]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=None)

        async def run():
            result = await pipeline.process(image_paths, project)
            return result

        result = asyncio.run(run())

    if result.success:
        console.print(Panel(
            f"[bold green]Processing Complete[/bold green]\n\n"
            f"Mesh: {result.mesh_path}\n"
            f"Images: {result.camera_count} ({result.matched_images} matched)\n"
            f"Vertices: {result.vertex_count:,}\n"
            f"Faces: {result.face_count:,}\n"
            f"Time: {result.processing_time:.1f}s",
            title="Photogrammetry Result",
        ))
    else:
        console.print(f"[red]Processing failed: {result.error_message}[/red]")
        console.print(f"Stage completed: {result.stage_completed.value}")


@photogrammetry.command()
@click.pass_context
def list(ctx: click.Context) -> None:
    """List photogrammetry projects.

    Examples:
        cli photogrammetry list
    """
    from src.capture.photogrammetry import PhotogrammetryPipeline

    pipeline = PhotogrammetryPipeline()
    projects = pipeline.list_projects()

    if not projects:
        console.print("[dim]No photogrammetry projects found[/dim]")
        return

    table = Table(title="Photogrammetry Projects")
    table.add_column("Name")
    table.add_column("Created")
    table.add_column("Vertices")
    table.add_column("Faces")

    for proj in projects:
        table.add_row(
            proj["name"],
            proj.get("created", "-")[:10],
            f"{proj.get('vertex_count', 0):,}",
            f"{proj.get('face_count', 0):,}",
        )

    console.print(table)


@photogrammetry.command()
@click.argument("project_name")
@click.pass_context
def info(ctx: click.Context, project_name: str) -> None:
    """Show project information.

    Examples:
        cli photogrammetry info my_scan
    """
    from src.capture.photogrammetry import PhotogrammetryPipeline

    pipeline = PhotogrammetryPipeline()
    proj = pipeline.get_project_info(project_name)

    if not proj:
        console.print(f"[red]Project not found: {project_name}[/red]")
        return

    console.print(Panel(
        f"[bold]Name:[/bold] {proj['name']}\n"
        f"[bold]Path:[/bold] {proj['path']}\n"
        f"[bold]Created:[/bold] {proj.get('created', '-')}\n"
        f"[bold]Vertices:[/bold] {proj.get('vertex_count', 0):,}\n"
        f"[bold]Faces:[/bold] {proj.get('face_count', 0):,}\n"
        f"[bold]Mesh Files:[/bold] {', '.join(proj.get('mesh_files', []))}",
        title=f"Project: {project_name}",
    ))


@photogrammetry.command()
@click.argument("project_name")
@click.option("--confirm", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete(ctx: click.Context, project_name: str, confirm: bool) -> None:
    """Delete a photogrammetry project.

    Examples:
        cli photogrammetry delete my_scan
        cli photogrammetry delete my_scan -y
    """
    from src.capture.photogrammetry import PhotogrammetryPipeline

    pipeline = PhotogrammetryPipeline()

    if not pipeline.get_project_info(project_name):
        console.print(f"[red]Project not found: {project_name}[/red]")
        return

    if not confirm:
        if not click.confirm(f"Delete project '{project_name}'?"):
            console.print("Cancelled")
            return

    if pipeline.delete_project(project_name):
        console.print(f"[green]Deleted project: {project_name}[/green]")
    else:
        console.print(f"[red]Failed to delete project[/red]")


@photogrammetry.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show photogrammetry system status.

    Examples:
        cli photogrammetry status
    """
    from src.capture.photogrammetry import PhotogrammetryPipeline

    pipeline = PhotogrammetryPipeline()

    console.print("[bold]Photogrammetry Status[/bold]")
    console.print()

    if pipeline.meshroom_available:
        console.print("[green]\u2714[/green] Meshroom/AliceVision: Available")
    else:
        console.print("[yellow]\u26a0[/yellow] Meshroom/AliceVision: Not found (using fallback)")

    console.print(f"Output directory: {pipeline.output_dir}")

    projects = pipeline.list_projects()
    console.print(f"Projects: {len(projects)}")
