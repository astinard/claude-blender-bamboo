"""AI generation CLI commands for Claude Fab Lab."""

import asyncio
import click
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.command()
@click.argument("prompt")
@click.option("--provider", "-p", default="meshy",
              type=click.Choice(["meshy", "tripo", "mock"]),
              help="AI provider to use")
@click.option("--output", "-o", default=None, help="Output filename (without extension)")
@click.option("--output-dir", "-d", default=None, help="Output directory")
@click.option("--format", "-f", "output_format", default="stl",
              type=click.Choice(["stl", "obj", "glb", "3mf"]),
              help="Output format")
@click.option("--style", "-s", default="printable",
              type=click.Choice(["realistic", "cartoon", "low_poly", "sculpture", "printable"]),
              help="Art style")
@click.option("--negative", "-n", default=None, help="Negative prompt (what to avoid)")
@click.option("--no-wait", is_flag=True, help="Don't wait for completion")
@click.option("--mock", is_flag=True, help="Use mock mode (no API calls)")
@click.option("--json", "output_json", is_flag=True, help="Output result as JSON")
def generate(
    prompt: str,
    provider: str,
    output: str,
    output_dir: str,
    output_format: str,
    style: str,
    negative: str,
    no_wait: bool,
    mock: bool,
    output_json: bool,
) -> None:
    """Generate 3D model from text description.

    Example: fab generate "a dragon phone stand" --provider meshy --output dragon

    Providers:
    - meshy: Meshy AI (recommended, requires MESHY_API_KEY)
    - tripo: Tripo AI (requires TRIPO_API_KEY)
    - mock: Mock mode for testing (no API key needed)
    """
    from src.ai.text_to_3d import (
        TextTo3DGenerator,
        GenerationProvider,
        ModelFormat,
        ArtStyle,
        GenerationStatus,
    )

    # Override provider if mock flag is set
    if mock:
        provider = "mock"

    try:
        provider_enum = GenerationProvider(provider)
        format_enum = ModelFormat(output_format)
        style_enum = ArtStyle(style)
    except ValueError as e:
        console.print(f"[red]Invalid option: {e}[/red]")
        return

    generator = TextTo3DGenerator(default_provider=provider_enum)

    # Check if provider is available
    if not generator.is_provider_available(provider_enum):
        available = ", ".join(p.value for p in generator.get_available_providers())
        console.print(f"[red]Provider '{provider}' not available.[/red]")
        console.print(f"[dim]Available providers: {available}[/dim]")

        if provider != "mock":
            console.print("\n[yellow]Hint: Set the API key environment variable:[/yellow]")
            if provider == "meshy":
                console.print("  export MESHY_API_KEY=your_key")
            elif provider == "tripo":
                console.print("  export TRIPO_API_KEY=your_key")
            console.print("\n[dim]Or use --mock for testing without API calls[/dim]")
        return

    if not output_json:
        console.print(f"[bold]AI Text-to-3D Generation[/bold]")
        console.print(f"  Prompt: {prompt}")
        console.print(f"  Provider: {provider}")
        console.print(f"  Format: {output_format}")
        console.print(f"  Style: {style}")
        if negative:
            console.print(f"  Avoid: {negative}")
        console.print()

    # Progress callback for status updates
    def progress_callback(result):
        if not output_json:
            console.print(f"[dim]Status: {result.status.value}[/dim]")

    # Run generation
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            disable=output_json,
        ) as progress:
            task = progress.add_task("Generating model...", total=None)

            result = asyncio.run(
                generator.generate(
                    prompt=prompt,
                    provider=provider_enum,
                    output_format=format_enum,
                    art_style=style_enum,
                    output_dir=output_dir,
                    output_name=output,
                    negative_prompt=negative,
                    wait_for_completion=not no_wait,
                    progress_callback=progress_callback if not output_json else None,
                )
            )

            progress.update(task, completed=True)

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return
    except Exception as e:
        console.print(f"[red]Generation failed: {e}[/red]")
        return

    # Output results
    if output_json:
        import json
        data = {
            "request_id": result.request_id,
            "status": result.status.value,
            "provider": result.provider.value,
            "output_path": result.output_path,
            "duration_seconds": result.duration_seconds,
            "file_size_bytes": result.file_size_bytes,
            "error_message": result.error_message,
        }
        console.print(json.dumps(data, indent=2))
        return

    # Display result
    if result.is_successful:
        console.print(f"\n[green]✓ Generation complete![/green]")
        console.print(f"  Output: {result.output_path}")
        console.print(f"  Size: {result.file_size_bytes:,} bytes")
        console.print(f"  Time: {result.duration_seconds:.1f}s")

        if result.vertex_count > 0:
            console.print(f"  Vertices: {result.vertex_count:,}")
            console.print(f"  Faces: {result.face_count:,}")
            if result.is_watertight:
                console.print(f"  [green]Watertight: Yes (good for printing)[/green]")

        # Suggest next steps
        console.print(f"\n[dim]Next steps:[/dim]")
        console.print(f"  fab suggest {result.output_path} --fix-issues")
        console.print(f"  fab queue add {result.output_path}")

    elif result.status == GenerationStatus.PROCESSING:
        console.print(f"\n[yellow]Generation in progress[/yellow]")
        console.print(f"  Task ID: {result.provider_task_id}")
        console.print(f"\n[dim]Check status later or re-run without --no-wait[/dim]")

    else:
        console.print(f"\n[red]Generation failed[/red]")
        if result.error_message:
            console.print(f"  Error: {result.error_message}")
        if result.error_code:
            console.print(f"  Code: {result.error_code}")


@click.command("generate-status")
@click.argument("task_id")
@click.option("--provider", "-p", default="meshy",
              type=click.Choice(["meshy", "tripo"]),
              help="Provider that owns the task")
def generate_status(task_id: str, provider: str) -> None:
    """Check status of a generation task.

    Example: fab generate-status abc123 --provider meshy
    """
    from src.ai.text_to_3d import GenerationProvider
    from src.ai.meshy_client import MeshyClient
    from src.ai.tripo_client import TripoClient

    try:
        provider_enum = GenerationProvider(provider)
    except ValueError:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        return

    console.print(f"Checking status for task: {task_id}")

    if provider_enum == GenerationProvider.MESHY:
        client = MeshyClient()
    else:
        client = TripoClient()

    result = asyncio.run(client.check_status(task_id))

    console.print(f"\nStatus: {result.status.value}")

    if result.is_successful:
        console.print(f"[green]Generation complete![/green]")
        if result.model_url:
            console.print(f"Model URL: {result.model_url}")
        if result.preview_url:
            console.print(f"Preview: {result.preview_url}")
    elif result.error_message:
        console.print(f"[red]Error: {result.error_message}[/red]")
