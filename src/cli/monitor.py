"""Monitoring CLI commands for Claude Fab Lab."""

import asyncio
import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


@click.command()
@click.option("--camera", "-c", default="h2d", type=click.Choice(["h2d", "usb", "ip", "mock"]),
              help="Camera source")
@click.option("--auto-pause", is_flag=True, help="Auto-pause on failure detection")
@click.option("--printer-ip", "-p", help="Printer IP address")
@click.option("--duration", "-d", type=float, help="Monitoring duration in seconds")
@click.option("--threshold", "-t", type=float, default=0.7, help="Detection confidence threshold")
@click.option("--mock", is_flag=True, help="Use mock mode for testing")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def monitor(
    camera: str,
    auto_pause: bool,
    printer_ip: str,
    duration: float,
    threshold: float,
    mock: bool,
    verbose: bool,
) -> None:
    """Start real-time print monitoring.

    Monitors the 3D print using camera feed and detects failures like:
    - Spaghetti/stringing (detached filament)
    - Warping/lifting from bed
    - Layer shifts
    - Missing extrusion

    Examples:

        fab monitor --camera h2d --auto-pause

        fab monitor --camera mock --duration 60

        fab monitor -c usb --printer-ip 192.168.1.100 -v
    """
    from src.monitoring import (
        CameraStream,
        CameraConfig,
        CameraType,
        FailureDetector,
        DetectionSettings,
        AlertSeverity,
    )

    # Map camera string to enum
    camera_types = {
        "h2d": CameraType.H2D,
        "usb": CameraType.USB,
        "ip": CameraType.IP,
        "mock": CameraType.MOCK,
    }

    camera_type = camera_types[camera]
    if mock:
        camera_type = CameraType.MOCK

    console.print("[bold]Print Monitoring[/bold]")
    console.print()

    # Create configuration
    config = CameraConfig(
        camera_type=camera_type,
        printer_ip=printer_ip,
    )

    settings = DetectionSettings(
        spaghetti_threshold=threshold,
        auto_pause_enabled=auto_pause,
        auto_pause_severity=AlertSeverity.CRITICAL,
    )

    if verbose:
        console.print("[dim]Configuration:[/dim]")
        console.print(f"  Camera type: {camera_type.value}")
        console.print(f"  Printer IP: {printer_ip or 'auto-detect'}")
        console.print(f"  Auto-pause: {auto_pause}")
        console.print(f"  Threshold: {threshold}")
        console.print()

    # Create camera and detector
    camera_stream = CameraStream(config)
    detector = FailureDetector(camera_stream, settings)

    # Track alerts
    alerts_list = []

    def on_alert(alert):
        alerts_list.append(alert)
        severity_colors = {
            "info": "blue",
            "warning": "yellow",
            "critical": "red",
        }
        color = severity_colors.get(alert.severity.value, "white")
        console.print(
            f"[{color}]ALERT: {alert.failure_type.value.upper()} "
            f"({alert.confidence:.0%} confidence)[/{color}]"
        )
        console.print(f"  Recommended: {alert.recommended_action}")
        if alert.auto_paused:
            console.print("  [red]Print auto-paused[/red]")

    detector.register_alert_callback(on_alert)

    # Run monitoring
    try:
        asyncio.run(_run_monitoring(detector, camera_stream, duration, verbose))
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user[/yellow]")
    finally:
        # Show summary
        stats = detector.stats
        console.print()
        console.print("[bold]Monitoring Summary[/bold]")

        summary_table = Table(show_header=False, box=None)
        summary_table.add_row("Frames analyzed:", str(stats.frames_analyzed))
        summary_table.add_row("Alerts generated:", str(stats.alerts_generated))
        summary_table.add_row("False positives:", str(stats.false_positives_marked))
        summary_table.add_row("Auto-pauses:", str(stats.auto_pauses))
        summary_table.add_row("Avg detection time:", f"{stats.detection_time_avg_ms:.1f}ms")
        summary_table.add_row("Uptime:", f"{stats.uptime_seconds:.1f}s")

        console.print(summary_table)

        if alerts_list:
            console.print()
            console.print(f"[yellow]Total alerts: {len(alerts_list)}[/yellow]")
            for failure_type, count in stats.alerts_by_type.items():
                console.print(f"  {failure_type.value}: {count}")


async def _run_monitoring(detector, camera, duration, verbose):
    """Run the monitoring loop."""
    from rich.live import Live
    from rich.table import Table

    success = await detector.start_monitoring()
    if not success:
        console.print("[red]Failed to start monitoring[/red]")
        return

    console.print("[green]Monitoring started[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    try:
        if duration:
            # Run for specified duration
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Monitoring...", total=None)
                await asyncio.sleep(duration)
        else:
            # Run indefinitely
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Monitoring (Ctrl+C to stop)...", total=None)
                while detector.is_monitoring:
                    await asyncio.sleep(1)

                    # Update status periodically in verbose mode
                    if verbose:
                        stats = detector.stats
                        progress.update(
                            task,
                            description=f"Monitoring... ({stats.frames_analyzed} frames, "
                                       f"{stats.alerts_generated} alerts)",
                        )
    finally:
        await detector.stop_monitoring()
        await camera.disconnect()


@click.command()
@click.option("--printer-ip", "-p", help="Printer IP address")
@click.option("--output", "-o", help="Output file path")
def snapshot(printer_ip: str, output: str) -> None:
    """Take a camera snapshot.

    Captures a single frame from the printer camera.

    Examples:

        fab snapshot --output snapshot.jpg

        fab snapshot -p 192.168.1.100 -o print_check.jpg
    """
    from src.monitoring import CameraStream, CameraConfig, CameraType

    config = CameraConfig(
        camera_type=CameraType.MOCK,  # Default to mock for now
        printer_ip=printer_ip,
    )

    camera = CameraStream(config)

    async def capture():
        await camera.connect()
        path = await camera.capture_snapshot(output)
        await camera.disconnect()
        return path

    try:
        result = asyncio.run(capture())
        if result:
            console.print(f"[green]Snapshot saved: {result}[/green]")
        else:
            console.print("[red]Failed to capture snapshot[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@click.command()
@click.option("--printer-ip", "-p", help="Printer IP address")
def camera_status(printer_ip: str) -> None:
    """Show camera status.

    Displays information about the connected camera.

    Examples:

        fab camera-status

        fab camera-status -p 192.168.1.100
    """
    from src.monitoring import CameraStream, CameraConfig, CameraType

    config = CameraConfig(
        camera_type=CameraType.MOCK,
        printer_ip=printer_ip,
    )

    camera = CameraStream(config)

    async def check_status():
        connected = await camera.connect()
        status = camera.status
        await camera.disconnect()
        return connected, status

    try:
        connected, status = asyncio.run(check_status())

        console.print("[bold]Camera Status[/bold]")
        console.print()

        status_table = Table(show_header=False, box=None)
        status_table.add_row("Type:", config.camera_type.value.upper())
        status_table.add_row("Resolution:", config.resolution)
        status_table.add_row("FPS:", str(config.fps))
        status_table.add_row("Connected:", "[green]Yes[/green]" if connected else "[red]No[/red]")
        status_table.add_row("Status:", status.value)

        console.print(status_table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
