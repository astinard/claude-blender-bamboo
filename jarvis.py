#!/usr/bin/env python3
"""
JARVIS - Fab Lab AI Assistant

Launch the sci-fi voice and visual interface.

Usage:
    python jarvis.py              # Full experience with voice
    python jarvis.py --silent     # No voice, just visuals
    python jarvis.py --demo       # Run demo sequence
"""

import sys
import argparse

# Add src to path
sys.path.insert(0, "src")

from jarvis.core import Jarvis
from jarvis.voice import VoiceConfig


def demo_sequence(jarvis: Jarvis):
    """Run a demo sequence showing off capabilities."""
    import time

    commands = [
        ("scan this phone case", 2),
        ("analyze the mesh", 2),
        ("make it 20 percent smaller", 1),
        ("hollow it out", 1),
        ("estimate the cost", 1),
        ("status", 1),
    ]

    jarvis.display.header("DEMO MODE")
    jarvis.say("Running demonstration sequence.")
    time.sleep(1)

    for cmd, delay in commands:
        print(f"\n{'─' * 60}")
        print(f"  Command: '{cmd}'")
        print(f"{'─' * 60}\n")
        time.sleep(0.5)
        jarvis.command(cmd)
        time.sleep(delay)

    jarvis.say("Demonstration complete. JARVIS is ready for your commands.")


def main():
    parser = argparse.ArgumentParser(
        description="JARVIS - Fab Lab AI Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python jarvis.py              # Full experience with voice
  python jarvis.py --silent     # No voice, visual-only mode
  python jarvis.py --demo       # Run demonstration sequence
  python jarvis.py --voice Alex # Use different voice (macOS)

Available voices (macOS):
  Samantha (default), Daniel, Alex, Tessa, Karen, Moira, Fiona
        """
    )

    parser.add_argument(
        "--silent", "-s",
        action="store_true",
        help="Disable voice output"
    )

    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run demonstration sequence"
    )

    parser.add_argument(
        "--voice", "-v",
        default="Samantha",
        help="Voice to use (default: Samantha)"
    )

    parser.add_argument(
        "--rate", "-r",
        type=int,
        default=200,
        help="Speech rate in words per minute (default: 200)"
    )

    parser.add_argument(
        "--skip-boot",
        action="store_true",
        help="Skip boot animation"
    )

    args = parser.parse_args()

    # Configure voice
    voice_config = VoiceConfig(
        voice=args.voice,
        rate=args.rate,
        enabled=not args.silent,
    )

    # Create and boot JARVIS
    jarvis = Jarvis(
        voice_enabled=not args.silent,
        voice_config=voice_config,
    )

    jarvis.boot(skip_animation=args.skip_boot)

    if args.demo:
        demo_sequence(jarvis)
        print()

    # Enter interactive mode
    jarvis.interactive()


if __name__ == "__main__":
    main()
