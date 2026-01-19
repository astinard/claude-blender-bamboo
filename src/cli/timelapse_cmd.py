"""CLI commands for time-lapse generation."""

import asyncio
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel

console = Console()


@click.group()
def timelapse():
    """Time-lapse generation commands."""
    pass


@timelapse.command()
@click.option("--print-id", help="ID of the print job")
@click.option("--print-name", help="Name of the print file")
@click.option("--interval", "-i", default=10.0, help="Capture interval in seconds")
@click.option("--format", "-f", "output_format", default="mp4",
              type=click.Choice(["mp4", "gif", "frames"]),
              help="Output format")
@click.option("--fps", default=30, help="Output video FPS")
@click.option("--resolution", "-r", default="720p",
              type=click.Choice(["480p", "720p", "1080p"]),
              help="Capture resolution")
@click.option("--max-frames", default=10000, help="Maximum frames to capture")
@click.option("--camera-type", default="mock",
              type=click.Choice(["h2d", "usb", "ip", "mock"]),
              help="Camera type to use")
@click.option("--camera-url", help="Camera URL (for IP camera)")
@click.pass_context
def start(
    ctx: click.Context,
    print_id: str,
    print_name: str,
    interval: float,
    output_format: str,
    fps: int,
    resolution: str,
    max_frames: int,
    camera_type: str,
    camera_url: str,
) -> None:
    """Start recording a time-lapse.

    Records frames at configured intervals and exports as video.
    Press Ctrl+C to stop recording and export.

    Examples:
        cli timelapse start --print-name model.stl
        cli timelapse start --interval 5 --format gif
        cli timelapse start --camera-type h2d --resolution 1080p
    """
    from src.monitoring.timelapse import (
        TimelapseGenerator,
        TimelapseConfig,
        OutputFormat,
        CaptureMode,
    )
    from src.monitoring.camera_stream import CameraStream, CameraConfig, CameraType

    # Map format string to enum
    format_map = {
        "mp4": OutputFormat.MP4,
        "gif": OutputFormat.GIF,
        "frames": OutputFormat.FRAMES,
    }

    # Map camera type string to enum
    camera_type_map = {
        "h2d": CameraType.H2D,
        "usb": CameraType.USB,
        "ip": CameraType.IP,
        "mock": CameraType.MOCK,
    }

    # Create config
    config = TimelapseConfig(
        capture_mode=CaptureMode.INTERVAL,
        capture_interval_seconds=interval,
        output_format=format_map[output_format],
        output_fps=fps,
        max_frames=max_frames,
        resolution=resolution,
        auto_export=True,
    )

    # Create camera config
    cam_config = CameraConfig(
        camera_type=camera_type_map[camera_type],
        url=camera_url,
        resolution=resolution,
    )

    async def run_recording():
        camera = CameraStream(cam_config)
        generator = TimelapseGenerator(camera, config)

        console.print("[bold green]Starting time-lapse recording...[/bold green]")
        console.print(f"  Interval: {interval}s")
        console.print(f"  Format: {output_format}")
        console.print(f"  Resolution: {resolution}")
        console.print(f"  Camera: {camera_type}")
        console.print()

        session_id = await generator.start_recording(
            print_id=print_id,
            print_name=print_name,
        )

        console.print(f"[bold]Session ID:[/bold] {session_id}")
        console.print("[dim]Press Ctrl+C to stop recording[/dim]")
        console.print()

        try:
            with Live(console=console, refresh_per_second=1) as live:
                while generator.is_recording:
                    info = generator.get_session_info()
                    if info:
                        panel = Panel(
                            f"Frames: {info['current_frames']}\n"
                            f"Duration: {info.get('current_duration', 0):.1f}s",
                            title="Recording",
                            border_style="green",
                        )
                        live.update(panel)
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            console.print()
            console.print("[yellow]Stopping recording...[/yellow]")

        session = await generator.stop_recording()
        await camera.disconnect()

        if session:
            console.print()
            console.print("[bold green]Recording complete![/bold green]")
            console.print(f"  Frames captured: {session.frames_captured}")
            console.print(f"  Duration: {session.duration_seconds:.1f}s")
            if session.output_path:
                console.print(f"  Output: {session.output_path}")

    asyncio.run(run_recording())


@timelapse.command()
@click.option("--duration", "-d", required=True, type=float,
              help="Recording duration in seconds")
@click.option("--print-id", help="ID of the print job")
@click.option("--print-name", help="Name of the print file")
@click.option("--interval", "-i", default=10.0, help="Capture interval in seconds")
@click.option("--format", "-f", "output_format", default="mp4",
              type=click.Choice(["mp4", "gif", "frames"]),
              help="Output format")
@click.pass_context
def record(
    ctx: click.Context,
    duration: float,
    print_id: str,
    print_name: str,
    interval: float,
    output_format: str,
) -> None:
    """Record a fixed-duration time-lapse.

    Records for a specified duration and automatically exports.

    Examples:
        cli timelapse record --duration 60 --print-name test.stl
        cli timelapse record -d 300 --interval 5 --format gif
    """
    from src.monitoring.timelapse import (
        create_timelapse,
        OutputFormat,
    )

    # Map format string to enum
    format_map = {
        "mp4": OutputFormat.MP4,
        "gif": OutputFormat.GIF,
        "frames": OutputFormat.FRAMES,
    }

    console.print(f"[bold]Recording time-lapse for {duration}s...[/bold]")

    async def run():
        output = await create_timelapse(
            print_id=print_id,
            print_name=print_name,
            duration_seconds=duration,
            interval_seconds=interval,
            output_format=format_map[output_format],
        )

        if output:
            console.print(f"[green]Time-lapse saved to:[/green] {output}")
        else:
            console.print("[yellow]No output generated (may need ffmpeg installed)[/yellow]")

    asyncio.run(run())


@timelapse.command()
@click.argument("frames_dir", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output file path")
@click.option("--format", "-f", "output_format", default="mp4",
              type=click.Choice(["mp4", "gif"]),
              help="Output format")
@click.option("--fps", default=30, help="Output video FPS")
@click.pass_context
def export(
    ctx: click.Context,
    frames_dir: str,
    output: str,
    output_format: str,
    fps: int,
) -> None:
    """Export existing frames to video.

    Takes a directory of captured frames and exports to MP4 or GIF.

    Examples:
        cli timelapse export /path/to/frames --output timelapse.mp4
        cli timelapse export /path/to/frames --format gif --fps 15
    """
    import shutil
    from pathlib import Path

    frames_path = Path(frames_dir)
    frame_files = sorted(frames_path.glob("frame_*.jpg"))

    if not frame_files:
        console.print("[red]No frame files found in directory[/red]")
        return

    console.print(f"Found {len(frame_files)} frames")

    # Determine output path
    if not output:
        output = f"timelapse.{output_format}"

    output_path = Path(output)

    # Check for ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        console.print("[red]ffmpeg not found. Install ffmpeg to export videos.[/red]")
        return

    import subprocess

    if output_format == "mp4":
        args = [
            ffmpeg_path,
            "-y",
            "-framerate", str(fps),
            "-i", str(frames_path / "frame_%06d.jpg"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            str(output_path),
        ]
    else:  # gif
        args = [
            ffmpeg_path,
            "-y",
            "-framerate", str(min(fps, 15)),
            "-i", str(frames_path / "frame_%06d.jpg"),
            "-vf", "scale=480:-1",
            str(output_path),
        ]

    console.print(f"Exporting to {output_path}...")

    result = subprocess.run(args, capture_output=True, text=True)

    if result.returncode == 0:
        console.print(f"[green]Exported to:[/green] {output_path}")
    else:
        console.print(f"[red]Export failed:[/red] {result.stderr}")
