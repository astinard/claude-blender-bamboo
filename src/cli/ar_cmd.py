"""CLI commands for AR preview."""

import asyncio
import click
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
def ar():
    """AR preview commands."""
    pass


@ar.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output USDZ path")
@click.option("--scale", "-s", default=1.0, help="Scale factor (meters)")
@click.option("--no-center", is_flag=True, help="Don't center the model")
@click.option("--color", "-c", default="0.8,0.8,0.8", help="Material color (R,G,B)")
@click.pass_context
def export(
    ctx: click.Context,
    model_path: str,
    output: str,
    scale: float,
    no_center: bool,
    color: str,
) -> None:
    """Export a model to USDZ format.

    Converts STL, OBJ, or 3MF files to USDZ for iOS AR Quick Look.

    Examples:
        cli ar export model.stl
        cli ar export model.obj --scale 0.001 --output preview.usdz
        cli ar export model.stl --color 1.0,0.5,0.2
    """
    from src.ar.usdz_exporter import USDZExporter, ExportConfig, ExportStatus

    # Parse color
    try:
        r, g, b = [float(x.strip()) for x in color.split(",")]
    except ValueError:
        console.print("[red]Invalid color format. Use R,G,B (e.g., 0.8,0.5,0.2)[/red]")
        return

    config = ExportConfig(
        scale=scale,
        center_model=not no_center,
        material_color=(r, g, b),
    )

    console.print(f"[bold]Exporting {model_path} to USDZ...[/bold]")

    async def run():
        exporter = USDZExporter(config)
        result = await exporter.export(model_path, output)

        if result.status == ExportStatus.COMPLETED:
            console.print()
            console.print("[green]Export successful![/green]")
            console.print(f"  Output: {result.output_path}")
            console.print(f"  Size: {result.file_size_bytes / 1024:.1f} KB")
            console.print(f"  Vertices: {result.vertex_count}")
            console.print(f"  Faces: {result.face_count}")
        else:
            console.print(f"[red]Export failed: {result.error_message}[/red]")

    asyncio.run(run())


@ar.command()
@click.argument("model_path", type=click.Path(exists=True))
@click.option("--port", "-p", default=9880, help="Server port")
@click.option("--no-browser", is_flag=True, help="Don't open browser")
@click.option("--no-qr", is_flag=True, help="Don't generate QR code")
@click.pass_context
def serve(
    ctx: click.Context,
    model_path: str,
    port: int,
    no_browser: bool,
    no_qr: bool,
) -> None:
    """Start AR preview server for a model.

    Exports the model to USDZ and starts a local server.
    Scan the QR code with your iPhone to view in AR.

    Examples:
        cli ar serve model.stl
        cli ar serve model.obj --port 9000
        cli ar serve model.stl --no-browser
    """
    from src.ar.ar_server import ARServer

    console.print(f"[bold]Starting AR preview server...[/bold]")
    console.print(f"  Model: {model_path}")
    console.print(f"  Port: {port}")
    console.print()

    async def run():
        server = ARServer(port=port)

        # Create session
        session = await server.create_session(
            model_path,
            generate_qr=not no_qr,
        )

        if not session.usdz_path:
            console.print("[red]Failed to export model to USDZ[/red]")
            return

        # Start server
        await server.start()

        # Display info
        console.print()
        console.print(Panel(
            f"[bold green]AR Preview Ready[/bold green]\n\n"
            f"Preview URL: {session.preview_url}\n"
            f"USDZ File: {session.usdz_path}\n"
            f"QR Code: {session.qr_code_path or 'Not generated'}",
            title="AR Server",
        ))

        # Open browser if requested
        if not no_browser and session.preview_url:
            import webbrowser
            webbrowser.open(session.preview_url)

        console.print()
        console.print("[dim]Press Ctrl+C to stop the server[/dim]")

        try:
            # Keep running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            console.print()
            console.print("[yellow]Shutting down server...[/yellow]")
            await server.stop()

    asyncio.run(run())


@ar.command()
@click.argument("url")
@click.option("--output", "-o", help="Output file path")
@click.option("--size", "-s", default=256, help="QR code size in pixels")
@click.pass_context
def qr(
    ctx: click.Context,
    url: str,
    output: str,
    size: int,
) -> None:
    """Generate a QR code for an AR preview URL.

    Examples:
        cli ar qr http://192.168.1.10:8080/ar/abc123
        cli ar qr "http://example.com/model.usdz" --output qr.png
    """
    from src.ar.qr_generator import QRGenerator, QRConfig

    config = QRConfig(size=size)
    generator = QRGenerator(config)

    console.print(f"[bold]Generating QR code for: {url}[/bold]")

    result = generator.generate(url, output)

    if result:
        console.print(f"[green]QR code saved to: {result}[/green]")
    else:
        console.print("[red]Failed to generate QR code[/red]")
        console.print("[dim]Install qrcode library: pip install qrcode[/dim]")


@ar.command()
@click.pass_context
def info(ctx: click.Context) -> None:
    """Show AR preview system information.

    Displays available tools and dependencies for AR export.
    """
    from src.ar.usdz_exporter import USDZExporter
    from src.ar.qr_generator import QRGenerator

    exporter = USDZExporter()
    qr_gen = QRGenerator()

    table = Table(title="AR Preview System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Notes")

    # Check USD library
    usd_available = exporter._check_usd_available()
    table.add_row(
        "USD Library (pxr)",
        "[green]Available[/green]" if usd_available else "[yellow]Not installed[/yellow]",
        "Native USDZ export" if usd_available else "pip install usd-core",
    )

    # Check usdc tool
    usdc_available = exporter._check_usdc_available()
    table.add_row(
        "usdc Command",
        "[green]Available[/green]" if usdc_available else "[yellow]Not found[/yellow]",
        "USD command-line tools" if usdc_available else "Install USD tools",
    )

    # Check qrcode library
    qrcode_available = qr_gen._check_qrcode_available()
    table.add_row(
        "QR Code Library",
        "[green]Available[/green]" if qrcode_available else "[yellow]Not installed[/yellow]",
        "QR code generation" if qrcode_available else "pip install qrcode",
    )

    # Check PIL
    pil_available = False
    try:
        from PIL import Image
        pil_available = True
    except ImportError:
        pass

    table.add_row(
        "Pillow (PIL)",
        "[green]Available[/green]" if pil_available else "[yellow]Not installed[/yellow]",
        "Image processing" if pil_available else "pip install pillow",
    )

    # Check aiohttp
    aiohttp_available = False
    try:
        import aiohttp
        aiohttp_available = True
    except ImportError:
        pass

    table.add_row(
        "aiohttp",
        "[green]Available[/green]" if aiohttp_available else "[yellow]Not installed[/yellow]",
        "Web server" if aiohttp_available else "pip install aiohttp",
    )

    console.print(table)
    console.print()

    # Export method info
    if usd_available:
        console.print("[green]USDZ export will use native USD library (best quality)[/green]")
    elif usdc_available:
        console.print("[yellow]USDZ export will use usdc command-line tool[/yellow]")
    else:
        console.print("[yellow]USDZ export will use fallback (basic USDA format)[/yellow]")
        console.print("[dim]For best results, install: pip install usd-core[/dim]")
