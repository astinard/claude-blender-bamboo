"""Shared utilities for Claude Fab Lab."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from rich.console import Console
from rich.logging import RichHandler

# Rich console for pretty output
console = Console()


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Set up logging with Rich handler."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    return logging.getLogger("fablab")


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(f"fablab.{name}")


def ensure_dir(path: Union[str, Path]) -> Path:
    """Ensure a directory exists and return the Path."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_hash(path: Union[str, Path], algorithm: str = "sha256") -> str:
    """Compute hash of a file."""
    path = Path(path)
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def timestamp() -> str:
    """Get current timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_size(size_bytes: int) -> str:
    """Format byte size as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds as human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:.0f}m {secs:.0f}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:.0f}h {minutes:.0f}m"


def safe_filename(name: str, max_length: int = 64) -> str:
    """Convert a string to a safe filename."""
    # Replace problematic characters
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    # Remove consecutive underscores
    while "__" in safe:
        safe = safe.replace("__", "_")
    # Trim
    return safe[:max_length].strip("_")
