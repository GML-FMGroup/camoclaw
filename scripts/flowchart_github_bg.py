#!/usr/bin/env python3
"""
Apply GitHub-style background to Flowchart.png (replace pure white with subtle gray).

GitHub Primer canvas_subtle: #f6f8fa
Usage: python scripts/flowchart_github_bg.py [--input assets/Flowchart.png] [--output assets/Flowchart.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
import numpy as np


# GitHub Primer light theme - canvas_subtle
GITHUB_BG = (0xF6, 0xF8, 0xFA)
WHITE = (255, 255, 255)


def apply_github_bg(
    input_path: Path,
    output_path: Path | None = None,
    white_threshold: int = 252,
) -> None:
    """Replace near-white pixels with GitHub-style background color."""
    if output_path is None:
        output_path = input_path

    img = Image.open(input_path).convert("RGB")
    arr = np.array(img)

    # Replace pixels that are nearly pure white
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mask = (r >= white_threshold) & (g >= white_threshold) & (b >= white_threshold)

    arr[mask, 0] = GITHUB_BG[0]
    arr[mask, 1] = GITHUB_BG[1]
    arr[mask, 2] = GITHUB_BG[2]

    out = Image.fromarray(arr)
    out.save(output_path, "PNG")
    print(f"Saved: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply GitHub-style background to flowchart")
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("assets/Flowchart.png"),
        help="Input flowchart PNG",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output path (default: overwrite input)",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=252,
        help="White replacement threshold 0-255 (default: 252, lower=more aggressive)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    input_path = (args.input if args.input.is_absolute() else root / args.input).resolve()
    output_path = args.output
    if output_path is not None and not output_path.is_absolute():
        output_path = root / output_path

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        return 1

    apply_github_bg(input_path, output_path, white_threshold=args.threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
