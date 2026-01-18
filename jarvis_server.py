#!/usr/bin/env python3
"""Launch the JARVIS Fab Lab Control server."""

import asyncio
import sys
import webbrowser
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.api.server import run_server


def main():
    """Start the JARVIS server."""
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║        █▀▀█ █▀▀█ █▀▀▀█ █  █ ▀█▀ █▀▀█                         ║
    ║        █▄▄█ █▄▄█ █▄▄▀█ █  █  █  █▄▄▀                         ║
    ║        █  █ █  █ █▄▄▄█  ▀▀   █  █▄▄▄                         ║
    ║                                                               ║
    ║              FAB LAB CONTROL SYSTEM v1.0                      ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    print("Starting JARVIS server on http://localhost:8080")
    print("Press Ctrl+C to stop\n")

    try:
        asyncio.run(run_server(port=8080, open_browser=True))
    except KeyboardInterrupt:
        print("\nJARVIS server stopped.")


if __name__ == "__main__":
    main()
