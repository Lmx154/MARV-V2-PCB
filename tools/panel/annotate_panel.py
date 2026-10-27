#!/usr/bin/env python3
"""Draw the V-score lines and legend on a top render of MARV-V2-panel.kicad_pcb.

Writes images/pcb/marv-v2-panel-annotated.png (1344 x 1434 px): a transparent-background
kicad-cli render of the panel is cropped to the 72 x 72 mm panel, scaled to 1328 px and
placed on black with an 8 px margin (about 18.44 px/mm), the four full-span V-scores are
drawn as red dashed lines, and a white legend strip is added underneath.

V-score positions are read from the User.1 lines of the panel board, so they always match
the saved panel. Run from anywhere with kicad-cli on the path and Pillow installed:
    python3 tools/panel/annotate_panel.py [--output PATH]
"""

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "MARV-V2-panel.kicad_pcb"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PANEL_MM = (64.0, 136.0)  # panel outline, both axes
MARGIN, SIZE, LEGEND = 8, 1328, 90
RED, GREY = (220, 30, 30), (60, 60, 60)


def vscores():
    text = PANEL.read_text()
    xs, ys = set(), set()
    for block in text.split("(gr_line")[1:]:
        block = block.split("\n\t(")[0]
        if '(layer "User.1")' not in block:
            continue
        m = re.search(r"\(start ([\d.]+) ([\d.]+)\)\s*\(end ([\d.]+) ([\d.]+)\)", block)
        x1, y1, x2, y2 = map(float, m.groups())
        if x1 == x2:
            xs.add(x1)
        elif y1 == y2:
            ys.add(y1)
    return sorted(xs), sorted(ys)


def render(path):
    cmd = [shutil.which("kicad-cli") or "kicad-cli", "pcb", "render", str(PANEL), "--output", str(path),
           "--width", "2000", "--height", "2000", "--side", "top", "--background", "transparent",
           "--quality", "high", "--use-board-stackup-colors", "--zoom", "0.9"]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)


def panel_bbox(img):
    """Bounding box of the green solder-mask panel (rows and columns that are mostly mask-coloured)."""
    w, h = img.size
    px = img.load()
    cols, rows = [0] * w, [0] * h
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 200 and g > r + 15 and g > b + 5:
                cols[x] += 1
                rows[y] += 1
    xs = [x for x, c in enumerate(cols) if c > 0.5 * max(cols)]
    ys = [y for y, c in enumerate(rows) if c > 0.5 * max(rows)]
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


def dashed(draw, p0, p1, on=15, off=7, width=3):
    (x0, y0), (x1, y1) = p0, p1
    vertical = x0 == x1
    pos, end = (y0, y1) if vertical else (x0, x1)
    while pos < end:
        stop = min(pos + on, end)
        if vertical:
            draw.rectangle([x0 - width // 2, pos, x0 + width // 2, stop - 1], fill=RED)
        else:
            draw.rectangle([pos, y0 - width // 2, stop - 1, y0 + width // 2], fill=RED)
        pos += on + off


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", type=Path, default=ROOT / "images/pcb/marv-v2-panel-annotated.png")
    args = ap.parse_args()
    xs, ys = vscores()
    if len(xs) != 2 or len(ys) != 2:
        raise SystemExit(f"expected 2 vertical and 2 horizontal User.1 V-score lines, found {xs} {ys}")
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "panel-top.png"
        render(raw)
        img = Image.open(raw).convert("RGBA")
    img = img.crop(panel_bbox(img)).resize((SIZE, SIZE), Image.LANCZOS)
    canvas = Image.new("RGB", (SIZE + 2 * MARGIN, SIZE + 2 * MARGIN), "black")
    canvas.paste(img.convert("RGB"), (MARGIN, MARGIN), img.split()[-1])
    out = Image.new("RGB", (canvas.width, canvas.height + LEGEND), "white")
    out.paste(canvas, (0, 0))
    d = ImageDraw.Draw(out)
    scale = SIZE / (PANEL_MM[1] - PANEL_MM[0])
    px = lambda v: round(MARGIN + (v - PANEL_MM[0]) * scale)
    for x in xs:
        dashed(d, (px(x), MARGIN), (px(x), MARGIN + SIZE))
    for y in ys:
        dashed(d, (MARGIN, px(y)), (MARGIN + SIZE, px(y)))
    font = ImageFont.truetype(FONT, 28)
    cy = canvas.height + LEGEND // 2 - 1
    d.rectangle([40, cy - 1, 110, cy + 1], fill=RED)
    d.text((125, cy), "V-score (4 full-span, 0.1 mm outside board edge)", font=font, fill=(0, 0, 0), anchor="lm")
    d.rectangle([930, cy - 15, 967, cy + 17], fill=GREY)
    d.text((980, cy), "routed pocket", font=font, fill=(0, 0, 0), anchor="lm")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.output)
    print("wrote", args.output)


if __name__ == "__main__":
    main()
