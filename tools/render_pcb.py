#!/usr/bin/env python3
"""Render the saved MARV PCB front/back for the README using KiCad 10."""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "MARV-V2.kicad_pcb"


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "images" / "pcb")
    parser.add_argument("--width", type=positive_int, default=1600)
    parser.add_argument("--height", type=positive_int, default=1400)
    args = parser.parse_args()

    cli = shutil.which("kicad-cli")
    if cli is None:
        parser.exit(1, "Install KiCad 10 (including kicad-cli and its 3D model libraries).\n")
    if not BOARD.is_file():
        parser.exit(1, f"Board not found: {BOARD}\n")

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Stage both images so a failed render leaves the previous gallery intact.
    with tempfile.TemporaryDirectory(prefix=".render-", dir=output) as scratch:
        staged = []
        for label, side in (("front", "top"), ("back", "bottom")):
            image = Path(scratch) / f"marv-v2-{label}.png"
            print(f"Rendering PCB {label}…", flush=True)
            command = [
                cli, "pcb", "render", str(BOARD),
                "--output", str(image),
                "--width", str(args.width), "--height", str(args.height),
                "--side", side, "--background", "transparent",
                "--quality", "high", "--use-board-stackup-colors",
                "--zoom", "0.9",
            ]
            try:
                result = subprocess.run(
                    command, cwd=ROOT, capture_output=True, text=True,
                    check=True, timeout=300,
                )
            except subprocess.CalledProcessError as error:
                parser.exit(1, f"KiCad render failed:\n{error.stdout}\n{error.stderr}\n")
            except subprocess.TimeoutExpired:
                parser.exit(1, f"Rendering {label} exceeded five minutes.\n")
            if result.stderr.strip():
                print(result.stderr.strip())
            if not image.is_file() or image.stat().st_size == 0:
                parser.exit(1, f"KiCad did not produce {image.name}.\n")
            staged.append(image)
        for image in staged:
            destination = output / image.name
            image.replace(destination)
            print(f"Saved {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
