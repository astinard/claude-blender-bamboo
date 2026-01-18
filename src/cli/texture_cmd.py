"""CLI commands for texture capture."""

import asyncio
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@click.group()
def texture():
    """Texture capture commands."""
    pass


@texture.command()
@click.argument("mesh")
@click.argument("images", nargs=-1, required=True)
@click.option("--project", "-p", help="Project name")
@click.option("--resolution", "-r", default=2048, help="Texture resolution")
@click.option("--format", "-f", "output_format", default="png",
              type=click.Choice(["png", "jpg", "tiff"]),
              help="Output format")
@click.option("--types", "-t", multiple=True,
              type=click.Choice(["diffuse", "normal", "roughness", "metallic", "ao", "height"]),
              help="Texture types to generate")
@click.pass_context
def capture(
    ctx: click.Context,
    mesh: str,
    images: tuple,
    project: str,
    resolution: int,
    output_format: str,
    types: tuple,
) -> None:
    """Capture textures from images and project onto mesh.

    Examples:
        cli texture capture model.obj image1.jpg image2.jpg
        cli texture capture model.stl *.jpg --resolution 4096
        cli texture capture model.obj photos/*.jpg --types diffuse --types normal
    """
    from src.capture.texture_capture import (
        TextureCapturer, TextureConfig, TextureFormat, TextureType
    )

    mesh_path = Path(mesh)
    if not mesh_path.exists():
        console.print(f"[red]Error: Mesh file not found: {mesh}[/red]")
        return

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

    if not image_paths:
        console.print("[red]Error: No valid images found[/red]")
        return

    console.print(f"Processing {len(image_paths)} images onto mesh...")

    # Configure texture types
    texture_types = [TextureType(t) for t in types] if types else [TextureType.DIFFUSE]

    config = TextureConfig(
        width=resolution,
        height=resolution,
        output_format=TextureFormat(output_format),
        texture_types=texture_types,
    )

    capturer = TextureCapturer(config=config)

    async def run():
        return await capturer.capture_from_images(
            str(mesh_path.absolute()),
            image_paths,
            project,
        )

    result = asyncio.run(run())

    if result.success:
        texture_list = "\n".join(
            f"  {k}: {Path(v).name}" for k, v in result.texture_paths.items()
        )
        console.print(Panel(
            f"[bold green]Texture Capture Complete[/bold green]\n\n"
            f"Mesh: {result.mesh_path}\n"
            f"Resolution: {result.resolution[0]}x{result.resolution[1]}\n"
            f"Time: {result.processing_time:.1f}s\n\n"
            f"Textures:\n{texture_list}",
            title="Texture Result",
        ))
    else:
        console.print(f"[red]Texture capture failed: {result.error_message}[/red]")


@texture.command()
@click.pass_context
def list(ctx: click.Context) -> None:
    """List texture capture projects.

    Examples:
        cli texture list
    """
    from src.capture.texture_capture import TextureCapturer

    capturer = TextureCapturer()
    projects = capturer.list_projects()

    if not projects:
        console.print("[dim]No texture projects found[/dim]")
        return

    table = Table(title="Texture Projects")
    table.add_column("Name")
    table.add_column("Created")
    table.add_column("Textures")

    for proj in projects:
        table.add_row(
            proj["name"],
            proj.get("created", "-")[:10],
            ", ".join(proj.get("textures", [])),
        )

    console.print(table)


@texture.command()
@click.argument("project_name")
@click.pass_context
def info(ctx: click.Context, project_name: str) -> None:
    """Show texture project information.

    Examples:
        cli texture info my_texture
    """
    from src.capture.texture_capture import TextureCapturer

    capturer = TextureCapturer()
    proj = capturer.get_project_info(project_name)

    if not proj:
        console.print(f"[red]Project not found: {project_name}[/red]")
        return

    textures = "\n".join(f"  - {Path(t).name}" for t in proj.get("textures", []))
    meshes = "\n".join(f"  - {Path(m).name}" for m in proj.get("meshes", []))

    console.print(Panel(
        f"[bold]Name:[/bold] {proj['name']}\n"
        f"[bold]Path:[/bold] {proj['path']}\n"
        f"[bold]Created:[/bold] {proj.get('created', '-')}\n\n"
        f"[bold]Textures:[/bold]\n{textures}\n\n"
        f"[bold]Meshes:[/bold]\n{meshes}",
        title=f"Project: {project_name}",
    ))


@texture.command()
@click.argument("project_name")
@click.option("--confirm", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete(ctx: click.Context, project_name: str, confirm: bool) -> None:
    """Delete a texture project.

    Examples:
        cli texture delete my_texture
        cli texture delete my_texture -y
    """
    from src.capture.texture_capture import TextureCapturer

    capturer = TextureCapturer()

    if not capturer.get_project_info(project_name):
        console.print(f"[red]Project not found: {project_name}[/red]")
        return

    if not confirm:
        if not click.confirm(f"Delete project '{project_name}'?"):
            console.print("Cancelled")
            return

    if capturer.delete_project(project_name):
        console.print(f"[green]Deleted project: {project_name}[/green]")
    else:
        console.print(f"[red]Failed to delete project[/red]")


@texture.command()
@click.argument("image")
@click.pass_context
def analyze(ctx: click.Context, image: str) -> None:
    """Analyze image colors for texture reference.

    Examples:
        cli texture analyze photo.jpg
    """
    from src.capture.texture_capture import TextureCapturer

    img_path = Path(image)
    if not img_path.exists():
        console.print(f"[red]Image not found: {image}[/red]")
        return

    capturer = TextureCapturer()

    async def run():
        return await capturer.extract_color_from_image(str(img_path.absolute()))

    colors = asyncio.run(run())

    if "error" in colors:
        console.print(f"[red]Error: {colors['error']}[/red]")
        return

    dominant = colors.get("dominant_color", [0, 0, 0])
    palette = colors.get("palette", [])

    console.print(Panel(
        f"[bold]Dominant Color:[/bold] RGB({dominant[0]}, {dominant[1]}, {dominant[2]})\n"
        f"[bold]Brightness:[/bold] {colors.get('average_brightness', 0):.2f}\n"
        f"[bold]Color Palette:[/bold] {len(palette)} colors",
        title=f"Color Analysis: {img_path.name}",
    ))
