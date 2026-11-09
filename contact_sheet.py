"""Tile the preview shots onto one labelled sheet, so the whole weapon can be
judged at a glance instead of opening nine files.

Usage: python3 contact_sheet.py SHOTDIR OUT.png
"""
import sys, os, glob
from PIL import Image, ImageDraw

SRC, OUT = sys.argv[1], sys.argv[2]
COLS = 3
CELL = (760, 520)
PAD = 10
BAR = 26
BG = (18, 20, 24)

shots = sorted(glob.glob(os.path.join(SRC, "[0-9][0-9]_*.png")))
if not shots:
    raise SystemExit(f"no shots in {SRC}")
rows = (len(shots) + COLS - 1) // COLS
sheet = Image.new("RGB", (COLS * (CELL[0] + PAD) + PAD,
                          rows * (CELL[1] + BAR + PAD) + PAD), BG)
draw = ImageDraw.Draw(sheet)
for i, p in enumerate(shots):
    im = Image.open(p).convert("RGB")
    im.thumbnail(CELL)
    x = PAD + (i % COLS) * (CELL[0] + PAD)
    y = PAD + (i // COLS) * (CELL[1] + BAR + PAD)
    sheet.paste(im, (x + (CELL[0] - im.width) // 2, y + BAR))
    label = os.path.basename(p)[3:-4].replace("_", " ")
    draw.text((x + 6, y + 7), label, fill=(210, 214, 220))
sheet.save(OUT)
print(f"contact sheet: {OUT}  ({len(shots)} views)")
