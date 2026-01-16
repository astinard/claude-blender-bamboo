#!/usr/bin/env python3
"""
Mock printer demonstration.

Shows how to use the mock printer for testing without hardware.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.printer import create_mock_printer, PrinterState


def main():
    """Demonstrate mock printer functionality."""
    print("=" * 50)
    print("Mock Printer Demonstration")
    print("=" * 50)

    # Create mock printer
    printer = create_mock_printer()

    print("\n1. Connecting to mock printer...")
    printer.connect()
    print(f"   Connected: {printer.is_connected}")

    print("\n2. Initial status:")
    status = printer.status
    print(f"   State: {status.state.value}")
    print(f"   Bed temp: {status.bed_temp}°C")
    print(f"   Nozzle temp: {status.nozzle_temp}°C")

    print("\n3. Uploading file...")
    result = printer.upload_file("demo_cube.stl", 50000)
    print(f"   Upload: {result.message}")

    print("\n4. Listing files...")
    files = printer.list_files()
    for f in files:
        print(f"   - {f.name} ({f.size} bytes)")

    print("\n5. Starting print...")
    result = printer.start_print("demo_cube.stl")
    print(f"   Result: {result.message}")

    print("\n6. Monitoring print (press Ctrl+C to stop)...")
    try:
        while True:
            status = printer.status
            state = status.state.value

            if status.state == PrinterState.PRINTING:
                print(f"   [{state}] Progress: {status.progress:.0f}% | "
                      f"Layer: {status.layer_current}/{status.layer_total} | "
                      f"Nozzle: {status.nozzle_temp:.0f}°C")
            elif status.state == PrinterState.PREPARING:
                print(f"   [{state}] Heating... "
                      f"Bed: {status.bed_temp:.0f}/{status.bed_temp_target:.0f}°C | "
                      f"Nozzle: {status.nozzle_temp:.0f}/{status.nozzle_temp_target:.0f}°C")
            elif status.state == PrinterState.FINISHED:
                print(f"   [{state}] Print complete!")
                break
            elif status.state == PrinterState.IDLE:
                print(f"   [{state}] Printer idle")
                break
            else:
                print(f"   [{state}]")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n7. Stopping print...")
        printer.stop_print()

    print("\n8. Disconnecting...")
    printer.disconnect()
    print("   Done!")


if __name__ == "__main__":
    main()
