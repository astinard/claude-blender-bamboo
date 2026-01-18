#!/usr/bin/env python3
"""
JARVIS Fab Lab Launcher

Launch the web dashboard and API server.

Usage:
    python launch.py              # Start server on http://localhost:8000
    python launch.py --port 3000  # Custom port
    python launch.py --host 0.0.0.0  # Allow external connections
"""

import sys
import argparse
import webbrowser
import time
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def open_browser(url: str, delay: float = 1.5):
    """Open browser after a short delay."""
    time.sleep(delay)
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Fab Lab - Web Dashboard & API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch.py                    # Start on localhost:8000
  python launch.py --port 3000        # Custom port
  python launch.py --no-browser       # Don't open browser
  python launch.py --host 0.0.0.0     # Allow network access

Features:
  - Web dashboard with 3D preview
  - Voice control (click 🎤 in browser)
  - Real-time status via WebSocket
  - Blender launcher
  - Printer/laser control

API Endpoints:
  GET  /              Web dashboard
  GET  /api/status    System status
  POST /api/scan      Start scan
  POST /api/print     Start print
  POST /api/command   Voice command
  WS   /ws            Real-time updates
        """
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)"
    )

    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically"
    )

    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗               ║
║       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝               ║
║       ██║███████║██████╔╝██║   ██║██║███████╗               ║
║  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║               ║
║  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║               ║
║   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝               ║
║                                                              ║
║              F A B   L A B   C O N T R O L                   ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  Dashboard:  {url:<44}║
║  API:        {url}/api/status{' '*27}║
║  WebSocket:  ws://{args.host}:{args.port}/ws{' '*30}║
╠══════════════════════════════════════════════════════════════╣
║  Press Ctrl+C to stop                                        ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # Open browser in background thread
    if not args.no_browser:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    # Import and run server
    try:
        from jarvis.server import run_server
        run_server(host=args.host, port=args.port)
    except ImportError as e:
        print(f"\nError: Missing dependencies. Please install:")
        print("  pip install fastapi uvicorn websockets")
        print(f"\nDetails: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nJARVIS shutting down. Goodbye.")


if __name__ == "__main__":
    main()
